import os
import boto3
from dotenv import load_dotenv
from typing import Optional
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
    system="""
あなたは楽天APIと連携したショッピングアシスタントです。
ユーザーのリクエストに対しては、必ず以下のいずれかのStructuredToolを使ってください：

- rakuten_search_with_filters（推奨）
- rakuten_ranking_from_keyword

ツールを使わずに、独自知識で回答することは禁止されています。
StructuredToolを使うには、以下のような形式で入力データを構成してください：

{
  "keyword": "イヤホン",
  "filters": {
    "maxPrice": 10000,
    "sort": "-reviewCount",
    "availability": 1
  }
}

この形式で `rakuten_search_with_filters` を使えば、商品検索ができます。正確に従ってください。
"""
)

# 🧩 StructuredTool定義
class RakutenSearchFilters(BaseModel):
    minPrice: Optional[int] = None
    maxPrice: Optional[int] = None
    postageFree: Optional[int] = None
    availability: Optional[int] = None
    sort: Optional[str] = None

class RakutenSearchInput(BaseModel):
    keyword: str
    filters: Optional[RakutenSearchFilters] = None

def rakuten_search_with_filters_func(keyword: str, filters: Optional[RakutenSearchFilters] = None) -> str:
    return search_products_with_filters(keyword, filters.dict() if filters else {})

rakuten_search_tool = StructuredTool.from_function(
    func=rakuten_search_with_filters_func,
    name="rakuten_search_with_filters",
    description="""
楽天市場で商品を検索します。以下のような形式で入力してください：
{
  "keyword": "イヤホン",
  "filters": {
    "minPrice": 3000,
    "maxPrice": 10000,
    "postageFree": 1,
    "availability": 1,
    "sort": "-reviewCount"
  }
}
filtersは任意ですが、価格帯や送料、在庫有無を指定すると精度が上がります。
""",
    args_schema=RakutenSearchInput,
)

rakuten_ranking_tool = StructuredTool.from_function(
    func=keyword_to_ranking_products,
    name="rakuten_ranking_from_keyword",
    description="キーワードに関連する楽天ジャンルの売れ筋ランキングを取得します。"
)

tools = [rakuten_search_tool, rakuten_ranking_tool]

# ✅ LangGraph prebuilt ReAct Agent で初期化
agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt="""
あなたは楽天商品を探して提案してくれるとても親切なショッピングアシスタントです。
ツールを必ず使って、ユーザーの要望に合った楽天商品を提案してください。
"""
)

# 🎯 ユーザー入力を処理する非同期関数（Claude応答 + Tool出力）
async def run_agent(user_input: str) -> dict:
    try:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": user_input}]})

        assistant_message = ""
        for message in reversed(result.get("messages", [])):
            if isinstance(message, AIMessage):
                assistant_message = message.content
                break

        tool_response = []
        for step in result.get("intermediate_steps", []):
            tool_response.append({
                "tool": getattr(step.tool, "name", "unknown"),
                "input": step.tool_input,
                "output": step.output,
            })

        # Claudeがツールを呼ばなかった場合はエラーを返す
        if not tool_response:
            return {
                "message": "[ERROR] Claudeはツールを使用せずに応答しました。プロンプトやdescriptionを見直してください。",
                "tool_response": []
            }

        return {
            "message": assistant_message,
            "tool_response": tool_response
        }

    except Exception as e:
        return {
            "message": f"[ERROR] {str(e)}",
            "tool_response": []
        }