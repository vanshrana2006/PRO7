"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Search as SearchIcon, Download, ExternalLink, Loader2, CheckCircle2, Library, Globe } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { UnifiedSearchResult, CorpusSearchResult } from "@/types/api";

type IngestState = "idle" | "loading" | "done" | "error";
type Tab = "discover" | "library";

const SOURCE_LABEL: Record<string, string> = {
  arxiv: "arXiv",
  semantic_scholar: "Semantic Scholar",
};

export default function SearchPage() {
  const [tab, setTab] = useState<Tab>("discover");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<UnifiedSearchResult[]>([]);
  const [libraryResults, setLibraryResults] = useState<CorpusSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ingestStates, setIngestStates] = useState<Record<string, IngestState>>({});

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      if (tab === "discover") {
        const res = await api.discover(query, 15);
        setResults(res);
      } else {
        const res = await api.corpusSearch(query, 15);
        setLibraryResults(res.results);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed. Is the backend running?");
    } finally {
      setSearching(false);
    }
  }

  async function handleIngest(arxivId: string) {
    setIngestStates((s) => ({ ...s, [arxivId]: "loading" }));
    try {
      const res = await api.ingestPaper(arxivId);
      setIngestStates((s) => ({ ...s, [arxivId]: res.status === "completed" ? "done" : "error" }));
    } catch {
      setIngestStates((s) => ({ ...s, [arxivId]: "error" }));
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow mb-3">Discovery Agent</p>
        <h1 className="font-display text-3xl text-ink mb-2">Search</h1>
        <p className="text-ink-muted max-w-xl">
          Discover new papers across arXiv and Semantic Scholar, or search what you&apos;ve
          already ingested with BM25 ranked full-text search.
        </p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => setTab("discover")}
          className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm transition-colors ${
            tab === "discover" ? "bg-phosphor/10 text-phosphor" : "text-ink-muted hover:text-ink hover:bg-white/5"
          }`}
        >
          <Globe className="h-3.5 w-3.5" />
          Discover new papers
        </button>
        <button
          onClick={() => setTab("library")}
          className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm transition-colors ${
            tab === "library" ? "bg-phosphor/10 text-phosphor" : "text-ink-muted hover:text-ink hover:bg-white/5"
          }`}
        >
          <Library className="h-3.5 w-3.5" />
          Search your library
        </button>
      </div>

      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-faint" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              tab === "discover"
                ? "e.g. graph neural networks, diffusion models, retrieval augmented generation..."
                : "search titles, abstracts, and full text of papers you've ingested..."
            }
            className="input-field pl-11"
          />
        </div>
        <button type="submit" disabled={searching} className="btn-primary">
          {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <SearchIcon className="h-4 w-4" />}
          Search
        </button>
      </form>

      {error && <div className="glass-panel p-4 text-sm text-discovery">{error}</div>}

      {tab === "library" && (
        <AnimatePresence>
          {libraryResults.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-2">
              {libraryResults.map((r) => (
                <Link
                  key={r.paper_id}
                  href={`/papers/${r.paper_id}`}
                  className="glass-panel p-4 flex items-center justify-between hover:border-phosphor/30"
                >
                  <span className="text-sm text-ink">{r.title}</span>
                  <span className="pill">score {r.score.toFixed(2)}</span>
                </Link>
              ))}
            </motion.div>
          )}
          {!searching && libraryResults.length === 0 && query && (
            <p className="text-sm text-ink-faint">No matches in your ingested library yet.</p>
          )}
        </AnimatePresence>
      )}

      {tab === "discover" && (
        <AnimatePresence>
          {results.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-3">
              {results.map((r) => {
                const key = `${r.source}:${r.source_id}`;
                const state = r.arxiv_id ? ingestStates[r.arxiv_id] ?? "idle" : "idle";
                return (
                  <motion.div
                    key={key}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="glass-panel p-5"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <h3 className="font-display text-lg text-ink mb-1">{r.title}</h3>
                        <p className="text-xs text-ink-muted mb-2">
                          {r.authors.slice(0, 4).join(", ")}
                          {r.authors.length > 4 ? ", et al." : ""}
                          {r.venue ? ` · ${r.venue}` : ""}
                          {r.year ? ` · ${r.year}` : ""}
                          {r.citation_count !== null ? ` · ${r.citation_count.toLocaleString()} citations` : ""}
                        </p>
                        <p className="text-sm text-ink-muted leading-relaxed line-clamp-3">{r.abstract}</p>
                        <span className="pill mt-2 inline-flex">{SOURCE_LABEL[r.source] ?? r.source}</span>
                      </div>
                      <div className="flex flex-col gap-2 shrink-0">
                        {r.arxiv_id ? (
                          <button
                            onClick={() => handleIngest(r.arxiv_id!)}
                            disabled={state === "loading" || state === "done"}
                            className="btn-secondary whitespace-nowrap"
                          >
                            {state === "loading" && <Loader2 className="h-4 w-4 animate-spin" />}
                            {state === "done" && <CheckCircle2 className="h-4 w-4 text-phosphor" />}
                            {state === "idle" && <Download className="h-4 w-4" />}
                            {state === "done" ? "Ingested" : state === "loading" ? "Ingesting..." : "Ingest"}
                          </button>
                        ) : (
                          <span className="text-xs text-ink-faint text-center max-w-[8rem]">
                            No arXiv PDF available to ingest
                          </span>
                        )}
                        {r.pdf_url && (
                          <a
                            href={r.pdf_url}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center justify-center gap-1.5 text-xs text-ink-muted hover:text-phosphor"
                          >
                            PDF <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                        {state === "error" && <span className="text-xs text-red-400 text-center">Ingest failed</span>}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}
