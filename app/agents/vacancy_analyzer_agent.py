"""Vacancy Analyzer Agent"""
import logging
from typing import Optional

from app.schemas.vacancy import VacancyProfile
from app.services.llm_provider import get_llm_provider
from app.services.vacancy_analyzer_stage import normalize_vacancy_profile

logger = logging.getLogger(__name__)

class VacancyAnalyzerAgent:
    def __init__(self):
        self.llm = get_llm_provider()
    
    def parse_vacancy(self, vacancy_text: str) -> VacancyProfile:
        """
        Parse job posting and extract vacancy profile
        
        Input: vacancy_text (str)
        Output: VacancyProfile (JSON)
        """
        if not vacancy_text or not vacancy_text.strip():
            profile = VacancyProfile()
            profile.raw_warnings.append("Empty vacancy text provided")
            return profile
        
        try:
            profile = normalize_vacancy_profile(self.llm.parse_vacancy(vacancy_text), vacancy_text)
            
            # Postprocessing: Fill missing data
            if not profile.seniority:
                profile.seniority = self.extract_role_level(vacancy_text)
            
            if not profile.keywords_for_ats:
                profile.keywords_for_ats = self.extract_keywords_for_ats(profile, vacancy_text)
            
            # Validation
            if not profile.role:
                profile.raw_warnings.append("Could not determine job title from posting")
            
            if not profile.must_have_skills:
                profile.raw_warnings.append("No clear 'must-have' skills identified. Results may be less accurate.")
            
            if len(vacancy_text) < 100:
                profile.raw_warnings.append("Job posting is very short. More details would improve accuracy.")
            
            return profile
        except Exception as e:
            logger.error(f"Error parsing vacancy: {e}")
            profile = VacancyProfile()
            profile.raw_warnings.append(f"Error processing vacancy: {str(e)}")
            return profile
    
    def extract_role_level(self, vacancy_text: str) -> Optional[str]:
        """Infer seniority level"""
        seniority_keywords = {
            "Junior": ["junior", "entry", "entry-level", "fresh", "джун", "джуниор"],
            "Middle": ["middle", "mid-level", "mid level", "intermediate", "1–3 года", "1-3 года", "3-5 years"],
            "Senior": ["senior", "principal", "staff", "3–6 лет", "3-6 лет", "5+ years", "7+ years"],
            "Lead": ["lead", "лид", "ведущий"],
            "Manager": ["manager", "director", "head of", "руководитель", "управляющий"]
        }
        
        lower_text = vacancy_text.lower()
        
        for level, keywords in seniority_keywords.items():
            for keyword in keywords:
                if keyword in lower_text:
                    return level
        
        return None
    
    def extract_keywords_for_ats(self, profile: VacancyProfile, vacancy_text: str) -> list:
        """Extract ATS keywords"""
        keywords = set(profile.must_have_skills + profile.nice_to_have_skills)
        
        # Add common keywords
        ats_keywords = ["resume", "cv", "application", "cover letter"]
        for keyword in ats_keywords:
            if keyword in vacancy_text.lower():
                keywords.add(keyword.title())
        
        return list(keywords)
