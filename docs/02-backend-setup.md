# Backend Setup (Phase 1)

## Directory Structure

```
backend/
├── main.py                  # FastAPI entry point
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables
└── app/
    ├── __init__.py
    ├── config.py            # Pydantic Settings (env-based config)
    ├── db/                  # Database layer
    │   ├── __init__.py
    │   ├── database.py      # asyncpg pool manager + migration runner
    │   └── migrations/      # Append-only SQL migrations
    │       └── 001_create_tables.sql
    ├── models/
    │   ├── __init__.py
    │   └── schemas.py       # All Pydantic request/response models
    ├── routers/
    │   ├── __init__.py
    │   ├── projects.py      # CRUD: /api/projects
    │   └── sandbox.py       # File ops: /api/sandbox
    └── services/
        ├── __init__.py
        └── project_service.py  # PostgreSQL-backed project + file management
```

## Prerequisites

- Python 3.10+
- PostgreSQL 14+ running locally

### Create the Database

```bash
createdb ai_design_sandbox
# or via psql:
psql -U postgres -c "CREATE DATABASE ai_design_sandbox;"
```

## Running the Backend

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Start dev server
uvicorn main:app --reload

# Or from project root
python run.py
```

On startup, the app will:
1. Connect to PostgreSQL using the `DATABASE_URL` from `.env`
2. Run any pending migrations (creates tables if first run)
3. Start the API server

The API docs are available at **http://localhost:8000/docs** (Swagger UI).

## API Endpoints (Phase 1)

### Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/` | List all projects |
| POST | `/api/projects/` | Create a new project |
| GET | `/api/projects/{id}` | Get project details + files |
| PATCH | `/api/projects/{id}` | Update project name/description |
| DELETE | `/api/projects/{id}` | Delete a project |

### Sandbox

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sandbox/{id}` | Get full sandbox state |
| PUT | `/api/sandbox/{id}/files` | Create/update a file |
| DELETE | `/api/sandbox/{id}/files?path=...` | Delete a file |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |

## Configuration

All config lives in `app/config.py` and is driven by environment variables (or `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | "AI Design Sandbox" | App title |
| `DEBUG` | `true` | Debug mode |
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8000` | Bind port |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/ai_design_sandbox` | PostgreSQL connection string |
| `DATABASE_POOL_MIN_SIZE` | `2` | Minimum pool connections |
| `DATABASE_POOL_MAX_SIZE` | `10` | Maximum pool connections |

## Project Model

Each project contains:
- `id` (UUID) — unique identifier
- `name` — human-readable name
- `description` — optional description
- `status` — `idle`, `generating`, or `error`
- `files` — list of `{path, content, file_type}`
- `created_at` / `updated_at` — timestamps

New projects are created with three boilerplate files: `index.html`, `style.css`, and `script.js`.

## Database Migrations

Migrations live in `app/db/migrations/` as numbered `.sql` files. They are **append-only** — never modify an existing migration file; add a new one instead.

```bash
# Example: add a new migration
touch backend/app/db/migrations/002_add_user_preferences.sql
# Write your SQL, then restart the server — it runs automatically
```

The `schema_migrations` table tracks what's been applied, so each migration runs exactly once.
