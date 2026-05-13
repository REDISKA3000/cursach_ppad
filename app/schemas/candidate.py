from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ConfidenceLevel = Literal["low", "medium", "high"]
EducationStatus = Literal["completed", "incomplete", "unknown"]
ExtractionMode = Literal["explicit", "inferred", "normalized", "fallback", "missing", "llm_validated", "llm_unvalidated"]
ValidationStatus = Literal["exact", "normalized_match", "block_match", "failed", "not_applicable", "not_validated"]


class ProvenanceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_block_id: Optional[str] = None
    source_snippets: List[str] = Field(default_factory=list)
    source_line_range: Optional[List[int]] = None
    extraction_mode: ExtractionMode = "explicit"
    validation_status: ValidationStatus = "not_applicable"
    confidence_hint: ConfidenceLevel = "medium"


class CandidateJobEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: int
    company: List[str] = Field(default_factory=list)
    position: List[str] = Field(default_factory=list)
    period: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)


class CandidateEvidenceBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_role: List[str] = Field(default_factory=list)
    total_experience: List[str] = Field(default_factory=list)
    skills_section: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    jobs: List[CandidateJobEvidenceItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_evidence(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        if value is None:
            return {}
        if not isinstance(value, dict):
            return {}

        if "jobs" in value or "total_experience" in value or "skills_section" in value:
            return value

        jobs_by_id: Dict[int, Dict[str, Any]] = {}
        for key, snippets in value.items():
            match = re_match_job_evidence_key(key)
            if not match:
                continue
            job_id, field_name = match
            item = jobs_by_id.setdefault(
                job_id,
                {"job_id": job_id, "company": [], "position": [], "period": [], "highlights": []},
            )
            if field_name in {"responsibilities", "achievements", "skills_used"}:
                item["highlights"].extend(_coerce_snippet_list(snippets)[:2])
            elif field_name in item:
                item[field_name].extend(_coerce_snippet_list(snippets))

        return {
            "target_role": _coerce_snippet_list(value.get("target_role")),
            "total_experience": _coerce_snippet_list(value.get("total_experience") or value.get("experience_years")),
            "skills_section": _coerce_snippet_list(value.get("skills_section") or value.get("skills_hard")),
            "education": _coerce_snippet_list(value.get("education")),
            "languages": _coerce_snippet_list(value.get("languages")),
            "jobs": list(jobs_by_id.values()),
        }

    @field_validator("target_role", "total_experience", "skills_section", "education", "languages", mode="before")
    @classmethod
    def _coerce_global_snippets(cls, value: Any) -> List[str]:
        return _coerce_snippet_list(value)

    def get_job(self, job_id: int) -> Optional[CandidateJobEvidenceItem]:
        for item in self.jobs:
            if item.job_id == job_id:
                return item
        return None

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        if key == "experience_years":
            return self.total_experience
        if key == "skills_hard":
            return self.skills_section

        match = re_match_job_evidence_key(key)
        if match:
            job_id, field_name = match
            job_evidence = self.get_job(job_id)
            if not job_evidence:
                return default
            if field_name in {"responsibilities", "achievements", "skills_used"}:
                return job_evidence.highlights
            return getattr(job_evidence, field_name, default)
        return default

    def __getitem__(self, key: str) -> Any:
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def keys(self) -> List[str]:
        return list(self.to_legacy_dict().keys())

    def items(self):
        return self.to_legacy_dict().items()

    def to_legacy_dict(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {
            "target_role": list(self.target_role),
            "experience_years": list(self.total_experience),
            "skills_hard": list(self.skills_section),
            "education": list(self.education),
            "languages": list(self.languages),
        }
        for job in self.jobs:
            result[f"job_{job.job_id}_company"] = list(job.company)
            result[f"job_{job.job_id}_position"] = list(job.position)
            result[f"job_{job.job_id}_period"] = list(job.period)
            result[f"job_{job.job_id}_highlights"] = list(job.highlights)
        return result


class CandidateJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    position: Optional[str] = None
    period: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    responsibilities: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    skills_used: List[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    year: Optional[str] = None
    status: EducationStatus = "unknown"


class LanguageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    level: Optional[str] = None


class ConfidenceBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall: ConfidenceLevel = "low"
    target_role: ConfidenceLevel = "low"
    experience_years: ConfidenceLevel = "low"
    jobs: ConfidenceLevel = "low"
    skills: ConfidenceLevel = "low"
    education: ConfidenceLevel = "low"
    languages: ConfidenceLevel = "low"


class CandidateCanonicalProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_role: Optional[str] = None
    experience_years: Optional[int] = None
    experience_months: Optional[int] = None
    summary_raw: Optional[str] = None
    jobs: List[CandidateJob] = Field(default_factory=list)
    skills_hard: List[str] = Field(default_factory=list)
    skills_soft: List[str] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    languages: List[LanguageItem] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)

    @field_validator("languages", mode="before")
    @classmethod
    def _coerce_languages(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            return value

        normalized = []
        for item in value:
            if isinstance(item, LanguageItem):
                normalized.append(item.model_dump())
            elif isinstance(item, str):
                cleaned = item.strip()
                if cleaned:
                    normalized.append({"name": cleaned, "level": None})
            elif isinstance(item, dict):
                normalized.append(item)
        return normalized


class CandidateProfileV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_profile: CandidateCanonicalProfile = Field(default_factory=CandidateCanonicalProfile)
    evidence: CandidateEvidenceBlock = Field(default_factory=CandidateEvidenceBlock)
    provenance: Dict[str, List[ProvenanceItem]] = Field(default_factory=dict)
    ambiguities: List[str] = Field(default_factory=list)
    confidence: ConfidenceBlock = Field(default_factory=ConfidenceBlock)
    raw_warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        if "canonical_profile" in data:
            return data

        legacy_keys = {
            "target_role",
            "experience_years",
            "experience_months",
            "summary_raw",
            "jobs",
            "skills_hard",
            "skills_soft",
            "education",
            "languages",
            "certifications",
        }
        if not any(key in data for key in legacy_keys):
            return data

        canonical = {
            "target_role": data.get("target_role"),
            "experience_years": data.get("experience_years"),
            "experience_months": data.get("experience_months"),
            "summary_raw": data.get("summary_raw"),
            "jobs": data.get("jobs", []),
            "skills_hard": data.get("skills_hard", []),
            "skills_soft": data.get("skills_soft", []),
            "education": data.get("education", []),
            "languages": data.get("languages", []),
            "certifications": data.get("certifications", []),
        }
        return {
            "canonical_profile": canonical,
            "evidence": data.get("evidence", {}),
            "provenance": data.get("provenance", {}),
            "ambiguities": data.get("ambiguities", []),
            "confidence": data.get("confidence", {}),
            "raw_warnings": data.get("raw_warnings", []),
        }

    @field_validator("provenance", mode="before")
    @classmethod
    def _coerce_provenance(cls, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            return {}

        normalized: Dict[str, List[Dict[str, Any]]] = {}
        for key, items in value.items():
            if items is None:
                normalized[key] = []
            elif isinstance(items, dict):
                normalized[key] = [items]
            elif isinstance(items, list):
                normalized[key] = [item for item in items if isinstance(item, dict)]
        return normalized

    def _sync_languages_from_legacy(self, value: Any) -> None:
        normalized: List[LanguageItem] = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, LanguageItem):
                    normalized.append(item)
                elif isinstance(item, str):
                    cleaned = item.strip()
                    if cleaned:
                        normalized.append(LanguageItem(name=cleaned, level=None))
                elif isinstance(item, dict) and item.get("name"):
                    normalized.append(LanguageItem(**item))
        self.canonical_profile.languages = normalized

    def _get_legacy_languages(self) -> List[str]:
        return [item.name for item in self.canonical_profile.languages if item.name]

    def __getattr__(self, name: str) -> Any:
        if name in {
            "target_role",
            "experience_years",
            "experience_months",
            "summary_raw",
            "jobs",
            "skills_hard",
            "skills_soft",
            "education",
            "certifications",
        }:
            return getattr(self.canonical_profile, name)
        if name == "languages":
            return self._get_legacy_languages()
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "languages" and "canonical_profile" in self.__dict__:
            self._sync_languages_from_legacy(value)
            return
        if name in {
            "target_role",
            "experience_years",
            "experience_months",
            "summary_raw",
            "jobs",
            "skills_hard",
            "skills_soft",
            "education",
            "certifications",
        } and "canonical_profile" in self.__dict__:
            setattr(self.__dict__["canonical_profile"], name, value)
            return
        super().__setattr__(name, value)

    def to_legacy_dict(self) -> Dict[str, Any]:
        return {
            "target_role": self.target_role,
            "experience_years": self.experience_years,
            "experience_months": self.experience_months,
            "summary_raw": self.summary_raw,
            "jobs": [job.model_dump() for job in self.jobs],
            "skills_hard": list(self.skills_hard),
            "skills_soft": list(self.skills_soft),
            "education": [item.model_dump() for item in self.education],
            "languages": self.languages,
            "certifications": list(self.certifications),
            "raw_warnings": list(self.raw_warnings),
        }


class CandidateProfile(CandidateProfileV2):
    pass


def _coerce_snippet_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        result = []
        for item in value:
            if item is None:
                continue
            cleaned = str(item).strip()
            if cleaned:
                result.append(cleaned)
        return result
    return []


def re_match_job_evidence_key(key: str) -> Optional[tuple[int, str]]:
    import re

    match = re.match(r"^job_(\d+)_(company|position|period|responsibilities|achievements|skills_used|highlights)$", str(key))
    if not match:
        return None
    return int(match.group(1)), match.group(2)
