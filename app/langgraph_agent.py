# ----------------------------
# 必要なライブラリをインポート
# ----------------------------
import os
import boto3
import time
import json
from typing_extensions import Annotated, TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from langchain_aws import ChatBedrock
from langgraph.checkpoint.memory import MemorySaver

# ----------------------------
# Yahoo API用のStructuredToolをインポート
# ----------------------------
from app.tools.yahoo_tool_wrappers import (
    search_yahoo_products_with_filters_tool
)

# ----------------------------
# .envファイルを読み込む
# ----------------------------
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

# ----------------------------
# AWS Bedrockクライアントの初期化
# ----------------------------
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("BEDROCK_AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("BEDROCK_AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("BEDROCK_AWS_SECRET_ACCESS_KEY"),
)

# ----------------------------
# Claude (Bedrock) 設定
# ----------------------------
llm = ChatBedrock(
    model=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"),
    client=bedrock_client,
    temperature=0.7,
    max_tokens=1024,
    model_kwargs={
        "system": """
あなたはショッピングアシスタントです。店頭でお客様をお迎えするような気持ちで、親切で丁寧な対応をお願いします。
お客様のご要望にお応えする際は、必ず以下の専用ツールをご利用ください：
- yahoo_search_with_filters（推奨）
"""
    }
)

# ----------------------------
# LangGraphで使うステート定義
# ----------------------------
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# ----------------------------
# Claudeにプロンプトと履歴を渡すノード
# ----------------------------
def llm_node(state: State):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "ショッピングアシスタントとして、必ずStructuredToolを使って応答してください。"),
        MessagesPlaceholder(variable_name="messages")
    ])
    agent = prompt | llm.bind_tools([
        search_yahoo_products_with_filters_tool
    ])
    result = agent.invoke(state)
    return {"messages": result}

# ----------------------------
# StructuredToolノード定義
# ----------------------------
tool_node = ToolNode([
    search_yahoo_products_with_filters_tool
])

# ----------------------------
# チェックポイントメモリ定義
# ----------------------------
memory = MemorySaver(max_token_limit=1000)

# ----------------------------
# グラフ構築関数
# ----------------------------
def build_graph():
    graph = StateGraph(State)
    graph.add_node("llm_agent", llm_node)
    graph.add_node("tool", tool_node)
    graph.add_edge(START, "llm_agent")
    graph.add_conditional_edges("llm_agent", tools_condition, {
        "tools": "tool",
        "__end__": END
    })
    graph.add_edge("tool", END)
    return graph.compile(checkpointer=memory)

graph_app = build_graph()

# ----------------------------
# グラフを非同期実行する関数
# ----------------------------
async def run_agent(user_input: str, thread_id: str = "default") -> dict:
    checkpoint = memory.get({"configurable": {"thread_id": thread_id}})
    past_messages = checkpoint.get("state", {}).get("messages", []) if checkpoint else []
    human_messages = [m for m in past_messages if isinstance(m, HumanMessage)]
    human_messages.append(HumanMessage(content=user_input))

    def run_with_retry():
        delay = 1
        for _ in range(5):
            try:
                return list(graph_app.stream(
                    {"messages": human_messages},
                    {"configurable": {"thread_id": thread_id}},
                ))
            except Exception as e:
                if "ThrottlingException" in str(e):
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise e
        raise RuntimeError("Claude API throttled after multiple retries.")

    complete_raw_events = []
    parsed_tool_content = None

    try:
        for event in run_with_retry():
            complete_raw_events.append(event)
            if "tool" in event:
                for msg in event["tool"].get("messages", []):
                    try:
                        parsed_tool_content = json.loads(msg.content)
                    except Exception:
                        parsed_tool_content = msg.content
    except Exception as e:
        return {"response": {"error": str(e)}}

    return {
        "complete_raw_events": complete_raw_events,
        "parsed_tool_content": parsed_tool_content
    }

# ----------------------------
# 現在の会話履歴を取得
# ----------------------------
def get_memory_state(thread_id: str):
    return memory.get({"configurable": {"thread_id": thread_id}})
