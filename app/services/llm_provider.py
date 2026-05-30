"""OpenAI LLM provider with robust JSON parsing and fallback logic"""
import json
import logging
import os
import re
from typing import Optional, Dict, Any, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import (
    CANDIDATE_PROFILE_MODEL,
    CAREER_STRATEGY_MODEL,
    OPENAI_API_KEY,
    OPENAI_ENABLED,
    OPENAI_MAX_RETRIES,
    OPENAI_MODEL,
    OPENAI_TIMEOUT,
    RESUME_CRITIC_MODEL,
    RESUME_WRITER_MODEL,
    VACANCY_ANALYZER_MODEL,
)
from app.schemas.candidate import CandidateProfile
from app.schemas.vacancy import VacancyProfile
from app.schemas.strategy import StrategyBrief
from app.schemas.resume import TechnicalReport, GeneratedResume
from app.services.candidate_profile_stage import (
    build_follow_up_questions,
    detect_resume_sections,
    enrich_candidate_profile_with_sections,
    normalize_candidate_profile,
    parse_candidate_profile_section_text,
)
from app.services.vacancy_analyzer_stage import (
    normalize_vacancy_profile,
    parse_vacancy_section_text,
)
from app.services.career_strategy_stage import (
    build_fallback_strategy,
    build_strategy_context,
    normalize_strategy_brief,
    parse_career_strategy_section_text,
)
from app.services.resume_writer_stage import (
    build_deterministic_resume,
    build_resume_critic_context,
    build_resume_writer_context,
    finalize_generated_resume,
    parse_resume_critic_section_text,
    parse_resume_writer_section_text,
)
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

    @classmethod
    def render(cls, prompt_name: str, **kwargs) -> str:
        """Render prompt placeholders without interpreting JSON braces."""
        content = cls.load(prompt_name)
        for key, value in kwargs.items():
            content = content.replace(f"{{{key}}}", str(value))
        return content


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
        text = re.sub(
            r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)

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

    CANDIDATE_PROFILE_TEMPERATURE = 0.1
    CANDIDATE_PROFILE_MAX_OUTPUT_TOKENS = 1200
    CANDIDATE_PROFILE_SOFT_INPUT_BUDGET = 2500
    VACANCY_ANALYZER_TEMPERATURE = 0.1
    VACANCY_ANALYZER_MAX_OUTPUT_TOKENS = 800
    CAREER_STRATEGY_TEMPERATURE = 0.2
    CAREER_STRATEGY_MAX_OUTPUT_TOKENS = 1200
    RESUME_WRITER_TEMPERATURE = 0.25
    RESUME_WRITER_MAX_OUTPUT_TOKENS = 2200
    RESUME_CRITIC_TEMPERATURE = 0.1
    RESUME_CRITIC_MAX_OUTPUT_TOKENS = 900

    def __init__(self):
        self.name = "openai"
        self.enabled = OPENAI_ENABLED and bool(OPENAI_API_KEY)
        self.fallback = MockLLM()

        logger.info(
            "OpenAI Provider initialized: enabled=%s default_model=%s candidate_model=%s vacancy_model=%s "
            "strategy_model=%s writer_model=%s critic_model=%s",
            self.enabled,
            OPENAI_MODEL,
            CANDIDATE_PROFILE_MODEL,
            VACANCY_ANALYZER_MODEL,
            CAREER_STRATEGY_MODEL,
            RESUME_WRITER_MODEL,
            RESUME_CRITIC_MODEL,
        )

        if self.enabled:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=OPENAI_API_KEY)
                logger.info("✓ OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.enabled = False

    @retry(stop=stop_after_attempt(OPENAI_MAX_RETRIES), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_chat(
        self,
        messages: list,
        temperature: float = 0.3,
        model: Optional[str] = None,
        max_completion_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
        verbosity: Optional[str] = None,
    ) -> str:
        """Call OpenAI API with logging"""
        if not self.enabled:
            raise Exception("OpenAI API is not enabled")

        try:
            selected_model = model or OPENAI_MODEL
            logger.debug(
                "📡 OpenAI API call model=%s temperature=%s max_completion_tokens=%s reasoning_effort=%s verbosity=%s",
                selected_model,
                temperature,
                max_completion_tokens,
                reasoning_effort,
                verbosity,
            )
            request_kwargs = {
                "model": selected_model,
                "messages": messages,
                "temperature": temperature,
                "timeout": OPENAI_TIMEOUT,
            }
            if max_completion_tokens is not None:
                request_kwargs["max_completion_tokens"] = max_completion_tokens
            if reasoning_effort is not None:
                request_kwargs["reasoning_effort"] = reasoning_effort
            if verbosity is not None:
                request_kwargs["verbosity"] = verbosity

            response = self.client.chat.completions.create(**request_kwargs)
            content = response.choices[0].message.content.strip()
            logger.debug(
                f"✓ Response from {selected_model}: {len(content)} chars")
            return content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    @retry(stop=stop_after_attempt(OPENAI_MAX_RETRIES), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_response_text(
        self,
        *,
        instructions: str,
        input_text: str,
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> str:
        """Call Responses API and return text output."""
        if not self.enabled:
            raise Exception("OpenAI API is not enabled")

        try:
            logger.debug(
                "📡 OpenAI Responses API call model=%s temperature=%s max_output_tokens=%s",
                model,
                temperature,
                max_output_tokens,
            )
            response = self.client.responses.create(
                model=model,
                instructions=instructions,
                input=input_text,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                timeout=OPENAI_TIMEOUT,
            )
            if getattr(response, "error", None):
                raise Exception(str(response.error))
            content = (response.output_text or "").strip()
            logger.debug(
                f"✓ Responses API output from {model}: {len(content)} chars")
            return content
        except Exception as e:
            logger.error(f"OpenAI Responses API call failed: {e}")
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
        logger.debug(
            f"🔍 Parsing response ({context}): {response_text[:100]}...")

        # Try JSON parsing
        parsed_dict, repaired = JSONRepair.try_parse(
            response_text, schema_class)

        if parsed_dict:
            try:
                obj = schema_class(**parsed_dict)
                status = "repaired" if repaired else "clean"
                logger.info(f"✓ Parsed {context} ({status})")
                return obj, False
            except Exception as e:
                logger.warning(
                    f"Pydantic validation failed for {context}: {e}")

        logger.warning(f"Failed to parse {context} - using fallback")
        return None, True

    def parse_candidate_profile(self, resume_text: str) -> CandidateProfile:
        """Extract candidate profile from resume"""
        prepared = detect_resume_sections(
            resume_text,
            soft_input_budget=self.CANDIDATE_PROFILE_SOFT_INPUT_BUDGET,
        )

        if not self.enabled:
            logger.debug(
                "Using fallback: OpenAI disabled for CandidateProfile")
            fallback_profile = self.fallback.parse_candidate_profile(
                prepared.normalized_text)
            if prepared.was_truncated:
                fallback_profile.raw_warnings.append(
                    "CandidateProfile input was section-truncated before extraction")
            final_profile = normalize_candidate_profile(
                fallback_profile, prepared.normalized_text, prepared)
            final_profile = enrich_candidate_profile_with_sections(
                final_profile, prepared)
            logger.info(
                "CandidateProfile fallback used; confidence=%s ambiguities=%s",
                final_profile.confidence.model_dump(),
                final_profile.ambiguities,
            )
            return final_profile

        try:
            logger.info(
                "CandidateProfile stage config: model=%s temperature=%s max_output_tokens=%s soft_input_budget=%s truncated=%s",
                CANDIDATE_PROFILE_MODEL,
                self.CANDIDATE_PROFILE_TEMPERATURE,
                self.CANDIDATE_PROFILE_MAX_OUTPUT_TOKENS,
                self.CANDIDATE_PROFILE_SOFT_INPUT_BUDGET,
                prepared.was_truncated,
            )
            prompt = PromptLoader.render(
                "candidate_profile",
                section_preview=prepared.section_preview or "No sections detected",
                resume_text=prepared.llm_resume_text,
            )

            response = self._call_response_text(
                instructions="You are a resume parser. Extract information accurately without hallucinating. Return only the requested section-based text format, never JSON.",
                input_text=prompt,
                model=CANDIDATE_PROFILE_MODEL,
                temperature=self.CANDIDATE_PROFILE_TEMPERATURE,
                max_output_tokens=self.CANDIDATE_PROFILE_MAX_OUTPUT_TOKENS,
            )
            print(response)
            logger.debug("CandidateProfile raw section response: %s", response)
            parsed_profile = parse_candidate_profile_section_text(response)
            fallback_used = False

            if prepared.was_truncated:
                parsed_profile.raw_warnings.append(
                    "CandidateProfile input was section-truncated before extraction")

            final_profile = normalize_candidate_profile(
                parsed_profile, prepared.normalized_text, prepared)
            final_profile = enrich_candidate_profile_with_sections(
                final_profile, prepared)
            logger.debug("CandidateProfile parsed section profile: %s",
                         final_profile.model_dump())
            logger.info(
                "CandidateProfile completed fallback_used=%s confidence=%s ambiguities=%s follow_ups=%s",
                fallback_used,
                final_profile.confidence.model_dump(),
                final_profile.ambiguities,
                build_follow_up_questions(final_profile),
            )
            return final_profile

        except Exception as e:
            logger.error(f"Error in parse_candidate_profile: {e}")
            fallback_profile = self.fallback.parse_candidate_profile(
                prepared.normalized_text)
            final_profile = normalize_candidate_profile(
                fallback_profile, prepared.normalized_text, prepared)
            final_profile = enrich_candidate_profile_with_sections(
                final_profile, prepared)
            logger.info(
                "CandidateProfile exception fallback used; confidence=%s ambiguities=%s",
                final_profile.confidence.model_dump(),
                final_profile.ambiguities,
            )
            return final_profile

    def _validate_candidate_profile_response(self, response_text: Optional[str]) -> Optional[CandidateProfile]:
        if not response_text:
            logger.warning("CandidateProfile response is empty")
            return None

        logger.debug("CandidateProfile parsing attempt from response text")
        json_text = JSONRepair.extract_json_block(response_text)
        try:
            parsed_dict = json.loads(json_text)
        except json.JSONDecodeError as exc:
            logger.warning(
                "CandidateProfile JSON parse failed before repair: %s", exc)
            return None

        try:
            return CandidateProfile.model_validate(parsed_dict)
        except Exception as exc:
            logger.warning("CandidateProfile validation error: %s", exc)
            return None

    def _repair_candidate_profile_json(self, raw_response: str) -> str:
        repair_prompt = f"""Repair the following model output into valid JSON.

Rules:
- Return JSON only.
- Do not add any new facts.
- Preserve the same top-level keys:
  - canonical_profile
  - evidence
  - ambiguities
  - confidence
  - raw_warnings
- If a value cannot be recovered, use null, [] or {{}} as appropriate.

Broken response:
{raw_response}
"""

        return self._call_response_text(
            instructions="You repair malformed JSON. Return valid JSON only and never invent missing facts.",
            input_text=repair_prompt,
            model=CANDIDATE_PROFILE_MODEL,
            temperature=0.1,
            max_output_tokens=self.CANDIDATE_PROFILE_MAX_OUTPUT_TOKENS,
        )

    def parse_vacancy(self, vacancy_text: str) -> VacancyProfile:
        """Extract vacancy profile from job posting"""
        if not self.enabled:
            logger.debug("VacancyAnalyzer fallback used: OpenAI disabled")
            return normalize_vacancy_profile(self.fallback.parse_vacancy(vacancy_text), vacancy_text)

        try:
            prompt = PromptLoader.render(
                "vacancy_analyzer", vacancy_text=vacancy_text)

            logger.info(
                "VacancyAnalyzer stage config: provider=openai model=%s temperature=%s max_output_tokens=%s",
                VACANCY_ANALYZER_MODEL,
                self.VACANCY_ANALYZER_TEMPERATURE,
                self.VACANCY_ANALYZER_MAX_OUTPUT_TOKENS,
            )
            response = self._call_response_text(
                instructions="You are a job posting parser. Extract requirements accurately. Return only the requested section-based text format, never JSON.",
                input_text=prompt,
                model=VACANCY_ANALYZER_MODEL,
                temperature=self.VACANCY_ANALYZER_TEMPERATURE,
                max_output_tokens=self.VACANCY_ANALYZER_MAX_OUTPUT_TOKENS,
            )
            logger.debug("VacancyAnalyzer raw section response: %s", response)

            if not response.strip():
                logger.warning(
                    "VacancyAnalyzer fallback used: empty OpenAI section output")
                return normalize_vacancy_profile(self.fallback.parse_vacancy(vacancy_text), vacancy_text)

            parsed_profile = parse_vacancy_section_text(response)
            parsed_sections_count = len(re.findall(
                r"^\[[A-Z_]+\]\s*$", response, flags=re.MULTILINE))
            if parsed_sections_count == 0:
                logger.warning(
                    "VacancyAnalyzer fallback used: section output completely unparsable")
                return normalize_vacancy_profile(self.fallback.parse_vacancy(vacancy_text), vacancy_text)

            final_profile = normalize_vacancy_profile(
                parsed_profile, vacancy_text)
            logger.info(
                "VacancyAnalyzer completed fallback_used=false parsed_sections=%s role=%s must_have=%s warnings=%s",
                parsed_sections_count,
                final_profile.role,
                len(final_profile.must_have_skills),
                final_profile.raw_warnings,
            )
            return final_profile

        except Exception as e:
            logger.error(
                "VacancyAnalyzer fallback used after exception: %s", e)
            return normalize_vacancy_profile(self.fallback.parse_vacancy(vacancy_text), vacancy_text)

    def build_strategy(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        candidate_preferences: Optional[Dict[str, Any]] = None
    ) -> StrategyBrief:
        """Build LLM-driven career strategy from section-based output."""
        if not self.enabled:
            logger.debug("Using fallback: OpenAI disabled for CareerStrategy")
            return build_fallback_strategy(
                candidate_profile,
                vacancy_profile,
                candidate_preferences,
                reason="OpenAI disabled",
            )

        try:
            strategy_context = build_strategy_context(
                candidate_profile,
                vacancy_profile,
                candidate_preferences,
            )
            prompt = PromptLoader.render(
                "career_strategy",
                strategy_context=strategy_context,
            )

            logger.info(
                "CareerStrategy stage config: model=%s temperature=%s max_output_tokens=%s",
                CAREER_STRATEGY_MODEL,
                self.CAREER_STRATEGY_TEMPERATURE,
                self.CAREER_STRATEGY_MAX_OUTPUT_TOKENS,
            )
            response = self._call_response_text(
                instructions=(
                    "You are a career strategist. Build a focused, factual resume adaptation strategy. "
                    "Return only the requested section-based format."
                ),
                input_text=prompt,
                model=CAREER_STRATEGY_MODEL,
                temperature=self.CAREER_STRATEGY_TEMPERATURE,
                max_output_tokens=self.CAREER_STRATEGY_MAX_OUTPUT_TOKENS,
            )

            logger.debug("CareerStrategy raw section output:\n%s", response)
            if not response.strip():
                logger.warning(
                    "CareerStrategy fallback used: empty model output")
                return build_fallback_strategy(
                    candidate_profile,
                    vacancy_profile,
                    candidate_preferences,
                    reason="empty model output",
                )

            strategy, parsed_sections_count = parse_career_strategy_section_text(
                response,
                candidate_profile,
                vacancy_profile,
                candidate_preferences,
            )
            logger.info(
                "CareerStrategy parsed_sections=%s fallback_used=%s confidence=%s fit=%s support_fit=%s",
                parsed_sections_count,
                strategy.fallback_used,
                strategy.strategy_confidence,
                strategy.fit_score,
                strategy.support_fit_score,
            )
            if parsed_sections_count == 0:
                logger.warning(
                    "CareerStrategy fallback used: section output completely unparsable")
                return build_fallback_strategy(
                    candidate_profile,
                    vacancy_profile,
                    candidate_preferences,
                    reason="section output completely unparsable",
                )

            return normalize_strategy_brief(
                strategy,
                candidate_profile,
                vacancy_profile,
                candidate_preferences,
            )

        except Exception as e:
            logger.error(f"CareerStrategy fallback used after exception: {e}")
            return build_fallback_strategy(
                candidate_profile,
                vacancy_profile,
                candidate_preferences,
                reason=str(e),
            )

    def generate_resume(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        strategy_brief: StrategyBrief
    ) -> GeneratedResume:
        """Generate adapted resume with LLM writer and critic."""
        if not self.enabled:
            logger.debug(
                "Using deterministic resume fallback: OpenAI disabled")
            return build_deterministic_resume(
                candidate_profile,
                vacancy_profile,
                strategy_brief,
                reason="OpenAI disabled",
            )

        try:
            writer_context = build_resume_writer_context(
                candidate_profile, vacancy_profile, strategy_brief)
            writer_prompt = PromptLoader.render(
                "resume_writer",
                resume_writer_context=writer_context,
            )
            logger.info(
                "ResumeWriter stage config: model=%s temperature=%s max_output_tokens=%s",
                RESUME_WRITER_MODEL,
                self.RESUME_WRITER_TEMPERATURE,
                self.RESUME_WRITER_MAX_OUTPUT_TOKENS,
            )
            writer_response = self._call_response_text(
                instructions=(
                    "You are a grounded resume writer. Use only candidate facts and return "
                    "only the requested section-based format."
                ),
                input_text=writer_prompt,
                model=RESUME_WRITER_MODEL,
                temperature=self.RESUME_WRITER_TEMPERATURE,
                max_output_tokens=self.RESUME_WRITER_MAX_OUTPUT_TOKENS,
            )
            logger.debug("ResumeWriter raw section output:\n%s",
                         writer_response)
            if not writer_response.strip():
                logger.warning(
                    "ResumeWriter fallback used: empty writer output")
                return build_deterministic_resume(
                    candidate_profile,
                    vacancy_profile,
                    strategy_brief,
                    reason="empty writer output",
                )

            generated_resume, writer_warnings, parsed_sections = parse_resume_writer_section_text(
                writer_response)
            if parsed_sections == 0 or len(generated_resume.resume_text.strip()) < 80:
                logger.warning(
                    "ResumeWriter fallback used: unparsable writer output")
                return build_deterministic_resume(
                    candidate_profile,
                    vacancy_profile,
                    strategy_brief,
                    reason="unparsable writer output",
                )

            critic_report = None
            critic_fallback_used = False
            try:
                critic_context = build_resume_critic_context(
                    generated_resume,
                    candidate_profile,
                    vacancy_profile,
                    strategy_brief,
                )
                critic_prompt = PromptLoader.render(
                    "resume_critic",
                    resume_critic_context=critic_context,
                )
                logger.info(
                    "ResumeCritic stage config: model=%s temperature=%s max_output_tokens=%s",
                    RESUME_CRITIC_MODEL,
                    self.RESUME_CRITIC_TEMPERATURE,
                    self.RESUME_CRITIC_MAX_OUTPUT_TOKENS,
                )
                critic_response = self._call_response_text(
                    instructions=(
                        "You are a strict resume critic. Check the final resume against source facts, "
                        "vacancy requirements, and strategy. Return only the requested section-based format."
                    ),
                    input_text=critic_prompt,
                    model=RESUME_CRITIC_MODEL,
                    temperature=self.RESUME_CRITIC_TEMPERATURE,
                    max_output_tokens=self.RESUME_CRITIC_MAX_OUTPUT_TOKENS,
                )
                logger.debug(
                    "ResumeCritic raw section output:\n%s", critic_response)
                critic_report, critic_sections = parse_resume_critic_section_text(
                    critic_response)
                if critic_sections == 0:
                    critic_fallback_used = True
                    critic_report = None
            except Exception as critic_error:
                logger.warning(
                    "ResumeCritic fallback used after exception: %s", critic_error)
                critic_fallback_used = True

            return finalize_generated_resume(
                generated_resume,
                candidate_profile,
                vacancy_profile,
                strategy_brief,
                writer_warnings,
                writer_fallback_used=False,
                critic_report=critic_report,
                critic_fallback_used=critic_fallback_used,
            )

        except Exception as e:
            logger.error(f"ResumeWriter fallback used after exception: {e}")
            return build_deterministic_resume(
                candidate_profile,
                vacancy_profile,
                strategy_brief,
                reason=str(e),
            )


# Factory function
def get_llm_provider():
    """Get appropriate LLM provider"""
    return OpenAIProvider()
