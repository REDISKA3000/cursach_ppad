"""Vacancy Analyzer Agent"""
import logging
from app.schemas.vacancy import VacancyProfile
from app.services.llm_provider import get_llm_provider

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
            profile = self.llm.parse_vacancy(vacancy_text)
            
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
    
    def extract_role_level(self, vacancy_text: str) -> str:
        """Infer seniority level"""
        seniority_keywords = {
            "junior": ["junior", "entry", "entry-level", "fresh"],
            "mid": ["mid-level", "mid level", "intermediate", "3-5 years"],
            "senior": ["senior", "lead", "principal", "staff", "5+ years", "7+ years"],
            "manager": ["manager", "lead", "director", "head of"]
        }
        
        lower_text = vacancy_text.lower()
        
        for level, keywords in seniority_keywords.items():
            for keyword in keywords:
                if keyword in lower_text:
                    return level
        
        return "mid"  # default
    
    def extract_keywords_for_ats(self, profile: VacancyProfile, vacancy_text: str) -> list:
        """Extract ATS keywords"""
        keywords = set(profile.must_have_skills + profile.nice_to_have_skills)
        
        # Add common keywords
        ats_keywords = ["resume", "cv", "application", "cover letter"]
        for keyword in ats_keywords:
            if keyword in vacancy_text.lower():
                keywords.add(keyword.title())
        
        return list(keywords)
