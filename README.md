# DnD Game Master

Веб-приложение — ИИ ведущий для настольных ролевых игр. Использует локальную LLM (Ollama) и механики D&D 5e.

## Требования

- Python 3.11+
- [Ollama](https://ollama.com/) с загруженной моделью (например `llama3`, `mistral`, `gemma3`)

## Быстрый старт

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Запустить Ollama (отдельный терминал)
ollama serve
ollama pull llama3   # или другая модель

# 3. Запустить приложение
python run.py

# 4. Открыть в браузере
# С этого же ПК:  http://localhost:8000
# С телефона по локальной сети:  http://<IP-адрес-ПК>:8000
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `PORT` | `8000` | Порт сервера |
| `LLM_BASE_URL` | `http://localhost:11434` | URL Ollama |
| `LLM_MODEL` | `llama3` | Название модели |
| `LLM_TEMPERATURE` | `0.8` | Температура генерации |
| `LLM_MAX_TOKENS` | `1024` | Максимум токенов в ответе |
| `DB_PATH` | `dnd_game.db` | Путь к SQLite базе данных |

## Доступ с телефона

Если нужен доступ из интернета (а не только по локальной сети):

```bash
# Вариант 1: ngrok
ngrok http 8000

# Вариант 2: cloudflared tunnel
cloudflare tunnel --url http://localhost:8000
```

## Функциональность

- **Создание приключения**: название, описание мира, до 4 персонажей с полными D&D характеристиками
- **Ролевой отыгрыш**: LLM держит роль GM и не выходит из образа
- **Боевая система**: броски инициативы, атаки, урона, спасброски — как в D&D 5e
- **Трекер HP**: управление здоровьем персонажей прямо в игре
- **История сессий**: все приключения сохраняются в SQLite
- **WebSocket**: потоковая передача ответов LLM в реальном времени

## Структура проекта

```
├── backend/
│   ├── main.py       # FastAPI приложение, WebSocket
│   ├── models.py     # SQLAlchemy модели (Adventure, Character, Message)
│   ├── schemas.py    # Pydantic схемы
│   ├── database.py   # Подключение к SQLite
│   ├── llm.py        # Клиент Ollama, системный промпт
│   └── dnd.py        # Механики D&D (кубики, боёвка)
├── frontend/
│   ├── index.html    # SPA
│   └── static/
│       ├── style.css
│       └── app.js
├── requirements.txt
└── run.py
```
