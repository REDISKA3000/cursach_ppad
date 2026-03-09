// Глобальное состояние
let currentConversationId = null;
let currentUserId = null;
let currentResumeId = null;
let currentCandidateProfile = null;
let currentVacancyProfile = null;
let currentStrategyBrief = null;
let currentTechReport = null;

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    // Получить ID со страницы
    const urlParams = new URLSearchParams(window.location.search);
    currentConversationId = urlParams.get('conversation_id') || 1;
    currentUserId = urlParams.get('user_id') || 1;
    
    loadModelInfo();
    loadResumes();
});

// Загрузить информацию о модели
async function loadModelInfo() {
    console.log('📡 Fetching model info...');
    try {
        const response = await fetch('/api/model-info');
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('✅ Model info received:', data);
        
        // Вывести в консоль
        console.log(`🤖 Model: ${data.status}`);
        console.log(`   Provider: ${data.provider}`);
        console.log(`   Model: ${data.model}`);
        console.log(`   API Key: ${data.api_key_present ? '✓' : '✗'}`);
        
        // Показать на странице
        const statusEl = document.getElementById('model-status');
        console.log('Status element:', statusEl);
        
        if (statusEl) {
            statusEl.textContent = data.status;
            statusEl.title = `Provider: ${data.provider}\nModel: ${data.model}`;
            console.log('✓ Status updated on page');
        } else {
            console.warn('⚠️ model-status element not found');
        }
    } catch (error) {
        console.error('❌ Error loading model info:', error);
        const statusEl = document.getElementById('model-status');
        if (statusEl) {
            statusEl.textContent = '⚠️ Error loading status';
        }
    }
}

// Переключение видимости секции
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        const toggle = event.target;
        if (section.style.display === 'none') {
            section.style.display = 'block';
            toggle.textContent = '▼';
        } else {
            section.style.display = 'none';
            toggle.textContent = '▶';
        }
    }
}

// Отправить сообщение в чат
function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Показать сообщение пользователя
    addMessage('user', message);
    input.value = '';
    
    // Отправить на сервер
    fetch('/api/chat/message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            conversation_id: currentConversationId,
            message: message
        })
    })
    .then(r => r.json())
    .then(data => {
        addMessage(data.role || 'assistant', data.content);
        
        // Если похоже, что резюме и вакансия загружены, проверить готовность
        if (message.toLowerCase().includes('резюме') || message.toLowerCase().includes('вакансия')) {
            checkReadyForGeneration();
        }
    })
    .catch(err => {
        addMessage('system', `Ошибка: ${err.message}`);
        console.error(err);
    });
}

// Добавить сообщение в чат
function addMessage(role, content) {
    const container = document.getElementById('messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}-message`;
    const roleText = role === 'user' ? 'Вы' : role === 'assistant' ? 'Ассистент' : 'Система';
    msgDiv.innerHTML = `<strong>${roleText}:</strong> ${escapeHtml(content)}`;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

// Загрузить файл
function triggerFileUpload() {
    document.getElementById('file-input').click();
}

function uploadFile() {
    const file = document.getElementById('file-input').files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', currentUserId);
    formData.append('conversation_id', currentConversationId);
    
    addMessage('system', `Загружаю ${file.name}...`);
    
    fetch('/api/upload-resume', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        addMessage('assistant', `Загружен файл ${file.name}. Найдено ${data.candidate_profile.jobs.length} мест работы.`);
        
        // Отобразить профиль кандидата
        displayCandidateProfile(data.candidate_profile);
        
        // Показать предупреждения
        if (data.warnings && data.warnings.length > 0) {
            addMessage('system', `⚠️ Предупреждения: ${data.warnings.join(', ')}`);
        }
        
        // Показать уточняющие вопросы
        if (data.questions && data.questions.length > 0) {
            addMessage('assistant', `Уточняющие вопросы: ${data.questions.join(' | ')}`);
        }
    })
    .catch(err => {
        addMessage('system', `Ошибка при загрузке: ${err.message}`);
        console.error(err);
    });
}

// Обработать вакансию
function processVacancy() {
    const vacancyText = document.getElementById('vacancy-input').value.trim();
    const resumeText = document.getElementById('user-input').value.trim();
    
    if (!vacancyText || !resumeText) {
        alert('Пожалуйста, заполните резюме и описание вакансии');
        return;
    }
    
    addMessage('system', 'Анализирую вакансию и генерирую адаптированное резюме...');
    
    fetch('/api/generate/full', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            user_id: currentUserId,
            conversation_id: currentConversationId,
            resume_text: resumeText,
            vacancy_text: vacancyText
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'ok') {
            addMessage('assistant', '✅ Резюме успешно сгенерировано!');
            currentResumeId = data.resume_id;
            
            // Отобразить все профили
            displayCandidateProfile(data.candidate_profile);
            displayVacancyProfile(data.vacancy_profile);
            displayStrategyBrief(data.strategy_brief);
            displayGeneratedResume(data.generated_resume);
            
            // Показать кнопки экспорта
            document.getElementById('export-buttons').style.display = 'flex';
            
            // Загрузить список резюме
            loadResumes();
        } else {
            addMessage('system', `❌ Ошибка: ${data.message || 'Неизвестная ошибка'}`);
        }
    })
    .catch(err => {
        addMessage('system', `Ошибка при генерации резюме: ${err.message}`);
        console.error(err);
    });
}

// Отобразить профиль кандидата
function displayCandidateProfile(profile) {
    currentCandidateProfile = profile;
    const json = JSON.stringify(profile, null, 2);
    document.getElementById('candidate-json').textContent = json;
}

// Отобразить профиль вакансии
function displayVacancyProfile(profile) {
    currentVacancyProfile = profile;
    const json = JSON.stringify(profile, null, 2);
    document.getElementById('vacancy-json').textContent = json;
}

// Отобразить стратегию
function displayStrategyBrief(strategy) {
    currentStrategyBrief = strategy;
    const json = JSON.stringify(strategy, null, 2);
    document.getElementById('strategy-json').textContent = json;
}

// Отобразить сгенерированное резюме
function displayGeneratedResume(resume) {
    if (resume.text) {
        document.getElementById('resume-content').innerHTML = `<pre>${escapeHtml(resume.text)}</pre>`;
    }
    
    if (resume.technical_report) {
        currentTechReport = resume.technical_report;
        document.getElementById('tech-report-json').textContent = JSON.stringify(resume.technical_report, null, 2);
        document.getElementById('tech-report').style.display = 'block';
    }
}

// Скачать TXT
function downloadTxt() {
    if (!currentResumeId) {
        alert('Нет сгенерированного резюме');
        return;
    }
    
    window.location.href = `/api/resumes/${currentResumeId}/download/txt`;
}

// Скачать PDF
function downloadPdf() {
    if (!currentResumeId) {
        alert('Нет сгенерированного резюме');
        return;
    }
    
    window.location.href = `/api/resumes/${currentResumeId}/download/pdf`;
}

// Загрузить список резюме
function loadResumes() {
    fetch(`/api/resumes?user_id=${currentUserId}`)
    .then(r => r.json())
    .then(data => {
        const list = document.getElementById('resumes-list');
        list.innerHTML = '';
        
        if (data.resumes && data.resumes.length > 0) {
            data.resumes.forEach(resume => {
                const card = document.createElement('div');
                card.className = 'resume-card';
                const date = new Date(resume.created_at).toLocaleDateString('ru-RU');
                
                card.innerHTML = `
                    <h4>${escapeHtml(resume.title)}</h4>
                    <p>Создано: ${date}</p>
                    <div class="resume-card-actions">
                        <button onclick="viewResume(${resume.id})">Просмотр</button>
                        <button onclick="downloadResumeTxt(${resume.id})">TXT</button>
                        <button onclick="downloadResumePdf(${resume.id})">PDF</button>
                    </div>
                `;
                list.appendChild(card);
            });
        } else {
            list.innerHTML = '<p class="placeholder">Нет ранее сгенерированных резюме</p>';
        }
    })
    .catch(err => console.error('Ошибка при загрузке резюме:', err));
}

// Просмотреть резюме
function viewResume(resumeId) {
    fetch(`/api/resumes/${resumeId}`)
    .then(r => r.json())
    .then(data => {
        currentResumeId = resumeId;
        displayGeneratedResume({
            text: data.resume_text,
            technical_report: data.technical_report
        });
        
        if (data.candidate_profile) {
            displayCandidateProfile(data.candidate_profile);
        }
        if (data.vacancy_profile) {
            displayVacancyProfile(data.vacancy_profile);
        }
        if (data.strategy_brief) {
            displayStrategyBrief(data.strategy_brief);
        }
        
        document.getElementById('export-buttons').style.display = 'flex';
        
        // Прокрутить к резюме
        document.querySelector('.result-panel').scrollIntoView({behavior: 'smooth'});
    })
    .catch(err => console.error('Ошибка при загрузке резюме:', err));
}

// Скачать резюме TXT
function downloadResumeTxt(resumeId) {
    window.location.href = `/api/resumes/${resumeId}/download/txt`;
}

// Скачать резюме PDF
function downloadResumePdf(resumeId) {
    window.location.href = `/api/resumes/${resumeId}/download/pdf`;
}

// Проверить готовность к генерации
function checkReadyForGeneration() {
    const resume = document.getElementById('user-input').value.trim();
    const vacancy = document.getElementById('vacancy-input').value.trim();
    
    if (resume && vacancy) {
        // Автоматически предложить генерацию
        addMessage('assistant', '✅ Резюме и вакансия загружены! Нажмите "Анализировать вакансию" для генерации адаптированного резюме.');
    }
}

// Скачать Candidate Profile как JSON
function downloadCandidateJSON() {
    if (!currentCandidateProfile) {
        alert('Профиль кандидата не загружен');
        return;
    }
    const json = JSON.stringify(currentCandidateProfile, null, 2);
    downloadJSON(json, 'candidate_profile.json');
}

// Скачать Vacancy Profile как JSON
function downloadVacancyJSON() {
    if (!currentVacancyProfile) {
        alert('Профиль вакансии не загружен');
        return;
    }
    const json = JSON.stringify(currentVacancyProfile, null, 2);
    downloadJSON(json, 'vacancy_profile.json');
}

// Скачать Strategy Brief как JSON
function downloadStrategyJSON() {
    if (!currentStrategyBrief) {
        alert('Стратегия не загружена');
        return;
    }
    const json = JSON.stringify(currentStrategyBrief, null, 2);
    downloadJSON(json, 'strategy_brief.json');
}

// Скачать Technical Report как JSON
function downloadTechReportJSON() {
    if (!currentTechReport) {
        alert('Технический отчёт не загружен');
        return;
    }
    const json = JSON.stringify(currentTechReport, null, 2);
    downloadJSON(json, 'technical_report.json');
}

// Скачать JSON файл
function downloadJSON(json, filename) {
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// Утилита: Экранировать HTML
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
