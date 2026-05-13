"""Section-based CareerStrategy parsing and light validation."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.schemas.candidate import CandidateJob, CandidateProfile
from app.schemas.strategy import StrategyBrief
from app.schemas.vacancy import VacancyProfile
from app.services.profile_matching import (
    analyze_candidate_fit,
    canonicalize_phrase,
    dedupe_preserve,
    phrase_match_score,
)


SECTION_RE = re.compile(r"^\[([A-Z_]+)\]\s*$", re.MULTILINE)
MAX_ITEMS_PER_LIST = 10


def build_strategy_context(
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    candidate_preferences: Optional[Dict[str, Any]] = None,
) -> str:
    """Build compact but rich context for the LLM strategist."""
    lines: List[str] = []
    experience = candidate_profile.experience_months
    if experience is None and candidate_profile.experience_years is not None:
        experience = candidate_profile.experience_years * 12

    lines.append("CANDIDATE")
    lines.append(f"target_role: {candidate_profile.target_role or ''}")
    lines.append(f"experience_months: {experience if experience is not None else ''}")
    lines.append(f"experience_years: {candidate_profile.experience_years if candidate_profile.experience_years is not None else ''}")
    lines.append(f"skills_hard: {_join_limited(candidate_profile.skills_hard, 30)}")
    lines.append(f"skills_soft: {_join_limited(candidate_profile.skills_soft, 12)}")
    lines.append(f"education: {_format_education(candidate_profile)}")
    lines.append(f"languages: {_format_languages(candidate_profile)}")
    lines.append("")
    lines.append("CANDIDATE_JOBS")
    for job in candidate_profile.jobs[:6]:
        lines.extend(_format_job(job))
        lines.append("")

    lines.append("VACANCY")
    lines.append(f"role: {vacancy_profile.role or ''}")
    lines.append(f"seniority: {vacancy_profile.seniority or ''}")
    lines.append(f"industry: {vacancy_profile.industry or ''}")
    lines.append(f"must_have: {_join_limited(vacancy_profile.must_have_skills, 24)}")
    lines.append(f"nice_to_have: {_join_limited(vacancy_profile.nice_to_have_skills, 16)}")
    lines.append(f"responsibilities: {_join_limited(vacancy_profile.key_responsibilities, 16)}")
    lines.append(f"ats_keywords: {_join_limited(vacancy_profile.keywords_for_ats, 24)}")
    lines.append("")
    lines.append("CANDIDATE_PREFERENCES")
    lines.append(_format_preferences(candidate_preferences))
    return "\n".join(lines).strip()


def parse_career_strategy_section_text(
    response_text: str,
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    candidate_preferences: Optional[Dict[str, Any]] = None,
) -> Tuple[StrategyBrief, int]:
    """Parse section-based LLM strategy output into StrategyBrief."""
    sections = _split_sections(response_text)
    parsed_count = len([value for value in sections.values() if value.strip()])
    support = analyze_candidate_fit(candidate_profile, vacancy_profile)

    qualitative_fit = _clean_scalar(sections.get("QUALITATIVE_FIT", ""))
    support_score = support.fit_score
    fit_score = combine_fit_score(qualitative_fit, support_score)

    strategy = StrategyBrief(
        positioning=_clean_scalar(sections.get("POSITIONING", "")),
        qualitative_fit=qualitative_fit,
        support_fit_score=support_score,
        fit_score=fit_score,
        highlight_job_ids=_parse_ids(sections.get("HIGHLIGHT_JOBS", "")),
        downplay_job_ids=_parse_ids(sections.get("DOWNPLAY_JOBS", "")),
        skills_to_highlight=_parse_phrase_list(sections.get("SKILLS_TO_HIGHLIGHT", "")),
        skills_to_soften=_parse_phrase_list(sections.get("SKILLS_TO_SOFTEN", "")),
        achievement_highlights=_parse_bullets(sections.get("ACHIEVEMENT_HIGHLIGHTS", "")),
        gaps=_parse_bullets(sections.get("GAPS", "")),
        resume_variants=_parse_bullets(sections.get("RESUME_VARIANTS", "")),
        recommendations_short=_clean_scalar(sections.get("RECOMMENDATIONS", "")),
        strategy_warnings=_parse_bullets(sections.get("WARNINGS", "")),
        fallback_used=False,
    )

    normalize_strategy_brief(strategy, candidate_profile, vacancy_profile, candidate_preferences)
    return strategy, parsed_count


def normalize_strategy_brief(
    strategy: StrategyBrief,
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    candidate_preferences: Optional[Dict[str, Any]] = None,
    *,
    fallback_used: Optional[bool] = None,
) -> StrategyBrief:
    """Validate and lightly enrich an LLM-first StrategyBrief without strategic overwrite."""
    support = analyze_candidate_fit(candidate_profile, vacancy_profile)
    valid_job_ids = [job.id for job in candidate_profile.jobs]

    if fallback_used is not None:
        strategy.fallback_used = fallback_used

    strategy.positioning = canonicalize_phrase(strategy.positioning)
    if not strategy.positioning:
        strategy.positioning = support.positioning
        strategy.strategy_warnings.append("Positioning was missing; support fallback used")

    strategy.qualitative_fit = _clean_scalar(strategy.qualitative_fit)
    if strategy.support_fit_score is None:
        strategy.support_fit_score = support.fit_score

    strategy.highlight_job_ids = _valid_unique_ids(strategy.highlight_job_ids, valid_job_ids)
    if not strategy.highlight_job_ids and support.highlight_job_ids:
        strategy.highlight_job_ids = support.highlight_job_ids[:3]
        strategy.strategy_warnings.append("Highlight job ids were missing; support fallback used")

    strategy.downplay_job_ids = _valid_unique_ids(strategy.downplay_job_ids, valid_job_ids)
    if not strategy.downplay_job_ids:
        strategy.downplay_job_ids = [job_id for job_id in valid_job_ids if job_id not in strategy.highlight_job_ids]

    strategy.skills_to_highlight = _prioritize_skills_to_highlight(
        strategy.skills_to_highlight,
        candidate_profile,
        vacancy_profile,
        support,
        strategy.highlight_job_ids,
    )
    if not strategy.skills_to_highlight:
        strategy.skills_to_highlight = support.skills_to_highlight[:8]
        strategy.strategy_warnings.append("Skills to highlight were missing; support fallback used")

    strategy.skills_to_soften = [
        skill for skill in _normalize_skills(strategy.skills_to_soften)
        if skill.lower() not in {item.lower() for item in strategy.skills_to_highlight}
    ]

    strategy.achievement_highlights = _ground_achievement_highlights(
        strategy.achievement_highlights,
        candidate_profile,
        support,
    )
    if not strategy.achievement_highlights:
        strategy.strategy_warnings.append("Achievement highlights were missing; support snippets used")

    strategy.gaps = dedupe_preserve(strategy.gaps or support.gaps)
    strategy.qualitative_fit = _calibrate_qualitative_fit(
        strategy.qualitative_fit,
        strategy.support_fit_score or support.fit_score,
        strategy.gaps,
        vacancy_profile,
        strategy.strategy_warnings,
    )
    strategy.fit_score = combine_fit_score(strategy.qualitative_fit, strategy.support_fit_score or support.fit_score)
    strategy.resume_variants = _normalize_resume_variants(strategy.resume_variants, candidate_profile, vacancy_profile, strategy.positioning)
    strategy.recommendations_short = canonicalize_phrase(strategy.recommendations_short)
    if not strategy.recommendations_short:
        strategy.recommendations_short = support.recommendations_short
        strategy.strategy_warnings.append("Recommendations were missing; support fallback used")

    strategy.priority_themes = _derive_priority_themes(strategy, support, vacancy_profile)
    strategy.strategy_warnings = dedupe_preserve(strategy.strategy_warnings)[:8]
    strategy.strategy_confidence = _strategy_confidence(strategy)
    return strategy


def build_fallback_strategy(
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    candidate_preferences: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> StrategyBrief:
    """Full deterministic fallback used only when LLM path is unavailable/unusable."""
    support = analyze_candidate_fit(candidate_profile, vacancy_profile)
    strategy = StrategyBrief(
        positioning=support.positioning,
        qualitative_fit=_qualitative_from_score(support.fit_score),
        support_fit_score=support.fit_score,
        fit_score=support.fit_score,
        highlight_job_ids=support.highlight_job_ids,
        downplay_job_ids=support.downplay_job_ids,
        skills_to_highlight=support.skills_to_highlight,
        skills_to_soften=[],
        achievement_highlights=[],
        priority_themes=support.themes,
        gaps=support.gaps,
        resume_variants=_normalize_resume_variants([], candidate_profile, vacancy_profile, support.positioning),
        recommendations_short=support.recommendations_short,
        strategy_confidence="low",
        fallback_used=True,
        strategy_warnings=[f"CareerStrategy fallback used: {reason}" if reason else "CareerStrategy fallback used"],
    )
    return normalize_strategy_brief(
        strategy,
        candidate_profile,
        vacancy_profile,
        candidate_preferences,
        fallback_used=True,
    )


def combine_fit_score(qualitative_fit: str, support_score: float) -> float:
    """Combine model qualitative judgment with deterministic support signal."""
    qualitative_score = _qualitative_score(qualitative_fit)
    if qualitative_score is None:
        return max(0.0, min(round(support_score, 3), 0.95))
    return max(0.0, min(round((qualitative_score * 0.45) + (support_score * 0.55), 3), 0.95))


def _split_sections(text: str) -> Dict[str, str]:
    if not text:
        return {}
    matches = list(SECTION_RE.finditer(text))
    sections: Dict[str, str] = {}
    for idx, match in enumerate(matches):
        name = match.group(1).strip().upper()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    return sections


def _format_job(job: CandidateJob) -> List[str]:
    lines = [
        f"job_id: {job.id}",
        f"company: {job.company_name or ''}",
        f"company_type: {job.company_type or ''}",
        f"position: {job.position or ''}",
        f"period: {job.period or ''}",
        f"skills_used: {_join_limited(job.skills_used, 10)}",
    ]
    responsibilities = job.responsibilities[:4]
    achievements = job.achievements[:3]
    if responsibilities:
        lines.append("responsibilities:")
        lines.extend(f"- {item}" for item in responsibilities)
    if achievements:
        lines.append("achievements:")
        lines.extend(f"- {item}" for item in achievements)
    return lines


def _format_education(candidate_profile: CandidateProfile) -> str:
    items = []
    for edu in candidate_profile.education[:4]:
        parts = [edu.institution, edu.degree, getattr(edu, "field", None), edu.year, getattr(edu, "status", None)]
        items.append(" | ".join(part for part in parts if part))
    return "; ".join(items)


def _format_languages(candidate_profile: CandidateProfile) -> str:
    canonical = getattr(candidate_profile, "canonical_profile", None)
    language_items = getattr(canonical, "languages", None) if canonical else None
    if language_items:
        result = []
        for item in language_items:
            result.append(f"{item.name} {item.level or ''}".strip())
        return "; ".join(result)
    return "; ".join(candidate_profile.languages)


def _format_preferences(candidate_preferences: Optional[Dict[str, Any]]) -> str:
    if not candidate_preferences:
        return "none"
    parts = []
    for key, value in candidate_preferences.items():
        if value in (None, "", [], {}):
            continue
        parts.append(f"{key}: {value}")
    return "\n".join(parts) if parts else "none"


def _join_limited(items: Iterable[str], limit: int) -> str:
    return "; ".join(canonicalize_phrase(item) for item in list(items or [])[:limit] if canonicalize_phrase(item))


def _clean_scalar(text: str) -> str:
    lines = [line.strip(" \t-•") for line in (text or "").splitlines()]
    return canonicalize_phrase(" ".join(line for line in lines if line))


def _parse_bullets(text: str) -> List[str]:
    items: List[str] = []
    for line in (text or "").splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        cleaned = re.sub(r"^\d+[\).]\s*", "", cleaned)
        cleaned = cleaned.strip(" -•\t")
        if cleaned:
            items.append(canonicalize_phrase(cleaned))
    if not items and text and ";" in text:
        items = _parse_phrase_list(text)
    return dedupe_preserve(items)[:MAX_ITEMS_PER_LIST]


def _parse_phrase_list(text: str) -> List[str]:
    raw_parts: List[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip(" -•\t")
        if not stripped:
            continue
        raw_parts.extend(part.strip() for part in stripped.split(";"))
    return dedupe_preserve(raw_parts)[:MAX_ITEMS_PER_LIST]


def _parse_ids(text: str) -> List[int]:
    return [int(match) for match in re.findall(r"\d+", text or "")]


def _valid_unique_ids(ids: List[int], valid_ids: List[int]) -> List[int]:
    valid_set = set(valid_ids)
    result = []
    for item in ids:
        if item in valid_set and item not in result:
            result.append(item)
    return result


def _normalize_skills(skills: List[str]) -> List[str]:
    return dedupe_preserve(skill for skill in skills if canonicalize_phrase(skill))[:MAX_ITEMS_PER_LIST]


def _prioritize_skills_to_highlight(
    skills: List[str],
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    support,
    highlight_job_ids: List[int],
) -> List[str]:
    """Keep LLM skills, but rank them by vacancy relevance and candidate evidence."""
    candidates = dedupe_preserve(list(skills or []) + list(getattr(support, "skills_to_highlight", []) or []))
    if not candidates:
        return []

    candidate_texts = _candidate_evidence_texts(candidate_profile, highlight_job_ids)
    vacancy_phrases = dedupe_preserve(
        [vacancy_profile.role or "", vacancy_profile.industry or ""]
        + vacancy_profile.must_have_skills
        + vacancy_profile.nice_to_have_skills
        + vacancy_profile.key_responsibilities
        + vacancy_profile.keywords_for_ats
    )
    support_skills = {skill.lower() for skill in getattr(support, "skills_to_highlight", []) or []}
    must_have_text = " ".join(vacancy_profile.must_have_skills)

    scored = []
    for index, skill in enumerate(candidates):
        cleaned = canonicalize_phrase(skill)
        if not cleaned:
            continue
        vacancy_score = max((phrase_match_score(cleaned, [phrase]) for phrase in vacancy_phrases), default=0.0)
        evidence_score = phrase_match_score(cleaned, candidate_texts)
        support_bonus = 0.16 if cleaned.lower() in support_skills else 0.0
        must_bonus = 0.12 if phrase_match_score(cleaned, [must_have_text]) >= 0.55 else 0.0
        domain_bonus = 0.10 if _is_domain_critical_skill(cleaned, vacancy_profile) else 0.0
        score = (vacancy_score * 0.52) + (evidence_score * 0.28) + support_bonus + must_bonus + domain_bonus
        if evidence_score < 0.28 and cleaned.lower() not in support_skills:
            score -= 0.45
        scored.append((cleaned, score, index))

    scored.sort(key=lambda item: (-item[1], item[2]))
    strong = [skill for skill, score, _ in scored if score >= 0.34]
    if len(strong) < 4:
        strong = [skill for skill, _, _ in scored]
    return dedupe_preserve(strong)[:8]


def _candidate_evidence_texts(candidate_profile: CandidateProfile, highlight_job_ids: List[int]) -> List[str]:
    texts: List[str] = []
    texts.extend(candidate_profile.skills_hard)
    texts.extend(candidate_profile.skills_soft)
    selected_ids = set(highlight_job_ids)
    for job in candidate_profile.jobs:
        if selected_ids and job.id not in selected_ids:
            continue
        texts.extend(filter(None, [job.position, job.company_name, job.company_type, job.period]))
        texts.extend(job.responsibilities)
        texts.extend(job.achievements)
        texts.extend(job.skills_used)
    if not texts:
        for job in candidate_profile.jobs:
            texts.extend(job.responsibilities)
            texts.extend(job.achievements)
            texts.extend(job.skills_used)
    return [text for text in texts if text]


def _is_domain_critical_skill(skill: str, vacancy_profile: VacancyProfile) -> bool:
    norm = _norm(skill)
    vacancy_norm = _norm(" ".join(
        [vacancy_profile.role or "", vacancy_profile.industry or ""]
        + vacancy_profile.must_have_skills
        + vacancy_profile.key_responsibilities
    ))
    if not norm or not vacancy_norm:
        return False
    domain_markers = (
        "risk", "риск", "credit", "кредит", "банк", "bank", "fraud", "фрод",
        "monitor", "монитор", "incident", "инцидент", "sql", "excel",
        "pd", "lgd", "отчет", "report",
    )
    return any(marker in norm and marker in vacancy_norm for marker in domain_markers)


def _calibrate_qualitative_fit(
    qualitative_fit: str,
    support_score: float,
    gaps: List[str],
    vacancy_profile: VacancyProfile,
    warnings: List[str],
) -> str:
    """Downgrade optimistic qualitative labels when support/gaps do not justify them."""
    current_label = _qualitative_label(qualitative_fit)
    if not current_label:
        return qualitative_fit

    major_gaps = _count_major_gaps(gaps, vacancy_profile)
    calibrated = current_label
    if current_label == "high" and (support_score < 0.68 or major_gaps >= 2):
        calibrated = "medium"
    elif current_label == "medium" and support_score < 0.36 and major_gaps >= 3:
        calibrated = "low"

    if calibrated == current_label:
        return qualitative_fit

    warnings.append(
        f"Qualitative fit calibrated from {current_label} to {calibrated}: support_score={support_score}, major_gaps={major_gaps}"
    )
    reason = _strip_qualitative_prefix(qualitative_fit)
    if reason:
        return f"{calibrated} - {reason}"
    return calibrated


def _count_major_gaps(gaps: List[str], vacancy_profile: VacancyProfile) -> int:
    if not gaps:
        return 0
    must_have_text = " ".join(vacancy_profile.must_have_skills)
    responsibility_text = " ".join(vacancy_profile.key_responsibilities)
    count = 0
    for gap in gaps:
        if phrase_match_score(gap, vacancy_profile.must_have_skills) >= 0.55:
            count += 1
            continue
        if phrase_match_score(gap, [must_have_text]) >= 0.50:
            count += 1
            continue
        if _is_domain_critical_skill(gap, vacancy_profile) and phrase_match_score(gap, [responsibility_text]) >= 0.35:
            count += 1
    return count


def _qualitative_label(text: str) -> Optional[str]:
    normalized = (text or "").strip().lower()
    if re.search(r"\bhigh\b|высок", normalized):
        return "high"
    if re.search(r"\bmedium\b|средн", normalized):
        return "medium"
    if re.search(r"\blow\b|низк|слаб", normalized):
        return "low"
    return None


def _strip_qualitative_prefix(text: str) -> str:
    return re.sub(r"^\s*(high|medium|low|высок\w*|средн\w*|низк\w*)\s*[-:—–]?\s*", "", text or "", flags=re.IGNORECASE).strip()


def _ground_achievement_highlights(items: List[str], candidate_profile: CandidateProfile, support) -> List[str]:
    source_texts = []
    for job in candidate_profile.jobs:
        source_texts.extend(job.achievements)
        source_texts.extend(job.responsibilities)

    grounded = []
    for item in items:
        cleaned = canonicalize_phrase(item)
        if not cleaned:
            continue
        if phrase_match_score(cleaned, source_texts) >= 0.45:
            grounded.append(cleaned)

    if len(grounded) < 2:
        for match in support.job_matches:
            for point in match.top_responsibilities:
                cleaned = canonicalize_phrase(point)
                if cleaned:
                    grounded.append(cleaned)
                if len(grounded) >= 5:
                    break
            if len(grounded) >= 5:
                break

    return dedupe_preserve(grounded)[:5]


def _normalize_resume_variants(
    variants: List[str],
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    positioning: str,
) -> List[str]:
    result = dedupe_preserve(variants)
    if positioning:
        result.insert(0, positioning)
    if vacancy_profile.role:
        result.append(f"Акцент на релевантный опыт для роли {vacancy_profile.role}")
    if candidate_profile.target_role and candidate_profile.target_role != vacancy_profile.role:
        result.append(f"Мост между {candidate_profile.target_role} и требованиями вакансии")
    return dedupe_preserve(result)[:3]


def _derive_priority_themes(strategy: StrategyBrief, support, vacancy_profile: VacancyProfile) -> List[str]:
    themes = []
    source_texts = []
    source_texts.append(strategy.positioning)
    source_texts.extend(strategy.achievement_highlights)
    source_texts.extend(getattr(support, "themes", [])[:4])
    for match in getattr(support, "job_matches", [])[:2]:
        source_texts.extend(getattr(match, "matched_requirements", [])[:3])
        source_texts.extend(getattr(match, "top_responsibilities", [])[:2])
    source_texts.extend(vacancy_profile.key_responsibilities[:4])

    for text in source_texts:
        theme = _strategic_theme_from_text(text)
        if theme:
            themes.append(theme)

    for theme in getattr(support, "themes", [])[:4]:
        mapped = _strategic_theme_from_text(theme)
        if mapped:
            themes.append(mapped)

    return dedupe_preserve(themes)[:5]


def _strategic_theme_from_text(text: str) -> Optional[str]:
    norm = _norm(text)
    if not norm:
        return None
    if re.match(r"^(анализировать|проводить|выявлять|отслеживать|вести|коммуницировать|разрабатывать|настраивать|создавать|готовить|участвовать|работать)\b", norm):
        return None
    if re.search(r"\bpd\b|\blgd\b|risk based|скоринг|scoring", norm):
        return "PD/LGD и risk-based decisioning"
    if "портфел" in norm and ("риск" in norm or "risk" in norm):
        return "портфельная риск-аналитика"
    if ("монитор" in norm or "дашборд" in norm or "dashboard" in norm or "отчет" in norm or "report" in norm) and (
        "риск" in norm or "risk" in norm or "банк" in norm or "bank" in norm or "кредит" in norm
    ):
        return "банковская риск-отчетность и мониторинг"
    if ("кредит" in norm or "credit" in norm) and ("риск" in norm or "risk" in norm):
        return "кредитные риски"
    if "фрод" in norm or "fraud" in norm:
        return "антифрод и платежные риски"
    if "инцидент" in norm or "incident" in norm or "эскалац" in norm:
        return "управление инцидентами и эскалациями"
    if "монитор" in norm:
        return "мониторинг ключевых процессов"
    if ("данн" in norm or "data" in norm) and ("витрин" in norm or "dwh" in norm or "etl" in norm or "warehouse" in norm):
        return "DWH/ETL и витрины данных"
    if ("bi" in norm or "дашборд" in norm or "dashboard" in norm) and not _is_tool_like_theme(text):
        return "BI-аналитика и управленческая отчетность"
    cleaned = canonicalize_phrase(text)
    if 8 <= len(cleaned) <= 70 and not _is_tool_like_theme(cleaned):
        return cleaned
    return None


def _is_tool_like_theme(text: str) -> bool:
    cleaned = canonicalize_phrase(text)
    norm = _norm(cleaned)
    if not cleaned:
        return True
    tool_names = {
        "sql", "excel", "python", "r", "power bi", "tableau", "grafana",
        "clickhouse", "greenplum", "postgresql", "mysql", "jira", "confluence",
    }
    if norm in tool_names:
        return True
    tokens = norm.split()
    if len(tokens) <= 2 and all(re.fullmatch(r"[a-z0-9+#.\-]+", token) for token in tokens):
        return True
    return False


def _norm(text: str) -> str:
    return (text or "").lower().replace("ё", "е")


def _qualitative_score(text: str) -> Optional[float]:
    normalized = (text or "").strip().lower()
    if not normalized:
        return None
    if re.search(r"\bhigh\b|высок", normalized):
        return 0.82
    if re.search(r"\bmedium\b|средн", normalized):
        return 0.58
    if re.search(r"\blow\b|низк|слаб", normalized):
        return 0.32
    return None


def _qualitative_from_score(score: float) -> str:
    if score >= 0.72:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _strategy_confidence(strategy: StrategyBrief) -> str:
    if strategy.fallback_used:
        return "low"
    core_ok = bool(strategy.positioning and strategy.highlight_job_ids and strategy.skills_to_highlight)
    rich_ok = bool(strategy.achievement_highlights and strategy.recommendations_short and strategy.qualitative_fit)
    if core_ok and rich_ok and len(strategy.strategy_warnings) <= 1:
        return "high"
    if core_ok:
        return "medium"
    return "low"
