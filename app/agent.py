import os
from langchain.llms import Bedrock
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain.tools import tool
from app.rakuten_api import search_products
from app.memory import memory
from dotenv import load_dotenv

load_dotenv()

@tool
def rakuten_search(query: str) -> str:
    """楽天市場で商品を検索します。"""
    return search_products(query)

llm = Bedrock(
    region_name=os.getenv("AWS_REGION"),
    model_id="anthropic.claude-3-haiku-20240307",
)

tools = [rakuten_search]

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    memory=memory,
    verbose=True
)

async def run_agent(user_input: str) -> str:
    return agent.run(user_input)
