"use client";

import { useState } from "react";
import type { Clarification } from "@/lib/types";

interface ClarificationFormProps {
  clarifications: Clarification[];
  onSubmit: (responses: { question_id: string; answer: string }[]) => void;
  disabled: boolean;
}

export default function ClarificationForm({ clarifications, onSubmit, disabled }: ClarificationFormProps) {
  const [answers, setAnswers] = useState<Record<string, string>>(() =>
    Object.fromEntries(clarifications.map((_, i) => [String(i), ""]))
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const responses = clarifications.map((c, i) => ({
      question_id: c.question,
      answer: answers[String(i)] || "",
    }));
    onSubmit(responses);
  }

  const allAnswered = clarifications.every((_, i) => answers[String(i)]?.trim());

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-5">
      <div className="flex items-start gap-3 mb-4">
        <div className="h-8 w-8 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
          <svg className="h-4 w-4 text-amber-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
          </svg>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-amber-900">Clarification Needed</h3>
          <p className="text-xs text-amber-700 mt-0.5">
            More information is needed to accurately match trials. Please answer the following:
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {clarifications.map((c, i) => (
          <div key={i} className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-800">
              {c.question}
            </label>
            <p className="text-xs text-gray-500">{c.context}</p>
            <input
              type="text"
              value={answers[String(i)] || ""}
              onChange={(e) => setAnswers({ ...answers, [String(i)]: e.target.value })}
              disabled={disabled}
              placeholder="Your answer..."
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none disabled:bg-gray-100"
            />
          </div>
        ))}

        <button
          type="submit"
          disabled={disabled || !allAnswered}
          className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 focus:ring-2 focus:ring-amber-500/20 focus:outline-none disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          Submit Answers
        </button>
      </form>
    </div>
  );
}
