# AI Design Sandbox — CLAUDE.md

> **Workflow:** After every design discussion, I auto-update this file and the memory files to reflect decisions made. If something seems out of date, it probably is — just ask.

## Project Overview

AI-powered design-to-code platform. Users describe what they want in natural language, and the platform generates a fully editable web project with a live preview and code editor.

- **Phase 1 (Complete)**: Backend — FastAPI with project CRUD, sandbox file operations, PostgreSQL persistence via raw SQL, AI engine with OpenAI-compatible HTTP provider.
- **Phase 2 (Complete)**: Frontend — ChatGPT-inspired layout with centered chat landing page, Monaco editor, live canvas iframe preview, sidebar toggles between project list and chat. All 44 bugs (18 critical + 26 medium/low) from frontend and backend audits fixed.
- **Phase 3 (Not Started)**: Polish, testing, Figma integration, ZIP export, design upload.

## Architecture

```
Next.js Frontend (port 3000)  ←→  FastAPI Backend (port 8000)
                                           │
                               PostgreSQL 16 (port 5432)
```

Monorepo with two packages (no monorepo tool — `run.py` spawns subprocesses, Docker Compose for containerized workflow).

## Prerequisites

- **Docker**: `docker compose up --build` (recommended)
- **Local dev**: PostgreSQL 14+ running locally, `createdb ai_design_sandbox`

## Quick Start

### Docker (recommended)

```bash
docker compose up --build
```

### Local Dev

```bash
# Backend
cd backend && pip install -r requirements.txt && uvicorn main:app --reload

# Frontend
cd frontend && npm install && npm run dev

# Both
python run.py --all
```

API docs: `http://localhost:8000/docs`

## Key Files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI entry point |
| `backend/app/config.py` | Pydantic Settings (env-driven), requires TARGET_URL/JWT_TOKEN/MODEL for AI |
| `backend/app/models/schemas.py` | All Pydantic request/response models |
| `backend/app/routers/projects.py` | CRUD: `/api/projects` |
| `backend/app/routers/sandbox.py` | File ops: `/api/sandbox` |
| `backend/app/routers/ai.py` | `POST /api/ai/generate` — AI code generation |
| `backend/app/routers/chat.py` | `GET/POST /api/projects/{id}/chat` — Chat message persistence |
| `backend/app/services/project_service.py` | PostgreSQL-backed project + file + chat message management (asyncpg) |
| `backend/app/services/ai_service.py` | Abstract BaseAIProvider + HttpAIProvider (OpenAI-compatible) |
| `backend/app/db/database.py` | asyncpg pool manager + migration runner |
| `backend/app/db/migrations/` | Append-only SQL migration files |
| `frontend/src/app/page.tsx` | Main page — orchestrates sidebar, main content, chat state, API calls |
| `frontend/src/app/components/Sidebar.tsx` | Collapsible sidebar — project list OR chat panel (toggles based on mode) |
| `frontend/src/app/components/MainContent.tsx` | Centered chat landing page OR Editor + Canvas split |
| `frontend/src/app/components/ChatPanel.tsx` | Chat message list with markdown rendering + integrated prompt input |
| `frontend/src/app/components/EditorPane.tsx` | Monaco editor with model-based tab switching (preserves undo history) |
| `frontend/src/app/components/FileExplorer.tsx` | VS Code-style file tree with directory structure, icons, rename/delete/new file |
| `frontend/src/app/components/LiveCanvas.tsx` | Sandboxed iframe preview with per-file CSS/JS inlining |
| `frontend/src/app/lib/api.ts` | Typed API client |
| `frontend/src/app/lib/types.ts` | Shared TypeScript interfaces |
| `frontend/src/app/lib/fileIcons.tsx` | File type icon utility (SVG icons by extension) |
| `frontend/src/app/hooks/useProjects.ts` | Custom hook: project CRUD state management |
| `frontend/src/app/hooks/useChat.ts` | Custom hook: chat messages, AI generation, WebSocket streaming |
| `frontend/src/app/hooks/useFileSave.ts` | Custom hook: file state, debounced auto-save, dirty tracking |
| `docker-compose.yml` | 3-service Compose definition (backend, frontend, db) |
| `backend/Dockerfile` | Python 3.12-slim image for FastAPI |
| `frontend/Dockerfile` | Node 22-alpine image for Next.js |
| `run.py` | One-command launcher |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/projects/` | List all projects |
| POST | `/api/projects/` | Create project (with boilerplate files) |
| GET | `/api/projects/{id}` | Get project details + files |
| PATCH | `/api/projects/{id}` | Update name/description |
| DELETE | `/api/projects/{id}` | Delete project |
| GET | `/api/sandbox/{id}` | Get full sandbox state |
| PUT | `/api/sandbox/{id}/files` | Create/update a file |
| DELETE | `/api/sandbox/{id}/files?path=...` | Delete a file |
| POST | `/api/ai/generate` | Generate code from prompt (returns message + files) |
| GET | `/api/projects/{id}/chat` | Get chat messages for a project |
| POST | `/api/projects/{id}/chat` | Save a chat message |

## Data Model

**Project**: `id` (UUID), `name`, `description`, `status` (idle/generating/error), `files` (list of {path, content, file_type}), `created_at`, `updated_at`.

**GenerateResponse**: `project_id`, `project_name`, `message` (AI conversational response), `files` (generated files).

**ChatMessage**: `id`, `project_id`, `role` (user/assistant), `content`, `files` (JSONB), `created_at`.

New projects get boilerplate: `index.html`, `style.css`, `script.js`.

## Coding Conventions

- **Backend**: FastAPI + Pydantic v2 (use `model_dump()`, `model_validate()`). Singleton service pattern injected into `app.state`. UUIDs as strings.
- **Database**: Raw SQL via `asyncpg` (no ORM). Append-only migrations in `app/db/migrations/`. Separate `files` table (not JSONB) for atomic single-file operations. JSONB columns require `json.dumps()` for inserts.
- **AI**: Abstract BaseAIProvider + HttpAIProvider. OpenAI-compatible chat format (messages array). JWT bearer auth. Returns `(message, list[ProjectFile])` tuple. Parses `{"message": "...", "files": [...]}` from `choices[0].message.content`. System prompt tells model to preserve indentation/line breaks and use standard filenames.
- **Frontend**: Next.js 16 App Router, React 19, Tailwind CSS v4 syntax (`@import "tailwindcss"`, `@theme inline`), TypeScript, Monaco Editor, react-markdown + remark-gfm for AI message rendering.
- **File type inference**: From extension — `.html`, `.css`, `.js`, `.json`, `.py`, or `other`.
- **No tests yet** — add them when implementing new features.
- **Root `.gitignore`** exists — excludes `.env`, `__pycache__/`, `node_modules/`, `.next/`, etc.
- **Zero lint/type errors** — `npx tsc --noEmit` and `npx eslint src/` both pass clean. Maintain this standard before committing.

## Environment Variables (.env at project root)

The `.env` file lives at the **project root** (`./.env`) — not in `backend/`. Docker Compose auto-reads it from the root. The backend's Pydantic Settings resolves the path absolutely from `config.py`.

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | "AI Design Sandbox" | App title |
| `DEBUG` | `true` | Debug mode |
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8000` | Bind port |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/ai_design_sandbox` | PostgreSQL connection string (hardcoded in docker-compose.yml) |
| `DATABASE_POOL_MIN_SIZE` | `2` | Minimum pool connections |
| `DATABASE_POOL_MAX_SIZE` | `10` | Maximum pool connections |
| `TARGET_URL` | (required for AI) | AI provider API endpoint (OpenAI-compatible) |
| `JWT_TOKEN` | (required for AI) | AI provider JWT bearer token |
| `MODEL` | (required for AI) | AI model identifier |
| `FIGMA_CLIENT_ID` | (empty) | Figma OAuth |
| `FIGMA_CLIENT_SECRET` | (empty) | Figma OAuth |
| `FIGMA_REDIRECT_URI` | `http://localhost:8000/api/figma/callback` | Figma OAuth |

## Bugs Fixed

1. **`backend/app/routers/ai.py`** — Replaced `type("FakeCreate", ...)` with proper `ProjectCreate(name=..., description=...)`.
2. **`backend/app/services/ai_service.py`** — Made JSON extraction robust: finds first `{`/last `}` instead of relying on regex stripping.
3. **`backend/app/config.py`** — Changed `env_file` path from relative `".env"` to absolute path resolving to project root.
4. **`.env` moved** from `backend/` to project root so Docker Compose can read it.
5. **Root `.gitignore`** created.
6. **Git history rewritten** — removed `backend/.env` from all commits. Pushed to new repo `ai-app-builder`.
7. **Nested button bug** — `Sidebar.tsx` had `<button>` inside `<button>`, causing hydration errors. Changed to `<div role="button">`.
8. **Chat persistence JSONB encoding** — `project_service.py` was passing a Python list to asyncpg's JSONB column instead of a JSON string. Fixed with `json.dumps()`.
9. **AI output formatting** — System prompt said "NO markdown formatting" which some models interpreted as "remove all newlines/indentation." Updated to explicitly tell the model to preserve formatting and use standard filenames.
10. **Chat messages disappearing on landing page prompt** — `useEffect` for loading chat messages depended on `[activeProjectId, generating]`. When `generating` flipped to `false` after WebSocket stream completed, the effect re-fetched messages from the backend, overwriting in-memory streaming state. Fixed by removing `generating` from the dependency array.
11. **CSS not applying in live preview** — `LiveCanvas.tsx` iframe `key` used `htmlContent.slice(0, 100)`, so CSS changes (inlined later in the HTML) didn't trigger a remount. Fixed by using the full `htmlContent` as the key.
12. **Monaco editor remount on tab switch** — `EditorPane.tsx` used `key={activeFile?.path}` which destroyed and recreated the editor on every tab switch, losing undo history, cursor position, and scroll position. Fixed by using Monaco's model API (`editor.setModel()`) with cached URI-based models.
13. **Debounce cross-project data corruption** — `page.tsx` debounced save timers captured `activeProjectId` at creation time. If the user switched projects while a save was pending, content could be written to the wrong project. Fixed by adding a `projectIdRef` guard and clearing pending timers on project switch.
14. **Delete file active switching** — `handleDeleteFile` had a TODO comment about switching the active file when the deleted file was active. Fixed by adding a `useEffect` in `MainContent` that resets `activeFilePath` when the active file is deleted.
15. **LiveCanvas CSS/JS inlining** — Only the first `.css`/`.js` file by array order was inlined. The regex replacement ignored which file was linked. Fixed by building a filename→content map and matching each `<link>`/`<script>` tag to its corresponding file.
16. **iframeError never resets** — Once set to true, the error message persisted forever. Fixed by adding a `useEffect` that resets `iframeError` when `htmlContent` changes.
17. **Duplicate file feedback** — Adding a file with a path that already existed silently failed. Fixed by showing an inline error message that auto-dismisses after 2.5 seconds.
18. **Dead `savingFiles` state** — Tracked in page.tsx but never displayed or passed to any component. Removed.
19. **Redundant `rows={1}`** — The landing page textarea had `rows={1}` which was redundant with the auto-resize `useEffect`. Removed.

## Features Added

1. **AI conversational responses** — `GenerateResponse` now includes a `message` field with the AI's explanation.
2. **Chat panel in sidebar** — Sidebar toggles between project list and chat panel with markdown-rendered AI messages.
3. **Centered chat landing page** — ChatGPT-style landing page when no project is selected. Sending a prompt auto-creates a project.
4. **Chat persistence** — `chat_messages` table + API endpoints. Messages survive page refresh.
5. **No auto-select** — App starts with centered chat landing, no project auto-selected.
6. **Auto-create project on prompt** — Sending a prompt from the landing page creates a project automatically.
7. **File saving to backend** — Edits in Monaco are auto-saved to the backend via debounced `PUT /api/sandbox/{id}/files` (800ms debounce). File changes persist across page refresh.
8. **Add/delete files from UI** — "+" button in file tab bar with inline input for naming new files. "×" button on each tab with confirmation bar before deleting. Auto-appends `.html` if no extension given. Duplicate paths rejected. Empty state with "Add File" button when no files exist.
9. **View mode toggle** — Three-way toggle (Preview / Code / Split) in the project name bar. Defaults to Preview mode. Preview shows full-screen LiveCanvas, Code shows full-screen EditorPane, Split shows 50/50 layout.
10. **WebSocket streaming for AI generation** — AI generation now streams results over WebSocket (`/api/ai/ws/generate`). Message text appears character-by-character in chat (extracted from streaming JSON via regex, no raw JSON shown). File tabs appear and content streams into the Monaco editor in real-time during generation. Falls back to REST endpoint if WebSocket fails. Uses `StreamingHttpAIProvider` with OpenAI-compatible SSE streaming. Timeout increased to 300s.
11. **VS Code-style file explorer** — New `FileExplorer.tsx` component with tree view organized by directory structure, file-type icons (HTML, CSS, JS, JSON, Python, TypeScript, Markdown, SVG), collapsible directories, inline rename/delete/new file actions, active file highlighting, and unsaved changes indicator (blue dot). Replaces the flat tab bar as the primary file navigation.
12. **Monaco model-based tab switching** — Editor now uses Monaco's model API to preserve undo history, cursor position, and scroll position when switching between files. Models are cached by URI so switching back restores full editor state.
13. **Custom hooks refactor** — Extracted `useProjects`, `useChat`, and `useFileSave` hooks from `page.tsx`, reducing it from 430+ lines of mixed state logic to ~100 lines of orchestration code.
14. **File type icons** — New `fileIcons.tsx` utility with inline SVG icons for common file extensions, used consistently in the file explorer.
15. **Unsaved changes tracking** — Files with pending debounced saves show a blue dot indicator in the file explorer. The `dirtyFiles` set is cleared when switching projects.

## Bugs Fixed (44 total)

All bugs from the [[frontend-bug-audit]] and [[backend-ai-bug-audit]] have been fixed. See [[critical-bugs-fixed-june-2026]] in memory for full details.

### Critical bugs (18):

**Backend & AI Pipeline:**
1. **AI must echo back ALL files on every request** — Changed system prompt: AI now only includes files it wants to CREATE or MODIFY. Backend merges AI output with existing files (AI files override by path, everything else preserved).
2. **Chat messages never persisted by AI endpoints** — Both REST (`POST /api/ai/generate`) and WebSocket (`/api/ai/ws/generate`) now save user prompt and AI response as chat messages.
3. **No transaction across AI read-then-write** — Added `upsert_files_transactional()` method that upserts all files atomically in a single DB transaction.
4. **WebSocket persistence has no rollback** — WebSocket handler now uses `upsert_files_transactional()` for atomic file persistence.
5. **Connection pool exhaustion — no retry/backoff** — Added `acquire_with_retry()` with exponential backoff (3 retries, 0.5s base delay). All `pool.acquire()` calls in `project_service.py` now use it.
6. **Streaming content diff can corrupt file data** — Added `startswith` check before slicing. If content shifts unexpectedly, sends full corrected content as delta.
7. **Final re-parse disagrees with streamed content** — After final parse, compares with streamed content and sends corrective `file_chunk` delta if they differ.
8. **Parse failure yields empty files** — On parse failure, falls back to existing files instead of returning empty array.
9. **Unbounded chat history growth** — Limited to last 10 messages, each truncated to 2000 chars.
10. **Frontend saveMessage fire-and-forget** — `saveMessage` call for user messages is now awaited.

**Frontend:**
11. **REST fallback state leak** — Added 60s WebSocket timeout. REST success path now sets `writingStatus` to done. Added `setGenerating(false)` guard in else branch.
12. **File state overwrite on concurrent edits** — `handleFilesChange` now merges updates into existing state instead of replacing the entire array.
13. **Editor mounts with no model** — Added refs (`filesRef`, `activeFilePathRef`) to `handleEditorDidMount` so it reads latest props instead of stale closure.
14. **Directory collapse resets on every keystroke** — Moved expanded state to parent `FileExplorer` as `expandedDirs: Set<string>`, persisted across re-renders.
15. **Full iframe remount on every keystroke** — Removed `key={htmlContent}` from iframe. `srcDoc` updates content without remounting.
16. **CDN scripts silently removed** — JS inlining regex now preserves original `<script src="...">` tag when no matching project file exists.
17. **iframe onError is dead code** — Replaced with `useEffect` that checks iframe content after 2s timeout to detect rendering failures.
18. **No aria-live on chat messages** — Added `role="log"` and `aria-live="polite"` to chat messages container.

### Medium/Low priority bugs (26):

**Backend:**
19. **ProjectFile.path and SandboxFileUpdate.path max_length** — Added `max_length=512` validation to prevent DB crash on long paths.
20. **save_chat_message doesn't touch updated_at** — Now updates `projects.updated_at` so active conversations surface to top of list.
21. **Timezone data loss** — Removed all `.replace(tzinfo=None)` calls. Schemas now use `datetime.now(timezone.utc)`.
22. **Role unvalidated in ChatMessageSchema** — Added `pattern="^(user|assistant)$"` regex validation.
23. **Empty/path-traversal file paths** — Added `_validate_sandbox_path()` to sandbox endpoints blocking empty paths, `../`, `~`, and absolute paths.
24. **Chat content no max_length** — Added `max_length=100_000` to prevent DoS via unbounded content.
25. **No connection health check** — `acquire_with_retry()` now runs `SELECT 1` health check to detect stale connections.
26. **message_re regex matches inside file content** — Changed regex to require `"files"` after `"message"` to avoid matching inside file content.
27. **Unknown file_type crashes generation** — Added try/except around `FileType()` constructor, defaults to `other`.
28. **Timeout mismatch** — Added separate `_connect_timeout=30s` to httpx client to avoid proxy timeouts.
29. **print() instead of logging** — Replaced `print()` with `logger.info()` in database.py.
30. **JSONB type check code smell** — Extracted `_parse_jsonb_files()` helper to clean up defensive type checks.

**Frontend:**
31. **Swallowed API errors on project fetch** — Added `setError()` call with user-visible message on fetch failure.
32. **handlePrompt recreated on every keystroke** — Added `filesRef` to avoid stale closure on `files` dependency.
33. **Module-level chatIdCounter never reset** — Replaced module-level counter with `useRef` per hook instance.
34. **Ineffective loadingMessagesRef guard** — Replaced with request-ID-based stale response detection.
35. **setDirtyFiles called inside setFiles updater** — Moved side effects outside the state updater function.
36. **Focusable element hidden behind delete overlay** — Added `tabIndex={-1}`, `aria-hidden`, and `pointer-events-none` to underlying element.
37. **MainContent missing effect deps** — Added `filesRef` to `handleFileContentChange` to avoid full array recreation on keystroke.
38. **Send buttons missing aria-label** — Added `aria-label="Send prompt"` and `aria-label="Send message"`.
39. **Duplicate error not announced to screen readers** — Added `role="alert"` and `aria-live="assertive"` to error display.
40. **No filename validation on new file/rename** — Added `validateFilename()` with error messages for invalid chars, slashes, length, etc.
41. **LiveCanvas missing allow-same-origin** — Added `allow-same-origin` to iframe sandbox for fetch/localStorage support.
42. **Duplicate key in Sidebar** — Removed duplicate `key={project.id}` from inner div.
43. **Emoji accessibility** — Added `role="img"` and `aria-label` to wrench emoji in writing indicator.
44. **Unused imports** — Removed unused `useId` and `useMemo` imports.

## Cleanup Session (June 2026)

After the 44-bug fix session, a full project audit was performed. **20 items** fixed:
- **Backend**: Removed dead code `_get_service()` from `projects.py`
- **Frontend ESLint errors (9)**: Ref assignments moved to `useEffect`, setState wrapped in `setTimeout`, `monacoRef` typed properly, unused eslint-disable removed
- **Frontend ESLint warnings (9)**: Unused props/variables/imports removed, dead `loadingMessagesRef` removed
- **Git**: All 22 files committed as `6c7c40e` with descriptive message
- **Verification**: TypeScript zero errors, ESLint zero errors/warnings, Python all files compile

## Post-Cleanup Bug Fixes (June 2026)

### Bug 45: `async with await acquire_with_retry(pool)` TypeError
**File**: `backend/app/services/project_service.py`
**Root cause**: `acquire_with_retry()` returns a raw `asyncpg.Connection`, but all 10 call sites used `async with await acquire_with_retry(pool) as conn:`. `asyncpg.Connection` does not support `async with` — only `Pool.acquire()` returns a context-manager proxy.
**Fix**: Changed all 10 call sites to `conn = await acquire_with_retry(pool)` with explicit `pool.release(conn)` in a `finally` block.

### Bug 46: `connect_timeout` not supported by asyncpg 0.30.0
**File**: `backend/app/db/database.py`
**Root cause**: `connect_timeout` is not a valid parameter for `asyncpg.create_pool()` in version 0.30.0.
**Fix**: Removed `connect_timeout=10` from `create_pool()` call.

### Bug 47: Server hangs when pool is exhausted or DB unreachable
**File**: `backend/app/db/database.py`
**Root cause**: `pool.acquire()` had no timeout — blocks forever when all connections are busy or DB is unreachable.
**Fix**: Added `timeout=10` to `create_pool()`, `pool.acquire()` in `acquire_with_retry()`, and `pool.acquire()` in `run_migrations()`. Server now fails fast (~15s) instead of hanging indefinitely.

## Phase 3 (Not Started)

The following features are planned for Phase 3:
- Figma OAuth integration
- ZIP export endpoint
- Design Upload, Figma Import, Download Button

## Dependencies

**Backend**: fastapi, uvicorn, pydantic, pydantic-settings, python-multipart, httpx (AI provider calls), python-dotenv, asyncpg

**Frontend**: next, react, react-dom, tailwindcss, @tailwindcss/postcss, typescript, eslint, eslint-config-next, @monaco-editor/react, react-markdown, remark-gfm
