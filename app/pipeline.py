"""The triage pipeline: retrieve -> prompt -> LLM -> validate -> ground-check.

The grounding check is the guardrail that matters most here: the model may only
cite chunks that were actually retrieved. Invented citations are dropped, and
an answer left with no valid citation is downgraded to a docs gap instead of
being shown as confident. Both events are logged, so they can be monitored.
"""

import time
import uuid

from pydantic import ValidationError

from app.config import LLM_MAX_RETRIES
from app.llm import LLMClient, extract_json
from app.prompts import Prompt
from app.retrieval import Retriever
from app.schemas import Ticket, TicketAnalysis, TriageMeta, TriageResponse
from app.tracing import log_trace


class TriageError(RuntimeError):
    """The model never produced a valid TicketAnalysis."""

def normalize_citation(citation: str) -> str:
    """Models sometimes write 'chunk_id: foo-1' or '[foo-1]'. Reduce to 'foo-1'."""
    return citation.replace("chunk_id:", "").strip().strip("[]` ")


def format_context(results) -> str:
    return "\n\n".join(
        f"[chunk_id: {c.chunk_id}] ({c.kind}: {c.title})\n{c.text}" for c, _ in results
    )


class TriagePipeline:
    def __init__(self, retriever: Retriever, llm: LLMClient, prompt: Prompt, top_k: int = 4):
        self.retriever = retriever
        self.llm = llm
        self.prompt = prompt
        self.top_k = top_k

    def run(self, ticket: Ticket) -> TriageResponse:
        trace_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()

        results = self.retriever.search(f"{ticket.subject}\n{ticket.body}", k=self.top_k)
        valid_ids = {c.chunk_id for c, _ in results}

        messages = self.prompt.render(
            context=format_context(results) or "(no relevant passages found)",
            subject=ticket.subject,
            body=ticket.body,
        )

        analysis, usage, retries = self._ask_with_retries(messages)
        analysis.citations = [normalize_citation(c) for c in analysis.citations]

        # --- grounding check ---
        dropped = [c for c in analysis.citations if c not in valid_ids]
        analysis.citations = [c for c in analysis.citations if c in valid_ids]
        if not analysis.citations and not analysis.docs_gap:
            analysis.docs_gap = True
            analysis.confidence = min(analysis.confidence, 0.3)

        meta = TriageMeta(
            trace_id=trace_id,
            model=self.llm.model,
            prompt=self.prompt.label,
            latency_ms=int((time.perf_counter() - started) * 1000),
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=usage.cost_usd,
            retries=retries,
            dropped_citations=dropped,
            retrieved=[c.chunk_id for c, _ in results],
        )
        log_trace(
            {
                "trace_id": trace_id,
                "ticket_id": ticket.ticket_id,
                **meta.model_dump(exclude={"trace_id"}),
                "category": analysis.category.value,
                "severity": analysis.severity.value,
                "docs_gap": analysis.docs_gap,
                "confidence": analysis.confidence,
            }
        )
        return TriageResponse(analysis=analysis, sources=[c for c, _ in results], meta=meta)

    def _ask_with_retries(self, messages: list[dict]):
        last_error = ""
        for attempt in range(LLM_MAX_RETRIES + 1):
            msgs = messages
            if last_error:  # tell the model what was wrong with the previous attempt
                msgs = messages + [
                    {
                        "role": "user",
                        "content": f"Your previous answer was invalid ({last_error}). "
                        "Reply again with ONLY a valid JSON object matching the schema.",
                    }
                ]
            result = self.llm.complete(msgs)
            try:
                return TicketAnalysis.model_validate(extract_json(result.text)), result, attempt
            except (ValueError, ValidationError) as exc:  # JSONDecodeError is a ValueError
                last_error = str(exc).splitlines()[0][:200]
        raise TriageError(f"No valid output after {LLM_MAX_RETRIES + 1} attempts: {last_error}")