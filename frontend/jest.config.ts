import type { Config } from "jest";

const config: Config = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  transform: {
    "^.+\\.tsx?$": ["ts-jest", { tsconfig: "tsconfig.jest.json" }],
  },
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
  testPathIgnorePatterns: ["<rootDir>/.next/", "<rootDir>/node_modules/"],
  transformIgnorePatterns: ["node_modules/(?!(.*\\.mjs$|remark-gfm|react-markdown|vfile|unist-|unified|bail|is-plain-obj|trough|remark-|mdast-|micromark|decode-|character-|property-|hast-|space-|comma-|zwitch|ccount|escape-|markdown-table|trim-lines|@anthropic-ai|@monaco-editor))"],
};

export default config;
