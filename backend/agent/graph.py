from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from backend.agent.tools import search_events_by_semantics, query_events_by_sql, count_events, get_video_info, analyze_video_visually
from backend.core.config import settings

def get_agent():
    # Initialize the LLM (Using Groq for fast, free inference)
    llm = ChatGroq(model_name="llama-3.1-8b-instant", api_key=settings.GROQ_API_KEY)
    
    tools = [search_events_by_semantics, query_events_by_sql, count_events, get_video_info, analyze_video_visually]
    
    # Create the ReAct agent graph
    agent_executor = create_react_agent(llm, tools)
    return agent_executor

def run_query(user_query: str):
    agent = get_agent()
    # Execute the query through the agent
    response = agent.invoke({"messages": [("user", f"You are SentraVision's Security AI. You monitor events and answer queries. Answer this: {user_query}")]})
    
    return response["messages"][-1].content
