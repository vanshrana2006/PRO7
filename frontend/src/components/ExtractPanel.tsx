"use client";

import { useState } from "react";
import { Network, Loader2, Sparkles } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { GraphResponse } from "@/types/api";

const TYPE_COLORS: Record<string, string> = {
  method: "text-phosphor",
  dataset: "text-discovery",
  metric: "text-blue-300",
  claim: "text-purple-300",
  paper: "text-ink",
};

export function ExtractPanel({ paperId }: { paperId: string }) {
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [methodUsed, setMethodUsed] = useState<string | null>(null);

  async function handleExtract() {
    setStatus("loading");
    setError(null);
    try {
      const result = await api.extractKnowledge(paperId);
      setMethodUsed(result.method_used);
      const g = await api.getGraph(paperId);
      setGraph(g);
      setStatus("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Extraction failed");
      setStatus("error");
    }
  }

  const grouped = graph?.nodes.reduce<Record<string, typeof graph.nodes>>((acc, node) => {
    if (node.type === "paper") return acc;
    (acc[node.type] ??= []).push(node);
    return acc;
  }, {});

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center justify-between mb-1">
        <h2 className="font-display text-lg text-ink flex items-center gap-2">
          <Network className="h-4 w-4 text-phosphor" />
          Knowledge Graph
        </h2>
        {status !== "done" && (
          <button onClick={handleExtract} disabled={status === "loading"} className="btn-secondary">
            {status === "loading" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Extract knowledge
          </button>
        )}
      </div>

      {methodUsed && (
        <p className="text-xs text-ink-faint mb-4 font-mono">
          extracted via {methodUsed === "llm" ? "LLM refinement" : "heuristic pattern matching"}
        </p>
      )}

      {error && <p className="text-sm text-discovery mt-2">{error}</p>}

      {status === "idle" && !error && (
        <p className="text-sm text-ink-muted mt-3">
          Extract methods, datasets, metrics, and claims from this paper and merge them into the
          shared knowledge graph.
        </p>
      )}

      {grouped && Object.keys(grouped).length > 0 && (
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
          {Object.entries(grouped).map(([type, nodes]) => (
            <div key={type}>
              <p className={`font-mono text-xs uppercase tracking-wider mb-2 ${TYPE_COLORS[type] ?? "text-ink-muted"}`}>
                {type}s ({nodes.length})
              </p>
              <ul className="flex flex-col gap-1.5">
                {nodes.map((n) => (
                  <li key={n.id} className="text-sm text-ink-muted truncate" title={n.name}>
                    {n.name}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {status === "done" && grouped && Object.keys(grouped).length === 0 && (
        <p className="text-sm text-ink-faint mt-3">
          No methods, datasets, metrics, or claims were recognized in this paper&apos;s text.
        </p>
      )}
    </div>
  );
}
