from __future__ import annotations

import importlib
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.config import CANDIDATE_EVIDENCE_VALIDATION_ENABLED
from app.schemas.candidate import (
    CandidateCanonicalProfile,
    CandidateEvidenceBlock,
    CandidateJob,
    CandidateJobEvidenceItem,
    CandidateProfile,
    ConfidenceBlock,
    EducationItem,
    LanguageItem,
    ProvenanceItem,
)

logger = logging.getLogger(__name__)


SECTION_DEFINITIONS = [
    ("desired_role", [r"^желаемая должность", r"^desired role", r"^headline", r"^target role"]),
    ("summary", [r"^о себе", r"^summary", r"^profile", r"^professional summary"]),
    ("work_experience", [r"^опыт работы", r"^experience", r"^work experience", r"^employment"]),
    ("skills", [r"^навыки", r"^skills", r"^tech stack", r"^competencies"]),
    ("education", [r"^образование", r"^education", r"^academic background"]),
    ("languages", [r"^языки", r"^languages"]),
    ("certifications", [r"^сертификат", r"^certification", r"^licenses?"]),
]

SECTION_PRIORITY = [
    "header",
    "desired_role",
    "summary",
    "work_experience",
    "skills",
    "education",
    "languages",
    "certifications",
    "other",
]

TOKEN_BUDGETS = {
    "header": 250,
    "desired_role": 180,
    "summary": 220,
    "work_experience": 1200,
    "skills": 350,
    "education": 220,
    "languages": 120,
    "certifications": 120,
    "other": 120,
}

MONTH_ALIASES = {
    "январь": 1,
    "января": 1,
    "january": 1,
    "jan": 1,
    "февраль": 2,
    "февраля": 2,
    "february": 2,
    "feb": 2,
    "март": 3,
    "марта": 3,
    "march": 3,
    "mar": 3,
    "апрель": 4,
    "апреля": 4,
    "april": 4,
    "apr": 4,
    "май": 5,
    "мая": 5,
    "may": 5,
    "июнь": 6,
    "июня": 6,
    "june": 6,
    "jun": 6,
    "июль": 7,
    "июля": 7,
    "july": 7,
    "jul": 7,
    "август": 8,
    "августа": 8,
    "august": 8,
    "aug": 8,
    "сентябрь": 9,
    "сентября": 9,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "октябрь": 10,
    "октября": 10,
    "october": 10,
    "oct": 10,
    "ноябрь": 11,
    "ноября": 11,
    "november": 11,
    "nov": 11,
    "декабрь": 12,
    "декабря": 12,
    "december": 12,
    "dec": 12,
}

LANGUAGE_NAME_MAP = {
    "русский": "Русский",
    "russian": "Русский",
    "английский": "Английский",
    "english": "Английский",
    "немецкий": "Немецкий",
    "german": "Немецкий",
    "французский": "Французский",
    "french": "Французский",
    "испанский": "Испанский",
    "spanish": "Испанский",
    "китайский": "Китайский",
    "chinese": "Китайский",
}

LANGUAGE_LEVEL_PATTERNS = {
    r"\bupper[- ]?intermediate\b": "Upper-Intermediate",
    r"\blower[- ]?intermediate\b": "Lower-Intermediate",
    r"\bpre[- ]?intermediate\b": "Pre-Intermediate",
    r"\bb2\b": "B2",
    r"\bb1\b": "B1",
    r"\bc1\b": "C1",
    r"\bc2\b": "C2",
    r"\ba1\b": "A1",
    r"\ba2\b": "A2",
    r"advanced|свобод": "Advanced",
    r"intermediate|средне": "Intermediate",
    r"elementary|basic|базов": "Basic",
    r"fluent|свободное владение": "Fluent",
    r"native|родн": "Native",
}

SOFT_SKILL_NOISE = {
    "коммуникабельность",
    "ответственность",
    "стрессоустойчивость",
    "user",
    "hard skills",
    "soft skills",
    "skills",
    "skill",
}

PRESENTATION_SOFT_SKILL_PATTERNS = [
    r"\bподготовк[а-я]*\s+презентац",
    r"\bнавык[а-я]*\s+презентац",
    r"\bpresentation skills?\b",
    r"\bpreparing presentations?\b",
]

HARD_SKILL_PREFIX_NOISE = [
    r"^навыки?\s+",
    r"^знание\s+",
    r"^уверенное\s+владение\s+",
    r"^опыт\s+работы\s+с\s+",
]

ROLE_NOISE_PATTERNS = [
    r"^резюме$",
    r"^curriculum vitae$",
    r"^cv$",
    r"^специализации",
]

IMPACT_PATTERNS = [
    r"\b\d+(?:[.,]\d+)?\s*%",
    r"\b(?:increase|decrease|reduce|improve|grow|boost|cut|save|deliver|achiev|optimi[sz]e)\w*",
    r"\b(?:увелич|сократ|сниз|оптимиз|ускор|рост|роста|повыс|достиг|внедрил|внедрила|позволил|позволила|автоматиз)\w*",
    r"\b(?:resulted in|led to|enabled|allowing|which helped|что позволило|что помогло)\b",
]

DOMAIN_CONTEXT_PATTERNS = {
    "bank / financial sector": [r"\bбанк\b", r"\bbank(?:ing)?\b", r"финансов", r"\bfintech\b", r"\bpayments?\b", r"\bcredit\b", r"лизинг"],
    "retail / e-commerce": [r"\bretail\b", r"рознич", r"ритейл", r"\be-?commerce\b", r"\bmarketplace\b", r"маркетплейс", r"магазин"],
    "software / SaaS": [r"\bsaas\b", r"\bsoftware\b", r"\bplatform\b", r"\bproduct company\b", r"\bsoftware\b", r"\bweb\b"],
    "marketing agency": [r"маркетингов", r"\bmarketing\b", r"\bagency\b", r"\bmedia\b", r"агентств"],
    "telecom": [r"\btelecom\b", r"телеком", r"связ"],
    "consulting": [r"\bconsulting\b", r"консалт"],
    "logistics": [r"\blogistics\b", r"логист", r"supply chain"],
    "manufacturing": [r"\bmanufactur", r"производств", r"industrial"],
}

COMPANY_TYPE_ALIASES = {
    "bank": "bank / financial sector",
    "banking": "bank / financial sector",
    "financial": "bank / financial sector",
    "financialsector": "bank / financial sector",
    "finance": "bank / financial sector",
    "fintech": "bank / financial sector",
    "retail": "retail / e-commerce",
    "ecommerce": "retail / e-commerce",
    "e-commerce": "retail / e-commerce",
    "marketplace": "retail / e-commerce",
    "agency": "marketing agency",
    "marketingagency": "marketing agency",
    "marketing": "marketing agency",
    "software": "software / SaaS",
    "saas": "software / SaaS",
    "softwareasaservice": "software / SaaS",
}

EXPERIENCE_EXPLICIT_PATTERNS = [
    r"опыт работы[^.\n:]*[:—-]?\s*(\d+)\s*(?:года|год|лет)\s*(\d+)?\s*(?:месяца|месяцев|месяц)?",
    r"(?:total\s+)?experience[^.\n:]*[:—-]?\s*(\d+)\s*years?\s*(\d+)?\s*months?",
]

JOB_HEADER_NOISE = {
    "responsibilities",
    "achievements",
    "experience",
    "work experience",
    "skills",
    "education",
    "languages",
}


def _load_optional_module(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def normalize_whitespace(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def canonicalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip(" ,.;:-")


def normalize_phrase_key(value: str) -> str:
    normalized = canonicalize_text(value).lower()
    normalized = normalized.replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9]+", "", normalized)
    return normalized


def estimate_tokens(text: str) -> int:
    if not text:
        return 0

    tiktoken = _load_optional_module("tiktoken")
    if tiktoken:
        try:
            encoder = tiktoken.get_encoding("cl100k_base")
            return len(encoder.encode(text))
        except Exception:
            pass

    return max(1, math.ceil(len(text) / 4))


def trim_to_token_budget(text: str, token_budget: int) -> str:
    if not text:
        return ""
    if estimate_tokens(text) <= token_budget:
        return text

    lines = [line for line in text.splitlines() if line.strip()]
    kept: List[str] = []
    used = 0
    for line in lines:
        line_tokens = estimate_tokens(line) + 1
        if used + line_tokens > token_budget:
            break
        kept.append(line)
        used += line_tokens

    result = "\n".join(kept).strip()
    if result == text.strip():
        return result
    return result + "\n[TRUNCATED]"


@dataclass
class SourceSpan:
    start_line: int
    end_line: int


@dataclass
class ResumeSectionBlock:
    block_id: str
    section_name: str
    raw_text: str
    start_line: int
    end_line: int
    normalized_block_text: str


@dataclass
class JobSourceBlock:
    block_id: str
    raw_block_text: str
    start_line: int
    end_line: int
    section_name: str
    normalized_block_text: str
    boundary_confidence: str = "medium"


@dataclass
class ResumeSectionPreview:
    normalized_text: str
    section_texts: Dict[str, str]
    section_blocks: Dict[str, ResumeSectionBlock]
    job_blocks: List[JobSourceBlock]
    section_preview: str
    llm_resume_text: str
    was_truncated: bool


def detect_resume_sections(resume_text: str, soft_input_budget: int = 2500) -> ResumeSectionPreview:
    normalized_text = normalize_whitespace(resume_text)
    lines = normalized_text.splitlines()

    section_positions: List[Tuple[int, str]] = []
    for index, raw_line in enumerate(lines):
        line = canonicalize_text(raw_line).lower()
        if not line:
            continue
        for section_name, patterns in SECTION_DEFINITIONS:
            if any(re.search(pattern, line) for pattern in patterns):
                section_positions.append((index, section_name))
                break

    deduped_positions: List[Tuple[int, str]] = []
    seen_sections = set()
    for index, section_name in section_positions:
        if deduped_positions and deduped_positions[-1][0] == index:
            continue
        if section_name in seen_sections and section_name != "work_experience":
            continue
        deduped_positions.append((index, section_name))
        seen_sections.add(section_name)

    section_texts: Dict[str, str] = {name: "" for name in SECTION_PRIORITY}
    section_ranges: Dict[str, Tuple[int, int]] = {}
    if not deduped_positions:
        section_texts["header"] = normalized_text
        if lines:
            section_ranges["header"] = (1, len(lines))
    else:
        first_index = deduped_positions[0][0]
        section_texts["header"] = "\n".join(lines[:first_index]).strip()
        if first_index > 0:
            section_ranges["header"] = (1, first_index)
        for pos, (line_index, section_name) in enumerate(deduped_positions):
            end_index = deduped_positions[pos + 1][0] if pos + 1 < len(deduped_positions) else len(lines)
            section_texts[section_name] = "\n".join(lines[line_index:end_index]).strip()
            if end_index > line_index:
                section_ranges[section_name] = (line_index + 1, end_index)

        used_line_indexes = {idx for idx, _ in deduped_positions}
        other_lines = [line for idx, line in enumerate(lines) if idx not in used_line_indexes]
        existing = "\n".join(other_lines).strip()
        if existing and not section_texts["other"]:
            section_texts["other"] = existing
            section_ranges["other"] = (1, len(lines))

    section_blocks: Dict[str, ResumeSectionBlock] = {}
    for section_name, content in section_texts.items():
        if not content.strip():
            continue
        start_line, end_line = section_ranges.get(section_name, (1, len(lines) if lines else 1))
        section_blocks[section_name] = ResumeSectionBlock(
            block_id=f"section:{section_name}",
            section_name=section_name,
            raw_text=content,
            start_line=start_line,
            end_line=end_line,
            normalized_block_text=normalize_whitespace(content),
        )

    preview_blocks = []
    for section_name in SECTION_PRIORITY:
        content = canonicalize_text(section_texts.get(section_name, ""))
        if not content:
            continue
        preview_lines = [line.strip() for line in section_texts[section_name].splitlines() if line.strip()][:6]
        preview_blocks.append(f"[{section_name}]\n" + "\n".join(preview_lines))
    section_preview = "\n\n".join(preview_blocks).strip()

    llm_blocks: List[str] = []
    remaining_budget = soft_input_budget
    for section_name in SECTION_PRIORITY:
        content = section_texts.get(section_name, "").strip()
        if not content or remaining_budget <= 0:
            continue
        section_budget = min(TOKEN_BUDGETS.get(section_name, 120), remaining_budget)
        trimmed = trim_to_token_budget(content, section_budget)
        if not trimmed:
            continue
        llm_blocks.append(f"{section_name.upper()}:\n{trimmed}")
        remaining_budget -= min(estimate_tokens(trimmed), section_budget)

    llm_resume_text = "\n\n".join(llm_blocks).strip() or normalized_text
    was_truncated = estimate_tokens(normalized_text) > soft_input_budget

    return ResumeSectionPreview(
        normalized_text=normalized_text,
        section_texts=section_texts,
        section_blocks=section_blocks,
        job_blocks=detect_job_source_blocks(section_blocks, normalized_text),
        section_preview=section_preview,
        llm_resume_text=llm_resume_text,
        was_truncated=was_truncated,
    )


def detect_job_source_blocks(
    section_blocks: Dict[str, ResumeSectionBlock],
    normalized_text: str,
) -> List[JobSourceBlock]:
    source_sections = []
    if section_blocks.get("work_experience"):
        source_sections.append(section_blocks["work_experience"])
    else:
        full_lines = normalized_text.splitlines()
        source_sections.append(
            ResumeSectionBlock(
                block_id="section:full_resume",
                section_name="full_resume",
                raw_text=normalized_text,
                start_line=1,
                end_line=len(full_lines) if full_lines else 1,
                normalized_block_text=normalized_text,
            )
        )

    blocks: List[JobSourceBlock] = []
    for section in source_sections:
        section_lines = section.raw_text.splitlines()
        candidate_period_indexes = [
            index for index, line in enumerate(section_lines)
            if _looks_like_job_period_line(line)
        ]
        if not candidate_period_indexes:
            continue

        starts = [_find_job_block_start(section_lines, index) for index in candidate_period_indexes]
        for ordinal, period_index in enumerate(candidate_period_indexes):
            start = starts[ordinal]
            next_start = starts[ordinal + 1] if ordinal + 1 < len(starts) else len(section_lines)
            end = max(period_index + 1, next_start)
            raw_block_lines = section_lines[start:end]
            raw_block_text = "\n".join(raw_block_lines).strip()
            if not _looks_like_valid_job_block(raw_block_text):
                continue

            block_number = len(blocks) + 1
            start_line = section.start_line + start
            end_line = section.start_line + end - 1
            blocks.append(
                JobSourceBlock(
                    block_id=f"job_source:{block_number}",
                    raw_block_text=raw_block_text,
                    start_line=start_line,
                    end_line=end_line,
                    section_name=section.section_name,
                    normalized_block_text=normalize_whitespace(raw_block_text),
                    boundary_confidence="high" if section.section_name == "work_experience" else "medium",
                )
            )

    return blocks


def _looks_like_job_period_line(line: str) -> bool:
    cleaned = canonicalize_text(line).lower()
    if not cleaned:
        return False
    if re.search(r"(опыт работы|experience)[^.\n]*(?:год|years?|months?|месяц)", cleaned):
        return False
    has_year = bool(re.search(r"\b(19\d{2}|20\d{2})\b", cleaned))
    has_range = bool(re.search(r"(—|-|to|по|present|current|настоящее)", cleaned))
    has_month = any(month in cleaned for month in MONTH_ALIASES)
    return has_year and (has_range or has_month)


def _find_job_block_start(lines: Sequence[str], period_index: int) -> int:
    start = period_index
    for index in range(period_index - 1, max(-1, period_index - 4), -1):
        line = lines[index].strip()
        if not line:
            break
        if _is_bullet_like(line):
            break
        if _looks_like_section_heading(line):
            break
        start = index
    return start


def _looks_like_valid_job_block(raw_block_text: str) -> bool:
    lines = [line.strip() for line in raw_block_text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    has_period = any(_looks_like_job_period_line(line) for line in lines[:4])
    non_bullet_header_lines = [line for line in lines[:5] if not _is_bullet_like(line) and not _looks_like_job_period_line(line)]
    has_body = any(_is_bullet_like(line) for line in lines[2:]) or len(lines) >= 4
    return has_period and len(non_bullet_header_lines) >= 1 and has_body


def _is_bullet_like(line: str) -> bool:
    return bool(re.match(r"^\s*(?:[-•*]|\d+[.)])\s+", line))


def _looks_like_section_heading(line: str) -> bool:
    lowered = canonicalize_text(line).lower()
    if not lowered:
        return False
    return any(any(re.search(pattern, lowered) for pattern in patterns) for _, patterns in SECTION_DEFINITIONS)


def build_evidence_map(
    resume_text: str,
    profile: CandidateProfile,
    preview: Optional[ResumeSectionPreview] = None,
) -> Dict[str, List[str]]:
    evidence, _ = build_evidence_package(resume_text, profile, preview)
    return evidence.to_legacy_dict()


def parse_candidate_profile_section_text(response_text: str) -> CandidateProfile:
    """Parse the LLM's section-based CandidateProfile response into the public schema."""
    sections = _parse_section_blocks(response_text or "")
    evidence = CandidateEvidenceBlock()

    target_role = _section_value(sections, "TARGET_ROLE")
    experience_months = _parse_int(_section_value(sections, "EXPERIENCE_MONTHS"))
    experience_raw = _section_value(sections, "EXPERIENCE_RAW")
    summary_raw = _section_value(sections, "SUMMARY_RAW")

    jobs: List[CandidateJob] = []
    for section_name in sorted(
        (name for name in sections if re.match(r"^JOB_\d+$", name)),
        key=lambda name: int(name.split("_")[1]),
    ):
        job_id = int(section_name.split("_")[1])
        job, job_evidence = _parse_job_section(job_id, sections[section_name])
        if job:
            jobs.append(job)
            evidence.jobs.append(job_evidence)

    skills_hard = _parse_semicolon_section(sections.get("SKILLS_HARD", []))
    skills_soft = _parse_semicolon_section(sections.get("SKILLS_SOFT", []))
    education = _parse_education_section(sections.get("EDUCATION", []))
    languages = _parse_languages_section(sections.get("LANGUAGES", []))
    certifications = _parse_semicolon_section(sections.get("CERTIFICATIONS", []))
    ambiguities = _parse_bullet_or_line_section(sections.get("AMBIGUITIES", []))
    raw_warnings = _parse_bullet_or_line_section(sections.get("WARNINGS", []))

    evidence.target_role = [target_role] if target_role else []
    evidence.total_experience = [experience_raw] if experience_raw else []
    evidence.skills_section = ["; ".join(skills_hard)] if skills_hard else []
    evidence.education = [line for line in sections.get("EDUCATION", []) if line.strip()]
    evidence.languages = [line for line in sections.get("LANGUAGES", []) if line.strip()]

    if "TARGET_ROLE" not in sections:
        raw_warnings.append("CandidateProfile section missing: TARGET_ROLE")
    if "EXPERIENCE_MONTHS" not in sections:
        raw_warnings.append("CandidateProfile section missing: EXPERIENCE_MONTHS")
    if not jobs:
        raw_warnings.append("CandidateProfile section parser found no jobs")

    canonical = CandidateCanonicalProfile(
        target_role=target_role or None,
        experience_years=(experience_months // 12) if experience_months is not None else None,
        experience_months=experience_months,
        summary_raw=summary_raw or None,
        jobs=jobs,
        skills_hard=skills_hard,
        skills_soft=skills_soft,
        education=education,
        languages=languages,
        certifications=certifications,
    )
    return CandidateProfile(
        canonical_profile=canonical,
        evidence=evidence,
        ambiguities=ambiguities,
        raw_warnings=raw_warnings,
    )


def _parse_section_blocks(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    cleaned = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
    for raw_line in cleaned.splitlines():
        line = raw_line.rstrip()
        match = re.match(r"^\s*\[([A-Z][A-Z0-9_]*?)\]\s*$", line)
        if match:
            current = match.group(1).upper()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return sections


def _section_value(sections: Dict[str, List[str]], name: str) -> str:
    lines = [canonicalize_text(line) for line in sections.get(name, []) if canonicalize_text(line)]
    return "\n".join(lines).strip()


def _parse_int(value: str) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def _parse_semicolon_section(lines: Sequence[str]) -> List[str]:
    joined = "\n".join(lines)
    parts = re.split(r";|\n|,", joined)
    return _dedupe_strings([canonicalize_text(part.lstrip("-•* ")) for part in parts if canonicalize_text(part.lstrip("-•* "))])


def _parse_bullet_or_line_section(lines: Sequence[str]) -> List[str]:
    result = []
    for line in lines:
        cleaned = canonicalize_text(re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", line))
        if cleaned:
            result.append(cleaned)
    return _dedupe_strings(result)


def _parse_job_section(job_id: int, lines: Sequence[str]) -> Tuple[Optional[CandidateJob], CandidateJobEvidenceItem]:
    fields = {"company": "", "company_type": "", "position": "", "period": ""}
    highlights: List[str] = []
    in_highlights = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        key_match = re.match(r"^(company|company_type|position|period|highlights)\s*:\s*(.*)$", line, re.IGNORECASE)
        if key_match:
            key = key_match.group(1).lower()
            value = canonicalize_text(key_match.group(2))
            in_highlights = key == "highlights"
            if key in fields:
                fields[key] = value
            elif key == "highlights" and value:
                highlights.append(value)
            continue

        if in_highlights or re.match(r"^\s*[-•*]\s+", line):
            cleaned = canonicalize_text(re.sub(r"^\s*[-•*]\s*", "", line))
            if cleaned:
                highlights.append(cleaned)

    present_fields = sum(bool(fields[key]) for key in ["company", "position", "period"])
    job_evidence = CandidateJobEvidenceItem(
        job_id=job_id,
        company=[fields["company"]] if fields["company"] else [],
        position=[fields["position"]] if fields["position"] else [],
        period=[fields["period"]] if fields["period"] else [],
        highlights=_dedupe_strings(highlights[:2]),
    )
    if present_fields < 2:
        return None, job_evidence
    return (
        CandidateJob(
            id=job_id,
            company_name=fields["company"] or None,
            company_type=fields["company_type"] or None,
            position=fields["position"] or None,
            period=fields["period"] or None,
            responsibilities=_dedupe_strings(highlights[:2]),
            achievements=[],
            skills_used=[],
        ),
        job_evidence,
    )


def _parse_education_section(lines: Sequence[str]) -> List[EducationItem]:
    items = []
    for line in lines:
        cleaned = canonicalize_text(line)
        if not cleaned:
            continue
        parts = [canonicalize_text(part) for part in cleaned.split("|")]
        if len(parts) < 6:
            parts = (parts + [""] * 6)[:6]
        _, institution, degree, field, year, status = parts[:6]
        normalized_status = status if status in {"completed", "incomplete", "unknown"} else "unknown"
        if any([institution, degree, field, year]):
            items.append(
                EducationItem(
                    institution=institution or None,
                    degree=degree or None,
                    field=field or None,
                    year=year or None,
                    status=normalized_status,
                )
            )
    return items


def _parse_languages_section(lines: Sequence[str]) -> List[LanguageItem]:
    languages = []
    for line in lines:
        cleaned = canonicalize_text(line)
        if not cleaned:
            continue
        parts = [canonicalize_text(part) for part in cleaned.split("|")]
        name = parts[0] if parts else ""
        level = parts[1] if len(parts) > 1 else None
        if name:
            languages.append(LanguageItem(name=name, level=level or None))
    return languages


def build_evidence_package(
    resume_text: str,
    profile: CandidateProfile,
    preview: Optional[ResumeSectionPreview] = None,
) -> Tuple[CandidateEvidenceBlock, Dict[str, List[ProvenanceItem]]]:
    preview = preview or detect_resume_sections(resume_text)
    original_evidence = CandidateEvidenceBlock.model_validate(profile.evidence)
    evidence = CandidateEvidenceBlock()
    provenance: Dict[str, List[ProvenanceItem]] = {}

    def collect_global_from_block(
        label: str,
        source_snippets: Iterable[str],
        candidates: Iterable[str],
        block: Optional[ResumeSectionBlock | JobSourceBlock],
        *,
        allow_local_fallback: bool = True,
        max_snippets: int = 3,
    ) -> List[str]:
        snippets: List[str] = []
        line_range: Optional[List[int]] = None
        extraction_mode = "missing"
        validation_status = "failed"
        confidence_hint = "low"

        if not CANDIDATE_EVIDENCE_VALIDATION_ENABLED:
            snippets = _soft_clean_llm_evidence(source_snippets, max_snippets=max_snippets)
            if snippets:
                extraction_mode = "llm_unvalidated"
                validation_status = "not_validated"
                confidence_hint = "medium"
        elif block:
            snippets, line_range, validation_status = _validate_llm_evidence_in_block(
                block,
                source_snippets,
                max_snippets=max_snippets,
            )
            if snippets:
                extraction_mode = "llm_validated"
                confidence_hint = "high" if validation_status == "exact" else "medium"

        if block and not snippets and allow_local_fallback:
            snippets, line_range = _extract_snippets_from_block(block, candidates, max_snippets=max_snippets)
            if snippets:
                extraction_mode = "fallback"
                validation_status = "block_match"
                confidence_hint = "medium"

        provenance[label] = [
            ProvenanceItem(
                source_block_id=block.block_id if block else None,
                source_snippets=snippets,
                source_line_range=line_range if line_range else None,
                extraction_mode=extraction_mode if snippets else "missing",
                validation_status=validation_status if snippets else "failed",
                confidence_hint=confidence_hint if snippets else "low",
            )
        ]
        return snippets

    target_block = preview.section_blocks.get("desired_role") or preview.section_blocks.get("header")
    evidence.target_role = collect_global_from_block(
        "target_role",
        original_evidence.target_role,
        [profile.target_role or ""],
        target_block,
    )

    full_block = _full_resume_block(preview)
    experience_line_range = None
    if CANDIDATE_EVIDENCE_VALIDATION_ENABLED:
        experience_snippets, experience_line_range, experience_status = _validate_llm_evidence_in_block(
            full_block,
            original_evidence.total_experience,
        )
        experience_mode = "llm_validated"
        experience_confidence = "high" if experience_status == "exact" else "medium"
    else:
        experience_snippets = _soft_clean_llm_evidence(original_evidence.total_experience)
        experience_status = "not_validated" if experience_snippets else "failed"
        experience_mode = "llm_unvalidated" if experience_snippets else "missing"
        experience_confidence = "medium" if experience_snippets else "low"
    if not experience_snippets:
        experience_snippets = _extract_explicit_experience_snippets(preview.normalized_text)
        experience_line_range = _line_range_for_snippets(full_block, experience_snippets)
        experience_status = "exact" if experience_snippets else "failed"
        experience_mode = "fallback" if experience_snippets else "missing"
        experience_confidence = "medium" if experience_snippets else "low"
    if experience_snippets:
        evidence.total_experience = experience_snippets
        provenance["total_experience"] = [
            ProvenanceItem(
                source_block_id=full_block.block_id,
                source_snippets=experience_snippets,
                source_line_range=experience_line_range,
                extraction_mode=experience_mode,
                validation_status=experience_status,
                confidence_hint=experience_confidence,
            )
        ]
        if profile.experience_months is not None:
            provenance["experience_months"] = [
                ProvenanceItem(
                    source_block_id=full_block.block_id,
                    source_snippets=experience_snippets,
                    source_line_range=experience_line_range,
                    extraction_mode="normalized",
                    validation_status=experience_status,
                    confidence_hint=experience_confidence,
                )
            ]
    elif profile.experience_years:
        evidence.total_experience = collect_global_from_block(
            "total_experience",
            [],
            [f"{profile.experience_years} years", f"{profile.experience_years} лет"],
            full_block,
        )

    skills_block = preview.section_blocks.get("skills") or preview.section_blocks.get("work_experience")
    skills_evidence_source = original_evidence.skills_section
    if not CANDIDATE_EVIDENCE_VALIDATION_ENABLED and profile.skills_hard:
        skills_evidence_source = ["; ".join(profile.skills_hard)]
    evidence.skills_section = collect_global_from_block(
        "skills_section",
        skills_evidence_source,
        profile.skills_hard[:10],
        skills_block,
    )

    job_block_map = _match_jobs_to_blocks(profile.jobs, preview.job_blocks)
    for job in profile.jobs:
        block = job_block_map.get(job.id)
        original_job_evidence = original_evidence.get_job(job.id)
        job_evidence = CandidateJobEvidenceItem(
            job_id=job.id,
            company=collect_global_from_block(
                f"job_{job.id}_company",
                original_job_evidence.company if original_job_evidence else [],
                [job.company_name or ""],
                block,
            ),
            position=collect_global_from_block(
                f"job_{job.id}_position",
                original_job_evidence.position if original_job_evidence else [],
                [job.position or ""],
                block,
            ),
            period=collect_global_from_block(
                f"job_{job.id}_period",
                original_job_evidence.period if original_job_evidence else [],
                [job.period or "", job.start_date or "", job.end_date or ""],
                block,
            ),
            highlights=collect_global_from_block(
                f"job_{job.id}_highlights",
                original_job_evidence.highlights if original_job_evidence else [],
                [*job.achievements[:2], *job.responsibilities[:3], *job.skills_used[:3]],
                block,
                max_snippets=2,
            ),
        )
        evidence.jobs.append(job_evidence)

    education_candidates = []
    for item in profile.education:
        education_candidates.extend(filter(None, [item.institution, item.degree, item.field, item.year]))
    evidence.education = collect_global_from_block(
        "education",
        original_evidence.education,
        education_candidates[:8],
        preview.section_blocks.get("education"),
    )

    language_candidates = []
    for item in profile.canonical_profile.languages:
        for alias in _language_display_aliases(item.name):
            if item.level:
                language_candidates.extend([f"{alias} — {item.level}", f"{alias} ({item.level})", f"{alias} {item.level}"])
            language_candidates.append(alias)
    evidence.languages = collect_global_from_block(
        "languages",
        original_evidence.languages,
        language_candidates,
        preview.section_blocks.get("languages"),
    )

    return evidence, provenance


def _extract_raw_snippets(text: str, candidates: Iterable[str], max_snippets: int = 2) -> List[str]:
    if not text:
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    snippets: List[str] = []
    for candidate in candidates:
        cleaned = canonicalize_text(candidate)
        if not cleaned:
            continue
        pattern = re.compile(rf"([^\n]{{0,120}}{re.escape(cleaned)}[^\n]{{0,120}})", flags=re.IGNORECASE)
        exact_found = False
        for match in pattern.finditer(text):
            snippets.append(match.group(1).strip())
            exact_found = True
            if len(_dedupe_snippets(snippets)) >= max_snippets:
                return _dedupe_snippets(snippets)[:max_snippets]
        if exact_found:
            continue

        candidate_key = normalize_phrase_key(cleaned)
        candidate_words = {word for word in re.findall(r"[A-Za-zА-Яа-я0-9+#./-]+", cleaned.lower()) if len(word) > 2}
        for line in lines:
            line_clean = canonicalize_text(line)
            line_key = normalize_phrase_key(line_clean)
            if not line_key:
                continue
            if candidate_key and candidate_key in line_key:
                snippets.append(line_clean)
            elif candidate_words and len(candidate_words) >= 2 and len(cleaned) > 10 and not re.match(r"^\d{4}-\d{2}$", cleaned):
                line_words = set(re.findall(r"[A-Za-zА-Яа-я0-9+#./-]+", line_clean.lower()))
                if candidate_words.issubset(line_words) or len(candidate_words & line_words) >= min(2, len(candidate_words)):
                    snippets.append(line_clean)
            if len(_dedupe_snippets(snippets)) >= max_snippets:
                return _dedupe_snippets(snippets)[:max_snippets]
    return _dedupe_snippets(snippets)[:max_snippets]


def _extract_snippets_from_block(
    block: ResumeSectionBlock | JobSourceBlock,
    candidates: Iterable[str],
    max_snippets: int = 2,
) -> Tuple[List[str], Optional[List[int]]]:
    snippets: List[str] = []
    line_ranges: List[List[int]] = []
    block_text = _block_text(block)
    block_lines = block_text.splitlines()

    for candidate in candidates:
        cleaned = canonicalize_text(candidate)
        if not cleaned:
            continue

        exact_pattern = re.compile(re.escape(cleaned), flags=re.IGNORECASE)
        for offset, raw_line in enumerate(block_lines):
            line = canonicalize_text(raw_line)
            if not line:
                continue
            if exact_pattern.search(line):
                snippets.append(line)
                absolute_line = block.start_line + offset
                line_ranges.append([absolute_line, absolute_line])
                if len(_dedupe_snippets(snippets)) >= max_snippets:
                    return _dedupe_snippets(snippets)[:max_snippets], _merge_line_ranges(line_ranges)

        candidate_key = normalize_phrase_key(cleaned)
        candidate_words = {word for word in re.findall(r"[A-Za-zА-Яа-я0-9+#./-]+", cleaned.lower()) if len(word) > 2}
        if not candidate_key or len(candidate_words) < 2:
            continue
        for offset, raw_line in enumerate(block_lines):
            line = canonicalize_text(raw_line)
            line_words = set(re.findall(r"[A-Za-zА-Яа-я0-9+#./-]+", line.lower()))
            if candidate_key in normalize_phrase_key(line) or candidate_words.issubset(line_words):
                snippets.append(line)
                absolute_line = block.start_line + offset
                line_ranges.append([absolute_line, absolute_line])
                if len(_dedupe_snippets(snippets)) >= max_snippets:
                    return _dedupe_snippets(snippets)[:max_snippets], _merge_line_ranges(line_ranges)

    return _dedupe_snippets(snippets)[:max_snippets], _merge_line_ranges(line_ranges)


def _validate_llm_evidence_in_block(
    block: ResumeSectionBlock | JobSourceBlock,
    llm_snippets: Iterable[str],
    max_snippets: int = 3,
) -> Tuple[List[str], Optional[List[int]], str]:
    block_lines = _block_text(block).splitlines()
    accepted: List[str] = []
    line_ranges: List[List[int]] = []
    best_status = "failed"
    status_rank = {"failed": 0, "block_match": 1, "normalized_match": 2, "exact": 3}

    for snippet in llm_snippets or []:
        cleaned = canonicalize_text(snippet)
        if not cleaned:
            continue
        matched_line, line_number, status = _match_snippet_to_block_line(cleaned, block_lines, block.start_line)
        if not matched_line:
            continue

        accepted.append(_trim_validated_snippet(cleaned, matched_line))
        line_ranges.append([line_number, line_number])
        if status_rank[status] > status_rank[best_status]:
            best_status = status
        if len(_dedupe_snippets(accepted)) >= max_snippets:
            break

    return _dedupe_snippets(accepted)[:max_snippets], _merge_line_ranges(line_ranges), best_status


def _soft_clean_llm_evidence(llm_snippets: Iterable[str], max_snippets: int = 3) -> List[str]:
    cleaned_items: List[str] = []
    for snippet in llm_snippets or []:
        cleaned = canonicalize_text(str(snippet))
        if not cleaned:
            continue
        cleaned = cleaned.replace("–", "—")
        cleaned = re.sub(r"^\s*(?:[-•*]|\d+[.)])\s+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" `\"'")
        if cleaned:
            cleaned_items.append(cleaned)
        if len(_dedupe_snippets(cleaned_items)) >= max_snippets:
            break
    return _dedupe_snippets(cleaned_items)[:max_snippets]


def _match_snippet_to_block_line(
    snippet: str,
    block_lines: Sequence[str],
    start_line: int,
) -> Tuple[Optional[str], Optional[int], str]:
    snippet_norm = _soft_match_key(snippet)
    snippet_words = _meaningful_words(snippet)

    for offset, raw_line in enumerate(block_lines):
        line = canonicalize_text(raw_line)
        if not line:
            continue
        line_number = start_line + offset
        if snippet.lower() in line.lower():
            return line, line_number, "exact"
        if snippet_norm and snippet_norm in _soft_match_key(line):
            return line, line_number, "normalized_match"

    if len(snippet_words) >= 2:
        for offset, raw_line in enumerate(block_lines):
            line = canonicalize_text(raw_line)
            line_words = _meaningful_words(line)
            overlap = snippet_words & line_words
            if len(overlap) >= min(len(snippet_words), 3):
                return line, start_line + offset, "block_match"

    return None, None, "failed"


def _soft_match_key(value: str) -> str:
    cleaned = canonicalize_text(value).lower().replace("ё", "е")
    cleaned = cleaned.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")


def _meaningful_words(value: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[A-Za-zА-Яа-я0-9+#./-]+", value.lower())
        if len(word) > 2
    }


def _trim_validated_snippet(llm_snippet: str, matched_line: str, max_chars: int = 220) -> str:
    cleaned = canonicalize_text(llm_snippet)
    matched = canonicalize_text(matched_line)
    if cleaned and len(cleaned) <= max_chars and _soft_match_key(cleaned) in _soft_match_key(matched):
        return cleaned
    if len(matched) <= max_chars:
        return matched
    return matched[:max_chars].rstrip(" ,.;:-") + "..."


def _filter_existing_evidence_for_block(
    snippets: Iterable[str],
    block: Optional[ResumeSectionBlock | JobSourceBlock],
) -> List[str]:
    if not block:
        return []
    block_key = normalize_phrase_key(_block_text(block))
    valid = []
    for snippet in snippets:
        cleaned = canonicalize_text(snippet)
        if cleaned and normalize_phrase_key(cleaned) in block_key:
            valid.append(cleaned)
    return _dedupe_snippets(valid)


def _block_text(block: ResumeSectionBlock | JobSourceBlock) -> str:
    return block.raw_block_text if isinstance(block, JobSourceBlock) else block.raw_text


def _merge_line_ranges(ranges: Sequence[List[int]]) -> Optional[List[int]]:
    if not ranges:
        return None
    return [min(item[0] for item in ranges), max(item[1] for item in ranges)]


def _line_range_for_snippets(
    block: ResumeSectionBlock | JobSourceBlock,
    snippets: Sequence[str],
) -> Optional[List[int]]:
    _, line_range = _extract_snippets_from_block(block, snippets, max_snippets=max(1, len(snippets)))
    return line_range


def _full_resume_block(preview: ResumeSectionPreview) -> ResumeSectionBlock:
    lines = preview.normalized_text.splitlines()
    return ResumeSectionBlock(
        block_id="section:full_resume",
        section_name="full_resume",
        raw_text=preview.normalized_text,
        start_line=1,
        end_line=len(lines) if lines else 1,
        normalized_block_text=preview.normalized_text,
    )


def _match_jobs_to_blocks(
    jobs: Sequence[CandidateJob],
    blocks: Sequence[JobSourceBlock],
) -> Dict[int, JobSourceBlock]:
    result: Dict[int, JobSourceBlock] = {}
    used_blocks = set()

    for job_index, job in enumerate(jobs):
        best_block = None
        best_score = 0
        for block_index, block in enumerate(blocks):
            if block.block_id in used_blocks:
                continue
            score = _job_block_match_score(job, block)
            if score > best_score:
                best_score = score
                best_block = block

        if best_block is None and job_index < len(blocks) and blocks[job_index].block_id not in used_blocks:
            best_block = blocks[job_index]
            best_score = 1

        if best_block is not None and best_score > 0:
            result[job.id] = best_block
            used_blocks.add(best_block.block_id)

    return result


def _job_block_match_score(job: CandidateJob, block: JobSourceBlock) -> int:
    block_key = normalize_phrase_key(block.raw_block_text)
    score = 0
    for value, weight in [
        (job.company_name, 4),
        (job.position, 3),
        (job.period, 3),
        (job.start_date, 1),
        (job.end_date, 1),
    ]:
        key = normalize_phrase_key(value or "")
        if key and key in block_key:
            score += weight

    for line in [*job.responsibilities[:2], *job.achievements[:2]]:
        key = normalize_phrase_key(line)
        if key and key in block_key:
            score += 1

    return score


def _extract_explicit_experience_snippets(text: str) -> List[str]:
    snippets: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            continue
        if any(re.search(pattern, lowered) for pattern in EXPERIENCE_EXPLICIT_PATTERNS):
            snippets.append(stripped)
        elif re.search(r"(опыт работы|experience)[^.\n]*\d", lowered):
            snippets.append(stripped)
    return _dedupe_snippets(snippets)[:2]


def enrich_candidate_profile_with_sections(profile: CandidateProfile, preview: ResumeSectionPreview) -> CandidateProfile:
    if profile.target_role and not preview.section_texts.get("desired_role"):
        profile.ambiguities.append("Target role inferred from resume header")

    if profile.skills_hard and not preview.section_texts.get("skills"):
        profile.ambiguities.append("Hard skills partly extracted from work-experience context")

    if profile.education and not preview.section_texts.get("education"):
        profile.ambiguities.append("Education inferred from noisy or unlabeled resume section")

    if profile.canonical_profile.languages and not preview.section_texts.get("languages"):
        profile.ambiguities.append("Languages inferred outside a dedicated language section")

    profile.ambiguities = _dedupe_strings(profile.ambiguities)
    return profile


def _dedupe_snippets(snippets: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for snippet in snippets:
        cleaned = canonicalize_text(snippet)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        result.append(cleaned)
        seen.add(lowered)
    return result


def normalize_candidate_profile(
    profile: CandidateProfile,
    resume_text: str,
    preview: Optional[ResumeSectionPreview] = None,
) -> CandidateProfile:
    profile = CandidateProfile.model_validate(profile.model_dump())
    preview = preview or detect_resume_sections(resume_text)
    profile.raw_warnings = _dedupe_strings(profile.raw_warnings)
    profile.ambiguities = _dedupe_strings(profile.ambiguities)

    _normalize_target_role(profile)
    _normalize_jobs(profile, resume_text)
    _normalize_education(profile)
    _normalize_languages(profile, resume_text)
    _normalize_skills(profile, resume_text)
    _normalize_certifications(profile)
    _sanity_check_experience(profile, resume_text)

    profile.evidence, profile.provenance = build_evidence_package(resume_text, profile, preview)
    profile.confidence = derive_confidence(profile, resume_text, preview)
    profile.ambiguities = _dedupe_strings(profile.ambiguities)
    profile.raw_warnings = _dedupe_strings(profile.raw_warnings)
    return profile


def _normalize_target_role(profile: CandidateProfile) -> None:
    role = canonicalize_text(profile.target_role)
    if not role:
        profile.target_role = None
        return
    lowered = role.lower()
    if any(re.search(pattern, lowered) for pattern in ROLE_NOISE_PATTERNS):
        profile.raw_warnings.append("Target role looked like document boilerplate and was cleared")
        profile.target_role = None
        return
    profile.target_role = role


def _normalize_jobs(profile: CandidateProfile, resume_text: str) -> None:
    normalized_jobs: List[CandidateJob] = []
    headline_norm = normalize_phrase_key(profile.target_role or "")
    summary_norm = normalize_phrase_key(profile.summary_raw or "")

    for job in profile.jobs:
        job.company_name = _optional_clean(job.company_name)
        job.company_type = _normalize_company_type(job.company_type)
        job.position = _optional_clean(job.position)
        job.period = _optional_clean(job.period)
        job.responsibilities = _dedupe_strings(job.responsibilities)
        job.achievements = _dedupe_strings(job.achievements)
        job.skills_used = _dedupe_strings(job.skills_used)

        present_fields = sum(bool(value) for value in [job.company_name, job.position, job.period])
        if present_fields < 2:
            profile.raw_warnings.append(f"Dropped weak job entry #{job.id}: not enough evidence for a real work block")
            continue

        if job.position and headline_norm and normalize_phrase_key(job.position) == headline_norm and not job.company_name:
            profile.raw_warnings.append(f"Dropped headline-like job entry #{job.id}")
            continue

        if job.position and summary_norm and normalize_phrase_key(job.position) == summary_norm:
            profile.raw_warnings.append(f"Dropped summary-like job entry #{job.id}")
            continue

        start_date, end_date, is_current = normalize_period_dates(job.period, job.start_date, job.end_date, job.is_current)
        job.start_date = start_date
        job.end_date = end_date
        job.is_current = is_current
        job.company_type = job.company_type or _infer_company_type(job, resume_text)
        _split_job_achievements(job)

        normalized_jobs.append(job)

    for index, job in enumerate(normalized_jobs, start=1):
        job.id = index

    profile.jobs = normalized_jobs


def normalize_period_dates(
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    is_current: bool,
) -> Tuple[Optional[str], Optional[str], bool]:
    start = _normalize_date_string(start_date)
    end = _normalize_date_string(end_date)

    current = bool(is_current)
    if period:
        lowered = period.lower()
        current = current or "настоящее время" in lowered or "present" in lowered or "current" in lowered
        parsed_start, parsed_end = _extract_dates_from_period(period)
        start = start or parsed_start
        end = end or parsed_end
        if current:
            end = None

    return start, end, current


def _extract_dates_from_period(period: str) -> Tuple[Optional[str], Optional[str]]:
    period = period.replace("—", "-")
    matches = re.findall(r"([A-Za-zА-Яа-я]+)?\s*(\d{4})", period)
    parsed = []
    for month_text, year_text in matches[:2]:
        month_value = 1
        if month_text:
            month_value = MONTH_ALIASES.get(month_text.strip().lower(), 1)
        parsed.append(f"{int(year_text):04d}-{month_value:02d}")

    if not parsed:
        years = re.findall(r"\b(19\d{2}|20\d{2})\b", period)
        if years:
            parsed = [f"{int(year):04d}-01" for year in years[:2]]

    if len(parsed) == 1:
        return parsed[0], None
    if len(parsed) >= 2:
        return parsed[0], parsed[1]
    return None, None


def _normalize_date_string(value: Optional[str]) -> Optional[str]:
    cleaned = _optional_clean(value)
    if not cleaned:
        return None
    if re.match(r"^\d{4}-\d{2}$", cleaned):
        return cleaned
    parsed_start, _ = _extract_dates_from_period(cleaned)
    return parsed_start


def _infer_company_type(job: CandidateJob, resume_text: str) -> Optional[str]:
    search_candidates = [job.company_name or "", job.position or ""]
    snippets = _extract_raw_snippets(resume_text, search_candidates, max_snippets=4)
    combined = " ".join(snippets).lower()
    if not combined:
        return None

    for label, patterns in DOMAIN_CONTEXT_PATTERNS.items():
        if any(re.search(pattern, combined) for pattern in patterns):
            return label
    return None


def _normalize_company_type(value: Optional[str]) -> Optional[str]:
    cleaned = _optional_clean(value)
    if not cleaned:
        return None

    key = normalize_phrase_key(cleaned)
    if key in COMPANY_TYPE_ALIASES:
        return COMPANY_TYPE_ALIASES[key]

    lowered = cleaned.lower()
    for label, patterns in DOMAIN_CONTEXT_PATTERNS.items():
        if label == lowered:
            return label
        if any(re.search(pattern, lowered) for pattern in patterns):
            return label
    return cleaned


def _split_job_achievements(job: CandidateJob) -> None:
    moved: List[str] = []
    kept: List[str] = []

    for line in job.responsibilities:
        if _looks_like_achievement(line):
            moved.append(line)
        else:
            kept.append(line)

    explicit_achievements = [item for item in job.achievements if item]
    job.achievements = _dedupe_strings([*explicit_achievements, *moved])
    if job.achievements:
        achievement_keys = {normalize_phrase_key(item) for item in job.achievements}
        kept = [item for item in kept if normalize_phrase_key(item) not in achievement_keys]
    job.responsibilities = _dedupe_strings(kept)


def _looks_like_achievement(text: str) -> bool:
    lowered = canonicalize_text(text).lower()
    if not lowered:
        return False
    has_quantified_impact = bool(re.search(r"\b\d+(?:[.,]\d+)?\s*%|\b\d+(?:[.,]\d+)?\b", lowered))
    has_result_phrase = bool(re.search(r"resulted in|led to|enabled|allowing|что позволило|что помогло|в результате", lowered))
    has_impact_verb = bool(re.search(r"\b(?:increase|decrease|reduce|improve|grow|boost|cut|save|deliver|achiev|optimi[sz]e|увелич|сократ|сниз|ускор|рост|повыс|достиг|позволил|позволила)\w*", lowered))
    if has_result_phrase or (has_quantified_impact and has_impact_verb):
        return True
    return False


def _build_job_skills_used(job: CandidateJob, explicit_skills: Sequence[str], resume_text: str) -> List[str]:
    source_text = "\n".join([*(job.responsibilities or []), *(job.achievements or [])])
    explicit_matches = []
    normalized_source = normalize_phrase_key(source_text)
    for skill in explicit_skills:
        key = normalize_phrase_key(skill)
        if key and key in normalized_source:
            explicit_matches.append(skill)

    inferred: List[str] = []
    if not explicit_matches:
        inferred = _extract_tool_like_phrases(source_text)
    if not explicit_matches and not inferred:
        context_snippets = _extract_raw_snippets(resume_text, [job.company_name or "", job.position or ""], max_snippets=3)
        inferred = _extract_tool_like_phrases(" ".join(context_snippets))

    return _dedupe_normalized_labels([*job.skills_used, *explicit_matches, *inferred])


def _extract_tool_like_phrases(text: str) -> List[str]:
    if not text:
        return []

    phrases: List[str] = []
    patterns = [
        r"\b[A-Z][A-Za-z0-9+#./-]{1,}(?:\s+[A-Z][A-Za-z0-9+#./-]{1,}){0,2}\b",
        r"\b[A-Z]{2,}(?:/[A-Z]{2,})?\b",
        r"\b[A-Za-z][A-Za-z0-9_+#./-]*[+#/\d-][A-Za-z0-9_+#./-]*\b",
        r"(?:using|with|via|through|через|с использованием)\s+([A-Za-z][A-Za-z0-9+#./-]*(?:\s+[A-Za-z][A-Za-z0-9+#./-]*){0,2})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            candidate = canonicalize_text(match.group(1) if match.lastindex else match.group(0))
            if not candidate or candidate.lower() in JOB_HEADER_NOISE:
                continue
            if len(candidate) < 2:
                continue
            if candidate.lower() in {"and", "with", "using", "data", "analysis", "python for", "sql for"}:
                continue
            phrases.append(candidate)
    return _dedupe_normalized_labels(phrases[:20])


def _normalize_skills(profile: CandidateProfile, resume_text: str) -> None:
    language_keys = {
        alias
        for language in profile.canonical_profile.languages
        for alias in _language_aliases(language.name)
    }

    cleaned_hard: List[str] = []
    moved_to_soft: List[str] = []
    seen_hard_keys = set()

    for skill in profile.skills_hard:
        cleaned = canonicalize_text(skill)
        if not cleaned:
            continue
        if _is_language_like_skill(cleaned, language_keys):
            continue
        if _is_presentation_soft_skill(cleaned):
            moved_to_soft.append(cleaned)
            continue

        key = _skill_dedupe_key(cleaned)
        if not key or key in seen_hard_keys:
            continue
        seen_hard_keys.add(key)
        cleaned_hard.append(cleaned)

    profile.skills_hard = cleaned_hard

    cleaned_soft = []
    hard_keys = {normalize_phrase_key(skill) for skill in profile.skills_hard}
    for skill in [*profile.skills_soft, *moved_to_soft]:
        cleaned = canonicalize_text(skill)
        if not cleaned:
            continue
        if len(cleaned.split()) > 4:
            continue
        key = normalize_phrase_key(cleaned)
        if not key or key in SOFT_SKILL_NOISE or key in hard_keys:
            continue
        cleaned_soft.append(cleaned)
    profile.skills_soft = _dedupe_normalized_labels(cleaned_soft)

    explicit_skills = list(profile.skills_hard)
    for job in profile.jobs:
        job.skills_used = _build_job_skills_used(job, explicit_skills, resume_text)


def _is_language_like_skill(skill: str, language_keys: set[str]) -> bool:
    key = normalize_phrase_key(skill)
    if not key:
        return False

    all_language_keys = set(language_keys)
    for source, normalized in LANGUAGE_NAME_MAP.items():
        all_language_keys.add(normalize_phrase_key(source))
        all_language_keys.add(normalize_phrase_key(normalized))

    language_suffixes = ("язык", "language")
    if key in all_language_keys:
        return True
    if any(key == f"{language_key}{suffix}" for language_key in all_language_keys for suffix in language_suffixes):
        return True
    if any(language_key and language_key in key for language_key in all_language_keys):
        return bool(re.search(r"\b(язык|language|native|родн|intermediate|advanced|basic|[ABC][12])\b", skill, re.IGNORECASE))
    return False


def _is_presentation_soft_skill(skill: str) -> bool:
    lowered = skill.lower()
    if any(re.search(pattern, lowered) for pattern in PRESENTATION_SOFT_SKILL_PATTERNS):
        return True
    return False


def _skill_dedupe_key(skill: str) -> str:
    lowered = canonicalize_text(skill).lower().replace("ё", "е")
    for pattern in HARD_SKILL_PREFIX_NOISE:
        lowered = re.sub(pattern, "", lowered)
    lowered = lowered.replace("a/b", "ab")
    lowered = re.sub(r"\bab[-\s]?тест(?:ы|ирование)?\b", "abtest", lowered)
    lowered = re.sub(r"\ba\s*/\s*b[-\s]?test(?:ing|s)?\b", "abtest", lowered)
    lowered = re.sub(r"\bpower\s*bi\b", "powerbi", lowered)
    lowered = re.sub(r"\bms\s*excel\b", "excel", lowered)
    lowered = re.sub(r"\bms\s*sql\b", "mssql", lowered)
    lowered = re.sub(r"\batlassian\s+", "", lowered)
    return re.sub(r"[^a-zа-я0-9+#]+", "", lowered)


def _normalize_education(profile: CandidateProfile) -> None:
    cleaned_items = []
    for item in profile.education:
        item.institution = _optional_clean(item.institution)
        item.degree = _optional_clean(item.degree)
        item.field = _optional_clean(item.field)
        item.year = _optional_clean(item.year)
        item.status = _normalize_education_status(item)

        if _looks_like_work_noise_in_education(item):
            profile.raw_warnings.append("Dropped noisy education item that looked like work experience")
            continue
        if not any([item.institution, item.degree, item.field, item.year]):
            continue
        cleaned_items.append(item)
    profile.education = cleaned_items


def _normalize_education_status(item: EducationItem) -> str:
    combined = " ".join(filter(None, [item.degree, item.field])).lower()
    if "неокон" in combined or "incomplete" in combined or "ongoing" in combined:
        return "incomplete"
    if "бакалав" in combined or "магистр" in combined or "master" in combined or "bachelor" in combined:
        return "completed"
    return item.status or "unknown"


def _looks_like_work_noise_in_education(item: EducationItem) -> bool:
    combined = " ".join(filter(None, [item.institution, item.degree, item.field])).lower()
    if not combined:
        return False
    if re.search(r"\b(январ|феврал|март|апрел|май|июн|июл|август|сентябр|октябр|ноябр|декабр)\b", combined):
        return True
    if re.search(r"\b(настоящее время|present|current)\b", combined):
        return True
    if re.search(r"\b(аналитик|менеджер|engineer|developer|scientist)\b", combined):
        return True
    if "•" in combined or combined.startswith("-"):
        return True
    return False


def _normalize_languages(profile: CandidateProfile, resume_text: str) -> None:
    language_items: List[LanguageItem] = []
    raw_language_lines = _extract_language_lines(resume_text)
    seen = set()
    for item in profile.canonical_profile.languages:
        split_name, inline_level = _split_language_name_and_level(item.name)
        name = _normalize_language_name(split_name)
        if not name:
            continue
        level = _normalize_language_level(item.level) or inline_level
        if not level:
            level = _find_language_level_in_lines(name, raw_language_lines)
        key = normalize_phrase_key(name)
        if key in seen:
            continue
        language_items.append(LanguageItem(name=name, level=level))
        seen.add(key)

    if not language_items:
        for line in raw_language_lines:
            detected_name = _detect_language_name_in_text(line)
            if not detected_name:
                continue
            key = normalize_phrase_key(detected_name)
            if key in seen:
                continue
            language_items.append(LanguageItem(name=detected_name, level=_normalize_language_level(line)))
            seen.add(key)
    profile.canonical_profile.languages = language_items


def _normalize_language_name(value: Optional[str]) -> Optional[str]:
    cleaned = canonicalize_text(value)
    if not cleaned:
        return None
    lowered = cleaned.lower()
    return LANGUAGE_NAME_MAP.get(lowered, cleaned.title())


def _detect_language_name_in_text(text: str) -> Optional[str]:
    lowered = canonicalize_text(text).lower()
    for source, normalized in LANGUAGE_NAME_MAP.items():
        if source in lowered:
            return normalized
    return None


def _split_language_name_and_level(value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    cleaned = canonicalize_text(value)
    if not cleaned:
        return None, None
    parts = re.split(r"\s+[—-]\s+|\(", cleaned, maxsplit=1)
    name = canonicalize_text(parts[0])
    inline_level = None
    if len(parts) > 1:
        inline_level = _normalize_language_level(parts[1].rstrip(") "))
    return name, inline_level


def _normalize_language_level(value: Optional[str]) -> Optional[str]:
    cleaned = canonicalize_text(value)
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if normalize_phrase_key(cleaned) in {normalize_phrase_key(name) for name in LANGUAGE_NAME_MAP}:
        return None
    for pattern, normalized in LANGUAGE_LEVEL_PATTERNS.items():
        if re.search(pattern, lowered):
            return normalized
    if re.fullmatch(r"[ABC][12]", cleaned.upper()):
        return cleaned.upper()
    return None


def _normalize_certifications(profile: CandidateProfile) -> None:
    profile.certifications = _dedupe_strings(profile.certifications)


def _sanity_check_experience(profile: CandidateProfile, resume_text: str) -> None:
    explicit_months, explicit_label = _extract_explicit_experience_months(resume_text, profile.evidence.get("experience_years", []))
    calculated_months = _calculate_experience_months_from_jobs(profile.jobs)
    llm_months = int(profile.experience_months) if profile.experience_months else None

    if explicit_months is not None:
        profile.experience_months = explicit_months
        profile.experience_years = explicit_months // 12
        if explicit_label:
            profile.ambiguities.append(f"Total experience preserved from explicit resume statement: {explicit_label}")
    elif llm_months is not None:
        profile.experience_months = llm_months
        profile.experience_years = llm_months // 12
    elif calculated_months is not None:
        profile.experience_months = calculated_months
        profile.experience_years = calculated_months // 12
        profile.ambiguities.append("Experience months inferred from work periods")

    if calculated_months is not None and profile.experience_months is not None:
        if abs(profile.experience_months - calculated_months) > 6:
            profile.raw_warnings.append("Experience months conflict with parsed job periods")
            profile.ambiguities.append(
                f"Parsed total experience may be {profile.experience_months} months, while job dates suggest about {calculated_months} months"
            )
    elif profile.experience_years is None:
        profile.raw_warnings.append("Could not determine total experience years with confidence")


def _extract_language_lines(resume_text: str) -> List[str]:
    return [line.strip() for line in resume_text.splitlines() if line.strip() and re.search(r"(язык|language|english|англий|русский|russian|немец|german|french|français|spanish|испан)", line, re.IGNORECASE)]


def _find_language_level_in_lines(language_name: str, lines: Sequence[str]) -> Optional[str]:
    aliases = _language_aliases(language_name)
    for line in lines:
        line_key = normalize_phrase_key(line)
        if aliases and not any(alias in line_key for alias in aliases):
            continue
        level = _normalize_language_level(line)
        if level:
            return level
    return None


def _language_aliases(language_name: str) -> List[str]:
    normalized = _normalize_language_name(language_name)
    if not normalized:
        return []
    aliases = {normalize_phrase_key(normalized)}
    for source, mapped in LANGUAGE_NAME_MAP.items():
        if mapped == normalized:
            aliases.add(normalize_phrase_key(source))
    return [alias for alias in aliases if alias]


def _language_display_aliases(language_name: str) -> List[str]:
    normalized = _normalize_language_name(language_name)
    if not normalized:
        return []
    aliases = [normalized]
    for source, mapped in LANGUAGE_NAME_MAP.items():
        if mapped == normalized and source.title() not in aliases:
            aliases.append(source.title())
    return aliases


def _extract_explicit_experience_months(resume_text: str, evidence_snippets: Sequence[str]) -> Tuple[Optional[int], Optional[str]]:
    candidates = [*evidence_snippets, *[line.strip() for line in resume_text.splitlines() if line.strip()]]
    for snippet in candidates:
        lowered = snippet.lower()
        for pattern in EXPERIENCE_EXPLICIT_PATTERNS:
            match = re.search(pattern, lowered)
            if not match:
                continue
            years = int(match.group(1))
            months = int(match.group(2)) if match.lastindex and match.group(2) else 0
            return years * 12 + months, canonicalize_text(snippet)
    return None, None


def _calculate_experience_months_from_jobs(jobs: Sequence[CandidateJob]) -> Optional[int]:
    total_months = 0
    counted = False
    now = datetime.utcnow()
    for job in jobs:
        if not job.start_date:
            continue
        counted = True
        start = _parse_yyyy_mm(job.start_date)
        end = _parse_yyyy_mm(job.end_date) if job.end_date else now
        if not start or not end:
            continue
        months = max(0, (end.year - start.year) * 12 + (end.month - start.month) + 1)
        total_months += months
    if not counted:
        return None
    return max(0, total_months)


def _parse_yyyy_mm(value: str) -> Optional[datetime]:
    if not value or not re.match(r"^\d{4}-\d{2}$", value):
        return None
    year, month = value.split("-")
    return datetime(int(year), int(month), 1)


def derive_confidence(
    profile: CandidateProfile,
    resume_text: str,
    preview: Optional[ResumeSectionPreview] = None,
) -> ConfidenceBlock:
    preview = preview or detect_resume_sections(resume_text)

    role_conf = _anchored_confidence(profile, ["target_role"]) if profile.target_role else "low"
    if role_conf == "high" and any("target role" in item.lower() or "role inferred" in item.lower() for item in profile.ambiguities):
        role_conf = "medium"

    jobs_conf = "low"
    if profile.jobs:
        job_levels = []
        for job in profile.jobs:
            required_labels = [
                f"job_{job.id}_company",
                f"job_{job.id}_position",
                f"job_{job.id}_period",
                f"job_{job.id}_highlights",
            ]
            required_conf = _anchored_confidence(profile, required_labels)
            job_levels.append(required_conf)

        jobs_conf = _combine_confidence(job_levels)
        structurally_complete_jobs = sum(
            1 for job in profile.jobs if job.company_name and job.position and job.period
        )
        jobs_have_periods = all(bool(job.period or job.start_date) for job in profile.jobs)
        if structurally_complete_jobs:
            if structurally_complete_jobs == len(profile.jobs) and jobs_have_periods:
                jobs_conf = "high" if jobs_conf == "high" else "medium"
            else:
                jobs_conf = "medium" if jobs_conf == "low" else jobs_conf
        if not preview.job_blocks:
            jobs_conf = "medium" if structurally_complete_jobs else ("medium" if jobs_conf == "high" else "low")
        weak_jobs = any(not job.skills_used for job in profile.jobs)
        achievement_signal_present = any(_looks_like_achievement(item) for job in profile.jobs for item in [*job.responsibilities, *job.achievements])
        achievements_missing = achievement_signal_present and any(not job.achievements for job in profile.jobs)
        if weak_jobs or achievements_missing:
            jobs_conf = "medium" if structurally_complete_jobs or jobs_conf == "high" else "low"

    skills_conf = "low"
    if profile.skills_hard:
        skills_conf = _anchored_confidence(profile, ["skills_section"])
        if profile.jobs and any(not job.skills_used for job in profile.jobs):
            skills_conf = "medium" if skills_conf == "high" else "low"
        if skills_conf == "low" and len(profile.skills_hard) >= 3:
            skills_conf = "medium"

    education_conf = "low"
    if profile.education:
        education_conf = _anchored_confidence(profile, ["education"])
        if any(item.status == "unknown" for item in profile.education):
            education_conf = "medium"

    languages_conf = "low"
    if profile.canonical_profile.languages:
        explicit_language_lines = _extract_language_lines(resume_text)
        if all(item.level for item in profile.canonical_profile.languages):
            languages_conf = "high"
        else:
            languages_conf = "medium"
        if explicit_language_lines and any(re.search(r"(?:—|-|\(|\bA1\b|\bA2\b|\bB1\b|\bB2\b|\bC1\b|\bC2\b|native|родн|intermediate|basic)", line, re.IGNORECASE) for line in explicit_language_lines):
            if any(not item.level for item in profile.canonical_profile.languages):
                languages_conf = "low"
        if not preview.section_blocks.get("languages"):
            languages_conf = "medium" if languages_conf == "high" else languages_conf
        anchoring_conf = _anchored_confidence(profile, ["languages"])
        if anchoring_conf == "low":
            languages_conf = "medium" if all(item.name and item.level for item in profile.canonical_profile.languages) else "low"
        elif anchoring_conf == "medium" and languages_conf == "high":
            languages_conf = "medium"

    experience_conf = "low"
    if profile.experience_months or profile.experience_years:
        explicit_months, _ = _extract_explicit_experience_months(resume_text, profile.evidence.get("experience_years", []))
        anchoring_conf = _anchored_confidence(profile, ["total_experience", "experience_months"])
        if explicit_months is not None and anchoring_conf != "low":
            experience_conf = "high"
        elif any("inferred from work periods" in item.lower() for item in profile.ambiguities):
            experience_conf = "medium"
        else:
            experience_conf = anchoring_conf if anchoring_conf != "low" else "medium"

    levels = [role_conf, jobs_conf, skills_conf, education_conf, languages_conf, experience_conf]
    score_map = {"low": 0, "medium": 1, "high": 2}
    avg_score = sum(score_map[level] for level in levels) / len(levels)
    usable_profile = bool(
        profile.target_role
        and profile.jobs
        and jobs_conf != "low"
        and (profile.experience_months is not None or profile.experience_years is not None)
        and (profile.skills_hard or profile.education or profile.canonical_profile.languages)
    )
    overall = "low"
    if jobs_conf == "low" or role_conf == "low":
        overall = "low"
    elif avg_score >= 1.6:
        overall = "high"
    elif avg_score >= 0.9:
        overall = "medium"
    if usable_profile and overall == "low":
        overall = "medium"

    return ConfidenceBlock(
        overall=overall,
        target_role=role_conf,
        experience_years=experience_conf,
        jobs=jobs_conf,
        skills=skills_conf,
        education=education_conf,
        languages=languages_conf,
    )


def _anchored_confidence(profile: CandidateProfile, labels: Sequence[str]) -> str:
    hints: List[str] = []
    for label in labels:
        for item in profile.provenance.get(label, []):
            if item.validation_status == "failed" or item.extraction_mode == "missing":
                hints.append("low")
                continue
            if item.extraction_mode == "llm_validated" and item.validation_status == "exact":
                hints.append("high")
            elif item.confidence_hint:
                hints.append(item.confidence_hint)
            else:
                hints.append("medium")

    if not hints:
        return "low"
    return _combine_confidence(hints)


def _combine_confidence(levels: Sequence[str]) -> str:
    if not levels:
        return "low"
    score_map = {"low": 0, "medium": 1, "high": 2}
    scores = [score_map.get(level, 0) for level in levels]
    if min(scores) == 0:
        return "low" if scores.count(0) >= max(1, len(scores) // 2) else "medium"
    avg = sum(scores) / len(scores)
    if avg >= 1.75:
        return "high"
    if avg >= 1:
        return "medium"
    return "low"


def build_follow_up_questions(profile: CandidateProfile) -> List[str]:
    questions: List[str] = []

    if not profile.target_role or profile.confidence.target_role == "low":
        questions.append("Уточните, пожалуйста, вашу целевую роль.")
    elif profile.confidence.target_role == "medium":
        questions.append(f"Правильно ли я понял, что ваша целевая роль — {profile.target_role}?")

    if not profile.experience_years or profile.confidence.experience_years != "high":
        if profile.experience_years:
            questions.append(f"Подтвердите, пожалуйста, суммарный стаж: {_format_years_ru(profile.experience_years)}?")
        else:
            questions.append("Уточните, пожалуйста, ваш суммарный профессиональный стаж.")

    if profile.canonical_profile.languages:
        languages_without_level = [item.name for item in profile.canonical_profile.languages if not item.level]
        if languages_without_level:
            questions.append(f"Уточните уровень языка: {languages_without_level[0]}.")
    elif profile.confidence.languages == "low":
        questions.append("Какими языками вы владеете и на каком уровне?")

    if profile.confidence.education == "low" and profile.education:
        first_item = profile.education[0]
        target = first_item.institution or "вашего образования"
        questions.append(f"Уточните статус и направление обучения для {target}.")

    if not profile.jobs:
        questions.append("Добавьте, пожалуйста, хотя бы один подтверждённый блок опыта работы.")

    return questions[:3]


def _format_years_ru(years: int) -> str:
    value = abs(int(years))
    if 11 <= value % 100 <= 14:
        suffix = "лет"
    elif value % 10 == 1:
        suffix = "год"
    elif 2 <= value % 10 <= 4:
        suffix = "года"
    else:
        suffix = "лет"
    return f"{years} {suffix}"


def _dedupe_strings(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in items:
        cleaned = canonicalize_text(item)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        result.append(cleaned)
        seen.add(lowered)
    return result


def _dedupe_normalized_labels(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in items:
        cleaned = canonicalize_text(item)
        if not cleaned:
            continue
        key = normalize_phrase_key(cleaned)
        if not key or key in seen:
            continue
        result.append(cleaned)
        seen.add(key)
    return result


def _optional_clean(value: Optional[str]) -> Optional[str]:
    cleaned = canonicalize_text(value)
    return cleaned or None
