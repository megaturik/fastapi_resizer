# fastapi_resizer

Асинхронный Python-сервис для загрузки, валидации, ресайза, сжатия и выдачи изображений. Поддерживает режимы `stream` и `cache`, автоматически определяет расширения по заголовкам, проверяет размер и сохраняет либо отдает изображения в нужном формате.

## Стек

- Python >= 3.9  
- FastAPI == 0.115.13  
- httpx  
- Pillow  

## Переменные окружения (.env)

| Переменная        | Описание                                                                  |
|------------------|---------------------------------------------------------------------------|
| `RESIZE_DIR`     | Абсолютный путь к папке для сохранения обработанных изображений (`cache`-режим) |
| `MAX_IMAGE_SIZE` | Максимальный размер изображения в байтах (например, `31457280` для 30 MB) |
| `QUALITY`        | Качество сжатия (от 0 до 100)                                              |
| `ORIGIN_URL`     | Базовый URL-источник изображений                                           |
| `MODE`           | Режим работы: `stream` или `cache`                                        |

**Пример `.env`:**

```
RESIZE_DIR=/var/www/fastapi_resizer/resizes/
MAX_IMAGE_SIZE=31457280
QUALITY=80
ORIGIN_URL='https://example.com/'
MODE='stream'
```

## Установка и запуск

### При использовании системного Python >= 3.9:

```bash
# Клонируйте репозиторий
git clone https://github.com/megaturik/fastapi_resizer.git
cd fastapi_resizer

# Создайте и активируйте виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Установите зависимости
pip install -r requirements.txt

# Настройка переменных окружения
cd app
cp .env.example .env
vim .env  # отредактируйте .env под своё окружение

# Запуск приложения
fastapi dev main.py 

# или запуск через Uvicorn:
uvicorn main:app --access-log --host 127.0.0.1 --port 8000
```

### Если в системе нет Python >= 3.9, используйте uv:

```bash
# Установка uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Перейдите в директорию проекта
cd fastapi_resizer

# Установка Python и зависимостей
uv sync

# Запуск приложения
uv run fastapi dev main.py

# или запуск через Uvicorn:
uv run uvicorn main:app --access-log --host 127.0.0.1 --port 8000
```
