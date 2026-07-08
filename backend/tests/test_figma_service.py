"""Tests for FigmaService: URL parsing, color conversion, node walking,
JSON filtering, canvas detection, and prompt building.

These tests use mock Figma data and do NOT call the Figma API.
"""

from __future__ import annotations

import json

import pytest

from app.services.figma_service import FigmaService


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def svc() -> FigmaService:
    return FigmaService()


@pytest.fixture
def mock_simple_design() -> dict:
    """A simple one-canvas Figma design."""
    return {
        "name": "Simple Design",
        "lastModified": "2026-07-08T12:00:00Z",
        "document": {
            "id": "0:1",
            "type": "DOCUMENT",
            "name": "Test",
            "children": [
                {
                    "id": "1:1",
                    "type": "CANVAS",
                    "name": "Desktop",
                    "children": [
                        {
                            "id": "2:1",
                            "type": "FRAME",
                            "name": "Hero",
                            "absoluteBoundingBox": {"x": 0, "y": 0, "width": 1440, "height": 800},
                            "fills": [{"type": "SOLID", "color": {"r": 0.11, "g": 0.12, "b": 0.23, "a": 1}, "opacity": 1}],
                            "strokes": [],
                            "effects": [],
                            "children": [
                                {
                                    "id": "2:2",
                                    "type": "TEXT",
                                    "name": "Title",
                                    "absoluteBoundingBox": {"x": 200, "y": 200, "width": 1040, "height": 80},
                                    "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1, "a": 1}, "opacity": 1}],
                                    "characters": "Hello World",
                                    "style": {
                                        "fontFamily": "Inter", "fontSize": 64, "fontWeight": 700,
                                        "textAlignHorizontal": "CENTER", "lineHeightPx": 80,
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }


@pytest.fixture
def mock_multi_canvas_design() -> dict:
    """A Figma design with Desktop + Mobile canvases."""
    return {
        "name": "Responsive Design",
        "document": {
            "id": "0:1",
            "type": "DOCUMENT",
            "name": "Test",
            "children": [
                {
                    "id": "1:1",
                    "type": "CANVAS",
                    "name": "Desktop HD",
                    "children": [
                        {
                            "id": "2:1",
                            "type": "FRAME",
                            "name": "Hero",
                            "absoluteBoundingBox": {"x": 0, "y": 0, "width": 1440, "height": 800},
                            "fills": [{"type": "SOLID", "color": {"r": 0, "g": 0, "b": 0, "a": 1}, "opacity": 1}],
                            "strokes": [], "effects": [],
                            "children": [],
                        }
                    ],
                },
                {
                    "id": "1:2",
                    "type": "CANVAS",
                    "name": "Mobile",
                    "children": [
                        {
                            "id": "3:1",
                            "type": "FRAME",
                            "name": "Hero Mobile",
                            "absoluteBoundingBox": {"x": 0, "y": 0, "width": 375, "height": 667},
                            "fills": [{"type": "SOLID", "color": {"r": 0, "g": 0, "b": 0, "a": 1}, "opacity": 1}],
                            "strokes": [], "effects": [],
                            "children": [],
                        }
                    ],
                },
            ],
        },
    }


@pytest.fixture
def mock_design_with_images() -> dict:
    """A Figma design with image fills (to test filtering)."""
    return {
        "name": "Image Design",
        "document": {
            "id": "0:1",
            "type": "DOCUMENT",
            "name": "Test",
            "children": [
                {
                    "id": "1:1",
                    "type": "CANVAS",
                    "name": "Page 1",
                    "children": [
                        {
                            "id": "2:1",
                            "type": "FRAME",
                            "name": "Section",
                            "absoluteBoundingBox": {"x": 0, "y": 0, "width": 1440, "height": 900},
                            "fills": [
                                {"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1, "a": 1}, "opacity": 1},
                                {"type": "IMAGE", "imageRef": "img_abc", "scaleMode": "FILL",
                                 "imageTransform": [[1, 0, 0], [0, 1, 0]], "opacity": 1},
                            ],
                            "strokes": [], "effects": [],
                            "children": [],
                        }
                    ],
                }
            ],
        },
    }


# ── URL parsing tests ─────────────────────────────────────────


class TestExtractFileKey:
    def test_standard_file_url(self, svc):
        assert svc.extract_file_key("https://www.figma.com/file/ABC123/My-Design") == "ABC123"

    def test_design_url(self, svc):
        assert svc.extract_file_key("https://www.figma.com/design/ABC123/My-Design") == "ABC123"

    def test_url_with_trailing_slash(self, svc):
        assert svc.extract_file_key("https://www.figma.com/file/ABC123/") == "ABC123"

    def test_bare_key(self, svc):
        assert svc.extract_file_key("ABC123") == "ABC123"

    def test_bare_key_with_dashes(self, svc):
        assert svc.extract_file_key("abc-def_123") == "abc-def_123"

    def test_invalid_url_raises(self, svc):
        with pytest.raises(ValueError, match="Could not extract"):
            svc.extract_file_key("https://example.com/page")

    def test_empty_string_raises(self, svc):
        with pytest.raises(ValueError, match="Could not extract"):
            svc.extract_file_key("")


# ── Color conversion tests ────────────────────────────────────


class TestColorConversion:
    def test_rgb_to_hex_white(self, svc):
        assert svc._rgb_to_hex(1, 1, 1) == "#ffffff"

    def test_rgb_to_hex_black(self, svc):
        assert svc._rgb_to_hex(0, 0, 0) == "#000000"

    def test_rgb_to_hex_red(self, svc):
        assert svc._rgb_to_hex(1, 0, 0) == "#ff0000"

    def test_rgb_to_hex_mid_gray(self, svc):
        assert svc._rgb_to_hex(0.5, 0.5, 0.5) == "#808080"

    def test_rgb_to_hex_figma_blue(self, svc):
        # 0.3 * 255 = 76.5, rounds to 76 = 4c
        assert svc._rgb_to_hex(0.4, 0.3, 1.0) == "#664cff"

    def test_get_solid_color_solid(self, svc):
        fills = [{"type": "SOLID", "color": {"r": 1, "g": 0, "b": 0, "a": 1}, "opacity": 1}]
        assert svc._get_solid_color(fills) == "#ff0000"

    def test_get_solid_color_none(self, svc):
        assert svc._get_solid_color(None) is None

    def test_get_solid_color_empty(self, svc):
        assert svc._get_solid_color([]) is None

    def test_get_solid_color_skips_gradient(self, svc):
        fills = [
            {"type": "GRADIENT", "gradientStops": []},
            {"type": "SOLID", "color": {"r": 0, "g": 1, "b": 0, "a": 1}, "opacity": 1},
        ]
        assert svc._get_solid_color(fills) == "#00ff00"

    def test_get_text_color_from_fills(self, svc):
        node = {"fills": [{"type": "SOLID", "color": {"r": 0.5, "g": 0.5, "b": 0.5, "a": 1}, "opacity": 1}]}
        assert svc._get_text_color(node) == "#808080"

    def test_get_text_color_default(self, svc):
        assert svc._get_text_color({}) == "#000000"


# ── Canvas detection tests ────────────────────────────────────


class TestCanvasDetection:
    def test_get_canvases_single(self, svc, mock_simple_design):
        canvases = svc._get_canvases(mock_simple_design["document"])
        assert len(canvases) == 1
        assert canvases[0]["name"] == "Desktop"

    def test_get_canvases_multi(self, svc, mock_multi_canvas_design):
        canvases = svc._get_canvases(mock_multi_canvas_design["document"])
        assert len(canvases) == 2

    def test_classify_desktop_by_name(self, svc):
        canvas = {"name": "Desktop HD"}
        assert svc._classify_canvas(canvas) == "desktop"

    def test_classify_desktop_by_width(self, svc):
        canvas = {"name": "Page 1", "children": [
            {"absoluteBoundingBox": {"width": 1440, "height": 900}}
        ]}
        assert svc._classify_canvas(canvas) == "desktop"

    def test_classify_mobile_by_name(self, svc):
        canvas = {"name": "Mobile"}
        assert svc._classify_canvas(canvas) == "mobile"

    def test_classify_mobile_by_width(self, svc):
        canvas = {"name": "Page 1", "children": [
            {"absoluteBoundingBox": {"width": 375, "height": 667}}
        ]}
        assert svc._classify_canvas(canvas) == "mobile"

    def test_classify_tablet(self, svc):
        canvas = {"name": "Tablet", "children": [
            {"absoluteBoundingBox": {"width": 768, "height": 1024}}
        ]}
        assert svc._classify_canvas(canvas) == "tablet"

    def test_classify_unknown(self, svc):
        canvas = {"name": "", "children": []}
        assert svc._classify_canvas(canvas) == "unknown"

    def test_get_canvas_dimensions(self, svc, mock_simple_design):
        canvas = mock_simple_design["document"]["children"][0]
        w, h = svc._get_canvas_dimensions(canvas)
        assert w == 1440
        assert h == 800


# ── Node walking tests ────────────────────────────────────────


class TestWalkNodes:
    def test_walk_simple_design(self, svc, mock_simple_design):
        canvas = mock_simple_design["document"]["children"][0]
        lines = svc._walk_nodes(canvas)
        assert len(lines) >= 2  # canvas + frame + text
        assert any("[CANVAS]" in l for l in lines)
        assert any("[FRAME]" in l for l in lines)
        assert any("[TEXT]" in l for l in lines)

    def test_walk_includes_positions(self, svc, mock_simple_design):
        canvas = mock_simple_design["document"]["children"][0]
        lines = svc._walk_nodes(canvas)
        # The FRAME should have @(0,0) 1440x800
        frame_line = next(l for l in lines if "[FRAME]" in l)
        assert "1440x800" in frame_line

    def test_walk_includes_colors(self, svc, mock_simple_design):
        canvas = mock_simple_design["document"]["children"][0]
        lines = svc._walk_nodes(canvas)
        frame_line = next(l for l in lines if "[FRAME]" in l)
        assert "bg:" in frame_line

    def test_walk_includes_text(self, svc, mock_simple_design):
        canvas = mock_simple_design["document"]["children"][0]
        lines = svc._walk_nodes(canvas)
        text_line = next(l for l in lines if "[TEXT]" in l)
        assert 'text:"Hello World"' in text_line
        assert "ff:Inter" in text_line
        assert "fs:64" in text_line
        assert "fw:700" in text_line


# ── JSON filtering tests ──────────────────────────────────────


class TestFilterFigmaData:
    def test_filter_strips_components(self, svc):
        data = {
            "name": "Test",
            "components": {"c1": {"name": "Button"}},
            "document": {"id": "0:1", "type": "DOCUMENT", "name": "Root", "children": []},
        }
        filtered = svc._filter_figma_data(data)
        assert "components" not in filtered

    def test_filter_strips_styles(self, svc):
        data = {
            "name": "Test",
            "styles": {"s1": {"name": "Heading"}},
            "document": {"id": "0:1", "type": "DOCUMENT", "name": "Root", "children": []},
        }
        filtered = svc._filter_figma_data(data)
        assert "styles" not in filtered

    def test_filter_strips_plugin_data(self, svc):
        data = {
            "name": "Test",
            "document": {
                "id": "0:1", "type": "DOCUMENT", "name": "Root",
                "pluginData": {"figmoji": {"data": "stuff"}},
                "children": [],
            },
        }
        filtered = svc._filter_figma_data(data)
        doc = filtered["document"]
        assert "pluginData" not in doc

    def test_filter_keeps_name_and_modified(self, svc):
        data = {
            "name": "Keep Me",
            "lastModified": "2026-01-01T00:00:00Z",
            "document": {"id": "0:1", "type": "DOCUMENT", "name": "Root", "children": []},
        }
        filtered = svc._filter_figma_data(data)
        assert filtered["name"] == "Keep Me"
        assert filtered["lastModified"] == "2026-01-01T00:00:00Z"

    def test_filter_strips_image_data(self, svc, mock_design_with_images):
        filtered = svc._filter_figma_data(mock_design_with_images)
        # Get the fills from the filtered data
        canvas = filtered["document"]["children"][0]
        frame = canvas["children"][0]
        fills = frame["fills"]
        # Should have 2 fills: SOLID and IMAGE
        assert len(fills) == 2
        # IMAGE fill should have type and scaleMode but NOT imageRef
        image_fill = fills[1]
        assert image_fill["type"] == "IMAGE"
        assert image_fill["scaleMode"] == "FILL"
        assert "imageRef" not in image_fill
        assert "imageTransform" not in image_fill

    def test_filter_preserves_node_structure(self, svc, mock_simple_design):
        filtered = svc._filter_figma_data(mock_simple_design)
        doc = filtered["document"]
        assert doc["type"] == "DOCUMENT"
        assert len(doc["children"]) == 1
        canvas = doc["children"][0]
        assert canvas["type"] == "CANVAS"
        assert len(canvas["children"]) == 1
        frame = canvas["children"][0]
        assert frame["type"] == "FRAME"
        assert frame["absoluteBoundingBox"]["width"] == 1440

    def test_filter_preserves_text_content(self, svc, mock_simple_design):
        filtered = svc._filter_figma_data(mock_simple_design)
        frame = filtered["document"]["children"][0]["children"][0]
        text_node = frame["children"][0]
        assert text_node["characters"] == "Hello World"
        assert text_node["style"]["fontFamily"] == "Inter"

    def test_filter_size_reduction(self, svc, mock_design_with_images):
        """Filtering should reduce the JSON size."""
        raw = json.dumps(mock_design_with_images)
        filtered_data = svc._filter_figma_data(mock_design_with_images)
        filtered = json.dumps(filtered_data)
        assert len(filtered) < len(raw)


# ── Prompt building tests ─────────────────────────────────────


class TestBuildDesignPrompt:
    def test_build_prompt_includes_design_name(self, svc, mock_simple_design):
        prompt = svc.build_design_prompt(mock_simple_design)
        assert "Simple Design" in prompt

    def test_build_prompt_includes_summary_section(self, svc, mock_simple_design):
        prompt = svc.build_design_prompt(mock_simple_design)
        assert "## Design Tree Summary" in prompt

    def test_build_prompt_includes_filtered_json(self, svc, mock_simple_design):
        prompt = svc.build_design_prompt(mock_simple_design)
        assert "## Filtered Figma JSON" in prompt

    def test_build_prompt_includes_instructions(self, svc, mock_simple_design):
        prompt = svc.build_design_prompt(mock_simple_design)
        assert "## Instructions" in prompt
        assert "Render ALL nodes" in prompt

    def test_build_prompt_includes_canvas_label(self, svc, mock_simple_design):
        prompt = svc.build_design_prompt(mock_simple_design)
        assert "Desktop" in prompt

    def test_build_prompt_multi_canvas(self, svc, mock_multi_canvas_design):
        prompt = svc.build_design_prompt(mock_multi_canvas_design)
        assert "Desktop HD" in prompt
        assert "Mobile" in prompt
        assert "responsive" in prompt.lower()

    def test_build_prompt_single_canvas_no_responsive(self, svc, mock_simple_design):
        prompt = svc.build_design_prompt(mock_simple_design)
        assert "responsive" not in prompt.lower()

    def test_build_prompt_no_document_fallback(self, svc):
        prompt = svc.build_design_prompt({"name": "Fallback"})
        assert "could not be fully parsed" in prompt

    def test_build_prompt_empty_document_fallback(self, svc):
        prompt = svc.build_design_prompt({"name": "Empty", "document": {}})
        assert "could not be fully parsed" in prompt


# ── Cache tests ───────────────────────────────────────────────


class TestCache:
    def test_clear_cache_all(self, svc):
        # Populate cache by calling clear_cache to set up state
        FigmaService.clear_cache()
        assert FigmaService.get_cache_info()["entries"] == 0

    def test_clear_cache_specific_key(self, svc):
        FigmaService.clear_cache("test_key")
        assert FigmaService.get_cache_info()["entries"] == 0

    def test_get_cache_info_structure(self, svc):
        info = FigmaService.get_cache_info()
        assert "entries" in info
        assert "keys" in info
        assert "ttl_seconds" in info
        assert info["ttl_seconds"] == 300
