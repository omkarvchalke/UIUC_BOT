export type ConfidenceLevel = "high" | "medium" | "low";

export interface SourceRef {
  title: string;
  url: string;
  category: string;
  department: string;
  // Present on /api/sources results (SourceItem), absent on /api/chat's
  // inline source citations (the backend's ChatResponse.sources don't
  // include it) — optional so SourceCard can render either shape.
  source_type?: string;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  question: string;
  history?: ChatTurn[];
}

export interface ChatResponse {
  answer: string;
  sources: SourceRef[];
  confidence: ConfidenceLevel;
  next_steps: string[];
  requires_official_confirmation: boolean;
}

// POST /api/chat/stream SSE event shapes
export interface ChatStreamDeltaEvent {
  type: "delta";
  text: string;
}

export interface ChatStreamDoneEvent {
  type: "done";
  sources: SourceRef[];
  confidence: ConfidenceLevel;
  next_steps: string[];
  requires_official_confirmation: boolean;
}

export interface ChatStreamErrorEvent {
  type: "error";
  detail: string;
}

export type ChatStreamEvent =
  | ChatStreamDeltaEvent
  | ChatStreamDoneEvent
  | ChatStreamErrorEvent;

export interface SourceItem {
  title: string;
  category: string;
  department: string;
  url: string;
  source_type: string;
}

export interface SourceListResponse {
  sources: SourceItem[];
}

export type StudentType = "freshman" | "transfer" | "graduate";
export type StudentStatus = "domestic" | "international";
export type Term = "fall" | "spring";
export type Housing = "on-campus" | "off-campus" | "not sure";

export interface ChecklistRequest {
  student_type: StudentType;
  student_status: StudentStatus;
  term: Term;
  housing: Housing;
}

export interface ChecklistItem {
  task: string;
  source_title?: string | null;
  source_url?: string | null;
}

export interface ChecklistSection {
  title: string;
  items: ChecklistItem[];
}

export interface ChecklistResponse {
  disclaimer: string;
  sections: ChecklistSection[];
}

export type FeedbackRating =
  | "helpful"
  | "not_helpful"
  | "wrong_source"
  | "missing_information";

export interface FeedbackRequest {
  question: string;
  answer: string;
  rating: FeedbackRating;
  comment?: string | null;
  source_titles: string[];
}

export interface FeedbackResponse {
  status: string;
}

export interface HealthResponse {
  status: string;
  service: string;
}

// Chat page message model (client-side only, not sent to the backend as-is)
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  question?: string;
  response?: ChatResponse;
  error?: string;
  // True while an assistant message's answer text is still being appended
  // to via SSE deltas — MessageBubble hides confidence/sources/next-steps
  // until the stream finishes and this flips to false.
  streaming?: boolean;
}
