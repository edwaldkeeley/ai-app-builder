export interface Project {
  id: string;
  name: string;
  description: string;
  status: "idle" | "generating" | "error";
  file_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectFile {
  path: string;
  content: string;
  file_type: "html" | "css" | "javascript" | "json" | "python" | "other";
}

export interface ProjectDetail {
  id: string;
  name: string;
  description: string;
  status: "idle" | "generating" | "error";
  files: ProjectFile[];
  created_at: string;
  updated_at: string;
}

export interface SandboxState {
  project_id: string;
  files: ProjectFile[];
  active_file_path: string | null;
}

export interface GenerateResponse {
  project_id: string;
  project_name: string;
  message: string;
  files: ProjectFile[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  files?: ProjectFile[];
  timestamp: string;
}

export interface ChatMessageSchema {
  id: number;
  project_id: string;
  role: string;
  content: string;
  files: ProjectFile[];
  created_at: string;
}

// ── Figma ──────────────────────────────────────────────────

export interface FigmaFile {
  key: string;
  name: string;
  last_modified?: string;
  thumbnail_url?: string;
}

export interface FigmaStatus {
  connected: boolean;
}

