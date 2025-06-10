# app/main.py

from fastapi import FastAPI, Request
from app.langgraph_agent import run_agent

app = FastAPI()

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_input = body.get("message", "")
    response = await run_agent(user_input)
    return {"response": response}
