const state = {
  initialized: false,
  page: "landing",
  step: 0,
  mode: "file",
  userId: null,
  conversationId: null,
  authenticated: false,
  authUser: null,
  authMode: "login",
  authError: "",
  resumeText: "",
  vacancyText: "",
  uploadedFileName: "",
  currentResumeId: null,
  candidateProfile: null,
  vacancyProfile: null,
  strategyBrief: null,
  generatedResume: null,
  techReport: null,
  resumeWarnings: [],
  vacancyWarnings: [],
  clarifyingQuestions: [],
  resumes: [],
  sourceResume: null,
  adaptations: [],
  currentAdaptation: null,
  pendingAdaptation: null,
  recommendedVacancies: [],
  selectedExternalVacancy: null,
  vacancySearch: "",
  vacancySourceFilter: "all",
  vacancyAdaptingId: null,
  cabinetView: "resume",
  newAdaptationMode: "url",
  newAdaptationText: "",
  newAdaptationUrl: "",
  fetchedVacancy: null,
  vacancyFetchError: "",
  vacancyFetching: false,
  adaptationSubmitting: false,
  sourceResumeMode: "upload",
  sourceResumeEditingBlock: null,
  manualResumeDraft: null,
  manualResumeSubmitting: false,
  sourceResumeSelecting: false,
  sourceResumeUpdating: false,
  modelInfo: null,
  lastResumeAnalyzedText: "",
};

const landingPage = document.getElementById("landingPage");
const flowPage = document.getElementById("flowPage");
const cabinetPage = document.getElementById("cabinetPage");
const cabinetRoot = document.getElementById("cabinetRoot");
const authPage = document.getElementById("authPage");
const authRoot = document.getElementById("authRoot");
const railSteps = [...document.querySelectorAll(".rail-step")];
const screen = document.getElementById("screen");
const toast = document.getElementById("toast");
const topActions = document.getElementById("topActions");

const meta = [
  {
    label: "Создание source resume",
    title: "Добавьте резюме",
    subtitle: "Загрузите базовое резюме один раз. Система извлечёт опыт, навыки, образование и сохранит профиль для будущих адаптаций.",
    next: "Сохранить резюме",
  },
  {
    label: "Шаг 2 из 4",
    title: "Вставьте вакансию",
    subtitle: "Добавьте описание позиции. Чем подробнее текст, тем точнее система выделит требования и ключевые обязанности.",
    next: "Запустить анализ",
  },
  {
    label: "Шаг 3 из 4",
    title: "Проверьте анализ",
    subtitle: "Перед генерацией система показывает промежуточные результаты, чтобы итоговое резюме было понятным и проверяемым.",
    next: "Сгенерировать резюме",
  },
  {
    label: "Шаг 4 из 4",
    title: "Готовый результат",
    subtitle: "Проверьте адаптированную версию резюме и скачайте её в нужном формате.",
    next: "Новая вакансия",
  },
];

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (match) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[match]);
}

function showToast(text) {
  toast.textContent = text;
  toast.classList.add("show");
  clearTimeout(showToast._timeoutId);
  showToast._timeoutId = setTimeout(() => toast.classList.remove("show"), 2200);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setBusy(isBusy) {
  const next = document.getElementById("nextBtn");
  if (next) {
    next.disabled = isBusy;
    next.textContent = isBusy ? "Подождите..." : `${meta[state.step].next} →`;
    next.style.opacity = isBusy ? "0.7" : "1";
    next.style.cursor = isBusy ? "wait" : "pointer";
  }
}

function head() {
  const currentMeta = meta[state.step];
  const progress = state.step === 0 ? 100 : (state.step + 1) * 25;
  return `
    <div class="progress-wrap">
      <div class="progress-meta">
        <span>${currentMeta.label}</span>
        <span>${state.step === 0 ? "базовый профиль" : `${progress}% готово`}</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width:${progress}%"></div>
      </div>
    </div>

    <div class="screen-head">
      <h2>${currentMeta.title}</h2>
      <p class="screen-sub">${currentMeta.subtitle}</p>
    </div>
  `;
}

function actions() {
  const backButton = state.step > 0
    ? `<button class="ghost-btn" id="prevBtn" type="button">← Назад</button>`
    : `<button class="ghost-btn" id="homeBtn" type="button">← На главную</button>`;

  return `
    <div class="screen-actions">
      ${backButton}
      <button class="next-btn" id="nextBtn" type="button">${meta[state.step].next} →</button>
    </div>
  `;
}

function warningBlock(items) {
  const grouped = groupUserWarnings(items);
  if (!grouped.soft.length && !grouped.important.length) {
    return "";
  }

  return `
    <div class="change-list">
      <b>Что стоит уточнить</b>
      ${grouped.soft.length ? `
        <ul>
          ${grouped.soft.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      ` : ""}
      ${grouped.important.length ? `
        <b style="display:block; margin-top:14px;">Важные замечания</b>
        <ul>
          ${grouped.important.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      ` : ""}
    </div>
  `;
}

function renderWarningsContent(items) {
  const grouped = groupUserWarnings(items);
  if (!grouped.soft.length && !grouped.important.length) {
    return renderEmpty("Критичных уточнений нет");
  }

  return `
    ${grouped.soft.length ? `
      <ul class="agent-list">
        ${grouped.soft.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    ` : ""}
    ${grouped.important.length ? `
      <div class="agent-subblock">
        <b>Важные замечания</b>
        <ul class="agent-list">
          ${grouped.important.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </div>
    ` : ""}
  `;
}

function sanitizeWarnings(warnings) {
  const technicalMarkers = [
    "badrequest",
    "retryerror",
    "fallback used",
    "exception fallback",
    "profile extracted using hh.ru parsing",
    "profile extracted using section-based parsing",
  ];

  const cleaned = [];
  (warnings || []).forEach((warning) => {
    const text = String(warning || "").trim();
    if (!text) return;
    const lowered = text.toLowerCase();
    if (technicalMarkers.some((marker) => lowered.includes(marker))) {
      return;
    }

    const friendly = humanizeWarning(text);
    if (friendly && !cleaned.includes(friendly)) {
      cleaned.push(friendly);
    }
  });
  return cleaned;
}

function humanizeWarning(text) {
  let value = String(text || "").trim();
  if (!value) {
    return "";
  }

  value = value.replace(/\[[A-Z0-9_]+\]/g, "").replace(/\s{2,}/g, " ").trim(" .;:-");
  const lowered = value.toLowerCase();

  if (!value) {
    return "";
  }

  if (lowered.includes("summary_raw") || lowered.includes("summary") && lowered.includes("missing")) {
    return "Краткое описание профиля не найдено. При желании можно добавить 2-3 предложения о вашем опыте.";
  }
  if (lowered.includes("section missing") || lowered.includes("section parser")) {
    return "Некоторые разделы резюме распознаны не полностью. Проверьте, что опыт, навыки и образование указаны явно.";
  }
  if (lowered.includes("no jobs") || lowered.includes("found no jobs")) {
    return "Не удалось уверенно выделить опыт работы. Проверьте, что компании, должности и даты указаны отдельными строками.";
  }
  if (lowered.includes("languages inferred outside") || lowered.includes("language section")) {
    return "Уровни языков лучше указать отдельным разделом, например: Английский — B2.";
  }
  if (lowered.includes("target role inferred") || lowered.includes("target role")) {
    return "Целевая роль определена по заголовку резюме. Проверьте, что она указана корректно.";
  }
  if (lowered.includes("experience") && (lowered.includes("inferred") || lowered.includes("estimated") || lowered.includes("ambiguous"))) {
    return "Суммарный опыт рассчитан по датам. Если в резюме есть точный стаж, лучше указать его явно.";
  }
  if (lowered.includes("truncated") || lowered.includes("обрез")) {
    return "Резюме было длинным, часть текста могла не попасть в анализ. Проверьте самые важные блоки опыта.";
  }
  if (lowered.includes("missing") || lowered.includes("absent") || lowered.includes("отсутств")) {
    return "Некоторые данные отсутствуют или указаны неявно. При необходимости добавьте их в резюме.";
  }

  return value;
}

function groupUserWarnings(items) {
  const soft = [];
  const important = [];

  sanitizeWarnings(items).forEach((item) => {
    const lowered = item.toLowerCase();
    const isImportant = [
      "не удалось уверенно выделить опыт работы",
      "резюме было длинным",
      "проверьте, что компании",
    ].some((marker) => lowered.includes(marker));

    if (isImportant) {
      important.push(item);
    } else {
      soft.push(item);
    }
  });

  return { soft, important };
}

function summaryPills(values) {
  const filtered = values.filter(Boolean);
  if (!filtered.length) {
    return "";
  }

  return `
    <div class="micro">
      ${filtered.map((value) => `<span>${escapeHtml(value)}</span>`).join("")}
    </div>
  `;
}

function canonicalCandidateProfile(profile) {
  if (!profile) {
    return null;
  }
  return profile.canonical_profile || profile;
}

function compactEvidenceForDisplay(evidence) {
  if (!evidence) {
    return {
      target_role: [],
      total_experience: [],
      skills_section: [],
      education: [],
      languages: [],
      jobs: [],
    };
  }

  if (Array.isArray(evidence.jobs)) {
    return {
      target_role: evidence.target_role || [],
      total_experience: evidence.total_experience || evidence.experience_years || [],
      skills_section: evidence.skills_section || evidence.skills_hard || [],
      education: evidence.education || [],
      languages: evidence.languages || [],
      jobs: evidence.jobs.map((job) => ({
        job_id: job.job_id,
        company: job.company || [],
        position: job.position || [],
        period: job.period || [],
        highlights: job.highlights || [],
      })),
    };
  }

  const jobsById = {};
  Object.entries(evidence).forEach(([key, value]) => {
    const match = key.match(/^job_(\d+)_(company|position|period|highlights|responsibilities|achievements|skills_used)$/);
    if (!match) {
      return;
    }

    const jobId = Number(match[1]);
    const field = match[2];
    const job = jobsById[jobId] || {
      job_id: jobId,
      company: [],
      position: [],
      period: [],
      highlights: [],
    };
    const snippets = Array.isArray(value) ? value : [value].filter(Boolean);

    if (field === "responsibilities" || field === "achievements" || field === "skills_used") {
      job.highlights.push(...snippets);
    } else {
      job[field] = snippets;
    }
    jobsById[jobId] = job;
  });

  return {
    target_role: evidence.target_role || [],
    total_experience: evidence.total_experience || evidence.experience_years || [],
    skills_section: evidence.skills_section || evidence.skills_hard || [],
    education: evidence.education || [],
    languages: evidence.languages || [],
    jobs: Object.values(jobsById).sort((a, b) => a.job_id - b.job_id),
  };
}

function candidateProfileDisplayPayload(profile) {
  if (!profile) {
    return null;
  }

  return {
    canonical_profile: canonicalCandidateProfile(profile),
    evidence: compactEvidenceForDisplay(profile.evidence),
    confidence: profile.confidence || {},
    ambiguities: profile.ambiguities || [],
    raw_warnings: sanitizeWarnings(profile.raw_warnings || []),
  };
}

function asList(value) {
  if (!value) {
    return [];
  }
  const raw = Array.isArray(value) ? value : [value];
  const seen = new Set();
  return raw
    .map((item) => String(item ?? "").trim())
    .filter(Boolean)
    .filter((item) => {
      const key = item.toLowerCase();
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
}

function asRawList(value) {
  if (!value) {
    return [];
  }
  return Array.isArray(value) ? value.filter(Boolean) : [value].filter(Boolean);
}

function limitedList(value, limit = 8) {
  return asList(value).slice(0, limit);
}

function splitLines(value) {
  return String(value || "")
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function splitDelimited(value) {
  return String(value || "")
    .split(/[;\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

const manualPeriodMonthMap = {
  янв: 1,
  январ: 1,
  feb: 2,
  фев: 2,
  февр: 2,
  март: 3,
  мар: 3,
  apr: 4,
  апр: 4,
  апрел: 4,
  may: 5,
  май: 5,
  мая: 5,
  jun: 6,
  июн: 6,
  июнь: 6,
  jul: 7,
  июл: 7,
  июль: 7,
  aug: 8,
  авг: 8,
  август: 8,
  sep: 9,
  сент: 9,
  сен: 9,
  сентябр: 9,
  oct: 10,
  окт: 10,
  октябр: 10,
  nov: 11,
  ноя: 11,
  ноябр: 11,
  dec: 12,
  дек: 12,
  декабр: 12,
};

function normalizeTwoDigitYear(value) {
  const year = Number.parseInt(value, 10);
  if (!Number.isFinite(year)) {
    return null;
  }
  if (year < 100) {
    return year >= 70 ? 1900 + year : 2000 + year;
  }
  return year;
}

function padMonth(month) {
  return String(month).padStart(2, "0");
}

function parseManualPeriodPart(value, isEnd = false) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) {
    return null;
  }
  if (/(н\.?\s*в\.?|наст|present|current|now)/i.test(raw)) {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1, current: true };
  }

  const numeric = raw.match(/\b(0?[1-9]|1[0-2])[./\s]+((?:19|20)?\d{2})\b/);
  if (numeric) {
    const year = normalizeTwoDigitYear(numeric[2]);
    if (year) {
      return { year, month: Number.parseInt(numeric[1], 10), current: false };
    }
  }

  const monthEntry = Object.entries(manualPeriodMonthMap)
    .find(([token]) => raw.includes(token));
  const fourDigit = raw.match(/\b(19|20)\d{2}\b/);
  const twoDigitMatches = [...raw.matchAll(/(?:^|[.\s])(\d{2})(?!\d)/g)].map((match) => match[1]);
  const year = fourDigit
    ? Number.parseInt(fourDigit[0], 10)
    : normalizeTwoDigitYear(twoDigitMatches[twoDigitMatches.length - 1]);

  if (!year) {
    return null;
  }
  return {
    year,
    month: monthEntry ? monthEntry[1] : (isEnd ? 12 : 1),
    current: false,
  };
}

function parseManualPeriodRange(period) {
  const normalized = String(period || "")
    .replace(/[—–]/g, "-")
    .replace(/\s+по\s+/gi, " - ")
    .trim();
  if (!normalized) {
    return null;
  }
  const parts = normalized.split(/\s*-\s*/).filter(Boolean);
  const start = parseManualPeriodPart(parts[0], false);
  const end = parseManualPeriodPart(parts.slice(1).join(" - ") || parts[0], true);
  if (!start || !end) {
    return null;
  }
  const months = (end.year - start.year) * 12 + (end.month - start.month) + 1;
  if (!Number.isFinite(months) || months <= 0) {
    return null;
  }
  return {
    months,
    startDate: `${start.year}-${padMonth(start.month)}`,
    endDate: end.current ? null : `${end.year}-${padMonth(end.month)}`,
    isCurrent: Boolean(end.current),
  };
}

function formatExperience(canonical) {
  const months = Number(canonical?.experience_months || 0);
  if (months > 0) {
    const years = Math.floor(months / 12);
    const rest = months % 12;
    const parts = [];
    if (years) parts.push(`${years} ${years === 1 ? "год" : years < 5 ? "года" : "лет"}`);
    if (rest) parts.push(`${rest} мес.`);
    return parts.join(" ") || `${months} мес.`;
  }

  if (canonical?.experience_years) {
    return `${canonical.experience_years} лет`;
  }

  return "не указано";
}

function renderEmpty(text = "Нет данных") {
  return `<p class="agent-empty">${escapeHtml(text)}</p>`;
}

function renderBulletList(items, emptyText = "Нет данных") {
  const values = asList(items);
  if (!values.length) {
    return renderEmpty(emptyText);
  }
  return `<ul class="agent-list">${values.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderChips(items, limit = 18) {
  const values = limitedList(items, limit);
  if (!values.length) {
    return renderEmpty();
  }
  return `<div class="agent-chips">${values.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>`;
}

function renderAgentSection(title, bodyHtml) {
  return `
    <section class="agent-section">
      <h4>${escapeHtml(title)}</h4>
      ${bodyHtml}
    </section>
  `;
}

function renderMetricGrid(items) {
  const cells = items
    .filter((item) => item.value !== undefined && item.value !== null && String(item.value).trim() !== "")
    .map((item) => `
      <div class="agent-metric">
        <span>${escapeHtml(item.label)}</span>
        <b>${escapeHtml(item.value)}</b>
      </div>
    `)
    .join("");

  return cells ? `<div class="agent-metrics">${cells}</div>` : renderEmpty();
}

function humanizeStatus(value) {
  const text = String(value || "").trim();
  const lower = text.toLowerCase();
  if (lower === "high") return "высокая";
  if (lower === "medium") return "средняя";
  if (lower === "low") return "низкая";
  return text;
}

function renderDebugJson(payload, label = "Показать JSON") {
  return `
    <details class="agent-debug">
      <summary>${escapeHtml(label)}</summary>
      <pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
    </details>
  `;
}

function candidateProfileDisplayModel(profile) {
  const displayPayload = candidateProfileDisplayPayload(profile);
  const canonical = displayPayload?.canonical_profile || {};
  return {
    payload: displayPayload,
    canonical,
    evidence: displayPayload?.evidence || {},
    warnings: [
      ...(displayPayload?.ambiguities || []),
      ...(displayPayload?.raw_warnings || []),
    ],
  };
}

function renderCandidateProfileView(profile) {
  const model = candidateProfileDisplayModel(profile);
  const candidate = model.canonical;
  const jobs = Array.isArray(candidate.jobs) ? candidate.jobs : [];
  const education = Array.isArray(candidate.education) ? candidate.education : [];
  const languages = Array.isArray(candidate.languages) ? candidate.languages : [];

  const jobsHtml = jobs.length
    ? jobs.map((job) => {
      const bullets = [
        ...(job.achievements || []),
        ...(job.responsibilities || []),
      ].slice(0, 3);
      return `
        <article class="agent-job-card">
          <div>
            <b>${escapeHtml(job.position || "Должность не указана")}</b>
            <span>${escapeHtml([job.company_name, job.company_type].filter(Boolean).join(" · ") || "Компания не указана")}</span>
          </div>
          <p>${escapeHtml(job.period || "Период не указан")}</p>
          ${renderBulletList(bullets, "Ключевые пункты не выделены")}
        </article>
      `;
    }).join("")
    : renderEmpty("Опыт работы не распознан");

  const educationHtml = education.length
    ? education.map((item) => `
      <div class="agent-line">
        <b>${escapeHtml(item.institution || "Учебное заведение не указано")}</b>
        <span>${escapeHtml([item.degree, item.field, item.year, item.status].filter(Boolean).join(" · "))}</span>
      </div>
    `).join("")
    : renderEmpty("Образование не указано");

  const languagesHtml = languages.length
    ? languages.map((item) => {
      if (typeof item === "string") {
        return `<span>${escapeHtml(item)}</span>`;
      }
      return `<span>${escapeHtml([item.name, item.level].filter(Boolean).join(" · "))}</span>`;
    }).join("")
    : "";

  const hasProvenance = profile?.provenance && Object.keys(profile.provenance).length > 0;

  return `
    <div class="agent-view">
      ${renderAgentSection("Кратко", renderMetricGrid([
    { label: "Целевая роль", value: candidate.target_role || "не указана" },
    { label: "Опыт", value: formatExperience(candidate) },
    { label: "Мест работы", value: jobs.length },
    { label: "Уверенность", value: humanizeStatus(model.payload?.confidence?.overall) || "не указана" },
  ]))}
      ${renderAgentSection("Ключевые профессиональные навыки", renderChips(candidate.skills_hard))}
      ${renderAgentSection("Гибкие навыки", renderChips(candidate.skills_soft, 10))}
      ${renderAgentSection("Опыт работы", jobsHtml)}
      ${renderAgentSection("Образование", educationHtml)}
      ${renderAgentSection("Языки", languagesHtml ? `<div class="agent-chips">${languagesHtml}</div>` : renderEmpty("Языки не указаны"))}
      ${renderAgentSection("Что стоит уточнить", renderWarningsContent(model.warnings))}
      ${renderDebugJson(model.payload)}
      ${hasProvenance ? renderDebugJson(profile.provenance, "Показать технические данные provenance") : ""}
    </div>
  `;
}

function renderVacancyProfileView(profile) {
  return `
    <div class="agent-view">
      ${renderAgentSection("Кратко", renderMetricGrid([
    { label: "Роль", value: profile.role || "не указана" },
    { label: "Уровень", value: profile.seniority || "не указан" },
    { label: "Индустрия", value: profile.industry || "не указана" },
  ]))}
      ${renderAgentSection("Обязательные требования", renderBulletList(profile.must_have_skills, "Обязательные требования не выделены"))}
      ${renderAgentSection("Будет плюсом", renderBulletList(profile.nice_to_have_skills, "Дополнительные требования не указаны"))}
      ${renderAgentSection("Основные задачи", renderBulletList(profile.key_responsibilities, "Задачи не выделены"))}
      ${renderAgentSection("ATS-ключевые слова", renderChips(profile.keywords_for_ats, 24))}
      ${renderAgentSection("Что стоит уточнить", renderWarningsContent(profile.raw_warnings || []))}
      ${renderDebugJson(profile)}
    </div>
  `;
}

function jobLabelById(jobId) {
  const candidate = canonicalCandidateProfile(state.candidateProfile);
  const job = (candidate?.jobs || []).find((item) => Number(item.id) === Number(jobId));
  if (!job) {
    return `Работа #${jobId}`;
  }
  return [job.position, job.company_name, job.period].filter(Boolean).join(" · ");
}

function renderJobIdList(ids, emptyText) {
  const values = asList(ids).map((id) => jobLabelById(id));
  return renderBulletList(values, emptyText);
}

function renderFit(strategy) {
  const finalScore = Number(strategy.fit_score || 0);
  const supportScore = Number(strategy.support_fit_score || 0);
  const hasFinalScore = strategy.fit_score !== undefined && strategy.fit_score !== null && Number.isFinite(finalScore);
  const hasSupportScore = strategy.support_fit_score !== undefined && strategy.support_fit_score !== null && Number.isFinite(supportScore);
  return renderMetricGrid([
    { label: "Итоговая оценка", value: hasFinalScore ? `${Math.round(finalScore * 100)}%` : "не указана" },
    { label: "Качественная оценка", value: humanizeStatus(strategy.qualitative_fit) || "не указано" },
    { label: "Поддерживающая оценка", value: hasSupportScore ? `${Math.round(supportScore * 100)}%` : "не указана" },
    { label: "Уверенность стратегии", value: humanizeStatus(strategy.strategy_confidence) || "не указана" },
  ]);
}

function renderCareerStrategyView(strategy) {
  return `
    <div class="agent-view">
      ${renderAgentSection("Позиционирование", `<p class="agent-text">${escapeHtml(strategy.positioning || "Позиционирование не сформировано")}</p>`)}
      ${renderAgentSection("Оценка соответствия", renderFit(strategy))}
      ${renderAgentSection("Какие места работы выделяем", renderJobIdList(strategy.highlight_job_ids, "Нет явного фокуса по местам работы"))}
      ${renderAgentSection("Какие места работы уводим ниже", renderJobIdList(strategy.downplay_job_ids, "Ничего специально не уводим ниже"))}
      ${renderAgentSection("Какие навыки усиливаем", renderChips(strategy.skills_to_highlight, 16))}
      ${renderAgentSection("Какие навыки лучше не выдвигать", renderChips(strategy.skills_to_soften, 12))}
      ${renderAgentSection("Какие достижения вынести в центр", renderBulletList(strategy.achievement_highlights, "Достижения не выделены отдельно"))}
      ${renderAgentSection("Основные темы резюме", renderChips(strategy.priority_themes, 12))}
      ${renderAgentSection("Гэпы", renderBulletList(strategy.gaps, "Критичные гэпы не выделены"))}
      ${renderAgentSection("Рекомендации по подаче", `<p class="agent-text">${escapeHtml(strategy.recommendations_short || "Рекомендации не сформированы")}</p>`)}
      ${strategy.strategy_warnings?.length ? renderAgentSection("Что стоит уточнить", renderWarningsContent(strategy.strategy_warnings)) : ""}
      ${renderDebugJson(strategy)}
    </div>
  `;
}

function renderTechnicalReportView(report, resume) {
  const resumeText = resume?.text || resume?.resume_text || "";
  const writerWarnings = [
    ...(report?.writer_warnings || []),
    ...(report?.critic_warnings || []),
  ];

  return `
    <div class="agent-view">
      ${renderAgentSection("Готовое резюме", resumeText
    ? `<pre class="agent-resume-text">${escapeHtml(resumeText)}</pre>`
    : renderEmpty("Текст резюме не найден"))}
      ${renderAgentSection("Что вошло в итог", `
        ${renderMetricGrid([
      { label: "Резервная генерация", value: report?.writer_fallback_used ? "да" : "нет" },
      { label: "Резервная проверка", value: report?.critic_fallback_used ? "да" : "нет" },
      { label: "Уверенность проверки", value: humanizeStatus(report?.critic_confidence) || "не указана" },
    ])}
        <div class="agent-subblock">
          <b>Использованные места работы</b>
          ${renderJobIdList(report?.used_highlight_job_ids, "Не указаны")}
        </div>
        <div class="agent-subblock">
          <b>Использованные достижения</b>
          ${renderBulletList(report?.used_achievement_highlights, "Не указаны")}
        </div>
        <div class="agent-subblock">
          <b>Темы позиционирования</b>
          ${renderChips(report?.used_priority_themes, 12)}
        </div>
      `)}
      ${renderAgentSection("Что покрыто по вакансии", renderBulletList(report?.covered_must_haves, "Покрытые требования не указаны"))}
      ${renderAgentSection("Что не покрыто", renderBulletList(report?.uncovered_must_haves, "Явных непокрытых требований нет"))}
      ${renderAgentSection("Замечания критика", renderWarningsContent(writerWarnings))}
      ${report?.hallucination_checks?.length ? renderAgentSection("Проверка фактов", renderBulletList(report.hallucination_checks)) : ""}
      ${report?.omitted_strategy_items?.length ? renderAgentSection("Что не вошло из стратегии", renderBulletList(report.omitted_strategy_items)) : ""}
      ${renderDebugJson(report || {})}
    </div>
  `;
}

function renderResume() {
  const candidate = canonicalCandidateProfile(state.candidateProfile);
  const uploadedSummary = state.uploadedFileName
    ? `
      <div class="change-list">
        <b>Файл уже добавлен</b>
        <ul>
          <li>${escapeHtml(state.uploadedFileName)}</li>
          <li>${candidate?.jobs?.length || 0} мест работы распознано</li>
          <li>${candidate?.skills_hard?.length || 0} профессиональных навыков найдено</li>
        </ul>
      </div>
    `
    : "";

  screen.innerHTML = `
    ${head()}
    <div class="field-wrap">
      <div class="input-tabs">
        <button class="input-tab ${state.mode === "file" ? "active" : ""}" data-mode="file">Загрузить файл</button>
        <button class="input-tab ${state.mode === "text" ? "active" : ""}" data-mode="text">Вставить текст</button>
      </div>

      ${state.mode === "file" ? `
        <div class="drop" id="drop">
          <div>
            <div class="drop-icon">⇧</div>
            <b>${state.uploadedFileName ? "Резюме загружено" : "Перетащите резюме сюда"}</b>
            <p>${state.uploadedFileName ? escapeHtml(state.uploadedFileName) : "или нажмите, чтобы выбрать файл"}</p>
          </div>
        </div>
        <input type="file" id="file" hidden accept=".txt,.pdf,.doc,.docx" />
        ${uploadedSummary}
      ` : `
        <textarea id="resumeText" placeholder="Вставьте текст резюме...">${escapeHtml(state.resumeText)}</textarea>
      `}

      ${summaryPills([
    "TXT, PDF, DOCX",
    "до 10 МБ",
  ])}
      ${warningBlock(state.resumeWarnings)}
    </div>
    ${actions()}
  `;

  document.querySelectorAll(".input-tab").forEach((button) => {
    button.onclick = () => {
      state.mode = button.dataset.mode;
      render();
    };
  });

  const resumeText = document.getElementById("resumeText");
  if (resumeText) {
    resumeText.oninput = (event) => {
      state.resumeText = event.target.value;
    };
  }

  const drop = document.getElementById("drop");
  const fileInput = document.getElementById("file");
  if (drop && fileInput) {
    drop.onclick = () => fileInput.click();
    fileInput.onchange = async () => {
      if (fileInput.files[0]) {
        await uploadResumeFile(fileInput.files[0]);
      }
    };

    drop.ondragover = (event) => {
      event.preventDefault();
      drop.style.borderColor = "#111";
    };
    drop.ondragleave = () => {
      drop.style.borderColor = "#cfc8bc";
    };
    drop.ondrop = async (event) => {
      event.preventDefault();
      drop.style.borderColor = "#cfc8bc";
      const file = event.dataTransfer?.files?.[0];
      if (file) {
        await uploadResumeFile(file);
      }
    };
  }

  bindActions();
}

function renderVacancy() {
  screen.innerHTML = `
    ${head()}
    <div class="field-wrap">
      <textarea id="vacancyText" placeholder="Вставьте текст вакансии...">${escapeHtml(state.vacancyText)}</textarea>
      ${summaryPills([
    "обязанности",
    "требования",
    "ключевые навыки",
  ])}
      ${warningBlock(state.resumeWarnings)}
    </div>
    ${actions()}
  `;

  document.getElementById("vacancyText").oninput = (event) => {
    state.vacancyText = event.target.value;
  };

  bindActions();
}

function candidateSummary(profile) {
  if (!profile) {
    return "Профиль кандидата появится после анализа резюме.";
  }

  const canonical = canonicalCandidateProfile(profile);
  const parts = [];
  if (canonical?.target_role) parts.push(`роль: ${canonical.target_role}`);
  if (canonical?.experience_years) parts.push(`опыт: ${canonical.experience_years} лет`);
  parts.push(`мест работы: ${canonical?.jobs?.length || 0}`);
  parts.push(`проф. навыков: ${canonical?.skills_hard?.length || 0}`);
  return parts.join(", ");
}

function vacancySummary(profile) {
  if (!profile) {
    return "Профиль вакансии появится после второго шага.";
  }

  const parts = [];
  if (profile.role) parts.push(profile.role);
  if (profile.seniority) parts.push(profile.seniority);
  parts.push(`обязательных требований: ${profile.must_have_skills?.length || 0}`);
  parts.push(`задач: ${profile.key_responsibilities?.length || 0}`);
  return parts.join(", ");
}

function strategySummary(strategy) {
  if (!strategy) {
    return "Стратегия появится после анализа соответствия резюме вакансии.";
  }

  if (strategy.recommendations_short) {
    return strategy.recommendations_short;
  }

  return "Стратегия готова к проверке.";
}

function renderAnalysis() {
  const scoreValue = state.strategyBrief?.fit_score ? `${Math.round(state.strategyBrief.fit_score * 100)}%` : "готово";

  screen.innerHTML = `
    ${head()}
    <div class="analysis">
      <article class="analysis-item">
        <div class="analysis-ico">👤</div>
        <div>
          <h3>Профиль кандидата</h3>
          <p>${escapeHtml(candidateSummary(state.candidateProfile))}</p>
        </div>
        <div class="score">готово</div>
        <button class="soft-link" type="button" data-type="candidate">Показать подробнее</button>
      </article>
      <article class="analysis-item">
        <div class="analysis-ico">💼</div>
        <div>
          <h3>Профиль вакансии</h3>
          <p>${escapeHtml(vacancySummary(state.vacancyProfile))}</p>
        </div>
        <div class="score">готово</div>
        <button class="soft-link" type="button" data-type="vacancy">Показать подробнее</button>
      </article>
      <article class="analysis-item">
        <div class="analysis-ico">🎯</div>
        <div>
          <h3>Стратегия адаптации</h3>
          <p>${escapeHtml(strategySummary(state.strategyBrief))}</p>
        </div>
        <div class="score">${scoreValue}</div>
        <button class="soft-link" type="button" data-type="strategy">Показать подробнее</button>
      </article>
      ${state.clarifyingQuestions.length ? `
        <div class="change-list">
          <b>Уточнения перед отправкой</b>
          <ul>
            ${state.clarifyingQuestions.map((question) => `<li>${escapeHtml(question)}</li>`).join("")}
          </ul>
        </div>
      ` : ""}
      ${warningBlock([...state.resumeWarnings, ...state.vacancyWarnings])}
    </div>
    ${actions()}
  `;

  document.querySelectorAll(".soft-link").forEach((button) => {
    button.onclick = () => openDetailsModal(button.dataset.type);
  });

  bindActions();
}

function buildChangeItems() {
  const items = [];

  if (state.strategyBrief?.skills_to_highlight?.length) {
    items.push(`Вверх подняты навыки: ${state.strategyBrief.skills_to_highlight.slice(0, 4).join(", ")}`);
  }

  if (state.techReport?.covered_must_haves?.length) {
    items.push(`Покрыты требования: ${state.techReport.covered_must_haves.slice(0, 4).join(", ")}`);
  }

  if (state.techReport?.uncovered_must_haves?.length) {
    items.push(`Остались пробелы: ${state.techReport.uncovered_must_haves.slice(0, 3).join(", ")}`);
  }

  if (state.techReport?.critic_warnings?.length) {
    items.push(state.techReport.critic_warnings[0]);
  }

  if (!items.length) {
    items.push("Результат собран из исходного резюме и требований вакансии без добавления новых фактов.");
  }

  return items;
}

function renderResult() {
  const title = state.generatedResume?.title || "Сгенерированное резюме";
  const role = state.vacancyProfile?.role || state.strategyBrief?.positioning || "Адаптированная версия";
  const resumeText = state.generatedResume?.text || "Результат появится после генерации.";
  const changeItems = buildChangeItems();

  screen.innerHTML = `
    ${head()}
    <div class="result-layout">
      <article class="doc">
        <h3>${escapeHtml(title)}</h3>
        <p class="role">${escapeHtml(role)}</p>
        <h4>Текст резюме</h4>
        <pre style="white-space:pre-wrap; margin:0; font:inherit; line-height:1.7; color:#3f3d39;">${escapeHtml(resumeText)}</pre>
      </article>
      <aside class="download">
        <b>Что было изменено</b>
        <div class="change-list">
          <ul>
            ${changeItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </div>

        <b style="margin-top:18px;">Скачать</b>
        <button class="format" data-format="PDF">PDF</button>
        <button class="format" data-format="DOCX">DOCX</button>
        <button class="format" data-format="TXT">TXT</button>
        <button class="format" id="detailsReportBtn" style="margin-top:18px;">Тех. отчёт</button>
      </aside>
    </div>
    ${actions()}
  `;

  document.querySelectorAll(".format").forEach((button) => {
    button.onclick = () => handleDownload(button.dataset.format);
  });

  const reportButton = document.getElementById("detailsReportBtn");
  if (reportButton) {
    reportButton.onclick = () => openDetailsModal("report");
  }

  bindActions();
}

function sourceResumeDisplayModel(source) {
  const profile = source?.candidate_profile || null;
  const candidate = canonicalCandidateProfile(profile);
  return {
    id: source?.id || null,
    fileName: source?.file_name || "резюме",
    updatedAt: source?.updated_at ? new Date(source.updated_at).toLocaleString("ru-RU") : "",
    rawText: source?.raw_text || "",
    candidate,
    evidence: compactEvidenceForDisplay(profile?.evidence),
    warnings: sanitizeWarnings(source?.warnings || source?.candidate_profile?.raw_warnings || []),
  };
}

function emptyManualJob(id = 1) {
  return {
    id,
    company_name: "",
    company_type: "",
    position: "",
    start_month: "",
    start_year: "",
    end_month: "",
    end_year: "",
    is_current: false,
    responsibilities: "",
    achievements: "",
  };
}

function emptyManualEducation() {
  return { institution: "", degree: "", field: "", start_year: "", end_year: "", status: "unknown" };
}

function emptyManualLanguage() {
  return { name: "", level: "" };
}

const manualMonthNames = [
  "Январь",
  "Февраль",
  "Март",
  "Апрель",
  "Май",
  "Июнь",
  "Июль",
  "Август",
  "Сентябрь",
  "Октябрь",
  "Ноябрь",
  "Декабрь",
];

function splitYearMonth(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})$/);
  if (!match) {
    return { year: "", month: "" };
  }
  return { year: match[1], month: String(Number(match[2])) };
}

function manualJobDateParts(job) {
  const start = splitYearMonth(job.start_date);
  const end = splitYearMonth(job.end_date);
  const fallback = !start.year && job.period ? parseManualPeriodRange(job.period) : null;
  const fallbackStart = splitYearMonth(fallback?.startDate);
  const fallbackEnd = splitYearMonth(fallback?.endDate);
  return {
    start_month: start.month || fallbackStart.month || "",
    start_year: start.year || fallbackStart.year || "",
    end_month: end.month || fallbackEnd.month || "",
    end_year: end.year || fallbackEnd.year || "",
    is_current: Boolean(job.is_current || fallback?.isCurrent),
  };
}

function monthSelectOptions(selectedValue) {
  return `<option value="">Месяц</option>${manualMonthNames.map((name, index) => {
    const value = String(index + 1);
    return `<option value="${value}"${String(selectedValue) === value ? " selected" : ""}>${name}</option>`;
  }).join("")}`;
}

function yearSelectOptions(selectedValue) {
  const currentYear = new Date().getFullYear();
  const years = [];
  for (let year = currentYear; year >= currentYear - 55; year -= 1) {
    years.push(year);
  }
  return `<option value="">Год</option>${years.map((year) => (
    `<option value="${year}"${String(selectedValue) === String(year) ? " selected" : ""}>${year}</option>`
  )).join("")}`;
}

function educationYearSelectOptions(selectedValue) {
  const currentYear = new Date().getFullYear();
  const years = [];
  for (let year = currentYear + 8; year >= currentYear - 70; year -= 1) {
    years.push(year);
  }
  return `<option value="">Год</option>${years.map((year) => (
    `<option value="${year}"${String(selectedValue) === String(year) ? " selected" : ""}>${year}</option>`
  )).join("")}`;
}

function parseEducationYears(value) {
  const years = String(value || "").match(/\b(?:19|20)\d{2}\b/g) || [];
  return {
    start_year: years[0] || "",
    end_year: years.length > 1 ? years[years.length - 1] : (years[0] || ""),
  };
}

function formatEducationYears(item) {
  const start = String(item.start_year || "").trim();
  const end = String(item.end_year || "").trim();
  if (start && end && start !== end) {
    return `${start} - ${end}`;
  }
  return end || start || "";
}

const manualLanguageOptions = [
  "Русский",
  "Английский",
  "Немецкий",
  "Французский",
  "Испанский",
  "Итальянский",
  "Китайский",
  "Турецкий",
  "Казахский",
];

const manualLanguageLevelOptions = [
  "Native",
  "C2",
  "C1",
  "B2",
  "B1",
  "A2",
  "A1",
];

function selectOptions(values, selectedValue, emptyLabel) {
  const selected = String(selectedValue || "");
  const uniqueValues = values.includes(selected) || !selected ? values : [selected, ...values];
  return `<option value="">${escapeHtml(emptyLabel)}</option>${uniqueValues.map((value) => (
    `<option value="${escapeHtml(value)}"${selected === value ? " selected" : ""}>${escapeHtml(value)}</option>`
  )).join("")}`;
}

function manualYearMonth(year, month) {
  const numericYear = Number.parseInt(year, 10);
  const numericMonth = Number.parseInt(month, 10);
  if (!numericYear || !numericMonth) {
    return null;
  }
  return { year: numericYear, month: numericMonth };
}

function manualMonthName(month) {
  return manualMonthNames[Number(month) - 1] || "";
}

function formatManualJobPeriod(job) {
  const start = manualYearMonth(job.start_year, job.start_month);
  if (!start) {
    return "";
  }
  const startLabel = `${manualMonthName(start.month)} ${start.year}`;
  if (job.is_current) {
    return `${startLabel} — настоящее время`;
  }
  const end = manualYearMonth(job.end_year, job.end_month);
  if (!end) {
    return startLabel;
  }
  return `${startLabel} — ${manualMonthName(end.month)} ${end.year}`;
}

function manualJobPeriodRange(job) {
  const start = manualYearMonth(job.start_year, job.start_month);
  if (!start) {
    return null;
  }
  const end = job.is_current
    ? { year: new Date().getFullYear(), month: new Date().getMonth() + 1, current: true }
    : manualYearMonth(job.end_year, job.end_month);
  if (!end) {
    return null;
  }
  const months = (end.year - start.year) * 12 + (end.month - start.month) + 1;
  if (!Number.isFinite(months) || months <= 0) {
    return null;
  }
  return {
    months,
    startDate: `${start.year}-${padMonth(start.month)}`,
    endDate: end.current ? null : `${end.year}-${padMonth(end.month)}`,
    isCurrent: Boolean(end.current),
  };
}

function manualDraftFromCandidate(candidate) {
  const source = candidate || {};
  return {
    target_role: source.target_role || "",
    summary_raw: source.summary_raw || "",
    skills_hard: asList(source.skills_hard).join("; "),
    skills_soft: asList(source.skills_soft).join("; "),
    achievements: "",
    jobs: (source.jobs?.length ? source.jobs : [emptyManualJob(1)]).map((job, index) => ({
      id: index + 1,
      company_name: job.company_name || "",
      company_type: job.company_type || "",
      position: job.position || "",
      ...manualJobDateParts(job),
      responsibilities: asList(job.responsibilities).join("\n"),
      achievements: asList(job.achievements).join("\n"),
    })),
    education: (source.education?.length ? source.education : [emptyManualEducation()]).map((item) => {
      const years = parseEducationYears(item.year);
      return {
        institution: item.institution || "",
        degree: item.degree || "",
        field: item.field || "",
        start_year: item.start_year || years.start_year || "",
        end_year: item.end_year || years.end_year || "",
        status: item.status || "unknown",
      };
    }),
    languages: (source.languages?.length ? source.languages : [emptyManualLanguage()]).map((item) => (
      typeof item === "string"
        ? { name: item, level: "" }
        : { name: item.name || "", level: item.level || "" }
    )),
  };
}

function getManualResumeDraft() {
  if (!state.manualResumeDraft) {
    const candidate = canonicalCandidateProfile(state.sourceResume?.candidate_profile);
    state.manualResumeDraft = manualDraftFromCandidate(candidate);
  }
  return state.manualResumeDraft;
}

function sourceEditBlockMatches(type, index = null) {
  const block = state.sourceResumeEditingBlock;
  if (!block || block.type !== type) {
    return false;
  }
  return index === null || Number(block.index) === Number(index);
}

function sourceEditButton(type, label = "✎", index = null) {
  const indexAttr = index === null ? "" : ` data-edit-index="${index}"`;
  return `<button class="cabinet-icon-btn" data-edit-source-block="${escapeHtml(type)}"${indexAttr} type="button" aria-label="Редактировать">${escapeHtml(label)}</button>`;
}

function sourceDeleteButton(type, index) {
  return `<button class="cabinet-tiny-btn" data-delete-source-item="${escapeHtml(type)}" data-delete-index="${index}" type="button">Удалить</button>`;
}

function sourceSectionHead(title, editable, addType = "") {
  return `
    <div class="cabinet-section-head">
      <h2>${escapeHtml(title)}</h2>
      ${editable && addType ? `<button class="cabinet-mini-btn" data-add-source-item="${escapeHtml(addType)}" type="button">+ Добавить</button>` : ""}
    </div>
  `;
}

function sourceBlockEditorActions() {
  return `
    <div class="source-block-actions">
      <button class="cabinet-mini-btn dark" type="submit" ${state.manualResumeSubmitting ? "disabled" : ""}>${state.manualResumeSubmitting ? "Сохраняем..." : "Сохранить"}</button>
      <button class="cabinet-mini-btn" data-cancel-source-edit type="button" ${state.manualResumeSubmitting ? "disabled" : ""}>Отмена</button>
    </div>
  `;
}

function manualDraftJobToDisplay(job, index) {
  return {
    id: index + 1,
    company_name: job.company_name || "",
    company_type: job.company_type || "",
    position: job.position || "",
    period: formatManualJobPeriod(job),
    responsibilities: splitLines(job.responsibilities),
    achievements: splitLines(job.achievements),
    skills_used: [],
  };
}

function sourceEditCandidateSnapshot() {
  const draft = getManualResumeDraft();
  return {
    ...manualDraftToCandidateProfile().canonical_profile,
    jobs: (draft.jobs || []).map(manualDraftJobToDisplay),
    education: (draft.education || []).map((item) => ({
      institution: item.institution || "",
      degree: item.degree || "",
      field: item.field || "",
      year: formatEducationYears(item),
      status: item.status || "unknown",
    })),
    languages: (draft.languages || []).map((item) => ({ name: item.name || "", level: item.level || "" })),
    skills_hard: splitDelimited(draft.skills_hard),
    skills_soft: splitDelimited(draft.skills_soft),
    target_role: draft.target_role || "",
    summary_raw: draft.summary_raw || "",
  };
}

function manualDraftToCandidateProfile() {
  const draft = getManualResumeDraft();
  const jobs = (draft.jobs || [])
    .map((job, index) => {
      const parsedPeriod = manualJobPeriodRange(job);
      const period = formatManualJobPeriod(job);
      return {
        id: index + 1,
        company_name: job.company_name?.trim() || null,
        company_type: job.company_type?.trim() || null,
        position: job.position?.trim() || null,
        period: period || null,
        start_date: parsedPeriod?.startDate || null,
        end_date: parsedPeriod?.endDate || null,
        is_current: parsedPeriod?.isCurrent || Boolean(job.is_current),
        responsibilities: splitLines(job.responsibilities),
        achievements: splitLines(job.achievements),
        skills_used: [],
        _manual_months: parsedPeriod?.months || null,
      };
    })
    .filter((job) => job.company_name || job.position || job.period || job.responsibilities.length || job.achievements.length);
  const education = (draft.education || [])
    .map((item) => ({
      institution: item.institution?.trim() || null,
      degree: item.degree?.trim() || null,
      field: item.field?.trim() || null,
      year: formatEducationYears(item) || null,
      status: item.status || "unknown",
    }))
    .filter((item) => item.institution || item.degree || item.field || item.year);
  const languages = (draft.languages || [])
    .map((item) => ({ name: item.name?.trim() || "", level: item.level?.trim() || null }))
    .filter((item) => item.name);
  const achievements = jobs.flatMap((job) => (
    job.achievements || []
  ).map((item) => ({
    company: job.company_name || "",
    text: item,
    metric: "",
    evidence: item,
    source: "manual_form",
  })));
  const skillsHard = splitDelimited(draft.skills_hard);
  const skillsSoft = splitDelimited(draft.skills_soft);
  const totalExperience = jobs.reduce((sum, job) => sum + (Number(job._manual_months) || 0), 0) || null;
  jobs.forEach((job) => {
    delete job._manual_months;
  });
  const highlightsByJob = jobs.map((job) => ({
    job_id: job.id,
    company: job.company_name ? [job.company_name] : [],
    position: job.position ? [job.position] : [],
    period: job.period ? [job.period] : [],
    highlights: [...job.achievements, ...job.responsibilities],
  }));

  return {
    canonical_profile: {
      target_role: draft.target_role?.trim() || null,
      experience_years: totalExperience ? Math.floor(totalExperience / 12) : null,
      experience_months: totalExperience,
      summary_raw: draft.summary_raw?.trim() || null,
      jobs,
      skills_hard: skillsHard,
      skills_soft: skillsSoft,
      education,
      languages,
      certifications: [],
      achievements,
    },
    evidence: {
      target_role: draft.target_role?.trim() ? [draft.target_role.trim()] : [],
      total_experience: totalExperience ? [`${totalExperience} месяцев`] : [],
      skills_section: skillsHard.length ? [skillsHard.join("; ")] : [],
      education: education.map((item, index) => [index + 1, item.institution, item.degree, item.field, item.year, item.status].filter(Boolean).join(" | ")),
      languages: languages.map((item) => [item.name, item.level].filter(Boolean).join(" | ")),
      achievements: achievements.map((item) => item.evidence || item.text).filter(Boolean),
      jobs: highlightsByJob,
    },
    provenance: {},
    ambiguities: [],
    confidence: {
      overall: "medium",
      target_role: draft.target_role ? "high" : "low",
      experience_years: totalExperience ? "medium" : "low",
      jobs: jobs.length ? "medium" : "low",
      skills: skillsHard.length ? "medium" : "low",
      education: education.length ? "medium" : "low",
      languages: languages.length ? "medium" : "low",
    },
    raw_warnings: totalExperience ? [] : ["Общий опыт не рассчитан: заполните периоды работы в местах работы."],
  };
}

function manualCandidateProfileToRawText(profile) {
  const canonical = profile.canonical_profile || {};
  const lines = [];
  if (canonical.target_role) lines.push("Целевая роль", canonical.target_role, "");
  if (canonical.experience_months) lines.push("Опыт", `${canonical.experience_months} месяцев`, "");
  if (canonical.summary_raw) lines.push("Сводка", canonical.summary_raw, "");
  if (canonical.jobs?.length) {
    lines.push("Опыт работы");
    canonical.jobs.forEach((job) => {
      lines.push([job.company_name, job.position, job.period].filter(Boolean).join(" | "));
      [...(job.responsibilities || []), ...(job.achievements || [])].forEach((item) => lines.push(`- ${item}`));
      lines.push("");
    });
  }
  if (canonical.skills_hard?.length) lines.push("Hard skills", canonical.skills_hard.join("; "), "");
  if (canonical.skills_soft?.length) lines.push("Soft skills", canonical.skills_soft.join("; "), "");
  if (canonical.education?.length) {
    lines.push("Образование");
    canonical.education.forEach((item) => lines.push([item.institution, item.degree, item.field, item.year].filter(Boolean).join(" | ")));
    lines.push("");
  }
  if (canonical.languages?.length) {
    lines.push("Языки");
    canonical.languages.forEach((item) => lines.push([item.name, item.level].filter(Boolean).join(" | ")));
  }
  return lines.join("\n").trim();
}

function adaptationListDisplayModel(adaptation) {
  return {
    id: adaptation.id,
    title: adaptation.title || "Адаптированное резюме",
    status: adaptation.status || "completed",
    createdAt: adaptation.created_at
      ? new Date(adaptation.created_at).toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
      : "",
  };
}

function adaptationDetailDisplayModel(adaptation) {
  const generated = adaptation?.generated_resume || {};
  return {
    id: adaptation?.id,
    title: adaptation?.title || generated.title || "Адаптированное резюме",
    summary: adaptation?.summary || "",
    vacancyProfile: adaptation?.vacancy_profile || {},
    strategyBrief: adaptation?.strategy_brief || {},
    generatedResume: generated,
    technicalReport: adaptation?.technical_report || generated.technical_report || {},
    resumeText: generated.text || adaptation?.generated_resume_text || "",
  };
}

function vacancySourceLabel(source) {
  const labels = {
    getmatch: "GetMatch",
    openhunt: "OpenHunt",
    yandex: "Яндекс",
    sber: "Сбер",
    generic: "Другое",
  };
  return labels[source] || source || "Источник";
}

function externalVacancyDisplayModel(vacancy) {
  return {
    id: vacancy.id,
    source: vacancy.source || "generic",
    sourceLabel: vacancySourceLabel(vacancy.source),
    title: vacancy.title || "Вакансия",
    company: vacancy.company || "",
    location: vacancy.location || "",
    salary: vacancy.salary || "",
    description: vacancy.description || vacancy.summary || "",
    normalizedText: vacancy.normalized_text || "",
    sourceUrl: vacancy.source_url || "",
  };
}

function filteredExternalVacancies() {
  const query = state.vacancySearch.trim().toLowerCase();
  return (state.recommendedVacancies || [])
    .map(externalVacancyDisplayModel)
    .filter((item) => {
      const sourceMatches = state.vacancySourceFilter === "all" || item.source === state.vacancySourceFilter;
      if (!sourceMatches) {
        return false;
      }
      if (!query) {
        return true;
      }
      return [item.title, item.company, item.location, item.description]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
}

function cabinetNav() {
  const items = [
    ["resume", "◎", "Моё резюме", "базовый профиль"],
    ["adaptations", "◫", "Адаптации", "версии под вакансии"],
    ["new", "＋", "Новая адаптация", "без повторной загрузки"],
  ];
  if (state.currentAdaptation || state.pendingAdaptation) {
    items.push(["detail", "↗", "Карточка адаптации", "резюме + анализ"]);
  }

  return `
    <aside class="cabinet-rail">
      ${items.map(([view, icon, title, subtitle]) => `
        <button class="cabinet-nav-item ${state.cabinetView === view ? "active" : ""}" data-cabinet-view="${view}" type="button">
          <div class="cabinet-nav-ico">${icon}</div>
          <div class="cabinet-nav-copy"><b>${escapeHtml(title)}</b><span>${escapeHtml(subtitle)}</span></div>
        </button>
      `).join("")}
    </aside>
  `;
}

function renderVacancyRecommendationsRail() {
  const vacancies = filteredExternalVacancies();
  const sourceOptions = Array.from(new Set((state.recommendedVacancies || []).map((item) => item.source).filter(Boolean)));
  return `
    <aside class="cabinet-vacancy-rail">
      <div class="cabinet-vacancy-head">
        <h3>Рекомендации для вас</h3>
        <p>Подходящие вакансии рядом с рабочей зоной.</p>
      </div>
      <input
        class="cabinet-vacancy-search"
        id="vacancyRecommendationSearch"
        placeholder="Поиск по названию или компании"
        value="${escapeHtml(state.vacancySearch)}"
      />
      <select class="cabinet-source-select" id="vacancySourceFilter">
        <option value="all"${state.vacancySourceFilter === "all" ? " selected" : ""}>Источник ▾</option>
        ${sourceOptions.map((source) => `<option value="${escapeHtml(source)}"${state.vacancySourceFilter === source ? " selected" : ""}>${escapeHtml(vacancySourceLabel(source))}</option>`).join("")}
      </select>
      <div class="cabinet-vacancy-list">
        ${vacancies.length ? vacancies.map((item) => `
          <article class="cabinet-vacancy-card">
            <div class="cabinet-vacancy-top">
              <div>
                <h4>${escapeHtml(item.title)}</h4>
                <div class="cabinet-vacancy-meta">${escapeHtml([item.company, item.location].filter(Boolean).join(" · ") || "Компания не указана")}</div>
              </div>
              <span class="cabinet-vacancy-source">${escapeHtml(item.sourceLabel)}</span>
            </div>
            <p>${escapeHtml(item.description || "Описание сохранено в snapshot вакансии.")}</p>
            <div class="cabinet-vacancy-actions">
              <button class="cabinet-tiny-btn" data-open-external-vacancy="${item.id}" type="button">Открыть</button>
              <button class="cabinet-tiny-btn dark" data-adapt-external-vacancy="${item.id}" type="button" ${state.vacancyAdaptingId === item.id ? "disabled" : ""}>
                ${state.vacancyAdaptingId === item.id ? "Готовим..." : "Адаптировать"}
              </button>
            </div>
          </article>
        `).join("") : `
          <div class="cabinet-vacancy-empty">Пока нет рекомендаций. Сохраните базовое резюме, и система подберёт вакансии из OpenHunt и GetMatch.</div>
        `}
      </div>
    </aside>
  `;
}

function cabinetShell(contentHtml) {
  return `
    <div class="cabinet-workspace">
      ${cabinetNav()}
      <section class="cabinet-screen">
        ${contentHtml}
      </section>
      ${renderVacancyRecommendationsRail()}
    </div>
  `;
}

function cabinetHero(title, subtitle, actionsHtml = "", breadcrumb = "Кабинет") {
  return `
    <div class="cabinet-breadcrumb">${escapeHtml(breadcrumb)}</div>
    <div class="cabinet-hero">
      <div>
        <h1>${escapeHtml(title)}</h1>
        ${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ""}
      </div>
      ${actionsHtml ? `<div class="cabinet-actions">${actionsHtml}</div>` : ""}
    </div>
  `;
}

function renderSourceTextEditor(type, title, value, multiline = false) {
  return `
    <form class="source-block-editor" data-source-block-form="${escapeHtml(type)}">
      <label>${escapeHtml(title)}
        ${multiline
    ? `<textarea class="cabinet-textarea manual-small-textarea" data-source-field="value">${escapeHtml(value || "")}</textarea>`
    : `<input class="auth-input" data-source-field="value" value="${escapeHtml(value || "")}">`}
      </label>
      ${sourceBlockEditorActions()}
    </form>
  `;
}

function renderSourceJobEditor(job, index) {
  return `
    <form class="source-block-editor" data-source-block-form="job" data-edit-index="${index}">
      <div class="manual-grid">
        <label>Компания
          <input class="auth-input" data-source-field="company_name" value="${escapeHtml(job.company_name)}">
        </label>
        <label>Тип компании
          <input class="auth-input" data-source-field="company_type" value="${escapeHtml(job.company_type)}">
        </label>
        <label>Должность
          <input class="auth-input" data-source-field="position" value="${escapeHtml(job.position)}">
        </label>
      </div>
      <div class="manual-period-grid">
        <div>
          <div class="manual-period-title">Начало работы</div>
          <div class="manual-grid manual-date-grid">
            <label>Месяц
              <select class="auth-input" data-source-field="start_month">${monthSelectOptions(job.start_month)}</select>
            </label>
            <label>Год
              <select class="auth-input" data-source-field="start_year">${yearSelectOptions(job.start_year)}</select>
            </label>
          </div>
        </div>
        <div>
          <div class="manual-period-title">Окончание работы</div>
          <div class="manual-grid manual-date-grid">
            <label>Месяц
              <select class="auth-input" data-source-field="end_month" ${job.is_current ? "disabled" : ""}>${monthSelectOptions(job.end_month)}</select>
            </label>
            <label>Год
              <select class="auth-input" data-source-field="end_year" ${job.is_current ? "disabled" : ""}>${yearSelectOptions(job.end_year)}</select>
            </label>
          </div>
          <label class="manual-checkbox">
            <input type="checkbox" data-source-field="is_current" ${job.is_current ? "checked" : ""}>
            <span>Работаю сейчас</span>
          </label>
        </div>
      </div>
      <label>Обязанности / факты, по одному на строку
        <textarea class="cabinet-textarea manual-small-textarea" data-source-field="responsibilities">${escapeHtml(job.responsibilities)}</textarea>
      </label>
      <label>Достижения, по одному на строку
        <textarea class="cabinet-textarea manual-small-textarea" data-source-field="achievements">${escapeHtml(job.achievements)}</textarea>
      </label>
      ${sourceBlockEditorActions()}
    </form>
  `;
}

function renderSourceEducationEditor(item, index) {
  return `
    <form class="source-block-editor" data-source-block-form="education" data-edit-index="${index}">
      <div class="manual-grid">
        <input class="auth-input" data-source-field="institution" value="${escapeHtml(item.institution)}" placeholder="Учебное заведение">
        <input class="auth-input" data-source-field="degree" value="${escapeHtml(item.degree)}" placeholder="Степень">
        <input class="auth-input" data-source-field="field" value="${escapeHtml(item.field)}" placeholder="Направление">
      </div>
      <div class="manual-grid manual-education-years">
        <label>Год начала
          <select class="auth-input" data-source-field="start_year">${educationYearSelectOptions(item.start_year)}</select>
        </label>
        <label>Год окончания
          <select class="auth-input" data-source-field="end_year">${educationYearSelectOptions(item.end_year)}</select>
        </label>
      </div>
      ${sourceBlockEditorActions()}
    </form>
  `;
}

function renderSourceLanguageEditor(item, index) {
  return `
    <form class="source-block-editor" data-source-block-form="language" data-edit-index="${index}">
      <div class="manual-grid">
        <select class="auth-input" data-source-field="name">${selectOptions(manualLanguageOptions, item.name, "Язык")}</select>
        <select class="auth-input" data-source-field="level">${selectOptions(manualLanguageLevelOptions, item.level, "Уровень")}</select>
      </div>
      ${sourceBlockEditorActions()}
    </form>
  `;
}

function renderSourceSkillsEditor(draft) {
  return `
    <form class="source-block-editor" data-source-block-form="skills">
      <div class="manual-grid">
        <label>Hard skills, через ;
          <textarea class="cabinet-textarea manual-small-textarea" data-source-field="skills_hard">${escapeHtml(draft.skills_hard)}</textarea>
        </label>
        <label>Soft / управленческие навыки, через ;
          <textarea class="cabinet-textarea manual-small-textarea" data-source-field="skills_soft">${escapeHtml(draft.skills_soft)}</textarea>
        </label>
      </div>
      ${sourceBlockEditorActions()}
    </form>
  `;
}

function renderCandidateBasics(candidate, editable) {
  return `
    <div class="cabinet-stack" style="margin-top:18px">
      <div class="cabinet-row-line">
        <b>Целевая роль</b>
        ${sourceEditBlockMatches("target_role")
    ? renderSourceTextEditor("target_role", "Целевая роль", getManualResumeDraft().target_role, false)
    : `<span>${escapeHtml(candidate.target_role || "не указана")}</span>${editable ? sourceEditButton("target_role") : ""}`}
      </div>
      <div class="cabinet-row-line"><b>Общий опыт</b><span>${escapeHtml(formatExperience(candidate))}</span></div>
      <div class="cabinet-row-line">
        <b>Сводка профиля</b>
        ${sourceEditBlockMatches("summary")
    ? renderSourceTextEditor("summary", "Сводка профиля", getManualResumeDraft().summary_raw, true)
    : `<span>${escapeHtml(candidate.summary_raw || "не указана")}</span>${editable ? sourceEditButton("summary") : ""}`}
      </div>
    </div>
  `;
}

function renderCabinetJobs(jobs, evidence, editable = false) {
  const draft = getManualResumeDraft();
  const displayJobs = editable ? (draft.jobs || []).map(manualDraftJobToDisplay) : jobs;
  if (!jobs?.length) {
    return `
      ${sourceSectionHead("Опыт работы", editable, "job")}
      <div class="cabinet-empty">Опыт работы пока не распознан.</div>
    `;
  }
  const evidenceJobs = evidence?.jobs || [];
  return `
    ${sourceSectionHead("Опыт работы", editable, "job")}
    <div class="cabinet-job-list">
      ${displayJobs.map((job, index) => {
    const draftJob = draft.jobs?.[index] || emptyManualJob(index + 1);
    if (editable && sourceEditBlockMatches("job", index)) {
      return `<article class="cabinet-job-card">${renderSourceJobEditor(draftJob, index)}</article>`;
    }
    const evidenceJob = evidenceJobs.find((item) => Number(item.job_id) === Number(job.id));
    const bullets = asList([
      ...(job.achievements || []),
      ...(job.responsibilities || []),
      ...(evidenceJob?.highlights || []),
    ]);
    const skillsUsed = asList(job.skills_used);
    return `
          <article class="cabinet-job-card">
            <div class="cabinet-job-head">
              <div>
                <b>${escapeHtml([job.position, job.company_name].filter(Boolean).join(" — ") || "Место работы")}</b>
                <span>${escapeHtml([job.period, job.company_type].filter(Boolean).join(" · "))}</span>
              </div>
              <div class="cabinet-edit-actions">
                <div class="cabinet-badge">${index === 0 ? "Основной опыт" : "Поддерживающий опыт"}</div>
                ${editable ? `${sourceEditButton("job", "✎", index)}${sourceDeleteButton("job", index)}` : ""}
              </div>
            </div>
            ${bullets.length ? `<ul>${bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
            ${skillsUsed.length ? `<div class="cabinet-chip-row cabinet-chip-row-compact">${skillsUsed.map((skill) => `<span>${escapeHtml(skill)}</span>`).join("")}</div>` : ""}
          </article>
        `;
  }).join("")}
    </div>
  `;
}

function formatCandidateAchievement(item) {
  if (!item) {
    return "";
  }
  if (typeof item === "string") {
    return item;
  }
  const metric = item.metric ? ` (${item.metric})` : "";
  const company = item.company ? `${item.company}: ` : "";
  return `${company}${item.text || item.evidence || ""}${metric}`;
}

function renderCandidateAchievements(candidate, evidence) {
  const achievements = asRawList(candidate?.achievements)
    .map(formatCandidateAchievement)
    .filter(Boolean);
  const evidenceAchievements = asList(evidence?.achievements);
  const seen = new Set();
  const values = [...achievements, ...evidenceAchievements].filter((item) => {
    const key = String(item || "")
      .toLowerCase()
      .replace(/\s*\([^)]*\)\s*$/g, "")
      .replace(/\s+/g, " ")
      .trim();
    if (!key || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
  if (!values.length) {
    return "";
  }
  return `
    <div class="cabinet-card cabinet-span-12">
      <h2>Ключевые достижения</h2>
      <ul class="cabinet-info-list">
        ${values.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </div>
  `;
}

function renderCabinetProfileSignals(candidate, editable = false) {
  const draft = getManualResumeDraft();
  const hardSkills = asList(candidate.skills_hard);
  const softSkills = asList(candidate.skills_soft);
  const languages = asRawList(candidate.languages)
    .map((item) => typeof item === "string" ? item : [item.name, item.level].filter(Boolean).join(" — "))
    .filter(Boolean);
  const education = asRawList(candidate.education)
    .map((item) => typeof item === "string" ? item : [item.institution, item.degree, item.field, item.year, item.status && item.status !== "unknown" ? item.status : ""].filter(Boolean).join(" · "))
    .filter(Boolean);

  return `
    <div class="cabinet-card cabinet-span-12">
      ${sourceSectionHead("Образование", editable, "education")}
      <div class="cabinet-stack" style="margin-top:14px">
        ${editable ? (draft.education || []).map((item, index) => `
          <div class="cabinet-row-line">
            <b>Образование ${index + 1}</b>
            ${sourceEditBlockMatches("education", index)
    ? renderSourceEducationEditor(item, index)
    : `<span>${escapeHtml([item.institution, item.degree, item.field, formatEducationYears(item)].filter(Boolean).join(" · ") || "не указано")}</span><span class="cabinet-edit-actions">${sourceEditButton("education", "✎", index)}${sourceDeleteButton("education", index)}</span>`}
          </div>
        `).join("") : `<div class="cabinet-row-line"><b>Образование</b><span>${escapeHtml(education.join(" | ") || "не указано")}</span></div>`}
      </div>
    </div>
    <div class="cabinet-card cabinet-span-12">
      ${sourceSectionHead("Языки", editable, "language")}
      <div class="cabinet-stack" style="margin-top:14px">
        ${editable ? (draft.languages || []).map((item, index) => `
          <div class="cabinet-row-line">
            <b>Язык ${index + 1}</b>
            ${sourceEditBlockMatches("language", index)
    ? renderSourceLanguageEditor(item, index)
    : `<span>${escapeHtml([item.name, item.level].filter(Boolean).join(" — ") || "не указан")}</span><span class="cabinet-edit-actions">${sourceEditButton("language", "✎", index)}${sourceDeleteButton("language", index)}</span>`}
          </div>
        `).join("") : `<div class="cabinet-row-line"><b>Языки</b><span>${escapeHtml(languages.join(" · ") || "не указаны")}</span></div>`}
      </div>
    </div>
    <div class="cabinet-card cabinet-span-12">
      <div class="cabinet-section-head">
        <h2>Навыки</h2>
        ${editable ? sourceEditButton("skills") : ""}
      </div>
      ${sourceEditBlockMatches("skills") ? renderSourceSkillsEditor(draft) : `
        ${hardSkills.length ? `<div class="cabinet-chip-row">${hardSkills.map((skill) => `<span>${escapeHtml(skill)}</span>`).join("")}</div>` : `<div class="cabinet-empty">Hard skills пока не распознаны.</div>`}
        ${softSkills.length ? `
          <h3 class="cabinet-subtitle">Управленческие и рабочие навыки</h3>
          <div class="cabinet-chip-row">${softSkills.map((skill) => `<span>${escapeHtml(skill)}</span>`).join("")}</div>
        ` : ""}
      `}
    </div>
  `;
}

function renderManualResumeForm() {
  const draft = getManualResumeDraft();
  const isEditMode = Boolean(state.sourceResume?.id);
  return `
    <div class="cabinet-card cabinet-span-12 manual-resume-card">
      <div class="manual-resume-head">
        <div>
          <h2>${isEditMode ? "Редактировать базовое резюме" : "Создать резюме вручную"}</h2>
          <p>${isEditMode ? "Измените сохранённый source profile. Будущие адаптации будут использовать обновлённые данные." : "Заполните базовый профиль. Эти данные станут source profile для будущих адаптаций."}</p>
        </div>
      </div>
      <form id="manualResumeForm" class="manual-resume-form">
        <label>Целевая роль
          <input class="auth-input" data-manual-field="target_role" value="${escapeHtml(draft.target_role)}" placeholder="Например: Продуктовый аналитик">
        </label>
        <label>Сводка профиля
          <textarea class="cabinet-textarea manual-small-textarea" data-manual-field="summary_raw" placeholder="2-3 предложения о вашем опыте">${escapeHtml(draft.summary_raw)}</textarea>
        </label>

        <div class="manual-section">
          <div class="manual-section-title">
            <h3>Опыт работы</h3>
            <button class="cabinet-mini-btn" data-add-manual-job type="button">Добавить место</button>
          </div>
          ${(draft.jobs || []).map((job, index) => `
            <article class="manual-repeat-card">
              <div class="manual-repeat-head">
                <b>Место работы ${index + 1}</b>
                ${(draft.jobs || []).length > 1 ? `<button class="cabinet-tiny-btn" data-remove-manual-job="${index}" type="button">Удалить</button>` : ""}
              </div>
              <div class="manual-grid">
                <label>Компания
                  <input class="auth-input" data-manual-job="${index}" data-job-field="company_name" value="${escapeHtml(job.company_name)}">
                </label>
                <label>Тип компании
                  <input class="auth-input" data-manual-job="${index}" data-job-field="company_type" value="${escapeHtml(job.company_type)}" placeholder="bank, fintech, retail...">
                </label>
                <label>Должность
                  <input class="auth-input" data-manual-job="${index}" data-job-field="position" value="${escapeHtml(job.position)}">
                </label>
              </div>
              <div class="manual-period-grid">
                <div>
                  <div class="manual-period-title">Начало работы</div>
                  <div class="manual-grid manual-date-grid">
                    <label>Месяц
                      <select class="auth-input" data-manual-job="${index}" data-job-field="start_month">
                        ${monthSelectOptions(job.start_month)}
                      </select>
                    </label>
                    <label>Год
                      <select class="auth-input" data-manual-job="${index}" data-job-field="start_year">
                        ${yearSelectOptions(job.start_year)}
                      </select>
                    </label>
                  </div>
                </div>
                <div>
                  <div class="manual-period-title">Окончание работы</div>
                  <div class="manual-grid manual-date-grid">
                    <label>Месяц
                      <select class="auth-input" data-manual-job="${index}" data-job-field="end_month" ${job.is_current ? "disabled" : ""}>
                        ${monthSelectOptions(job.end_month)}
                      </select>
                    </label>
                    <label>Год
                      <select class="auth-input" data-manual-job="${index}" data-job-field="end_year" ${job.is_current ? "disabled" : ""}>
                        ${yearSelectOptions(job.end_year)}
                      </select>
                    </label>
                  </div>
                  <label class="manual-checkbox">
                    <input type="checkbox" data-manual-job="${index}" data-job-field="is_current" ${job.is_current ? "checked" : ""}>
                    <span>Работаю сейчас</span>
                  </label>
                </div>
              </div>
              <label>Обязанности / факты, по одному на строку
                <textarea class="cabinet-textarea manual-small-textarea" data-manual-job="${index}" data-job-field="responsibilities">${escapeHtml(job.responsibilities)}</textarea>
              </label>
              <label>Достижения, по одному на строку
                <textarea class="cabinet-textarea manual-small-textarea" data-manual-job="${index}" data-job-field="achievements">${escapeHtml(job.achievements)}</textarea>
              </label>
            </article>
          `).join("")}
        </div>

        <div class="manual-grid">
          <label>Hard skills, через ;
            <textarea class="cabinet-textarea manual-small-textarea" data-manual-field="skills_hard">${escapeHtml(draft.skills_hard)}</textarea>
          </label>
          <label>Soft / управленческие навыки, через ;
            <textarea class="cabinet-textarea manual-small-textarea" data-manual-field="skills_soft">${escapeHtml(draft.skills_soft)}</textarea>
          </label>
        </div>

        <div class="manual-section">
          <div class="manual-section-title">
            <h3>Образование</h3>
            <button class="cabinet-mini-btn" data-add-manual-education type="button">Добавить</button>
          </div>
          ${(draft.education || []).map((item, index) => `
            <article class="manual-repeat-card compact">
              <div class="manual-repeat-head">
                <b>Образование ${index + 1}</b>
                ${(draft.education || []).length > 1 ? `<button class="cabinet-tiny-btn" data-remove-manual-education="${index}" type="button">Удалить</button>` : ""}
              </div>
              <div class="manual-grid">
                <input class="auth-input" data-manual-education="${index}" data-education-field="institution" value="${escapeHtml(item.institution)}" placeholder="Учебное заведение">
                <input class="auth-input" data-manual-education="${index}" data-education-field="degree" value="${escapeHtml(item.degree)}" placeholder="Степень">
                <input class="auth-input" data-manual-education="${index}" data-education-field="field" value="${escapeHtml(item.field)}" placeholder="Направление">
              </div>
              <div class="manual-grid manual-education-years">
                <label>Год начала
                  <select class="auth-input" data-manual-education="${index}" data-education-field="start_year">
                    ${educationYearSelectOptions(item.start_year)}
                  </select>
                </label>
                <label>Год окончания
                  <select class="auth-input" data-manual-education="${index}" data-education-field="end_year">
                    ${educationYearSelectOptions(item.end_year)}
                  </select>
                </label>
              </div>
            </article>
          `).join("")}
        </div>

        <div class="manual-section">
          <div class="manual-section-title">
            <h3>Языки</h3>
            <button class="cabinet-mini-btn" data-add-manual-language type="button">Добавить</button>
          </div>
          ${(draft.languages || []).map((item, index) => `
            <div class="manual-grid manual-language-row">
              <select class="auth-input" data-manual-language="${index}" data-language-field="name">
                ${selectOptions(manualLanguageOptions, item.name, "Язык")}
              </select>
              <select class="auth-input" data-manual-language="${index}" data-language-field="level">
                ${selectOptions(manualLanguageLevelOptions, item.level, "Уровень")}
              </select>
              ${(draft.languages || []).length > 1 ? `<button class="cabinet-tiny-btn" data-remove-manual-language="${index}" type="button">Удалить</button>` : ""}
            </div>
          `).join("")}
        </div>

        <div class="cta-inline">
          <button class="btn btn-primary" type="submit" ${state.manualResumeSubmitting ? "disabled" : ""}>
            ${state.manualResumeSubmitting ? "Сохраняем..." : (isEditMode ? "Сохранить изменения" : "Сохранить базовое резюме")}
          </button>
          <button class="btn btn-secondary" id="cancelManualResume" type="button" ${state.manualResumeSubmitting ? "disabled" : ""}>Отмена</button>
        </div>
        ${state.manualResumeSubmitting ? `
          <div class="cabinet-progress-card" role="status" aria-live="polite">
            <div class="cabinet-spinner"></div>
            <div>
              <b>Сохраняем профиль</b>
              <p>Проверяем структуру и сохраняем её как базовое резюме для будущих адаптаций.</p>
            </div>
          </div>
        ` : ""}
      </form>
    </div>
  `;
}

function renderCabinetResumeScreen() {
  const model = sourceResumeDisplayModel(state.sourceResume);
  const hasSourceResume = Boolean(model.id);
  const showManualForm = state.sourceResumeMode === "manual";
  const isInlineEditable = hasSourceResume && !showManualForm;
  const candidate = isInlineEditable ? sourceEditCandidateSnapshot() : (model.candidate || {});
  const jobs = candidate.jobs || [];
  const isSourceBusy = state.sourceResumeSelecting || state.sourceResumeUpdating || state.manualResumeSubmitting;

  const content = `
    ${cabinetHero(
    "Моё резюме",
    "Это базовый профиль кандидата. Он используется как source для всех новых адаптаций.",
    hasSourceResume && !showManualForm ? `
        <button class="btn btn-secondary" id="cabinetUploadResume" type="button" ${isSourceBusy ? "disabled" : ""}>
          ${state.sourceResumeUpdating ? "Загружаем..." : state.sourceResumeSelecting ? "Выберите файл..." : "Загрузить новый файл"}
        </button>
        <button class="btn btn-primary" data-cabinet-view="new" type="button" ${isSourceBusy ? "disabled" : ""}>Создать новую адаптацию</button>
      ` : (!hasSourceResume ? `
        <button class="btn btn-secondary" id="cabinetUploadResume" type="button" ${isSourceBusy ? "disabled" : ""}>
          ${state.sourceResumeUpdating ? "Загружаем..." : state.sourceResumeSelecting ? "Выберите файл..." : "Загрузить резюме"}
        </button>
        <button class="btn btn-primary" id="cabinetCreateManualResume" type="button" ${isSourceBusy ? "disabled" : ""}>Создать резюме</button>
      ` : ""),
    "Кабинет / Моё резюме"
  )}
    <input type="file" id="cabinetSourceFile" hidden accept=".txt,.pdf,.doc,.docx" />
    ${showManualForm ? `<div class="cabinet-grid">${renderManualResumeForm()}</div>` : ""}
    ${hasSourceResume && !showManualForm ? `
      <div class="cabinet-grid">
        <div class="cabinet-card cabinet-span-12">
          <div class="file-chip">${escapeHtml(model.fileName)}${model.updatedAt ? ` · обновлено ${escapeHtml(model.updatedAt)}` : ""}</div>
          ${isSourceBusy ? `
            <div class="cabinet-progress-card" role="status" aria-live="polite">
              <div class="cabinet-spinner"></div>
              <div>
                <b>${state.sourceResumeUpdating ? "Обновляем базовое резюме" : "Выберите файл резюме"}</b>
                <p>${state.sourceResumeUpdating ? "Извлекаем текст, заново строим профиль кандидата и сохраняем его для будущих адаптаций." : "После выбора файла сервис сразу начнёт обновление профиля."}</p>
              </div>
            </div>
          ` : ""}
          ${renderCandidateBasics(candidate, isInlineEditable)}
          ${renderCabinetJobs(jobs, model.evidence, isInlineEditable)}
        </div>
        ${renderCabinetProfileSignals(candidate, isInlineEditable)}
      </div>
    ` : !showManualForm ? `
      <div class="cabinet-grid">
        <div class="cabinet-card cabinet-span-12">
          <div class="cabinet-empty">
            Базовое резюме ещё не сохранено. Вы можете загрузить файл с резюме или создать профиль вручную кнопками выше.
          </div>
        </div>
      </div>
    ` : ""}
  `;
  return cabinetShell(content);
}

function renderCabinetAdaptationsScreen() {
  const cards = state.adaptations.length
    ? state.adaptations.map((item) => {
      const model = adaptationListDisplayModel(item);
      return `
        <article class="cabinet-adaptation-card">
          <div>
            <h3>${escapeHtml(model.title)}</h3>
            ${model.createdAt ? `<p>${escapeHtml(model.createdAt)}</p>` : ""}
          </div>
          <div class="cabinet-actions-col">
            <button class="cabinet-mini-btn" data-open-adaptation="${model.id}" type="button">Открыть</button>
            <button class="cabinet-mini-btn" data-download-adaptation="${model.id}" type="button">Скачать PDF</button>
            <button class="cabinet-mini-btn" data-regenerate-adaptation="${model.id}" type="button">Перегенерировать</button>
          </div>
        </article>
      `;
    }).join("")
    : `<div class="cabinet-empty">Адаптаций пока нет. Создайте первую версию под вакансию.</div>`;

  return cabinetShell(`
    ${cabinetHero(
    "Адаптации",
    "",
    `<button class="btn btn-primary" data-cabinet-view="new" type="button">Новая адаптация</button>`,
    "Кабинет / Адаптации"
  )}
    <div class="cabinet-adaptation-list">${cards}</div>
  `);
}

function renderCabinetNewAdaptationScreen() {
  const fetched = state.fetchedVacancy;
  const canRunUrlAdaptation = state.newAdaptationMode === "url" && fetched?.success && fetched.normalized_text;
  return cabinetShell(`
    ${cabinetHero("Новая адаптация", "", "", "Кабинет / Адаптации / Новая адаптация")}
    <div class="cabinet-grid">
      <div class="cabinet-card cabinet-span-12">
        <h2>Вакансия</h2>
        <div class="cabinet-tabs">
          <button class="cabinet-tab ${state.newAdaptationMode === "url" ? "active" : ""}" data-adaptation-mode="url" type="button">Ссылка</button>
          <button class="cabinet-tab ${state.newAdaptationMode === "text" ? "active" : ""}" data-adaptation-mode="text" type="button">Вставить текст</button>
        </div>
        ${state.newAdaptationMode === "text" ? `
          <textarea class="cabinet-textarea" id="cabinetVacancyText" placeholder="Вставьте описание вакансии сюда...">${escapeHtml(state.newAdaptationText)}</textarea>
        ` : `
          <div class="cabinet-note" style="margin-top:14px">
            Вставьте ссылку на одну вакансию.
          </div>
          <div class="cabinet-url-box">
            <input class="auth-input" id="cabinetVacancyUrl" type="url" placeholder="https://getmatch.ru/vacancies/..." value="${escapeHtml(state.newAdaptationUrl)}" ${state.vacancyFetching || state.adaptationSubmitting ? "disabled" : ""}>
            <button class="btn btn-secondary" id="fetchCabinetVacancy" type="button" ${state.vacancyFetching || state.adaptationSubmitting ? "disabled" : ""}>
              ${state.vacancyFetching ? "Получаем..." : "Получить вакансию"}
            </button>
          </div>
          ${state.vacancyFetching ? `
            <div class="cabinet-progress-card" role="status" aria-live="polite">
              <div class="cabinet-spinner"></div>
              <div>
                <b>Получаем вакансию по ссылке</b>
                <p>Открываем страницу, извлекаем заголовок, компанию и описание. Если сайт закрыт антиботом, предложим ручной ввод.</p>
              </div>
            </div>
          ` : ""}
          ${state.vacancyFetchError ? `
            <div class="auth-error" style="margin-top:14px">
              ${escapeHtml(state.vacancyFetchError)}
              <button class="cabinet-inline-link" id="fallbackToVacancyText" type="button">Вставить текст вручную</button>
            </div>
          ` : ""}
          ${fetched?.success ? `
            <div class="cabinet-vacancy-preview">
              <b>${escapeHtml(fetched.title || "Вакансия получена")}</b>
              ${fetched.company ? `<span>${escapeHtml(fetched.company)}</span>` : ""}
              <p>${escapeHtml((fetched.description || fetched.normalized_text || "").slice(0, 520))}${(fetched.description || "").length > 520 ? "..." : ""}</p>
              ${(fetched.warnings || []).length ? `<ul>${fetched.warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
            </div>
            <div class="cabinet-url-text-fallback">
              <textarea class="cabinet-textarea" id="cabinetFetchedVacancyText" placeholder="При необходимости можно поправить извлечённый текст перед запуском...">${escapeHtml(fetched.normalized_text || "")}</textarea>
              <div>
                <p class="cabinet-small-note">Этот текст будет передан в VacancyAnalyzer и сохранён в adaptation snapshot.</p>
              </div>
            </div>
          ` : ""}
        `}
        <div class="cta-inline">
          <button class="btn btn-primary" id="runCabinetAdaptation" type="button" ${state.adaptationSubmitting || state.vacancyFetching || (state.newAdaptationMode === "url" && !canRunUrlAdaptation) ? "disabled" : ""}>
            ${state.adaptationSubmitting ? "Адаптация запускается..." : "Запустить адаптацию"}
          </button>
          <button class="btn btn-secondary" id="draftCabinetAdaptation" type="button" ${state.adaptationSubmitting ? "disabled" : ""}>Черновик</button>
        </div>
        ${state.adaptationSubmitting ? `
          <div class="cabinet-progress-card" role="status" aria-live="polite">
            <div class="cabinet-spinner"></div>
            <div>
              <b>Готовим адаптацию</b>
              <p>Анализируем вакансию, строим стратегию и собираем новую версию резюме. Обычно это занимает несколько секунд.</p>
            </div>
          </div>
        ` : ""}
      </div>
    </div>
  `);
}

function renderCabinetProfileCard(title, html) {
  return `<div class="cabinet-card"><h2>${escapeHtml(title)}</h2>${html}</div>`;
}

function renderAuth() {
  if (!authRoot) {
    return;
  }
  const isRegister = state.authMode === "register";
  authRoot.innerHTML = `
    <div class="auth-shell">
      <article class="auth-card">
        <h1>${isRegister ? "Создайте аккаунт" : "Войдите в кабинет"}</h1>
        <p>${isRegister
      ? "После регистрации начнём с базового резюме: оно станет основой для всех будущих адаптаций."
      : "Войдите, чтобы открыть сохранённое резюме и адаптации под вакансии."}</p>
        <form class="auth-form" id="authForm">
          ${state.authError ? `<div class="auth-error">${escapeHtml(state.authError)}</div>` : ""}
          <input class="auth-input" id="authEmail" name="email" type="text" inputmode="email" placeholder="Email" autocomplete="email" required />
          <input class="auth-input" id="authPassword" name="password" type="password" placeholder="Пароль" autocomplete="${isRegister ? "new-password" : "current-password"}" required />
          ${isRegister ? `<input class="auth-input" id="authPasswordConfirm" name="password_confirm" type="password" placeholder="Повторите пароль" autocomplete="new-password" required />` : ""}
          <button class="btn btn-primary" id="authSubmit" type="submit">${isRegister ? "Создать аккаунт" : "Войти"}</button>
        </form>
        <div class="auth-switch">
          ${isRegister ? "Уже есть аккаунт?" : "Нет аккаунта?"}
          <button class="auth-link" id="authSwitch" type="button">${isRegister ? "Войти" : "Зарегистрироваться"}</button>
        </div>
      </article>
    </div>
  `;

  document.getElementById("authSwitch").onclick = () => {
    state.authError = "";
    state.authMode = isRegister ? "login" : "register";
    renderAuth();
  };

  document.getElementById("authForm").onsubmit = async (event) => {
    event.preventDefault();
    const submit = document.getElementById("authSubmit");
    submit.disabled = true;
    submit.textContent = "Подождите...";
    try {
      const fields = {
        email: document.getElementById("authEmail").value,
        password: document.getElementById("authPassword").value,
      };
      if (isRegister) {
        fields.password_confirm = document.getElementById("authPasswordConfirm").value;
      }
      await submitAuth(isRegister ? "register" : "login", fields);
    } catch (error) {
      state.authError = error.message;
      renderAuth();
    }
  };
}

function renderCabinetAdaptationDetailScreen() {
  if (state.pendingAdaptation) {
    const pending = state.pendingAdaptation;
    return cabinetShell(`
      ${cabinetHero(
      "Карточка адаптации",
      "",
      "",
      `Кабинет / Адаптации / ${pending.title || "Новая адаптация"}`
    )}
      <div class="cabinet-grid">
        <div class="cabinet-span-12">
          <div class="cabinet-resume-view cabinet-pending-adaptation">
            <h2>${escapeHtml(pending.title || "Готовим адаптацию")}</h2>
            <div class="role">${escapeHtml([pending.company, pending.sourceLabel].filter(Boolean).join(" · ") || "Анализ вакансии")}</div>
            <div class="cabinet-progress-card">
              <div class="cabinet-spinner"></div>
              <div>
                <b>Готовим вакансию</b>
                <p>Анализируем вакансию, строим стратегию и собираем резюме. Готовый результат появится здесь автоматически.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    `);
  }

  const model = adaptationDetailDisplayModel(state.currentAdaptation);
  if (!state.currentAdaptation) {
    return cabinetShell(`
      ${cabinetHero("Карточка адаптации", "", "", "Кабинет / Адаптации")}
      <div class="cabinet-empty">Выберите адаптацию из списка.</div>
    `);
  }

  const vacancy = model.vacancyProfile;
  const strategy = model.strategyBrief;
  const report = model.technicalReport;
  return cabinetShell(`
    ${cabinetHero(
    "Карточка адаптации",
    "",
    `
        <button class="btn btn-secondary" data-cabinet-view="adaptations" type="button">Назад к адаптациям</button>
        <button class="btn btn-secondary" data-regenerate-adaptation="${model.id}" type="button">Перегенерировать</button>
        <button class="btn btn-primary" data-download-adaptation="${model.id}" type="button">Скачать PDF</button>
      `,
    `Кабинет / Адаптации / ${model.title}`
  )}
    <div class="cabinet-grid">
      <div class="cabinet-span-12">
        <div class="cabinet-resume-view">
          <h2>${escapeHtml(model.title)}</h2>
          <div class="role">${escapeHtml(vacancy.role || strategy.positioning || "Адаптированная версия")}</div>
          <pre>${escapeHtml(model.resumeText || "Текст резюме не найден")}</pre>
        </div>
      </div>
      <div class="cabinet-span-12 cabinet-detail-stack">
        ${renderCabinetProfileCard("Профиль вакансии", `
          <div class="cabinet-stack">
            <div class="cabinet-row-line"><b>Роль</b><span>${escapeHtml(vacancy.role || "не указана")}</span></div>
            <div class="cabinet-row-line"><b>Уровень / индустрия</b><span>${escapeHtml([vacancy.seniority, vacancy.industry].filter(Boolean).join(" · ") || "не указано")}</span></div>
          </div>
          <div class="cabinet-chip-row">${limitedList([...(vacancy.must_have_skills || []), ...(vacancy.keywords_for_ats || [])], 16).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
        `)}
        ${renderCabinetProfileCard("Стратегия", `
          <ul class="cabinet-info-list">
            <li><b>Позиционирование:</b> ${escapeHtml(strategy.positioning || "не сформировано")}</li>
            <li><b>Что выделяем:</b> ${escapeHtml(limitedList(strategy.skills_to_highlight, 8).join(", ") || "не указано")}</li>
            <li><b>Темы:</b> ${escapeHtml(limitedList(strategy.priority_themes, 6).join(", ") || "не указано")}</li>
            <li><b>Гэпы:</b> ${escapeHtml(limitedList(strategy.gaps, 8).join(", ") || "нет явных гэпов")}</li>
          </ul>
        `)}
        ${renderCabinetProfileCard("Отчёт критика", `
          <ul class="cabinet-info-list">
            ${(report.covered_must_haves || []).slice(0, 6).map((item) => `<li>Покрыто: ${escapeHtml(item)}</li>`).join("")}
            ${(report.uncovered_must_haves || []).slice(0, 6).map((item) => `<li>Не покрыто: ${escapeHtml(item)}</li>`).join("")}
            ${(report.critic_warnings || []).slice(0, 4).map((item) => `<li>${escapeHtml(humanizeWarning(item))}</li>`).join("")}
          </ul>
          <div class="cabinet-badge">confidence · ${escapeHtml(humanizeStatus(report.critic_confidence) || "средняя")}</div>
        `)}
      </div>
    </div>
  `);
}

function renderCabinet() {
  if (!cabinetRoot) {
    return;
  }
  if (!state.authenticated) {
    state.authMode = "login";
    showPage("auth");
    return;
  }
  if (!state.sourceResume && state.cabinetView !== "resume") {
    state.cabinetView = "resume";
    renderCabinet();
    return;
  }
  if (state.cabinetView === "adaptations") {
    cabinetRoot.innerHTML = renderCabinetAdaptationsScreen();
  } else if (state.cabinetView === "new") {
    cabinetRoot.innerHTML = renderCabinetNewAdaptationScreen();
  } else if (state.cabinetView === "detail") {
    cabinetRoot.innerHTML = renderCabinetAdaptationDetailScreen();
  } else {
    cabinetRoot.innerHTML = renderCabinetResumeScreen();
  }
  bindCabinetActions();
}

function bindVacancyRailActions() {
  const vacancySearch = document.getElementById("vacancyRecommendationSearch");
  if (vacancySearch) {
    vacancySearch.oninput = (event) => {
      state.vacancySearch = event.target.value;
      refreshVacancyRail({ keepSearchFocus: true });
    };
  }

  const vacancySourceFilter = document.getElementById("vacancySourceFilter");
  if (vacancySourceFilter) {
    vacancySourceFilter.onchange = (event) => {
      state.vacancySourceFilter = event.target.value;
      refreshVacancyRail();
    };
  }

  document.querySelectorAll("[data-open-external-vacancy]").forEach((button) => {
    button.onclick = () => openExternalVacancy(Number(button.dataset.openExternalVacancy));
  });

  document.querySelectorAll("[data-adapt-external-vacancy]").forEach((button) => {
    button.onclick = () => adaptExternalVacancy(Number(button.dataset.adaptExternalVacancy));
  });
}

function refreshVacancyRail(options = {}) {
  const currentRail = document.querySelector(".cabinet-vacancy-rail");
  if (!currentRail) {
    return;
  }
  currentRail.outerHTML = renderVacancyRecommendationsRail();
  bindVacancyRailActions();
  if (options.keepSearchFocus) {
    const refreshedSearch = document.getElementById("vacancyRecommendationSearch");
    if (refreshedSearch) {
      refreshedSearch.focus();
      const cursor = refreshedSearch.value.length;
      refreshedSearch.setSelectionRange(cursor, cursor);
    }
  }
}

function bindManualResumeFormActions() {
  const form = document.getElementById("manualResumeForm");
  if (!form) {
    return;
  }
  const draft = getManualResumeDraft();

  form.querySelectorAll("[data-manual-field]").forEach((input) => {
    input.oninput = (event) => {
      draft[input.dataset.manualField] = event.target.value;
    };
  });
  form.querySelectorAll("[data-manual-job]").forEach((input) => {
    const updateJobField = (event) => {
      const index = Number(input.dataset.manualJob);
      const field = input.dataset.jobField;
      if (draft.jobs[index] && field) {
        draft.jobs[index][field] = input.type === "checkbox" ? event.target.checked : event.target.value;
        if (field === "is_current") {
          if (event.target.checked) {
            draft.jobs[index].end_month = "";
            draft.jobs[index].end_year = "";
          }
          renderCabinet();
        }
      }
    };
    input.oninput = updateJobField;
    input.onchange = updateJobField;
  });
  form.querySelectorAll("[data-manual-education]").forEach((input) => {
    const updateEducationField = (event) => {
      const index = Number(input.dataset.manualEducation);
      const field = input.dataset.educationField;
      if (draft.education[index] && field) {
        draft.education[index][field] = event.target.value;
      }
    };
    input.oninput = updateEducationField;
    input.onchange = updateEducationField;
  });
  form.querySelectorAll("[data-manual-language]").forEach((input) => {
    const updateLanguageField = (event) => {
      const index = Number(input.dataset.manualLanguage);
      const field = input.dataset.languageField;
      if (draft.languages[index] && field) {
        draft.languages[index][field] = event.target.value;
      }
    };
    input.oninput = updateLanguageField;
    input.onchange = updateLanguageField;
  });

  form.querySelector("[data-add-manual-job]")?.addEventListener("click", () => {
    draft.jobs.push(emptyManualJob(draft.jobs.length + 1));
    renderCabinet();
  });
  form.querySelectorAll("[data-remove-manual-job]").forEach((button) => {
    button.onclick = () => {
      draft.jobs.splice(Number(button.dataset.removeManualJob), 1);
      renderCabinet();
    };
  });
  form.querySelector("[data-add-manual-education]")?.addEventListener("click", () => {
    draft.education.push(emptyManualEducation());
    renderCabinet();
  });
  form.querySelectorAll("[data-remove-manual-education]").forEach((button) => {
    button.onclick = () => {
      draft.education.splice(Number(button.dataset.removeManualEducation), 1);
      renderCabinet();
    };
  });
  form.querySelector("[data-add-manual-language]")?.addEventListener("click", () => {
    draft.languages.push(emptyManualLanguage());
    renderCabinet();
  });
  form.querySelectorAll("[data-remove-manual-language]").forEach((button) => {
    button.onclick = () => {
      draft.languages.splice(Number(button.dataset.removeManualLanguage), 1);
      renderCabinet();
    };
  });

  const cancel = document.getElementById("cancelManualResume");
  if (cancel) {
    cancel.onclick = () => {
      state.sourceResumeMode = "upload";
      state.sourceResumeEditingBlock = null;
      state.manualResumeDraft = null;
      renderCabinet();
    };
  }

  form.onsubmit = async (event) => {
    event.preventDefault();
    await saveManualSourceResume();
  };
}

function readSourceBlockFields(form) {
  const values = {};
  form.querySelectorAll("[data-source-field]").forEach((input) => {
    values[input.dataset.sourceField] = input.type === "checkbox" ? input.checked : input.value;
  });
  return values;
}

async function saveSourceResumeDraftFromBlock(message = "Базовое резюме обновлено") {
  const candidateProfile = manualDraftToCandidateProfile();
  state.manualResumeSubmitting = true;
  renderCabinet();
  try {
    const data = await postJson("/api/source-resume/manual", {
      candidate_profile: candidateProfile,
      raw_text: manualCandidateProfileToRawText(candidateProfile),
    }, "PUT");
    state.sourceResume = data.source_resume;
    state.candidateProfile = data.source_resume?.candidate_profile || state.candidateProfile;
    state.resumeText = data.source_resume?.raw_text || state.resumeText;
    state.sourceResumeMode = "upload";
    state.sourceResumeEditingBlock = null;
    state.manualResumeDraft = manualDraftFromCandidate(canonicalCandidateProfile(state.sourceResume?.candidate_profile));
    await loadRecommendedVacancies();
    showToast(message);
  } catch (error) {
    showToast(error.message);
  } finally {
    state.manualResumeSubmitting = false;
    renderCabinet();
  }
}

function bindSourceBlockEditActions() {
  if (!state.sourceResume) {
    return;
  }
  const draft = getManualResumeDraft();

  document.querySelectorAll("[data-edit-source-block]").forEach((button) => {
    button.onclick = () => {
      state.sourceResumeEditingBlock = {
        type: button.dataset.editSourceBlock,
        index: button.dataset.editIndex === undefined ? null : Number(button.dataset.editIndex),
      };
      renderCabinet();
    };
  });

  document.querySelectorAll("[data-cancel-source-edit]").forEach((button) => {
    button.onclick = () => {
      const block = state.sourceResumeEditingBlock;
      if (block?.isNew) {
        if (block.type === "job") {
          draft.jobs.splice(Number(block.index), 1);
        } else if (block.type === "education") {
          draft.education.splice(Number(block.index), 1);
        } else if (block.type === "language") {
          draft.languages.splice(Number(block.index), 1);
        }
      } else {
        state.manualResumeDraft = manualDraftFromCandidate(canonicalCandidateProfile(state.sourceResume?.candidate_profile));
      }
      state.sourceResumeEditingBlock = null;
      renderCabinet();
    };
  });

  document.querySelectorAll("[data-add-source-item]").forEach((button) => {
    button.onclick = () => {
      const type = button.dataset.addSourceItem;
      if (type === "job") {
        draft.jobs.push(emptyManualJob(draft.jobs.length + 1));
        state.sourceResumeEditingBlock = { type: "job", index: draft.jobs.length - 1, isNew: true };
      } else if (type === "education") {
        draft.education.push(emptyManualEducation());
        state.sourceResumeEditingBlock = { type: "education", index: draft.education.length - 1, isNew: true };
      } else if (type === "language") {
        draft.languages.push(emptyManualLanguage());
        state.sourceResumeEditingBlock = { type: "language", index: draft.languages.length - 1, isNew: true };
      }
      renderCabinet();
    };
  });

  document.querySelectorAll("[data-delete-source-item]").forEach((button) => {
    button.onclick = async () => {
      const type = button.dataset.deleteSourceItem;
      const index = Number(button.dataset.deleteIndex);
      if (!Number.isFinite(index)) {
        return;
      }
      if (!window.confirm("Удалить этот блок из базового резюме?")) {
        return;
      }
      if (type === "job") {
        draft.jobs.splice(index, 1);
      } else if (type === "education") {
        draft.education.splice(index, 1);
      } else if (type === "language") {
        draft.languages.splice(index, 1);
      }
      state.sourceResumeEditingBlock = null;
      await saveSourceResumeDraftFromBlock("Блок удалён");
    };
  });

  document.querySelectorAll("[data-source-block-form]").forEach((form) => {
    form.querySelectorAll("[data-source-field='is_current']").forEach((checkbox) => {
      checkbox.onchange = (event) => {
        const index = Number(form.dataset.editIndex);
        if (draft.jobs[index]) {
          draft.jobs[index] = { ...draft.jobs[index], ...readSourceBlockFields(form), is_current: event.target.checked };
          if (event.target.checked) {
            draft.jobs[index].end_month = "";
            draft.jobs[index].end_year = "";
          }
          renderCabinet();
        }
      };
    });

    form.onsubmit = async (event) => {
      event.preventDefault();
      const type = form.dataset.sourceBlockForm;
      const index = Number(form.dataset.editIndex);
      const values = readSourceBlockFields(form);
      if (type === "target_role") {
        draft.target_role = values.value || "";
      } else if (type === "summary") {
        draft.summary_raw = values.value || "";
      } else if (type === "skills") {
        draft.skills_hard = values.skills_hard || "";
        draft.skills_soft = values.skills_soft || "";
      } else if (type === "job" && draft.jobs[index]) {
        draft.jobs[index] = { ...draft.jobs[index], ...values };
      } else if (type === "education" && draft.education[index]) {
        draft.education[index] = { ...draft.education[index], ...values };
      } else if (type === "language" && draft.languages[index]) {
        draft.languages[index] = { ...draft.languages[index], ...values };
      }
      await saveSourceResumeDraftFromBlock();
    };
  });
}

function bindCabinetActions() {
  document.querySelectorAll("[data-cabinet-view]").forEach((button) => {
    button.onclick = async () => {
      state.cabinetView = button.dataset.cabinetView;
      if (state.cabinetView === "adaptations") {
        await loadAdaptations();
      }
      if (state.cabinetView === "new") {
        state.newAdaptationMode = "url";
        state.vacancyFetchError = "";
      }
      renderCabinet();
    };
  });

  const uploadResume = document.getElementById("cabinetUploadResume");
  const sourceFile = document.getElementById("cabinetSourceFile");
  if (uploadResume && sourceFile) {
    uploadResume.onclick = async () => {
      state.sourceResumeMode = "upload";
      state.sourceResumeEditingBlock = null;
      state.manualResumeDraft = null;
      state.sourceResumeSelecting = true;
      renderCabinet();
      setTimeout(() => {
        const refreshedSourceFile = document.getElementById("cabinetSourceFile");
        if (!refreshedSourceFile) {
          state.sourceResumeSelecting = false;
          renderCabinet();
          return;
        }
        const resetAfterPicker = () => {
          setTimeout(() => {
            if (state.sourceResumeSelecting && !state.sourceResumeUpdating) {
              state.sourceResumeSelecting = false;
              renderCabinet();
            }
          }, 250);
          window.removeEventListener("focus", resetAfterPicker);
        };
        window.addEventListener("focus", resetAfterPicker);
        refreshedSourceFile.click();
      }, 0);
    };
    sourceFile.onchange = async () => {
      if (sourceFile.files?.[0]) {
        state.sourceResumeSelecting = false;
        await updateSourceResumeFile(sourceFile.files[0]);
      }
    };
  }

  const entryResume = document.getElementById("cabinetEntryResume");
  if (entryResume) {
    entryResume.onclick = () => {
      state.step = 0;
      showPage("flow");
    };
  }

  const createManualResume = document.getElementById("cabinetCreateManualResume");
  if (createManualResume) {
    createManualResume.onclick = () => {
      state.sourceResumeMode = "manual";
      state.sourceResumeEditingBlock = null;
      state.manualResumeDraft = manualDraftFromCandidate(canonicalCandidateProfile(state.sourceResume?.candidate_profile));
      renderCabinet();
    };
  }

  bindManualResumeFormActions();
  bindSourceBlockEditActions();

  document.querySelectorAll("[data-adaptation-mode]").forEach((button) => {
    button.onclick = () => {
      state.newAdaptationMode = button.dataset.adaptationMode;
      state.vacancyFetchError = "";
      renderCabinet();
    };
  });

  const vacancyText = document.getElementById("cabinetVacancyText");
  if (vacancyText) {
    vacancyText.oninput = (event) => {
      state.newAdaptationText = event.target.value;
    };
  }

  const vacancyUrl = document.getElementById("cabinetVacancyUrl");
  if (vacancyUrl) {
    vacancyUrl.oninput = (event) => {
      state.newAdaptationUrl = event.target.value;
      state.fetchedVacancy = null;
      state.vacancyFetchError = "";
    };
  }

  const fetchedVacancyText = document.getElementById("cabinetFetchedVacancyText");
  if (fetchedVacancyText) {
    fetchedVacancyText.oninput = (event) => {
      if (state.fetchedVacancy) {
        state.fetchedVacancy.normalized_text = event.target.value;
      }
    };
  }

  const fetchVacancy = document.getElementById("fetchCabinetVacancy");
  if (fetchVacancy) {
    fetchVacancy.onclick = fetchCabinetVacancyFromUrl;
  }

  const fallbackToText = document.getElementById("fallbackToVacancyText");
  if (fallbackToText) {
    fallbackToText.onclick = () => {
      state.newAdaptationMode = "text";
      state.vacancyFetchError = "";
      renderCabinet();
    };
  }

  const runAdaptation = document.getElementById("runCabinetAdaptation");
  if (runAdaptation) {
    runAdaptation.onclick = createCabinetAdaptation;
  }

  const draftAdaptation = document.getElementById("draftCabinetAdaptation");
  if (draftAdaptation) {
    draftAdaptation.onclick = () => showToast("Черновик сохранён локально на экране");
  }

  document.querySelectorAll("[data-open-adaptation]").forEach((button) => {
    button.onclick = () => openCabinetAdaptation(Number(button.dataset.openAdaptation));
  });

  document.querySelectorAll("[data-download-adaptation]").forEach((button) => {
    button.onclick = () => {
      window.location.href = `/api/adaptations/${button.dataset.downloadAdaptation}/download/pdf`;
    };
  });

  document.querySelectorAll("[data-regenerate-adaptation]").forEach((button) => {
    button.onclick = () => regenerateCabinetAdaptation(Number(button.dataset.regenerateAdaptation));
  });

  bindVacancyRailActions();
}

async function updateSourceResumeFile(file) {
  state.sourceResumeSelecting = false;
  state.sourceResumeUpdating = true;
  renderCabinet();
  try {
    const formData = new FormData();
    formData.append("file", file);
    if (state.conversationId) {
      formData.append("conversation_id", String(state.conversationId));
    }
    const data = await postFormData("/api/source-resume/upload", formData);
    state.sourceResume = data.source_resume;
    state.candidateProfile = data.source_resume?.candidate_profile || state.candidateProfile;
    state.resumeText = data.source_resume?.raw_text || state.resumeText;
    state.uploadedFileName = data.source_resume?.file_name || file.name;
    await loadRecommendedVacancies();
    showToast("Базовое резюме обновлено");
  } catch (error) {
    showToast(error.message);
  } finally {
    state.sourceResumeSelecting = false;
    state.sourceResumeUpdating = false;
    renderCabinet();
  }
}

async function saveManualSourceResume() {
  const candidateProfile = manualDraftToCandidateProfile();
  const canonical = candidateProfile.canonical_profile || {};
  if (!canonical.target_role && !canonical.jobs.length && !canonical.skills_hard.length && !canonical.education.length) {
    showToast("Заполните хотя бы роль, опыт, навыки или образование");
    return;
  }
  state.manualResumeSubmitting = true;
  renderCabinet();
  try {
    const isEditMode = Boolean(state.sourceResume?.id);
    const data = await postJson("/api/source-resume/manual", {
      candidate_profile: candidateProfile,
      raw_text: manualCandidateProfileToRawText(candidateProfile),
    }, isEditMode ? "PUT" : "POST");
    state.sourceResume = data.source_resume;
    state.candidateProfile = data.source_resume?.candidate_profile || state.candidateProfile;
    state.resumeText = data.source_resume?.raw_text || state.resumeText;
    state.uploadedFileName = data.source_resume?.file_name || "Создано вручную";
    state.sourceResumeMode = "upload";
    state.manualResumeDraft = null;
    await loadRecommendedVacancies();
    showToast(isEditMode ? "Базовое резюме обновлено" : "Базовое резюме сохранено");
  } catch (error) {
    showToast(error.message);
  } finally {
    state.manualResumeSubmitting = false;
    renderCabinet();
  }
}

async function createCabinetAdaptation() {
  if (!state.sourceResume) {
    showToast("Сначала сохраните базовое резюме");
    return;
  }
  state.adaptationSubmitting = true;
  renderCabinet();
  try {
    const startedAt = Date.now();
    const formData = new FormData();
    if (state.newAdaptationMode === "url") {
      formData.append("vacancy_text", state.fetchedVacancy?.normalized_text || "");
      formData.append("vacancy_source_type", "url");
      formData.append("vacancy_source_url", state.newAdaptationUrl);
    } else {
      formData.append("vacancy_text", state.newAdaptationText);
      formData.append("vacancy_source_type", "text");
    }
    const data = await postFormData("/api/adaptations", formData);
    const remainingLoadingMs = 700 - (Date.now() - startedAt);
    if (remainingLoadingMs > 0) {
      await sleep(remainingLoadingMs);
    }
    state.currentAdaptation = data.adaptation;
    state.newAdaptationText = "";
    state.newAdaptationUrl = "";
    state.fetchedVacancy = null;
    state.vacancyFetchError = "";
    state.adaptationSubmitting = false;
    await loadAdaptations();
    await loadRecommendedVacancies();
    state.cabinetView = "detail";
    showToast("Адаптация готова");
    renderCabinet();
  } catch (error) {
    state.adaptationSubmitting = false;
    showToast(error.message);
    renderCabinet();
  }
}

async function fetchCabinetVacancyFromUrl() {
  if (!state.newAdaptationUrl.trim()) {
    state.vacancyFetchError = "Вставьте ссылку на вакансию";
    renderCabinet();
    return;
  }
  state.vacancyFetching = true;
  state.vacancyFetchError = "";
  state.fetchedVacancy = null;
  renderCabinet();
  try {
    const data = await postForm("/api/vacancy/fetch", { url: state.newAdaptationUrl });
    if (!data.success) {
      state.vacancyFetchError = data.message || (data.warnings || [])[0] || "Не удалось получить вакансию по ссылке";
      state.fetchedVacancy = null;
      return;
    }
    state.fetchedVacancy = data;
    if (data.external_vacancy) {
      await loadRecommendedVacancies();
    }
    showToast("Вакансия получена");
  } catch (error) {
    state.vacancyFetchError = error.message || "Не удалось получить вакансию по ссылке";
  } finally {
    state.vacancyFetching = false;
    renderCabinet();
  }
}

async function openCabinetAdaptation(adaptationId) {
  setBusy(true);
  try {
    const data = await fetchJson(`/api/adaptations/${adaptationId}`);
    state.currentAdaptation = data.adaptation;
    state.pendingAdaptation = null;
    state.cabinetView = "detail";
    renderCabinet();
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
}

async function regenerateCabinetAdaptation(adaptationId) {
  setBusy(true);
  try {
    const data = await postForm(`/api/adaptations/${adaptationId}/regenerate`, {});
    state.currentAdaptation = data.adaptation;
    await loadAdaptations();
    await loadRecommendedVacancies();
    state.cabinetView = "detail";
    showToast("Адаптация перегенерирована");
    renderCabinet();
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
}

function renderExternalVacancyDetail(vacancy) {
  const model = externalVacancyDisplayModel(vacancy);
  return `
    <div class="cabinet-stack">
      <div class="cabinet-row-line"><b>Источник</b><span>${escapeHtml(model.sourceLabel)}</span></div>
      <div class="cabinet-row-line"><b>Компания</b><span>${escapeHtml([model.company, model.location].filter(Boolean).join(" · ") || "не указана")}</span></div>
      ${model.salary ? `<div class="cabinet-row-line"><b>Зарплата</b><span>${escapeHtml(model.salary)}</span></div>` : ""}
      <div class="cabinet-row-line">
        <b>Описание</b>
        <span>
          ${escapeHtml(model.description || "Описание не найдено")}
          ${model.sourceUrl ? `<br><a href="${escapeHtml(model.sourceUrl)}" target="_blank" rel="noopener noreferrer">Ссылка</a>` : ""}
        </span>
      </div>
    </div>
    <div class="cta-inline" style="margin-top:18px">
      <button class="btn btn-primary" data-adapt-external-vacancy="${model.id}" type="button">Адаптировать</button>
    </div>
  `;
}

async function openExternalVacancy(vacancyId) {
  try {
    const data = await fetchJson(`/api/recommended-vacancies/${vacancyId}`);
    state.selectedExternalVacancy = data.vacancy;
    openModal(data.vacancy?.title || "Вакансия", renderExternalVacancyDetail(data.vacancy));
    const modalBody = document.getElementById("flowModalBody");
    modalBody?.querySelectorAll("[data-adapt-external-vacancy]").forEach((button) => {
      button.onclick = () => {
        closeModal();
        adaptExternalVacancy(Number(button.dataset.adaptExternalVacancy));
      };
    });
  } catch (error) {
    showToast(error.message);
  }
}

async function adaptExternalVacancy(vacancyId) {
  if (!state.sourceResume) {
    showToast("Сначала сохраните базовое резюме");
    return;
  }
  const vacancy = (state.recommendedVacancies || []).find((item) => Number(item.id) === Number(vacancyId));
  const model = vacancy ? externalVacancyDisplayModel(vacancy) : { title: "Новая адаптация", company: "", location: "", sourceLabel: "" };
  state.vacancyAdaptingId = vacancyId;
  state.pendingAdaptation = {
    vacancyId,
    title: model.title || "Новая адаптация",
    company: [model.company, model.location].filter(Boolean).join(" · "),
    sourceLabel: model.sourceLabel || "",
  };
  state.currentAdaptation = null;
  state.cabinetView = "detail";
  renderCabinet();
  try {
    const data = await postForm(`/api/recommended-vacancies/${vacancyId}/adapt`, {});
    state.currentAdaptation = data.adaptation;
    state.pendingAdaptation = null;
    await loadAdaptations();
    await loadRecommendedVacancies();
    state.cabinetView = "detail";
    showToast("Адаптация готова");
  } catch (error) {
    state.pendingAdaptation = null;
    state.cabinetView = "new";
    showToast(error.message);
  } finally {
    state.vacancyAdaptingId = null;
    renderCabinet();
  }
}

function updateRail() {
  railSteps.forEach((element, index) => {
    element.classList.toggle("active", index === state.step);
    element.classList.toggle("done", index < state.step);
    element.querySelector(".rail-num").textContent = index < state.step ? "✓" : index + 1;
  });
}

function render() {
  if (!state.authenticated) {
    state.authMode = "register";
    showPage("auth");
    return;
  }
  if (state.step !== 0 && state.step !== 3) {
    state.step = 0;
  }
  updateRail();
  if (state.step === 0) renderResume();
  if (state.step === 3) renderResult();
}

function showPage(page) {
  state.page = page;
  document.body.classList.toggle("flow-mode", page === "flow");
  document.body.classList.toggle("cabinet-mode", page === "cabinet");
  document.body.classList.toggle("auth-mode", page === "auth");
  landingPage.classList.toggle("active", page === "landing");
  flowPage.classList.toggle("active", page === "flow");
  if (cabinetPage) {
    cabinetPage.classList.toggle("active", page === "cabinet");
  }
  if (authPage) {
    authPage.classList.toggle("active", page === "auth");
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (page === "flow") render();
  if (page === "cabinet") renderCabinet();
  if (page === "auth") renderAuth();
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

async function postForm(url, fields) {
  const body = new URLSearchParams();
  Object.entries(fields).forEach(([key, value]) => {
    body.append(key, value ?? "");
  });

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

async function postJson(url, payload, method = "POST") {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

async function postFormData(url, formData) {
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function applyAuthSession(data) {
  state.authenticated = Boolean(data.authenticated);
  state.authUser = data.user || null;
  state.userId = data.user_id || data.user?.id || null;
  state.conversationId = data.conversation_id || null;
  if (!state.authenticated) {
    state.sourceResume = null;
    state.adaptations = [];
    state.recommendedVacancies = [];
    state.currentAdaptation = null;
    state.manualResumeDraft = null;
    state.sourceResumeMode = "upload";
  }
}

async function loadAuthSession() {
  const data = await fetchJson("/api/auth/session");
  applyAuthSession(data);
  return data;
}

async function submitAuth(mode, fields) {
  const data = await postForm(`/api/auth/${mode}`, fields);
  applyAuthSession(data);
  state.authError = "";
  if (data.has_source_resume) {
    await loadSourceResume();
    await loadAdaptations();
    await loadRecommendedVacancies();
    state.cabinetView = "resume";
    showPage("cabinet");
    return;
  }
  state.sourceResume = null;
  state.sourceResumeMode = "upload";
  state.manualResumeDraft = null;
  state.cabinetView = "resume";
  showPage("cabinet");
}

async function logout() {
  await postForm("/api/auth/logout", {});
  state.authenticated = false;
  state.authUser = null;
  state.userId = null;
  state.conversationId = null;
  state.sourceResume = null;
  state.adaptations = [];
  state.recommendedVacancies = [];
  state.currentAdaptation = null;
  state.manualResumeDraft = null;
  state.sourceResumeMode = "upload";
  state.candidateProfile = null;
  state.resumeText = "";
  state.uploadedFileName = "";
  state.authMode = "login";
  showPage("landing");
  showToast("Вы вышли из аккаунта");
}

async function bootstrapSession() {
  const data = await fetchJson("/api/session/bootstrap");
  state.userId = data.user_id;
  state.conversationId = data.conversation_id;
}

async function loadModelInfo() {
  state.modelInfo = await fetchJson("/api/model-info");
  const existing = document.getElementById("modelPill");
  if (existing) {
    existing.remove();
  }
}

async function loadResumes() {
  if (!state.userId) {
    return;
  }

  const data = await fetchJson(`/api/resumes?user_id=${state.userId}`);
  state.resumes = data.resumes || [];
}

async function loadSourceResume() {
  if (!state.authenticated) {
    return;
  }
  const data = await fetchJson("/api/source-resume");
  state.sourceResume = data.source_resume || null;
  if (state.sourceResume) {
    state.sourceResumeSelecting = false;
    state.sourceResumeUpdating = false;
    state.resumeText = state.sourceResume.raw_text || state.resumeText;
    state.candidateProfile = state.sourceResume.candidate_profile || state.candidateProfile;
    state.uploadedFileName = state.sourceResume.file_name || state.uploadedFileName;
  }
}

async function loadAdaptations() {
  if (!state.authenticated) {
    return;
  }
  const data = await fetchJson("/api/adaptations");
  state.adaptations = data.adaptations || [];
}

async function loadRecommendedVacancies() {
  if (!state.authenticated || !state.sourceResume) {
    state.recommendedVacancies = [];
    return;
  }
  try {
    const data = await fetchJson("/api/recommended-vacancies");
    state.recommendedVacancies = data.vacancies || [];
  } catch (error) {
    state.recommendedVacancies = [];
    console.warn("Failed to load recommended vacancies", error);
  }
}

async function uploadResumeFile(file) {
  if (!state.authenticated) {
    state.authMode = "register";
    showPage("auth");
    return;
  }

  setBusy(true);
  try {
    const formData = new FormData();
    formData.append("file", file);
    if (state.conversationId) {
      formData.append("conversation_id", String(state.conversationId));
    }

    const data = await postFormData("/api/source-resume/upload", formData);

    state.uploadedFileName = file.name;
    state.resumeText = data.source_resume?.raw_text || "";
    state.sourceResume = data.source_resume || state.sourceResume;
    state.candidateProfile = data.source_resume?.candidate_profile || state.candidateProfile;
    state.resumeWarnings = sanitizeWarnings(data.source_resume?.warnings || []);
    state.clarifyingQuestions = data.source_resume?.questions || [];
    state.lastResumeAnalyzedText = state.resumeText;
    showToast("Резюме обработано");
    state.cabinetView = "resume";
    await loadAdaptations();
    await loadRecommendedVacancies();
    showPage("cabinet");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
}

async function ensureResumeAnalyzed() {
  if (!state.authenticated) {
    throw new Error("Сначала войдите в аккаунт");
  }

  if (state.mode === "file") {
    if (!state.resumeText) {
      throw new Error("Сначала загрузите файл с резюме");
    }
    return;
  }

  if (!state.resumeText.trim()) {
    throw new Error("Вставьте текст резюме");
  }

  if (state.lastResumeAnalyzedText === state.resumeText && state.candidateProfile) {
    return;
  }

  const data = await postForm("/api/source-resume/text", {
    resume_text: state.resumeText,
    conversation_id: state.conversationId || "",
  });

  state.sourceResume = data.source_resume || state.sourceResume;
  state.candidateProfile = data.source_resume?.candidate_profile || state.candidateProfile;
  state.resumeWarnings = sanitizeWarnings(data.source_resume?.warnings || []);
  state.clarifyingQuestions = data.source_resume?.questions || [];
  state.lastResumeAnalyzedText = state.resumeText;
}

async function buildPreview() {
  if (!state.resumeText.trim()) {
    throw new Error("Не найден текст резюме");
  }
  if (!state.vacancyText.trim()) {
    throw new Error("Вставьте текст вакансии");
  }

  const data = await postForm("/api/analyze/preview", {
    resume_text: state.resumeText,
    vacancy_text: state.vacancyText,
    conversation_id: state.conversationId,
  });

  state.candidateProfile = data.candidate_profile;
  state.vacancyProfile = data.vacancy_profile;
  state.strategyBrief = data.strategy_brief;
  state.resumeWarnings = sanitizeWarnings(data.warnings?.candidate || []);
  state.vacancyWarnings = sanitizeWarnings(data.warnings?.vacancy || []);
  state.clarifyingQuestions = data.questions || [];
}

async function generateResume() {
  const data = await postForm("/api/generate/full", {
    user_id: state.userId,
    conversation_id: state.conversationId,
    resume_text: state.resumeText,
    vacancy_text: state.vacancyText,
  });

  state.currentResumeId = data.resume_id;
  state.candidateProfile = data.candidate_profile;
  state.vacancyProfile = data.vacancy_profile;
  state.strategyBrief = data.strategy_brief;
  state.generatedResume = data.generated_resume;
  state.techReport = data.generated_resume?.technical_report || null;
  state.resumeWarnings = sanitizeWarnings(data.candidate_profile?.raw_warnings || []);
  state.vacancyWarnings = sanitizeWarnings(data.vacancy_profile?.raw_warnings || []);
  await loadResumes();
}

async function handleNextStep() {
  setBusy(true);
  try {
    if (state.step === 0) {
      await ensureResumeAnalyzed();
      state.cabinetView = "resume";
      await loadSourceResume();
      await loadAdaptations();
      await loadRecommendedVacancies();
      showPage("cabinet");
      showToast("Базовое резюме сохранено");
      return;
    }
    state.step = 0;
    render();
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
}

function bindActions() {
  const previousButton = document.getElementById("prevBtn");
  const homeButton = document.getElementById("homeBtn");
  const nextButton = document.getElementById("nextBtn");

  if (homeButton) {
    homeButton.onclick = () => showPage("landing");
  }

  if (previousButton) {
    previousButton.onclick = () => {
      state.step = Math.max(0, state.step - 1);
      render();
    };
  }

  if (nextButton) {
    nextButton.onclick = handleNextStep;
  }
}

function handleDownload(format) {
  if (format === undefined) {
    return;
  }

  if (!state.currentResumeId) {
    showToast("Сначала сгенерируйте или откройте резюме из истории");
    return;
  }

  if (format === "PDF") {
    window.location.href = `/api/resumes/${state.currentResumeId}/download/pdf`;
    return;
  }

  if (format === "TXT") {
    window.location.href = `/api/resumes/${state.currentResumeId}/download/txt`;
    return;
  }

  showToast("DOCX пока не поддерживается в этом MVP");
}

function ensureModal() {
  let modal = document.getElementById("flowModal");
  if (modal) {
    return modal;
  }

  modal = document.createElement("div");
  modal.id = "flowModal";
  modal.style.cssText = [
    "position:fixed",
    "inset:0",
    "display:none",
    "align-items:center",
    "justify-content:center",
    "background:rgba(23,23,23,.45)",
    "z-index:30",
    "padding:24px",
  ].join(";");

  modal.innerHTML = `
    <div style="width:min(860px, 100%); max-height:85vh; overflow:auto; background:#fffdf9; border-radius:28px; border:1px solid #ded7cc; box-shadow:0 28px 80px rgba(39,32,24,.18); padding:28px;">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:18px;">
        <h3 id="flowModalTitle" style="margin:0; font-size:24px; letter-spacing:-.04em;">Детали</h3>
        <button id="flowModalClose" type="button" style="border:1px solid #ded7cc; background:#fff; border-radius:14px; min-width:44px; min-height:44px; cursor:pointer;">✕</button>
      </div>
      <div id="flowModalBody" style="font-size:14px; line-height:1.6; color:#3f3d39;"></div>
    </div>
  `;

  modal.onclick = (event) => {
    if (event.target === modal) {
      closeModal();
    }
  };

  document.body.appendChild(modal);
  document.getElementById("flowModalClose").onclick = closeModal;
  return modal;
}

function closeModal() {
  const modal = document.getElementById("flowModal");
  if (modal) {
    modal.style.display = "none";
  }
}

function openModal(title, bodyHtml) {
  const modal = ensureModal();
  document.getElementById("flowModalTitle").textContent = title;
  document.getElementById("flowModalBody").innerHTML = bodyHtml;
  modal.style.display = "flex";
}

function openDetailsModal(type) {
  const payloadMap = {
    candidate: state.candidateProfile,
    vacancy: state.vacancyProfile,
    strategy: state.strategyBrief,
    report: state.techReport,
  };

  const titleMap = {
    candidate: "Профиль кандидата",
    vacancy: "Профиль вакансии",
    strategy: "Стратегия адаптации",
    report: "Технический отчет",
  };

  const payload = payloadMap[type];
  if (!payload) {
    showToast("Данные еще не готовы");
    return;
  }

  if (type === "candidate") {
    openModal(titleMap[type], renderCandidateProfileView(payload));
    return;
  }

  if (type === "vacancy") {
    openModal(titleMap[type], renderVacancyProfileView(payload));
    return;
  }

  if (type === "strategy") {
    openModal(titleMap[type], renderCareerStrategyView(payload));
    return;
  }

  if (type === "report") {
    openModal(titleMap[type], renderTechnicalReportView(payload, state.generatedResume));
    return;
  }

  openModal(
    titleMap[type],
    `<pre style="margin:0; white-space:pre-wrap; font:inherit;">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`,
  );
}

async function openHistoryModal() {
  await loadResumes();

  if (!state.resumes.length) {
    openModal("История", "<p style='margin:0;'>Пока нет сохраненных резюме.</p>");
    return;
  }

  const cards = state.resumes.map((resume) => `
    <button
      type="button"
      class="history-resume"
      data-resume-id="${resume.id}"
      style="width:100%; text-align:left; margin:0 0 12px; padding:16px 18px; border-radius:18px; border:1px solid #ded7cc; background:#fff; cursor:pointer;"
    >
      <strong style="display:block; font-size:16px; margin-bottom:6px;">${escapeHtml(resume.title)}</strong>
      <span style="color:#706f6b;">${escapeHtml(new Date(resume.created_at).toLocaleDateString("ru-RU"))}</span>
    </button>
  `).join("");

  openModal("История резюме", cards);
  document.querySelectorAll(".history-resume").forEach((button) => {
    button.onclick = async () => {
      await loadResumeFromHistory(Number(button.dataset.resumeId));
      closeModal();
    };
  });
}

async function loadResumeFromHistory(resumeId) {
  try {
    const data = await fetchJson(`/api/resumes/${resumeId}`);
    state.currentResumeId = resumeId;
    state.generatedResume = {
      title: data.title,
      text: data.resume_text,
      technical_report: data.technical_report,
    };
    state.techReport = data.technical_report;
    state.candidateProfile = data.candidate_profile;
    state.vacancyProfile = data.vacancy_profile;
    state.strategyBrief = data.strategy_brief;
    state.resumeWarnings = sanitizeWarnings(data.candidate_profile?.raw_warnings || []);
    state.vacancyWarnings = sanitizeWarnings(data.vacancy_profile?.raw_warnings || []);
    state.step = 3;
    showPage("flow");
    showToast("Резюме открыто из истории");
  } catch (error) {
    showToast(error.message);
  }
}

async function openProductEntry() {
  if (!state.authenticated) {
    state.authMode = "register";
    state.authError = "";
    showPage("auth");
    return;
  }
  await loadSourceResume();
  await loadAdaptations();
  await loadRecommendedVacancies();
  if (state.sourceResume) {
    state.cabinetView = "resume";
    showPage("cabinet");
    return;
  }
  state.sourceResumeMode = "upload";
  state.manualResumeDraft = null;
  state.cabinetView = "resume";
  showPage("cabinet");
}

function bindStaticActions() {
  document.getElementById("logicBtn").onclick = () => {
    document.getElementById("howItWorks").scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const landingLogin = document.getElementById("landingLogin");
  if (landingLogin) {
    landingLogin.onclick = () => {
      state.authMode = "login";
      state.authError = "";
      showPage("auth");
    };
  }

  const landingRegister = document.getElementById("landingRegister");
  if (landingRegister) {
    landingRegister.onclick = () => {
      state.authMode = "register";
      state.authError = "";
      showPage("auth");
    };
  }

  const topLogout = document.getElementById("topLogout");
  if (topLogout) {
    topLogout.onclick = logout;
  }

  document.getElementById("startFlowBottom").onclick = openProductEntry;

  railSteps.forEach((element) => {
    element.onclick = () => {
      state.step = 0;
      showPage("flow");
    };
  });
}

async function init() {
  bindStaticActions();

  try {
    await loadAuthSession();
    await loadModelInfo();
    if (state.authenticated) {
      await loadResumes();
      await loadSourceResume();
      await loadAdaptations();
      await loadRecommendedVacancies();
    }
    state.initialized = true;
  } catch (error) {
    showToast(`Ошибка инициализации: ${error.message}`);
  }
}

init();
