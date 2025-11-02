# 🎯 УПРОЩЕННАЯ СХЕМА АРХИТЕКТУРЫ

```
                    ┌─────────────────┐
                    │     USERS       │
                    │  (Browser)      │
                    └─────────┬───────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   NGINX PROXY   │
                    │  :8081          │
                    └─────────┬───────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │            FRONTEND                    │
        │  Next.js + React + TypeScript         │
        │  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
        │  │ /login  │ │ /todos  │ │ /kanban │   │
        │  │ /signup │ │ /lists  │ │         │   │
        │  └─────────┘ └─────────┘ └─────────┘   │
        └─────────────────┬───────────────────────┘
                          │ HTTP API Calls
                          ▼
        ┌─────────────────────────────────────────┐
        │            BACKEND                      │
        │  Flask + SQLAlchemy + Alembic          │
        │  ┌─────────────────────────────────┐   │
        │  │        API ENDPOINTS            │   │
        │  │  /api/login    /api/signup      │   │
        │  │  /api/lists    /api/todos       │   │
        │  │  /api/todos/bulk                │   │
        │  │  /api/todos/move                │   │
        │  └─────────────────────────────────┘   │
        │  ┌─────────────────────────────────┐   │
        │  │      SQLALCHEMY MODELS           │   │
        │  │  User → TodoList → Todo          │   │
        │  │  Todo → TodoItem + TodoComment   │   │
        │  └─────────────────────────────────┘   │
        └─────────────────┬───────────────────────┘
                          │ SQL Queries
                          ▼
        ┌─────────────────────────────────────────┐
        │            DATABASE                     │
        │  PostgreSQL 16                         │
        │  ┌─────────────────────────────────┐   │
        │  │         TABLES                  │   │
        │  │  users, todo_lists, todos       │   │
        │  │  todo_items, todo_comments      │   │
        │  │  todo_attachments               │   │
        │  └─────────────────────────────────┘   │
        └─────────────────┬───────────────────────┘
                          │ Cache Operations
                          ▼
        ┌─────────────────────────────────────────┐
        │            CACHE                       │
        │  Redis 7                               │
        │  ┌─────────────────────────────────┐   │
        │  │      CACHE DATA                 │   │
        │  │  refresh:token_id               │   │
        │  │  blacklist:token                │   │
        │  │  session:user_id                │   │
        │  └─────────────────────────────────┘   │
        └─────────────────────────────────────────┘
```

## 🔄 ПОТОК ДАННЫХ

### 1. ПОЛЬЗОВАТЕЛЬ ВХОДИТ В СИСТЕМУ
```
User → Frontend → NGINX → Backend → PostgreSQL
  ↓      ↓         ↓        ↓         ↓
Login → JWT → Proxy → Validate → Store User
  ↓      ↓         ↓        ↓         ↓
Token → Store → CORS → Redis → Session
```

### 2. СОЗДАЕТ ЗАДАЧУ
```
User → Frontend → NGINX → Backend → SQLAlchemy → PostgreSQL
  ↓      ↓         ↓        ↓         ↓           ↓
Input → Form → Proxy → API → Model → Table
  ↓      ↓         ↓        ↓         ↓           ↓
Submit → POST → Route → ORM → Insert → Store
```

### 3. ПЕРЕТАСКИВАЕТ ЗАДАЧУ
```
User → Frontend → NGINX → Backend → SQLAlchemy → PostgreSQL
  ↓      ↓         ↓        ↓         ↓           ↓
Drag → @dnd-kit → Proxy → API → Model → Update
  ↓      ↓         ↓        ↓         ↓           ↓
Drop → Position → Route → ORM → Position → Store
```

## 🛠️ ТЕХНОЛОГИИ ПО СЛОЯМ

### Frontend Layer
- **Next.js 14** - React Framework
- **TypeScript** - Type Safety  
- **@dnd-kit** - Drag & Drop
- **Tailwind CSS** - Styling

### Backend Layer  
- **Flask 3.0** - Web Framework
- **SQLAlchemy 3.1** - ORM
- **Alembic 1.13** - Migrations
- **PyJWT 2.9** - Authentication

### Database Layer
- **PostgreSQL 16** - Primary Database
- **Connection Pooling** - Performance
- **Foreign Keys** - Data Integrity

### Cache Layer
- **Redis 7** - Session Storage
- **JWT Blacklist** - Security
- **Refresh Tokens** - Authentication

## 📊 ПОРТЫ

| Сервис    | Порт  | URL                    |
|-----------|-------|------------------------|
| Frontend  | 3001  | http://localhost:3001  |
| Backend   | 5000  | http://localhost:5000  |
| Database  | 5432  | localhost:5432         |
| Redis     | 6379  | localhost:6379         |
| Adminer   | 8080  | http://localhost:8080  |
| NGINX     | 8081  | http://localhost:8081  |

## 🎯 ОСНОВНЫЕ КОМПОНЕНТЫ

### Frontend (Next.js)
- **Страницы**: /login, /signup, /todos, /kanban, /lists
- **Функции**: Авторизация, CRUD, Drag&Drop, Поиск, Фильтры
- **Технологии**: React, TypeScript, @dnd-kit, Tailwind

### Backend (Flask + SQLAlchemy)
- **API**: REST endpoints для всех операций
- **Модели**: User, TodoList, Todo, TodoItem, TodoComment
- **Аутентификация**: JWT + Redis для сессий
- **Миграции**: Alembic для версионирования БД

### Database (PostgreSQL)
- **Таблицы**: 6 основных таблиц с связями
- **Индексы**: Для быстрого поиска
- **Ограничения**: Foreign Keys для целостности данных

### Cache (Redis)
- **Refresh токены**: Для обновления JWT
- **Blacklist**: Для отозванных токенов
- **Сессии**: Временное хранение данных

## 🚀 ЗАПУСК

```bash
# Запуск всех сервисов
docker compose up -d --build

# Проверка
curl http://localhost:5000/health
curl http://localhost:3001
curl http://localhost:8081
```

**Архитектура готова к продакшену!** 🎉
