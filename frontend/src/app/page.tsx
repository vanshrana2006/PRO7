import Link from "next/link";
import { ArrowRight, FileText, Network, Sparkles } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { PaperSummary } from "@/types/api";
import { PaperCard } from "@/components/PaperCard";

async function getRecentPapers(): Promise<{ papers: PaperSummary[]; error: string | null }> {
  try {
    const papers = await api.listPapers(6, 0);
    return { papers, error: null };
  } catch (err) {
    const message = err instanceof ApiError ? err.message : "Could not reach the backend API.";
    return { papers: [], error: message };
  }
}

export default async function DashboardPage() {
  const { papers, error } = await getRecentPapers();

  return (
    <div className="flex flex-col gap-14">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl glass-panel px-8 py-14 sm:px-14">
        <p className="eyebrow mb-4">The Autonomous AI Scientist</p>
        <h1 className="font-display text-4xl sm:text-5xl leading-tight text-ink max-w-2xl">
          Every paper is a star.
          <br />
          <span className="italic text-phosphor">The graph is the map.</span>
        </h1>
        <p className="mt-5 max-w-xl text-ink-muted leading-relaxed">
          AI ResearchOS discovers papers on arXiv, reads them structurally, extracts methods,
          datasets, and claims, and connects them into a living knowledge graph — then writes the
          literature review for you.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/research" className="btn-primary">
            <Sparkles className="h-4 w-4" />
            Run autonomous research
          </Link>
          <Link href="/search" className="btn-secondary">
            Discover papers
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* Feature strip -- grounded in the real pipeline stages, not generic icons */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          {
            icon: FileText,
            title: "Read structurally",
            desc: "PDFs are parsed into sections, references, and claims — not flattened into plain text.",
          },
          {
            icon: Network,
            title: "Build the graph",
            desc: "Methods, datasets, and metrics are linked into a shared, cross-paper knowledge graph.",
          },
          {
            icon: Sparkles,
            title: "Synthesize findings",
            desc: "A literature review is generated from extracted, evidence-grounded facts.",
          },
        ].map(({ icon: Icon, title, desc }) => (
          <div key={title} className="glass-panel p-6">
            <Icon className="h-5 w-5 text-phosphor mb-3" />
            <h3 className="font-display text-lg text-ink mb-1.5">{title}</h3>
            <p className="text-sm text-ink-muted leading-relaxed">{desc}</p>
          </div>
        ))}
      </section>

      {/* Recent papers */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-2xl text-ink">Recently ingested</h2>
          <Link href="/search" className="text-sm text-phosphor hover:underline">
            Discover more →
          </Link>
        </div>

        {error && (
          <div className="glass-panel p-6 text-sm text-discovery">
            Couldn&apos;t load papers from the API: {error}. Make sure the backend is running (see
            README).
          </div>
        )}

        {!error && papers.length === 0 && (
          <div className="glass-panel p-8 text-center">
            <p className="text-ink-muted">
              No papers ingested yet. Start with{" "}
              <Link href="/search" className="text-phosphor hover:underline">
                Discover
              </Link>{" "}
              or run the{" "}
              <Link href="/research" className="text-phosphor hover:underline">
                autonomous pipeline
              </Link>
              .
            </p>
          </div>
        )}

        {papers.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {papers.map((paper) => (
              <PaperCard key={paper.id} paper={paper} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
