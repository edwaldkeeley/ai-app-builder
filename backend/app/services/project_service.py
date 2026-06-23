"""Project CRUD backed by PostgreSQL via raw SQL (asyncpg).

All methods are async.  The connection pool is obtained from
``app.db.database.get_pool()``.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import asyncpg

from app.db.database import get_pool
from app.models.schemas import (
    ChatMessageSchema,
    FileType,
    Project,
    ProjectCreate,
    ProjectFile,
    ProjectSummary,
    ProjectUpdate,
)


class ProjectService:
    """Manages sandbox projects in PostgreSQL."""

    # ── helpers ────────────────────────────────────────────────────

    @staticmethod
    def _row_to_project(row: asyncpg.Record, file_rows: list[asyncpg.Record]) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=row["status"],
            files=[
                ProjectFile(path=r["path"], content=r["content"], file_type=r["file_type"])
                for r in file_rows
            ],
            created_at=row["created_at"].replace(tzinfo=None),
            updated_at=row["updated_at"].replace(tzinfo=None),
        )

    # ── CRUD ──────────────────────────────────────────────────────

    async def create(self, data: ProjectCreate) -> Project:
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO projects (name, description)
                    VALUES ($1, $2)
                    RETURNING id, name, description, status, created_at, updated_at
                    """,
                    data.name,
                    data.description,
                )

                boilerplate = [
                    ("index.html", HTML_BOILERPLATE, "html"),
                    ("style.css", CSS_BOILERPLATE, "css"),
                    ("script.js", JS_BOILERPLATE, "javascript"),
                ]
                for path, content, file_type in boilerplate:
                    await conn.execute(
                        """
                        INSERT INTO files (project_id, path, content, file_type)
                        VALUES ($1, $2, $3, $4)
                        """,
                        row["id"],
                        path,
                        content,
                        file_type,
                    )

                file_rows = await conn.fetch(
                    "SELECT path, content, file_type FROM files WHERE project_id = $1 ORDER BY path",
                    row["id"],
                )

        return self._row_to_project(row, file_rows)

    async def get(self, project_id: UUID) -> Project | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, name, description, status, created_at, updated_at FROM projects WHERE id = $1",
                project_id,
            )
            if row is None:
                return None
            file_rows = await conn.fetch(
                "SELECT path, content, file_type FROM files WHERE project_id = $1 ORDER BY path",
                project_id,
            )
        return self._row_to_project(row, file_rows)

    async def list_all(self) -> list[ProjectSummary]:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.id, p.name, p.description, p.status,
                       p.created_at, p.updated_at,
                       COUNT(f.id)::int AS file_count
                FROM projects p
                LEFT JOIN files f ON f.project_id = p.id
                GROUP BY p.id
                ORDER BY p.updated_at DESC
                """
            )
        return [
            ProjectSummary(
                id=r["id"],
                name=r["name"],
                description=r["description"],
                status=r["status"],
                file_count=r["file_count"],
                created_at=r["created_at"].replace(tzinfo=None),
                updated_at=r["updated_at"].replace(tzinfo=None),
            )
            for r in rows
        ]

    async def update(self, project_id: UUID, data: ProjectUpdate) -> Project | None:
        # Build dynamic SET clause for non-None fields
        sets: list[str] = []
        params: list = []
        idx = 1
        if data.name is not None:
            sets.append(f"name = ${idx}")
            params.append(data.name)
            idx += 1
        if data.description is not None:
            sets.append(f"description = ${idx}")
            params.append(data.description)
            idx += 1

        if not sets:
            return await self.get(project_id)

        pool = get_pool()
        async with pool.acquire() as conn:
            params.append(project_id)
            sql = (
                f"UPDATE projects SET {', '.join(sets)} WHERE id = ${idx}"
                " RETURNING id, name, description, status, created_at, updated_at"
            )
            row = await conn.fetchrow(sql, *params)
            if row is None:
                return None
            file_rows = await conn.fetch(
                "SELECT path, content, file_type FROM files WHERE project_id = $1 ORDER BY path",
                project_id,
            )
        return self._row_to_project(row, file_rows)

    async def delete(self, project_id: UUID) -> bool:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM projects WHERE id = $1", project_id)
        return int(result.split()[-1]) > 0

    # ── File operations ───────────────────────────────────────────

    async def upsert_file(self, project_id: UUID, path: str, content: str) -> ProjectFile | None:
        ext = Path(path).suffix.lower()
        type_map: dict[str, FileType] = {
            ".html": FileType.html,
            ".htm": FileType.html,
            ".css": FileType.css,
            ".js": FileType.js,
            ".json": FileType.json,
            ".py": FileType.python,
        }
        file_type = type_map.get(ext, FileType.other)

        pool = get_pool()
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT 1 FROM projects WHERE id = $1", project_id)
            if exists is None:
                return None

            row = await conn.fetchrow(
                """
                INSERT INTO files (project_id, path, content, file_type)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (project_id, path)
                DO UPDATE SET content = EXCLUDED.content, file_type = EXCLUDED.file_type
                RETURNING path, content, file_type
                """,
                project_id,
                path,
                content,
                file_type.value,
            )

            # Touch project updated_at so list order reflects latest activity
            await conn.execute("UPDATE projects SET updated_at = NOW() WHERE id = $1", project_id)

        return ProjectFile(path=row["path"], content=row["content"], file_type=row["file_type"])

    async def delete_file(self, project_id: UUID, path: str) -> bool:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM files WHERE project_id = $1 AND path = $2",
                project_id,
                path,
            )
            deleted = int(result.split()[-1]) > 0
            if deleted:
                await conn.execute("UPDATE projects SET updated_at = NOW() WHERE id = $1", project_id)
            return deleted

    # ── Chat messages ───────────────────────────────────────────

    async def get_chat_messages(self, project_id: UUID) -> list[ChatMessageSchema]:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, project_id, role, content, files, created_at "
                "FROM chat_messages WHERE project_id = $1 ORDER BY created_at",
                project_id,
            )
        return [
            ChatMessageSchema(
                id=r["id"],
                project_id=r["project_id"],
                role=r["role"],
                content=r["content"],
                files=[ProjectFile(**f) for f in (json.loads(r["files"]) if isinstance(r["files"], str) else (r["files"] or []))],
                created_at=r["created_at"].replace(tzinfo=None),
            )
            for r in rows
        ]

    async def save_chat_message(self, project_id: UUID, role: str, content: str, files: list[ProjectFile] | None = None) -> ChatMessageSchema:
        pool = get_pool()
        files_json = json.dumps([f.model_dump() for f in (files or [])])
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO chat_messages (project_id, role, content, files) "
                "VALUES ($1, $2, $3, $4) "
                "RETURNING id, project_id, role, content, files, created_at",
                project_id,
                role,
                content,
                files_json,
            )
        return ChatMessageSchema(
            id=row["id"],
            project_id=row["project_id"],
            role=row["role"],
            content=row["content"],
            files=[ProjectFile(**f) for f in (json.loads(row["files"]) if isinstance(row["files"], str) else (row["files"] or []))],
            created_at=row["created_at"].replace(tzinfo=None),
        )


# ── Boilerplate templates ──────────────────────────────────

HTML_BOILERPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>My Project</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <h1>Hello, Sandbox!</h1>
  <p>Start editing to see your changes live.</p>
  <script src="script.js"></script>
</body>
</html>
"""

CSS_BOILERPLATE = """\
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: system-ui, -apple-system, sans-serif;
  background: #f5f5f5;
  color: #1a1a1a;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
}

h1 {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

p {
  font-size: 1.125rem;
  color: #555;
}
"""

JS_BOILERPLATE = """\
console.log('Sandbox ready!');
"""
