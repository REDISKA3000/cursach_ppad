"""Mock LLM provider for demo mode"""
import json
import re
from typing import Optional, Dict, Any, List
from app.schemas.candidate import CandidateProfile, CandidateJob, EducationItem
from app.schemas.vacancy import VacancyProfile
from app.schemas.strategy import StrategyBrief
from app.schemas.resume import TechnicalReport, GeneratedResume
from app.services.profile_matching import analyze_candidate_fit

class MockLLM:
    """Mock LLM implementation for development and demo"""
    
    def __init__(self):
        self.name = "mock_llm"
    
    def parse_candidate_profile(self, resume_text: str) -> CandidateProfile:
        """Extract candidate profile from resume text using section-based parsing"""
        profile = CandidateProfile()

        normalized_text = self._normalize_resume_text(resume_text)

        if self._looks_like_hh_resume(normalized_text):
            sections = self._split_hh_resume_into_sections(normalized_text)
            profile.target_role = self._extract_hh_target_role(sections)
            profile.experience_years = self._extract_hh_experience_years(sections)
            profile.jobs = self._extract_hh_jobs(sections)
            profile.education = self._extract_hh_education(sections)
            profile.languages = self._extract_hh_languages(sections)
            profile.skills_hard, profile.skills_soft = self._extract_hh_skills(sections)

            if not profile.jobs:
                profile.raw_warnings.append("No jobs found in hh.ru resume")

            profile.raw_warnings.append("Profile extracted using hh.ru parsing")
            return profile
        
        # Split resume into sections by Russian markers
        sections = self._split_resume_into_sections(normalized_text)
        
        # Extract from sections
        profile.experience_years = self._extract_experience_years_v2(sections)
        profile.skills_hard, profile.skills_soft = self._extract_skills_v2(sections)
        profile.jobs = self._extract_jobs_v2(sections)
        profile.education = self._extract_education_v2(sections)
        profile.languages = self._extract_languages_v2(sections)
        profile.target_role = self._extract_target_role_v2(sections)
        
        if not profile.jobs:
            profile.raw_warnings.append("No jobs found in resume")
        
        profile.raw_warnings.append("Profile extracted using section-based parsing")
        return profile

    def _normalize_resume_text(self, text: str) -> str:
        """Normalize whitespace and strip recurring PDF footer noise."""
        if not text:
            return ""

        text = text.replace('\xa0', ' ')
        text = text.replace('\u200b', '')
        text = text.replace('\r', '\n')
        text = re.sub(r'Резюме обновлено.*?(?=\n|$)', '', text)
        text = re.sub(r'Гладилин Егор\s*•\s*', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _looks_like_hh_resume(self, text: str) -> bool:
        """Detect hh.ru-style resume exports."""
        markers = [
            'Желаемая должность и зарплата',
            'Специализации:',
            'Опыт работы',
            'Образование',
            'Навыки',
        ]
        return sum(1 for marker in markers if marker in text) >= 4

    def _split_hh_resume_into_sections(self, text: str) -> Dict[str, str]:
        """Split hh.ru resume into main sections."""
        markers = [
            ('desired', 'Желаемая должность и зарплата'),
            ('experience', 'Опыт работы'),
            ('education', 'Образование'),
            ('skills', 'Навыки'),
        ]

        positions = []
        for key, label in markers:
            match = re.search(re.escape(label), text)
            if match:
                positions.append((key, match.start(), label))

        positions.sort(key=lambda item: item[1])

        sections = {
            'header': text,
            'desired': '',
            'experience': '',
            'education': '',
            'skills': '',
        }

        if not positions:
            return sections

        sections['header'] = text[:positions[0][1]].strip()

        for index, (key, start, label) in enumerate(positions):
            end = positions[index + 1][1] if index + 1 < len(positions) else len(text)
            sections[key] = text[start:end].strip()

        return sections

    def _clean_hh_lines(self, text: str) -> List[str]:
        """Normalize hh.ru section lines."""
        lines = []
        for raw_line in text.split('\n'):
            line = re.sub(r'\s+', ' ', raw_line).strip()
            if not line:
                continue
            if 'Резюме обновлено' in line:
                continue
            lines.append(line)
        return lines

    def _extract_hh_target_role(self, sections: Dict[str, str]) -> Optional[str]:
        """Extract desired role from hh.ru desired position block."""
        desired_lines = self._clean_hh_lines(sections.get('desired', ''))
        for line in desired_lines:
            if line == 'Желаемая должность и зарплата':
                continue
            if line.startswith('Специализации'):
                break
            if line.startswith('— '):
                continue
            if line.startswith('Тип занятости') or line.startswith('Формат работы'):
                continue
            if line.startswith('Желательное время'):
                continue
            if re.search(r'₽|\$\s*|€', line):
                continue
            return line
        return None

    def _extract_hh_experience_years(self, sections: Dict[str, str]) -> Optional[int]:
        """Extract total work experience from hh.ru experience header."""
        experience_text = sections.get('experience', '')
        match = re.search(
            r'Опыт работы\s*[—-]\s*(\d+)\s*(?:год|года|лет)(?:\s+(\d+)\s*(?:месяц|месяца|месяцев))?',
            experience_text,
            re.IGNORECASE,
        )
        if match:
            years = int(match.group(1))
            months = int(match.group(2) or 0)
            return years + (1 if months >= 6 else 0)

        date_ranges = re.findall(r'(\d{4})[–\-](\d{4})', experience_text)
        if date_ranges:
            return max(int(end) - int(start) for start, end in date_ranges)

        return None

    def _extract_hh_jobs(self, sections: Dict[str, str]) -> List[CandidateJob]:
        """Extract job blocks from hh.ru experience section."""
        lines = self._clean_hh_lines(sections.get('experience', ''))
        if lines and lines[0].startswith('Опыт работы'):
            lines = lines[1:]

        prepared_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r'^[А-Яа-яA-Za-z]+\s+\d{4}\s*[—-]$', line) and i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line == 'настоящее время' or re.match(r'^[А-Яа-яA-Za-z]+\s+\d{4}$', next_line):
                    prepared_lines.append(f"{line} {next_line}")
                    i += 2
                    continue
            prepared_lines.append(line)
            i += 1

        jobs = []
        job_id = 1
        i = 0
        while i < len(prepared_lines):
            if not self._is_hh_period_line(prepared_lines[i]):
                i += 1
                continue

            period = prepared_lines[i]
            i += 1
            duration = None
            if i < len(prepared_lines) and self._is_duration_line(prepared_lines[i]):
                duration = prepared_lines[i]
                i += 1

            block = []
            while i < len(prepared_lines) and not self._is_hh_period_line(prepared_lines[i]):
                block.append(prepared_lines[i])
                i += 1

            job = self._build_hh_job(job_id, period, duration, block)
            if job:
                jobs.append(job)
                job_id += 1

        return jobs

    def _is_hh_period_line(self, line: str) -> bool:
        """Check hh.ru style period line."""
        return bool(re.match(
            r'^(?:[А-Яа-яA-Za-z]+)\s+\d{4}\s*[—-]\s*(?:настоящее время|[А-Яа-яA-Za-z]+\s+\d{4})$',
            line
        ))

    def _is_duration_line(self, line: str) -> bool:
        """Check hh.ru duration line like '1 год 7 месяцев'."""
        return bool(re.match(r'^\d+\s+(?:год|года|лет|месяц|месяца|месяцев)', line))

    def _is_hh_meta_noise(self, line: str) -> bool:
        """Filter location, site and industry lines from hh job headers."""
        line_lower = line.lower()
        noise_markers = [
            'www.',
            'финансовый сектор',
            'розничная торговля',
            'электроника',
            'интернет-магазин',
            'бытовая техника',
            'климатическое оборудование',
            'москва',
        ]
        return line.startswith('•') or any(marker in line_lower for marker in noise_markers)

    def _looks_like_role_line(self, line: str) -> bool:
        """Detect likely position names."""
        role_markers = [
            'аналитик', 'manager', 'scientist', 'engineer', 'developer',
            'product', 'risk', 'data', 'bi-', 'риск', 'стажер', 'intern'
        ]
        line_lower = line.lower()
        return any(marker in line_lower for marker in role_markers)

    def _build_hh_job(
        self,
        job_id: int,
        period: str,
        duration: Optional[str],
        block: List[str],
    ) -> Optional[CandidateJob]:
        """Build CandidateJob from hh.ru job block."""
        block = [line for line in block if 'Резюме обновлено' not in line]
        if not block:
            return None

        company_name = block[0]
        first_bullet_index = next((idx for idx, line in enumerate(block) if line.startswith('-')), len(block))
        meta_lines = block[1:first_bullet_index]
        bullet_lines = block[first_bullet_index:]

        position_candidates = [line for line in meta_lines if not self._is_hh_meta_noise(line) and self._looks_like_role_line(line)]
        position = position_candidates[-1] if position_candidates else None

        if not position:
            fallback_candidates = [line for line in meta_lines if not self._is_hh_meta_noise(line)]
            position = fallback_candidates[-1] if fallback_candidates else None

        responsibilities = []
        for line in bullet_lines:
            if line.startswith('-') or line.startswith('•'):
                responsibilities.append(line.lstrip('-• ').strip())
            elif responsibilities:
                responsibilities[-1] = f"{responsibilities[-1]} {line}".strip()

        if not responsibilities and len(block) > 1:
            responsibilities = [line for line in block[1:] if not self._is_hh_meta_noise(line)]

        job = CandidateJob(
            id=job_id,
            company_name=company_name,
            position=position,
            period=f"{period} ({duration})" if duration else period,
            responsibilities=responsibilities[:8],
            achievements=[],
            skills_used=[],
        )
        return job if job.company_name or job.position else None

    def _extract_hh_education(self, sections: Dict[str, str]) -> List[EducationItem]:
        """Extract education blocks from hh.ru education section."""
        lines = self._clean_hh_lines(sections.get('education', ''))
        if lines and lines[0] == 'Образование':
            lines = lines[1:]

        education = []
        i = 0
        while i < len(lines):
            if not re.fullmatch(r'(19|20)\d{2}', lines[i]):
                i += 1
                continue

            year = lines[i]
            i += 1
            block = []
            while i < len(lines) and not re.fullmatch(r'(19|20)\d{2}', lines[i]):
                block.append(lines[i])
                i += 1

            if not block:
                continue

            institution_index = next((idx for idx, line in enumerate(block) if len(line) > 12), 0)
            institution = block[institution_index]

            if institution_index + 1 < len(block):
                next_line = block[institution_index + 1]
                if (
                    institution.endswith('школа')
                    or institution.endswith('School')
                    or next_line[:1].islower()
                ):
                    institution = f"{institution} {next_line}".strip()
                    block.pop(institution_index + 1)

            degree_parts = [line for idx, line in enumerate(block) if idx != institution_index]
            education.append(EducationItem(
                institution=institution,
                degree=", ".join(degree_parts) if degree_parts else None,
                year=year,
            ))

        return education

    def _extract_hh_languages(self, sections: Dict[str, str]) -> List[str]:
        """Extract languages from hh.ru skills section."""
        skills_text = sections.get('skills', '')
        languages = []
        patterns = [
            (r'русский\s+—', 'Русский'),
            (r'английский\s+—', 'Английский'),
            (r'german\s+—|немецкий\s+—', 'Немецкий'),
            (r'french\s+—|французский\s+—', 'Французский'),
            (r'spanish\s+—|испанский\s+—', 'Испанский'),
        ]

        lowered = skills_text.lower()
        for pattern, language in patterns:
            if re.search(pattern, lowered) and language not in languages:
                languages.append(language)

        return languages

    def _extract_hh_skills(self, sections: Dict[str, str]) -> tuple:
        """Extract explicit and inferred skills from hh.ru skills section."""
        hard_skills = []
        soft_skills = []

        raw_skills = sections.get('skills', '')
        explicit_text = raw_skills.split('Навыки', 1)[1] if 'Навыки' in raw_skills else raw_skills
        expanded_tokens = []
        for token in re.split(r'\s{2,}|\n', explicit_text.replace('\xa0', ' ')):
            token = token.strip(' -•\t')
            if not token:
                continue
            if '\n' in token or len(token) > 90:
                expanded_tokens.extend(
                    part.strip(' -•\t')
                    for part in re.split(r'\n| {2,}', token)
                    if part.strip(' -•\t')
                )
            else:
                expanded_tokens.append(token)

        tokens = expanded_tokens

        seen = set()
        for token in tokens:
            token = re.sub(r'\s+', ' ', token).strip(' -•\t')
            if not token:
                continue
            token_lower = token.lower()
            if '—' in token and re.search(r'родной|[abc]\d', token_lower):
                continue
            if token_lower in {'знание языков', 'навыки'}:
                continue
            if 'язык' in token_lower:
                continue
            if '\n' in token or len(token) > 80:
                continue
            if token_lower.startswith('навыки ') or token_lower.startswith('знание языков'):
                continue
            if 'русский' in token_lower and 'английский' in token_lower:
                continue
            if token_lower.count(' ') > 8:
                continue
            if token_lower not in seen:
                hard_skills.append(token)
                seen.add(token_lower)

        generic_hard, generic_soft = self._extract_skills_v2({
            'header': sections.get('header', ''),
            'experience': sections.get('experience', ''),
            'skills': raw_skills,
            'education': sections.get('education', ''),
            'languages': '',
            'other': '',
        })

        for skill in generic_hard:
            skill_lower = skill.lower()
            if skill_lower not in seen:
                hard_skills.append(skill)
                seen.add(skill_lower)

        for skill in generic_soft:
            if skill.lower() not in {s.lower() for s in soft_skills}:
                soft_skills.append(skill)

        return hard_skills, soft_skills
    
    def _split_resume_into_sections(self, text: str) -> Dict[str, str]:
        """Split resume by Russian section markers"""
        sections = {
            'header': '',
            'experience': '',
            'skills': '',
            'education': '',
            'languages': '',
            'other': ''
        }
        
        lines = text.split('\n')
        current_section = 'header'
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Skip section header lines themselves
            if any(x in line_lower for x in ['опыт работы', 'work experience', 'профессиональный опыт']):
                current_section = 'experience'
                continue
            elif any(x in line_lower for x in ['навыки:', 'skill', 'ключевые навыки', 'компетенции']):
                current_section = 'skills'
                continue
            elif any(x in line_lower for x in ['образование:', 'education', 'учебное']):
                current_section = 'education'
                continue
            elif any(x in line_lower for x in ['язык', 'language', 'иностранные']):
                current_section = 'languages'
                continue
            
            # Accumulate line in current section
            sections[current_section] += line + '\n'
        
        return sections
    
    def _extract_experience_years_v2(self, sections: Dict[str, str]) -> Optional[int]:
        """Extract experience years from header + experience sections"""
        text = sections['experience'] or sections['header']

        explicit_match = re.search(r'опыт[^.\n:]{0,40}(\d+)\s*(?:лет|года|год)', text, re.IGNORECASE)
        if explicit_match:
            return int(explicit_match.group(1))
        
        # Pattern 1: "5 лет"
        match = re.search(r'(\d+)\s*(?:лет|год|years?)', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Pattern 2: Date ranges "2019-2024"
        matches = re.findall(r'(\d{4})[–\-](\d{4})', text)
        if matches:
            years = [int(m[1]) - int(m[0]) for m in matches]
            return max(years) if years else None
        
        return None
    
    def _extract_skills_v2(self, sections: Dict[str, str]) -> tuple:
        """Extract skills from dedicated section + experience"""
        hard_skills = []
        soft_skills = []
        
        skills_text = sections['skills'] + '\n' + sections['experience']
        text_lower = skills_text.lower()
        
        # Comprehensive keyword matching with case-insensitive deduplication
        tech_keywords = {
            'sql': 'SQL',
            'a/b': 'A/B-тестирование', 'a/b-тест': 'A/B-тестирование', 'ab-test': 'A/B-тестирование',
            'аналитика': 'Продуктовая аналитика', 'аналитик': 'Продуктовая аналитика',
            'юнит-экономика': 'Юнит-экономика', 'юнит экономика': 'Юнит-экономика',
            'метрика': 'Продуктовая аналитика',
            'cjm': 'CJM', 'customer journey': 'CJM',
            'backlog': 'Backlog management', 'бэклог': 'Backlog management',
            'growth': 'Growth', 'грас': 'Growth',
            'retention': 'Retention', 'ретеншн': 'Retention',
            'monetization': 'Монетизация', 'монетизация': 'Монетизация',
            'onboarding': 'Onboarding', 'онбординг': 'Onboarding',
            'product strategy': 'Product Strategy', 'стратегия продукта': 'Product Strategy',
            'product manager': 'Product Manager', 'product owner': 'Product Owner',
            'python': 'Python', 'javascript': 'JavaScript', 'react': 'React',
            'aws': 'AWS', 'docker': 'Docker', 'kubernetes': 'Kubernetes'
        }
        
        # Extract skills with case-insensitive deduplication
        found_skills_lower = set()
        for keyword, skill_name in tech_keywords.items():
            if keyword in text_lower:
                skill_lower = skill_name.lower()
                if skill_lower not in found_skills_lower:
                    hard_skills.append(skill_name)
                    found_skills_lower.add(skill_lower)
        
        # Explicit skills section parsing
        skills_section = sections['skills']
        if skills_section:
            for line in skills_section.split(','):
                skill = re.sub(r'\s+', ' ', line).strip()
                if (
                    len(skill) >= 2
                    and len(skill) <= 80
                    and 'знание языков' not in skill.lower()
                    and not skill.lower().startswith('навыки')
                    and 'русский' not in skill.lower()
                    and 'английский' not in skill.lower()
                ):
                    skill_lower = skill.lower()
                    if skill_lower not in found_skills_lower:
                        hard_skills.append(skill)
                        found_skills_lower.add(skill_lower)
        
        # Soft skills - also deduplicated
        soft_keywords = {
            'коммуникация': 'Коммуникация',
            'лидерство': 'Лидерство',
            'teamwork': 'Командная работа',
            'аналитическое': 'Аналитическое мышление'
        }
        
        found_soft_lower = set()
        for keyword, skill_name in soft_keywords.items():
            if keyword in text_lower:
                skill_lower = skill_name.lower()
                if skill_lower not in found_soft_lower and skill_lower != 'аналит':
                    soft_skills.append(skill_name)
                    found_soft_lower.add(skill_lower)
        
        return hard_skills, soft_skills
    
    def _extract_jobs_v2(self, sections: Dict[str, str]) -> List:
        """Extract jobs from experience section"""
        jobs = []
        exp_text = sections['experience']
        lines = [l.strip() for l in exp_text.split('\n') if l.strip()]
        
        current_job = None
        job_id = 0
        pending_company = None  # Hold company name from previous line
        
        i = 0
        while i < len(lines):
            line = lines[i]
            line_lower = line.lower()
            
            company_keywords = ['т-банк', 'tcs', 'ozon', 'яндекс', 'google', 'sber', 'vk', 'mail', 'avito']
            job_titles = ['product manager', 'senior product', 'head of', 'manager', 'engineer', 'developer']
            achievement_verbs = ['запустил', 'разработал', 'провел', 'создал', 'увеличил', 'улучшил']
            
            is_company_line = any(kw in line_lower for kw in company_keywords)
            is_position_line = any(jt in line_lower for jt in job_titles) and not any(line_lower.startswith(v) for v in achievement_verbs)
            is_period = self._is_period_line(line)
            
            if is_company_line:
                # Save previous job
                if current_job and (current_job.responsibilities or current_job.achievements):
                    jobs.append(current_job)
                
                job_id += 1
                current_job = CandidateJob(id=job_id)
                
                # Parse company and position if comma-separated
                if ',' in line:
                    parts = line.split(',')
                    current_job.company_name = parts[0].strip()
                    current_job.position = parts[1].strip() if len(parts) > 1 else None
                else:
                    current_job.company_name = line
                    pending_company = line
            
            elif is_position_line and current_job:
                # Position line following company
                current_job.position = line
                pending_company = None
            
            elif is_period and current_job:
                # Period line
                current_job.period = line
            
            elif current_job and (line.startswith('-') or line.startswith('•')):
                # Bullet point
                text = line.lstrip('-•* ').strip()
                if len(text) > 5:
                    if len(text) > 60 or any(x in text.lower() for x in ['разви', 'провод', 'работ', 'отвеч', 'взаимодейств', 'форм', 'управ', 'запус']):
                        current_job.responsibilities.append(text)
                    else:
                        current_job.achievements.append(text)
            
            i += 1
        
        # Save last job
        if current_job and (current_job.responsibilities or current_job.achievements):
            jobs.append(current_job)
        
        return jobs
    
    def _extract_education_v2(self, sections: Dict[str, str]) -> List:
        """Extract education - only valid entries"""
        education = []
        edu_text = sections['education']
        
        # Look for pattern: "University, Degree, Field, Year"
        lines = [l.strip() for l in edu_text.split('\n') if l.strip() and len(l.strip()) > 10]
        
        for line in lines:
            # Look for year pattern
            year_match = re.search(r'\b(19|20)\d{2}\b', line)
            
            # If has year and reasonable length, treat as education entry
            if year_match:
                edu = EducationItem()
                
                # Try to parse institution and degree
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                    edu.institution = parts[0]
                    if len(parts) > 1:
                        edu.degree = parts[1]
                    if len(parts) > 2:
                        edu.year = parts[2]
                else:
                    edu.institution = line
                    edu.year = year_match.group()
                
                education.append(edu)
        
        return education
    
    def _extract_languages_v2(self, sections: Dict[str, str]) -> List[str]:
        """Extract languages from dedicated section"""
        lang_text = (sections['languages'] + ' ' + sections['header']).lower()
        languages = []
        
        # Known language patterns - with multiple aliases
        language_patterns = [
            (['русск', 'russian'], 'Русский'),
            (['english', 'англ'], 'Английский'),
            (['deutsch', 'немец'], 'Немецкий'),
            (['français', 'franç', 'франц'], 'Французский'),
            (['испан', 'spanish'], 'Испанский'),
            (['итал', 'italian'], 'Итальянский'),
            (['китай', 'chinese'], 'Китайский'),
            (['японск', 'japanese'], 'Японский'),
        ]
        
        found = set()
        for patterns, lang_name in language_patterns:
            for pattern in patterns:
                if pattern in lang_text:
                    if lang_name.lower() not in found:
                        languages.append(lang_name)
                        found.add(lang_name.lower())
                    break
        
        return languages
    
    def _extract_target_role_v2(self, sections: Dict[str, str]) -> Optional[str]:
        """Extract target role from header section"""
        header = sections['header']
        
        # Look for lines containing role keywords
        for line in header.split('\n'):
            line_strip = line.strip()
            if not line_strip or len(line_strip) < 5:
                continue
            
            # Skip company names
            if any(x in line_strip.lower() for x in ['банк', 'ozon', 'яндекс', 'google']):
                continue
            
            # Check for role keywords
            if any(x in line_strip.lower() for x in ['product manager', 'manager', 'engineer', 'developer', 'менеджер']):
                # Remove section markers if present
                line_clean = line_strip.replace('ПРОФЕССИОНАЛЬНАЯ ЦЕЛЬ:', '').replace('CAREER GOAL:', '').strip()
                line_clean = line_clean.replace('ДОЛЖНОСТЬ:', '').replace('POSITION:', '').strip()
                if ':' in line_clean:
                    line_clean = line_clean.split(':', 1)[1].strip()
                return line_clean if line_clean else line_strip
        
        return None
    
    def _is_period_line(self, line: str) -> bool:
        """Check if line is a period (2019-2024 or 2019–2024)"""
        return bool(re.search(r'\d{4}[–\-]\d{4}', line))
    
    def parse_vacancy_profile(self, vacancy_text: str) -> VacancyProfile:
        """Extract vacancy profile with section-based parsing"""
        profile = VacancyProfile()

        vacancy_text = self._normalize_vacancy_text(vacancy_text)
        
        # Split vacancy into sections
        sections = self._split_vacancy_into_sections(vacancy_text)
        
        # Extract basic info
        profile.role = self._extract_vacancy_role(sections)
        profile.seniority = self._extract_seniority(sections)
        profile.industry = self._extract_industry(sections)
        
        # Extract skills
        profile.must_have_skills = self._extract_must_have_skills(sections)
        profile.nice_to_have_skills = self._extract_nice_to_have_skills(sections)
        
        # Extract responsibilities
        profile.key_responsibilities = self._extract_key_responsibilities(sections)
        profile.keywords_for_ats = self._extract_vacancy_keywords(
            profile.role,
            profile.must_have_skills,
            profile.nice_to_have_skills,
            profile.key_responsibilities,
        )
        
        return profile
    
    def parse_vacancy(self, vacancy_text: str) -> VacancyProfile:
        """Alias for parse_vacancy_profile for API compatibility"""
        return self.parse_vacancy_profile(vacancy_text)

    def _normalize_vacancy_text(self, text: str) -> str:
        """Normalize whitespace in vacancy text."""
        if not text:
            return ""

        text = text.replace('\xa0', ' ')
        text = text.replace('\u200b', '')
        text = text.replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _clean_vacancy_lines(self, text: str) -> List[str]:
        """Return non-empty normalized vacancy lines."""
        return [
            re.sub(r'\s+', ' ', line).strip()
            for line in text.split('\n')
            if re.sub(r'\s+', ' ', line).strip()
        ]
    
    def _split_vacancy_into_sections(self, text: str) -> Dict[str, str]:
        """Split vacancy into common job-posting sections."""
        sections = {
            'header': '',
            'offer': '',
            'requirements': '',
            'responsibilities': '',
            'nice_to_have': '',
            'other': ''
        }
        
        lines = self._clean_vacancy_lines(text)
        current_section = 'header'
        
        for line in lines:
            line_lower = line.lower().strip(' :')
            
            if (
                line_lower in {'что мы предлагаем', 'мы предлагаем', 'условия'}
                or line_lower.startswith('what we offer')
            ):
                current_section = 'offer'
                continue
            if (
                line_lower in {
                    'наши пожелания к кандидатам',
                    'требования',
                    'требования к кандидатам',
                    'требования к кандидату',
                    'что ожидаем',
                    'мы ожидаем',
                    'что важно для нас',
                    'наши ожидания',
                    'наши пожелания',
                    'вам подойдет вакансия, если у вас есть',
                    'ты точно справишься, если',
                    'пожелания к кандидатам',
                    'requirements',
                    'must have',
                    'must-have',
                    'ключевые навыки',
                }
                or line_lower.startswith('requirements')
            ):
                current_section = 'requirements'
                continue
            elif (
                line_lower in {
                    'чем предстоит заниматься',
                    'чем нужно заниматься',
                    'задачи',
                    'обязанности',
                    'ключевые задачи',
                    'вам предстоит заниматься',
                    'тебе предстоит',
                    'что предстоит делать',
                    'о чем эта роль',
                }
                or line_lower.startswith('responsibil')
                or line_lower.startswith('duties')
                or line_lower.startswith('ответствен')
            ):
                current_section = 'responsibilities'
                continue
            elif (
                line_lower in {
                    'будет плюсом',
                    'будет преимуществом',
                    'nice-to-have',
                    'nice to have',
                    'желательно',
                    'как преимущество',
                }
                or line_lower.startswith('advantage')
            ):
                current_section = 'nice_to_have'
                continue
            
            sections[current_section] += line + '\n'
        
        return sections
    
    def _extract_vacancy_role(self, sections: Dict[str, str]) -> Optional[str]:
        """Extract job role from header"""
        header_lines = self._clean_vacancy_lines(sections['header'])
        skip_markers = [
            '₽', '$', '€', 'опыт работы', 'полная занятость', 'частичная занятость',
            'график', 'рабочие часы', 'формат работы', 'удалённо', 'удаленно',
        ]

        for line in header_lines[:8]:
            cleaned = line.replace('Вакансия:', '').replace('VACANCY:', '').strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if any(marker in lowered for marker in skip_markers):
                continue
            if 'сейчас эту вакансию смотрят' in lowered:
                continue
            return cleaned

        return header_lines[0] if header_lines else None
    
    def _extract_seniority(self, sections: Dict[str, str]) -> Optional[str]:
        """Extract seniority level"""
        text = sections['header'] + ' ' + sections['requirements']
        seniority_keywords = {
            'senior': 'Senior',
            'старший': 'Senior',
            'middle': 'Middle',
            'миддл': 'Middle',
            'junior': 'Junior',
            'джун': 'Junior',
        }
        
        for keyword, level in seniority_keywords.items():
            if keyword in text.lower():
                return level

        years_match = re.search(r'опыт работы:\s*(\d+)\s*[–-]\s*(\d+)\s*г', text.lower())
        if years_match:
            min_years = int(years_match.group(1))
            max_years = int(years_match.group(2))
            if max_years <= 2:
                return 'Junior'
            if min_years <= 1 and max_years <= 4:
                return 'Middle'
            if max_years >= 5:
                return 'Senior'
        return None
    
    def _extract_industry(self, sections: Dict[str, str]) -> Optional[str]:
        """Extract industry from header/requirements"""
        text = (sections['header'] + ' ' + sections['requirements'] + ' ' + sections.get('offer', '')).lower()
        industry_keywords = {
            'финтех': 'FinTech',
            'fintech': 'FinTech',
            'банк': 'Banking',
            'банка': 'Banking',
            'банков': 'Banking',
            'банковск': 'Banking',
            'платеж': 'Payments',
            'e-commerce': 'E-commerce',
            'tech': 'Technology',
            'saas': 'SaaS',
            'retail': 'Retail',
        }
        
        for keyword, industry in industry_keywords.items():
            if keyword in text:
                return industry
        return None
    
    def _extract_must_have_skills(self, sections: Dict[str, str]) -> List[str]:
        """Extract must-have skills from requirements section"""
        req_text = sections['requirements']
        skills = []
        found_skills = set()

        for line in self._clean_vacancy_lines(req_text):
            for item in self._extract_skill_candidates_from_line(line):
                lowered = item.lower()
                if lowered not in found_skills:
                    skills.append(item)
                    found_skills.add(lowered)
        
        return skills
    
    def _extract_nice_to_have_skills(self, sections: Dict[str, str]) -> List[str]:
        """Extract nice-to-have skills"""
        skills = []
        found_skills = set()
        for line in self._clean_vacancy_lines(sections['nice_to_have']):
            for item in self._extract_skill_candidates_from_line(line):
                lowered = item.lower()
                if lowered not in found_skills:
                    skills.append(item)
                    found_skills.add(lowered)
        
        return skills
    
    def _extract_key_responsibilities(self, sections: Dict[str, str]) -> List[str]:
        """Extract key responsibilities"""
        responsibilities = []
        current_item = None

        for line in self._clean_vacancy_lines(sections['responsibilities']):
            clean = line.lstrip('—–-•* ').strip()
            if len(clean) < 4:
                continue
            if line.startswith(('—', '–', '-', '•')) or clean[:1].isupper():
                if current_item:
                    responsibilities.append(current_item)
                current_item = clean
            elif current_item:
                current_item = f"{current_item} {clean}".strip()
            else:
                current_item = clean

        if current_item:
            responsibilities.append(current_item)
        
        return responsibilities if responsibilities else []

    def _extract_skill_candidates_from_line(self, line: str) -> List[str]:
        """Extract requirement phrases generically instead of via fixed entity maps."""
        clean = re.sub(r'\s+', ' ', line).strip().lstrip('—–-•* ').strip()
        if not clean:
            return []

        candidates = []
        seen = set()

        def add(value: str):
            normalized = self._normalize_candidate_term(value)
            if not normalized:
                return
            lowered = normalized.lower()
            if lowered not in seen:
                candidates.append(normalized)
                seen.add(lowered)

        for part in re.findall(r'\(([^)]+)\)', clean):
            for token in self._split_candidate_terms(part):
                add(token)

        main_text = re.sub(r'\([^)]*\)', '', clean).strip()
        if ':' in main_text:
            left, right = main_text.split(':', 1)
            if len(left.split()) <= 4:
                main_text = right.strip() or main_text

        stripped = self._strip_requirement_prefix(main_text)
        for token in self._split_candidate_terms(stripped):
            add(token)

        latin_terms = re.findall(
            r'\b(?:[A-Za-z][A-Za-z0-9.+#-]*)(?:\s+[A-Za-z][A-Za-z0-9.+#-]*)*\b',
            clean,
        )
        for token in latin_terms:
            if len(token) >= 2:
                add(token)

        if not candidates and 3 <= len(stripped) <= 140:
            add(stripped)

        return candidates

    def _strip_requirement_prefix(self, text: str) -> str:
        """Remove generic lead-in phrases while preserving the actual requirement."""
        patterns = [
            r'^(?:обязательны|обязательно)\s+',
            r'^(?:знание|знания)\s+',
            r'^(?:умение|уметь)\s+',
            r'^(?:навык|навыки)\s+',
            r'^(?:опыт работы с|опыт работы именно в роли|опыт работы именно в области|опыт работы в|опыт в)\s+',
            r'^(?:понимание|понимать)\s+',
            r'^(?:уверенное владение|уверенно владеть|уверенно владеешь|владение)\s+',
            r'^(?:способность)\s+',
            r'^(?:работаешь в|имеешь опыт работы с|имеешь опыт|умеешь)\s+',
            r'^(?:теоретические знания)\s+',
            r'^(?:отлично знаешь|хорошо понимаешь|уверенно владеешь)\s+',
            r'^(?:того,\s*как устроены)\s+',
        ]

        stripped = text.strip(' .;')
        for pattern in patterns:
            stripped = re.sub(pattern, '', stripped, flags=re.IGNORECASE).strip(' .;')
        return stripped

    def _split_candidate_terms(self, text: str) -> List[str]:
        """Split a requirement line into reusable skill/competency phrases."""
        text = text.strip(' .;')
        if not text:
            return []

        text = re.sub(r'\s+', ' ', text)
        parts = re.split(r',|/|;| либо | или ', text)
        candidates = []

        for part in parts:
            item = part.strip(' .;')
            if not item:
                continue
            if item.lower() in {'и', 'др', 'и др', 'пр', 'т.д', 'т.з'}:
                continue
            if self._is_noise_candidate(item):
                continue
            candidates.append(item)

        if len(candidates) <= 1 and ' и ' in text:
            and_parts = [part.strip(' .;') for part in text.split(' и ') if part.strip(' .;')]
            short_and_parts = [part for part in and_parts if len(part.split()) <= 4]
            if len(short_and_parts) >= 2:
                candidates = short_and_parts

        if not candidates:
            candidates = [text]

        return candidates

    def _normalize_candidate_term(self, text: str) -> Optional[str]:
        """Normalize spacing and drop obviously noisy fragments."""
        value = re.sub(r'\s+', ' ', text).strip(' .;:')
        value = re.sub(r'\bи др\.?\b', '', value, flags=re.IGNORECASE).strip(' .;:')
        value = value.replace('т.з', '').strip(' .;:')
        value = value.strip('-')
        if self._is_noise_candidate(value):
            return None
        return value

    def _is_noise_candidate(self, text: str) -> bool:
        """Filter fragments that are too generic to be useful as requirements."""
        if not text or len(text) < 2:
            return True
        lowered = text.lower()
        if text.endswith('-'):
            return True
        if lowered in {'того', 'пр', 'др', 'как'}:
            return True
        if lowered in {'на уровне не ниже intermediate', 'аналитический склад ума', 'нацеленность на результат', 'проактивность'}:
            return True
        if lowered.startswith('уровень дохода') or lowered.startswith('полная занятость'):
            return True
        if len(text) > 140:
            return True
        return False

    def _extract_vacancy_keywords(
        self,
        role: Optional[str],
        must_have_skills: List[str],
        nice_to_have_skills: List[str],
        responsibilities: List[str],
    ) -> List[str]:
        """Build ATS keywords from parsed vacancy data."""
        keywords = []
        seen = set()

        def add(value: Optional[str]):
            if not value:
                return
            lowered = value.lower()
            if lowered not in seen:
                keywords.append(value)
                seen.add(lowered)

        add(role)
        for item in must_have_skills + nice_to_have_skills:
            add(item)

        responsibility_terms = {
            'мониторинг': 'Мониторинг',
            'инцидент': 'Инциденты',
            'эскалац': 'Эскалация',
            'данн': 'Данные',
            'аномал': 'Аномалии',
        }
        for responsibility in responsibilities:
            for candidate in self._extract_skill_candidates_from_line(responsibility):
                add(candidate)
            lowered = responsibility.lower()
            for marker, keyword in responsibility_terms.items():
                if marker in lowered:
                    add(keyword)

        return keywords
    
    def build_strategy(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        candidate_preferences: Optional[Dict[str, Any]] = None,
    ) -> StrategyBrief:
        """Build strategy for resume adaptation"""
        from app.services.career_strategy_stage import build_fallback_strategy

        return build_fallback_strategy(
            candidate_profile,
            vacancy_profile,
            candidate_preferences,
            reason="mock mode",
        )
    
    def generate_resume(
        self,
        candidate_profile: CandidateProfile,
        vacancy_profile: VacancyProfile,
        strategy_brief: StrategyBrief
    ) -> GeneratedResume:
        """Generate adapted resume in mock mode using the same backend heuristics."""
        from app.services.resume_writer_stage import build_deterministic_resume

        return build_deterministic_resume(
            candidate_profile,
            vacancy_profile,
            strategy_brief,
            reason="mock mode",
        )
