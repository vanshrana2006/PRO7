import type {
  CorpusSearchResponse,
  ExtractResponse,
  GraphResponse,
  IngestResponse,
  PaperDetail,
  PaperSummary,
  UnifiedSearchResult,
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new ApiError(detail, res.status);
  }

  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; service: string; phase: number }>("/api/health"),

  discover: (q: string, maxResults = 20, sources = "arxiv,semantic_scholar") =>
    request<UnifiedSearchResult[]>(
      `/api/papers/discover?q=${encodeURIComponent(q)}&max_results=${maxResults}&sources=${encodeURIComponent(sources)}`,
    ),

  ingestPaper: (arxivId: string) =>
    request<IngestResponse>("/api/papers/ingest", {
      method: "POST",
      body: JSON.stringify({ arxiv_id: arxivId }),
    }),

  listPapers: (limit = 50, offset = 0) =>
    request<PaperSummary[]>(`/api/papers?limit=${limit}&offset=${offset}`),

  corpusSearch: (q: string, topK = 10) =>
    request<CorpusSearchResponse>(`/api/papers/corpus-search?q=${encodeURIComponent(q)}&top_k=${topK}`),

  getPaper: (paperId: string) => request<PaperDetail>(`/api/papers/${paperId}`),

  extractKnowledge: (paperId: string) =>
    request<ExtractResponse>(`/api/knowledge/extract/${paperId}`, { method: "POST" }),

  getGraph: (paperId: string) => request<GraphResponse>(`/api/knowledge/graph/${paperId}`),

  /** Builds the URL for the SSE streaming endpoint -- consumed directly
   * via `new EventSource(url)`, not through the shared `request()`
   * helper above, since EventSource manages its own connection/parsing. */
  researchStreamUrl: (query: string, maxPapers = 5) =>
    `${API_BASE}/api/research/run/stream?query=${encodeURIComponent(query)}&max_papers=${maxPapers}`,
};

export { ApiError };
