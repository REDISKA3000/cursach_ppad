from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.config import OPENAI_ENABLED
from app.schemas.role_relevance import CandidateVacancy, RerankResult, RoleProfile
from app.services.embedding_provider import normalize_text
from app.services.llm_provider import JSONRepair, OpenAIProvider

logger = logging.getLogger(__name__)


def _contains_any(text: str, concepts: list[str]) -> list[str]:
    normalized = normalize_text(text)
    return [concept for concept in concepts if normalize_text(concept) in normalized]


def _keyword_signals(candidate: CandidateVacancy, group: str) -> list[str]:
    return list((candidate.matched_signals.get("keywords") or {}).get(group) or [])


def _structured_signals(candidate: CandidateVacancy, group: str) -> list[str]:
    return list((candidate.matched_signals.get("structured") or {}).get(group) or [])


def _segment_flags(segment: str) -> tuple[bool, bool]:
    if segment == "core":
        return True, False
    if segment == "adjacent":
        return False, True
    return False, False


def rule_based_rerank(candidate: CandidateVacancy, role_profile: RoleProfile) -> RerankResult:
    title = normalize_text(candidate.title)
    full_text = normalize_text(f"{candidate.title}\n{candidate.raw_text}")

    title_synonyms = _contains_any(title, role_profile.synonyms)
    title_adjacent = _contains_any(title, role_profile.adjacent_roles)
    title_excluded = _contains_any(title, role_profile.excluded_roles)
    title_negative = _contains_any(title, role_profile.negative_concepts)

    must = _keyword_signals(candidate, "must_have") or _contains_any(full_text, role_profile.must_have_concepts)
    related = _keyword_signals(candidate, "related") or _contains_any(full_text, role_profile.related_concepts)
    negative = list(dict.fromkeys([*_keyword_signals(candidate, "negative"), *title_negative]))
    excluded = list(dict.fromkeys([*_keyword_signals(candidate, "excluded"), *title_excluded]))
    adjacent = _keyword_signals(candidate, "adjacent") or title_adjacent
    structured = candidate.matched_signals.get("structured") or {}
    role_family_match = bool(structured.get("matched_role_family"))

    strong_excluded = bool(title_excluded or len(negative) >= 2 or excluded)
    product_context = bool(
        _contains_any(
            full_text,
            [
                "продуктовые метрики",
                "продуктовая аналитика",
                "продуктовой аналитики",
                "воронки",
                "a/b-тест",
                "ab-тест",
                "эксперименты",
                "retention",
                "conversion",
                "пользовательского поведения",
                "продуктовая команда",
                "продуктовых команд",
            ],
        )
    )

    if strong_excluded and not (title_synonyms and product_context and len(must) >= 3):
        segment = "excluded"
        rerank_score = min(0.35, max(0.05, candidate.hybrid_retrieval_score * 0.45))
        confidence = 0.86 if title_excluded or excluded else 0.74
        reason = _excluded_reason(candidate, negative, excluded)
    elif (title_synonyms or role_family_match) and product_context and len(must) >= 2:
        segment = "core"
        rerank_score = min(0.98, max(0.72, candidate.hybrid_retrieval_score + 0.18))
        confidence = 0.88 if title_synonyms else 0.8
        reason = _core_reason(must, related, title_synonyms, role_family_match)
    elif title_synonyms and len(must) >= 2 and not strong_excluded:
        segment = "core"
        rerank_score = min(0.92, max(0.68, candidate.hybrid_retrieval_score + 0.12))
        confidence = 0.76
        reason = _core_reason(must, related, title_synonyms, role_family_match)
    elif adjacent or candidate.semantic_score >= 0.58 or len(related) >= 2 or len(must) >= 2:
        segment = "adjacent"
        rerank_score = min(0.76, max(0.45, candidate.hybrid_retrieval_score + 0.04))
        confidence = 0.76 if adjacent else 0.64
        reason = _adjacent_reason(candidate, adjacent, must, related, product_context)
    else:
        segment = "excluded"
        rerank_score = min(0.42, max(0.08, candidate.hybrid_retrieval_score * 0.55))
        confidence = 0.62
        reason = "Недостаточно сигналов, что вакансия относится к целевой роли; явный профессиональный контекст роли не найден."

    use_market, use_adjacent = _segment_flags(segment)
    return RerankResult(
        vacancy_id=candidate.vacancy_id,
        market_segment=segment,
        rerank_score=round(rerank_score, 4),
        confidence=round(confidence, 4),
        reason=reason,
        use_for_market_analysis=use_market,
        use_for_adjacent_opportunities=use_adjacent,
    )


def _core_reason(must: list[str], related: list[str], title_synonyms: list[str], role_family_match: bool) -> str:
    signals = list(dict.fromkeys([*must[:4], *related[:2]]))
    prefix = "Вакансия напрямую относится к целевой роли"
    if title_synonyms:
        prefix += f": в названии есть {', '.join(title_synonyms[:2])}"
    elif role_family_match:
        prefix += ": совпадает профиль/семейство роли"
    if signals:
        return f"{prefix}; также найдены ключевые сигналы: {', '.join(signals)}."
    return f"{prefix}; найден релевантный продуктовый контекст."


def _adjacent_reason(
    candidate: CandidateVacancy,
    adjacent: list[str],
    must: list[str],
    related: list[str],
    product_context: bool,
) -> str:
    if adjacent:
        return (
            f"Вакансия близка к целевой роли как {', '.join(adjacent[:2])}: "
            f"есть пересечения по навыкам/задачам ({', '.join([*must[:2], *related[:2]]) or 'общая аналитика'}), "
            "но полного продуктового контекста недостаточно."
        )
    if product_context:
        return "Вакансия содержит часть продуктовых сигналов, но по названию и описанию не выглядит прямым совпадением с целевой ролью."
    return (
        "Вакансия пересекается с целевой ролью по аналитическим инструментам или задачам, "
        "но без явных признаков прямой специализации."
    )


def _excluded_reason(candidate: CandidateVacancy, negative: list[str], excluded: list[str]) -> str:
    signals = list(dict.fromkeys([*excluded[:3], *negative[:4]]))
    if signals:
        return f"Вакансия исключена: найдены нерелевантные для целевой роли сигналы ({', '.join(signals)})."
    return "Вакансия исключена: профессиональный контекст не соответствует целевой роли."


class VacancyLLMReranker:
    def __init__(self, provider: OpenAIProvider | None = None):
        self.provider = provider

    def rerank_candidate_pool(
        self,
        role_profile: RoleProfile,
        candidate_pool: list[CandidateVacancy],
        batch_size: int = 5,
        use_llm: bool = True,
    ) -> list[RerankResult]:
        if not use_llm or not OPENAI_ENABLED:
            if use_llm:
                logger.info("[Reranker] LLM disabled or unavailable, fallback to rule-based reranker")
            return [rule_based_rerank(candidate, role_profile) for candidate in candidate_pool]

        provider = self.provider or OpenAIProvider()
        if not provider.enabled:
            logger.info("[Reranker] LLM failed, fallback to rule-based reranker")
            return [rule_based_rerank(candidate, role_profile) for candidate in candidate_pool]

        results: list[RerankResult] = []
        batches = [
            candidate_pool[index : index + batch_size]
            for index in range(0, len(candidate_pool), batch_size)
        ]
        for batch_index, batch in enumerate(batches, start=1):
            logger.info("[Reranker] batch %s/%s", batch_index, len(batches))
            batch_results = self._rerank_batch_with_fallback(provider, role_profile, batch)
            results.extend(batch_results)
        return results

    def _rerank_batch_with_fallback(
        self,
        provider: OpenAIProvider,
        role_profile: RoleProfile,
        batch: list[CandidateVacancy],
    ) -> list[RerankResult]:
        fallback_by_id = {candidate.vacancy_id: rule_based_rerank(candidate, role_profile) for candidate in batch}
        prompt = self._build_batch_prompt(role_profile, batch)
        for attempt in range(1, 3):
            try:
                raw = provider._call_chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_completion_tokens=2500,
                )
                parsed, _ = JSONRepair.try_parse(raw)
                if not isinstance(parsed, list):
                    raise ValueError("LLM response is not a JSON array")
                valid_by_id = self._validate_llm_results(parsed)
                return [valid_by_id.get(candidate.vacancy_id, fallback_by_id[candidate.vacancy_id]) for candidate in batch]
            except Exception as exc:
                logger.warning("[Reranker] LLM batch failed attempt=%s error=%s", attempt, exc)
        logger.info("[Reranker] LLM failed, fallback to rule-based reranker")
        return list(fallback_by_id.values())

    def _validate_llm_results(self, payload: list[Any]) -> dict[str, RerankResult]:
        valid: dict[str, RerankResult] = {}
        for item in payload:
            try:
                result = RerankResult.model_validate(item)
            except ValidationError:
                continue
            market, adjacent = _segment_flags(result.market_segment)
            result.use_for_market_analysis = market
            result.use_for_adjacent_opportunities = adjacent
            valid[result.vacancy_id] = result
        return valid

    def _build_batch_prompt(self, role_profile: RoleProfile, batch: list[CandidateVacancy]) -> str:
        vacancies = []
        for candidate in batch:
            vacancies.append(
                {
                    "vacancy_id": candidate.vacancy_id,
                    "title": candidate.title,
                    "company": candidate.company,
                    "raw_text": candidate.raw_text[:3500],
                    "matched_signals": candidate.matched_signals,
                }
            )
        return (
            "Ты классифицируешь вакансии относительно целевой роли пользователя.\n"
            f"Целевая роль: {role_profile.target_role}\n"
            f"Профиль роли: {role_profile.model_dump_json(ensure_ascii=False)}\n\n"
            "Классы: core, adjacent, excluded.\n"
            "Правила:\n"
            "- Не относить вакансию к core только из-за слова аналитик.\n"
            "- System Analyst, Financial Analyst, Business Analyst 1C, бухгалтерская аналитика, ТЗ, UML, BPMN и сбор требований обычно excluded.\n"
            "- Data Analytics/BI без продуктового контекста обычно adjacent.\n"
            "- Product metrics, funnels, A/B tests, user behavior, SQL/BI и продуктовая команда обычно core.\n"
            "- Не выдумывай факты, которых нет в вакансии.\n"
            "Верни строго JSON-массив объектов по схеме: "
            "{vacancy_id, market_segment, rerank_score, confidence, reason, "
            "use_for_market_analysis, use_for_adjacent_opportunities}.\n\n"
            f"Вакансии: {json.dumps(vacancies, ensure_ascii=False)}"
        )
