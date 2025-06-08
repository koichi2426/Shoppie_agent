import os
from dotenv import load_dotenv
from langchain_community.chat_models import BedrockChat
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain.tools import tool
from app.rakuten_api import (
    search_products,
    get_ranking,
    search_genres,
    get_new_arrivals,
    get_lowest_price,
    get_product_detail,
)
from app.memory import memory

load_dotenv()

@tool
def rakuten_search(query: str) -> str:
    """楽天市場で商品を検索します。"""
    return search_products(query)

@tool
def rakuten_ranking(genre_id: str = "100283") -> str:
    """楽天市場の人気ランキングを取得します（ジャンルID指定）。"""
    return get_ranking(genre_id)

@tool
def rakuten_genre_search(keyword: str) -> str:
    """キーワードに関連する楽天ジャンルを検索します。"""
    return search_genres(keyword)

@tool
def rakuten_new_arrivals(keyword: str) -> str:
    """指定したキーワードで新着商品を検索します。"""
    return get_new_arrivals(keyword)

@tool
def rakuten_lowest_price(keyword: str) -> str:
    """指定したキーワードで最安値の商品を検索します。"""
    return get_lowest_price(keyword)

@tool
def rakuten_product_detail(item_code: str) -> str:
    """指定したitemCodeの商品詳細情報を取得します。"""
    return get_product_detail(item_code)

# Claude 3.5 Haiku を Bedrock 経由で初期化
llm = BedrockChat(
    model_id="anthropic.claude-3-haiku-20240307",
    region_name=os.getenv("AWS_REGION")
)

# 使用可能なツール一覧
tools = [
    rakuten_search,
    rakuten_ranking,
    rakuten_genre_search,
    rakuten_new_arrivals,
    rakuten_lowest_price,
    rakuten_product_detail
]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    memory=memory,
    verbose=True
)

async def run_agent(user_input: str) -> str:
    try:
        return agent.run(user_input)
    except Exception as e:
        return f"[ERROR] {str(e)}"
