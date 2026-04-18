"use client";

import { useState } from "react";

const EXAMPLES = [
  "55yo male, stage III NSCLC, prior pembrolizumab, ECOG 1, PD-L1 high, Houston TX",
  "42yo female, HER2+ breast cancer stage II, prior trastuzumab and docetaxel, ECOG 0, New York",
  "68yo male, metastatic colorectal cancer, KRAS G12C, prior FOLFOX and bevacizumab, ECOG 2",
];

interface PatientInputProps {
  onSubmit: (text: string) => void;
  disabled: boolean;
}

export default function PatientInput({ onSubmit, disabled }: PatientInputProps) {
  const [text, setText] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (text.trim()) {
      onSubmit(text.trim());
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="patient-input" className="block text-sm font-medium text-gray-700 mb-1">
          Patient Description
        </label>
        <textarea
          id="patient-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={disabled}
          placeholder="Describe the patient: age, sex, diagnosis, stage, biomarkers, prior therapies, performance status, location..."
          rows={4}
          className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none disabled:bg-gray-50 disabled:text-gray-500 resize-none"
        />
      </div>

      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((example, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setText(example)}
              disabled={disabled}
              className="text-xs px-2.5 py-1 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300 disabled:opacity-50 transition-colors"
            >
              Example {i + 1}
            </button>
          ))}
        </div>

        <button
          type="submit"
          disabled={disabled || !text.trim()}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 focus:ring-2 focus:ring-blue-500/20 focus:outline-none disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          Find Trials
        </button>
      </div>
    </form>
  );
}
