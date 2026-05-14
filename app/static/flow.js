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
  cabinetView: "resume",
  newAdaptationMode: "text",
  newAdaptationText: "",
  newAdaptationFile: null,
  adaptationSubmitting: false,
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
    subtitle: "Загрузите базовое резюме один раз. Система извлечёт опыт, навыки, образование и сохранит source profile для будущих адаптаций.",
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
        <span>${state.step === 0 ? "source profile" : `${progress}% готово`}</span>
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
      job.highlights.push(...snippets.slice(0, 2));
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

function limitedList(value, limit = 8) {
  return asList(value).slice(0, limit);
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
  const candidate = canonicalCandidateProfile(source?.candidate_profile);
  return {
    id: source?.id || null,
    fileName: source?.file_name || "Базовое резюме",
    updatedAt: source?.updated_at ? new Date(source.updated_at).toLocaleString("ru-RU") : "",
    rawText: source?.raw_text || "",
    candidate,
    warnings: sanitizeWarnings(source?.warnings || source?.candidate_profile?.raw_warnings || []),
  };
}

function adaptationListDisplayModel(adaptation) {
  return {
    id: adaptation.id,
    title: adaptation.title || "Адаптированное резюме",
    summary: adaptation.summary || "Адаптация сохранена.",
    status: adaptation.status || "completed",
    createdAt: adaptation.created_at ? new Date(adaptation.created_at).toLocaleDateString("ru-RU") : "",
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

function cabinetNav() {
  const items = [
    ["resume", "◎", "Моё резюме", "базовый профиль"],
    ["adaptations", "◫", "Адаптации", "версии под вакансии"],
    ["new", "＋", "Новая адаптация", "без повторной загрузки"],
  ];
  if (state.currentAdaptation) {
    items.push(["detail", "↗", "Карточка адаптации", "резюме + анализ"]);
  }

  return `
    <aside class="cabinet-rail">
      <h3>Кабинет</h3>
      ${items.map(([view, icon, title, subtitle]) => `
        <button class="cabinet-nav-item ${state.cabinetView === view ? "active" : ""}" data-cabinet-view="${view}" type="button">
          <div class="cabinet-nav-ico">${icon}</div>
          <div class="cabinet-nav-copy"><b>${escapeHtml(title)}</b><span>${escapeHtml(subtitle)}</span></div>
        </button>
      `).join("")}
      <div class="cabinet-status-card">
        <b>Один source profile</b>
        <p>Базовое резюме хранится отдельно. Новые вакансии создают отдельные адаптации без повторной загрузки резюме.</p>
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

function renderCabinetJobs(jobs) {
  if (!jobs?.length) {
    return `<div class="cabinet-empty">Опыт работы пока не распознан.</div>`;
  }
  return `
    <div class="cabinet-job-list">
      ${jobs.map((job, index) => {
        const bullets = [
          ...(job.achievements || []),
          ...(job.responsibilities || []),
        ].slice(0, index === 0 ? 3 : 2);
        return `
          <article class="cabinet-job-card">
            <div class="cabinet-job-head">
              <div>
                <b>${escapeHtml([job.position, job.company_name].filter(Boolean).join(" — ") || "Место работы")}</b>
                <span>${escapeHtml([job.period, job.company_type].filter(Boolean).join(" · "))}</span>
              </div>
              <div class="cabinet-badge">${index === 0 ? "Основной опыт" : "Поддерживающий опыт"}</div>
            </div>
            ${bullets.length ? `<ul>${bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function renderCabinetResumeScreen() {
  const model = sourceResumeDisplayModel(state.sourceResume);
  const candidate = model.candidate || {};
  const jobs = candidate.jobs || [];
  const educationText = (candidate.education || [])
    .map((item) => [item.institution, item.degree, item.field, item.year].filter(Boolean).join(" · "))
    .filter(Boolean)
    .join(" | ");
  const languageText = (candidate.languages || [])
    .map((item) => typeof item === "string" ? item : [item.name, item.level].filter(Boolean).join(" — "))
    .filter(Boolean)
    .join(" · ");

  const content = `
    ${cabinetHero(
      "Моё резюме",
      "Это базовый профиль кандидата. Он используется как source для всех новых адаптаций.",
      model.id ? `
        <button class="btn btn-secondary" id="cabinetUpdateResume" type="button">Обновить резюме</button>
        <button class="btn btn-primary" data-cabinet-view="new" type="button">Создать новую адаптацию</button>
      ` : `
        <button class="btn btn-primary" id="cabinetEntryResume" type="button">Добавить базовое резюме</button>
      `,
      "Кабинет / Моё резюме"
    )}
    <input type="file" id="cabinetSourceFile" hidden accept=".txt,.pdf,.doc,.docx" />
    ${model.id ? `
      <div class="cabinet-grid">
        <div class="cabinet-card cabinet-span-12">
          <h2>Базовое резюме</h2>
          <div class="file-chip">${escapeHtml(model.fileName)}${model.updatedAt ? ` · обновлено ${escapeHtml(model.updatedAt)}` : ""}</div>
          <div class="cabinet-stack" style="margin-top:18px">
            <div class="cabinet-row-line"><b>Целевая роль</b><span>${escapeHtml(candidate.target_role || "не указана")}</span></div>
            <div class="cabinet-row-line"><b>Общий опыт</b><span>${escapeHtml(formatExperience(candidate))}</span></div>
            ${candidate.summary_raw ? `<div class="cabinet-row-line"><b>Сводка профиля</b><span>${escapeHtml(candidate.summary_raw)}</span></div>` : ""}
          </div>
          ${renderCabinetJobs(jobs)}
          <div class="cabinet-stack" style="margin-top:18px">
            <div class="cabinet-row-line"><b>Образование</b><span>${escapeHtml(educationText || "не указано")}</span></div>
            <div class="cabinet-row-line"><b>Языки</b><span>${escapeHtml(languageText || "не указаны")}</span></div>
          </div>
        </div>
        <div class="cabinet-card cabinet-span-12">
          <h2>Ключевые навыки</h2>
          ${candidate.skills_hard?.length ? `<div class="cabinet-chip-row">${limitedList(candidate.skills_hard, 24).map((skill) => `<span>${escapeHtml(skill)}</span>`).join("")}</div>` : `<div class="cabinet-empty">Навыки пока не распознаны.</div>`}
        </div>
      </div>
    ` : `
      <div class="cabinet-grid">
        <div class="cabinet-card cabinet-span-12">
          <div class="cabinet-empty">
            Базовое резюме ещё не сохранено. Сначала создайте source profile, затем кабинет станет основной рабочей зоной для адаптаций.
          </div>
        </div>
      </div>
    `}
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
            <p>${escapeHtml(model.summary)}</p>
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
  return cabinetShell(`
    ${cabinetHero("Новая адаптация", "", "", "Кабинет / Адаптации / Новая адаптация")}
    <div class="cabinet-grid">
      <div class="cabinet-card cabinet-span-12">
        <h2>Вакансия</h2>
        <div class="cabinet-tabs">
          <button class="cabinet-tab ${state.newAdaptationMode === "text" ? "active" : ""}" data-adaptation-mode="text" type="button">Вставить текст</button>
          <button class="cabinet-tab ${state.newAdaptationMode === "file" ? "active" : ""}" data-adaptation-mode="file" type="button">Загрузить файл</button>
        </div>
        <div class="cabinet-note" style="margin-top:14px">
          Source resume уже сохранён. Повторно загружать его не нужно — новая адаптация будет создана на базе текущего CandidateProfile.
        </div>
        ${state.newAdaptationMode === "text" ? `
          <textarea class="cabinet-textarea" id="cabinetVacancyText" placeholder="Вставьте описание вакансии сюда...">${escapeHtml(state.newAdaptationText)}</textarea>
        ` : `
          <div class="cabinet-file-zone" id="cabinetVacancyDrop">
            <div>
              <b>${state.newAdaptationFile ? escapeHtml(state.newAdaptationFile.name) : "Загрузите файл вакансии"}</b>
              <p>TXT, PDF или DOCX</p>
            </div>
          </div>
          <input type="file" id="cabinetVacancyFile" hidden accept=".txt,.pdf,.doc,.docx" />
        `}
        <div class="cta-inline">
          <button class="btn btn-primary" id="runCabinetAdaptation" type="button" ${state.adaptationSubmitting ? "disabled" : ""}>
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
          ? "После регистрации начнём с базового резюме: оно станет source profile для всех будущих адаптаций."
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
    state.step = 0;
    showPage("flow");
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

function bindCabinetActions() {
  document.querySelectorAll("[data-cabinet-view]").forEach((button) => {
    button.onclick = async () => {
      state.cabinetView = button.dataset.cabinetView;
      if (state.cabinetView === "adaptations") {
        await loadAdaptations();
      }
      renderCabinet();
    };
  });

  const updateResume = document.getElementById("cabinetUpdateResume");
  const sourceFile = document.getElementById("cabinetSourceFile");
  if (updateResume && sourceFile) {
    updateResume.onclick = () => sourceFile.click();
    sourceFile.onchange = async () => {
      if (sourceFile.files?.[0]) {
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

  document.querySelectorAll("[data-adaptation-mode]").forEach((button) => {
    button.onclick = () => {
      state.newAdaptationMode = button.dataset.adaptationMode;
      renderCabinet();
    };
  });

  const vacancyText = document.getElementById("cabinetVacancyText");
  if (vacancyText) {
    vacancyText.oninput = (event) => {
      state.newAdaptationText = event.target.value;
    };
  }

  const vacancyDrop = document.getElementById("cabinetVacancyDrop");
  const vacancyFile = document.getElementById("cabinetVacancyFile");
  if (vacancyDrop && vacancyFile) {
    vacancyDrop.onclick = () => vacancyFile.click();
    vacancyFile.onchange = () => {
      state.newAdaptationFile = vacancyFile.files?.[0] || null;
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
}

async function updateSourceResumeFile(file) {
  setBusy(true);
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
    showToast("Базовое резюме обновлено");
    renderCabinet();
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
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
    if (state.newAdaptationMode === "file" && state.newAdaptationFile) {
      formData.append("file", state.newAdaptationFile);
    } else {
      formData.append("vacancy_text", state.newAdaptationText);
    }
    const data = await postFormData("/api/adaptations", formData);
    const remainingLoadingMs = 700 - (Date.now() - startedAt);
    if (remainingLoadingMs > 0) {
      await sleep(remainingLoadingMs);
    }
    state.currentAdaptation = data.adaptation;
    state.newAdaptationText = "";
    state.newAdaptationFile = null;
    state.adaptationSubmitting = false;
    await loadAdaptations();
    state.cabinetView = "detail";
    showToast("Адаптация готова");
    renderCabinet();
  } catch (error) {
    state.adaptationSubmitting = false;
    showToast(error.message);
    renderCabinet();
  }
}

async function openCabinetAdaptation(adaptationId) {
  setBusy(true);
  try {
    const data = await fetchJson(`/api/adaptations/${adaptationId}`);
    state.currentAdaptation = data.adaptation;
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
    state.cabinetView = "detail";
    showToast("Адаптация перегенерирована");
    renderCabinet();
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
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
    state.currentAdaptation = null;
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
    state.cabinetView = "resume";
    showPage("cabinet");
    return;
  }
  state.step = 0;
  showPage("flow");
}

async function logout() {
  await postForm("/api/auth/logout", {});
  state.authenticated = false;
  state.authUser = null;
  state.userId = null;
  state.conversationId = null;
  state.sourceResume = null;
  state.adaptations = [];
  state.currentAdaptation = null;
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
  if (state.sourceResume) {
    state.cabinetView = "resume";
    showPage("cabinet");
    return;
  }
  state.step = 0;
  showPage("flow");
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

  document.getElementById("topHistory").onclick = openHistoryModal;
  const topLogout = document.getElementById("topLogout");
  if (topLogout) {
    topLogout.onclick = logout;
  }
  const topCabinet = document.getElementById("topCabinet");
  if (topCabinet) {
    topCabinet.onclick = async () => {
      if (!state.authenticated) {
        state.authMode = "login";
        showPage("auth");
        return;
      }
      await loadSourceResume();
      await loadAdaptations();
      if (!state.sourceResume) {
        state.step = 0;
        showPage("flow");
        showToast("Сначала сохраните базовое резюме");
        return;
      }
      state.cabinetView = "resume";
      showPage("cabinet");
    };
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
    }
    state.initialized = true;
  } catch (error) {
    showToast(`Ошибка инициализации: ${error.message}`);
  }
}

init();
