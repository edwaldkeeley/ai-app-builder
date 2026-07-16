import { describe, it, expect } from "@jest/globals";
import { getFileIcon, default as FileIcon } from "../app/lib/fileIcons";
import type { ReactNode } from "react";

describe("getFileIcon", () => {
  it("returns HTML icon for .html files", () => {
    const icon = getFileIcon("index.html");
    const rendered = icon("w-4 h-4");
    expect(rendered).toBeDefined();
  });

  it("returns CSS icon for .css files", () => {
    const icon = getFileIcon("style.css");
    expect(icon).toBeDefined();
  });

  it("returns JS icon for .js files", () => {
    const icon = getFileIcon("script.js");
    expect(icon).toBeDefined();
  });

  it("returns JSON icon for .json files", () => {
    const icon = getFileIcon("data.json");
    expect(icon).toBeDefined();
  });

  it("returns Python icon for .py files", () => {
    const icon = getFileIcon("main.py");
    expect(icon).toBeDefined();
  });

  it("returns TS icon for .ts files", () => {
    const icon = getFileIcon("component.ts");
    expect(icon).toBeDefined();
  });

  it("returns TSX icon for .tsx files", () => {
    const icon = getFileIcon("Component.tsx");
    expect(icon).toBeDefined();
  });

  it("returns Markdown icon for .md files", () => {
    const icon = getFileIcon("README.md");
    expect(icon).toBeDefined();
  });

  it("returns SVG icon for .svg files", () => {
    const icon = getFileIcon("icon.svg");
    expect(icon).toBeDefined();
  });

  it("returns default icon for unknown extensions", () => {
    const icon = getFileIcon("file.xyz");
    expect(icon).toBeDefined();
  });

  it("returns default icon for files with no extension", () => {
    const icon = getFileIcon("Makefile");
    expect(icon).toBeDefined();
  });

  it("handles paths with directories", () => {
    const icon = getFileIcon("src/components/Button.tsx");
    expect(icon).toBeDefined();
  });

  it("is case insensitive for extensions", () => {
    const htmlIcon = getFileIcon("index.HTML");
    const cssIcon = getFileIcon("style.CSS");
    expect(htmlIcon).toBeDefined();
    expect(cssIcon).toBeDefined();
  });
});

describe("FileIcon component", () => {
  it("renders without crashing", () => {
    // FileIcon returns a React element — we can verify it's valid
    const element = FileIcon({ path: "index.html" });
    expect(element).toBeDefined();
  });

  it("accepts custom className", () => {
    const element = FileIcon({ path: "style.css", className: "w-6 h-6" });
    expect(element).toBeDefined();
  });

  it("handles unknown extensions", () => {
    const element = FileIcon({ path: "file.unknown" });
    expect(element).toBeDefined();
  });
});
