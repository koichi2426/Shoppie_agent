# app/main.py

from fastapi import FastAPI, Request
from app.langgraph_agent import run_agent

app = FastAPI()

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_input = body.get("user_input", "")  # ← ここを修正
    thread_id = body.get("thread_id", "default")

    response = await run_agent(user_input, thread_id=thread_id)
    return {"response": response}
