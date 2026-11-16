from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator
from ._frozen_core.retrieval import query_tokens

Pair = Annotated[list[int], Field(min_length=2, max_length=2)]
Short = Annotated[str, Field(min_length=1, max_length=160)]

class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class ErrorInfo(Model):
    code: str
    message: str

class ErrorResponse(Model):
    error: ErrorInfo

class Question(Model):
    question: Annotated[str, Field(min_length=1, max_length=4096)]

    @field_validator("question")
    @classmethod
    def valid_question(cls, value):
        if not value.strip():
            raise ValueError("Question must not be blank")
        query_tokens(value)
        return value

class SearchRequest(Question):
    top_k: Annotated[int, Field(ge=1, le=10)] = 3

class SourceSelection(Model):
    source_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")]
    passage_id: Annotated[str, Field(min_length=1, max_length=120)]

class Passage(Model):
    passage_id: str
    source_id: str
    parent_chunk_id: str
    source_path: str
    product_version: str
    commit: str
    immutable_url: str
    source_url: str
    source_sha256: str
    text_sha256: str
    text: str
    source_lines: Pair
    source_char_range: Pair
    parent_char_range: Pair

class RankedPassages(Model):
    rank: int
    score: float
    chunk_id: str
    text: str
    section_titles: list[str]
    passages: list[Passage]

class SearchResponse(Model):
    application_version: str
    corpus_build_id: str
    question: str
    score_kind: str
    unverified: Literal[True] = True
    results: list[RankedPassages]
    limitations: list[str]

class DraftContent(Model):
    title: Short = "Support issue"
    issue: Annotated[str, Field(min_length=1, max_length=8000)]
    environment: Annotated[dict[str, str], Field(max_length=20)] = Field(default_factory=dict)
    selected_sources: Annotated[list[SourceSelection], Field(max_length=10)] = Field(default_factory=list)
    missing_information: Annotated[list[Annotated[str, Field(min_length=1, max_length=500)]], Field(max_length=10)] = Field(
        default_factory=lambda: ["Exact error message and reproduction steps", "Operating system and architecture", "Python, package and application versions"])
    human_notes: Annotated[str, Field(max_length=4000)] = ""

    @model_validator(mode="after")
    def content_limits(self):
        if not self.title.strip() or not self.issue.strip():
            raise ValueError("Title and issue must not be blank")
        if any(not k.strip() or len(k)>80 or len(v)>2048 for k,v in self.environment.items()):
            raise ValueError("Environment keys/values exceed limits")
        def check(value):
            if isinstance(value,str):
                if any((ord(c)<32 and c not in "\t\n\r") or 0xD800<=ord(c)<=0xDFFF for c in value):
                    raise ValueError("Unsupported control character")
            elif isinstance(value,dict):
                for k,v in value.items():check(k);check(v)
            elif isinstance(value,list):
                for v in value:check(v)
        check(self.model_dump())
        return self

class TicketPatch(Model):
    expected_revision: Annotated[int, Field(ge=1)]
    title: Short | None = None
    issue: Annotated[str, Field(min_length=1, max_length=8000)] | None = None
    environment: Annotated[dict[str, str], Field(max_length=20)] | None = None
    selected_sources: Annotated[list[SourceSelection], Field(max_length=10)] | None = None
    missing_information: Annotated[list[str], Field(max_length=10)] | None = None
    human_notes: Annotated[str, Field(max_length=4000)] | None = None

    @model_validator(mode="after")
    def edits_present(self):
        edits=self.model_fields_set-{"expected_revision"}
        if not edits or any(getattr(self,k) is None for k in edits):
            raise ValueError("Provide non-null permitted edits")
        return self

class ReviewRequest(Model):
    expected_revision: Annotated[int, Field(ge=1)]
    confirm_review: Literal[True]
    reviewer_label: Annotated[str, Field(min_length=1, max_length=80)] = "local user"
    note: Annotated[str, Field(max_length=2000)] = ""

    @field_validator("confirm_review",mode="before")
    @classmethod
    def explicit_confirmation(cls,value):
        if value is not True:raise ValueError("Explicit true confirmation required")
        return value

class RevisionInfo(Model):
    revision: int
    content_sha256: str
    created_at: str

class ReviewEvent(Model):
    event_id: str
    revision: int
    reviewer_label: str
    note: str
    recorded_at: str
    content_sha256: str
    identity_authenticated: Literal[False] = False
    current_revision: bool

class TicketResponse(Model):
    ticket_id: str
    revision: int
    review_state: Literal["unreviewed","review_recorded"]
    content: DraftContent
    documentation: list[Passage]
    rendered_text: str
    content_sha256: str
    history: list[RevisionInfo]
    review_events: list[ReviewEvent]
    limitations: list[str]

class HealthResponse(Model):
    status: Literal["ok"]
    application_version: str

class ReadyResponse(Model):
    ready: bool
    corpus_ready: bool
    store_ready: bool
    detail: str

class GenerationAvailability(Model):
    enabled: bool
    available: bool
    state: str
    reason: str | None = None

class MetadataResponse(Model):
    application_version: str
    corpus_build_id: str | None
    sources: list[dict[str,str]]
    capabilities: dict[str,bool]
    experimental_generation: GenerationAvailability
    measured_limitations: dict
    limitations: list[str]

class ExperimentalResponse(Model):
    request_id: str
    application_version: str
    experimental: Literal[True] = True
    unverified: Literal[True] = True
    model_status: JsonValue | None
    application_validation_outcome: Literal["validated_answer","validated_insufficient_evidence","generation_validation_error"]
    raw_output: str | None
    validated_response: dict | None
    finish_reason: str | None
    supplied_passages: list[dict]
    omitted_blocks: list[dict]
    identifiers: dict[str,str]
    timings: dict[str,float]
    error: ErrorInfo | None
    limitations: list[str]
