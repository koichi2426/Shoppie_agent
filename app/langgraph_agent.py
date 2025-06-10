# langgraph_agent.py

import os
import boto3
from dotenv import load_dotenv
from typing_extensions import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_aws import ChatBedrock
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
import json

# ✅ 楽天APIのStructuredToolラッパー
from app.tools.rakuten_tool_wrappers import (
    search_products_with_filters_tool,
    keyword_to_ranking_products_tool
)

# -------------------------
# ✅ 環境変数読み込み & Bedrock設定
# -------------------------
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("BEDROCK_AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("BEDROCK_AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("BEDROCK_AWS_SECRET_ACCESS_KEY"),
)

# 🤖 Claude 3.5（Tool使用を強制）
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
"""
)

# -------------------------
# 💾 ステート定義
# -------------------------
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# -------------------------
# 🤖 LLMノード
# -------------------------
def llm_node(state: State):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "楽天ショッピングアシスタントとして、必ずStructuredToolを使って応答してください。"),
        MessagesPlaceholder(variable_name="messages")
    ])
    agent = prompt | llm.bind_tools([
        search_products_with_filters_tool,
        keyword_to_ranking_products_tool
    ])
    result = agent.invoke(state)
    return {"messages": result}

# -------------------------
# 🧰 Toolノード
# -------------------------
tool_node = ToolNode([
    search_products_with_filters_tool,
    keyword_to_ranking_products_tool
])

# -------------------------
# 🧠 LangGraph構築
# -------------------------
def build_graph():
    graph = StateGraph(State)

    graph.add_node("llm_agent", llm_node)
    graph.add_node("tool", tool_node)

    graph.add_edge(START, "llm_agent")

    graph.add_conditional_edges("llm_agent", tools_condition, {
        "tools": "tool",
        "__end__": END
    })

    graph.add_edge("tool", "llm_agent")
    graph.add_edge("llm_agent", END)

    return graph.compile()

# -------------------------
# 🚀 実行テスト
# -------------------------
if __name__ == "__main__":
    app = build_graph()
    print("🛍️ Shoppieエージェントへようこそ！")
    user_input = input("ユーザーの発話を入力してください：")
    events = app.stream({"messages": [("user", user_input)]})
    for event in events:
        print(event)

# -------------------------
# 🌐 FastAPIから使う関数
# -------------------------
async def run_agent(user_input: str) -> dict:
    app = build_graph()
    events = app.stream({"messages": [HumanMessage(content=user_input)]})

    complete_raw_events = []  # 🌟 完全な生データ用
    parsed_tool_content = None  # 🌟 パースされたツール結果

    for event in events:
        # 🌟 完全な生データを一切パースせずに保存
        complete_raw_events.append(event)
        
        # 🌟 toolノードのToolMessage.contentだけ別途パース
        if "tool" in event:
            for msg in event["tool"].get("messages", []):
                if isinstance(msg, ToolMessage):
                    try:
                        parsed_tool_content = json.loads(msg.content)
                    except Exception:
                        parsed_tool_content = msg.content

    return {
        "complete_raw_events": complete_raw_events,  # 🌟 完全な生データ（オブジェクトそのまま）
        "parsed_tool_content": parsed_tool_content   # 🌟 パースされたツール結果
    }