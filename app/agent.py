import os
import boto3
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain.tools import tool
from app.tools.rakuten_api import (
    search_products_with_filters,
    keyword_to_ranking_products,
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
def rakuten_search_with_filters(input: dict) -> str:
    """
    楽天市場でキーワードと条件を指定して商品を検索します。

    🔸 input は以下の形式の辞書です:
    {
        "keyword": "検索キーワード（例：ノートパソコン）",
        "filters": {
            "minPrice": 最低価格（例:3000）,         # 任意
            "maxPrice": 最高価格（例:10000）,        # 任意
            "postageFree": 1 で送料無料のみに限定,     # 任意
            "availability": 1 で在庫ありのみに限定,   # 任意
            "sort": 並び順（以下のいずれか）             # 任意
                - +itemPrice（価格が安い順）
                - -itemPrice（価格が高い順）
                - +reviewCount（レビュー件数が少ない順）
                - -reviewCount（レビュー件数が多い順）
                - +reviewAverage（レビュー評価が低い順）
                - -reviewAverage（レビュー評価が高い順）
                - +affiliateRate（報酬率が低い順）
                - -affiliateRate（報酬率が高い順）
        }
    }

    🔹 filters が指定されない場合、通常検索として動作します。
    """
    return search_products_with_filters(input["keyword"], input.get("filters", {}))


@tool
def rakuten_ranking_from_keyword(keyword: str) -> str:
    """楽天市場でキーワードからジャンルを推定し、そのジャンルの売れ筋ランキングを取得します。"""
    return keyword_to_ranking_products(keyword)

# 🔧 利用するツール一覧
tools = [
    rakuten_search_with_filters,
    rakuten_ranking_from_keyword,
]

# 🧠 エージェント初期化（Claude + Memory + ReAct）
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True,
)

# 🎯 ユーザー入力を処理する非同期関数
async def run_agent(user_input: str) -> str:
    try:
        return await agent.arun(user_input)
    except Exception as e:
        return f"[ERROR] {str(e)}"
