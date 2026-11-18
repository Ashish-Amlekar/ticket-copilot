"""FastAPI service.

Run:   uvicorn app.main:app --port 8000
Docs:  http://localhost:8000/docs

GET  /health     liveness + which model / prompt / KB size is loaded
POST /triage     ticket in -> structured analysis + sources + meta out
POST /feedback   accepted | edited | rejected, tied to a trace_id
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app import config
from app.llm import LiteLLMClient, LLMError
from app.pipeline import TriageError, TriagePipeline
from app.prompts import load_prompt
from app.retrieval import build_retriever, load_chunks
from app.schemas import Feedback, Ticket, TriageResponse
from app.tracing import log_feedback

state: dict = {}


def build_pipeline() -> TriagePipeline:
    retriever = build_retriever(load_chunks(config.KB_PATH), config.RETRIEVER, config.EMBEDDING_MODEL)
    llm = LiteLLMClient(config.LLM_MODEL, config.LLM_TEMPERATURE)
    return TriagePipeline(retriever, llm, load_prompt(), top_k=config.TOP_K)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if "pipeline" not in state:  # tests inject their own pipeline
        state["pipeline"] = build_pipeline()
    yield


app = FastAPI(title="Support Ticket Copilot", lifespan=lifespan)


@app.get("/health")
def health():
    p: TriagePipeline = state["pipeline"]
    return {
        "status": "ok",
        "model": p.llm.model,
        "prompt": p.prompt.label,
        "retriever": type(p.retriever).__name__,
        "kb_chunks": len(p.retriever.chunks),
    }


@app.post("/triage", response_model=TriageResponse)
def triage(ticket: Ticket):
    try:
        return state["pipeline"].run(ticket)
    except TriageError as exc:  # model answered but never with valid output
        raise HTTPException(status_code=502, detail=str(exc))
    except LLMError as exc:  # model backend down / misconfigured
        raise HTTPException(status_code=503, detail=f"LLM backend unavailable: {exc}")


@app.post("/feedback")
def feedback(fb: Feedback):
    log_feedback(fb.model_dump())
    return {"status": "recorded"}