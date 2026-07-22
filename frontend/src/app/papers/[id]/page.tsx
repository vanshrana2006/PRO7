import { notFound } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { ExtractPanel } from "@/components/ExtractPanel";

export default async function PaperDetailPage({ params }: { params: { id: string } }) {
  let paper;
  try {
    paper = await api.getPaper(params.id);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="eyebrow mb-3">{paper.primary_category || "Paper"}</p>
        <h1 className="font-display text-3xl text-ink leading-tight mb-3">{paper.title}</h1>
        {paper.authors.length > 0 && (
          <p className="text-ink-muted mb-2">{paper.authors.map((a) => a.name).join(", ")}</p>
        )}
        <div className="flex flex-wrap gap-2">
          {paper.arxiv_id && <span className="pill">arXiv:{paper.arxiv_id}</span>}
          {paper.num_pages && <span className="pill">{paper.num_pages} pages</span>}
          <span className="pill">{paper.extraction_status}</span>
        </div>
      </div>

      {paper.abstract && (
        <div className="glass-panel p-6">
          <h2 className="font-display text-lg text-ink mb-2">Abstract</h2>
          <p className="text-ink-muted leading-relaxed">{paper.abstract}</p>
        </div>
      )}

      {paper.extraction_status === "completed" && <ExtractPanel paperId={paper.id} />}

      {paper.extraction_status === "failed" && paper.extraction_error && (
        <div className="glass-panel p-6 text-sm text-discovery">
          Extraction failed: {paper.extraction_error}
        </div>
      )}

      {paper.sections.length > 0 && (
        <div>
          <h2 className="font-display text-2xl text-ink mb-4">Sections</h2>
          <div className="flex flex-col gap-3">
            {paper.sections
              .filter((s) => s.section_type !== "references")
              .map((section) => (
                <details key={section.id} className="glass-panel p-5 group">
                  <summary className="cursor-pointer font-display text-base text-ink flex items-center justify-between">
                    {section.heading}
                    <span className="pill capitalize">{section.section_type.replace("_", " ")}</span>
                  </summary>
                  <p className="text-sm text-ink-muted leading-relaxed mt-3 whitespace-pre-line">
                    {section.content.slice(0, 2000)}
                    {section.content.length > 2000 ? "…" : ""}
                  </p>
                </details>
              ))}
          </div>
        </div>
      )}

      {paper.references.length > 0 && (
        <div>
          <h2 className="font-display text-2xl text-ink mb-4">
            References <span className="text-ink-faint text-base">({paper.references.length})</span>
          </h2>
          <div className="glass-panel p-5 flex flex-col gap-2">
            {paper.references.map((ref) => (
              <p key={ref.id} className="text-sm text-ink-muted leading-relaxed">
                {ref.parsed_year && <span className="text-phosphor font-mono text-xs mr-2">{ref.parsed_year}</span>}
                {ref.raw_text}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
