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
}

export interface ChatApiResponse {
  answer: string;
  grounded: boolean;
  needs_clarification: boolean;
  citations: Citation[];
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
  createdAt: string;
  // Only set on assistant messages -- the user question this answer was
  // responding to, stashed at creation time in useChat so feedback
  // submission doesn't need to look up the preceding message.
  question?: string;
  feedback?: FeedbackRating;
}
