"""OpenAI LLM provider with robust JSON parsing and fallback logic"""
import json
import logging
import os
import re
from typing import Optional, Dict, Any, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TIMEOUT, OPENAI_MAX_RETRIES, OPENAI_ENABLED
from app.schemas.candidate import CandidateProfile
from app.schemas.vacancy import VacancyProfile
from app.schemas.strategy import StrategyBrief
from app.schemas.resume import TechnicalReport, GeneratedResume
from app.services.mock_llm import MockLLM

logger = logging.getLogger(__name__)


class PromptLoader:
    """Load prompts from files"""
    
    _prompts_cache = {}
    
    @classmethod
    def load(cls, prompt_name: str) -> str:
        """Load prompt from file"""
        if prompt_name in cls._prompts_cache:
            return cls._prompts_cache[prompt_name]
        
        prompt_path = os.path.join(
            os.path.dirname(__file__), 
            "..", "prompts", 
            f"{prompt_name}.txt"
        )
        
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                cls._prompts_cache[prompt_name] = content
                return content
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {prompt_path}")
            return ""


class JSONRepair:
    """Helper for repairing and parsing JSON"""
    
    @staticmethod
    def strip_code_fences(text: str) -> str:
        """Remove markdown code fences"""
        # ```json ... ``` or ``` ... ```
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        return text.strip()
    
    @staticmethod
    def extract_json_block(text: str) -> Optional[str]:
        """Extract JSON block from text"""
        text = JSONRepair.strip_code_fences(text)
        
        # Try to find {...}
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)
        
        # Try to find [...]
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            return match.group(0)
        
        return text
    
    @staticmethod
    def basic_repair(text: str) -> str:
        """Attempt basic JSON repair"""
        # Remove trailing commas
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        
        # Fix unquoted keys
        text = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
        
        # Fix single quotes to double quotes (careful with apostrophes)
        text = re.sub(r"'([^']*)'", r'"\1"', text)
        
        return text
    
    @staticmethod
    def try_parse(text: str, schema_class=None) -> Tuple[Optional[Dict], bool]:
        """
        Try to parse JSON with repair attempts
        
        Returns: (parsed_dict, repaired_flag)
        """
        if not text:
            return None, False
        
        # Step 1: Extract JSON block
        text = JSONRepair.extract_json_block(text)
        
        # Step 2: Try direct parse
        try:
            return json.loads(text), False
        except json.JSONDecodeError as e:
            logger.debug(f"Initial JSON parse failed: {e}")
        
        # Step 3: Try basic repair
        repaired = JSONRepair.basic_repair(text)
        try:
            return json.loads(repaired), True
        except json.JSONDecodeError as e:
            logger.debug(f"Repair attempt failed: {e}")
        
        return None, False


class OpenAIProvider:
    """OpenAI LLM provider with robust fallback logic"""
    
    def __init__(self):
        self.name = "openai"
        self.enabled = OPENAI_ENABLED and bool(OPENAI_API_KEY)
        self.fallback = MockLLM()
        
        logger.info(f"OpenAI Provider initialized: enabled={self.enabled}, model={OPENAI_MODEL}")
        
        if self.enabled:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=OPENAI_API_KEY)
                logger.info("✓ OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.enabled = False
    
    @retry(stop=stop_after_attempt(OPENAI_MAX_RETRIES), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_chat(self, messages: list, temperature: float = 0.3) -> str:
        """Call OpenAI API with logging"""
        if not self.enabled:
            raise Exception("OpenAI API is not enabled")
        
        try:
            logger.debug(f"📡 OpenAI API call using model: {OPENAI_MODEL}")
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
                timeout=OPENAI_TIMEOUT,
            )
            content = response.choices[0].message.content.strip()
            logger.debug(f"✓ Response from {OPENAI_MODEL}: {len(content)} chars")
            return content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
    
    def _parse_with_fallback(
        self, 
        response_text: str, 
        schema_class,
        context: str = ""
    ) -> Tuple[Any, bool]:
        """
        Parse JSON response with fallback handling
        
        Returns: (parsed_object, used_fallback)
        """
        logger.debug(f"🔍 Parsing response ({context}): {response_text[:100]}...")
        
        # Try JSON parsing
        parsed_dict, repaired = JSONRepair.try_parse(response_text, schema_class)
        
        if parsed_dict:
            try:
                obj = schema_class(**parsed_dict)
                status = "repaired" if repaired else "clean"
                logger.info(f"✓ Parsed {context} ({status})")
                return obj, False
            except Exception as e:
                logger.warning(f"Pydantic validation failed for {context}: {e}")
        
        logger.warning(f"Failed to parse {context} - using fallback")
        return None, True
    
    def parse_candidate_profile(self, resume_text: str) -> CandidateProfile:
        """Extract candidate profile from resume"""
        if not self.enabled:
            logger.debug("Using fallback: OpenAI disabled")
            return self.fallback.parse_candidate_profile(resume_text)
        
        try:
            prompt = PromptLoader.load("candidate_profile").format(resume_text=resume_text)
            
            response = self._call_chat([
                {"role": "system", "content": "You are a resume parser. Extract information accurately without hallucinating."},
                {"role": "user", "content": prompt}
            ])
            
            obj, used_fallback = self._parse_with_fallback(response, CandidateProfile, "CandidateProfile")
            
            if obj:
                return obj
            else:
                return self.fallback.parse_candidate_profile(resume_text)
        
        except Exception as e:
            logger.error(f"Error in parse_candidate_profile: {e}")
            return self.fallback.parse_candidate_profile(resume_text)
    
    def parse_vacancy(self, vacancy_text: str) -> VacancyProfile:
        """Extract vacancy profile from job posting"""
        if not self.enabled:
            logger.debug("Using fallback: OpenAI disabled")
            return self.fallback.parse_vacancy(vacancy_text)
        
        try:
            prompt = PromptLoader.load("vacancy_analyzer").format(vacancy_text=vacancy_text)
            
            response = self._call_chat([
                {"role": "system", "content": "You are a job posting parser. Extract requirements accurately."},
                {"role": "user", "content": prompt}
            ])
            
            obj, used_fallback = self._parse_with_fallback(response, VacancyProfile, "VacancyProfile")
            
            if obj:
                return obj
            else:
                return self.fallback.parse_vacancy(vacancy_text)
        
        except Exception as e:
            logger.error(f"Error in parse_vacancy: {e}")
            return self.fallback.parse_vacancy(vacancy_text)
    
    def build_strategy(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        candidate_preferences: Optional[Dict[str, Any]] = None
    ) -> StrategyBrief:
        """Build career strategy"""
        if not self.enabled:
            logger.debug("Using fallback: OpenAI disabled")
            return self.fallback.build_strategy(candidate_profile, vacancy_profile, candidate_preferences)
        
        try:
            prompt_template = PromptLoader.load("career_strategy")
            prompt = prompt_template.format(
                experience_years=candidate_profile.experience_years or "N/A",
                target_role=candidate_profile.target_role or "N/A",
                candidate_skills=", ".join(candidate_profile.skills_hard[:10]),
                vacancy_role=vacancy_profile.role or "N/A",
                vacancy_seniority=vacancy_profile.seniority or "N/A",
                must_have_skills=", ".join(vacancy_profile.must_have_skills),
                nice_to_have_skills=", ".join(vacancy_profile.nice_to_have_skills),
                job_count=len(candidate_profile.jobs)
            )
            
            response = self._call_chat([
                {"role": "system", "content": "You are a career strategist. Be objective and honest."},
                {"role": "user", "content": prompt}
            ])
            
            obj, used_fallback = self._parse_with_fallback(response, StrategyBrief, "StrategyBrief")
            
            if obj:
                return obj
            else:
                return self.fallback.build_strategy(candidate_profile, vacancy_profile, candidate_preferences)
        
        except Exception as e:
            logger.error(f"Error in build_strategy: {e}")
            return self.fallback.build_strategy(candidate_profile, vacancy_profile, candidate_preferences)
    
    def generate_resume(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        strategy_brief: StrategyBrief
    ) -> GeneratedResume:
        """Generate adapted resume"""
        if not self.enabled:
            logger.debug("Using fallback: OpenAI disabled")
            return self.fallback.generate_resume(candidate_profile, vacancy_profile, strategy_brief)
        
        try:
            # Generate resume text
            prompt = f"""Write a professional resume based on candidate profile for a {vacancy_profile.role} position.
Use ONLY facts from the provided profile. Do not invent information.

Target role: {vacancy_profile.role}
Must highlight: {", ".join(strategy_brief.skills_to_highlight)}
Experience: {candidate_profile.experience_years} years
Key skills: {", ".join(candidate_profile.skills_hard[:10])}

Write professional resume text in 500 words max."""
            
            resume_text = self._call_chat([
                {"role": "system", "content": "You are a professional resume writer. Write only factual information from the provided profile."},
                {"role": "user", "content": prompt}
            ], temperature=0.5)
            
            # Generate technical report
            report_prompt_template = PromptLoader.load("resume_critic")
            report_prompt = report_prompt_template.format(
                must_have_skills=", ".join(vacancy_profile.must_have_skills),
                candidate_skills=", ".join(candidate_profile.skills_hard),
                candidate_jobs=len(candidate_profile.jobs)
            )
            
            report_response = self._call_chat([
                {"role": "system", "content": "You are a resume critic. Check for accuracy and completeness."},
                {"role": "user", "content": report_prompt}
            ])
            
            obj, used_fallback = self._parse_with_fallback(report_response, TechnicalReport, "TechnicalReport")
            
            if obj:
                report = obj
            else:
                report = TechnicalReport()
            
            return GeneratedResume(
                title=f"Resume for {vacancy_profile.role}",
                resume_text=resume_text,
                technical_report=report
            )
        
        except Exception as e:
            logger.error(f"Error in generate_resume: {e}")
            return self.fallback.generate_resume(candidate_profile, vacancy_profile, strategy_brief)


# Factory function
def get_llm_provider():
    """Get appropriate LLM provider"""
    return OpenAIProvider()
