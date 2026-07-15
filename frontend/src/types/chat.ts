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

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  grounded?: boolean;
  needsClarification?: boolean;
  createdAt: string;
}
