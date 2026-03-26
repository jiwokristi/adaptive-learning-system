const API_BASE = "/api";

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  status: string;
  page_count: number | null;
  created_at: string;
  topic_count?: number;
  concept_count?: number;
  error_message?: string;
}

export interface Topic {
  id: string;
  name: string;
  parent_topic_id: string | null;
  depth: number;
  concept_count: number;
}

export interface Concept {
  id: string;
  name: string;
  definition: string;
  concept_type: string;
  difficulty: number;
  importance: number;
  source_pages: number[];
  supporting_quote: string | null;
  topic_name?: string;
}

export interface TopicWithConcepts extends Topic {
  concepts: Concept[];
}

export interface Exam {
  id: string;
  document_id: string;
  status: string;
  question_count: number;
  score: number | null;
  max_score: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface ExamQuestion {
  id: string;
  question_index: number;
  question_text: string;
  question_type: string;
  options: { label: string; text: string }[];
  bloom_level: string | null;
  difficulty: number;
}

export interface ExamDetail extends Exam {
  questions: ExamQuestion[];
}

export interface QuestionResult {
  question_id: string;
  question_text: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  explanation: string;
}

export interface ExamResult extends Exam {
  questions: QuestionResult[];
}

export interface TopicMastery {
  topic_id: string;
  topic_name: string;
  mastery_score: number;
  attempts: number;
  correct: number;
}

// -- API functions --

export async function uploadDocument(file: File, userId: string): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  form.append("user_id", userId);

  const res = await fetch(`${API_BASE}/documents/`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listDocuments(userId: string): Promise<Document[]> {
  const res = await fetch(`${API_BASE}/documents/?user_id=${userId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDocument(documentId: string): Promise<Document> {
  const res = await fetch(`${API_BASE}/documents/${documentId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getTopicsWithConcepts(documentId: string): Promise<TopicWithConcepts[]> {
  const res = await fetch(`${API_BASE}/documents/${documentId}/topics`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function generateExam(
  userId: string,
  documentId: string,
  numQuestions: number = 10
): Promise<Exam> {
  const res = await fetch(`${API_BASE}/exams/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      document_id: documentId,
      num_questions: numQuestions,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getExam(examId: string): Promise<ExamDetail> {
  const res = await fetch(`${API_BASE}/exams/${examId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function submitExam(
  examId: string,
  answers: { question_id: string; answer: string }[]
): Promise<ExamResult> {
  const res = await fetch(`${API_BASE}/exams/${examId}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getExamResults(examId: string): Promise<ExamResult> {
  const res = await fetch(`${API_BASE}/exams/${examId}/results`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDocumentMastery(
  documentId: string,
  userId: string
): Promise<TopicMastery[]> {
  const res = await fetch(
    `${API_BASE}/documents/${documentId}/mastery?user_id=${userId}`
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
