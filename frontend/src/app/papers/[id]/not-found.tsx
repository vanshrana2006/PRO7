import Link from "next/link";

export default function PaperNotFound() {
  return (
    <div className="glass-panel p-12 text-center">
      <p className="eyebrow mb-3">404</p>
      <h1 className="font-display text-2xl text-ink mb-3">This paper isn&apos;t in the graph yet</h1>
      <p className="text-ink-muted mb-6">It may not have been ingested, or the link is out of date.</p>
      <Link href="/search" className="btn-primary inline-flex">
        Discover papers
      </Link>
    </div>
  );
}
