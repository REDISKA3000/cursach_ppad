from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RoleType = Literal["individual_contributor", "manager", "executive", "hybrid"]
MarketSegment = Literal["core", "adjacent", "excluded"]


class RoleProfile(BaseModel):
    target_role: str
    canonical_role: str
    role_family: str
    role_type: RoleType
    synonyms: list[str]
    must_have_concepts: list[str]
    related_concepts: list[str]
    negative_concepts: list[str]
    adjacent_roles: list[str]
    excluded_roles: list[str]


class SemanticScoreResult(BaseModel):
    score: float = Field(ge=0, le=1)
    matched_signals: list[str] = Field(default_factory=list)
    details: dict[str, float] = Field(default_factory=dict)


class KeywordScoreResult(BaseModel):
    score: float = Field(ge=0, le=1)
    matched_synonyms: list[str] = Field(default_factory=list)
    matched_must_have: list[str] = Field(default_factory=list)
    matched_related: list[str] = Field(default_factory=list)
    matched_negative: list[str] = Field(default_factory=list)
    matched_adjacent: list[str] = Field(default_factory=list)
    matched_excluded: list[str] = Field(default_factory=list)


class StructuredScoreResult(BaseModel):
    score: float = Field(ge=0, le=1)
    matched_role_family: bool = False
    matched_skills: list[str] = Field(default_factory=list)
    matched_tasks: list[str] = Field(default_factory=list)
    matched_tools: list[str] = Field(default_factory=list)
    matched_negative: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class VacancyRecord(BaseModel):
    vacancy_id: str
    title: str = ""
    company: str | None = None
    url: str | None = None
    raw_text: str = ""
    description: str = ""
    requirements: str = ""
    responsibilities: str = ""
    salary: str | None = None
    tags: list[str] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = None


class CandidateVacancy(BaseModel):
    vacancy_id: str
    title: str
    company: str | None = None
    url: str | None = None
    raw_text: str
    semantic_score: float = Field(ge=0, le=1)
    keyword_score: float = Field(ge=0, le=1)
    structured_score: float = Field(ge=0, le=1)
    quality_score: float = Field(ge=0, le=1)
    hybrid_retrieval_score: float = Field(ge=0, le=1)
    matched_signals: dict[str, Any] = Field(default_factory=dict)


class RerankResult(BaseModel):
    vacancy_id: str
    market_segment: MarketSegment
    rerank_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    reason: str
    use_for_market_analysis: bool
    use_for_adjacent_opportunities: bool


class RoleRelevancePipelineStats(BaseModel):
    total_vacancies: int
    candidate_pool_size: int
    core_count: int
    adjacent_count: int
    excluded_count: int


class FinalRankedVacancy(BaseModel):
    vacancy_id: str
    title: str
    company: str | None = None
    url: str | None = None
    hybrid_retrieval_score: float = Field(ge=0, le=1)
    semantic_score: float = Field(ge=0, le=1)
    keyword_score: float = Field(ge=0, le=1)
    structured_score: float = Field(ge=0, le=1)
    quality_score: float = Field(ge=0, le=1)
    rerank_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    market_segment: MarketSegment
    reason: str
    matched_signals: dict[str, Any] = Field(default_factory=dict)


class RoleRelevancePipelineResult(BaseModel):
    target_role: str
    role_profile: RoleProfile
    stats: RoleRelevancePipelineStats
    results: list[FinalRankedVacancy]


class RoleRelevanceRequest(BaseModel):
    target_role: str
    limit: int = Field(default=300, ge=1, le=1000)
    use_llm_reranker: bool = True
