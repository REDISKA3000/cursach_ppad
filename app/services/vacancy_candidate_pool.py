from __future__ import annotations

import logging
import re

from app.schemas.role_relevance import (
    CandidateVacancy,
    KeywordScoreResult,
    RoleProfile,
    SemanticScoreResult,
    StructuredScoreResult,
    VacancyRecord,
)
from app.services.vacancy_hybrid_retriever import VacancyHybridRetriever

logger = logging.getLogger(__name__)


def calculate_vacancy_quality_score(vacancy: VacancyRecord) -> float:
    text = vacancy.raw_text or vacancy.description or ""
    text_len = len(text.strip())
    score = 0.0
    if vacancy.description.strip():
        score += 0.25
    if text_len >= 300:
        score += 0.25
    elif text_len >= 120:
        score += 0.12
    if vacancy.company:
        score += 0.15
    if vacancy.url:
        score += 0.15
    if vacancy.salary:
        score += 0.08
    if vacancy.title:
        score += 0.12

    if text_len < 80:
        score -= 0.25
    if _looks_noisy(text):
        score -= 0.15
    return round(max(0.0, min(1.0, score)), 4)


def _looks_noisy(text: str) -> bool:
    if not text:
        return True
    visible = re.sub(r"\s+", "", text)
    if not visible:
        return True
    punctuation_share = sum(1 for char in visible if not char.isalnum()) / max(1, len(visible))
    return punctuation_share > 0.45


def calculate_hybrid_retrieval_score(
    semantic: SemanticScoreResult,
    keyword: KeywordScoreResult,
    structured: StructuredScoreResult,
    quality_score: float,
) -> float:
    score = (
        0.40 * semantic.score
        + 0.30 * structured.score
        + 0.20 * keyword.score
        + 0.10 * quality_score
    )
    return round(max(0.0, min(1.0, score)), 4)


def _matched_signals(
    semantic: SemanticScoreResult,
    keyword: KeywordScoreResult,
    structured: StructuredScoreResult,
) -> dict:
    return {
        "semantic": semantic.matched_signals,
        "semantic_details": semantic.details,
        "keywords": {
            "synonyms": keyword.matched_synonyms,
            "must_have": keyword.matched_must_have,
            "related": keyword.matched_related,
            "negative": keyword.matched_negative,
            "adjacent": keyword.matched_adjacent,
            "excluded": keyword.matched_excluded,
        },
        "structured": {
            "matched_role_family": structured.matched_role_family,
            "skills": structured.matched_skills,
            "tasks": structured.matched_tasks,
            "tools": structured.matched_tools,
            "negative": structured.matched_negative,
            "details": structured.details,
        },
    }


class VacancyCandidatePoolBuilder:
    def __init__(self, retriever: VacancyHybridRetriever | None = None):
        self.retriever = retriever or VacancyHybridRetriever()

    def build_candidate_pool(
        self,
        role_profile: RoleProfile,
        vacancies: list[VacancyRecord],
        limit: int = 300,
        min_hybrid_score: float | None = None,
    ) -> list[CandidateVacancy]:
        candidates: list[CandidateVacancy] = []
        for vacancy in vacancies:
            semantic = self.retriever.calculate_semantic_score(role_profile, vacancy)
            keyword = self.retriever.calculate_keyword_score(role_profile, vacancy)
            structured = self.retriever.calculate_structured_score(role_profile, vacancy)
            quality = calculate_vacancy_quality_score(vacancy)
            hybrid = calculate_hybrid_retrieval_score(semantic, keyword, structured, quality)
            if min_hybrid_score is not None and hybrid < min_hybrid_score:
                continue

            candidates.append(
                CandidateVacancy(
                    vacancy_id=vacancy.vacancy_id,
                    title=vacancy.title,
                    company=vacancy.company,
                    url=vacancy.url,
                    raw_text=vacancy.raw_text,
                    semantic_score=semantic.score,
                    keyword_score=keyword.score,
                    structured_score=structured.score,
                    quality_score=quality,
                    hybrid_retrieval_score=hybrid,
                    matched_signals=_matched_signals(semantic, keyword, structured),
                )
            )

        candidates.sort(key=lambda item: item.hybrid_retrieval_score, reverse=True)
        pool = candidates[: min(limit, len(candidates))]
        logger.info("[HybridSearch] candidate pool size=%s", len(pool))
        return pool
