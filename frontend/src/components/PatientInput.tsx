"use client";

import { useState } from "react";

const EXAMPLES = [
  "55-year-old male patient diagnosed with stage III non-small cell lung cancer. He was previously treated with pembrolizumab but experienced progression after 8 months. His PD-L1 expression is high (TPS >50%). Current performance status is ECOG 1. He has mild hypertension but is otherwise in good health. Located in the Houston, Texas area.",
  "42-year-old woman with HER2-positive invasive ductal carcinoma of the left breast, stage IIA. She completed neoadjuvant trastuzumab and docetaxel six months ago and achieved a partial response. ECOG performance status is 0. No significant comorbidities. She is based in New York City and interested in clinical trials.",
  "68-year-old male with metastatic colorectal adenocarcinoma, originally diagnosed two years ago. Tumor harbors a KRAS G12C mutation. He has been through two lines of therapy including FOLFOX and bevacizumab, both of which he progressed on. He has liver metastases and his current ECOG status is 2. Lives in the Chicago area.",
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
    <form onSubmit={handleSubmit} className="w-full space-y-4">
      <div className="flex flex-wrap gap-2 justify-start">
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
          className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none disabled:bg-white disabled:text-gray-500 resize-y"
        />
      </div>

      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="w-full rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 focus:ring-2 focus:ring-blue-500/20 focus:outline-none disabled:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Find Trials
      </button>
    </form>
  );
}
