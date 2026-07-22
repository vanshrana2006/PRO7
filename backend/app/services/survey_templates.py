"""
Template-based literature review generation -- the no-API-key fallback for
SurveyAgent. Pure string-building logic, zero dependencies, fully testable
offline (see tests/test_survey_templates.py).

Produces a structured Markdown summary from the knowledge already extracted
by ExtractionAgent: not prose written by a model, but a genuinely useful,
accurate roundup grounded entirely in extracted facts -- every line traces
to a real paper/entity, nothing is invented. The LLM path (survey_agent.py)
produces actual synthesized prose when a key is present.
"""
from __future__ import annotations


def generate_template_survey(query: str, knowledge_summaries: list[dict]) -> str:
    if not knowledge_summaries:
        return (
            f"# Literature Review: {query}\n\n"
            "No papers were successfully ingested and extracted for this query, "
            "so no review could be generated."
        )

    lines = [f"# Literature Review: {query}", ""]
    lines.append(
        f"This review covers {len(knowledge_summaries)} paper(s) discovered and "
        f"analyzed for the query \"{query}\"."
    )
    lines.append("")

    all_methods = sorted({m for k in knowledge_summaries for m in k.get("methods", [])})
    all_datasets = sorted({d for k in knowledge_summaries for d in k.get("datasets", [])})

    if all_methods:
        lines.append("## Methods Identified")
        for m in all_methods:
            lines.append(f"- {m}")
        lines.append("")

    if all_datasets:
        lines.append("## Datasets Used")
        for d in all_datasets:
            lines.append(f"- {d}")
        lines.append("")

    lines.append("## Per-Paper Summary")
    for k in knowledge_summaries:
        lines.append(f"### {k['paper_title']}")
        if k.get("methods"):
            lines.append(f"**Proposes:** {', '.join(k['methods'])}")
        if k.get("datasets"):
            lines.append(f"**Evaluated on:** {', '.join(k['datasets'])}")
        if k.get("claims"):
            lines.append("**Key claims:**")
            for c in k["claims"][:3]:
                lines.append(f"- {c}")
        lines.append("")

    return "\n".join(lines)
