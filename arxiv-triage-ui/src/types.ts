export interface Paper {
  id: number;
  arxiv_id: string;
  version: number;
  title: string;
  authors: string;
  abstract: string;
  categories: string;
  primary_category: string;
  submitted_at?: string;
  updated_at?: string;
  links_pdf?: string;
  links_html?: string;
  links_abs?: string;
  tags?: { list?: string[] } | null;
  signals?: {
    rubric?: Rubric;
    suggested_tags?: string[];
    [k: string]: any;
  } | null;
  state: "triage" | "shortlist" | "archived" | "hidden";
}

export interface ListResp { ok: boolean; data: Paper[]; total: number }

export interface StatsResp {
  ok: boolean;
  total: number;
  categories: Record<string, number>;
  tags: Record<string, number>;
  empty_tag_count: number;
}

export interface Rubric {
  novelty: number;
  evidence: number;
  clarity: number;
  reusability: number;
  fit: number;
  total: number;
}

export interface HistoResp {
  ok: boolean;
  counts: Record<string, number>;
}
