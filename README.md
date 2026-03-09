# Resume Career Consultant MVP

**Генерация адаптивных резюме: личный карьерный консультант на базе мультиагентной ИИ-системы**

## 📋 Описание проекта

Это демонстрационный MVP веб-приложения для адаптивной генерации резюме, разработанный специально для курсовой работы. Приложение использует мультиагентную ИИ-систему для анализа профиля кандидата и требований вакансии, а затем генерирует оптимизированное резюме.

## 🎯 Ключевые особенности

- ✅ **Безкодовый запуск** — без Docker, просто Python + pip
- ✅ **Работает без API ключа** — встроенный mock mode для демонстрации  
- ✅ **Мультиагентная система** — 4 специализированных агента
- ✅ **Серверный рендеринг** — никаких фреймворков вроде React, просто Jinja2 + HTML
- ✅ **Локальная БД** — SQLite, без внешних сервисов
- ✅ **Экспорт** — TXT и PDF форматы
- ✅ **Честная система** — не выдумывает факты, показывает warnings

## 🏗️ Архитектура

### 4 Агента:

1. **Candidate Profile Agent**
   - Извлекает данные из резюме пользователя
   - Нормализует опыт, навыки, образование
   - Выходные данные: `CandidateProfile` (JSON)

2. **Vacancy Analyzer Agent**
   - Анализирует текст вакансии
   - Выделяет must-have и nice-to-have навыки
   - Выходные данные: `VacancyProfile` (JSON)

3. **Career Strategy Agent**
   - Сравнивает профиль кандидата с требованиями вакансии
   - Рассчитывает fit score (0.0 - 1.0)
   - Определяет стратегию позиционирования
   - Выходные данные: `StrategyBrief` (JSON)

4. **Resume Writer & Critic Agent**
   - Генерирует оптимизированный текст резюме
   - Проводит self-check на галлюцинации
   - Выходные данные: `GeneratedResume` + `TechnicalReport`

### Технический стек:

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, Pydantic
- **Frontend**: Jinja2 шаблоны, vanilla JavaScript, HTMX
- **БД**: SQLite
- **LLM**: OpenAI API (real mode) + встроенные эвристики (mock mode)
- **Экспорт**: reportlab (PDF), встроенный TXT

## 🚀 Быстрый старт

### 1. Клонирование и подготовка

```bash
cd /path/to/project
python3 -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Конфигурация (опционально)

```bash
cp .env.example .env
# Отредактируй .env, если хочешь использовать OpenAI API
# Иначе приложение работает в mock mode
```

### 4. Запуск приложения

```bash
python run.py
```

Затем открой **http://localhost:8000** в браузере.

## 📖 Как использовать

### Пошаговый сценарий:

1. **Открой приложение** → Автоматически создается demo-user

2. **Вставь резюме**:
   - Напиши текст резюме в левом блоке
   - Или загрузи TXT файл кнопкой "Upload TXT"
   - Система парсит и показывает `CandidateProfile` JSON

3. **Вставь вакансию**:
   - Скопируй текст вакансии в большой textarea внизу
   - Нажми "Analyze Vacancy"
   - Система генерирует `VacancyProfile`

4. **Получи рекомендации**:
   - Система строит `StrategyBrief` с fit score и гайдлайнами
   - Видишь, какие навыки выделить, какие смягчить

5. **Скачай результат**:
   - На панели справа видишь сгенерированное резюме
   - Кнопки "Download TXT" и "Download PDF"

6. **История**:
   - Все сгенерированные резюме сохраняются в БД
   - Можно просмотреть и пересохранить старые версии

## 🔌 OpenAI Integration

### Real Mode (с API ключом)

Если настроить `.env`:
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo
OPENAI_ENABLED=true
```

То система:
- Будет использовать реальный OpenAI API вместо эвристик
- Сгенерирует более качественные JSON-структуры
- Напишет лучшее резюме

### Mock Mode (без API ключа)

По умолчанию (если `OPENAI_API_KEY` не заполнен):
- Система использует встроенные эвристики вместо LLM
- Все равно работает end-to-end
- Идеально для демонстрации и тестирования

## 📊 Структура проекта

```
.
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Конфиг с переменными окружения
│   ├── db.py                # SQLAlchemy setup
│   ├── models.py            # ORM модели
│   ├── schemas/             # Pydantic схемы
│   ├── agents/              # 4 агента
│   ├── services/            # LLM provider, orchestration, export
│   ├── repositories/        # Data access layer
│   ├── routers/             # API endpoints
│   ├── static/              # CSS, JS
│   └── templates/           # HTML (Jinja2)
├── data/                    # SQLite БД
├── uploads/                 # Загруженные файлы
├── exports/                 # Скачанные резюме
├── requirements.txt
├── .env.example
├── run.py                   # Script for running
└── README.md
```

## 🎓 Ключевые компоненты

### Pydantic Schemas

- `CandidateProfile` — профиль кандидата (jobs, skills, education)
- `VacancyProfile` — анализ вакансии (must-have skills, responsibilities)
- `StrategyBrief` — стратегия адаптации (fit score, positioning)
- `GeneratedResume` + `TechnicalReport` — финальный результат

### API Endpoints

```
GET     /                           # Главная страница
POST    /api/chat/message           # Отправить сообщение
GET     /api/chat/{id}              # История чата
POST    /api/upload-resume          # Загрузить резюме
POST    /api/generate/full          # Сгенерировать резюме
GET     /api/resumes                # Список резюме пользователя
GET     /api/resumes/{id}           # Получить резюме
GET     /api/resumes/{id}/download/txt
GET     /api/resumes/{id}/download/pdf
```

## ⚠️ Важные ограничения MVP

1. **Нет аутентификации** — используется demo-user для демонстрации
2. **No production deploy** — только локальный запуск
3. **Mock mode имеет подмяк** — хорошо для демо, но не заменяет реальный LLM
4. **Нет полной поддержки PDF/DOCX** — best effort, если не парсится, предложит вставить текст вручную
5. **Нет кэширования** — каждый запрос к LLM генерирует новый результат
6. **SQLite** — не масштабируется, но достаточно для MVP

## 🔍 Система не выдумывает факты

Запрещено в системе:
- ❌ Выдумывать компании
- ❌ Выдумывать должности
- ❌ Выдумывать технологии в skills
- ❌ Выдумывать цифры достижений
- ❌ Выдумывать опыт управления командой

Если данных не хватает:
- ⚠️ Возвращаются warnings
- 💬 Система задает уточняющие вопросы
- 🔤 Используются нейтральные формулировки

## 🧪 Примеры использования

### Пример резюме для вставки:

```
John Smith

Senior Software Engineer with 7 years of experience.

EXPERIENCE:

TechCorp Inc (2020-2024)
Position: Senior Python Developer
- Led team of 3 developers
- Built microservices in Python + FastAPI
- Reduced API response time by 40%

StartupXYZ (2018-2020)
Position: Full Stack Developer
- Built web applications in React + Django
- Handled 100K daily active users

SKILLS:
Python, JavaScript, SQL, React, FastAPI, Docker, AWS

EDUCATION:
B.S. Computer Science, State University (2018)

LANGUAGES:
English (Native), Spanish (Fluent)
```

### Пример вакансии для вставки:

```
Senior Python Developer

We are looking for an experienced Python developer to join our team.

Requirements:
- 5+ years of Python experience
- Experience with FastAPI or Django
- Knowledge of microservices architecture
- Experience with AWS or similar cloud platform

Nice to have:
- Leadership experience
- Open source contributions
- Experience with Docker and Kubernetes

Responsibilities:
- Design and implement scalable backend systems
- Mentor junior developers
- Participate in code reviews
- Collaborate with product team
```

## 📈 Информация о fit score

Fit score рассчитывается как:
- **Must-have skills match**: 50%
- **Nice-to-have skills match**: 30%
- **Experience level**: 20%

Результат: 0.0 - 1.0 (максимум 0.95)

## 🐛 Обработка ошибок

Приложение не падает при:
- Пустом резюме
- Некорректном формате вакансии
- Ошибке OpenAI API (переключается на mock)
- Невалидном ответе от LLM

Все ошибки показываются пользователю понятно в UI.

## 📝 Упрощения ради MVP

1. **Нет полноценного conversational AI** — управляемый сценарий, а не свободный чат
2. **Простые эвристики вместо LLM в mock mode** — достаточно для демо
3. **Нет кэширования результатов** — каждый раз новые генерации
4. **Базовый UI** — функционален, но не красивый
5. **Нет параллельной обработки** — последовательный pipeline
6. **Основной LLM API вызовов на backend** — security + stability

## 🚦 Статус проекта

✅ **Полностью рабочий MVP** с:
- ✅ Парсингом резюме
- ✅ Анализом вакансии
- ✅ Стратегическими рекомендациями
- ✅ Генерацией резюме
- ✅ Экспортом TXT/PDF
- ✅ Mock mode без API ключа
- ✅ Работающей БД и сохранением истории

## 💡 Что можно улучшить (future work)

1. Добавить реальную Aутентификацию (OAuth, JWT)
2. Улучшить UI дизайн (Tailwind, компоненты)
3. Добавить Rich PDF formatting (красивые стили)
4. Полная поддержка DOCX/PDF парсинга
5. Кэширование результатов OpenAI
6. Параллельная обработка агентов
7. Расширенная статистика и аналитика
8. WebSocket для real-time updates

## 📞 Вопросы

При возникновении проблем:
1. Проверь, что установлены все зависимости: `pip install -r requirements.txt`
2. Убедись, что порт 8000 свободен
3. Смотри логи в консоли (verbose mode по умолчанию)
4. Проверь, жив ли OpenAI API (если используешь real mode)

## 📄 Лицензия

MIT

---

**Разработано как MVP для курсовой работы по генерации адаптивных резюме** 🎓
