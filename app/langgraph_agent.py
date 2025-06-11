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
from langgraph.checkpoint.base import Checkpoint

# ✅ StructuredToolラッパー
from app.tools.rakuten_tool_wrappers import (
    search_products_with_filters_tool,
    keyword_to_ranking_products_tool
)

# ✅ .env読込 & Bedrockクライアント設定
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("BEDROCK_AWS_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("BEDROCK_AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("BEDROCK_AWS_SECRET_ACCESS_KEY"),
)

llm = ChatBedrock(
    model=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"),
    client=bedrock_client,
    temperature=0.7,
    max_tokens=1024,
    model_kwargs={
        "system": """
あなたは楽天市場のショッピングアシスタントです。店頭でお客様をお迎えするような気持ちで、親切で丁寧な対応をお願いします。
お客様のご要望にお応えする際は、必ず以下の専用ツールをご利用ください：
- rakuten_search_with_filters（推奨）
- rakuten_ranking_from_keyword
"""
    }
)

# ✅ LangGraphステート定義
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

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

tool_node = ToolNode([
    search_products_with_filters_tool,
    keyword_to_ranking_products_tool
])

# ✅ メモリ定義（人間の発言のみ使用）
memory = MemorySaver()

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

graph_app = build_graph()

# ✅ 実行関数（人間の発話のみ保存）
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

# ✅ メモリ取得ユーティリティ
def get_memory_state(thread_id: str):
    return memory.get({"configurable": {"thread_id": thread_id}})
