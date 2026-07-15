import type { StudentType } from "./chat";

export interface SessionCreateRequest {
  student_type?: StudentType | null;
  semester?: string | null;
  college?: string | null;
  department?: string | null;
}

export interface SessionResponse {
  id: string;
  student_type: StudentType | null;
  semester: string | null;
  college: string | null;
  department: string | null;
  created_at: string;
  updated_at: string;
}
