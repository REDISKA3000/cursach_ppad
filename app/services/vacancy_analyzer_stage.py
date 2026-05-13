"""Section-based parsing and cleanup for VacancyAnalyzer."""
from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Optional

from app.schemas.vacancy import VacancyProfile

logger = logging.getLogger(__name__)


SECTION_NAMES = {
    "ROLE",
    "SENIORITY",
    "INDUSTRY",
    "MUST_HAVE",
    "NICE_TO_HAVE",
    "RESPONSIBILITIES",
    "ATS_KEYWORDS",
    "WARNINGS",
}

SENIORITY_ALIASES = {
    "junior": "Junior",
    "jr": "Junior",
    "джуниор": "Junior",
    "джун": "Junior",
    "middle": "Middle",
    "mid": "Middle",
    "middle+": "Middle",
    "миддл": "Middle",
    "средний": "Middle",
    "senior": "Senior",
    "sr": "Senior",
    "старший": "Senior",
    "lead": "Lead",
    "лид": "Lead",
    "manager": "Manager",
    "head": "Manager",
    "director": "Manager",
    "руководитель": "Manager",
    "управляющий": "Manager",
}

INDUSTRY_PATTERNS = [
    ("Banking", [r"\bбанк\b", r"\bbank(?:ing)?\b", r"банков", r"финансов", r"кредит", r"лизинг"]),
    ("FinTech", [r"\bfintech\b", r"финтех"]),
    ("Payments", [r"платеж", r"payment"]),
    ("Retail / E-commerce", [r"ритейл", r"рознич", r"\bretail\b", r"\be-?commerce\b", r"marketplace", r"маркетплейс"]),
    ("Software / SaaS", [r"\bsaas\b", r"software", r"platform", r"платформ"]),
    ("Marketing", [r"маркетинг", r"marketing", r"agency", r"агентств"]),
    ("Telecom", [r"telecom", r"телеком", r"связ"]),
    ("Consulting", [r"consulting", r"консалт"]),
]

GENERIC_LOW_SIGNAL_REQUIREMENT_PATTERNS = [
    r"уверенн(?:ое|ый|ая)\s+пользовани[ея]\s+компьютер",
    r"уверенн(?:ое|ый|ая)\s+владени[ея]\s+компьютер",
    r"уверенн(?:ый|ая)\s+пользователь\s+пк",
    r"\bпк\b",
    r"грамотн(?:ая|ую)\s+реч",
    r"грамотн(?:ая|ое)\s+письм",
    r"коммуникабельн",
    r"стрессоустойчив",
    r"аккуратн",
    r"внимательн",
    r"ответственн",
    r"готовност[ьи]\s+работать\s+в\s+команд",
    r"работа\s+в\s+команд",
    r"проактивност",
    r"нацеленност[ьи]\s+на\s+результат",
    r"аналитический\s+склад\s+ума",
]

ROLE_CONTINUATION_PATTERNS = [
    r"^(?:младш(?:его|ий)|старш(?:его|ий)|ведущ(?:его|ий))?\s*риск-аналитик",
    r"^портфельн(?:ого|ый)\s+риск-менеджер",
    r"^product\s+analyst",
    r"^data\s+analyst",
    r"^business\s+analyst",
]

ATS_KEYWORD_REPLACEMENTS = [
    (r"банковские\s+мфо", ["банки", "МФО"]),
    (r"банках\s*/\s*мфо", ["банки", "МФО"]),
    (r"банках\s+мфо", ["банки", "МФО"]),
    (r"розничных\s+кредитных\s+рисках", ["розничные кредитные риски"]),
    (r"розничные\s+кредитные\s+риски", ["розничные кредитные риски"]),
]

BONUS_REQUIREMENT_PATTERNS = [
    r"\bbonus\b",
    r"\bplus\b",
    r"\bpreferred\b",
    r"\badvantage\b",
    r"будет\s+плюсом",
    r"будет\s+преимуществом",
    r"желательно",
    r"бонусом",
    r"как\s+преимуществ",
]

CORE_REQUIREMENT_PATTERNS = [
    r"\bsql\b",
    r"\bexcel\b",
    r"\bpython\b",
    r"\br\b",
    r"\bpower\s*bi\b",
    r"\btableau\b",
    r"\bgrafana\b",
    r"\bclick\s*house\b",
    r"\bclickhouse\b",
    r"\bjira\b",
    r"\bvisio\b",
    r"\bdwh\b",
    r"\betl\b",
    r"\bdata\s+vault\b",
    r"опыт\s+(?:от|не\s+менее|\d)",
    r"опыт\s+в\s+(?:банк|мфо|финансов|риск|роли|области)",
    r"высшее\s+(?:техническое|экономическое|финансовое|профильное)\s+образование",
    r"программирован",
    r"кредитн",
    r"риск",
    r"антифрод",
    r"платеж",
    r"субд",
    r"баз(?:ы|ами)?\s+данных",
]

ROLE_SKIP_MARKERS = [
    "₽",
    "$",
    "€",
    "опыт работы",
    "полная занятость",
    "частичная занятость",
    "график",
    "рабочие часы",
    "формат работы",
    "удал",
]


def parse_vacancy_section_text(response_text: str) -> VacancyProfile:
    """Parse the LLM section-based VacancyAnalyzer response into VacancyProfile."""
    sections = _parse_section_blocks(response_text or "")
    if not sections:
        return VacancyProfile(raw_warnings=["VacancyAnalyzer section parser found no recognized sections"])

    profile = VacancyProfile(
        role=_section_value(sections, "ROLE") or None,
        seniority=_section_value(sections, "SENIORITY") or None,
        industry=_section_value(sections, "INDUSTRY") or None,
        must_have_skills=_parse_bullet_section(sections.get("MUST_HAVE", [])),
        nice_to_have_skills=_parse_bullet_section(sections.get("NICE_TO_HAVE", [])),
        key_responsibilities=_parse_bullet_section(sections.get("RESPONSIBILITIES", [])),
        keywords_for_ats=_parse_semicolon_section(sections.get("ATS_KEYWORDS", [])),
        raw_warnings=_parse_bullet_section(sections.get("WARNINGS", [])),
    )

    missing = [name for name in SECTION_NAMES if name not in sections]
    if missing:
        profile.raw_warnings.append(f"VacancyAnalyzer response missing sections: {', '.join(sorted(missing))}")
    return profile


def normalize_vacancy_profile(profile: VacancyProfile, vacancy_text: str) -> VacancyProfile:
    """Apply lightweight deterministic cleanup without changing the public schema."""
    profile = VacancyProfile.model_validate(profile.model_dump())

    profile.role = normalize_role(profile.role, vacancy_text)
    profile.seniority = normalize_seniority(profile.seniority)
    profile.industry = normalize_industry(profile.industry, vacancy_text)
    profile.must_have_skills, profile.nice_to_have_skills = normalize_requirement_lists(
        profile.must_have_skills,
        profile.nice_to_have_skills,
    )
    profile.key_responsibilities = _dedupe_clean_items(profile.key_responsibilities)
    profile.raw_warnings = _dedupe_clean_items(profile.raw_warnings)

    must_keys = {_key(item) for item in profile.must_have_skills}
    profile.nice_to_have_skills = [
        item for item in profile.nice_to_have_skills if _key(item) not in must_keys
    ]

    profile.keywords_for_ats = normalize_ats_keywords(profile.keywords_for_ats)
    if not profile.keywords_for_ats:
        profile.keywords_for_ats = derive_ats_keywords(profile)

    if not profile.role:
        profile.raw_warnings.append("Could not determine job title from posting")
    if not profile.must_have_skills:
        profile.raw_warnings.append("No clear must-have requirements identified")
    if len((vacancy_text or "").strip()) < 100:
        profile.raw_warnings.append("Job posting is very short. More details would improve accuracy.")

    profile.raw_warnings = _dedupe_clean_items(profile.raw_warnings)
    return profile


def normalize_seniority(value: Optional[str]) -> Optional[str]:
    cleaned = _clean_scalar(value)
    if not cleaned:
        return None

    lowered = cleaned.lower().strip(" .;:+")
    if lowered in SENIORITY_ALIASES:
        return SENIORITY_ALIASES[lowered]
    for marker, normalized in SENIORITY_ALIASES.items():
        if re.search(rf"\b{re.escape(marker)}\b", lowered):
            return normalized
    return None


def normalize_role(value: Optional[str], vacancy_text: str) -> Optional[str]:
    role = _clean_scalar(value)
    header_role = _extract_role_from_header(vacancy_text)

    if not role:
        return header_role
    if header_role and _is_generic_role(role) and not _is_generic_role(header_role):
        return header_role
    if header_role and len(header_role) > len(role) + 4 and role.lower() in header_role.lower():
        return header_role
    return role


def normalize_requirement_lists(
    must_have: Iterable[str],
    nice_to_have: Iterable[str],
) -> tuple[List[str], List[str]]:
    must_items = merge_requirement_continuations(_dedupe_clean_items(must_have))
    nice_items = _dedupe_clean_items(nice_to_have)

    moved_to_nice: List[str] = []
    kept_must: List[str] = []
    has_strong_requirements = any(_is_core_requirement(item) for item in must_items)

    for item in must_items:
        if _is_bonus_requirement(item):
            moved_to_nice.extend(_extract_bonus_items(item))
            continue
        if has_strong_requirements and _is_generic_low_signal_requirement(item):
            continue
        kept_must.extend(_split_compound_requirement(item))

    normalized_nice: List[str] = []
    for item in [*nice_items, *moved_to_nice]:
        normalized_nice.extend(_split_compound_requirement(item, split_stack=True))

    kept_must = _dedupe_clean_items(kept_must)
    must_keys = {_key(item) for item in kept_must}
    normalized_nice = [
        item for item in _dedupe_clean_items(normalized_nice)
        if _key(item) not in must_keys
    ]
    return kept_must, normalized_nice


def merge_requirement_continuations(items: Iterable[str]) -> List[str]:
    merged: List[str] = []
    for item in items or []:
        cleaned = _clean_scalar(item)
        if not cleaned:
            continue
        if merged and _looks_like_requirement_continuation(merged[-1], cleaned):
            merged[-1] = f"{merged[-1]} / {cleaned}"
        else:
            merged.append(cleaned)
    return merged


def normalize_industry(value: Optional[str], vacancy_text: str = "") -> Optional[str]:
    source = " ".join(filter(None, [_clean_scalar(value), vacancy_text[:1000]])).lower()
    if not source:
        return None
    for label, patterns in INDUSTRY_PATTERNS:
        if any(re.search(pattern, source, re.IGNORECASE) for pattern in patterns):
            return label
    return _clean_scalar(value)


def derive_ats_keywords(profile: VacancyProfile, limit: int = 18) -> List[str]:
    keywords: List[str] = []
    for item in [
        profile.role,
        *(profile.must_have_skills or []),
        *(profile.nice_to_have_skills or []),
        *(profile.key_responsibilities or [])[:4],
    ]:
        for token in _split_keyword_item(item):
            keywords.append(token)
    return normalize_ats_keywords(keywords)[:limit]


def normalize_ats_keywords(items: Iterable[str]) -> List[str]:
    keywords: List[str] = []
    for item in items or []:
        cleaned = _clean_scalar(item)
        if not cleaned:
            continue
        lowered = cleaned.lower()

        replaced = False
        for pattern, replacements in ATS_KEYWORD_REPLACEMENTS:
            if re.search(pattern, lowered):
                keywords.extend(replacements)
                replaced = True
        if replaced:
            continue

        for part in _split_keyword_item(cleaned):
            part = _clean_scalar(part)
            if not part or _is_generic_low_signal_requirement(part):
                continue
            if len(part.split()) > 7:
                continue
            keywords.append(part)
    return _dedupe_clean_items(keywords)


def _parse_section_blocks(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None

    for raw_line in text.replace("\r", "\n").splitlines():
        line = raw_line.strip()
        match = re.fullmatch(r"\[([A-Z_]+)\]", line)
        if match and match.group(1) in SECTION_NAMES:
            current = match.group(1)
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(raw_line.rstrip())

    return sections


def _section_value(sections: Dict[str, List[str]], name: str) -> str:
    for line in sections.get(name, []):
        cleaned = _clean_scalar(line)
        if cleaned:
            return cleaned
    return ""


def _parse_bullet_section(lines: Iterable[str]) -> List[str]:
    items = []
    for line in lines or []:
        cleaned = _clean_scalar(re.sub(r"^\s*[-—–•*]\s*", "", line))
        if cleaned:
            items.append(cleaned)
    return _dedupe_clean_items(items)


def _parse_semicolon_section(lines: Iterable[str]) -> List[str]:
    text = "; ".join(_clean_scalar(line) for line in lines or [] if _clean_scalar(line))
    if not text:
        return []
    return _dedupe_clean_items(part for part in re.split(r";|\n", text) if part.strip())


def _split_keyword_item(value: Optional[str]) -> List[str]:
    if not value:
        return []
    cleaned = _clean_scalar(value)
    if not cleaned:
        return []
    if len(cleaned) <= 45 and not re.search(r";|/|\s+;\s+", cleaned):
        return [cleaned]
    parts = re.split(r",|/|;|\s+и\s+|\s+and\s+", cleaned)
    return [part.strip() for part in parts if 2 <= len(part.strip()) <= 45]


def _extract_role_from_header(vacancy_text: str) -> Optional[str]:
    for raw_line in (vacancy_text or "").splitlines()[:10]:
        line = _clean_scalar(raw_line.replace("Вакансия:", "").replace("VACANCY:", ""))
        if not line:
            continue
        lowered = line.lower()
        if any(marker in lowered for marker in ROLE_SKIP_MARKERS):
            continue
        if "сейчас эту вакансию смотрят" in lowered:
            continue
        return line
    return None


def _is_generic_role(role: str) -> bool:
    lowered = _clean_scalar(role).lower()
    return lowered in {
        "аналитик",
        "analyst",
        "менеджер",
        "manager",
        "специалист",
        "specialist",
    }


def _is_bonus_requirement(item: str) -> bool:
    lowered = item.lower()
    return any(re.search(pattern, lowered) for pattern in BONUS_REQUIREMENT_PATTERNS)


def _is_core_requirement(item: str) -> bool:
    lowered = item.lower()
    return any(re.search(pattern, lowered) for pattern in CORE_REQUIREMENT_PATTERNS)


def _is_generic_low_signal_requirement(item: str) -> bool:
    lowered = item.lower()
    return any(re.search(pattern, lowered) for pattern in GENERIC_LOW_SIGNAL_REQUIREMENT_PATTERNS)


def _extract_bonus_items(item: str) -> List[str]:
    cleaned = _clean_scalar(item)
    for pattern in BONUS_REQUIREMENT_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" :.-—–")
    return _split_compound_requirement(cleaned)


def _looks_like_requirement_continuation(previous: str, current: str) -> bool:
    prev = previous.lower()
    curr = current.lower().strip(" .;")
    if not re.search(r"опыт|роли|роль", prev):
        return False
    if _is_core_requirement(current) and not any(re.search(pattern, curr) for pattern in ROLE_CONTINUATION_PATTERNS):
        return False
    if any(re.search(pattern, curr) for pattern in ROLE_CONTINUATION_PATTERNS):
        return True
    if len(curr.split()) <= 5 and re.search(r"аналитик|менеджер|manager|analyst", curr):
        return True
    return False


def _split_compound_requirement(item: str, *, split_stack: bool = False) -> List[str]:
    cleaned = _clean_scalar(item)
    if not cleaned:
        return []

    if re.search(r"\bpython\s*/\s*r\b", cleaned, re.IGNORECASE):
        cleaned = re.sub(r"\bpython\s*/\s*r\b", "Python; R", cleaned, flags=re.IGNORECASE)
    if split_stack and _looks_like_stack_list(cleaned):
        parts = re.split(r",|;|/|\s+и\s+|\s+или\s+", cleaned)
        return [_clean_scalar(part) for part in parts if _clean_scalar(part)]

    if _is_core_requirement(cleaned) and len(cleaned) <= 120:
        return [cleaned]

    parts = re.split(r",|;|\s+или\s+", cleaned)
    short_parts = [_clean_scalar(part) for part in parts if 2 <= len(_clean_scalar(part)) <= 80]
    if len(short_parts) > 1 and any(_is_core_requirement(part) for part in short_parts):
        return short_parts
    return [cleaned]


def _looks_like_stack_list(value: str) -> bool:
    parts = [_clean_scalar(part) for part in re.split(r",|;|/|\s+и\s+|\s+или\s+", value) if _clean_scalar(part)]
    if len(parts) < 2 or len(parts) > 8:
        return False
    stack_like = 0
    for part in parts:
        if len(part.split()) <= 4 and (_is_core_requirement(part) or re.search(r"\b[A-ZА-Я][A-Za-zА-Яа-я0-9+#.]{0,12}\b", part)):
            stack_like += 1
    return stack_like >= max(2, len(parts) - 1)


def _dedupe_clean_items(items: Iterable[str]) -> List[str]:
    result = []
    seen = set()
    for item in items or []:
        cleaned = _clean_scalar(item)
        if not cleaned:
            continue
        key = _key(cleaned)
        if not key or key in seen:
            continue
        result.append(cleaned)
        seen.add(key)
    return result


def _clean_scalar(value: Optional[str]) -> str:
    if value is None:
        return ""
    cleaned = re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()
    cleaned = cleaned.strip(" \t\n\r-—–•*;")
    if cleaned.lower() in {"null", "none", "n/a", "not specified", "не указано"}:
        return ""
    return cleaned


def _key(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9+#]+", "", _clean_scalar(value).lower().replace("ё", "е"))
