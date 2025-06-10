import os
import boto3
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain.tools import tool
from app.tools.rakuten_api import (
    search_products,
    get_ranking,
    search_genres,
    get_new_arrivals,
    get_lowest_price,
    get_product_detail,
)
from app.memory import memory

# ✅ .env 読み込み
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

# ✅ 認証確認
print("✅ BEDROCK Key:", os.getenv("BEDROCK_AWS_ACCESS_KEY_ID"))

# ✅ boto3 client を構築
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("BEDROCK_AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("BEDROCK_AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("BEDROCK_AWS_SECRET_ACCESS_KEY"),
)

# 🤖 Claude 3.5 Haiku (Bedrock)
llm = ChatBedrock(
    model=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"),
    client=bedrock_client,
    temperature=0.7,
)

# 🛠 楽天APIツール定義
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

# 🔧 利用するツール一覧
tools = [
    rakuten_search,
    rakuten_ranking,
    rakuten_genre_search,
    rakuten_new_arrivals,
    rakuten_lowest_price,
    rakuten_product_detail,
]

# 🧠 エージェント初期化（Claude + Memory + ReAct）
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True,  # Claudeの出力エラー対策
)

# 🎯 ユーザー入力を処理する非同期関数
async def run_agent(user_input: str) -> str:
    try:
        return await agent.arun(user_input)
    except Exception as e:
        return f"[ERROR] {str(e)}"
