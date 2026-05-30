from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.repositories.resumes import JobBoardVacancyRepository
logger = logging.getLogger(__name__)

GETMATCH_BASE_URL = "https://getmatch.ru"
GETMATCH_API_BASE_URL = "https://getmatch.ru/api"
_POOL_SYNC_STARTED = False
_POOL_SYNC_LOCK = threading.Lock()


@dataclass
class VacancyPoolItem:
    source: str
    source_url: str
    title: str
    company: str = ""
    location: str = ""
    salary: str = ""
    description: str = ""
    normalized_text: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class GetMatchIngestionResult:
    total_from_api: int = 0
    discovered: int = 0
    saved: int = 0
    skipped: int = 0
    failed: int = 0
    items: list[VacancyPoolItem] = field(default_factory=list)


def ensure_vacancy_pool(db: Session, *, max_age_hours: int = 24) -> None:
    """Compatibility hook: synchronously fill the pool when explicitly called."""
    count = JobBoardVacancyRepository.count(db)
    if count:
        return
    result = ingest_getmatch_vacancies(db, limit=None, commit=True)
    logger.info(
        "Vacancy pool sync completed: total_from_api=%s discovered=%s saved=%s skipped=%s failed=%s",
        result.total_from_api,
        result.discovered,
        result.saved,
        result.skipped,
        result.failed,
    )


def start_getmatch_pool_sync_if_needed(
    session_factory,
    *,
    enabled: bool = True,
    min_size: int = 100,
    limit: int | None = None,
) -> bool:
    """Start a non-blocking GetMatch sync if the shared vacancy pool is empty/small.

    Railway deployments should not require a manual shell command just to make
    the recommendations rail useful. The sync is deliberately backgrounded so
    the web process can boot and pass health checks quickly.
    """
    if not enabled:
        logger.info("Vacancy pool auto-sync disabled")
        return False

    global _POOL_SYNC_STARTED
    with _POOL_SYNC_LOCK:
        if _POOL_SYNC_STARTED:
            return False
        _POOL_SYNC_STARTED = True

    def _run() -> None:
        db = session_factory()
        try:
            before = JobBoardVacancyRepository.count(db)
            if before >= min_size:
                logger.info("Vacancy pool auto-sync skipped: count=%s min_size=%s", before, min_size)
                return

            logger.info(
                "Vacancy pool auto-sync started: count=%s min_size=%s limit=%s",
                before,
                min_size,
                limit or "full",
            )
            removed_demo_rows = JobBoardVacancyRepository.delete_known_demo_rows(db)
            result = ingest_getmatch_vacancies(db, limit=limit, commit=True)
            after = JobBoardVacancyRepository.count(db)
            logger.info(
                "Vacancy pool auto-sync finished: total_from_api=%s discovered=%s saved=%s "
                "skipped=%s failed=%s removed_demo_rows=%s total_before=%s total_after=%s",
                result.total_from_api,
                result.discovered,
                result.saved,
                result.skipped,
                result.failed,
                removed_demo_rows,
                before,
                after,
            )
        except Exception:
            logger.exception("Vacancy pool auto-sync failed")
        finally:
            db.close()

    threading.Thread(target=_run, name="getmatch-vacancy-pool-sync", daemon=True).start()
    return True


def save_vacancy_pool_items(db: Session, collected: list[VacancyPoolItem]) -> int:
    saved = 0
    for item in collected:
        if not item.source_url or not item.title:
            continue
        JobBoardVacancyRepository.upsert_by_url(
            db,
            source=item.source,
            source_url=item.source_url,
            title=item.title,
            company=item.company,
            location=item.location,
            salary=item.salary,
            description=item.description,
            normalized_text=item.normalized_text or build_normalized_text(item),
            tags=item.tags,
        )
        saved += 1
    return saved


def ingest_getmatch_vacancies(db: Session, *, limit: int | None = None, commit: bool = True) -> GetMatchIngestionResult:
    """Discover real GetMatch offers, fetch detail JSON for each offer, and optionally save them."""
    result = GetMatchPoolCollector().collect(limit=limit)
    if commit:
        result.saved = save_vacancy_pool_items(db, result.items)
    return result


class GetMatchPoolCollector:
    source = "getmatch"
    listing_url = f"{GETMATCH_API_BASE_URL}/offers"

    def collect(self, limit: int | None = None) -> GetMatchIngestionResult:
        offers, total_from_api = self.discover_offers(limit=limit)
        items: list[VacancyPoolItem] = []
        skipped = 0
        failed = 0
        for offer in offers:
            try:
                detail = self.fetch_offer_detail(int(offer["id"]))
            except (KeyError, TypeError, ValueError, requests.RequestException) as exc:
                logger.info("GetMatch offer skipped %s: %s", offer.get("id"), exc)
                failed += 1
                continue
            item = self.offer_to_pool_item(detail)
            if item.description or item.normalized_text:
                items.append(item)
            else:
                skipped += 1
        return GetMatchIngestionResult(
            total_from_api=total_from_api,
            discovered=len(offers),
            skipped=skipped,
            failed=failed,
            items=items,
        )

    def discover_offers(self, *, limit: int | None = None, page_size: int = 50) -> tuple[list[dict], int]:
        offers: list[dict] = []
        seen_ids: set[int] = set()
        offset = 0
        total = 0
        while True:
            data = _download_json(
                self.listing_url,
                params={
                    "p": str(offset // page_size + 1),
                    "offset": str(offset),
                    "limit": str(page_size),
                    "sa": "",
                    "s": "offers",
                },
            )
            page_offers = data.get("offers") or []
            if not page_offers:
                break
            meta = data.get("meta") or {}
            total = int(meta.get("total") or total or 0)
            for offer in page_offers:
                offer_id = offer.get("id")
                if not offer_id or offer_id in seen_ids:
                    continue
                seen_ids.add(offer_id)
                offers.append(offer)
                if limit is not None and len(offers) >= limit:
                    break
            offset += page_size
            if limit is not None and len(offers) >= limit:
                break
            if total and offset >= total:
                break
        return offers, total

    def fetch_offer_detail(self, offer_id: int) -> dict:
        return _download_json(f"{GETMATCH_API_BASE_URL}/offers/{offer_id}")

    def offer_to_pool_item(self, offer: dict) -> VacancyPoolItem:
        title = _clean_text(offer.get("position") or offer.get("title") or "")
        company = _clean_text((offer.get("company") or {}).get("name") or "")
        source_url = urljoin(GETMATCH_BASE_URL, offer.get("url") or f"/vacancies/{offer.get('id')}")
        description_html = (
            offer.get("offer_description")
            or offer.get("description_html")
            or offer.get("description")
            or offer.get("short_description")
            or ""
        )
        description = _html_to_text(description_html)
        stack = [
            _clean_text(item.get("name") if isinstance(item, dict) else item)
            for item in (offer.get("stack") or [])
        ]
        location = _format_getmatch_locations(offer.get("location_items") or offer.get("location_requirements") or [])
        salary = _format_getmatch_salary(offer)
        tags = _extract_tags(" ".join([title, company, description, " ".join(stack)]))
        normalized_text = "\n".join(
            part
            for part in [
                f"Вакансия: {title}" if title else "",
                f"Компания: {company}" if company else "",
                f"Локация: {location}" if location else "",
                f"Зарплата: {salary}" if salary else "",
                f"Стек: {', '.join(stack)}" if stack else "",
                "Описание вакансии:",
                description,
                f"Источник: {source_url}",
            ]
            if part
        )
        return VacancyPoolItem(
            source="getmatch",
            source_url=source_url,
            title=title,
            company=company,
            location=location,
            salary=salary,
            description=description,
            normalized_text=normalized_text,
            tags=tags,
        )


class OpenHuntPoolCollector:
    source = "openhunt"
    listing_url = "https://openhunt.ru/"

    def collect(self, limit: int = 16) -> list[VacancyPoolItem]:
        html = _download(self.listing_url)
        soup = BeautifulSoup(html, "html.parser")
        items: list[VacancyPoolItem] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href") or ""
            url = urljoin(self.listing_url, href)
            if "openhunt.ru" in url or not url.startswith(("http://", "https://")):
                continue
            if url in seen:
                continue
            seen.add(url)

            container_text = _clean_text(anchor.parent.get_text(" ", strip=True) if anchor.parent else anchor.get_text(" ", strip=True))
            company = _clean_text(anchor.get_text(" ", strip=True)) or _company_from_openhunt_text(container_text) or "Компания"
            tags = _extract_tags(container_text)
            description = container_text or f"Карьерная страница {company}. Проверьте открытые роли на сайте компании."
            items.append(
                VacancyPoolItem(
                    source="openhunt",
                    source_url=url,
                    title=f"Вакансии {company}",
                    company=company,
                    description=description,
                    normalized_text=f"Источник: OpenHunt\nКомпания: {company}\nСсылка: {url}\nОписание: {description}",
                    tags=tags,
                )
            )
            if len(items) >= limit:
                break
        return items


def recommended_vacancies_for_source(db: Session, source_resume, *, limit: int = 30) -> list[dict]:
    candidate_profile = source_resume.candidate_profile_json or {}
    candidate_terms = candidate_recommendation_terms(candidate_profile)
    vacancies = JobBoardVacancyRepository.list_all(db)
    ranked = []
    for vacancy in vacancies:
        score, reason = score_vacancy(vacancy, candidate_terms)
        ranked.append((score, reason, vacancy))
    ranked.sort(key=lambda item: (item[0], item[2].collected_at or item[2].created_at), reverse=True)
    return [
        {
            "vacancy": vacancy,
            "score": round(score, 3),
            "reason": reason,
        }
        for score, reason, vacancy in ranked[:limit]
    ]


def candidate_recommendation_terms(profile: dict) -> dict:
    canonical = profile.get("canonical_profile") or profile
    skills = _as_list(canonical.get("skills_hard"))
    target_role = canonical.get("target_role") or ""
    jobs = canonical.get("jobs") or []
    job_terms = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_terms.extend(_as_list(job.get("skills_used")))
        job_terms.extend([job.get("position", ""), job.get("company_type", "")])

    return {
        "role_tokens": _tokens(target_role),
        "skill_tokens": set().union(*[_tokens(skill) for skill in skills], set()) if skills else set(),
        "domain_tokens": set().union(*[_tokens(term) for term in job_terms if term], set()) if job_terms else set(),
        "skills": skills,
        "target_role": target_role,
    }


def score_vacancy(vacancy, candidate_terms: dict) -> tuple[float, str]:
    haystack = " ".join(
        str(part or "")
        for part in [
            vacancy.title,
            vacancy.company,
            vacancy.location,
            vacancy.description,
            vacancy.normalized_text,
            " ".join(vacancy.tags_json or []),
        ]
    )
    hay_tokens = _tokens(haystack)
    role_overlap = len(candidate_terms["role_tokens"] & hay_tokens)
    skill_overlap = len(candidate_terms["skill_tokens"] & hay_tokens)
    domain_overlap = len(candidate_terms["domain_tokens"] & hay_tokens)
    score = role_overlap * 3.0 + skill_overlap * 1.4 + domain_overlap * 0.8

    reasons = []
    if role_overlap:
        reasons.append("совпадает по роли")
    if skill_overlap:
        reasons.append("есть пересечение по навыкам")
    if domain_overlap:
        reasons.append("похожий домен")
    if not reasons:
        reasons.append("свежая вакансия из пула")
    return score, ", ".join(reasons)


def build_normalized_text(item: VacancyPoolItem) -> str:
    parts = [
        f"Роль: {item.title}",
        f"Компания: {item.company}" if item.company else "",
        f"Локация: {item.location}" if item.location else "",
        f"Зарплата: {item.salary}" if item.salary else "",
        "Описание:",
        item.description,
    ]
    return "\n".join(part for part in parts if part)


def bootstrap_pool_items() -> list[VacancyPoolItem]:
    """Small resilient bootstrap so the rail is not empty when external sources are unavailable locally."""
    return [
        VacancyPoolItem(
            source="getmatch",
            source_url="https://getmatch.ru/vacancies/34390-one-day-offer-dlia-data-science?s=offers",
            title="Data Scientist",
            company="One Day Offer",
            location="Remote",
            description="Data Science роль: Python, ML, продуктовые метрики, эксперименты, аналитика данных.",
            tags=["data", "python", "ml", "analytics"],
        ),
        VacancyPoolItem(
            source="openhunt",
            source_url="https://yandex.ru/jobs",
            title="Вакансии Яндекс",
            company="Яндекс",
            description="Карьерный источник из OpenHunt: bigtech, product, analytics, backend, data, highload.",
            tags=["bigtech", "product", "analytics", "data"],
        ),
        VacancyPoolItem(
            source="openhunt",
            source_url="https://www.tbank.ru/career/",
            title="Вакансии T-Bank",
            company="T-Bank",
            description="Карьерный источник из OpenHunt: fintech, backend, data, platform, product analytics.",
            tags=["fintech", "data", "product", "analytics"],
        ),
    ]


def _download(url: str, timeout: int = 8) -> str:
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        },
    )
    response.raise_for_status()
    return response.text


def _download_json(url: str, *, params: dict = None, timeout: int = 12) -> dict:
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        },
    )
    response.raise_for_status()
    return response.json()


def _html_to_text(value: str) -> str:
    text = BeautifulSoup(str(value or ""), "html.parser").get_text("\n", strip=True)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _format_getmatch_locations(locations: list) -> str:
    labels = []
    for item in locations or []:
        if not isinstance(item, dict):
            continue
        label = item.get("label") or item.get("city") or item.get("country") or ""
        work_format = item.get("format") or ""
        text = " · ".join(part for part in [_clean_text(label), _clean_text(work_format)] if part)
        if text and text not in labels:
            labels.append(text)
    return "; ".join(labels)


def _format_getmatch_salary(offer: dict) -> str:
    if offer.get("salary_description"):
        return _clean_text(offer["salary_description"])
    salary_from = offer.get("salary_display_from")
    salary_to = offer.get("salary_display_to")
    currency = offer.get("salary_currency") or ""
    if salary_from and salary_to:
        return _clean_text(f"{salary_from}–{salary_to} {currency}")
    if salary_from:
        return _clean_text(f"от {salary_from} {currency}")
    if salary_to:
        return _clean_text(f"до {salary_to} {currency}")
    return ""


def _tokens(text: str) -> set[str]:
    normalized = str(text or "").lower().replace("ё", "е")
    return {token for token in re.findall(r"[a-zа-я0-9+#/.-]{2,}", normalized) if token not in _STOP_WORDS}


def _extract_tags(text: str) -> list[str]:
    tokens = _tokens(text)
    priority = [
        "python",
        "sql",
        "data",
        "analytics",
        "product",
        "ml",
        "backend",
        "frontend",
        "fintech",
        "banking",
        "risk",
        "bi",
        "etl",
        "airflow",
    ]
    return [tag for tag in priority if tag in tokens][:8]


def _company_from_openhunt_text(text: str) -> str:
    text = _clean_text(text)
    return text.split(" ", 1)[0] if text else ""


def _clean_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


_STOP_WORDS = {
    "and",
    "the",
    "для",
    "или",
    "это",
    "как",
    "что",
    "with",
    "from",
    "вакансии",
    "работа",
}
