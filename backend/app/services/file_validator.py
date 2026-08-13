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

    This function rewrites the imports to the correct ES module syntax,
    handling both top-level and indented (inside function body) patterns.
    """
    fixed: list[ProjectFile] = []
    for f in files:
        if not f.path.endswith(".jsx"):
            fixed.append(f)
            continue

        content = f.content

        # Pattern 1: const { useState, useEffect } = React; (with or without indent)
        # -> import React, { useState, useEffect } from "react";
        # The import must be placed at the TOP of the file (no indent), even if
        # the original const assignment was inside a function body.
        import_pattern = re.compile(
            r'^[ \t]*const\s*\{\s*([^}]+)\s*\}\s*=\s*React\s*;?\s*\n?',
            re.MULTILINE,
        )
        imports_found = []
        def _collect_import(m: re.Match) -> str:
            hooks = m.group(1).strip()
            imports_found.append(hooks)
            return ""  # remove the line entirely

        content = import_pattern.sub(_collect_import, content)
        if imports_found:
            # Collect all unique hooks
            all_hooks = []
            seen = set()
            for hooks in imports_found:
                for h in [x.strip() for x in hooks.split(",")]:
                    if h and h not in seen:
                        seen.add(h)
                        all_hooks.append(h)

            hook_list = ", ".join(all_hooks)
            import_line = f'import React, {{ {hook_list} }} from "react";\n'
            # Only add the import if it's not already present
            if f'from "react"' not in content and "from 'react'" not in content:
                content = import_line + content.lstrip()

        # Pattern 2: const root = ReactDOM.createRoot(...)
        # -> import { createRoot } from "react-dom/client";
        # and: const root = createRoot(...)
        if "ReactDOM.createRoot" in content:
            content = content.replace("ReactDOM.createRoot", "createRoot")
            if 'from "react-dom/client"' not in content and "from 'react-dom/client'" not in content:
                content = 'import { createRoot } from "react-dom/client";\n' + content

        # Pattern 3: React.X used in JSX/JS expressions (but not inside string literals).
        # After Pattern 1, React is imported so React.useState() is valid JS.
        # But some tools/transpilers prefer bare hook names. Only replace when
        # the React.X token appears as actual code (not inside a string or comment).
        # Heuristic: React. followed by a word boundary, NOT preceded by a quote
        # character (i.e. not inside a string literal).
        content = re.sub(
            r'(?<!["\'`])React\.(\w+)',
            r'\1',
            content,
        )

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
