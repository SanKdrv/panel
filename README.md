# Analytic Panel — административная панель RAG-системы

Веб-панель для оператора RAG-системы. Спроектирована по главе 3
бакалаврского диплома и реализует все 9 функциональных требований из
раздела 2.1.

## Архитектура

Трёхзвенное приложение:

- **Frontend**: Vue 3 + Vite + Bootstrap 5 + Vue Router. Раздаётся
  через nginx.
- **Backend**: FastAPI. Прокси к RAG API + локальная аутентификация
  + модуль автоматизированной оценки качества + экспорт метрик в
  Prometheus.
- **External**: RAG API (внешняя система), Prometheus + Grafana
  (мониторинг и исторические тренды качества).

Собственная база данных не требуется — вся история ведётся в RAG API,
а метрики качества — в Prometheus (gauge-метрики).

## Структура репозитория

```
analytic-panel/
├── backend/                 # FastAPI
│   ├── app/
│   │   ├── routers/         # auth, system, documents, prompts,
│   │   │                    # generate, leads, mautic, quality
│   │   ├── services/        # rag_client, quality, metrics
│   │   ├── data/            # gold_dataset.json
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── models.py
│   │   └── main.py
│   ├── tests/               # pytest — 9 файлов, ~50 тестов
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # Vue 3 + Vite
│   ├── src/
│   │   ├── views/           # 8 экранов
│   │   ├── components/
│   │   ├── api/
│   │   ├── store/
│   │   └── router/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── ops/
│   ├── prometheus/prometheus.yml
│   └── grafana/provisioning/dashboards/dashboards.yml
├── docker-compose.yml
└── .env.example
```

## Запуск

### 1. Подготовка `.env`

```bash
cp .env.example .env
# отредактировать RAG_API_SECRET, ADMIN_PASSWORD, SESSION_SECRET
```

### 2. Полный стек через Docker

```bash
docker compose up --build
```

После запуска:

- Панель: http://localhost:5173
- Backend API: http://localhost:8001 (Swagger на `/docs`)
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

### 3. Локальная разработка

Backend:
```bash
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8001
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Аутентификация

Логин/пароль задаются в `.env`:
```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secret
SESSION_SECRET=...   # для подписи JWT
```

При входе фронтенд получает JWT, который хранится в localStorage и
прикладывается ко всем запросам через заголовок `Authorization: Bearer`.

## Эндпоинты бэкенда

| Группа | Метод + путь | Назначение |
|---|---|---|
| auth | POST `/api/auth/login` | Логин -> JWT |
| auth | GET  `/api/auth/me` | Текущий пользователь |
| system | GET  `/api/system/health` | Здоровье RAG (публичный) |
| system | GET  `/api/system/dashboard` | Дашборд (health + grafana url) |
| documents | GET/POST `/api/documents/resource-types` | Типы ресурсов |
| documents | POST `/api/documents` | Загрузка документа |
| documents | GET  `/api/documents/{id}` | Получение ресурса |
| documents | POST `/api/documents/import/email` | Импорт Mautic |
| documents | GET  `/api/documents/vector-db/status` | Статус Qdrant |
| prompts | GET/PUT `/api/prompts` | 4 промпта воронки |
| generate | POST `/api/generate` | Запуск генерации |
| generate | GET  `/api/generate/status/{token}` | Статус задачи |
| leads | GET `/api/leads/{lead_id}` | Карточка лида |
| mautic | POST/PATCH `/api/mautic/field` | Поля Mautic |
| mautic | GET  `/api/mautic/contact/check` | Уникальность email |
| quality | POST `/api/quality/evaluate` | Запуск оценки качества |
| quality | GET  `/api/quality/latest` | Последний результат |
| metrics | GET  `/metrics` | Prometheus exposition |

## Модуль оценки качества

Реализует пайплайн из раздела 3.4 диплома:

1. Загрузка золотого тест-сета (`app/data/gold_dataset.json`).
2. Вызов RAG API для каждого вопроса, замер TPS.
3. **Faithfulness** — LLM-as-judge (Ollama).
4. **Answer Relevance** — косинусное сходство эмбеддингов.
5. **Context Precision** — доля ключевых слов эталона в ответе.
6. Агрегация и сравнение с ОДЗ.
7. Публикация Prometheus gauge-метрик.
8. Отображение на экране «Оценка качества».

Prometheus метрики:
- `rag_faithfulness`
- `rag_answer_relevance`
- `rag_context_precision`
- `rag_tps`
- `rag_quality_samples`
- `rag_quality_run_timestamp_seconds`

## Тесты

Backend (pytest, 9 файлов):

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

Покрывает: аутентификацию, JWT, все роутеры (с замоканным RAG-клиентом),
RAG-клиент (через respx), модуль качества (с замоканными judge/embed).

Frontend (vitest):

```bash
cd frontend
npm install
npm run test
```

