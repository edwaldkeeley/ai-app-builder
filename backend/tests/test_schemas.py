"""Tests for Pydantic schemas: validation, serialization, edge cases."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    ChatMessageSchema,
    FigmaUrlImportRequest,
    FileType,
    GenerateResponse,
    ProjectCreate,
    ProjectFile,
    ProjectUpdate,
    PromptRequest,
    SandboxFileUpdate,
)


# ── FileType enum ─────────────────────────────────────────────


class TestFileType:
    def test_valid_types(self):
        assert FileType("html") == FileType.html
        assert FileType("css") == FileType.css
        assert FileType("javascript") == FileType.js
        assert FileType("json") == FileType.json
        assert FileType("python") == FileType.python
        assert FileType("other") == FileType.other

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            FileType("text")


# ── ProjectFile ───────────────────────────────────────────────


class TestProjectFile:
    def test_minimal(self):
        pf = ProjectFile(path="test.html", content="<html></html>", file_type=FileType.html)
        assert pf.path == "test.html"
        assert pf.content == "<html></html>"
        assert pf.file_type == FileType.html

    def test_serializes_to_dict(self):
        pf = ProjectFile(path="test.js", content="console.log(1);", file_type=FileType.js)
        d = pf.model_dump()
        assert d["path"] == "test.js"
        assert d["file_type"] == "javascript"

    def test_serializes_to_json(self):
        pf = ProjectFile(path="test.html", content="<html></html>", file_type=FileType.html)
        j = pf.model_dump_json()
        assert '"path":"test.html"' in j
        assert '"file_type":"html"' in j


# ── ProjectCreate ─────────────────────────────────────────────


class TestProjectCreate:
    def test_minimal(self):
        pc = ProjectCreate(name="Test")
        assert pc.name == "Test"
        assert pc.description == ""

    def test_with_description(self):
        pc = ProjectCreate(name="Test", description="A test")
        assert pc.description == "A test"

    def test_name_required(self):
        with pytest.raises(ValidationError):
            ProjectCreate()

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            ProjectCreate(name="x" * 256)


# ── ProjectUpdate ─────────────────────────────────────────────


class TestProjectUpdate:
    def test_empty_update(self):
        pu = ProjectUpdate()
        assert pu.name is None
        assert pu.description is None

    def test_partial_update(self):
        pu = ProjectUpdate(name="New Name")
        assert pu.name == "New Name"
        assert pu.description is None


# ── PromptRequest ────────────────────────────────────────────


class TestPromptRequest:
    def test_minimal(self):
        pr = PromptRequest(prompt="Build something")
        assert pr.prompt == "Build something"
        assert pr.project_id is None

    def test_with_project_id(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        pr = PromptRequest(prompt="Update", project_id=uid)
        assert pr.project_id == uid

    def test_prompt_required(self):
        with pytest.raises(ValidationError):
            PromptRequest()


# ── GenerateResponse ──────────────────────────────────────────


class TestGenerateResponse:
    def test_minimal(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        gr = GenerateResponse(
            project_id=uid,
            project_name="Test",
            message="Done",
            files=[],
        )
        assert gr.project_id == uid
        assert gr.message == "Done"
        assert gr.files == []

    def test_with_files(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        gr = GenerateResponse(
            project_id=uid,
            project_name="Test",
            message="Done",
            files=[ProjectFile(path="index.html", content="<html></html>", file_type=FileType.html)],
        )
        assert len(gr.files) == 1


# ── SandboxFileUpdate ─────────────────────────────────────────


class TestSandboxFileUpdate:
    def test_minimal(self):
        sfu = SandboxFileUpdate(path="test.html", content="<html></html>")
        assert sfu.path == "test.html"
        assert sfu.content == "<html></html>"

    def test_path_max_length(self):
        with pytest.raises(ValidationError):
            SandboxFileUpdate(path="x" * 600, content="")

    def test_path_required(self):
        with pytest.raises(ValidationError):
            SandboxFileUpdate(content="data")


# ── ChatMessageSchema ─────────────────────────────────────────


class TestChatMessageSchema:
    def test_user_message(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        msg = ChatMessageSchema(role="user", content="Hello", project_id=uid)
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.project_id == uid

    def test_assistant_message(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        msg = ChatMessageSchema(role="assistant", content="Hi there", project_id=uid)
        assert msg.role == "assistant"

    def test_invalid_role(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        with pytest.raises(ValidationError, match="user|assistant"):
            ChatMessageSchema(role="admin", content="Hack", project_id=uid)

    def test_content_max_length(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        with pytest.raises(ValidationError):
            ChatMessageSchema(role="user", content="x" * 200_000, project_id=uid)

    def test_with_files(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        msg = ChatMessageSchema(
            role="assistant",
            content="Here are the files",
            project_id=uid,
            files=[ProjectFile(path="test.html", content="<html></html>", file_type=FileType.html)],
        )
        assert len(msg.files) == 1


# ── FigmaUrlImportRequest ─────────────────────────────────────


class TestFigmaUrlImportRequest:
    def test_minimal(self):
        req = FigmaUrlImportRequest(figma_url="ABC123", access_token="token123")
        assert req.figma_url == "ABC123"
        assert req.access_token == "token123"
        assert req.force_refresh is False

    def test_force_refresh(self):
        req = FigmaUrlImportRequest(figma_url="ABC123", access_token="token123", force_refresh=True)
        assert req.force_refresh is True

    def test_figma_url_required(self):
        with pytest.raises(ValidationError):
            FigmaUrlImportRequest(access_token="token123")

    def test_access_token_required(self):
        with pytest.raises(ValidationError):
            FigmaUrlImportRequest(figma_url="ABC123")
