"use client";

import { useState, useEffect, use } from "react";
import { getExam, submitExam, type ExamDetail, type ExamResult } from "@/lib/api";

export default function ExamPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [exam, setExam] = useState<ExamDetail | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [results, setResults] = useState<ExamResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState(0);

  useEffect(() => {
    getExam(id).then(setExam);
  }, [id]);

  async function handleSubmit() {
    if (!exam) return;

    const unanswered = exam.questions.filter((q) => !answers[q.id]);
    if (unanswered.length > 0) {
      if (
        !confirm(
          `You have ${unanswered.length} unanswered question(s). Submit anyway?`
        )
      )
        return;
    }

    setSubmitting(true);
    try {
      const result = await submitExam(
        id,
        exam.questions.map((q) => ({
          question_id: q.id,
          answer: answers[q.id] || "",
        }))
      );
      setResults(result);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (!exam) return <div className="text-gray-500">Loading exam...</div>;

  // -- Results view --
  if (results) {
    const correct = results.questions.filter((q) => q.is_correct).length;
    const total = results.questions.length;
    const pct = Math.round((correct / total) * 100);

    return (
      <div>
        <a href="/" className="text-sm text-blue-600 hover:underline">
          &larr; Back to documents
        </a>

        <div className="bg-white border border-gray-200 rounded-lg p-6 mt-4 mb-6 text-center">
          <h1 className="text-2xl font-bold mb-2">Quiz Results</h1>
          <p
            className={`text-4xl font-bold ${
              pct >= 70
                ? "text-green-600"
                : pct >= 50
                ? "text-yellow-600"
                : "text-red-600"
            }`}
          >
            {pct}%
          </p>
          <p className="text-gray-500 mt-1">
            {correct} of {total} correct
          </p>
        </div>

        <div className="space-y-4">
          {results.questions.map((q, i) => (
            <div
              key={q.question_id}
              className={`bg-white border rounded-lg p-5 ${
                q.is_correct ? "border-green-200" : "border-red-200"
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`mt-0.5 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white ${
                    q.is_correct ? "bg-green-500" : "bg-red-500"
                  }`}
                >
                  {q.is_correct ? "\u2713" : "\u2717"}
                </span>
                <div className="flex-1">
                  <p className="font-medium mb-2">
                    {i + 1}. {q.question_text}
                  </p>
                  {!q.is_correct && (
                    <p className="text-sm text-red-600 mb-1">
                      Your answer: {q.user_answer || "(no answer)"}
                    </p>
                  )}
                  <p className="text-sm text-green-700 mb-2">
                    Correct answer: {q.correct_answer}
                  </p>
                  <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
                    {q.explanation}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // -- Quiz view --
  const question = exam.questions[currentQuestion];
  const totalQuestions = exam.questions.length;
  const answeredCount = Object.keys(answers).length;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <a href="/" className="text-sm text-blue-600 hover:underline">
          &larr; Exit quiz
        </a>
        <span className="text-sm text-gray-500">
          {answeredCount}/{totalQuestions} answered
        </span>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm text-gray-500">
            Question {currentQuestion + 1} of {totalQuestions}
          </span>
          {question.bloom_level && (
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
              {question.bloom_level}
            </span>
          )}
        </div>

        <h2 className="text-lg font-medium mb-6">{question.question_text}</h2>

        <div className="space-y-3">
          {question.options.map((option) => (
            <button
              key={option.label}
              onClick={() =>
                setAnswers({ ...answers, [question.id]: option.label })
              }
              className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                answers[question.id] === option.label
                  ? "border-blue-500 bg-blue-50 text-blue-900"
                  : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
              }`}
            >
              <span className="font-medium mr-2">{option.label}.</span>
              {option.text}
            </button>
          ))}
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setCurrentQuestion(Math.max(0, currentQuestion - 1))}
          disabled={currentQuestion === 0}
          className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-30"
        >
          Previous
        </button>

        <div className="flex gap-1">
          {exam.questions.map((q, i) => (
            <button
              key={q.id}
              onClick={() => setCurrentQuestion(i)}
              className={`w-8 h-8 rounded text-xs font-medium ${
                i === currentQuestion
                  ? "bg-blue-600 text-white"
                  : answers[q.id]
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-500"
              }`}
            >
              {i + 1}
            </button>
          ))}
        </div>

        {currentQuestion < totalQuestions - 1 ? (
          <button
            onClick={() =>
              setCurrentQuestion(Math.min(totalQuestions - 1, currentQuestion + 1))
            }
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Next
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="px-5 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {submitting ? "Submitting..." : "Submit Quiz"}
          </button>
        )}
      </div>
    </div>
  );
}
