import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { BubbleInfo } from "../../types";

interface InspectorProblemsSectionProps {
  selectedBubble: BubbleInfo;
}

function formatStatus(status: string | undefined): string {
  if (!status) return "unknown";
  return status.replace(/_/g, " ");
}

export function InspectorProblemsSection({ selectedBubble }: InspectorProblemsSectionProps) {
  const problems = selectedBubble.problems ?? [];
  const hasProblems = problems.length > 0;

  return (
    <div className={`section-panel problems-panel ${hasProblems ? "has-problems" : "ok"}`}>
      <div className="section-title-simple">Review Status</div>
      <div className="review-status-row">
        {hasProblems ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
        <span className="review-status-text">{formatStatus(selectedBubble.status)}</span>
      </div>
      {hasProblems && (
        <ul className="problem-list">
          {problems.map((problem, index) => (
            <li key={`${index}-${problem}`} className="problem-item">
              {problem}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
