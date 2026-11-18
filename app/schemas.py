"""Request/response contracts. The LLM must produce a TicketAnalysis; anything
that does not validate is retried, then rejected. Structured output is what
makes the rest of the LLMOps story (evals, monitoring) measurable."""

from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    bug = "bug"
    configuration = "configuration"
    how_to = "how_to"
    performance = "performance"
    installation = "installation"
    other = "other"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Ticket(BaseModel):
    subject: str = Field(min_length=3, max_length=300)
    body: str = Field(min_length=10, max_length=8000)
    ticket_id: str | None = None


class Chunk(BaseModel):
    chunk_id: str
    source: str          # file or URL the chunk came from
    title: str           # section heading
    text: str
    kind: str = "doc"    # "doc" | "issue" | "release_note"


class TicketAnalysis(BaseModel):
    """What the LLM must return (as JSON)."""

    category: Category
    severity: Severity
    summary: str = Field(description="One sentence restating the problem")
    likely_root_cause: str
    suggested_steps: list[str] = Field(default_factory=list)
    draft_reply: str
    citations: list[str] = Field(
        default_factory=list,
        description="chunk_ids from the provided context that support the answer",
    )
    docs_gap: bool = Field(
        default=False,
        description="True when the context does not contain enough to answer",
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class TriageMeta(BaseModel):
    trace_id: str
    model: str
    prompt: str            # e.g. "triage@v1"
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    retries: int = 0
    dropped_citations: list[str] = Field(default_factory=list)
    retrieved: list[str] = Field(default_factory=list)


class TriageResponse(BaseModel):
    analysis: TicketAnalysis
    sources: list[Chunk]
    meta: TriageMeta


class Feedback(BaseModel):
    trace_id: str
    verdict: str = Field(pattern="^(accepted|edited|rejected)$")
    edited_reply: str | None = None
    comment: str | None = None