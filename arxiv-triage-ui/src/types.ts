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
  signals?: Record<string, any> | null;
  state: "triage" | "shortlist" | "archived" | "hidden";
}

export interface ListResp { ok: boolean; data: Paper[]; total: number }

