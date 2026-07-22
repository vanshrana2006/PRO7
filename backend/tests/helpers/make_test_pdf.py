"""Generates a real, on-disk PDF that mimics a research paper's structure,
so pdf_extractor can be tested against an actual PDF file rather than mocks.
"""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

PAPER_CONTENT = {
    "Abstract": (
        "This paper introduces a novel approach to graph representation "
        "learning that outperforms prior baselines on standard benchmarks."
    ),
    "1. Introduction": (
        "Graph neural networks have become a central tool in machine "
        "learning for structured data. Prior work has established strong "
        "baselines, but scalability remains an open problem."
    ),
    "2. Related Work": (
        "Kipf and Welling proposed graph convolutional networks. "
        "Velickovic et al. proposed graph attention mechanisms."
    ),
    "3. Methodology": (
        "We propose a hybrid message-passing scheme combining attention "
        "and convolution operators, trained with a contrastive objective."
    ),
    "4. Experiments": (
        "We evaluate on Cora, Citeseer, and PubMed, following the standard "
        "transductive split used in prior benchmarks."
    ),
    "5. Results": (
        "Our method achieves 84.2 percent accuracy on Cora, a 2.1 point "
        "improvement over the strongest baseline."
    ),
    "6. Limitations": (
        "Our approach assumes a static graph structure and does not "
        "directly handle dynamic or streaming graphs."
    ),
    "7. Conclusion": (
        "We presented a new graph learning method with strong empirical "
        "results and discussed its current limitations."
    ),
    "References": (
        "[1] Kipf, T. and Welling, M. Semi-Supervised Classification with "
        "Graph Convolutional Networks. 2017.\n"
        "[2] Velickovic, P. et al. Graph Attention Networks. 2018.\n"
        "[3] Hamilton, W. et al. Inductive Representation Learning on Large "
        "Graphs. 2017."
    ),
}


def build_test_pdf(path: str) -> None:
    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter

    for heading, body in PAPER_CONTENT.items():
        y = height - 72
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, heading)
        y -= 24
        c.setFont("Helvetica", 10)
        for line in _wrap(body, 90):
            c.drawString(72, y, line)
            y -= 14
        c.showPage()
    c.save()


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for raw_line in text.split("\n"):
        words = raw_line.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines
