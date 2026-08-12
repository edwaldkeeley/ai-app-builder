"""File validation and post-processing for AI-generated code.

Validates generated files for common issues (missing required files, empty
content) and fixes React import patterns that the AI often gets wrong.
"""

from __future__ import annotations

import re

from app.models.schemas import FileType, ProjectFile


def fix_react_imports(files: list[ProjectFile]) -> list[ProjectFile]:
    """Post-process .jsx files to fix React import patterns.

    The AI often generates code using the global React object pattern:
      const { useState } = React;
    instead of proper ES module imports:
      import React, { useState } from "react";

    This function rewrites the imports to the correct ES module syntax.
    """
    fixed: list[ProjectFile] = []
    for f in files:
        if not f.path.endswith(".jsx"):
            fixed.append(f)
            continue

        content = f.content

        # Pattern 1: const { useState, useEffect } = React;
        # -> import React, { useState, useEffect } from "react";
        import_pattern = re.compile(
            r'const\s*\{\s*([^}]+)\s*\}\s*=\s*React\s*;?\s*\n?'
        )
        content = import_pattern.sub(
            lambda m: f'import React, {{ {m.group(1).strip()} }} from "react";\n',
            content,
        )

        # Pattern 2: const root = ReactDOM.createRoot(...)
        # -> import { createRoot } from "react-dom/client";
        # and: const root = createRoot(...)
        if "ReactDOM.createRoot" in content:
            content = content.replace("ReactDOM.createRoot", "createRoot")
            if 'from "react-dom/client"' not in content and "from 'react-dom/client'" not in content:
                content = 'import { createRoot } from "react-dom/client";\n' + content

        # Pattern 3: React.useState, React.useEffect, etc.
        # -> useState, useEffect (already imported via pattern 1)
        content = re.sub(r'React\.(\w+)', r'\1', content)

        fixed.append(ProjectFile(path=f.path, content=content, file_type=f.file_type))

    return fixed


def validate_generated_files(
    files: list[ProjectFile],
    design_name: str = "",
    framework: str = "vanilla",
) -> list[str]:
    """Validate generated files for common issues.

    Checks:
    - index.html exists (required for vanilla projects)
    - style.css exists (recommended)
    - script.js exists (recommended for vanilla)
    - App.jsx exists (required for react)
    - index.html has a <body> tag
    - index.html has a <title> tag
    - style.css has content (not empty)
    - script.js has content (not empty)

    Returns a list of warning messages (empty = no issues).
    """
    warnings: list[str] = []
    file_map = {f.path: f for f in files}

    if framework == "react":
        # React projects: App.jsx is the entry point
        if "App.jsx" not in file_map:
            warnings.append("Missing required file: App.jsx")
    else:
        # Vanilla projects: index.html is the entry point
        if "index.html" not in file_map:
            warnings.append("Missing required file: index.html")
        if "script.js" not in file_map:
            warnings.append("Missing required file: script.js")

    if "style.css" not in file_map:
        warnings.append("Missing required file: style.css")

    # Validate index.html structure (only if it exists)
    if "index.html" in file_map:
        html_content = file_map["index.html"].content
        if "<body" not in html_content:
            warnings.append("index.html is missing <body> tag")
        if "<title>" not in html_content:
            warnings.append("index.html is missing <title> tag")
        # Check if style.css is linked when it exists in the project
        if "style.css" in file_map and "href=\"style.css\"" not in html_content and "href='style.css'" not in html_content:
            warnings.append("index.html does not link to style.css")

    # Validate style.css has content (only if it exists)
    if "style.css" in file_map:
        css_content = file_map["style.css"].content.strip()
        if not css_content:
            warnings.append("style.css is empty")
        elif len(css_content) < 50:
            warnings.append(f"style.css seems too short ({len(css_content)} chars)")

    # Validate script.js has content (only if it exists)
    if "script.js" in file_map:
        js_content = file_map["script.js"].content.strip()
        if not js_content:
            warnings.append("script.js is empty")

    return warnings
