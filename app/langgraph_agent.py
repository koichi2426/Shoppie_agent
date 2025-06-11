# ----------------------------
# 必要なライブラリをインポート
# ----------------------------
import os
import boto3  # AWSサービス用クライアントライブラリ
import time
import json
from typing_extensions import Annotated, TypedDict
from dotenv import load_dotenv  # .envファイルから環境変数を読み込む
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from langchain_aws import ChatBedrock
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import Checkpoint

# ----------------------------
# 楽天API用のStructuredToolをインポート
# ----------------------------
from app.tools.rakuten_tool_wrappers import (
    search_products_with_filters_tool,     # 商品検索（フィルターあり）
    keyword_to_ranking_products_tool       # キーワードからランキング取得
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
# Claude (Bedrock) をLangChain経由で使えるように設定
# ----------------------------
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

# ----------------------------
# LangGraphで使うステート（状態）の型定義
# ----------------------------
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# ----------------------------
# Claudeにプロンプトとメッセージ履歴を渡して実行するノード
# ----------------------------
def llm_node(state: State):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "楽天ショッピングアシスタントとして、必ずStructuredToolを使って応答してください。"),
        MessagesPlaceholder(variable_name="messages")  # 会話履歴をプロンプトに挿入
    ])
    agent = prompt | llm.bind_tools([
        search_products_with_filters_tool,
        keyword_to_ranking_products_tool
    ])
    result = agent.invoke(state)
    return {"messages": result}

# ----------------------------
# StructuredToolノードの定義（ツール実行専用）
# ----------------------------
tool_node = ToolNode([
    search_products_with_filters_tool,
    keyword_to_ranking_products_tool
])

# ----------------------------
# チェックポイント（会話の履歴）を記憶するメモリ
# ----------------------------
memory = MemorySaver()

# ----------------------------
# グラフ構築関数（LangGraphの状態遷移定義）
# ----------------------------
def build_graph():
    graph = StateGraph(State)

    # ノード定義
    graph.add_node("llm_agent", llm_node)
    graph.add_node("tool", tool_node)

    # スタート → Claude（llm_agent）
    graph.add_edge(START, "llm_agent")

    # Claudeの出力に応じて分岐
    graph.add_conditional_edges("llm_agent", tools_condition, {
        "tools": "tool",   # Claudeがツールを使う → toolノードへ
        "__end__": END     # ツール不要 → 終了
    })

    # ✅ ツール実行後はClaudeに戻さず、直接終了
    graph.add_edge("tool", END)

    return graph.compile(checkpointer=memory)


# グラフをビルドしてインスタンス化
graph_app = build_graph()

# ----------------------------
# ユーザー入力を受け取り、グラフを非同期で実行する関数
# ----------------------------
async def run_agent(user_input: str, thread_id: str = "default") -> dict:
    # 以前の会話履歴を取得（thread_idごと）
    checkpoint = memory.get({"configurable": {"thread_id": thread_id}})
    past_messages = checkpoint.get("state", {}).get("messages", []) if checkpoint else []

    # ユーザーの入力をメッセージとして追加
    human_messages = [m for m in past_messages if isinstance(m, HumanMessage)]
    human_messages.append(HumanMessage(content=user_input))

    # API制限（スロットリング）時のリトライ処理
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
                    delay *= 2  # リトライごとに待機時間を倍増
                else:
                    raise e
        raise RuntimeError("Claude API throttled after multiple retries.")

    complete_raw_events = []
    parsed_tool_content = None

    try:
        for event in run_with_retry():
            complete_raw_events.append(event)
            # ツール実行のレスポンスを解析（JSON or テキスト）
            if "tool" in event:
                for msg in event["tool"].get("messages", []):
                    try:
                        parsed_tool_content = json.loads(msg.content)
                    except Exception:
                        parsed_tool_content = msg.content
    except Exception as e:
        return {"response": {"error": str(e)}}

    # 実行結果を返す
    return {
        "complete_raw_events": complete_raw_events,
        "parsed_tool_content": parsed_tool_content
    }

# ----------------------------
# 現在の会話履歴（メモリ）を取得するユーティリティ関数
# ----------------------------
def get_memory_state(thread_id: str):
    return memory.get({"configurable": {"thread_id": thread_id}})
