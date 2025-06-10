import os
import boto3
from dotenv import load_dotenv
from typing import Optional, Dict
from pydantic import BaseModel
from langchain_aws import ChatBedrock
from langchain.tools import StructuredTool
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent
from app.tools.rakuten_api import search_products_with_filters, keyword_to_ranking_products

# ✅ .env読み込み
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

# ✅ Bedrockクライアント
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("BEDROCK_AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("BEDROCK_AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("BEDROCK_AWS_SECRET_ACCESS_KEY"),
)

# 🤖 Claude 3.5 Haiku
llm = ChatBedrock(
    model=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"),
    client=bedrock_client,
    temperature=0.7,
)

# 🧩 StructuredTool定義
class RakutenSearchInput(BaseModel):
    keyword: str
    filters: Optional[Dict] = {}

def rakuten_search_with_filters_func(keyword: str, filters: Optional[Dict] = {}) -> str:
    return search_products_with_filters(keyword, filters or {})

rakuten_search_tool = StructuredTool.from_function(
    func=rakuten_search_with_filters_func,
    name="rakuten_search_with_filters",
    description="楽天市場で商品を検索します。keywordとfilters（任意）を指定できます。",
    args_schema=RakutenSearchInput,
)

rakuten_ranking_tool = StructuredTool.from_function(
    func=keyword_to_ranking_products,
    name="rakuten_ranking_from_keyword",
    description="キーワードに関連する楽天ジャンルの売れ筋ランキングを取得します。",
)

tools = [rakuten_search_tool, rakuten_ranking_tool]

# ✅ LangGraph公式の prebuilt ReAct Agent を使って初期化
agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt="あなたは楽天商品を探して提案してくれるとても親切なショッピングアシスタントです。"
)

# 🎯 ユーザー入力を処理する非同期関数（Claude応答 + Tool出力）
async def run_agent(user_input: str) -> dict:
    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_input}]}
        )

        # Claudeのメッセージを取得
        assistant_message = ""
        for message in reversed(result.get("messages", [])):
            if isinstance(message, AIMessage):
                assistant_message = message.content
                break

        # toolの実行履歴を抽出（intermediate_stepsを使う）
        tool_response = []
        for step in result.get("intermediate_steps", []):
            tool_response.append({
                "tool": getattr(step.tool, "name", "unknown"),
                "input": step.tool_input,
                "output": step.output,
            })

        return {
            "message": assistant_message,
            "tool_response": tool_response
        }

    except Exception as e:
        return {
            "message": f"[ERROR] {str(e)}",
            "tool_response": []
        }
