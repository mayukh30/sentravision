from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from backend.agent.tools import create_session_tools
from backend.core.config import settings

def get_agent(session_id: str = None):
    # Initialize the LLM (Using Groq for fast, free inference)
    llm = ChatGroq(model_name="llama-3.1-8b-instant", api_key=settings.GROQ_API_KEY)
    
    # Create session-scoped tools so the agent only accesses this user's data
    tools = create_session_tools(session_id)
    
    # Create the ReAct agent graph
    agent_executor = create_react_agent(llm, tools)
    return agent_executor

def run_query(user_query: str, session_id: str = None):
    agent = get_agent(session_id)
    # Execute the query through the agent
    response = agent.invoke({"messages": [("user", f"You are SentraVision's Security AI. You monitor events and answer queries. Answer this: {user_query}")]})
    
    return response["messages"][-1].content
