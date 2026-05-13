"""Section-based ResumeWriter/Critic helpers and deterministic fallback."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from app.schemas.candidate import CandidateProfile
from app.schemas.resume import GeneratedResume, TechnicalReport
from app.schemas.strategy import StrategyBrief
from app.schemas.vacancy import VacancyProfile
from app.services.profile_matching import analyze_candidate_fit, canonicalize_phrase, dedupe_preserve, phrase_match_score


SECTION_RE = re.compile(r"^\[([A-Z_]+)\]\s*$", re.MULTILINE)


def build_resume_writer_context(
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    strategy_brief: StrategyBrief,
) -> str:
    lines: List[str] = []
    lines.append("CANDIDATE")
    lines.append(f"target_role: {candidate_profile.target_role or ''}")
    lines.append(f"experience_years: {candidate_profile.experience_years if candidate_profile.experience_years is not None else ''}")
    lines.append(f"experience_months: {candidate_profile.experience_months if candidate_profile.experience_months is not None else ''}")
    lines.append(f"skills_hard: {_join(candidate_profile.skills_hard[:32])}")
    lines.append(f"skills_soft: {_join(candidate_profile.skills_soft[:12])}")
    lines.append(f"education: {_format_education(candidate_profile)}")
    lines.append(f"languages: {_format_languages(candidate_profile)}")
    lines.append("")
    lines.append("WRITING_GUARDRAILS")
    lines.append("strategy_is_guidance_not_fact: true")
    lines.append(f"domain_grounding: {_confirmed_domain_context(candidate_profile, vacancy_profile)}")
    lines.append(f"confidence_guidance: {_confidence_writing_guidance(strategy_brief)}")
    lines.append("summary_policy: maximum 2-3 sentences and 40 words; summary sets frame, relevant experience sells")
    lines.append(
        "relevant_experience_policy: highlighted jobs must use the strongest grounded bullets; "
        "prefer action + object/process + method/context + grounded value"
    )
    lines.append(f"confirmed_key_skills: {_join(_build_targeted_key_skills(candidate_profile, vacancy_profile, strategy_brief, limit=12))}")
    lines.append(
        "key_skills_rule: use only confirmed_key_skills or other skills explicitly present in candidate facts; "
        "do not turn priority_themes, gaps, or vacancy-only requirements into skills"
    )
    lines.append("")
    lines.append("JOBS")
    for job in candidate_profile.jobs[:8]:
        lines.append(f"job_id: {job.id}")
        lines.append(f"company: {job.company_name or ''}")
        lines.append(f"company_type: {job.company_type or ''}")
        lines.append(f"position: {job.position or ''}")
        lines.append(f"period: {job.period or ''}")
        lines.append(f"skills_used: {_join(job.skills_used[:12])}")
        if job.responsibilities:
            lines.append("responsibilities:")
            lines.extend(f"- {item}" for item in job.responsibilities[:5])
        if job.achievements:
            lines.append("achievements:")
            lines.extend(f"- {item}" for item in job.achievements[:4])
        ranked_points = _rank_job_points_for_writer(job, vacancy_profile, strategy_brief)
        if ranked_points:
            lines.append("ranked_writer_bullets:")
            lines.extend(f"- {item}" for item in ranked_points[:4])
        lines.append("")

    lines.append("VACANCY")
    lines.append(f"role: {vacancy_profile.role or ''}")
    lines.append(f"seniority: {vacancy_profile.seniority or ''}")
    lines.append(f"industry: {vacancy_profile.industry or ''}")
    lines.append(f"must_have: {_join(vacancy_profile.must_have_skills[:28])}")
    lines.append(f"nice_to_have: {_join(vacancy_profile.nice_to_have_skills[:18])}")
    lines.append(f"responsibilities: {_join(vacancy_profile.key_responsibilities[:18])}")
    lines.append(f"ats_keywords: {_join(vacancy_profile.keywords_for_ats[:28])}")
    lines.append("")
    lines.append("STRATEGY")
    lines.append(f"positioning: {strategy_brief.positioning}")
    lines.append(f"highlight_job_ids: {_join(str(item) for item in strategy_brief.highlight_job_ids)}")
    lines.append(f"downplay_job_ids: {_join(str(item) for item in strategy_brief.downplay_job_ids)}")
    lines.append(f"skills_to_highlight: {_join(strategy_brief.skills_to_highlight)}")
    lines.append(f"skills_to_soften: {_join(strategy_brief.skills_to_soften)}")
    lines.append(f"achievement_highlights: {_join(strategy_brief.achievement_highlights[:6])}")
    lines.append(f"priority_themes: {_join(strategy_brief.priority_themes[:6])}")
    lines.append(f"gaps: {_join(strategy_brief.gaps)}")
    lines.append(f"resume_variants: {_join(strategy_brief.resume_variants)}")
    lines.append(f"recommendations_short: {strategy_brief.recommendations_short}")
    lines.append(f"strategy_confidence: {strategy_brief.strategy_confidence}")
    return "\n".join(lines).strip()


def parse_resume_writer_section_text(response_text: str) -> Tuple[GeneratedResume, List[str], int]:
    sections = _split_sections(response_text)
    parsed_count = len([value for value in sections.values() if value.strip()])
    title = _clean_scalar(sections.get("TITLE", "")) or "Адаптированное резюме"
    warnings = _parse_bullets(sections.get("WARNINGS", ""))

    text_parts = []
    _append_section(text_parts, "ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ", sections.get("SUMMARY", ""))
    _append_bullet_section(text_parts, "КЛЮЧЕВЫЕ КОМПЕТЕНЦИИ", sections.get("KEY_SKILLS", ""))
    _append_experience_section(text_parts, "РЕЛЕВАНТНЫЙ ОПЫТ", sections.get("RELEVANT_EXPERIENCE", ""))
    _append_experience_section(text_parts, "ДОПОЛНИТЕЛЬНЫЙ ОПЫТ", sections.get("ADDITIONAL_EXPERIENCE", ""))
    _append_section(text_parts, "ОБРАЗОВАНИЕ", sections.get("EDUCATION", ""))
    _append_section(text_parts, "ЯЗЫКИ", sections.get("LANGUAGES", ""))

    resume_text = "\n".join(text_parts).strip() + "\n"
    return GeneratedResume(title=title, resume_text=resume_text, technical_report=TechnicalReport()), warnings, parsed_count


def build_resume_critic_context(
    generated_resume: GeneratedResume,
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    strategy_brief: StrategyBrief,
) -> str:
    return "\n".join([
        "FINAL_RESUME",
        generated_resume.resume_text,
        "",
        "CANDIDATE_FACTS",
        build_resume_writer_context(candidate_profile, vacancy_profile, strategy_brief),
        "",
        "EXPECTED_STRATEGY_ITEMS",
        f"highlight_job_ids: {_join(str(item) for item in strategy_brief.highlight_job_ids)}",
        f"achievement_highlights: {_join(strategy_brief.achievement_highlights)}",
        f"priority_themes: {_join(strategy_brief.priority_themes)}",
        f"skills_to_highlight: {_join(strategy_brief.skills_to_highlight)}",
        f"skills_to_soften: {_join(strategy_brief.skills_to_soften)}",
    ])


def parse_resume_critic_section_text(response_text: str) -> Tuple[TechnicalReport, int]:
    sections = _split_sections(response_text)
    parsed_count = len([value for value in sections.values() if value.strip()])
    return TechnicalReport(
        covered_must_haves=_parse_bullets(sections.get("COVERED_MUST_HAVES", "")),
        uncovered_must_haves=_parse_bullets(sections.get("UNCOVERED_MUST_HAVES", "")),
        used_achievement_highlights=_parse_bullets(sections.get("USED_ACHIEVEMENT_HIGHLIGHTS", "")),
        used_priority_themes=_parse_bullets(sections.get("USED_PRIORITY_THEMES", "")),
        omitted_strategy_items=_parse_bullets(sections.get("OMITTED_STRATEGY_ITEMS", "")),
        hallucination_checks=dedupe_preserve(
            _parse_bullets(sections.get("HALLUCINATION_CHECKS", ""))
            + _parse_bullets(sections.get("QUALITY_CHECKS", ""))
        ),
        critic_warnings=_parse_bullets(sections.get("WARNINGS", "")),
        critic_confidence=_normalize_confidence(_clean_scalar(sections.get("CONFIDENCE", ""))),
    ), parsed_count


def build_rule_based_technical_report(
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    strategy_brief: StrategyBrief,
    resume_text: str,
    *,
    writer_fallback_used: bool = False,
    critic_fallback_used: bool = False,
    writer_warnings: List[str] | None = None,
) -> TechnicalReport:
    insights = analyze_candidate_fit(candidate_profile, vacancy_profile)
    report = TechnicalReport()
    resume_lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    resume_joined = "\n".join(resume_lines)

    report.highlighted_jobs = strategy_brief.highlight_job_ids or insights.highlight_job_ids
    report.highlighted_skills = strategy_brief.skills_to_highlight or insights.skills_to_highlight
    report.used_highlight_job_ids = _used_highlight_jobs(candidate_profile, report.highlighted_jobs, resume_joined)
    report.used_achievement_highlights = _used_items(strategy_brief.achievement_highlights, resume_joined, threshold=0.40)
    report.used_priority_themes = _used_items(strategy_brief.priority_themes, resume_joined, threshold=0.35)
    report.covered_must_haves = _covered_requirements(vacancy_profile.must_have_skills, resume_joined)
    report.uncovered_must_haves = [item for item in vacancy_profile.must_have_skills if item not in report.covered_must_haves]
    skills_block = _extract_resume_section(resume_text, "КЛЮЧЕВЫЕ КОМПЕТЕНЦИИ")
    downplayed_used = _used_downplayed_jobs(candidate_profile, strategy_brief.downplay_job_ids, resume_text)
    technical_markers = _technical_marker_checks(resume_text)
    structural_issues = _experience_structure_checks(resume_text)
    selling_quality_issues = _experience_selling_quality_checks(resume_text, candidate_profile, strategy_brief)
    summary_issues = _summary_quality_checks(resume_text)
    irrelevant_skills = _irrelevant_skill_checks(skills_block, candidate_profile, vacancy_profile, strategy_brief)
    strategy_leakage = _strategy_leakage_checks(skills_block, candidate_profile, strategy_brief)
    domain_overclaims = _domain_overclaim_checks(resume_text, candidate_profile, vacancy_profile)

    omitted = []
    omitted.extend(f"achievement: {item}" for item in strategy_brief.achievement_highlights if item not in report.used_achievement_highlights)
    omitted.extend(f"priority theme: {item}" for item in strategy_brief.priority_themes if item not in report.used_priority_themes)
    omitted.extend(f"skill: {item}" for item in strategy_brief.skills_to_highlight if phrase_match_score(item, [resume_joined]) < 0.45)
    omitted.extend(f"downplayed job still prominent: {item}" for item in downplayed_used)
    report.omitted_strategy_items = dedupe_preserve(omitted)[:10]

    checks = []
    checks.extend(_company_date_checks(candidate_profile, resume_joined))
    checks.extend(_skill_hallucination_checks(candidate_profile, vacancy_profile, strategy_brief, resume_joined))
    checks.extend(technical_markers)
    checks.extend(structural_issues)
    checks.extend(selling_quality_issues)
    checks.extend(summary_issues)
    checks.extend(irrelevant_skills)
    checks.extend(strategy_leakage)
    checks.extend(domain_overclaims)
    if not checks:
        checks.append("Автоматическая проверка не нашла явных признаков выдуманных фактов")
    report.hallucination_checks = checks

    warnings = []
    if any(_is_generic_placeholder(line) for line in resume_lines):
        warnings.append("Обнаружены шаблонные фразы - требуется редактура")
    if not report.covered_must_haves and vacancy_profile.must_have_skills:
        warnings.append("Требуемые навыки недостаточно отражены в финальном резюме")
    if len(report.uncovered_must_haves) > len(report.covered_must_haves):
        warnings.append("Больше непокрытых требований, чем покрытых")
    if report.omitted_strategy_items:
        warnings.append("Часть стратегических акцентов не попала в финальное резюме")
    if technical_markers:
        warnings.append("В финальном тексте остались технические маркеры writer-а")
    if structural_issues:
        warnings.append("Нарушена структура блоков опыта: проверьте порядок должность-компания / период / bullets")
    if selling_quality_issues:
        warnings.append("Релевантный опыт можно подать сильнее: часть bullets слишком duty-like или не использует достижения")
    if summary_issues:
        warnings.append("Профессиональный профиль слишком длинный или перетягивает продажу с опыта")
    if irrelevant_skills:
        warnings.append("Блок ключевых навыков содержит нерелевантный шум")
    if strategy_leakage:
        warnings.append("Стратегические темы попали в навыки как неподтвержденные факты")
    if domain_overclaims:
        warnings.append("В тексте есть риск завышения доменной релевантности")
    if downplayed_used:
        warnings.append("Опыт, который стратегия просила приглушить, всё еще заметен")
    report.critic_warnings = dedupe_preserve(warnings)[:8]
    report.critic_confidence = "medium" if not report.critic_warnings else "low"
    report.writer_fallback_used = writer_fallback_used
    report.critic_fallback_used = critic_fallback_used
    report.writer_warnings = writer_warnings or []
    return report


def merge_technical_reports(base: TechnicalReport, critic: TechnicalReport) -> TechnicalReport:
    base.covered_must_haves = critic.covered_must_haves or base.covered_must_haves
    base.uncovered_must_haves = critic.uncovered_must_haves or base.uncovered_must_haves
    base.used_achievement_highlights = critic.used_achievement_highlights or base.used_achievement_highlights
    base.used_priority_themes = critic.used_priority_themes or base.used_priority_themes
    base.omitted_strategy_items = dedupe_preserve(base.omitted_strategy_items + critic.omitted_strategy_items)[:10]
    base.hallucination_checks = dedupe_preserve(base.hallucination_checks + critic.hallucination_checks)[:10]
    base.critic_warnings = dedupe_preserve(base.critic_warnings + critic.critic_warnings)[:10]
    if critic.critic_confidence:
        base.critic_confidence = critic.critic_confidence
    return base


def build_deterministic_resume(
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    strategy_brief: StrategyBrief,
    *,
    reason: str = "",
) -> GeneratedResume:
    insights = analyze_candidate_fit(candidate_profile, vacancy_profile)
    highlight_ids = strategy_brief.highlight_job_ids or insights.highlight_job_ids
    ordered_jobs = _order_jobs(candidate_profile, insights, highlight_ids)
    parts: List[str] = []
    parts.extend(["ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ", _build_summary(candidate_profile, vacancy_profile, strategy_brief, insights), ""])
    skills = _build_targeted_key_skills(candidate_profile, vacancy_profile, strategy_brief) or insights.skills_to_highlight or candidate_profile.skills_hard[:6]
    if skills:
        parts.extend(["КЛЮЧЕВЫЕ КОМПЕТЕНЦИИ", ", ".join(skills[:8]), ""])
    if ordered_jobs:
        parts.append("РЕЛЕВАНТНЫЙ ОПЫТ")
        job_matches = {match.job_id: match for match in insights.job_matches}
        for job in ordered_jobs:
            if job.id not in highlight_ids:
                continue
            parts.append("")
            heading = " — ".join(part for part in [job.position, job.company_name] if part)
            if heading:
                parts.append(heading)
            if job.period:
                parts.append(job.period)
            for point in _select_job_points(job, job_matches.get(job.id), strategy_brief):
                parts.append(f"• {point}")
        secondary_jobs = [job for job in ordered_jobs if job.id not in highlight_ids]
        if secondary_jobs:
            parts.extend(["", "ДОПОЛНИТЕЛЬНЫЙ ОПЫТ"])
            for job in secondary_jobs:
                snapshot = _build_job_snapshot(job)
                if snapshot:
                    parts.append(f"• {snapshot}")
    parts.append("")
    if candidate_profile.education:
        parts.append("ОБРАЗОВАНИЕ")
        for edu in candidate_profile.education:
            line = " | ".join(part for part in [edu.institution, edu.degree, getattr(edu, "field", None), edu.year] if part)
            if line:
                parts.append(line)
        parts.append("")
    if candidate_profile.languages:
        parts.extend(["ЯЗЫКИ", ", ".join(candidate_profile.languages), ""])

    resume_text = "\n".join(parts).strip() + "\n"
    report = build_rule_based_technical_report(
        candidate_profile,
        vacancy_profile,
        strategy_brief,
        resume_text,
        writer_fallback_used=True,
        critic_fallback_used=True,
        writer_warnings=[f"Использована резервная генерация резюме: {reason}" if reason else "Использована резервная генерация резюме"],
    )
    return GeneratedResume(title=f"Резюме для {vacancy_profile.role or 'должности'}", resume_text=resume_text, technical_report=report)


def finalize_generated_resume(
    generated_resume: GeneratedResume,
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    strategy_brief: StrategyBrief,
    writer_warnings: List[str],
    *,
    writer_fallback_used: bool = False,
    critic_report: TechnicalReport | None = None,
    critic_fallback_used: bool = False,
) -> GeneratedResume:
    generated_resume.resume_text = polish_resume_text(
        generated_resume.resume_text,
        candidate_profile,
        vacancy_profile,
        strategy_brief,
    )
    base_report = build_rule_based_technical_report(
        candidate_profile,
        vacancy_profile,
        strategy_brief,
        generated_resume.resume_text,
        writer_fallback_used=writer_fallback_used,
        critic_fallback_used=critic_fallback_used,
        writer_warnings=writer_warnings,
    )
    if critic_report:
        base_report = merge_technical_reports(base_report, critic_report)
        base_report.critic_fallback_used = critic_fallback_used
    generated_resume.technical_report = base_report
    return generated_resume


def polish_resume_text(
    resume_text: str,
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    strategy_brief: StrategyBrief,
) -> str:
    """Final presentation cleanup without changing the public writer contract."""
    text = _normalize_resume_technical_markers(resume_text)
    text = _remove_ascii_resume_header(text)
    text = _shorten_summary_section(text)
    targeted_skills = _build_targeted_key_skills(candidate_profile, vacancy_profile, strategy_brief, limit=10)
    if targeted_skills:
        text = _replace_key_skills_section(text, targeted_skills)
    return text.strip() + "\n"


def _remove_ascii_resume_header(resume_text: str) -> str:
    lines = (resume_text or "").splitlines()
    output: List[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if re.fullmatch(r"={5,}", line):
            next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
            after_next = lines[index + 2].strip() if index + 2 < len(lines) else ""
            if next_line.upper() == "ПРОФЕССИОНАЛЬНОЕ РЕЗЮМЕ" and re.fullmatch(r"={5,}", after_next):
                index += 3
                while index < len(lines) and not lines[index].strip():
                    index += 1
                continue
        if line.upper() == "ПРОФЕССИОНАЛЬНОЕ РЕЗЮМЕ":
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            continue
        output.append(lines[index])
        index += 1
    return "\n".join(output)


def _split_sections(text: str) -> Dict[str, str]:
    matches = list(SECTION_RE.finditer(text or ""))
    sections: Dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).strip().upper()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    return sections


def _append_section(parts: List[str], heading: str, body: str) -> None:
    cleaned = body.strip()
    if not cleaned:
        return
    parts.extend([heading, cleaned, ""])


def _append_bullet_section(parts: List[str], heading: str, body: str) -> None:
    bullets = _parse_bullets(body)
    if not bullets:
        return
    parts.append(heading)
    parts.append(", ".join(bullets))
    parts.append("")


def _append_experience_section(parts: List[str], heading: str, body: str) -> None:
    cleaned = _format_experience_body(body)
    if not cleaned:
        return
    parts.extend([heading, cleaned, ""])


def _format_experience_body(body: str) -> str:
    lines = [line.strip() for line in (body or "").splitlines() if line.strip()]
    if not lines:
        return ""

    chunks: List[List[str]] = []
    current: List[str] = []
    for index, line in enumerate(lines):
        if _is_job_marker_line(line):
            if current:
                chunks.append(current)
                current = []
            continue
        if current and _starts_new_job_block(lines, index, current):
            chunks.append(current)
            current = []
        current.append(line)
    if current:
        chunks.append(current)

    if not chunks:
        return ""

    formatted = [_format_job_chunk(chunk) for chunk in chunks]
    return "\n\n".join(item for item in formatted if item).strip()


def _is_job_marker_line(line: str) -> bool:
    return bool(re.match(r"^\s*#{1,6}\s*job\s+\d+\b", line, re.IGNORECASE) or re.match(r"^\s*job\s+\d+\s*$", line, re.IGNORECASE))


def _starts_new_job_block(lines: List[str], index: int, current: List[str]) -> bool:
    line = lines[index].strip()
    if not line or re.match(r"^\s*[-•*]\s+", line):
        return False
    if _looks_like_period(line) or _is_labeled_job_metadata(line):
        return False
    if not _chunk_has_job_content(current):
        return False

    next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
    second_next_line = lines[index + 2].strip() if index + 2 < len(lines) else ""
    return (
        " — " in line
        or _looks_like_period(next_line)
        or _is_company_label(next_line)
        or (_is_company_label(next_line) and _looks_like_period(second_next_line))
    )


def _chunk_has_job_content(lines: List[str]) -> bool:
    has_heading = False
    has_period = False
    has_bullet = False
    for line in lines:
        if re.match(r"^\s*[-•*]\s+", line):
            has_bullet = True
        elif _looks_like_period(line) or re.match(r"^(period|период)\s*:", line, re.IGNORECASE):
            has_period = True
        elif not _is_labeled_job_metadata(line):
            has_heading = True
    return has_heading and (has_period or has_bullet)


def _is_labeled_job_metadata(line: str) -> bool:
    return bool(re.match(r"^(position|title|должность|company|компания|period|период)\s*:", line, re.IGNORECASE))


def _is_company_label(line: str) -> bool:
    return bool(re.match(r"^(company|компания)\s*:", line, re.IGNORECASE))


def _format_job_chunk(lines: List[str]) -> str:
    title = ""
    company = ""
    period = ""
    bullets: List[str] = []
    passthrough: List[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        label_match = re.match(r"^(position|title|должность)\s*:\s*(.+)$", line, re.IGNORECASE)
        if label_match:
            title = canonicalize_phrase(label_match.group(2))
            continue

        label_match = re.match(r"^(company|компания)\s*:\s*(.+)$", line, re.IGNORECASE)
        if label_match:
            company = canonicalize_phrase(label_match.group(2))
            continue

        label_match = re.match(r"^(period|период)\s*:\s*(.+)$", line, re.IGNORECASE)
        if label_match:
            period = canonicalize_phrase(label_match.group(2))
            continue

        if re.match(r"^\s*[-•*]\s+", line):
            bullet = canonicalize_phrase(re.sub(r"^\s*[-•*]\s+", "", line))
            if bullet:
                bullets.append(bullet)
            continue

        if not title and not _looks_like_period(line):
            title = canonicalize_phrase(line)
            continue
        if not period and _looks_like_period(line):
            period = canonicalize_phrase(line)
            continue
        passthrough.append(canonicalize_phrase(line))

    title, company = _split_title_company(title, company)
    output: List[str] = []
    heading = " — ".join(part for part in [title, company] if part)
    if heading:
        output.append(heading)
    if period:
        output.append(period)
    output.extend(f"• {item}" for item in dedupe_preserve(bullets + passthrough) if item)
    return "\n".join(output)


def _split_title_company(title: str, company: str) -> Tuple[str, str]:
    if company or " — " not in title:
        return title, company
    left, right = [part.strip() for part in title.split(" — ", 1)]
    return left, right


def _looks_like_period(line: str) -> bool:
    lowered = line.lower()
    month_words = (
        "январ", "феврал", "март", "апрел", "май", "июн", "июл", "август",
        "сентябр", "октябр", "ноябр", "декабр", "present", "current", "настоящее",
    )
    return bool(re.search(r"\b20\d{2}\b", lowered) or any(word in lowered for word in month_words))


def _parse_bullets(text: str) -> List[str]:
    result = []
    for line in (text or "").splitlines():
        cleaned = re.sub(r"^\d+[\).]\s*", "", line.strip()).strip(" -•\t")
        if cleaned:
            result.append(canonicalize_phrase(cleaned))
    if not result and ";" in (text or ""):
        result = [canonicalize_phrase(item) for item in text.split(";") if canonicalize_phrase(item)]
    return dedupe_preserve(result)


def _clean_scalar(text: str) -> str:
    return canonicalize_phrase(" ".join(line.strip(" -•\t") for line in (text or "").splitlines() if line.strip()))


def _join(items: Iterable[Any]) -> str:
    return "; ".join(canonicalize_phrase(str(item)) for item in items if canonicalize_phrase(str(item)))


def _normalize_resume_technical_markers(resume_text: str) -> str:
    output: List[str] = []
    for raw_line in (resume_text or "").splitlines():
        line = raw_line.rstrip()
        if _is_job_marker_line(line):
            continue

        company_match = re.match(r"^\s*(?:company|компания)\s*:\s*(.+)$", line, re.IGNORECASE)
        if company_match:
            company = canonicalize_phrase(company_match.group(1))
            last_index = _last_content_line_index(output)
            if last_index is not None and _can_attach_company(output[last_index]):
                output[last_index] = f"{output[last_index]} — {company}"
            elif company:
                output.append(company)
            continue

        period_match = re.match(r"^\s*(?:period|период)\s*:\s*(.+)$", line, re.IGNORECASE)
        if period_match:
            period = canonicalize_phrase(period_match.group(1))
            if period:
                output.append(period)
            continue

        position_match = re.match(r"^\s*(?:position|title|должность)\s*:\s*(.+)$", line, re.IGNORECASE)
        if position_match:
            position = canonicalize_phrase(position_match.group(1))
            if position:
                output.append(position)
            continue

        output.append(line)

    return "\n".join(output)


def _last_content_line_index(lines: List[str]) -> int | None:
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip():
            return index
    return None


def _can_attach_company(line: str) -> bool:
    stripped = line.strip()
    if not stripped or " — " in stripped or stripped.startswith(("•", "-", "*")):
        return False
    if stripped.isupper() or _looks_like_period(stripped):
        return False
    return True


def _replace_key_skills_section(resume_text: str, skills: List[str]) -> str:
    lines = (resume_text or "").splitlines()
    output: List[str] = []
    index = 0
    replaced = False

    while index < len(lines):
        line = lines[index]
        if line.strip().upper() == "КЛЮЧЕВЫЕ КОМПЕТЕНЦИИ":
            output.append(line)
            output.append(", ".join(skills))
            replaced = True
            index += 1
            while index < len(lines):
                next_line = lines[index]
                if not next_line.strip():
                    output.append(next_line)
                    index += 1
                    break
                if _is_resume_heading(next_line):
                    break
                index += 1
            continue
        output.append(line)
        index += 1

    if not replaced and skills:
        insertion = ["КЛЮЧЕВЫЕ КОМПЕТЕНЦИИ", ", ".join(skills), ""]
        for index, line in enumerate(output):
            if line.strip().upper() == "РЕЛЕВАНТНЫЙ ОПЫТ":
                return "\n".join(output[:index] + insertion + output[index:])
        output.extend([""] + insertion)

    return "\n".join(output)


def _shorten_summary_section(resume_text: str, *, max_words: int = 40, max_sentences: int = 3) -> str:
    lines = (resume_text or "").splitlines()
    output: List[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        output.append(line)
        if line.strip().upper() != "ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ":
            index += 1
            continue

        index += 1
        summary_lines: List[str] = []
        while index < len(lines):
            next_line = lines[index]
            if _is_resume_heading(next_line):
                break
            summary_lines.append(next_line)
            index += 1

        summary = " ".join(item.strip() for item in summary_lines if item.strip())
        shortened = _limit_summary_text(summary, max_words=max_words, max_sentences=max_sentences)
        if shortened:
            output.append(shortened)
            output.append("")
        continue

    return "\n".join(output)


def _limit_summary_text(text: str, *, max_words: int, max_sentences: int) -> str:
    cleaned = canonicalize_phrase(text)
    if not cleaned:
        return ""

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    if sentences:
        cleaned = " ".join(sentences[:max_sentences])

    words = cleaned.split()
    if len(words) <= max_words:
        return cleaned

    limited = " ".join(words[:max_words]).rstrip(" ,;:")
    if not re.search(r"[.!?]$", limited):
        limited += "."
    return limited


def _is_resume_heading(line: str) -> bool:
    stripped = line.strip()
    headings = {
        "ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ",
        "КЛЮЧЕВЫЕ КОМПЕТЕНЦИИ",
        "РЕЛЕВАНТНЫЙ ОПЫТ",
        "ДОПОЛНИТЕЛЬНЫЙ ОПЫТ",
        "ОБРАЗОВАНИЕ",
        "ЯЗЫКИ",
    }
    return stripped.upper() in headings


def _build_targeted_key_skills(
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    strategy_brief: StrategyBrief,
    *,
    limit: int = 10,
) -> List[str]:
    candidate_texts = _candidate_evidence_texts(candidate_profile)
    vacancy_texts = _vacancy_strategy_texts(vacancy_profile, strategy_brief)
    highlighted_job_texts = _highlighted_job_texts(candidate_profile, strategy_brief.highlight_job_ids)
    must_have_text = " ".join(vacancy_profile.must_have_skills + vacancy_profile.keywords_for_ats).lower()
    softened_text = " ".join(strategy_brief.skills_to_soften).lower()
    protected_text = " ".join(strategy_brief.skills_to_highlight + vacancy_profile.must_have_skills).lower()

    candidates: List[str] = []
    candidates.extend(strategy_brief.skills_to_highlight)
    candidates.extend(vacancy_profile.must_have_skills)
    candidates.extend(vacancy_profile.keywords_for_ats)
    candidates.extend(skill for job in candidate_profile.jobs if job.id in strategy_brief.highlight_job_ids for skill in job.skills_used)
    candidates.extend(candidate_profile.skills_hard)

    result: List[str] = []
    for raw_item in candidates:
        for item in _split_skill_item(raw_item):
            if not item or len(item) > 90:
                continue
            if _is_generic_skill_item(item):
                continue
            if _is_requirement_phrase_not_skill(item):
                continue
            if _is_short_unconfirmed_keyword(item, candidate_texts):
                continue
            if _is_unconfirmed_gap_skill(item, candidate_texts):
                continue
            if _matches_text(item, softened_text) and not _matches_text(item, protected_text):
                continue
            if _is_side_domain_skill(item) and not _matches_text(item, protected_text):
                continue
            grounded = (
                phrase_match_score(item, candidate_texts) >= 0.55
                or phrase_match_score(item, highlighted_job_texts) >= 0.35
                or _candidate_has_related_skill(item, candidate_profile)
            )
            strategic = phrase_match_score(item, vacancy_texts) >= 0.25 or _matches_text(item, must_have_text)
            if not (grounded and strategic):
                continue
            result.append(_canonical_skill_label(item, candidate_profile))
            result = dedupe_preserve(result)
            if len(result) >= limit:
                return result[:limit]

    return result[:limit]


def _rank_job_points_for_writer(job, vacancy_profile: VacancyProfile, strategy_brief: StrategyBrief) -> List[str]:
    """Rank job-local bullets by grounding, vacancy relevance, strategy relevance, and diversity."""
    raw_points = dedupe_preserve(list(job.achievements) + list(job.responsibilities))
    if not raw_points:
        return []

    vacancy_texts = _vacancy_strategy_texts(vacancy_profile, strategy_brief)
    strategy_texts = [
        strategy_brief.positioning,
        strategy_brief.recommendations_short,
        *strategy_brief.achievement_highlights,
        *strategy_brief.priority_themes,
        *strategy_brief.skills_to_highlight,
    ]
    job_skill_text = " ".join(job.skills_used + [job.position or "", job.company_type or ""])

    scored: List[Tuple[float, str]] = []
    for point in raw_points:
        cleaned = canonicalize_phrase(point)
        if not cleaned or _is_generic_placeholder(cleaned):
            continue
        score = 1.0
        if point in job.achievements:
            score += 0.25
        score += min(phrase_match_score(cleaned, vacancy_texts), 1.0) * 1.25
        score += min(phrase_match_score(cleaned, strategy_texts), 1.0) * 0.75
        score += min(phrase_match_score(cleaned, [job_skill_text]), 1.0) * 0.35
        if re.search(r"\d+(?:[,.]\d+)?\s*%|\b\d+[,.]?\d*\s*(?:раз|млн|тыс|kpi|npl|pd/lgd)\b", cleaned, re.IGNORECASE):
            score += 0.20
        scored.append((score, cleaned))

    ranked = [point for _, point in sorted(scored, key=lambda item: (-item[0], len(item[1])))]
    return _dedupe_semantic_points(ranked)[:4]


def _dedupe_semantic_points(points: List[str]) -> List[str]:
    result: List[str] = []
    for point in points:
        if any(phrase_match_score(point, [existing]) >= 0.72 for existing in result):
            continue
        result.append(point)
    return result


def _confirmed_domain_context(candidate_profile: CandidateProfile, vacancy_profile: VacancyProfile) -> str:
    vacancy_domain = canonicalize_phrase(vacancy_profile.industry or "")
    if not vacancy_domain:
        return "vacancy domain is not explicit; avoid domain overclaiming"

    candidate_texts = _candidate_evidence_texts(candidate_profile)
    score = phrase_match_score(vacancy_domain, candidate_texts)
    if score >= 0.55:
        return f"confirmed: candidate facts support vacancy domain '{vacancy_domain}'"
    if _has_partial_domain_overlap(vacancy_domain, candidate_texts):
        return f"partial: use cautious wording for vacancy domain '{vacancy_domain}'"
    return f"not_confirmed: do not state that candidate has direct experience in '{vacancy_domain}'"


def _has_partial_domain_overlap(vacancy_domain: str, candidate_texts: List[str]) -> bool:
    normalized = vacancy_domain.lower().replace("ё", "е")
    text = " ".join(candidate_texts).lower().replace("ё", "е")
    domain_groups = [
        {"bank", "banking", "банк", "банков", "финанс", "financial", "мфо", "кредит", "risk", "риск"},
        {"retail", "e-commerce", "ecommerce", "розниц", "ритейл", "торгов"},
        {"marketing", "agency", "маркетинг", "агентств"},
        {"software", "saas", "it", "разработ", "программ"},
    ]
    for group in domain_groups:
        if any(token in normalized for token in group) and any(token in text for token in group):
            return True
    return False


def _confidence_writing_guidance(strategy_brief: StrategyBrief) -> str:
    confidence = (strategy_brief.strategy_confidence or "medium").lower()
    gaps = [gap for gap in strategy_brief.gaps if canonicalize_phrase(gap)]
    if confidence == "high" and len(gaps) <= 1:
        return "high: direct, but still factual and grounded"
    if confidence == "low" or len(gaps) >= 3:
        return "cautious: avoid strong claims; acknowledge fit through adjacent confirmed experience"
    return "medium: position positively, but do not overstate domain or requirement coverage"


def _split_skill_item(item: str) -> List[str]:
    cleaned = canonicalize_phrase(str(item))
    if not cleaned:
        return []
    if len(cleaned) <= 35 and re.search(r"\s(?:/|;|\|)\s", cleaned):
        return [canonicalize_phrase(part) for part in re.split(r"\s(?:/|;|\|)\s", cleaned) if canonicalize_phrase(part)]
    if len(cleaned) <= 45 and re.match(r"^[A-Za-zА-Яа-я0-9+#.\- ]+(?:,\s*[A-Za-zА-Яа-я0-9+#.\- ]+)+$", cleaned):
        return [canonicalize_phrase(part) for part in cleaned.split(",") if canonicalize_phrase(part)]
    return [cleaned]


def _candidate_evidence_texts(candidate_profile: CandidateProfile) -> List[str]:
    texts: List[str] = []
    texts.extend(candidate_profile.skills_hard)
    texts.extend(candidate_profile.skills_soft)
    texts.append(candidate_profile.target_role or "")
    for job in candidate_profile.jobs:
        texts.extend(filter(None, [job.company_name, job.company_type, job.position, job.period]))
        texts.extend(job.skills_used)
        texts.extend(job.responsibilities)
        texts.extend(job.achievements)
    for education in candidate_profile.education:
        texts.extend(filter(None, [education.institution, education.degree, getattr(education, "field", None)]))
    return [text for text in texts if text]


def _vacancy_strategy_texts(vacancy_profile: VacancyProfile, strategy_brief: StrategyBrief) -> List[str]:
    texts = [
        vacancy_profile.role or "",
        vacancy_profile.seniority or "",
        vacancy_profile.industry or "",
        strategy_brief.positioning,
        strategy_brief.recommendations_short,
    ]
    texts.extend(vacancy_profile.must_have_skills)
    texts.extend(vacancy_profile.nice_to_have_skills)
    texts.extend(vacancy_profile.keywords_for_ats)
    texts.extend(vacancy_profile.key_responsibilities)
    texts.extend(strategy_brief.skills_to_highlight)
    texts.extend(strategy_brief.priority_themes)
    texts.extend(strategy_brief.achievement_highlights)
    return [text for text in texts if text]


def _highlighted_job_texts(candidate_profile: CandidateProfile, highlight_job_ids: List[int]) -> List[str]:
    texts: List[str] = []
    for job in candidate_profile.jobs:
        if job.id not in highlight_job_ids:
            continue
        texts.extend(filter(None, [job.company_name, job.company_type, job.position, job.period]))
        texts.extend(job.skills_used)
        texts.extend(job.responsibilities)
        texts.extend(job.achievements)
    return texts


def _matches_text(item: str, text: str) -> bool:
    normalized_item = re.sub(r"\s+", " ", item.lower().replace("ё", "е")).strip()
    normalized_text = re.sub(r"\s+", " ", text.lower().replace("ё", "е")).strip()
    return bool(normalized_item and normalized_item in normalized_text)


def _canonical_skill_label(item: str, candidate_profile: CandidateProfile) -> str:
    item_key = item.lower().replace("ё", "е")
    for skill in candidate_profile.skills_hard + candidate_profile.skills_soft:
        skill_clean = canonicalize_phrase(skill)
        skill_key = skill_clean.lower().replace("ё", "е")
        if item_key == skill_key:
            return skill_clean
        if len(item_key) >= 5 and item_key in {"excel", "power bi", "tableau", "python", "sql"} and item_key in skill_key:
            return skill_clean
    return canonicalize_phrase(item)


def _candidate_has_related_skill(item: str, candidate_profile: CandidateProfile) -> bool:
    item_key = item.lower().replace("ё", "е")
    aliases = {
        "excel": ["excel", "ms excel"],
        "power bi": ["power bi"],
        "sql": ["sql", "ms sql", "postgresql", "mysql", "greenplum"],
        "python": ["python"],
    }
    candidate_skills = " ".join(candidate_profile.skills_hard + candidate_profile.skills_soft).lower().replace("ё", "е")
    for key, variants in aliases.items():
        if key in item_key and any(variant in candidate_skills for variant in variants):
            return True
    return False


def _is_generic_skill_item(item: str) -> bool:
    lowered = item.lower()
    if lowered in {"аналитик", "данные", "мониторинг", "навыки", "требования"}:
        return True
    generic = [
        "уверенный пользователь", "пользование компьютером", "коммуникабельность",
        "ответственность", "стрессоустойчивость", "внимательность", "грамотная речь",
        "подготовка презентаций", "навыки презентации", "английский язык", "русский язык",
    ]
    return any(pattern in lowered for pattern in generic)


def _is_requirement_phrase_not_skill(item: str) -> bool:
    lowered = item.lower()
    requirement_patterns = [
        "опыт от ", "опыт работы", "опыт в ", "опыт на ", "опыт по ",
        "высшее образование", "образование", "готовность", "умение работать",
        "знание английского", "уровень английского",
    ]
    if any(pattern in lowered for pattern in requirement_patterns):
        return True
    if len(item) > 45 and not re.search(r"\b(sql|python|excel|power bi|tableau|java|r|spark|airflow|etl|dwh|bi|pd/lgd|npl)\b", lowered):
        return True
    return False


def _is_short_unconfirmed_keyword(item: str, candidate_texts: List[str]) -> bool:
    normalized = re.sub(r"[^a-zа-я0-9+#/]+", "", item.lower().replace("ё", "е"))
    if len(normalized) > 4:
        return False
    candidate_blob = " ".join(candidate_texts).lower().replace("ё", "е")
    return normalized not in re.sub(r"[^a-zа-я0-9+#/]+", " ", candidate_blob).split()


def _is_side_domain_skill(item: str) -> bool:
    lowered = item.lower()
    side_domain = [
        "google analytics", "datalens", "a/b", "ab тест", "a/b тест", "retention",
        "маркетинг", "маркетингов", "nps", "csi", "продуктовая аналитика",
    ]
    return any(pattern in lowered for pattern in side_domain)


def _is_unconfirmed_gap_skill(item: str, candidate_texts: List[str]) -> bool:
    lowered = item.lower()
    gap_like = ["инцидент", "эскалац", "grafana", "clickhouse"]
    return any(pattern in lowered for pattern in gap_like) and phrase_match_score(item, candidate_texts) < 0.70


def _format_education(candidate_profile: CandidateProfile) -> str:
    rows = []
    for edu in candidate_profile.education[:5]:
        rows.append(" | ".join(part for part in [edu.institution, edu.degree, getattr(edu, "field", None), edu.year] if part))
    return "; ".join(row for row in rows if row)


def _format_languages(candidate_profile: CandidateProfile) -> str:
    canonical = getattr(candidate_profile, "canonical_profile", None)
    language_items = getattr(canonical, "languages", None) if canonical else None
    if language_items:
        return "; ".join(f"{item.name} {item.level or ''}".strip() for item in language_items if item.name)
    return "; ".join(candidate_profile.languages)


def _normalize_confidence(value: str) -> str:
    normalized = (value or "").lower()
    if "high" in normalized or "высок" in normalized:
        return "high"
    if "low" in normalized or "низк" in normalized:
        return "low"
    return "medium"


def _extract_resume_section(resume_text: str, heading: str) -> str:
    lines = (resume_text or "").splitlines()
    capture = False
    captured: List[str] = []
    for line in lines:
        if line.strip().upper() == heading.upper():
            capture = True
            continue
        if capture and _is_resume_heading(line):
            break
        if capture:
            captured.append(line)
    return "\n".join(captured).strip()


def _technical_marker_checks(resume_text: str) -> List[str]:
    checks = []
    patterns = [
        (r"###\s*job\s+\d+", "В тексте остался технический маркер: ### Job"),
        (r"^\s*Company\s*:", "В тексте остался технический маркер: Company:"),
        (r"^\s*Period\s*:", "В тексте остался технический маркер: Period:"),
    ]
    for pattern, message in patterns:
        if re.search(pattern, resume_text or "", re.IGNORECASE | re.MULTILINE):
            checks.append(message)
    return checks


def _experience_structure_checks(resume_text: str) -> List[str]:
    section = _extract_resume_section(resume_text, "РЕЛЕВАНТНЫЙ ОПЫТ")
    if not section:
        return []

    checks = []
    lines = section.splitlines()
    seen_heading = False
    seen_period_for_current = False
    previous_was_bullet = False
    blank_after_bullet = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if previous_was_bullet:
                blank_after_bullet = True
            continue

        is_bullet = bool(re.match(r"^\s*[•\-*]\s+", line))
        is_heading = _is_human_job_heading(line)
        is_period = _looks_like_period(line)

        if is_bullet:
            bullet_text = re.sub(r"^\s*[•\-*]\s+", "", line).strip()
            if not seen_heading:
                checks.append("Пункт опыта указан до заголовка места работы")
            if _looks_like_period(bullet_text):
                checks.append("Период работы отрендерен как bullet")
            previous_was_bullet = True
            blank_after_bullet = False
            continue

        if is_heading:
            if previous_was_bullet and not blank_after_bullet:
                checks.append("Соседние блоки опыта не разделены пустой строкой")
            seen_heading = True
            seen_period_for_current = False
            previous_was_bullet = False
            blank_after_bullet = False
            continue

        if is_period:
            if not seen_heading:
                checks.append("Период работы указан до заголовка места работы")
            if seen_period_for_current:
                checks.append("В одном блоке опыта найдено несколько периодов")
            seen_period_for_current = True
            previous_was_bullet = False
            blank_after_bullet = False
            continue

        if seen_heading and not is_bullet and not is_period:
            checks.append(f"В блоке опыта есть неструктурированная строка: {line[:80]}")
        previous_was_bullet = False
        blank_after_bullet = False

    return dedupe_preserve(checks)[:6]


def _experience_selling_quality_checks(
    resume_text: str,
    candidate_profile: CandidateProfile,
    strategy_brief: StrategyBrief,
) -> List[str]:
    section = _extract_resume_section(resume_text, "РЕЛЕВАНТНЫЙ ОПЫТ")
    if not section:
        return ["В резюме отсутствует блок релевантного опыта"]

    bullets = _extract_bullets(section)
    highlighted_bullets = _bullets_for_highlighted_jobs(section, candidate_profile, strategy_brief.highlight_job_ids)
    if not highlighted_bullets:
        highlighted_bullets = bullets

    checks: List[str] = []
    duty_like = [bullet for bullet in highlighted_bullets if _is_duty_like_bullet(bullet)]
    if duty_like and len(duty_like) >= max(1, len(highlighted_bullets) // 2):
        checks.append("В highlighted experience слишком много duty-like bullets")

    achievement_sources = strategy_brief.achievement_highlights
    used_achievements = _used_items(achievement_sources, section, threshold=0.40)
    if achievement_sources and not used_achievements:
        checks.append("В highlighted experience не использованы доступные achievement highlights")

    if highlighted_bullets and not any(_has_business_value_signal(bullet) for bullet in highlighted_bullets):
        checks.append("Bullets highlighted jobs не показывают ownership, результат или бизнес-ценность")

    overlong_jobs = _highlighted_jobs_with_too_many_bullets(section, candidate_profile, strategy_brief.highlight_job_ids, max_bullets=4)
    if overlong_jobs:
        checks.append(f"В highlighted jobs слишком много bullets: {', '.join(overlong_jobs[:3])}")

    if _uses_weak_bullets_despite_stronger_sources(highlighted_bullets, candidate_profile, strategy_brief):
        checks.append("Highlighted jobs используют слабые duty-like bullets при наличии более сильных grounded фактов")

    if len(_dedupe_semantic_points(highlighted_bullets)) < len(highlighted_bullets) - 1:
        checks.append("Bullets в relevant experience частично дублируют одну и ту же мысль")

    additional = _extract_resume_section(resume_text, "ДОПОЛНИТЕЛЬНЫЙ ОПЫТ")
    additional_bullets = _extract_bullets(additional)
    if additional_bullets and len(additional_bullets) > max(2, len(highlighted_bullets)):
        checks.append("Дополнительный опыт выглядит детальнее релевантного опыта")

    return dedupe_preserve(checks)[:5]


def _summary_quality_checks(resume_text: str) -> List[str]:
    summary = _extract_resume_section(resume_text, "ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ")
    if not summary:
        return []

    checks = []
    words = re.findall(r"\S+", summary)
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", summary.strip()) if part.strip()]
    if len(words) > 40:
        checks.append(f"Профессиональный профиль слишком длинный: {len(words)} слов")
    if len(sentences) > 3:
        checks.append(f"Профессиональный профиль содержит слишком много предложений: {len(sentences)}")
    if _summary_carries_too_much_selling(summary):
        checks.append("Профессиональный профиль содержит слишком много proof/selling content вместо короткого framing")
    return checks


def _extract_bullets(text: str) -> List[str]:
    bullets = []
    for line in (text or "").splitlines():
        if re.match(r"^\s*[•\-*]\s+", line):
            bullets.append(canonicalize_phrase(re.sub(r"^\s*[•\-*]\s+", "", line)))
    return [item for item in bullets if item]


def _bullets_for_highlighted_jobs(
    relevant_section: str,
    candidate_profile: CandidateProfile,
    highlight_job_ids: List[int],
) -> List[str]:
    if not highlight_job_ids:
        return []

    lines = (relevant_section or "").splitlines()
    current_is_highlighted = False
    bullets: List[str] = []
    highlighted_jobs = [job for job in candidate_profile.jobs if job.id in highlight_job_ids]

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if _is_human_job_heading(line):
            current_is_highlighted = any(
                (job.company_name and job.company_name in line) or (job.position and job.position in line)
                for job in highlighted_jobs
            )
            continue
        if current_is_highlighted and re.match(r"^\s*[•\-*]\s+", line):
            bullets.append(canonicalize_phrase(re.sub(r"^\s*[•\-*]\s+", "", line)))
    return [item for item in bullets if item]


def _highlighted_jobs_with_too_many_bullets(
    relevant_section: str,
    candidate_profile: CandidateProfile,
    highlight_job_ids: List[int],
    *,
    max_bullets: int,
) -> List[str]:
    if not highlight_job_ids:
        return []

    lines = (relevant_section or "").splitlines()
    current_label = ""
    current_count = 0
    overlong: List[str] = []
    highlighted_jobs = [job for job in candidate_profile.jobs if job.id in highlight_job_ids]

    def flush() -> None:
        if current_label and current_count > max_bullets:
            overlong.append(current_label)

    for raw_line in lines + [""]:
        line = raw_line.strip()
        if _is_human_job_heading(line):
            flush()
            current_label = line if any(
                (job.company_name and job.company_name in line) or (job.position and job.position in line)
                for job in highlighted_jobs
            ) else ""
            current_count = 0
            continue
        if current_label and re.match(r"^\s*[•\-*]\s+", line):
            current_count += 1
    flush()
    return dedupe_preserve(overlong)


def _uses_weak_bullets_despite_stronger_sources(
    highlighted_bullets: List[str],
    candidate_profile: CandidateProfile,
    strategy_brief: StrategyBrief,
) -> bool:
    if not highlighted_bullets:
        return False
    weak_count = sum(1 for bullet in highlighted_bullets if _is_duty_like_bullet(bullet))
    if weak_count == 0:
        return False

    strong_sources: List[str] = []
    strong_sources.extend(strategy_brief.achievement_highlights)
    for job in candidate_profile.jobs:
        if job.id in strategy_brief.highlight_job_ids:
            strong_sources.extend(job.achievements)
            strong_sources.extend(point for point in job.responsibilities if _has_business_value_signal(point))
    return bool(strong_sources) and weak_count >= max(1, len(highlighted_bullets) // 2)


def _summary_carries_too_much_selling(summary: str) -> bool:
    lowered = summary.lower()
    proof_signals = (
        "разработал", "внедрил", "настроил", "автоматизировал", "увеличил",
        "сократил", "интегрировал", "обеспечил", "реализовал", "%", "pd/lgd",
    )
    signal_count = sum(1 for signal in proof_signals if signal in lowered)
    return signal_count >= 3


def _is_duty_like_bullet(bullet: str) -> bool:
    lowered = bullet.lower()
    weak_openings = (
        "участвовал", "участвовала", "занимался", "занималась", "работал над",
        "работала над", "выполнял", "выполняла", "помогал", "помогала",
    )
    return lowered.startswith(weak_openings)


def _has_business_value_signal(bullet: str) -> bool:
    lowered = bullet.lower()
    signals = (
        "разработ", "внедр", "настро", "автоматиз", "сформир", "интегр",
        "оптимиз", "увелич", "сократ", "позвол", "обеспеч", "выяв",
        "рекомендац", "модель", "дашборд", "мониторинг", "отчет", "витрин",
        "конверси", "npl", "pd/lgd", "%",
    )
    return any(signal in lowered for signal in signals)


def _is_human_job_heading(line: str) -> bool:
    if not line or line.startswith(("•", "-", "*")):
        return False
    if _looks_like_period(line) or _is_resume_heading(line):
        return False
    if " — " in line:
        return True
    return False


def _irrelevant_skill_checks(
    skills_block: str,
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    strategy_brief: StrategyBrief,
) -> List[str]:
    skills = _parse_skill_block(skills_block)
    if not skills:
        return []

    checks = []
    side_domain = [skill for skill in skills if _is_side_domain_skill(skill)]
    if side_domain:
        checks.append(f"В ключевых навыках есть потенциально нерелевантные пункты: {', '.join(side_domain[:4])}")
    if len(skills) > 12:
        checks.append(f"Блок ключевых навыков может быть слишком широким: {len(skills)} пунктов")

    recommended = set(item.lower() for item in _build_targeted_key_skills(candidate_profile, vacancy_profile, strategy_brief, limit=12))
    weak = [skill for skill in skills if skill.lower() not in recommended and phrase_match_score(skill, _vacancy_strategy_texts(vacancy_profile, strategy_brief)) < 0.25]
    if len(weak) >= 3:
        checks.append(f"В ключевых навыках есть слабо релевантные пункты: {', '.join(weak[:4])}")
    return checks


def _strategy_leakage_checks(
    skills_block: str,
    candidate_profile: CandidateProfile,
    strategy_brief: StrategyBrief,
) -> List[str]:
    skills = _parse_skill_block(skills_block)
    if not skills:
        return []

    candidate_texts = _candidate_evidence_texts(candidate_profile)
    checks = []
    for theme in strategy_brief.priority_themes + [strategy_brief.positioning, strategy_brief.recommendations_short]:
        theme = canonicalize_phrase(theme)
        if not theme:
            continue
        for skill in skills:
            if phrase_match_score(skill, [theme]) >= 0.65 and phrase_match_score(skill, candidate_texts) < 0.55:
                checks.append(f"Стратегическая тема в навыках без достаточного grounding: {skill}")
    return dedupe_preserve(checks)[:4]


def _domain_overclaim_checks(
    resume_text: str,
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
) -> List[str]:
    domain = canonicalize_phrase(vacancy_profile.industry or "")
    if not domain:
        return []

    candidate_texts = _candidate_evidence_texts(candidate_profile)
    if phrase_match_score(domain, candidate_texts) >= 0.55 or _has_partial_domain_overlap(domain, candidate_texts):
        return []

    summary = _extract_resume_section(resume_text, "ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ")
    skills = _extract_resume_section(resume_text, "КЛЮЧЕВЫЕ КОМПЕТЕНЦИИ")
    exposed_text = f"{summary}\n{skills}"
    if phrase_match_score(domain, [exposed_text]) >= 0.50:
        return [f"Домен вакансии «{domain}» звучит как факт кандидата, но не подтвержден профилем"]
    return []


def _parse_skill_block(skills_block: str) -> List[str]:
    text = (skills_block or "").replace("•", "\n").replace("-", "\n")
    parts = re.split(r"[,\n;]+", text)
    return dedupe_preserve(canonicalize_phrase(part) for part in parts if canonicalize_phrase(part))


def _used_downplayed_jobs(
    candidate_profile: CandidateProfile,
    downplay_job_ids: List[int],
    resume_text: str,
) -> List[str]:
    relevant_section = _extract_resume_section(resume_text, "РЕЛЕВАНТНЫЙ ОПЫТ")
    if not relevant_section:
        return []
    used = []
    for job in candidate_profile.jobs:
        if job.id not in downplay_job_ids:
            continue
        if job.company_name and job.company_name in relevant_section:
            used.append(" — ".join(part for part in [job.position, job.company_name] if part) or f"job {job.id}")
            continue
        if not job.company_name and job.position and job.position in relevant_section:
            used.append(" — ".join(part for part in [job.position, job.company_name] if part) or f"job {job.id}")
    return used


def _covered_requirements(requirements: List[str], resume_text: str) -> List[str]:
    return [item for item in requirements if phrase_match_score(item, [resume_text]) >= 0.48]


def _used_items(items: List[str], resume_text: str, threshold: float) -> List[str]:
    return [item for item in items if phrase_match_score(item, [resume_text]) >= threshold]


def _used_highlight_jobs(candidate_profile: CandidateProfile, highlighted_ids: List[int], resume_text: str) -> List[int]:
    used = []
    for job in candidate_profile.jobs:
        if job.id not in highlighted_ids:
            continue
        markers = [job.company_name or "", job.position or "", job.period or ""]
        if any(marker and marker in resume_text for marker in markers):
            used.append(job.id)
    return used


def _company_date_checks(candidate_profile: CandidateProfile, resume_text: str) -> List[str]:
    checks = []
    for job in candidate_profile.jobs:
        if job.company_name and job.company_name in resume_text:
            if job.period and job.period not in resume_text:
                checks.append(f"Компания «{job.company_name}» указана без исходного периода работы")
    return checks


def _skill_hallucination_checks(
    candidate_profile: CandidateProfile,
    vacancy_profile: VacancyProfile,
    strategy_brief: StrategyBrief,
    resume_text: str,
) -> List[str]:
    known_parts = candidate_profile.skills_hard + candidate_profile.skills_soft
    for job in candidate_profile.jobs:
        known_parts.extend(job.skills_used)
        known_parts.extend(job.responsibilities)
        known_parts.extend(job.achievements)
    known = " ".join(known_parts)
    checks = []
    common_tools = ["SQL", "Python", "Excel", "Power BI", "Tableau", "Grafana", "ClickHouse", "Greenplum", "Jira", "Confluence"]
    for tool in common_tools:
        if tool.lower() in resume_text.lower() and tool.lower() not in known.lower():
            checks.append(f"Возможное неподтвержденное упоминание инструмента: {tool}")
    return checks


def _order_jobs(candidate_profile: CandidateProfile, insights, highlight_ids: List[int]):
    score_map = {match.job_id: match.score for match in insights.job_matches}
    return sorted(candidate_profile.jobs, key=lambda job: (0 if job.id in highlight_ids else 1, -score_map.get(job.id, 0.0), job.id))


def _build_summary(candidate_profile, vacancy_profile, strategy_brief, insights) -> str:
    parts = []
    role = candidate_profile.target_role or vacancy_profile.role or "Кандидат"
    if candidate_profile.experience_years:
        parts.append(f"{role} с опытом {candidate_profile.experience_years} года(лет).")
    else:
        parts.append(f"{role}.")
    if strategy_brief.positioning:
        parts.append(strategy_brief.positioning + ".")
    if strategy_brief.priority_themes:
        parts.append(f"Фокус: {', '.join(strategy_brief.priority_themes[:3])}.")
    elif insights.themes:
        parts.append(f"Фокус: {', '.join(insights.themes[:3])}.")
    if insights.gaps:
        parts.append(f"Без додумывания закрывает не все требования: {', '.join(insights.gaps[:2])}.")
    return " ".join(parts)


def _select_job_points(job, job_match, strategy_brief: StrategyBrief) -> List[str]:
    points = []
    for item in strategy_brief.achievement_highlights:
        if phrase_match_score(item, job.responsibilities + job.achievements) >= 0.42:
            points.append(item)
    if job_match and job_match.top_responsibilities:
        points.extend(job_match.top_responsibilities)
    else:
        points.extend(job.responsibilities[:3])
    points.extend(job.achievements[:1])
    cleaned = []
    for point in points:
        if _is_generic_placeholder(point):
            continue
        shortened = _shorten_point(point)
        if shortened:
            cleaned.append(shortened)
        if len(dedupe_preserve(cleaned)) >= 3:
            break
    return dedupe_preserve(cleaned)[:3]


def _build_job_snapshot(job) -> str:
    title = " | ".join(part for part in [job.position, job.company_name, job.period] if part)
    points = _select_job_points(job, None, StrategyBrief())
    return f"{title}: {points[0]}" if points else title


def _shorten_point(text: str) -> str:
    cleaned = canonicalize_phrase(text)
    if len(cleaned) <= 180:
        return cleaned
    lowered = cleaned.lower()
    for separator in [", что позволило", ", которые", ", который", ", которая", ";", ". ", ", включая", ", что"]:
        index = lowered.find(separator)
        if index > 45:
            return cleaned[:index].rstrip(" ,;.")
    return cleaned[:177].rstrip(" ,;.") + "..."


def _is_generic_placeholder(text: str) -> bool:
    lowered = (text or "").lower()
    generic_phrases = [
        "contributed to team", "improved performance", "participated in", "worked on various",
        "gained experience", "collaborated across", "various responsibilities", "key responsibilities",
        "worked on projects", "helped improve", "assisted in",
    ]
    return any(phrase in lowered for phrase in generic_phrases)
