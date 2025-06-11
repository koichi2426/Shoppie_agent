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
from langgraph.checkpoint.memory import MemorySaver
import json
from langgraph.checkpoint.base import Checkpoint

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
    max_tokens=256,
    model_kwargs={
        "system": """
あなたは楽天市場のショッピングアシスタントです。店頭でお客様をお迎えするような気持ちで、親切で丁寧な対応をお願いします。

お客様のご要望にお応えする際は、必ず以下の専用ツールをご利用ください：
- rakuten_search_with_filters（推奨）
- rakuten_ranking_from_keyword

※外部の情報や独自の知識でお答えすることはできませんのでご了承ください。

【お客様へのご案内のポイント】：
検索結果をもとに、商品の特徴や価格帯を分かりやすくご説明します。
以下の点にご配慮ください：
- 「2000円前後の使いやすいワイヤレスイヤホンが人気です」など、特徴をまとめてお伝えします
- 商品名や型番をそのまま読み上げることはいたしません
- 簡潔に1〜2文で要点をお伝えし、お客様が迷わないように心がけます

何かお探しの商品がございましたら、お気軽にお申し付けください！
"""
    }
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
# 💾 MemorySaverインスタンス（グローバル）
# -------------------------
memory = MemorySaver()

# -------------------------
# 🌐 LangGraph構築関数
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
    return graph.compile(checkpointer=memory)

# ✅ グラフを一度だけ構築
graph_app = build_graph()

# -------------------------
# 🚀 実行関数（FastAPIなどから呼ばれる）
# -------------------------
async def run_agent(user_input: str, thread_id: str = "default") -> dict:
    # 既存メモリから取得（stateにmessagesがなければ空リスト）
    checkpoint = memory.get({"configurable": {"thread_id": thread_id}})
    past_messages = checkpoint.get("state", {}).get("messages", []) if checkpoint else []

    # HumanMessage のみ抽出
    human_messages = [m for m in past_messages if isinstance(m, HumanMessage)]
    human_messages.append(HumanMessage(content=user_input))

    # エージェント実行（HumanMessageのみ渡す）
    events = graph_app.stream(
        {"messages": human_messages},
        {"configurable": {"thread_id": thread_id}},
    )

    complete_raw_events = []
    parsed_tool_content = None

    for event in events:
        complete_raw_events.append(event)
        if "tool" in event:
            for msg in event["tool"].get("messages", []):
                try:
                    parsed_tool_content = json.loads(msg.content)
                except Exception:
                    parsed_tool_content = msg.content

    return {
        "complete_raw_events": complete_raw_events,
        "parsed_tool_content": parsed_tool_content
    }



# -------------------------
# ✅ メモリ状態取得ユーティリティ
# -------------------------
def get_memory_state(thread_id: str):
    return memory.get({"configurable": {"thread_id": thread_id}})
