import cv2
from ultralytics import YOLO
import threading
import time
import json
from backend.db.database import SessionLocal
from backend.db.models import Event
from backend.core.redis_client import get_redis_client

# ── COCO class IDs we care about ─────────────────────────────────────────────
PERSON     = 0
BICYCLE    = 1
CAR        = 2
MOTORCYCLE = 3
BUS        = 5
TRUCK      = 7
DETECT_CLASSES = [PERSON, BICYCLE, CAR, MOTORCYCLE, BUS, TRUCK]

CLASS_NAMES = {
    PERSON: "person", BICYCLE: "bicycle", CAR: "car",
    MOTORCYCLE: "motorcycle", BUS: "bus", TRUCK: "truck",
}
VEHICLE_CLASSES = {BICYCLE, CAR, MOTORCYCLE, BUS, TRUCK}

# Helmet model (keremberke/yolov8n-helmet-detection) class IDs
HELMET_ON  = 0   # "Hardhat"
NO_HELMET  = 1   # "NO-Hardhat"
# ─────────────────────────────────────────────────────────────────────────────


class StreamProcessor:
    def __init__(self, stream_id: int, source_url: str):
        self.stream_id   = stream_id
        self.source_url  = source_url
        self.file_path   = source_url

        # Main detection model (loaded eagerly so it's ready right away)
        self.model = YOLO("yolo11n.pt")

        # Specialized models – loaded lazily on first use
        self._helmet_model = None
        self._plate_model  = None
        self._ocr          = None

        self.is_running = False
        self.thread     = None

        # Tracking bookkeeping
        self.tracked_persons  = set()          # person track IDs seen
        self.tracked_vehicles = {}             # track_id -> cls int
        self.person_helmet_status = {}         # track_id -> "helmet"|"no_helmet"
        self.seen_plates = set()               # plate strings already logged

        # ── Real-time stats ──────────────────────────────────────────────────
        self.frames_processed = 0
        self.total_frames     = 0
        self.fps              = 0.0
        self.status           = "idle"

        self.persons_count    = 0
        self.helmet_count     = 0
        self.no_helmet_count  = 0
        self.vehicle_counts   = {"car": 0, "motorcycle": 0, "bicycle": 0, "bus": 0, "truck": 0}
        self.total_vehicles   = 0
        self.license_plates   = []   # list of plate strings (most-recent last)

    # ── Lazy model loaders ────────────────────────────────────────────────────

    def _get_helmet_model(self):
        if self._helmet_model is None:
            try:
                from huggingface_hub import hf_hub_download
                path = hf_hub_download(
                    repo_id="keremberke/yolov8n-helmet-detection",
                    filename="best.pt",
                )
                self._helmet_model = YOLO(path)
                print("✅ Helmet detection model loaded")
            except Exception as e:
                print(f"⚠️  Helmet model unavailable: {e}")
                self._helmet_model = False   # sentinel: don't retry
        return self._helmet_model if self._helmet_model else None

    def _get_plate_model(self):
        """
        No dedicated plate-detection model is loaded.
        Plates are instead read via OCR on the lower region of every vehicle crop.
        This method returns None but is kept for structural symmetry.
        """
        return None



    def _get_ocr(self):
        if self._ocr is None:
            try:
                import easyocr
                self._ocr = easyocr.Reader(['en'], gpu=False, verbose=False)
                print("✅ EasyOCR loaded")
            except Exception as e:
                print(f"⚠️  EasyOCR unavailable: {e}")
                self._ocr = False
        return self._ocr if self._ocr else None

    # ── Public API ────────────────────────────────────────────────────────────

    def get_stats(self):
        progress = 0
        if self.total_frames > 0:
            progress = min(100, round(self.frames_processed / self.total_frames * 100, 1))
        return {
            "stream_id":      self.stream_id,
            "status":         self.status,
            "frames_processed": self.frames_processed,
            "total_frames":   self.total_frames,
            "progress":       progress,
            "fps":            round(self.fps, 1),
            # persons
            "persons_count":  self.persons_count,
            "helmet_count":   self.helmet_count,
            "no_helmet_count": self.no_helmet_count,
            # vehicles
            "vehicle_counts": self.vehicle_counts,
            "total_vehicles": self.total_vehicles,
            # plates
            "license_plates": self.license_plates[-10:],
            "file_path":      self.file_path,
        }

    def start(self):
        self.is_running = True
        self.status     = "processing"
        self.thread = threading.Thread(target=self._process_stream, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        self.status = "stopped"

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _log(self, db, redis_client, event_type, obj_id, desc, meta=None):
        """Persist event to Postgres and publish to Redis."""
        try:
            ev = Event(
                stream_id=self.stream_id,
                event_type=event_type,
                object_id=str(obj_id),
                description=desc,
                event_metadata=meta or {},
            )
            db.add(ev)
            db.commit()
            db.refresh(ev)
            if redis_client:
                redis_client.publish("alerts", json.dumps({
                    "event_id":    ev.id,
                    "stream_id":   self.stream_id,
                    "type":        event_type,
                    "description": desc,
                }))
        except Exception as exc:
            print(f"Event log error: {exc}")
            try:
                db.rollback()
            except Exception:
                pass

    # ── Main processing loop ──────────────────────────────────────────────────

    def _process_stream(self):
        cap = cv2.VideoCapture(self.source_url)
        if not cap.isOpened():
            print(f"Cannot open: {self.source_url}")
            self.status = "error"
            return

        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        db            = SessionLocal()
        redis_client  = get_redis_client()

        t_start     = time.time()
        frame_count = 0

        try:
            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    break   # end of video / stream

                frame_count += 1
                self.frames_processed = frame_count

                # Update FPS every 15 frames
                if frame_count % 15 == 0:
                    elapsed  = time.time() - t_start
                    self.fps = frame_count / elapsed if elapsed > 0 else 0

                # ── 1. Person + Vehicle detection & tracking ──────────────────
                results = self.model.track(
                    frame,
                    persist=True,
                    classes=DETECT_CLASSES,
                    tracker="bytetrack.yaml",
                    verbose=False,
                    conf=0.35,
                )

                person_crops = []   # [(track_id, x1, y1, x2, y2)]

                if results[0].boxes is not None and results[0].boxes.id is not None:
                    boxes  = results[0].boxes.xyxy.cpu().numpy()
                    ids    = results[0].boxes.id.int().cpu().tolist()
                    clses  = results[0].boxes.cls.int().cpu().tolist()
                    confs  = results[0].boxes.conf.cpu().numpy()

                    for box, tid, cls, conf in zip(boxes, ids, clses, confs):
                        x1, y1, x2, y2 = map(int, box)

                        if cls == PERSON:
                            if tid not in self.tracked_persons:
                                self.tracked_persons.add(tid)
                                self.persons_count = len(self.tracked_persons)
                                self._log(db, redis_client,
                                    "person_detected", tid,
                                    f"Person #{tid} entered frame",
                                    {"bbox": box.tolist(), "confidence": float(conf)})
                            # always collect for helmet check
                            person_crops.append((tid, x1, y1, x2, y2))

                        elif cls in VEHICLE_CLASSES and tid not in self.tracked_vehicles:
                            self.tracked_vehicles[tid] = cls
                            vname = CLASS_NAMES[cls]
                            self.vehicle_counts[vname] += 1
                            self.total_vehicles = sum(self.vehicle_counts.values())
                            self._log(db, redis_client,
                                "vehicle_detected", tid,
                                f"{vname.capitalize()} #{tid} detected",
                                {"vehicle_type": vname, "bbox": box.tolist(), "confidence": float(conf)})

                # ── 2. Helmet detection – every 3rd frame on person crops ─────
                if person_crops and frame_count % 3 == 0:
                    hmodel = self._get_helmet_model()
                    if hmodel:
                        for tid, x1, y1, x2, y2 in person_crops:
                            if tid in self.person_helmet_status:
                                continue   # already classified this person

                            # Crop upper half of person bounding box (head area)
                            head_bottom = min(frame.shape[0], y1 + max(1, (y2 - y1) // 2))
                            crop = frame[max(0, y1):head_bottom, max(0, x1):min(frame.shape[1], x2)]
                            if crop.size == 0:
                                continue

                            h_res = hmodel(crop, verbose=False, conf=0.45)
                            if h_res[0].boxes is not None and len(h_res[0].boxes):
                                best  = max(h_res[0].boxes, key=lambda b: float(b.conf[0]))
                                hcls  = int(best.cls[0])
                                hconf = float(best.conf[0])

                                if hcls == HELMET_ON:
                                    self.person_helmet_status[tid] = "helmet"
                                    self.helmet_count += 1
                                    self._log(db, redis_client,
                                        "helmet_on", tid,
                                        f"✅ Person #{tid} is wearing a helmet ({hconf:.0%})",
                                        {"confidence": hconf})
                                else:   # NO_HELMET
                                    self.person_helmet_status[tid] = "no_helmet"
                                    self.no_helmet_count += 1
                                    self._log(db, redis_client,
                                        "no_helmet", tid,
                                        f"🚨 Person #{tid} NOT wearing a helmet! ({hconf:.0%})",
                                        {"confidence": hconf})

                # ── 3. License-plate OCR on vehicle crops – every 5th frame ──
                if frame_count % 5 == 0 and self.tracked_vehicles:
                    ocr = self._get_ocr()
                    if ocr and results[0].boxes is not None and results[0].boxes.id is not None:
                        boxes  = results[0].boxes.xyxy.cpu().numpy()
                        ids    = results[0].boxes.id.int().cpu().tolist()
                        clses  = results[0].boxes.cls.int().cpu().tolist()

                        for box, tid, cls in zip(boxes, ids, clses):
                            if cls not in VEHICLE_CLASSES:
                                continue
                            x1, y1, x2, y2 = map(int, box)
                            # Plate is always in the lower ~35% of the vehicle bbox
                            plate_y1 = y1 + int((y2 - y1) * 0.62)
                            plate_crop = frame[max(0, plate_y1):y2, max(0, x1):min(frame.shape[1], x2)]
                            if plate_crop.size == 0 or plate_crop.shape[0] < 10 or plate_crop.shape[1] < 20:
                                continue
                            try:
                                # Upscale crop for better OCR accuracy
                                import cv2 as _cv2
                                h, w = plate_crop.shape[:2]
                                plate_up = _cv2.resize(plate_crop, (w * 3, h * 3), interpolation=_cv2.INTER_CUBIC)
                                texts = ocr.readtext(
                                    plate_up, detail=0,
                                    allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                                    min_size=10,
                                )
                                plate_text = "".join(texts).strip().upper()
                                # Must be ≥5 chars and alphanumeric to avoid noise
                                if (plate_text and len(plate_text) >= 5
                                        and any(c.isdigit() for c in plate_text)
                                        and plate_text not in self.seen_plates):
                                    self.seen_plates.add(plate_text)
                                    self.license_plates.append(plate_text)
                                    self._log(db, redis_client,
                                        "license_plate", plate_text,
                                        f"License plate: {plate_text} (vehicle #{tid})",
                                        {"plate": plate_text, "vehicle_id": tid})
                            except Exception:
                                pass

        except Exception as exc:
            import traceback
            print(f"Stream processing error: {exc}")
            traceback.print_exc()
            self.status = "error"
        finally:
            cap.release()
            db.close()
            if self.status not in ("error", "stopped"):
                self.status = "done"
                elapsed  = time.time() - t_start
                self.fps = round(frame_count / elapsed, 1) if elapsed > 0 else 0
