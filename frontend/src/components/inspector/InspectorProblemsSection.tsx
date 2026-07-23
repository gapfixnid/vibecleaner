import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { BubbleInfo } from "../../types";

interface InspectorProblemsSectionProps {
  selectedBubble: BubbleInfo;
  t?: (key: string) => string;
}

function formatStatus(status: string | undefined, unknownLabel: string): string {
  if (!status) return unknownLabel;
  return status.replace(/_/g, " ");
}

function formatProblem(
  problem: import("../../types").BubbleProblemDto,
  t: (key: string) => string,
): string {
  if (problem.detail) return problem.detail;
  const key = `problems.${problem.code}`;
  const translated = t(key);
  return translated === key
    ? problem.code.replace(/_/g, " ").toLowerCase()
    : translated;
}

export function InspectorProblemsSection({ selectedBubble, t = (key) => key }: InspectorProblemsSectionProps) {
  const problems = selectedBubble.problems ?? [];
  const hasProblems = problems.length > 0;

  return (
    <div className={`section-panel problems-panel ${hasProblems ? "has-problems" : "ok"}`}>
      <div className="section-title-simple">{t("inspector.reviewStatus")}</div>
      <div className="review-status-row">
        {hasProblems ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
        <span className="review-status-text">{formatStatus(selectedBubble.status, t("inspector.unknown"))}</span>
      </div>
      {hasProblems && (
        <ul className="problem-list">
          {problems.map((problem, index) => (
            <li key={`${index}-${problem.code}-${problem.detail ?? ""}`} className="problem-item">
              {formatProblem(problem, t)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
