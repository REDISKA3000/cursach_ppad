from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


MANUAL_TEXT_FALLBACK = "manual_text"


class VacancyFetchError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str = "vacancy_fetch_failed",
        fallback: str = MANUAL_TEXT_FALLBACK,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.fallback = fallback


class UnsupportedVacancySourceError(VacancyFetchError):
    def __init__(self, domain: str) -> None:
        super().__init__(
            f"Ссылки с {domain} пока не поддерживаются автоматически. Вставьте текст вакансии вручную.",
            error_code="unsupported_source",
        )


class RestrictedVacancySourceError(VacancyFetchError):
    def __init__(self) -> None:
        super().__init__(
            "Ссылка HH пока не поддерживается автоматически. Вставьте текст вакансии вручную.",
            error_code="restricted_source_hh",
        )


@dataclass
class FetchedVacancy:
    success: bool
    source_type: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    salary: str = ""
    description: str = ""
    normalized_text: str = ""
    warnings: list[str] = field(default_factory=list)
    source_domain: str = ""
    url: str = ""


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {
            "script",
            "style",
            "noscript",
            "svg",
            "nav",
            "footer",
            "header",
            "aside",
            "form",
            "button",
        }:
            self._skip_depth += 1
        if tag in {"br", "p", "div", "li", "section", "article", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {
            "script",
            "style",
            "noscript",
            "svg",
            "nav",
            "footer",
            "header",
            "aside",
            "form",
            "button",
        } and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "li", "section", "article", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            cleaned = " ".join(data.split())
            if cleaned:
                self._parts.append(cleaned)

    def text(self) -> str:
        text = "\n".join(self._parts)
        lines = [" ".join(line.split()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line)


class VacancyExtractor:
    source_type = "generic"
    domains: tuple[str, ...] = ()

    def supports(self, domain: str, path: str) -> bool:
        return any(domain == item or domain.endswith(f".{item}") for item in self.domains)

    def extract(self, html_text: str, url: str, domain: str) -> FetchedVacancy:
        raise NotImplementedError

    def common_extract(
        self,
        html_text: str,
        url: str,
        domain: str,
        *,
        company_default: str = "",
        title_suffixes: Optional[list[str]] = None,
    ) -> FetchedVacancy:
        raw_title = (
            _meta(html_text, "og:title")
            or _meta(html_text, "twitter:title")
            or _extract_tag_text(html_text, "h1")
            or _extract_tag_text(html_text, "title")
        )
        description = (
            _description_from_json_ld(html_text)
            or _description_from_embedded_json(html_text)
            or _vacancy_content_from_html(html_text)
        )
        return FetchedVacancy(
            success=True,
            source_type=self.source_type,
            title=_clean_title(raw_title, suffixes=title_suffixes),
            company=_clean_text(_company_from_json_ld(html_text) or _company_from_embedded_json(html_text) or company_default),
            location=_clean_text(_location_from_json_ld(html_text) or _value_from_embedded_json(html_text, {"location", "city"})),
            salary=_clean_text(_salary_from_json_ld(html_text) or _value_from_embedded_json(html_text, {"salary", "salaryText"})),
            description=_clean_text(description),
            source_domain=domain,
            url=url,
            warnings=[],
        )


class GetMatchVacancyExtractor(VacancyExtractor):
    source_type = "getmatch"
    domains = ("getmatch.ru",)

    def extract(self, html_text: str, url: str, domain: str) -> FetchedVacancy:
        vacancy = self.common_extract(html_text, url, domain)
        if not vacancy.company:
            vacancy.company = _clean_text(_first_match(html_text, [
                r'"company"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"',
                r'"companyName"\s*:\s*"([^"]+)"',
            ]))
        return vacancy


class YandexVacancyExtractor(VacancyExtractor):
    source_type = "yandex"
    domains = ("yandex.ru",)

    def supports(self, domain: str, path: str) -> bool:
        return super().supports(domain, path) and ("/jobs" in path or "/vacancies" in path)

    def extract(self, html_text: str, url: str, domain: str) -> FetchedVacancy:
        return self.common_extract(
            html_text,
            url,
            domain,
            company_default="Яндекс",
            title_suffixes=["— Яндекс", "| Яндекс", " / Яндекс", "— Yandex", "| Yandex"],
        )


class SberVacancyExtractor(VacancyExtractor):
    source_type = "sber"
    domains = ("rabota.sber.ru", "career.sber.ru", "rabota.sberbank.ru")

    def extract(self, html_text: str, url: str, domain: str) -> FetchedVacancy:
        return self.common_extract(
            html_text,
            url,
            domain,
            company_default="Сбер",
            title_suffixes=["— Работа в Сбере", "| Работа в Сбере", " — Сбер", "| Сбер"],
        )


class GenericVacancyExtractor(VacancyExtractor):
    source_type = "generic"

    def extract(self, html_text: str, url: str, domain: str) -> FetchedVacancy:
        vacancy = self.common_extract(html_text, url, domain)
        vacancy.warnings.append("Описание извлечено generic parser-ом. Проверьте preview перед запуском адаптации.")
        return vacancy


SUPPORTED_EXTRACTORS: tuple[VacancyExtractor, ...] = (
    GetMatchVacancyExtractor(),
    YandexVacancyExtractor(),
    SberVacancyExtractor(),
)

GENERIC_EXTRACTOR = GenericVacancyExtractor()


def fetch_vacancy_from_url(url: str, timeout: int = 12) -> FetchedVacancy:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise VacancyFetchError(
            "Введите корректную ссылку на вакансию с http или https",
            error_code="invalid_url",
        )

    domain = parsed.netloc.lower().removeprefix("www.")
    if _is_hh_domain(domain):
        raise RestrictedVacancySourceError()

    extractor = _select_extractor(domain, parsed.path)
    html_text = _download_html(url, timeout=timeout)
    fetched = extractor.extract(html_text, url, domain)
    if fetched.source_type == "getmatch" and len(fetched.description) < 180:
        plain_text = _soup_page_text(html_text)
        if len(plain_text) > len(fetched.description):
            fetched.description = plain_text
            fetched.warnings.append("Описание GetMatch извлечено через plain text fallback.")

    if len(fetched.description) < 180:
        # Last bounded fallback: only the same already downloaded page, never another source.
        fallback = GENERIC_EXTRACTOR.extract(html_text, url, domain)
        if len(fallback.description) > len(fetched.description):
            fallback.source_type = fetched.source_type
            fallback.warnings.insert(0, "Основной extractor вернул неполное описание, использован HTML fallback этой же страницы.")
            fetched = fallback

    if len(fetched.description) < 180:
        raise VacancyFetchError(
            "Не удалось извлечь полное описание. Возможно, страница закрыта антиботом или рендерится через JS.",
            error_code="empty_extraction",
        )

    fetched.normalized_text = _build_normalized_text(fetched)
    return fetched


def _select_extractor(domain: str, path: str) -> VacancyExtractor:
    for extractor in SUPPORTED_EXTRACTORS:
        if extractor.supports(domain, path):
            return extractor
    raise UnsupportedVacancySourceError(domain)


def _download_html(url: str, timeout: int) -> str:
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
        )
    except requests.Timeout as exc:
        raise VacancyFetchError(
            "Сайт слишком долго отвечает. Вставьте текст вакансии вручную.",
            error_code="timeout",
        ) from exc
    except requests.RequestException as exc:
        raise VacancyFetchError(
            "Не удалось открыть ссылку. Проверьте URL или вставьте текст вакансии вручную.",
            error_code="request_failed",
        ) from exc

    if response.status_code >= 400:
        raise VacancyFetchError(
            f"Сайт вернул ошибку {response.status_code}. Вставьте текст вакансии вручную.",
            error_code="non_200",
        )
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        raise VacancyFetchError(
            "По ссылке не найдена HTML-страница вакансии.",
            error_code="not_html",
        )
    return response.text


def _is_hh_domain(domain: str) -> bool:
    return domain == "hh.ru" or domain.endswith(".hh.ru")


def _build_normalized_text(vacancy: FetchedVacancy) -> str:
    parts = []
    if vacancy.title:
        parts.append(f"Вакансия: {vacancy.title}")
    if vacancy.company:
        parts.append(f"Компания: {vacancy.company}")
    if vacancy.location:
        parts.append(f"Локация: {vacancy.location}")
    if vacancy.salary:
        parts.append(f"Зарплата: {vacancy.salary}")
    parts.append("Описание вакансии:")
    parts.append(vacancy.description)
    parts.append(f"Источник: {vacancy.url}")
    return "\n\n".join(part for part in parts if part).strip()


def _html_to_text(value: Optional[str]) -> str:
    if not value:
        return ""
    parser = _ReadableHTMLParser()
    parser.feed(html.unescape(value))
    return parser.text()


def _vacancy_content_from_html(html_text: str) -> str:
    candidates = []
    for pattern in [
        r"<main[^>]*>(.*?)</main>",
        r"<article[^>]*>(.*?)</article>",
        r'<section[^>]+(?:class|data-testid)=["\'][^"\']*(?:vacancy|job|description)[^"\']*["\'][^>]*>(.*?)</section>',
        r'<div[^>]+(?:class|data-testid)=["\'][^"\']*(?:vacancy|job|description)[^"\']*["\'][^>]*>(.*?)</div>',
        r"<body[^>]*>(.*?)</body>",
    ]:
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            candidates.append(_html_to_text(match.group(1)))
    candidates.append(_soup_page_text(html_text))
    return max(candidates, key=len, default=_html_to_text(html_text))


def _soup_page_text(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form", "button"]):
        tag.decompose()
    lines = [" ".join(line.split()) for line in soup.get_text("\n", strip=True).splitlines()]
    text = "\n".join(line for line in lines if line)
    return _strip_repeated_ui_lines(text)


def _strip_repeated_ui_lines(text: str) -> str:
    blocked = {
        "войти",
        "регистрация",
        "зарегистрироваться",
        "откликнуться",
        "поделиться",
        "в избранное",
        "вакансии",
        "компании",
        "соискатели",
    }
    result = []
    previous = ""
    for line in text.splitlines():
        normalized = line.strip()
        lowered = normalized.lower()
        if not normalized or lowered in blocked:
            continue
        if normalized == previous:
            continue
        result.append(normalized)
        previous = normalized
    return "\n".join(result)


def _meta(html_text: str, name: str) -> str:
    escaped = re.escape(name)
    patterns = [
        rf'<meta[^>]+property=["\']{escaped}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+name=["\']{escaped}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{escaped}["\']',
    ]
    return _first_match(html_text, patterns, flags=re.IGNORECASE)


def _extract_tag_text(html_text: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html_text, flags=re.IGNORECASE | re.DOTALL)
    return _html_to_text(match.group(1)) if match else ""


def _description_from_json_ld(html_text: str) -> str:
    for item in _json_ld_objects(html_text):
        if _json_type(item).lower() == "jobposting" and item.get("description"):
            return _html_to_text(str(item.get("description")))
    return ""


def _description_from_embedded_json(html_text: str) -> str:
    strings: list[str] = []
    for item in _embedded_json_objects(html_text):
        strings.extend(_json_strings(item))

    candidates = []
    for value in strings:
        text = _clean_text(value)
        lowered = text.lower()
        if len(text) < 180:
            continue
        if any(marker in lowered for marker in [
            "обязанности",
            "требования",
            "задачи",
            "responsibilities",
            "requirements",
            "ваканси",
            "команд",
            "опыт",
        ]):
            candidates.append(text)
    return max(candidates, key=len, default="")


def _company_from_json_ld(html_text: str) -> str:
    for item in _json_ld_objects(html_text):
        if _json_type(item).lower() != "jobposting":
            continue
        org = item.get("hiringOrganization") or {}
        if isinstance(org, dict):
            return str(org.get("name") or "")
    return ""


def _location_from_json_ld(html_text: str) -> str:
    for item in _json_ld_objects(html_text):
        if _json_type(item).lower() != "jobposting":
            continue
        location = item.get("jobLocation") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        if isinstance(location, dict):
            address = location.get("address") or {}
            if isinstance(address, dict):
                return str(address.get("addressLocality") or address.get("addressRegion") or "")
    return ""


def _salary_from_json_ld(html_text: str) -> str:
    for item in _json_ld_objects(html_text):
        if _json_type(item).lower() != "jobposting":
            continue
        salary = item.get("baseSalary") or {}
        if isinstance(salary, dict):
            value = salary.get("value") or {}
            if isinstance(value, dict):
                min_value = value.get("minValue")
                max_value = value.get("maxValue")
                currency = salary.get("currency") or value.get("currency") or ""
                if min_value or max_value:
                    return f"{min_value or ''}-{max_value or ''} {currency}".strip(" -")
    return ""


def _company_from_embedded_json(html_text: str) -> str:
    return _value_from_embedded_json(html_text, {"companyName", "company", "employer", "organization"})


def _value_from_embedded_json(html_text: str, keys: set[str]) -> str:
    for item in _embedded_json_objects(html_text):
        value = _find_json_value(item, keys)
        if value:
            return value
    return ""


def _find_json_value(value, keys: set[str]) -> str:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                if isinstance(item, str):
                    return item
                if isinstance(item, dict):
                    nested_name = item.get("name") or item.get("title") or item.get("value")
                    if nested_name:
                        return str(nested_name)
            found = _find_json_value(item, keys)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_json_value(item, keys)
            if found:
                return found
    return ""


def _json_ld_objects(html_text: str) -> list[dict]:
    result: list[dict] = []
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_text, flags=re.IGNORECASE | re.DOTALL):
        raw = html.unescape(match.group(1)).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        result.extend(item for item in items if isinstance(item, dict))
    return result


def _embedded_json_objects(html_text: str) -> list[dict | list]:
    result: list[dict | list] = []
    patterns = [
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html_text, flags=re.IGNORECASE | re.DOTALL):
            raw = html.unescape(match.group(1)).strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, (dict, list)):
                result.append(parsed)
    return result


def _json_strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_json_strings(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_json_strings(item))
        return result
    return []


def _json_type(item: dict) -> str:
    value = item.get("@type") or item.get("type") or ""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def _first_match(html_text: str, patterns: list[str], flags=re.IGNORECASE | re.DOTALL) -> str:
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=flags)
        if match:
            return match.group(1)
    return ""


def _clean_text(value: str) -> str:
    value = _html_to_text(value) if "<" in str(value) and ">" in str(value) else html.unescape(str(value or ""))
    lines = [" ".join(line.split()) for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _clean_title(value: str, suffixes: Optional[list[str]] = None) -> str:
    title = _clean_text(value)
    for suffix in suffixes or []:
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
    title = re.sub(r"\s*[|—-]\s*(GetMatch|getmatch|Яндекс Работа|Работа в Сбере)\s*$", "", title).strip()
    return title
