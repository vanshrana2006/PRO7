"""
Heuristic scientific knowledge extraction -- pure logic, zero DB or network
dependency, so it's fully unit-testable offline (see
tests/test_knowledge_extraction.py).

This is the extraction path that runs with NO API key. It recognizes:
  * Datasets    -- matched against a curated list of common ML/NLP/CV
                   benchmark dataset names (extendable).
  * Metrics     -- matched against a curated list of common evaluation
                   metric names.
  * Methods     -- "we propose/introduce/present <Name>" patterns in the
                   methodology/introduction sections.
  * Claims      -- sentences in the results section containing a
                   percentage or point-improvement figure.

An LLM-refinement pass (app/services/llm_extractor.py) sits behind the same
output shape (ExtractedEntity/ExtractedRelationship) and is used instead of
-- not in addition to -- this heuristic pass when an API key is available,
so callers never have to reconcile two disagreeing extractions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# A deliberately curated, extendable list rather than an attempt at
# exhaustive coverage -- precision over recall for the no-LLM path.
KNOWN_DATASETS = [
    "Cora", "Citeseer", "PubMed", "Reddit", "PPI",
    "ImageNet", "CIFAR-10", "CIFAR-100", "MNIST", "Fashion-MNIST",
    "COCO", "Pascal VOC", "ADE20K", "Cityscapes",
    "SQuAD", "GLUE", "SuperGLUE", "WikiText", "WikiText-2", "WikiText-103",
    "Penn Treebank", "CoNLL-2003", "OntoNotes",
    "MS MARCO", "Natural Questions", "TriviaQA", "HotpotQA",
    "LibriSpeech", "CommonVoice", "AudioSet",
    "OGB", "OGB-Arxiv", "OGB-Products", "ogbn-arxiv",
    "WordNet", "FB15k", "FB15k-237", "WN18", "WN18RR",
]

KNOWN_METRICS = [
    "accuracy", "precision", "recall", "F1", "F1-score", "F1 score",
    "AUC", "AUROC", "mAP", "mean average precision",
    "BLEU", "ROUGE", "ROUGE-L", "METEOR", "perplexity",
    "MSE", "RMSE", "MAE", "R2", "top-1 accuracy", "top-5 accuracy",
    "NDCG", "MRR", "hit rate", "hits@1", "hits@10",
]

_METHOD_PATTERNS = [
    re.compile(r"(?i:we propose)\s+(?:a\s+|an\s+|the\s+)?([A-Z][A-Za-z0-9\-]*(?:\s+[A-Z][A-Za-z0-9\-]*){0,4})"),
    re.compile(r"(?i:we introduce)\s+(?:a\s+|an\s+|the\s+)?([A-Z][A-Za-z0-9\-]*(?:\s+[A-Z][A-Za-z0-9\-]*){0,4})"),
    re.compile(r"(?i:we present)\s+(?:a\s+|an\s+|the\s+)?([A-Z][A-Za-z0-9\-]*(?:\s+[A-Z][A-Za-z0-9\-]*){0,4})"),
]

_CLAIM_NUMBER_PATTERN = re.compile(
    r"\b\d{1,3}(?:\.\d+)?\s*(?:%|percent\b|points?\b|pp\b)", re.IGNORECASE
)


@dataclass
class ExtractedEntity:
    entity_type: str  # method | dataset | metric | claim
    name: str
    description: str | None = None
    extraction_method: str = "heuristic"
    confidence: float = 0.6


@dataclass
class ExtractedRelationship:
    source_name: str
    target_name: str
    relationship_type: str
    evidence: str | None = None
    confidence: float = 0.6


@dataclass
class ExtractionOutput:
    entities: list[ExtractedEntity] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)


def _find_datasets(text: str) -> list[str]:
    found = set()
    for name in KNOWN_DATASETS:
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        if pattern.search(text):
            found.add(name)
    return sorted(found)


def _find_metrics(text: str) -> list[str]:
    found = set()
    for name in KNOWN_METRICS:
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        if pattern.search(text):
            found.add(name)
    return sorted(found)


def _find_methods(text: str) -> list[str]:
    found: list[str] = []
    for pattern in _METHOD_PATTERNS:
        for match in pattern.finditer(text):
            candidate = match.group(1).strip()
            # Filter out generic non-names ("a new approach" etc slipped
            # through despite the [A-Z] anchor if mid-sentence capitalized).
            if len(candidate.split()) <= 6 and candidate not in found:
                found.append(candidate)
    return found


def _find_claim_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if _CLAIM_NUMBER_PATTERN.search(s)]


def extract_from_sections(sections: dict[str, str], paper_title: str) -> ExtractionOutput:
    """`sections` maps section_type -> concatenated content, e.g.
    {'methodology': '...', 'experiments': '...', 'results': '...'}.
    Missing keys are treated as empty strings.
    """
    methodology_text = sections.get("methodology", "") + " " + sections.get("introduction", "")
    experiments_text = sections.get("experiments", "") + " " + sections.get("results", "")
    full_text = " ".join(sections.values())

    output = ExtractionOutput()

    methods = _find_methods(methodology_text)
    for method_name in methods:
        output.entities.append(ExtractedEntity(entity_type="method", name=method_name))
        output.relationships.append(
            ExtractedRelationship(
                source_name=paper_title,
                target_name=method_name,
                relationship_type="proposes",
                evidence=f"'we propose/introduce/present {method_name}' found in text",
            )
        )

    datasets = _find_datasets(full_text)
    for ds in datasets:
        output.entities.append(ExtractedEntity(entity_type="dataset", name=ds))
        output.relationships.append(
            ExtractedRelationship(
                source_name=paper_title,
                target_name=ds,
                relationship_type="evaluated_on",
                evidence=f"'{ds}' mentioned in paper text",
            )
        )

    metrics = _find_metrics(experiments_text or full_text)
    for m in metrics:
        output.entities.append(ExtractedEntity(entity_type="metric", name=m))
        output.relationships.append(
            ExtractedRelationship(
                source_name=paper_title,
                target_name=m,
                relationship_type="mentions",
                evidence=f"'{m}' mentioned in experiments/results",
            )
        )

    claim_sentences = _find_claim_sentences(sections.get("results", "") or experiments_text)
    for i, sentence in enumerate(claim_sentences):
        claim_name = f"{paper_title} — claim {i + 1}"
        output.entities.append(
            ExtractedEntity(entity_type="claim", name=claim_name, description=sentence)
        )
        output.relationships.append(
            ExtractedRelationship(
                source_name=paper_title,
                target_name=claim_name,
                relationship_type="mentions",
                evidence=sentence,
            )
        )

    return output
