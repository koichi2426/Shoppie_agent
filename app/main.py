from fastapi import FastAPI
from pydantic import BaseModel
from app.langgraph_agent import run_agent, get_memory_state

app = FastAPI()

# リクエスト用モデル
class ChatRequest(BaseModel):
    user_input: str
    thread_id: str = "default"

# チャット用エンドポイント
@app.post("/chat")
async def chat(request: ChatRequest):
    response = await run_agent(user_input=request.user_input, thread_id=request.thread_id)
    return {"response": response}

# メモリ確認用エンドポイント
@app.get("/memory/{thread_id}")
async def memory(thread_id: str):
    checkpoint = get_memory_state(thread_id)

    # チェックポイントが存在しない、または state 属性がない場合
    if not checkpoint or not hasattr(checkpoint, "state"):
        return {"message": f"No memory found for thread_id: {thread_id}"}

    # 会話履歴などのステートを整形して返す
    state_data = {
        k: [str(msg) for msg in v] if isinstance(v, list) else str(v)
        for k, v in checkpoint.state.items()
    }

    return {
        "thread_id": thread_id,
        "keys": list(checkpoint.state.keys()),
        "state": state_data
    }
