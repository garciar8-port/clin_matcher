"use client";

const STEPS = [
  { node: "intake_agent", label: "Extracting patient profile" },
  { node: "search_agent", label: "Searching ClinicalTrials.gov" },
  { node: "eligibility_evaluator", label: "Evaluating eligibility" },
  { node: "ranker_agent", label: "Ranking matches" },
];

interface ProgressIndicatorProps {
  currentNode: string;
  completedNodes: string[];
}

export default function ProgressIndicator({ currentNode, completedNodes }: ProgressIndicatorProps) {
  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-gray-700">Processing...</p>
      <div className="space-y-2">
        {STEPS.map((step) => {
          const isCompleted = completedNodes.includes(step.node);
          const isActive = currentNode === step.node && !isCompleted;

          return (
            <div key={step.node} className="flex items-center gap-3">
              <div className="flex-shrink-0">
                {isCompleted ? (
                  <div className="h-5 w-5 rounded-full bg-green-500 flex items-center justify-center">
                    <svg className="h-3 w-3 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  </div>
                ) : isActive ? (
                  <div className="h-5 w-5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                ) : (
                  <div className="h-5 w-5 rounded-full border-2 border-gray-200" />
                )}
              </div>
              <span className={`text-sm ${isCompleted ? "text-green-700" : isActive ? "text-blue-700 font-medium" : "text-gray-400"}`}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
