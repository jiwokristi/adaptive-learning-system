"use client";

import { useState, useEffect, use } from "react";
import {
  getDocument,
  getTopicsWithConcepts,
  getDocumentMastery,
  generateExam,
  type Document,
  type TopicWithConcepts,
  type TopicMastery,
} from "@/lib/api";

const USER_ID = "00000000-0000-0000-0000-000000000001";

export default function DocumentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [document, setDocument] = useState<Document | null>(null);
  const [topics, setTopics] = useState<TopicWithConcepts[]>([]);
  const [mastery, setMastery] = useState<TopicMastery[]>([]);
  const [expandedTopic, setExpandedTopic] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    getDocument(id).then(setDocument);
    getTopicsWithConcepts(id).then(setTopics);
    getDocumentMastery(id, USER_ID).then(setMastery).catch(() => {});
  }, [id]);

  async function handleGenerateExam() {
    setGenerating(true);
    try {
      const exam = await generateExam(USER_ID, id, 10);
      window.location.href = `/exams/${exam.id}`;
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to generate exam");
    } finally {
      setGenerating(false);
    }
  }

  if (!document) return <div className="text-gray-500">Loading...</div>;

  const masteryMap = Object.fromEntries(mastery.map((m) => [m.topic_id, m]));

  const typeColors: Record<string, string> = {
    definition: "bg-blue-100 text-blue-700",
    theorem: "bg-purple-100 text-purple-700",
    process: "bg-green-100 text-green-700",
    fact: "bg-gray-100 text-gray-700",
    formula: "bg-orange-100 text-orange-700",
    example: "bg-yellow-100 text-yellow-700",
    principle: "bg-red-100 text-red-700",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <a href="/" className="text-sm text-blue-600 hover:underline">
            &larr; Back to documents
          </a>
          <h1 className="text-2xl font-bold mt-2">{document.filename}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {document.page_count} pages &middot; {topics.length} topics &middot;{" "}
            {topics.reduce((sum, t) => sum + t.concepts.length, 0)} concepts
          </p>
        </div>
        <button
          onClick={handleGenerateExam}
          disabled={generating}
          className="bg-blue-600 text-white px-5 py-2.5 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {generating ? "Generating..." : "Practice Quiz"}
        </button>
      </div>

      {mastery.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-5 mb-6">
          <h2 className="font-semibold mb-3">Mastery by Topic</h2>
          <div className="space-y-2">
            {mastery.map((m) => (
              <div key={m.topic_id} className="flex items-center gap-3">
                <span className="text-sm w-48 truncate">{m.topic_name}</span>
                <div className="flex-1 bg-gray-200 rounded-full h-2.5">
                  <div
                    className={`h-2.5 rounded-full ${
                      m.mastery_score >= 0.7
                        ? "bg-green-500"
                        : m.mastery_score >= 0.4
                        ? "bg-yellow-500"
                        : "bg-red-500"
                    }`}
                    style={{ width: `${m.mastery_score * 100}%` }}
                  />
                </div>
                <span className="text-sm text-gray-500 w-20 text-right">
                  {Math.round(m.mastery_score * 100)}% ({m.correct}/{m.attempts})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {topics.map((topic) => (
          <div
            key={topic.id}
            className="bg-white border border-gray-200 rounded-lg overflow-hidden"
          >
            <button
              onClick={() =>
                setExpandedTopic(expandedTopic === topic.id ? null : topic.id)
              }
              className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <h3 className="font-semibold">{topic.name}</h3>
                <span className="text-xs text-gray-500">
                  {topic.concepts.length} concepts
                </span>
                {masteryMap[topic.id] && (
                  <span className="text-xs text-gray-500">
                    &middot; {Math.round(masteryMap[topic.id].mastery_score * 100)}%
                    mastered
                  </span>
                )}
              </div>
              <span className="text-gray-400">
                {expandedTopic === topic.id ? "\u25B2" : "\u25BC"}
              </span>
            </button>

            {expandedTopic === topic.id && (
              <div className="border-t border-gray-100 px-5 py-4 space-y-3">
                {topic.concepts.map((concept) => (
                  <div key={concept.id} className="pl-2 border-l-2 border-gray-200">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">{concept.name}</span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          typeColors[concept.concept_type] || "bg-gray-100"
                        }`}
                      >
                        {concept.concept_type}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600">{concept.definition}</p>
                    {concept.supporting_quote && (
                      <p className="text-xs text-gray-400 mt-1 italic">
                        &ldquo;{concept.supporting_quote}&rdquo;
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
