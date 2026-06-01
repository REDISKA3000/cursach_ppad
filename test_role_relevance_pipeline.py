from app.schemas.role_relevance import VacancyRecord
from app.services.role_profile_builder import build_role_profile
from app.services.vacancy_candidate_pool import VacancyCandidatePoolBuilder
from app.services.vacancy_hybrid_retriever import VacancyHybridRetriever
from app.services.vacancy_llm_reranker import rule_based_rerank


def _vacancy(vacancy_id: str, title: str, text: str, tags: list[str] | None = None) -> VacancyRecord:
    return VacancyRecord(
        vacancy_id=vacancy_id,
        title=title,
        company="TestCo",
        url=f"https://example.com/{vacancy_id}",
        raw_text=f"Вакансия: {title}\n{text}",
        description=text,
        tags=tags or [],
    )


def test_role_profile_created_for_product_analyst():
    profile = build_role_profile("Продуктовый аналитик")
    assert profile.canonical_role == "Product Analyst"
    assert "SQL" in profile.must_have_concepts
    assert "System Analyst" in profile.excluded_roles


def test_keyword_search_finds_must_have_concepts():
    profile = build_role_profile("Продуктовый аналитик")
    vacancy = _vacancy(
        "1",
        "Middle Product Analyst",
        "SQL, A/B-тесты, продуктовые метрики, retention, conversion, дашборды.",
    )
    result = VacancyHybridRetriever().calculate_keyword_score(profile, vacancy)
    assert "SQL" in result.matched_must_have
    assert "продуктовые метрики" in result.matched_must_have
    assert result.score > 0.6


def test_negative_concepts_reduce_keyword_score():
    profile = build_role_profile("Продуктовый аналитик")
    good = _vacancy("1", "Product Analyst", "SQL, A/B-тесты, продуктовые метрики, воронки.")
    bad = _vacancy("2", "Системный аналитик", "Сбор требований, ТЗ, UML, BPMN, функциональные требования.")
    retriever = VacancyHybridRetriever()
    good_score = retriever.calculate_keyword_score(profile, good).score
    bad_score = retriever.calculate_keyword_score(profile, bad).score
    assert bad_score < good_score


def test_structured_search_boosts_role_family_match():
    profile = build_role_profile("Продуктовый аналитик")
    vacancy = _vacancy(
        "1",
        "Продуктовый аналитик",
        "Развитие продуктовой аналитики, SQL, дашборды и эксперименты.",
        tags=["product", "analytics", "sql"],
    )
    result = VacancyHybridRetriever().calculate_structured_score(profile, vacancy)
    assert result.matched_role_family is True
    assert result.score > 0.6


def test_candidate_pool_sorted_by_hybrid_score():
    profile = build_role_profile("Продуктовый аналитик")
    vacancies = [
        _vacancy("sys", "Системный аналитик", "Сбор требований, ТЗ, UML, BPMN."),
        _vacancy("prod", "Product Analyst", "SQL, A/B-тесты, продуктовые метрики, retention, conversion."),
    ]
    pool = VacancyCandidatePoolBuilder().build_candidate_pool(profile, vacancies, limit=2)
    assert pool[0].vacancy_id == "prod"
    assert pool[0].hybrid_retrieval_score >= pool[1].hybrid_retrieval_score


def test_rule_based_fallback_segments_examples():
    profile = build_role_profile("Продуктовый аналитик")
    examples = [
        (
            "core1",
            "Middle Product Analyst",
            "SQL, A/B-тесты, продуктовые метрики, retention, conversion, дашборды.",
            "core",
        ),
        (
            "core2",
            "Аналитик продукта",
            "Проводить эксперименты, анализировать пользовательское поведение, SQL и воронки.",
            "core",
        ),
        (
            "adj1",
            "Data Analyst",
            "SQL, Python, BI, отчетность и визуализация данных.",
            "adjacent",
        ),
        (
            "adj2",
            "BI Analyst",
            "Power BI, Tableau, SQL, построение отчетности и дашбордов.",
            "adjacent",
        ),
        (
            "adj3",
            "Growth Analyst",
            "SQL, сегментация пользователей, гипотезы и conversion.",
            "adjacent",
        ),
        (
            "exc1",
            "Системный аналитик",
            "Сбор требований, ТЗ, UML, BPMN, постановка задач разработчикам.",
            "excluded",
        ),
        (
            "exc2",
            "Финансовый аналитик",
            "Финансовая отчетность, бюджетирование, управленческая отчетность.",
            "excluded",
        ),
        (
            "exc3",
            "Бизнес-аналитик 1С",
            "1С, бухгалтерия, функциональные требования и регламентная отчетность.",
            "excluded",
        ),
    ]
    pool = VacancyCandidatePoolBuilder()
    for vacancy_id, title, text, expected in examples:
        candidate = pool.build_candidate_pool(profile, [_vacancy(vacancy_id, title, text)], limit=1)[0]
        assert rule_based_rerank(candidate, profile).market_segment == expected
