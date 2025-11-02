# Mini-Trello (Monorepo)

Полноценный Trello-клон: backend (Flask + PostgreSQL + Celery + Redis + Docker), frontend (Next.js), reverse-proxy nginx.

---

## Быстрый старт через Docker Compose

```bash
git clone https://github.com/NURJAKS/Mini-Trello.git
cd Mini-Trello
docker-compose up --build
```

После билда сервисы будут доступны локально, например:
- Frontend: [http://localhost:3001](http://localhost:3001)
- API-gateway Kong: [http://localhost:8000](http://localhost:8000) (вся маршрутизация)
- Nginx: [http://localhost](http://localhost)
- Отдельные сервисы backend: порты 5001...5005 (см. docker-compose.yml)

> ⚠️ Все переменные окружения и пароли по умолчанию прописаны в `docker-compose.yml` для тестовой работы.

---

## Структура монорепозитория

- `/backend/` - микросервисы: user_service, board_service, card_service, comment_service, attachment_service (каждый отдельный Flask-приложение)
- `/frontend/` - Next.js-приложение (UI kanban)
- `docker-compose.yml` - основной orchestration-манифест сервисов, БД и фронта
- `nginx.conf` - пример конфиг-прокси nginx

---

## Системные требования
- Docker + Docker Compose
- (или) Python 3.11+, Node.js 20+, npm для ручного запуска

---

## Переменные окружения
В docker-compose все основные переменные заполнены:
- JWT_SECRET, DATABASE_URL, REDIS_URL (для каждого сервиса свои)
- NEXT_PUBLIC_API_URL (для фронта)

> Для PROD: обязательно заменить все секреты и закрыть доступы снаружи.

---

## Ручной запуск (альтернатива Docker)

1. **Backend-сервисы**
  - Для каждого сервисa (например, `backend/user_service`):
    ```bash
    cd backend/user_service
    pip install -r ../requirements.txt
    python app.py
    ```
  - Не забудьте поднять соответствующую БД PostgreSQL и Redis, прописать коннекты через ENV переменные!

2. **Frontend**
    ```bash
    cd frontend
    npm i
    npm run dev
    # next.js UI по умолчанию на http://localhost:3000
    ```
---

## Первый запуск после клона
1. Клонируйте:
    ```bash
    git clone https://github.com/NURJAKS/Mini-Trello.git
    cd Mini-Trello
    ```
2. Запустите:
    ```bash
    docker-compose up --build
    ```
3. Откройте браузер и проверьте:
    - [http://localhost:3001](http://localhost:3001) (UI)
    - [http://localhost:8000](http://localhost:8000) (API gateway)

---

## Сервисы и их порты
- user_service: 5001
- board_service: 5002
- card_service: 5003
- comment_service: 5004 (+ celery)
- attachment_service: 5005
- kong: 8000, 8001
- frontend: 3001
- nginx (проксирует фронт): 80

---

## Миграции
Для работы БД миграций используйте alembic и flask-migrate в папке каждого сервиса backend. Примеры команд внутри сервиса:
```bash
flask db init
flask db migrate
flask db upgrade
```

---

## ЧаВо
- **Ошибка портов/БД**: убедитесь, что настройки в .env и docker-compose не конфликтуют
- **Нет доступа к UI?**: дождитесь старта контейнера `frontend` и `nginx`, либо используйте прямой доступ
- **Клонируется не всё?**: проверьте, что нет "embedded repos" и что `git submodule` не используется!

---

## Контакты
Автор: github.com/NURJAKS
