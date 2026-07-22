"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Sparkles, Loader2, CheckCircle2, XCircle, Search, BookOpen, Network, FileText, AlertTriangle, Compass, Gem, TrendingUp, ClipboardList, Link2, Users } from "lucide-react";
import { api } from "@/lib/api";
import type { ResearchRunResponse } from "@/types/api";
import { MarkdownView } from "@/components/MarkdownView";

const AGENT_ICONS: Record<string, typeof Search> = {
  discovery_agent: Search,
  reading_agent: FileText,
  extraction_agent: Network,
  contradiction_agent: AlertTriangle,
  gap_agent: Compass,
  novelty_agent: Gem,
  timeline_agent: TrendingUp,
  analysis_agent: ClipboardList,
  citation_agent: Link2,
  recommendation_agent: Users,
  survey_agent: BookOpen,
};

interface ProgressEvent {
  agent: string;
  success: boolean;
  summary: string;
}

export default function ResearchPage() {
  const [query, setQuery] = useState("");
  const [maxPapers, setMaxPapers] = useState(5);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ResearchRunResponse | null>(null);
  const [liveProgress, setLiveProgress] = useState<ProgressEvent[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  // A ref, not state: es.onerror's closure is assigned once per run and
  // would otherwise capture liveProgress's value at that moment forever
  // (a classic React stale-closure bug) -- a ref stays current across
  // every later mutation without needing onerror to be redefined.
  const receivedAnyEventRef = useRef(false);

  useEffect(() => {
    // Closes the connection if the user navigates away mid-run -- without
    // this, an EventSource left open after unmount keeps the browser
    // connection (and the server-side generator producing it) alive
    // indefinitely for no one.
    return () => eventSourceRef.current?.close();
  }, []);

  function handleRun(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || running) return;

    eventSourceRef.current?.close();

    setRunning(true);
    setError(null);
    setResult(null);
    setLiveProgress([]);
    receivedAnyEventRef.current = false;

    const es = new EventSource(api.researchStreamUrl(query, maxPapers));
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      receivedAnyEventRef.current = true;
      const payload = JSON.parse(event.data);
      if (payload.type === "progress") {
        setLiveProgress((prev) => [...prev, payload]);
      } else if (payload.type === "result") {
        const { type: _type, ...rest } = payload;
        setResult(rest as ResearchRunResponse);
        setRunning(false);
        es.close();
      }
    };

    es.onerror = () => {
      // A live pipeline run can legitimately take minutes (downloading
      // and extracting several PDFs); only surface an error if we never
      // got a single event, since EventSource retries transient network
      // hiccups on its own and closing here would abandon a run that's
      // actually still in progress server-side.
      if (!receivedAnyEventRef.current) {
        setError("Connection to the research pipeline was lost. Is the backend running?");
        setRunning(false);
      }
      es.close();
    };
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow mb-3">Multi-Agent Pipeline</p>
        <h1 className="font-display text-3xl text-ink mb-2">Run autonomous research</h1>
        <p className="text-ink-muted max-w-2xl leading-relaxed">
          Discovery, Reading, Extraction, and seven analysis agents run in sequence, streamed live as
          each one finishes: search arXiv and Semantic Scholar, ingest and structurally read each
          paper, extract methods/datasets/claims into the knowledge graph, then synthesize a
          literature review — no manual steps.
        </p>
      </div>

      <form onSubmit={handleRun} className="glass-panel p-6 flex flex-col sm:flex-row gap-3 items-stretch sm:items-end">
        <div className="flex-1">
          <label className="text-xs text-ink-muted font-mono uppercase tracking-wider mb-1.5 block">
            Research topic
          </label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. retrieval augmented generation"
            className="input-field"
          />
        </div>
        <div className="sm:w-36">
          <label className="text-xs text-ink-muted font-mono uppercase tracking-wider mb-1.5 block">
            Max papers
          </label>
          <input
            type="number"
            min={1}
            max={15}
            value={maxPapers}
            onChange={(e) => setMaxPapers(Number(e.target.value))}
            className="input-field"
          />
        </div>
        <button type="submit" disabled={running} className="btn-primary h-[46px]">
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {running ? "Running pipeline..." : "Run pipeline"}
        </button>
      </form>

      {error && <div className="glass-panel p-4 text-sm text-discovery">{error}</div>}

      {running && (
        <div className="glass-panel p-6">
          <p className="text-ink-muted text-sm mb-4">
            Streaming live as each agent finishes — this can take a minute for several papers.
          </p>
          <div className="flex flex-col gap-2">
            {liveProgress.map((p, i) => {
              const Icon = AGENT_ICONS[p.agent] ?? Sparkles;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-center gap-3 text-sm"
                >
                  <Icon className="h-4 w-4 text-phosphor shrink-0" />
                  {p.success ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-phosphor shrink-0" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
                  )}
                  <span className="text-ink-muted capitalize shrink-0">{p.agent.replace("_", " ")}</span>
                  <span className="text-ink-faint truncate">{p.summary}</span>
                </motion.div>
              );
            })}
            {liveProgress.length === 0 && (
              <div className="flex items-center gap-2 text-sm text-ink-faint">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Starting discovery agent...
              </div>
            )}
          </div>
        </div>
      )}

      {result && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-6">
          {/* Agent trace */}
          <div className="glass-panel p-6">
            <h2 className="font-display text-lg text-ink mb-4">Agent trace</h2>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              {result.agent_results.map((r) => {
                const Icon = AGENT_ICONS[r.agent] ?? Sparkles;
                return (
                  <div key={r.agent} className="rounded-xl border border-glass-border p-4 bg-white/[0.02]">
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className="h-4 w-4 text-phosphor" />
                      {r.success ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-phosphor ml-auto" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 text-red-400 ml-auto" />
                      )}
                    </div>
                    <p className="text-xs font-mono text-ink-muted mb-1 capitalize">
                      {r.agent.replace("_", " ")}
                    </p>
                    <p className="text-xs text-ink-faint leading-snug">{r.summary}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            <StatCard label="Discovered" value={result.discovered_count} />
            <StatCard label="Ingested" value={result.ingested_count} />
            <StatCard label="Papers analyzed" value={result.knowledge.length} />
          </div>

          {/* Research intelligence: contradictions, gaps, novelty */}
          {(result.contradictions.length > 0 || result.gaps.length > 0 || result.novelty.some((n) => n.novelty_score < 1)) && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {result.contradictions.length > 0 && (
                <div className="glass-panel p-5">
                  <h3 className="flex items-center gap-2 font-display text-base text-ink mb-3">
                    <AlertTriangle className="h-4 w-4 text-discovery" />
                    Contradictions
                  </h3>
                  <div className="flex flex-col gap-3">
                    {result.contradictions.map((c) => (
                      <div key={c.dataset} className="text-sm">
                        <p className="text-ink">
                          {c.dataset} <span className="text-ink-faint font-mono text-xs">±{c.spread}pp</span>
                        </p>
                        <ul className="text-xs text-ink-muted mt-1 space-y-0.5">
                          {c.figures.map((f, i) => (
                            <li key={i}>
                              {f.paper_title}: {f.value}%
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.gaps.length > 0 && (
                <div className="glass-panel p-5">
                  <h3 className="flex items-center gap-2 font-display text-base text-ink mb-3">
                    <Compass className="h-4 w-4 text-phosphor" />
                    Research gaps
                  </h3>
                  <ul className="flex flex-col gap-2 text-sm text-ink-muted">
                    {result.gaps.map((g, i) => (
                      <li key={i}>
                        <span className="text-ink">{g.subject}</span>
                        <p className="text-xs text-ink-faint">{g.detail}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.novelty.some((n) => n.novelty_score < 1) && (
                <div className="glass-panel p-5">
                  <h3 className="flex items-center gap-2 font-display text-base text-ink mb-3">
                    <Gem className="h-4 w-4 text-purple-300" />
                    Novelty overlap
                  </h3>
                  <ul className="flex flex-col gap-2 text-sm">
                    {result.novelty
                      .filter((n) => n.novelty_score < 1)
                      .map((n, i) => (
                        <li key={i}>
                          <span className="text-ink">{n.method_name}</span>{" "}
                          <span className="text-xs font-mono text-ink-faint">{n.novelty_score.toFixed(2)}</span>
                          <p className="text-xs text-ink-muted">overlaps with {n.similar_to.join(", ")}</p>
                        </li>
                      ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Benchmark timelines */}
          {result.timelines.length > 0 && (
            <div className="glass-panel p-6">
              <h2 className="flex items-center gap-2 font-display text-lg text-ink mb-4">
                <TrendingUp className="h-4 w-4 text-phosphor" />
                Benchmark progress
              </h2>
              <div className="flex flex-col gap-4">
                {result.timelines.map((t) => (
                  <div key={t.dataset}>
                    <p className="text-sm text-ink mb-2">
                      {t.dataset} {t.improved && <span className="text-phosphor text-xs">↑ improved over time</span>}
                    </p>
                    <div className="flex items-end gap-3 h-16">
                      {t.points.map((p, i) => (
                        <div key={i} className="flex flex-col items-center gap-1">
                          <div
                            className="w-8 bg-phosphor/30 rounded-t"
                            style={{ height: `${Math.max(8, (p.value / 100) * 56)}px` }}
                            title={p.raw_claim}
                          />
                          <span className="text-[10px] text-ink-faint font-mono">{p.year}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Missing citations */}
          {result.missing_citations.length > 0 && (
            <div className="glass-panel p-6">
              <h2 className="flex items-center gap-2 font-display text-lg text-ink mb-4">
                <Link2 className="h-4 w-4 text-discovery" />
                Possible missing citations
              </h2>
              <ul className="flex flex-col gap-2">
                {result.missing_citations.map((m, i) => (
                  <li key={i} className="text-sm text-ink-muted">
                    <span className="text-ink">{m.citing_paper_title}</span> — {m.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Per-paper analysis */}
          {result.analyses.length > 0 && (
            <div className="glass-panel p-6">
              <h2 className="flex items-center gap-2 font-display text-lg text-ink mb-4">
                <ClipboardList className="h-4 w-4 text-phosphor" />
                Paper analysis
              </h2>
              <div className="flex flex-col gap-4">
                {result.analyses.map((a) => (
                  <div key={a.paper_id} className="border-t border-glass-border pt-4 first:border-0 first:pt-0">
                    <p className="text-sm text-ink mb-1">{a.paper_title}</p>
                    <p className="text-xs text-ink-muted mb-2">{a.summary}</p>
                    <div className="flex flex-wrap gap-2">
                      {a.novelty_score !== null && (
                        <span className="pill">novelty {a.novelty_score.toFixed(2)}</span>
                      )}
                      <span className="pill">impact {a.impact_score.toFixed(2)}</span>
                      <span className="pill">evidence density {a.evidence_density.toFixed(2)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Survey */}
          <div className="glass-panel p-8">
            <MarkdownView content={result.survey_markdown} />
          </div>
        </motion.div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="glass-panel p-5 text-center">
      <p className="font-display text-3xl text-phosphor">{value}</p>
      <p className="text-xs text-ink-muted font-mono uppercase tracking-wider mt-1">{label}</p>
    </div>
  );
}
