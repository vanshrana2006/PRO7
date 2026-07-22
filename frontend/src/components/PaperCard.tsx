import Link from "next/link";
import { CheckCircle2, Clock, AlertCircle, Loader2 } from "lucide-react";
import type { PaperSummary } from "@/types/api";

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; label: string; color: string }> = {
  completed: { icon: CheckCircle2, label: "Extracted", color: "text-phosphor" },
  failed: { icon: AlertCircle, label: "Failed", color: "text-red-400" },
  downloading: { icon: Loader2, label: "Downloading", color: "text-discovery" },
  extracting: { icon: Loader2, label: "Extracting", color: "text-discovery" },
  not_started: { icon: Clock, label: "Queued", color: "text-ink-faint" },
};

export function PaperCard({ paper }: { paper: PaperSummary }) {
  const status = STATUS_CONFIG[paper.extraction_status] ?? STATUS_CONFIG.not_started;
  const StatusIcon = status.icon;

  return (
    <Link
      href={`/papers/${paper.id}`}
      className="glass-panel tilt-card p-5 flex flex-col gap-3 hover:border-phosphor/30"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-base text-ink leading-snug line-clamp-2">{paper.title}</h3>
        <span className={`flex items-center gap-1 text-xs shrink-0 ${status.color}`}>
          <StatusIcon className="h-3.5 w-3.5" />
        </span>
      </div>

      {paper.authors.length > 0 && (
        <p className="text-xs text-ink-muted truncate">
          {paper.authors
            .slice(0, 3)
            .map((a) => a.name)
            .join(", ")}
          {paper.authors.length > 3 ? ", et al." : ""}
        </p>
      )}

      <div className="flex items-center gap-2 mt-1">
        {paper.primary_category && <span className="pill">{paper.primary_category}</span>}
        <span className="pill">{status.label}</span>
      </div>
    </Link>
  );
}
