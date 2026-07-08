"""Integration tests for API endpoints.

Tests the full request-response cycle through the FastAPI app with
a mock AI provider and test database.
"""

from __future__ import annotations

import pytest
import pytest_asyncio


# ── Health check ──────────────────────────────────────────────


class TestHealth:
    async def test_health_endpoint(self, async_client):
        response = await async_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app"] == "AI Design Sandbox"


# ── Project CRUD ──────────────────────────────────────────────


class TestProjects:
    async def test_list_projects_empty(self, async_client):
        response = await async_client.get("/api/projects/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_project(self, async_client):
        response = await async_client.post(
            "/api/projects/",
            json={"name": "New Project", "description": "Test"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Project"
        assert data["description"] == "Test"
        assert "id" in data
        assert data["status"] == "idle"

    async def test_create_project_defaults(self, async_client):
        response = await async_client.post(
            "/api/projects/",
            json={"name": "Minimal"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal"
        assert data["description"] == ""

    async def test_create_project_has_boilerplate_files(self, async_client):
        response = await async_client.post(
            "/api/projects/",
            json={"name": "With Files"},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["files"]) >= 3
        paths = [f["path"] for f in data["files"]]
        assert "index.html" in paths
        assert "style.css" in paths
        assert "script.js" in paths

    async def test_get_project(self, async_client, sample_project):
        project_id = sample_project.id
        response = await async_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(project_id)
        assert data["name"] == "Test Project"

    async def test_get_project_not_found(self, async_client):
        response = await async_client.get("/api/projects/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    async def test_update_project(self, async_client, sample_project):
        project_id = sample_project.id
        response = await async_client.patch(
            f"/api/projects/{project_id}",
            json={"name": "Updated Name", "description": "Updated desc"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated desc"

    async def test_update_project_partial(self, async_client, sample_project):
        project_id = sample_project.id
        response = await async_client.patch(
            f"/api/projects/{project_id}",
            json={"name": "Only Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Only Name"

    async def test_delete_project(self, async_client, sample_project):
        project_id = sample_project.id
        response = await async_client.delete(f"/api/projects/{project_id}")
        assert response.status_code == 204

        # Verify it's gone
        response = await async_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 404

    async def test_list_projects_after_create(self, async_client, sample_project):
        response = await async_client.get("/api/projects/")
        assert response.status_code == 200
        projects = response.json()
        assert len(projects) >= 1
        ids = [p["id"] for p in projects]
        assert str(sample_project.id) in ids


# ── Sandbox file operations ───────────────────────────────────


class TestSandbox:
    async def test_get_sandbox(self, async_client, project_with_files):
        project_id = project_with_files.id
        response = await async_client.get(f"/api/sandbox/{project_id}")
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) >= 3

    async def test_create_file(self, async_client, sample_project):
        project_id = sample_project.id
        response = await async_client.put(
            f"/api/sandbox/{project_id}/files",
            json={"path": "test.js", "content": "console.log('test');", "file_type": "javascript"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "test.js"

    async def test_update_file(self, async_client, project_with_files):
        project_id = project_with_files.id
        response = await async_client.put(
            f"/api/sandbox/{project_id}/files",
            json={"path": "index.html", "content": "<html>Updated</html>", "file_type": "html"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "<html>Updated</html>"

    async def test_delete_file(self, async_client, project_with_files):
        project_id = project_with_files.id
        response = await async_client.delete(
            f"/api/sandbox/{project_id}/files?path=script.js",
        )
        assert response.status_code == 204

        # Verify it's gone
        response = await async_client.get(f"/api/sandbox/{project_id}")
        data = response.json()
        paths = [f["path"] for f in data["files"]]
        assert "script.js" not in paths

    async def test_delete_nonexistent_file(self, async_client, sample_project):
        project_id = sample_project.id
        response = await async_client.delete(
            f"/api/sandbox/{project_id}/files?path=nonexistent.js",
        )
        assert response.status_code == 404

    async def test_create_file_without_extension(self, async_client, sample_project):
        project_id = sample_project.id
        response = await async_client.put(
            f"/api/sandbox/{project_id}/files",
            json={"path": "noext", "content": "data", "file_type": "other"},
        )
        assert response.status_code == 200

    async def test_create_duplicate_file(self, async_client, project_with_files):
        project_id = project_with_files.id
        response = await async_client.put(
            f"/api/sandbox/{project_id}/files",
            json={"path": "index.html", "content": "overwrite", "file_type": "html"},
        )
        # Should succeed (upsert behavior)
        assert response.status_code == 200


# ── Chat ──────────────────────────────────────────────────────


class TestChat:
    async def test_get_chat_empty(self, async_client, sample_project):
        project_id = sample_project.id
        response = await async_client.get(f"/api/projects/{project_id}/chat")
        assert response.status_code == 200
        assert response.json() == []

    async def test_save_chat_message(self, async_client, sample_project):
        project_id = sample_project.id
        response = await async_client.post(
            f"/api/projects/{project_id}/chat",
            json={"role": "user", "content": "Hello"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "user"
        assert data["content"] == "Hello"

    async def test_get_chat_messages(self, async_client, sample_project):
        project_id = sample_project.id
        await async_client.post(
            f"/api/projects/{project_id}/chat",
            json={"role": "user", "content": "First"},
        )
        await async_client.post(
            f"/api/projects/{project_id}/chat",
            json={"role": "assistant", "content": "Response"},
        )
        response = await async_client.get(f"/api/projects/{project_id}/chat")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 2
        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Response"

    async def test_save_chat_message_invalid_role(self, async_client, sample_project):
        project_id = sample_project.id
        response = await async_client.post(
            f"/api/projects/{project_id}/chat",
            json={"role": "admin", "content": "Hack"},
        )
        assert response.status_code == 422  # validation error


# ── AI generation ─────────────────────────────────────────────


class TestAIGeneration:
    async def test_generate_endpoint(self, async_client):
        response = await async_client.post(
            "/api/ai/generate",
            json={"prompt": "Build a landing page"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "project_id" in data
        assert "message" in data
        assert "files" in data
        assert len(data["files"]) >= 1

    async def test_generate_creates_project(self, async_client):
        response = await async_client.post(
            "/api/ai/generate",
            json={"prompt": "Build a todo app"},
        )
        assert response.status_code == 201
        data = response.json()
        # Verify the project exists
        project_response = await async_client.get(f"/api/projects/{data['project_id']}")
        assert project_response.status_code == 200

    async def test_generate_saves_chat_messages(self, async_client):
        response = await async_client.post(
            "/api/ai/generate",
            json={"prompt": "Build a calculator"},
        )
        assert response.status_code == 201
        data = response.json()
        # Check chat messages were saved
        chat_response = await async_client.get(f"/api/projects/{data['project_id']}/chat")
        messages = chat_response.json()
        assert len(messages) >= 2  # user prompt + AI response


# ── Figma import ──────────────────────────────────────────────


class TestFigmaImport:
    async def test_import_url_no_token(self, async_client):
        # Empty token fails Pydantic validation (min_length=1)
        response = await async_client.post(
            "/api/figma/import-url",
            json={"figma_url": "ABC123", "access_token": ""},
        )
        assert response.status_code == 422

    async def test_import_url_missing_token(self, async_client):
        # Missing token field
        response = await async_client.post(
            "/api/figma/import-url",
            json={"figma_url": "ABC123"},
        )
        assert response.status_code == 422

    async def test_import_url_invalid_url(self, async_client):
        # Invalid URL format that doesn't match bare key pattern
        response = await async_client.post(
            "/api/figma/import-url",
            json={"figma_url": "https://example.com/page", "access_token": "test-token"},
        )
        assert response.status_code == 400

    async def test_cache_endpoint(self, async_client):
        response = await async_client.get("/api/figma/cache")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "keys" in data

    async def test_clear_cache_endpoint(self, async_client):
        response = await async_client.delete("/api/figma/cache")
        assert response.status_code == 200
        data = response.json()
        assert "cleared" in data
