"""Candidate Profile Agent"""
import logging
from app.schemas.candidate import CandidateProfile
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

class CandidateProfileAgent:
    def __init__(self):
        self.llm = get_llm_provider()
    
    def parse_resume(self, resume_text: str) -> CandidateProfile:
        """
        Parse resume text and extract candidate profile
        
        Input: resume_text (str)
        Output: CandidateProfile (JSON)
        """
        if not resume_text or not resume_text.strip():
            profile = CandidateProfile()
            profile.raw_warnings.append("Empty resume provided")
            return profile
        
        try:
            profile = self.llm.parse_candidate_profile(resume_text)
            
            # Validation
            if not profile.jobs:
                profile.raw_warnings.append("No jobs detected in resume. Please ensure work experience is included.")
            if not profile.skills_hard:
                profile.raw_warnings.append("No technical skills detected. Please list your technical skills.")
            
            return profile
        except Exception as e:
            logger.error(f"Error parsing resume: {e}")
            profile = CandidateProfile()
            profile.raw_warnings.append(f"Error processing resume: {str(e)}")
            return profile
    
    def merge_with_answers(self, profile: CandidateProfile, answers: dict) -> CandidateProfile:
        """
        Merge candidate profile with questionnaire answers
        
        Inputs:
        - profile: CandidateProfile
        - answers: dict with keys like "target_role", "management_experience", etc.
        
        Output: Updated CandidateProfile
        """
        if answers.get("target_role"):
            profile.target_role = answers["target_role"]
        
        if answers.get("management_experience") and "no" not in str(answers.get("management_experience")).lower():
            if "leadership" not in profile.skills_soft:
                profile.skills_soft.append("Leadership")
        
        if answers.get("preferred_industry"):
            profile.raw_warnings.append(f"Preferred industry: {answers['preferred_industry']}")
        
        return profile
    
    def detect_missing_fields(self, profile: CandidateProfile) -> list:
        """Detect which fields are missing or ambiguous"""
        missing = []
        
        if not profile.target_role:
            missing.append("target_role")
        if not profile.experience_years:
            missing.append("experience_years")
        if not profile.jobs:
            missing.append("jobs")
        if not profile.skills_hard:
            missing.append("skills_hard")
        if not profile.education:
            missing.append("education")
        
        return missing
    
    def get_clarifying_questions(self, profile: CandidateProfile) -> list:
        """Generate clarifying questions based on missing fields"""
        questions = []
        
        if not profile.target_role:
            questions.append("What role are you targeting?")
        
        if not profile.experience_years or profile.experience_years == 0:
            questions.append("How many years of experience do you have?")
        
        if not any("lead" in skill.lower() or "manager" in skill.lower() for skill in profile.skills_soft):
            questions.append("Do you have experience in a management or leadership role?")
        
        if not profile.education:
            questions.append("What is your educational background?")
        
        if not profile.languages or len(profile.languages) == 0:
            questions.append("What languages do you speak fluently?")
        
        return questions[:5]  # Return max 5 questions
