from __future__ import annotations

import json
import logging
import math
from typing import Any

from sqlalchemy.orm import Session

from app.models import JobBoardVacancy
from app.schemas.role_relevance import (
    KeywordScoreResult,
    RoleProfile,
    SemanticScoreResult,
    StructuredScoreResult,
    VacancyRecord,
)
from app.services.embedding_provider import EmbeddingProvider, HashingEmbeddingProvider, cosine_similarity, normalize_text

logger = logging.getLogger(__name__)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            return [value]
    return []


def _contains(haystack: str, needle: str) -> bool:
    return bool(needle) and normalize_text(needle) in haystack


def _unique_matches(items: list[str], *texts: str) -> list[str]:
    normalized_texts = [normalize_text(text) for text in texts]
    matches = []
    for item in items:
        if any(_contains(text, item) for text in normalized_texts):
            matches.append(item)
    return list(dict.fromkeys(matches))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def vacancy_record_from_model(vacancy: JobBoardVacancy) -> VacancyRecord:
    tags = _as_list(vacancy.tags_json)
    raw_text = vacancy.normalized_text or "\n".join(
        part
        for part in [
            f"Вакансия: {vacancy.title or ''}",
            f"Компания: {vacancy.company or ''}",
            f"Локация: {vacancy.location or ''}",
            f"Зарплата: {vacancy.salary or ''}",
            vacancy.description or "",
            f"Теги: {', '.join(tags)}" if tags else "",
        ]
        if part
    )
    return VacancyRecord(
        vacancy_id=str(vacancy.id),
        title=vacancy.title or "",
        company=vacancy.company or None,
        url=vacancy.source_url or None,
        raw_text=raw_text,
        description=vacancy.description or "",
        salary=vacancy.salary or None,
        tags=tags,
        features={"tags": tags, "location": vacancy.location or "", "source": vacancy.source or ""},
        updated_at=vacancy.updated_at.isoformat() if vacancy.updated_at else None,
    )


def load_job_board_vacancies(db: Session) -> list[VacancyRecord]:
    vacancies = db.query(JobBoardVacancy).order_by(JobBoardVacancy.updated_at.desc()).all()
    return [vacancy_record_from_model(vacancy) for vacancy in vacancies]


class VacancyHybridRetriever:
    def __init__(self, embedding_provider: EmbeddingProvider | None = None):
        self.embedding_provider = embedding_provider or HashingEmbeddingProvider()

    def calculate_semantic_score(self, role_profile: RoleProfile, vacancy: VacancyRecord) -> SemanticScoreResult:
        profile_text = " ".join(
            [
                role_profile.target_role,
                role_profile.canonical_role,
                role_profile.role_family,
                " ".join(role_profile.synonyms),
                " ".join(role_profile.must_have_concepts),
                " ".join(role_profile.related_concepts),
            ]
        )
        must_have_text = " ".join(role_profile.must_have_concepts)
        task_text = " ".join([role_profile.role_family, *role_profile.must_have_concepts, *role_profile.related_concepts])

        details = {
            "title_similarity": cosine_similarity(
                self.embedding_provider.embed_text(role_profile.target_role),
                self.embedding_provider.embed_text(vacancy.title),
            ),
            "full_text_similarity": cosine_similarity(
                self.embedding_provider.embed_text(profile_text),
                self.embedding_provider.embed_text(vacancy.raw_text),
            ),
            "requirements_similarity": cosine_similarity(
                self.embedding_provider.embed_text(must_have_text),
                self.embedding_provider.embed_text(vacancy.description),
            ),
            "responsibilities_similarity": cosine_similarity(
                self.embedding_provider.embed_text(task_text),
                self.embedding_provider.embed_text(vacancy.raw_text),
            ),
        }
        score = (
            details["title_similarity"] * 0.35
            + details["full_text_similarity"] * 0.35
            + details["requirements_similarity"] * 0.15
            + details["responsibilities_similarity"] * 0.15
        )
        signals = [
            label
            for label, value in details.items()
            if value >= 0.66
        ]
        return SemanticScoreResult(score=round(score, 4), matched_signals=signals, details=details)

    def calculate_keyword_score(self, role_profile: RoleProfile, vacancy: VacancyRecord) -> KeywordScoreResult:
        title = normalize_text(vacancy.title)
        full_text = normalize_text(vacancy.raw_text)

        matched_synonyms_title = _unique_matches(role_profile.synonyms, title)
        matched_synonyms_text = [
            item for item in _unique_matches(role_profile.synonyms, full_text) if item not in matched_synonyms_title
        ]
        matched_must = _unique_matches(role_profile.must_have_concepts, full_text)
        matched_related = _unique_matches(role_profile.related_concepts, full_text)
        matched_negative = _unique_matches(role_profile.negative_concepts, full_text)
        matched_adjacent = _unique_matches(role_profile.adjacent_roles, title, full_text)
        matched_excluded = _unique_matches(role_profile.excluded_roles, title, full_text)

        raw_score = 0.0
        raw_score += 2.0 * len(matched_synonyms_title)
        raw_score += 1.5 * len(matched_synonyms_text)
        raw_score += 1.2 * len(matched_must)
        raw_score += 0.6 * len(matched_related)
        raw_score += 0.8 * len(matched_adjacent)
        raw_score -= 1.5 * len(matched_negative)
        raw_score -= 2.0 * len(matched_excluded)
        if matched_excluded and any(_contains(title, item) for item in matched_excluded):
            raw_score -= 2.0

        return KeywordScoreResult(
            score=round(_sigmoid((raw_score - 1.5) / 4.0), 4),
            matched_synonyms=list(dict.fromkeys([*matched_synonyms_title, *matched_synonyms_text])),
            matched_must_have=matched_must,
            matched_related=matched_related,
            matched_negative=matched_negative,
            matched_adjacent=matched_adjacent,
            matched_excluded=matched_excluded,
        )

    def calculate_structured_score(self, role_profile: RoleProfile, vacancy: VacancyRecord) -> StructuredScoreResult:
        tags = [normalize_text(tag) for tag in vacancy.tags]
        title = normalize_text(vacancy.title)
        full_text = normalize_text(vacancy.raw_text)
        feature_text = " ".join([*tags, title, full_text])

        product_family_markers = ["product", "продукт", "analytics", "аналитик"]
        data_family_markers = ["data", "bi", "аналитик данных"]
        matched_role_family = False
        if normalize_text(role_profile.role_family) == "product analytics":
            matched_role_family = any(marker in feature_text for marker in product_family_markers) and (
                "product" in feature_text or "продукт" in feature_text
            )
        elif normalize_text(role_profile.role_family) == "data analytics":
            matched_role_family = any(marker in feature_text for marker in data_family_markers)
        else:
            matched_role_family = normalize_text(role_profile.role_family) in feature_text

        matched_skills = _unique_matches(role_profile.must_have_concepts, " ".join(tags), full_text)
        matched_tasks = _unique_matches(role_profile.must_have_concepts + role_profile.related_concepts, full_text)
        matched_tools = _unique_matches(role_profile.related_concepts, " ".join(tags), full_text)
        matched_negative = _unique_matches(role_profile.negative_concepts + role_profile.excluded_roles, title, full_text)

        raw_score = 0.0
        raw_score += 3.0 if matched_role_family else 0.0
        raw_score += min(3.0, 0.8 * len(matched_skills))
        raw_score += min(2.0, 0.5 * len(matched_tasks))
        raw_score += min(1.5, 0.4 * len(matched_tools))
        raw_score -= min(4.0, 1.2 * len(matched_negative))
        if any(_contains(title, item) for item in role_profile.excluded_roles):
            raw_score -= 3.0

        return StructuredScoreResult(
            score=round(_sigmoid((raw_score - 1.5) / 3.5), 4),
            matched_role_family=matched_role_family,
            matched_skills=matched_skills,
            matched_tasks=matched_tasks,
            matched_tools=matched_tools,
            matched_negative=matched_negative,
            details={
                "tags": vacancy.tags,
                "raw_score": round(raw_score, 4),
                "source": vacancy.features.get("source"),
            },
        )
