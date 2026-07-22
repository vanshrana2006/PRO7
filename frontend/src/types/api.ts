export interface Author {
  id: string;
  name: string;
  affiliation: string | null;
}

export interface PaperSection {
  id: string;
  heading: string;
  section_type: string;
  order_index: number;
  page_start: number | null;
  page_end: number | null;
  content: string;
}

export interface PaperReference {
  id: string;
  raw_text: string;
  parsed_title: string | null;
  parsed_year: number | null;
  parsed_authors: string | null;
}

export interface PaperSummary {
  id: string;
  arxiv_id: string | null;
  title: string;
  abstract: string | null;
  authors: Author[];
  published_at: string | null;
  primary_category: string | null;
  pdf_url: string | null;
  extraction_status: string;
}

export interface PaperDetail extends PaperSummary {
  full_text: string | null;
  num_pages: number | null;
  sections: PaperSection[];
  references: PaperReference[];
  extraction_error: string | null;
}

export interface UnifiedSearchResult {
  source: "arxiv" | "semantic_scholar";
  source_id: string;
  arxiv_id: string | null;
  title: string;
  abstract: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  citation_count: number | null;
  pdf_url: string | null;
}

export interface IngestResponse {
  paper_id: string;
  status: string;
  message: string;
}

export interface GraphNode {
  id: string;
  type: string;
  name: string;
  confidence: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  evidence: string | null;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ExtractResponse {
  paper_id: string;
  method_used: string;
  entities_created: number;
  relationships_created: number;
}

export interface KnowledgeSummary {
  paper_id: string;
  paper_title: string;
  year: number | null;
  entities_created: number;
  relationships_created: number;
  method_used: string;
  methods: string[];
  datasets: string[];
  claims: string[];
}

export interface AgentResultOut {
  agent: string;
  success: boolean;
  summary: string;
}

export interface Contradiction {
  dataset: string;
  spread: number;
  figures: { paper_title: string; dataset: string; value: number; raw_claim: string }[];
}

export interface ResearchGap {
  kind: string;
  subject: string;
  detail: string;
}

export interface NoveltyAssessment {
  method_name: string;
  paper_title: string;
  novelty_score: number;
  similar_to: string[];
}

export interface TimelinePoint {
  paper_title: string;
  year: number;
  dataset: string;
  value: number;
  raw_claim: string;
}

export interface BenchmarkTimeline {
  dataset: string;
  points: TimelinePoint[];
  improved: boolean;
}

export interface PaperAnalysis {
  paper_id: string;
  paper_title: string;
  novelty_score: number | null;
  impact_score: number;
  evidence_density: number;
  key_contributions: string[];
  summary: string;
}

export interface MissingCitation {
  citing_paper_title: string;
  concept: string;
  concept_type: string;
  likely_source_paper: string;
  reason: string;
}

export interface PaperRecommendation {
  paper_title: string;
  recommended_paper_title: string;
  shared_concepts: string[];
  score: number;
}

export interface ResearchRunResponse {
  query: string;
  discovered_count: number;
  ingested_count: number;
  knowledge: KnowledgeSummary[];
  contradictions: Contradiction[];
  gaps: ResearchGap[];
  novelty: NoveltyAssessment[];
  timelines: BenchmarkTimeline[];
  analyses: PaperAnalysis[];
  missing_citations: MissingCitation[];
  recommendations: Record<string, PaperRecommendation[]>;
  survey_markdown: string;
  agent_results: AgentResultOut[];
  log: string[];
}

export interface CorpusSearchResult {
  paper_id: string;
  title: string;
  score: number;
}

export interface CorpusSearchResponse {
  query: string;
  results: CorpusSearchResult[];
}
