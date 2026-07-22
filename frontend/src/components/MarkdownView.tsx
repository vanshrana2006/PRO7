import React from "react";

/**
 * Renders the specific, limited Markdown subset our own backend produces
 * (survey_templates.py / the LLM survey prompt): #/##/### headings, **bold**,
 * "- " list items, and blank-line-separated paragraphs. Not a general
 * Markdown parser -- deliberately narrow so it has no external dependency
 * and no surprising edge cases on content we don't control.
 */
function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={`${keyPrefix}-${i}`} className="font-semibold text-ink">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={`${keyPrefix}-${i}`}>{part}</React.Fragment>;
  });
}

export function MarkdownView({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let listBuffer: string[] = [];

  const flushList = (key: string) => {
    if (listBuffer.length > 0) {
      elements.push(
        <ul key={key} className="list-disc list-inside space-y-1 text-ink-muted mb-4 ml-1">
          {listBuffer.map((item, i) => (
            <li key={i}>{renderInline(item, `${key}-li-${i}`)}</li>
          ))}
        </ul>,
      );
      listBuffer = [];
    }
  };

  lines.forEach((line, idx) => {
    const key = `line-${idx}`;
    if (line.startsWith("### ")) {
      flushList(`${key}-flush`);
      elements.push(
        <h3 key={key} className="font-display text-lg text-ink mt-6 mb-2">
          {renderInline(line.slice(4), key)}
        </h3>,
      );
    } else if (line.startsWith("## ")) {
      flushList(`${key}-flush`);
      elements.push(
        <h2 key={key} className="font-display text-xl text-ink mt-8 mb-3 border-b border-glass-border pb-2">
          {renderInline(line.slice(3), key)}
        </h2>,
      );
    } else if (line.startsWith("# ")) {
      flushList(`${key}-flush`);
      elements.push(
        <h1 key={key} className="font-display text-2xl text-ink mb-4">
          {renderInline(line.slice(2), key)}
        </h1>,
      );
    } else if (line.startsWith("- ")) {
      listBuffer.push(line.slice(2));
    } else if (line.trim() === "") {
      flushList(`${key}-flush`);
    } else {
      flushList(`${key}-flush`);
      elements.push(
        <p key={key} className="text-ink-muted leading-relaxed mb-3">
          {renderInline(line, key)}
        </p>,
      );
    }
  });
  flushList("final-flush");

  return <div className="font-sans text-sm">{elements}</div>;
}
