from pydantic import BaseModel
from typing import List

class TechnicalReport(BaseModel):
    highlighted_jobs: List[int] = []
    highlighted_skills: List[str] = []
    covered_must_haves: List[str] = []
    uncovered_must_haves: List[str] = []
    critic_warnings: List[str] = []

class GeneratedResume(BaseModel):
    title: str
    resume_text: str
    technical_report: TechnicalReport
