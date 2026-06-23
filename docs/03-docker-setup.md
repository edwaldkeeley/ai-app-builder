# Docker Setup

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                         │
│                                                          │
│  ┌──────────┐     ┌──────────┐     ┌──────────────────┐ │
│  │ Frontend │────▶│ Backend  │────▶│  PostgreSQL 16   │ │
│  │ :3000    │     │ :8000    │     │  :5432           │ │
│  │ (Next.js)│     │ (FastAPI)│     │  (db service)    │ │
│  └──────────┘     └──────────┘     └──────────────────┘ │
│       │                │                                 │
│       ▼                ▼                                 │
│  Host:3000         Host:8000                             │
└─────────────────────────────────────────────────────────┘
```

## Services

### db (PostgreSQL 16 Alpine)

- **Image:** `postgres:16-alpine`
- **Port:** 5432 (mapped to host)
- **Volume:** `pgdata` named volume for data persistence
- **Health check:** `pg_isready -U postgres` every 5 seconds
- **Credentials:** postgres / postgres (dev only)

### backend (FastAPI)

- **Build context:** `./backend`
- **Port:** 8000 (mapped to host)
- **Bind mount:** `./backend:/app` for hot reload
- **Depends on:** `db` (waits for healthy)
- **DATABASE_URL:** `postgresql://postgres:postgres@db:5432/ai_design_sandbox`

### frontend (Next.js)

- **Build context:** `./frontend`
- **Port:** 3000 (mapped to host)
- **Bind mount:** `./frontend:/app` for hot reload
- **Excluded volumes:** `/app/node_modules`, `/app/.next` (use container's installed deps)

## Network

All three services share the default Compose network. They can reach each other by service name (`db`, `backend`, `frontend`).

## Volumes

| Volume | Purpose |
|--------|---------|
| `pgdata` | Persists PostgreSQL data across restarts |

## Environment Variables

The `docker-compose.yml` sets all necessary environment variables. The local `.env` files are not used when running in Docker.

### Key Overrides

| Variable | Docker Value | Local Default |
|----------|-------------|---------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@db:5432/ai_design_sandbox` | `localhost` instead of `db` |
| `HOST` | `0.0.0.0` | `127.0.0.1` |

## Quick Start

```bash
# Build and start all services
docker compose up --build

# Or run in detached mode (background)
docker compose up --build -d
```

The app will be available at:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## Useful Commands

```bash
# View logs
docker compose logs -f

# View logs for a specific service
docker compose logs -f backend

# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes database data)
docker compose down -v

# Rebuild a single service
docker compose build backend

# Run a command inside a running container
docker compose exec backend python -c "print('hello')"

# Access PostgreSQL directly
docker compose exec db psql -U postgres -d ai_design_sandbox
```

## Troubleshooting

### Port Conflicts

If port 5432, 8000, or 3000 is already in use on the host, change the host port in `docker-compose.yml`:

```yaml
ports:
  - "5433:5432"  # Map host 5433 to container 5432
```

### Rebuilding

After changing dependencies (requirements.txt or package.json), rebuild:

```bash
docker compose build --no-cache backend
docker compose build --no-cache frontend
```

### Database Reset

To reset the database:

```bash
docker compose down -v    # Stops and removes volumes
docker compose up -d      # Starts fresh
```

### Viewing Logs

```bash
docker compose logs -f backend    # Follow backend logs
docker compose logs -f frontend   # Follow frontend logs
docker compose logs -f db         # Follow database logs
```
