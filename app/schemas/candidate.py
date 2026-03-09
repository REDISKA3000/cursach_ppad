from pydantic import BaseModel
from typing import Optional, List

class CandidateJob(BaseModel):
    id: int
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    position: Optional[str] = None
    period: Optional[str] = None
    responsibilities: List[str] = []
    achievements: List[str] = []
    skills_used: List[str] = []

class EducationItem(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    year: Optional[str] = None

class CandidateProfile(BaseModel):
    target_role: Optional[str] = None
    experience_years: Optional[int] = None
    summary_raw: Optional[str] = None
    jobs: List[CandidateJob] = []
    skills_hard: List[str] = []
    skills_soft: List[str] = []
    education: List[EducationItem] = []
    languages: List[str] = []
    certifications: List[str] = []
    raw_warnings: List[str] = []
