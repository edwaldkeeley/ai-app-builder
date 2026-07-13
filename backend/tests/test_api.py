"""Integration tests for API endpoints.

Tests the full request-response cycle through the FastAPI app with
a mock AI provider and test database.
"""

from __future__ import annotations

import pytest
import pytest_asyncio


# ── Auth ──────────────────────────────────────────────────────


class TestAuth:
    async def test_register(self, async_client):
        response = await async_client.post(
            "/api/auth/register",
            json={"email": "new@test.com", "username": "newuser", "password": "password123"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@test.com"
        assert data["username"] == "newuser"
        assert "id" in data

    async def test_register_duplicate_email(self, async_client, test_user):
        response = await async_client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "username": "another", "password": "password123"},
        )
        assert response.status_code == 409

    async def test_login(self, async_client, test_user):
        response = await async_client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "testpass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    async def test_login_wrong_password(self, async_client, test_user):
        response = await async_client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrong"},
        )
        assert response.status_code == 401

    async def test_me_authenticated(self, auth_client):
        response = await auth_client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    async def test_me_unauthenticated(self, async_client):
        response = await async_client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_logout(self, auth_client):
        response = await auth_client.post("/api/auth/logout")
        assert response.status_code == 200


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
    async def test_list_projects_empty(self, auth_client):
        response = await auth_client.get("/api/projects/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_project(self, auth_client):
        response = await auth_client.post(
            "/api/projects/",
            json={"name": "New Project", "description": "Test"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Project"
        assert data["description"] == "Test"
        assert "id" in data
        assert data["status"] == "idle"

    async def test_create_project_defaults(self, auth_client):
        response = await auth_client.post(
            "/api/projects/",
            json={"name": "Minimal"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal"
        assert data["description"] == ""

    async def test_create_project_has_boilerplate_files(self, auth_client):
        response = await auth_client.post(
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

    async def test_get_project(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(project_id)
        assert data["name"] == "Test Project"

    async def test_get_project_not_found(self, auth_client):
        response = await auth_client.get("/api/projects/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    async def test_update_project(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.patch(
            f"/api/projects/{project_id}",
            json={"name": "Updated Name", "description": "Updated desc"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated desc"

    async def test_update_project_partial(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.patch(
            f"/api/projects/{project_id}",
            json={"name": "Only Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Only Name"

    async def test_delete_project(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.delete(f"/api/projects/{project_id}")
        assert response.status_code == 204

        # Verify it's gone
        response = await auth_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 404

    async def test_list_projects_after_create(self, auth_client, sample_project):
        response = await auth_client.get("/api/projects/")
        assert response.status_code == 200
        projects = response.json()
        assert len(projects) >= 1
        ids = [p["id"] for p in projects]
        assert str(sample_project.id) in ids


# ── Sandbox file operations ───────────────────────────────────


class TestSandbox:
    async def test_get_sandbox(self, auth_client, project_with_files):
        project_id = project_with_files.id
        response = await auth_client.get(f"/api/sandbox/{project_id}")
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) >= 3

    async def test_create_file(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.put(
            f"/api/sandbox/{project_id}/files",
            json={"path": "test.js", "content": "console.log('test');", "file_type": "javascript"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "test.js"

    async def test_update_file(self, auth_client, project_with_files):
        project_id = project_with_files.id
        response = await auth_client.put(
            f"/api/sandbox/{project_id}/files",
            json={"path": "index.html", "content": "<html>Updated</html>", "file_type": "html"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "<html>Updated</html>"

    async def test_delete_file(self, auth_client, project_with_files):
        project_id = project_with_files.id
        response = await auth_client.delete(
            f"/api/sandbox/{project_id}/files?path=script.js",
        )
        assert response.status_code == 204

        # Verify it's gone
        response = await auth_client.get(f"/api/sandbox/{project_id}")
        data = response.json()
        paths = [f["path"] for f in data["files"]]
        assert "script.js" not in paths

    async def test_delete_nonexistent_file(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.delete(
            f"/api/sandbox/{project_id}/files?path=nonexistent.js",
        )
        assert response.status_code == 404

    async def test_create_file_without_extension(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.put(
            f"/api/sandbox/{project_id}/files",
            json={"path": "noext", "content": "data", "file_type": "other"},
        )
        assert response.status_code == 200

    async def test_create_duplicate_file(self, auth_client, project_with_files):
        project_id = project_with_files.id
        response = await auth_client.put(
            f"/api/sandbox/{project_id}/files",
            json={"path": "index.html", "content": "overwrite", "file_type": "html"},
        )
        # Should succeed (upsert behavior)
        assert response.status_code == 200


# ── Chat ──────────────────────────────────────────────────────


class TestChat:
    async def test_get_chat_empty(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.get(f"/api/projects/{project_id}/chat")
        assert response.status_code == 200
        assert response.json() == []

    async def test_save_chat_message(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.post(
            f"/api/projects/{project_id}/chat",
            json={"role": "user", "content": "Hello"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "user"
        assert data["content"] == "Hello"

    async def test_get_chat_messages(self, auth_client, sample_project):
        project_id = sample_project.id
        await auth_client.post(
            f"/api/projects/{project_id}/chat",
            json={"role": "user", "content": "First"},
        )
        await auth_client.post(
            f"/api/projects/{project_id}/chat",
            json={"role": "assistant", "content": "Response"},
        )
        response = await auth_client.get(f"/api/projects/{project_id}/chat")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 2
        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Response"

    async def test_save_chat_message_invalid_role(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.post(
            f"/api/projects/{project_id}/chat",
            json={"role": "admin", "content": "Hack"},
        )
        assert response.status_code == 422  # validation error


# ── AI generation ─────────────────────────────────────────────


class TestAIGeneration:
    async def test_generate_endpoint(self, auth_client):
        response = await auth_client.post(
            "/api/ai/generate",
            json={"prompt": "Build a landing page"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "project_id" in data
        assert "message" in data
        assert "files" in data
        assert len(data["files"]) >= 1

    async def test_generate_creates_project(self, auth_client):
        response = await auth_client.post(
            "/api/ai/generate",
            json={"prompt": "Build a todo app"},
        )
        assert response.status_code == 201
        data = response.json()
        # Verify the project exists
        project_response = await auth_client.get(f"/api/projects/{data['project_id']}")
        assert project_response.status_code == 200

    async def test_generate_saves_chat_messages(self, auth_client):
        response = await auth_client.post(
            "/api/ai/generate",
            json={"prompt": "Build a calculator"},
        )
        assert response.status_code == 201
        data = response.json()
        # Check chat messages were saved
        chat_response = await auth_client.get(f"/api/projects/{data['project_id']}/chat")
        messages = chat_response.json()
        assert len(messages) >= 2  # user prompt + AI response


# ── Figma import ──────────────────────────────────────────────


class TestFigmaImport:
    async def test_import_url_no_token(self, auth_client):
        # Empty token fails Pydantic validation (min_length=1)
        response = await auth_client.post(
            "/api/figma/import-url",
            json={"figma_url": "ABC123", "access_token": ""},
        )
        assert response.status_code == 422

    async def test_import_url_missing_token(self, auth_client):
        # Missing token field
        response = await auth_client.post(
            "/api/figma/import-url",
            json={"figma_url": "ABC123"},
        )
        assert response.status_code == 422

    async def test_import_url_invalid_url(self, auth_client):
        # Invalid URL format that doesn't match bare key pattern
        response = await auth_client.post(
            "/api/figma/import-url",
            json={"figma_url": "https://example.com/page", "access_token": "test-token"},
        )
        assert response.status_code == 400

    async def test_cache_endpoint(self, auth_client):
        response = await auth_client.get("/api/figma/cache")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "keys" in data

    async def test_clear_cache_endpoint(self, auth_client):
        response = await auth_client.delete("/api/figma/cache")
        assert response.status_code == 200
        data = response.json()
        assert "cleared" in data


# ── ZIP Export ────────────────────────────────────────────────


class TestExport:
    async def test_export_zip_success(self, auth_client, project_with_files):
        project_id = project_with_files.id
        response = await auth_client.get(f"/api/projects/{project_id}/export")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        cd = response.headers["content-disposition"]
        assert cd.startswith('attachment; filename="')
        assert cd.endswith('.zip"')

        import io
        import zipfile

        zf = zipfile.ZipFile(io.BytesIO(response.content))
        names = zf.namelist()
        assert "index.html" in names
        assert "style.css" in names
        assert "script.js" in names
        assert b"Hello" in zf.read("index.html")
        assert b"color: blue" in zf.read("style.css")

    async def test_export_zip_not_found(self, auth_client):
        response = await auth_client.get(
            "/api/projects/00000000-0000-0000-0000-000000000000/export",
        )
        assert response.status_code == 404

    async def test_export_zip_empty_project(self, auth_client, sample_project):
        project_id = sample_project.id
        response = await auth_client.get(f"/api/projects/{project_id}/export")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

        import io
        import zipfile

        zf = zipfile.ZipFile(io.BytesIO(response.content))
        # Boilerplate files are created with the project, so it's not truly empty
        assert len(zf.namelist()) >= 3

    async def test_export_zip_with_binary_file(
        self, auth_client, project_service, sample_project,
    ):
        """Base64-encoded image files should be decoded to raw bytes in the ZIP."""
        import base64

        from app.models.schemas import FileType, ProjectFile

        project_id = sample_project.id
        png_b64 = base64.b64encode(b"fake-png-bytes").decode("ascii")
        await project_service.upsert_files_transactional(project_id, [
            ProjectFile(path="image.png", content=png_b64, file_type=FileType.other),
        ])

        response = await auth_client.get(f"/api/projects/{project_id}/export")
        assert response.status_code == 200

        import io
        import zipfile

        zf = zipfile.ZipFile(io.BytesIO(response.content))
        assert "image.png" in zf.namelist()
        assert zf.read("image.png") == b"fake-png-bytes"

    async def test_export_zip_filename_sanitized(self, auth_client, project_service):
        """Special characters in project names should produce a safe filename."""
        from app.models.schemas import ProjectCreate

        project = await project_service.create(
            ProjectCreate(name='Test "Project" / Foo:Bar?', description=""),
        )
        response = await auth_client.get(f"/api/projects/{project.id}/export")
        assert response.status_code == 200
        cd = response.headers["content-disposition"]
        # Extract the filename from Content-Disposition
        filename = cd.split('filename="')[1].rsplit('"')[0]
        # Should not contain raw quotes, slashes, or question marks
        assert '"' not in filename
        assert "/" not in filename
        assert "?" not in filename
        assert filename.endswith(".zip")


# ── Design Upload ─────────────────────────────────────────────


class TestDesignUpload:
    async def test_upload_design_success(self, auth_client, sample_project):
        """Upload a PNG image and verify code is generated."""
        import io

        # Minimal valid 1x1 pixel PNG
        png_bytes = (
            b'\x89PNG\r\n\x1a\n'
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
            b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        project_id = sample_project.id
        response = await auth_client.post(
            f"/api/projects/{project_id}/upload-design",
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["project_id"] == str(project_id)
        assert "message" in data
        assert "files" in data
        assert len(data["files"]) >= 1

    async def test_upload_design_with_prompt(self, auth_client, sample_project):
        """Upload with an additional text prompt."""
        import io

        png_bytes = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        project_id = sample_project.id
        response = await auth_client.post(
            f"/api/projects/{project_id}/upload-design",
            data={"prompt": "Make it dark mode"},
            files={"file": ("design.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert response.status_code == 201

    async def test_upload_design_invalid_file_type(self, auth_client, sample_project):
        """Upload a non-image file should be rejected."""
        project_id = sample_project.id
        response = await auth_client.post(
            f"/api/projects/{project_id}/upload-design",
            files={"file": ("test.txt", b"not an image", "text/plain")},
        )
        assert response.status_code == 400

    async def test_upload_design_project_not_found(self, auth_client):
        """Upload to a non-existent project should 404."""
        response = await auth_client.post(
            "/api/projects/00000000-0000-0000-0000-000000000000/upload-design",
            files={"file": ("test.png", b"fake", "image/png")},
        )
        assert response.status_code == 404

    async def test_upload_design_unauthorized(self, async_client, sample_project):
        """Upload without auth should 401."""
        project_id = sample_project.id
        response = await async_client.post(
            f"/api/projects/{project_id}/upload-design",
            files={"file": ("test.png", b"fake", "image/png")},
        )
        assert response.status_code == 401

    async def test_upload_design_saves_chat_messages(self, auth_client, sample_project):
        """Verify chat messages are saved after upload."""
        import io

        png_bytes = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        project_id = sample_project.id
        await auth_client.post(
            f"/api/projects/{project_id}/upload-design",
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
        )
        chat_response = await auth_client.get(f"/api/projects/{project_id}/chat")
        messages = chat_response.json()
        assert len(messages) >= 2  # user prompt + AI response
