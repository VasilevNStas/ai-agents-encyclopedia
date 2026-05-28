"""SupportFlow API server."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..agent.core import (
    AgentSession,
    AgentStep,
    BudgetController,
    AuditTrail,
    Guardrail,
)
from ..agent.config import AgentConfig

app = FastAPI(title="SupportFlow Agent", version="2.1.0")
config = AgentConfig.from_env()
guardrail = Guardrail()
budget = BudgetController(config)
audit = AuditTrail()

# In-memory session store (Postgres in production)
sessions: dict[str, AgentSession] = {}


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    cost: float
    steps: int


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or f"{request.user_id}_{int(time.time())}"

    if session_id not in sessions:
        sessions[session_id] = AgentSession(
            session_id=session_id,
            user_id=request.user_id,
            start_time=time.time(),
        )

    session = sessions[session_id]

    # Input guardrail
    input_check = guardrail.check_input(request.message)
    if input_check["action"] == "block":
        raise HTTPException(status_code=403, detail=input_check["reason"])

    # Budget check
    budget_status = budget.check()
    if budget_status == "block":
        session.status = "budget_exceeded"
        return ChatResponse(
            response="Session budget exceeded. Start a new session.",
            session_id=session_id,
            cost=session.total_cost,
            steps=len(session.steps),
        )

    # Agent processing (simplified)
    step = AgentStep(
        step_number=len(session.steps) + 1,
        thought=f"Processing user request: {request.message}",
        action="search_knowledge_base",
        action_args={"query": request.message},
        observation="Mock result for demo",
        token_cost=0.001,
        latency_ms=100,
    )
    session.add_step(step)

    # Output guardrail
    output_check = guardrail.check_output("Mock response")
    if output_check["action"] == "sanitize":
        response_text = "Response sanitized for sensitive data."
    else:
        response_text = f"Mock response to: {request.message}"

    # Audit
    audit.record(session)

    return ChatResponse(
        response=response_text,
        session_id=session_id,
        cost=session.total_cost,
        steps=len(session.steps),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.1.0"}


@app.get("/audit/{user_id}")
async def get_audit(user_id: str):
    return {"records": audit.get_by_user(user_id)}


import time  # noqa: E402 — used in chat endpoint
