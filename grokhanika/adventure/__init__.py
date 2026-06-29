"""Модуль текстового приключения «Гроханики» с ИИ-гейм-мастером.

Ядро игры поверх боевого движка: ИИ ведёт повествование, опираясь на карточки и
лор из БД (RAG на локальных эмбеддингах), а не выдумывает мир. Используются
локальные open-source модели (через OpenAI-совместимый эндпоинт) и локальный
эмбеддер (sentence-transformers). Состояние сессии и настройки — в БД.

Подмодули:

* :mod:`grokhanika.adventure.config`     — конфиг LLM/эмбеддера (БД + env-дефолты);
* :mod:`grokhanika.adventure.llm`        — клиент OpenAI-совместимого сервера;
* :mod:`grokhanika.adventure.embeddings` — обёртка sentence-transformers;
* :mod:`grokhanika.adventure.retrieval`  — семантический поиск по карточкам/лору;
* :mod:`grokhanika.adventure.memory`     — окно/компактинг/эпизодическая память;
* :mod:`grokhanika.adventure.intent`     — анализ намерений игрока (JSON);
* :mod:`grokhanika.adventure.prompts`    — сборка системных промтов;
* :mod:`grokhanika.adventure.narrator`   — потоковый ответ ГМ;
* :mod:`grokhanika.adventure.scene`      — состояние сцены (закреплённые карточки);
* :mod:`grokhanika.adventure.session`    — оркестрация хода поверх БД.
"""
