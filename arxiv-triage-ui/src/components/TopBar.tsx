import React from "react";
import { cls } from "../utils";
import type { Paper } from "../types";

type Props = {
  query: string;
  setQuery: (v: string) => void;
  state: Paper["state"] | "";
  setStateFilter: (s: Paper["state"] | "") => void;
  refresh: () => void;
  fetchById?: (id: string) => void;
  quickFilters: string[];
  toggleFilter: (f: string) => void;
  selectedTag?: string;
  onCreateTag?: (t: string) => void;
  notesOnly?: boolean;
  setNotesOnly?: (v: boolean) => void;
};

export default function TopBar({ query, setQuery, state, setStateFilter, refresh, fetchById, quickFilters, toggleFilter, selectedTag, onCreateTag, notesOnly=false, setNotesOnly }: Props) {
  const [newTag, setNewTag] = React.useState("");
  const tabs: { key: Paper["state"] | ""; label: string }[] = [
    { key: "", label: "All#1" },
    { key: "triage", label: "Triage#2" },
    { key: "further_read", label: "Further‑Read#3" },
    { key: "archived", label: "Archived#4" },
    { key: "must_read", label: "Must‑Read#5" },
  ];
  return (
    <div className="sticky top-0 z-20 bg-white/90 backdrop-blur border-b">
      <div className="max-w-7xl mx-auto px-4 py-2 flex items-center gap-3">
        <div className="hidden sm:flex gap-1">
          {tabs.map(t => (
            <button key={t.key}
              onClick={() => setStateFilter(t.key)}
              className={cls("px-3 py-1.5 rounded-xl border", state===t.key?"bg-gray-900 text-white border-gray-900":"bg-white hover:bg-gray-50")}
            >{t.label}</button>
          ))}
          <button
            onClick={() => setNotesOnly?.(!notesOnly)}
            className={cls("px-3 py-1.5 rounded-xl border", notesOnly?"bg-gray-900 text-white border-gray-900":"bg-white hover:bg-gray-50")}
            title="Show only papers with notes"
          >Notes#0</button>
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="/ search title or abstract"
          className="w-full max-w-xl rounded-2xl border px-3 py-2 focus:outline-none focus:ring"
        />
        <button onClick={refresh} className="rounded-xl border px-3 py-2 hover:bg-gray-50 ml-auto">Refresh</button>
        <button
          className="rounded-xl border px-3 py-2 hover:bg-gray-50"
          onClick={() => {
            const m = (query || '').match(/^\d{4}\.\d{4,5}(?:v\d+)?$/);
            if (m) fetchById?.((query || '').replace(/v\d+$/, ''));
          }}
          title="Fetch paper by arXiv ID"
        >Fetch ID</button>
      </div>
      <div className="max-w-7xl mx-auto px-4 pb-2 flex flex-wrap gap-2 items-center">
        <span className="text-xs text-gray-500 mr-1">Tags:</span>
        <input
          value={newTag}
          onChange={(e)=>setNewTag(e.target.value)}
          onKeyDown={(e)=>{ if (e.key==='Enter' && newTag.trim()) { onCreateTag?.(newTag.trim()); setNewTag(""); } }}
          placeholder="New tag"
          className="text-xs border rounded px-2 py-1 w-28 mr-2"
        />
        {quickFilters.map((qf) => {
          const isEmpty = qf === "empty";
          return (
            <button
              key={qf}
              onClick={() => toggleFilter(qf)}
              draggable={!isEmpty}
              onDragStart={(e)=>{ if (!isEmpty) { try{ e.dataTransfer.setData('text/plain', qf); }catch{} } }}
              className={cls(
                "px-2 py-1 rounded-full border text-xs",
                isEmpty ? "text-red-600 border-red-300 bg-red-50" : "",
                selectedTag === qf && !isEmpty ? "bg-gray-900 text-white border-gray-900" : (!isEmpty ? "hover:bg-gray-50" : "")
              )}
              title={isEmpty ? "Show papers without tags" : undefined}
            >
              {isEmpty ? "empty" : `#${qf}`}
            </button>
          );
        })}
      </div>
    </div>
  );
}
