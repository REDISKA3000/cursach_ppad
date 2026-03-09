from pydantic import BaseModel
from typing import Optional, List

class VacancyProfile(BaseModel):
    role: Optional[str] = None
    seniority: Optional[str] = None
    industry: Optional[str] = None
    must_have_skills: List[str] = []
    nice_to_have_skills: List[str] = []
    key_responsibilities: List[str] = []
    keywords_for_ats: List[str] = []
    raw_warnings: List[str] = []
