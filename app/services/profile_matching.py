"""Generic matching and ranking helpers for candidate/vacancy adaptation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, List, Sequence

from app.schemas.candidate import CandidateJob, CandidateProfile
from app.schemas.vacancy import VacancyProfile


RUSSIAN_STOPWORDS = {
    "и", "в", "во", "на", "по", "для", "с", "со", "к", "ко", "от", "до",
    "из", "или", "либо", "а", "но", "не", "это", "как", "над", "под", "при",
    "также", "его", "ее", "их", "the", "and", "for", "with", "from", "into",
    "that", "this", "are", "was", "were", "our", "your",
}

GENERIC_THEME_TOKENS = {
    "аналитик", "аналитика", "данные", "данных", "опыт", "работы", "работа",
    "навык", "навыки", "знание", "умение", "требование", "требования",
    "высшее", "образование", "коммуникация", "коммуницировать",
}


@dataclass
class JobMatch:
    job_id: int
    score: float
    matched_requirements: List[str]
    top_responsibilities: List[str]


@dataclass
class StrategyInsights:
    fit_score: float
    highlight_job_ids: List[int]
    downplay_job_ids: List[int]
    skills_to_highlight: List[str]
    gaps: List[str]
    positioning: str
    recommendations_short: str
    covered_must_haves: List[str]
    uncovered_must_haves: List[str]
    themes: List[str]
    job_matches: List[JobMatch]


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().replace("ё", "е")
    text = text.replace("/", " ")
    text = re.sub(r"[^a-zа-я0-9+#.\- ]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def canonicalize_phrase(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip(" ,.;:-"))
    return cleaned


def tokenize(text: str) -> List[str]:
    tokens = []
    for token in normalize_text(text).split():
        token = normalize_token(token)
        if len(token) <= 1:
            continue
        if token.isdigit():
            continue
        if token in RUSSIAN_STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def normalize_token(token: str) -> str:
    token = token.strip(".-+")
    russian_suffixes = (
        "иями", "ями", "ами", "ыми", "ими", "иях", "иям", "ием", "ий", "ый",
        "ой", "ая", "ое", "ые", "ие", "ах", "ях", "ам", "ям",
        "ов", "ев", "ей", "ия", "ие", "ию", "а", "я",
        "ы", "и", "е", "о", "у", "ю",
    )
    english_suffixes = ("ing", "ed", "es", "s")

    for suffix in russian_suffixes:
        if len(token) > 5 and token.endswith(suffix):
            return token[:-len(suffix)]

    for suffix in english_suffixes:
        if len(token) > 4 and token.endswith(suffix):
            return token[:-len(suffix)]

    return token


def dedupe_preserve(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in items:
        cleaned = canonicalize_phrase(item)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        result.append(cleaned)
        seen.add(lowered)
    return result


def phrase_match_score(phrase: str, texts: Sequence[str]) -> float:
    phrase_norm = normalize_text(phrase)
    if not phrase_norm or not texts:
        return 0.0

    phrase_tokens = set(tokenize(phrase))
    best = 0.0

    for text in texts:
        text_norm = normalize_text(text)
        if not text_norm:
            continue

        if phrase_norm and phrase_norm in text_norm:
            best = max(best, 1.0)
            continue

        text_tokens = set(tokenize(text))
        if not phrase_tokens or not text_tokens:
            continue

        overlap = phrase_tokens & text_tokens
        if not overlap:
            continue

        recall = len(overlap) / len(phrase_tokens)
        precision = len(overlap) / max(len(text_tokens), 1)
        score = (recall * 0.8) + min(precision, 0.35)
        if len(phrase_tokens) >= 2 and len(overlap) == 1:
            score = min(score, 0.45)

        if len(phrase_tokens) == 1:
            score = max(score, 0.75 if next(iter(phrase_tokens)) in text_tokens else 0.0)

        best = max(best, min(score, 0.95))

    return min(best, 1.0)


def infer_seniority_score(experience_years: int | None, seniority: str | None) -> float:
    if not seniority:
        return 0.6
    if experience_years is None:
        return 0.45

    seniority_norm = normalize_text(seniority)
    if any(marker in seniority_norm for marker in ("junior", "intern", "стаж", "начал")):
        return 1.0 if experience_years <= 2 else 0.7
    if any(marker in seniority_norm for marker in ("middle", "mid", "1 3", "2 4")):
        return 1.0 if 1 <= experience_years <= 4 else 0.75
    if any(marker in seniority_norm for marker in ("senior", "lead", "head", "3 6", "более 6")):
        return 1.0 if experience_years >= 4 else 0.45
    return 0.65


def is_education_requirement(phrase: str) -> bool:
    norm = normalize_text(phrase)
    return "образован" in norm or "degree" in norm or "бакалав" in norm or "магистр" in norm


def is_language_requirement(phrase: str) -> bool:
    norm = normalize_text(phrase)
    return "англий" in norm or "english" in norm or "язык" in norm


def candidate_global_texts(candidate_profile: CandidateProfile) -> List[str]:
    texts: List[str] = []
    if candidate_profile.target_role:
        texts.append(candidate_profile.target_role)
    texts.extend(candidate_profile.skills_hard)
    texts.extend(candidate_profile.skills_soft)
    texts.extend(candidate_profile.languages)

    for education in candidate_profile.education:
        texts.extend(filter(None, [education.institution, education.degree, education.year]))

    for job in candidate_profile.jobs:
        texts.extend(job_texts(job))

    return [text for text in texts if text]


def job_texts(job: CandidateJob) -> List[str]:
    texts: List[str] = []
    texts.extend(filter(None, [job.position, job.company_name, job.period]))
    texts.extend(job.responsibilities)
    texts.extend(job.achievements)
    texts.extend(job.skills_used)
    return texts


def combined_vacancy_phrases(vacancy_profile: VacancyProfile) -> List[str]:
    phrases = []
    if vacancy_profile.role:
        phrases.append(vacancy_profile.role)
    phrases.extend(vacancy_profile.must_have_skills)
    phrases.extend(vacancy_profile.nice_to_have_skills)
    phrases.extend(vacancy_profile.key_responsibilities)
    phrases.extend(vacancy_profile.keywords_for_ats)
    return dedupe_preserve(phrases)


def extract_competency_themes(texts: Sequence[str], limit: int = 3) -> List[str]:
    candidates = []
    for text in texts:
        phrase = canonicalize_phrase(text)
        if not phrase:
            continue
        tokens = [token for token in tokenize(phrase) if token not in GENERIC_THEME_TOKENS]
        if not tokens:
            continue
        candidates.append(phrase)

    ranked = sorted(
        dedupe_preserve(candidates),
        key=lambda value: (-len(tokenize(value)), value.lower()),
    )
    return ranked[:limit]


def is_display_noise_phrase(phrase: str) -> bool:
    norm = normalize_text(phrase)
    tokens = tokenize(phrase)
    if not tokens:
        return True
    if len(canonicalize_phrase(phrase)) > 55:
        return True
    if len(tokens) > 6:
        return True
    if is_education_requirement(phrase):
        return True
    if "компьютер" in norm:
        return True
    if "вакансия" in norm:
        return True
    if norm.startswith("опыт ") and len(tokens) >= 3:
        return True
    if re.match(r"^(анализировать|проводить|выявлять|отслеживать|вести|коммуницировать)\b", norm):
        return True
    if len(tokens) == 1 and tokens[0] in GENERIC_THEME_TOKENS:
        return True
    return False


def is_generic_requirement_phrase(phrase: str) -> bool:
    norm = normalize_text(phrase)
    if is_education_requirement(phrase):
        return True
    if "компьютер" in norm:
        return True
    if norm.startswith("опыт ") and len(tokenize(phrase)) >= 3:
        return True
    tokens = tokenize(phrase)
    return len(tokens) == 1 and tokens[0] in GENERIC_THEME_TOKENS


def _requirement_coverage_score(
    candidate_profile: CandidateProfile,
    phrase: str,
    evidence_texts: Sequence[str],
) -> float:
    if is_education_requirement(phrase) and candidate_profile.education:
        return 1.0
    if is_language_requirement(phrase):
        joined_languages = " ".join(candidate_profile.languages)
        if phrase_match_score(phrase, [joined_languages]) >= 0.7:
            return 1.0
    if "компьютер" in normalize_text(phrase) and (
        candidate_profile.skills_hard or candidate_profile.jobs
    ):
        return 0.8
    return phrase_match_score(phrase, evidence_texts)


def _job_requirement_score(job: CandidateJob, vacancy_profile: VacancyProfile) -> JobMatch:
    texts = job_texts(job)
    weighted_matches = []

    for phrase in dedupe_preserve(vacancy_profile.must_have_skills):
        score = phrase_match_score(phrase, texts)
        weight = 1.5 if is_generic_requirement_phrase(phrase) else 4.0
        weighted_matches.append((phrase, score, weight))

    for phrase in dedupe_preserve(vacancy_profile.key_responsibilities):
        score = phrase_match_score(phrase, texts)
        weighted_matches.append((phrase, score, 3.0))

    if vacancy_profile.role and not is_generic_requirement_phrase(vacancy_profile.role):
        score = phrase_match_score(vacancy_profile.role, texts)
        weighted_matches.append((vacancy_profile.role, score, 2.0))

    total_weight = sum(weight for _, _, weight in weighted_matches) or 1.0
    weighted_score = sum(score * weight for _, score, weight in weighted_matches) / total_weight
    joined_text = " ".join(texts)
    if vacancy_profile.industry and "bank" in normalize_text(vacancy_profile.industry):
        if re.search(r"\bбанк|банков|кредит|портфел|риск", normalize_text(joined_text)):
            weighted_score += 0.08

    matched_requirements = [
        phrase for phrase, score, _ in sorted(weighted_matches, key=lambda item: item[1], reverse=True)
        if score >= 0.5 and not is_display_noise_phrase(phrase)
    ][:5]

    scored_responsibilities = []
    phrases = dedupe_preserve(
        vacancy_profile.must_have_skills + vacancy_profile.key_responsibilities + vacancy_profile.keywords_for_ats
    )
    for responsibility in job.responsibilities:
        score = max((phrase_match_score(phrase, [responsibility]) for phrase in phrases), default=0.0)
        scored_responsibilities.append((responsibility, score))

    scored_responsibilities.sort(key=lambda item: item[1], reverse=True)
    top_responsibilities = [text for text, score in scored_responsibilities if score >= 0.28][:3]
    if not top_responsibilities:
        top_responsibilities = [text for text, _ in scored_responsibilities[:2]]

    return JobMatch(
        job_id=job.id,
        score=round(min(weighted_score, 0.98), 3),
        matched_requirements=dedupe_preserve(matched_requirements),
        top_responsibilities=top_responsibilities,
    )


def analyze_candidate_fit(candidate_profile: CandidateProfile, vacancy_profile: VacancyProfile) -> StrategyInsights:
    evidence_texts = candidate_global_texts(candidate_profile)
    must_haves = dedupe_preserve(vacancy_profile.must_have_skills)
    responsibilities = dedupe_preserve(vacancy_profile.key_responsibilities)

    must_scores = [
        (phrase, _requirement_coverage_score(candidate_profile, phrase, evidence_texts))
        for phrase in must_haves
    ]
    responsibility_scores = [
        (phrase, phrase_match_score(phrase, evidence_texts))
        for phrase in responsibilities
    ]

    covered_must_haves = [phrase for phrase, score in must_scores if score >= 0.58]
    uncovered_must_haves = [phrase for phrase, score in must_scores if score < 0.58]

    role_texts = [candidate_profile.target_role] + [job.position or "" for job in candidate_profile.jobs]
    role_alignment = phrase_match_score(vacancy_profile.role or "", role_texts)
    seniority_alignment = infer_seniority_score(candidate_profile.experience_years, vacancy_profile.seniority)

    must_component = (
        sum(score for _, score in must_scores) / len(must_scores) if must_scores else 0.65
    )
    responsibility_component = (
        sum(score for _, score in responsibility_scores) / len(responsibility_scores)
        if responsibility_scores else 0.55
    )

    fit_score = (
        must_component * 0.5
        + responsibility_component * 0.25
        + role_alignment * 0.15
        + seniority_alignment * 0.10
    )
    fit_score = max(0.18, min(round(fit_score, 3), 0.95))

    ranked_jobs = sorted(
        (_job_requirement_score(job, vacancy_profile) for job in candidate_profile.jobs),
        key=lambda item: item.score,
        reverse=True,
    )

    highlight_job_ids = [match.job_id for match in ranked_jobs if match.score >= 0.24][:3]
    if not highlight_job_ids and ranked_jobs:
        highlight_job_ids = [ranked_jobs[0].job_id]
    if ranked_jobs and highlight_job_ids:
        top_score = ranked_jobs[0].score
        for match in ranked_jobs[1:]:
            if match.job_id in highlight_job_ids:
                continue
            if match.score >= 0.18 and match.score >= top_score - 0.03:
                highlight_job_ids.append(match.job_id)
            if len(highlight_job_ids) >= 3:
                break

    downplay_job_ids = [job.id for job in candidate_profile.jobs if job.id not in highlight_job_ids]

    relevant_phrases = []
    relevant_phrases.extend(covered_must_haves)
    for match in ranked_jobs[:2]:
        relevant_phrases.extend(match.matched_requirements[:3])
    relevant_phrases.extend(candidate_profile.skills_hard)
    relevant_phrases = dedupe_preserve(relevant_phrases)

    phrase_scores = []
    vacancy_phrases = combined_vacancy_phrases(vacancy_profile)
    for phrase in relevant_phrases:
        if is_display_noise_phrase(phrase):
            continue
        score = max(
            [phrase_match_score(phrase, [vacancy_phrase]) for vacancy_phrase in vacancy_phrases] + [0.0]
        )
        if phrase in covered_must_haves:
            score = max(score, 0.9)
        phrase_scores.append((phrase, score))

    phrase_scores.sort(key=lambda item: (-item[1], -len(tokenize(item[0]))))
    skills_to_highlight = [phrase for phrase, score in phrase_scores if score >= 0.55][:8]
    if not skills_to_highlight:
        skills_to_highlight = [
            phrase for phrase in dedupe_preserve(candidate_profile.skills_hard)
            if not is_display_noise_phrase(phrase)
        ][:6]

    theme_sources = []
    theme_sources.extend(skills_to_highlight)
    theme_sources.extend(match.matched_requirements[0] for match in ranked_jobs if match.matched_requirements)
    themes = extract_competency_themes(theme_sources, limit=3)

    target_role = candidate_profile.target_role or vacancy_profile.role or "Кандидат"
    lead_job = next((job for job in candidate_profile.jobs if job.id == highlight_job_ids[0]), None) if highlight_job_ids else None
    if lead_job and len(skills_to_highlight) < 4:
        supplemental = []
        lead_texts = job_texts(lead_job)
        for skill in dedupe_preserve(candidate_profile.skills_hard):
            if is_display_noise_phrase(skill) or skill in skills_to_highlight:
                continue
            score = max(
                phrase_match_score(skill, lead_texts),
                max((phrase_match_score(skill, [vacancy_phrase]) for vacancy_phrase in vacancy_phrases), default=0.0),
            )
            if score >= 0.45:
                supplemental.append((skill, score))
        supplemental.sort(key=lambda item: (-item[1], item[0].lower()))
        for skill, _ in supplemental:
            skills_to_highlight.append(skill)
            if len(skills_to_highlight) >= 4:
                break

    focus_points = []
    if lead_job and lead_job.position and normalize_text(lead_job.position) != normalize_text(target_role):
        focus_points.append(lead_job.position)
    focus_points.extend(themes[:2])
    focus_points = dedupe_preserve(focus_points)

    if focus_points:
        positioning = f"{target_role} с релевантным опытом: {', '.join(focus_points)}"
    else:
        positioning = target_role
    if vacancy_profile.industry and "bank" in normalize_text(vacancy_profile.industry):
        positioning += " в банковском контуре"

    top_job = next((job for job in candidate_profile.jobs if job.id in highlight_job_ids[:1]), None)
    top_job_focus = top_job.position if top_job and top_job.position else candidate_profile.target_role or vacancy_profile.role
    recommendation_parts = []
    if themes:
        recommendation_parts.append(f"Вынести наверх опыт в {', '.join(themes[:2])}")
    if top_job_focus:
        recommendation_parts.append(f"сделать опорой роль {top_job_focus}")
    if uncovered_must_haves:
        recommendation_parts.append(f"честно закрыть или отметить пробелы: {', '.join(uncovered_must_haves[:2])}")
    recommendations_short = "; ".join(recommendation_parts) or "Сместить акцент на наиболее релевантный опыт и подтвержденные компетенции."

    return StrategyInsights(
        fit_score=fit_score,
        highlight_job_ids=highlight_job_ids,
        downplay_job_ids=downplay_job_ids,
        skills_to_highlight=skills_to_highlight,
        gaps=uncovered_must_haves[:4],
        positioning=positioning,
        recommendations_short=recommendations_short,
        covered_must_haves=covered_must_haves,
        uncovered_must_haves=uncovered_must_haves,
        themes=themes,
        job_matches=ranked_jobs,
    )
