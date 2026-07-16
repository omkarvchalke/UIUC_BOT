export type StudentType = "freshman" | "transfer" | "graduate" | "international";

export const STUDENT_TYPE_LABELS: Record<StudentType, string> = {
  freshman: "Freshman",
  transfer: "Transfer student",
  graduate: "Graduate student",
  international: "International student",
};

export interface Citation {
  title: string;
  url: string;
  department: string;
  topic: string;
  // Debug-mode-only fields -- always present on the wire (see ChatCitation
  // on the backend), kept optional here so existing Citation literals in
  // tests/fixtures don't need updating.
  subtopic?: string | null;
  fused_score?: number;
  rerank_score?: number | null;
}

export interface ChatApiResponse {
  answer: string;
  grounded: boolean;
  needs_clarification: boolean;
  citations: Citation[];
  topic: string | null;
  classification_confidence: number | null;
}

export type FeedbackRating = "helpful" | "not_helpful";

export interface FeedbackRequest {
  session_id: string;
  message_id: string;
  question: string;
  answer: string;
  rating: FeedbackRating;
  comment?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  grounded?: boolean;
  needsClarification?: boolean;
  topic?: string | null;
  classificationConfidence?: number | null;
  createdAt: string;
  // Only set on assistant messages -- the user question this answer was
  // responding to, stashed at creation time in useChat so feedback
  // submission doesn't need to look up the preceding message.
  question?: string;
  feedback?: FeedbackRating;
}
