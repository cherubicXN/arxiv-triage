import React, { useEffect, useMemo, useState } from "react";
import TopBar from "./components/TopBar";
import PaperRow from "./components/PaperRow";
import DetailsDrawer from "./components/DetailsDrawer";
import CategoryBar from "./components/CategoryBar";
import type { Paper, ListResp } from "./types";
// utils imported by components where needed

/**
 * ArXiv Triage UI — v2
 * ---------------------------------------------------------
 * Layout upgrades:
 *  - Top app bar with state tabs + search + quick filters
 *  - Two-pane triage: List (left 2/3) + Details Drawer (right) on desktop
 *  - Right sidebar becomes collapsible on mobile
 *  - Batch selection toolbar for shortlist/archive/tag
 *  - Inline tag editor
 *  - Sticky load-more/footer actions
 */

// ==== Config / Utilities ====
// (cls, timeAgo moved to ./utils)
const API_BASE = (import.meta as any)?.env?.VITE_ARX_API ||
  (typeof process !== "undefined" ? (process as any).env?.NEXT_PUBLIC_ARX_API : null) ||
  "http://localhost:8787";

function useDebounced<T>(value: T, ms = 300) {
  const [deb, setDeb] = useState(value);
  useEffect(() => { const t = setTimeout(() => setDeb(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return deb;
}

// ==== API ====
async function fetchPapers({ state, query, page, pageSize }: { state?: string; query?: string; page: number; pageSize: number; }): Promise<ListResp> {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  if (state) params.set("state", state);
  if (query) params.set("query", query);
  const r = await fetch(`${API_BASE}/v1/papers?${params.toString()}`);
  if (!r.ok) throw new Error(`fetchPapers: ${r.status}`);
  return r.json();
}

async function setState(paperId: number, state: Paper["state"]) {
  const r = await fetch(`${API_BASE}/v1/papers/${paperId}/state`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  });
  if (!r.ok) throw new Error(`setState: ${r.status}`);
  return r.json();
}

async function addTags(paperId: number, tags: string[]) {
  const r = await fetch(`${API_BASE}/v1/papers/${paperId}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ add: tags }),
  });
  if (!r.ok) throw new Error(`tags: ${r.status}`);
  return r.json();
}

async function removeTags(paperId: number, tags: string[]) {
  const r = await fetch(`${API_BASE}/v1/papers/${paperId}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ remove: tags }),
  });
  if (!r.ok) throw new Error(`tags-remove: ${r.status}`);
  return r.json();
}

export default function App() {
  const [query, setQuery] = useState("");
  const q = useDebounced(query, 250);
  const [stateFilter, setStateFilter] = useState<Paper["state"]|"">("triage");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(40);
  const [items, setItems] = useState<Paper[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<Paper|null>(null);
  const [checked, setChecked] = useState<Record<number, boolean>>({});
  const [category, setCategory] = useState<string | "">("");
  const [selectedTag, setSelectedTag] = useState<string | "">("");
  const [userTags, setUserTags] = useState<string[]>([]);
  const [isBatchDragOver, setIsBatchDragOver] = useState(false);

  async function load(reset = false) {
    try {
      setLoading(true); setError(null);
      const res = await fetchPapers({ state: stateFilter || undefined, query: q || undefined, page, pageSize });
      setTotal(res.total);
      setItems(reset ? res.data : [...items, ...res.data]);
      if (reset) setChecked({});
    } catch (e: any) {
      setError(e.message || String(e));
    } finally { setLoading(false); }
  }

  useEffect(() => { setPage(1); load(true); /* eslint-disable-next-line */ }, [q, stateFilter]);
  useEffect(() => { if (page > 1) load(false); /* eslint-disable-next-line */ }, [page]);

  function refresh() { setPage(1); load(true); }

  async function mutate(paperId: number, newState: Paper["state"]) {
    await setState(paperId, newState);
    setItems((prev) => prev.filter((p) => p.id !== paperId));
    setChecked((m)=>{ const n={...m}; delete n[paperId]; return n; });
  }

  async function tagAdd(paperId: number, t: string) {
    // Optimistic update first
    setItems((prev) => prev.map((p) => p.id === paperId ? { ...p, tags: { list: Array.from(new Set([...(p.tags?.list || []), t])) } } : p));
    try {
      await addTags(paperId, [t]);
    } catch (e: any) {
      // Revert on failure and surface error
      setItems((prev) => prev.map((p) => p.id === paperId ? { ...p, tags: { list: (p.tags?.list || []).filter(x=>x!==t) } } : p));
      setError(e?.message || 'Failed to add tag');
    }
  }
  async function tagRemove(paperId: number, t: string) {
    // Optimistic remove
    setItems((prev) => prev.map((p) => p.id === paperId ? { ...p, tags: { list: (p.tags?.list || []).filter(x=>x!==t) } } : p));
    try {
      await removeTags(paperId, [t]);
    } catch (e: any) {
      // Revert on failure and surface error
      setItems((prev) => prev.map((p) => p.id === paperId ? { ...p, tags: { list: Array.from(new Set([...(p.tags?.list || []), t])) } } : p));
      setError(e?.message || 'Failed to remove tag');
    }
  }

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.target as HTMLElement)?.tagName === 'INPUT' || (e.target as HTMLElement)?.tagName === 'TEXTAREA') return;
      if (e.key === "/") { e.preventDefault(); const inp = document.querySelector<HTMLInputElement>("input"); inp?.focus(); return; }
      if (e.key === "Escape") setDrawer(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Derived
  const anyChecked = useMemo(()=> Object.values(checked).some(Boolean), [checked]);
  const selectedIds = useMemo(()=> Object.keys(checked).filter(k=>checked[Number(k)]).map(Number), [checked]);

  // Category clusters (brief)
  const byCat = useMemo(() => {
    const m = new Map<string, Paper[]>();
    for (const p of items) {
      const k = p.primary_category || "unknown";
      m.set(k, [...(m.get(k) || []), p]);
    }
    return Array.from(m.entries());
  }, [items]);

  const categoryOptions = useMemo(() => {
    // Build category list with counts from current items
    return byCat
      .map(([name, arr]) => ({ name, count: arr.length }))
      .sort((a, b) => b.count - a.count);
  }, [byCat]);

  // Tag counts and palette (auto-remove tags with zero association)
  const tagCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const p of items) {
      for (const t of p.tags?.list || []) {
        m.set(t, (m.get(t) || 0) + 1);
      }
    }
    return m;
  }, [items]);

  // Cleanup user-only tags that are not associated with any paper
  useEffect(() => {
    setUserTags((prev) => prev.filter((t) => (tagCounts.get(t) || 0) > 0));
  }, [tagCounts]);

  const paletteTags = useMemo(() => {
    const used = Array.from(tagCounts.keys());
    return Array.from(new Set(["empty", ...used, ...userTags]));
  }, [tagCounts, userTags]);

  // Toggle tag filter (client-side)
  const toggleFilter = (t: string) => setSelectedTag((prev) => prev === t ? "" : t);

  const visibleItems = useMemo(() => {
    let arr = items;
    if (category) arr = arr.filter((p) => (p.primary_category || "") === category);
    if (selectedTag) {
      if (selectedTag === "empty") {
        arr = arr.filter((p) => (p.tags?.list || []).length === 0);
      } else {
        arr = arr.filter((p) => (p.tags?.list || []).includes(selectedTag));
      }
    }
    return arr;
  }, [items, category, selectedTag]);

  // Batch ops
  const batch = {
    shortlist: async () => { await Promise.all(selectedIds.map(id => setState(id, "shortlist"))); refresh(); },
    archive: async () => { await Promise.all(selectedIds.map(id => setState(id, "archived"))); refresh(); },
    tag: async () => {
      const t = prompt("Add tag to selected"); if (!t) return;
      await Promise.all(selectedIds.map(id => addTags(id, [t])));
      refresh();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <TopBar
        query={query}
        setQuery={setQuery}
        state={stateFilter}
        setStateFilter={setStateFilter}
        refresh={refresh}
        quickFilters={paletteTags}
        toggleFilter={toggleFilter}
        selectedTag={selectedTag}
        onCreateTag={(t)=>setUserTags((prev)=> prev.includes(t) ? prev : [...prev, t])}
      />

      <CategoryBar categories={categoryOptions} selected={category} onSelect={setCategory} />

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-[5fr,1fr] gap-4 p-4">
        {/* List column */}
        <section className="rounded-2xl border bg-white overflow-hidden">
          <div className="px-3 py-2 text-sm text-gray-600 border-b flex items-center justify-between">
            <div>{visibleItems.length} / {total} results</div>
            <div className="flex items-center gap-3">
              <button className="text-xs underline" onClick={()=>setChecked(Object.fromEntries(visibleItems.map(p=>[p.id,true])))}>Select page</button>
              <button className="text-xs underline" onClick={()=>setChecked({})}>Clear</button>
            </div>
          </div>
          <div>
            {visibleItems.map((p) => (
              <PaperRow key={p.id}
                p={p}
                checked={!!checked[p.id]}
                onToggle={()=>setChecked((m)=>({...m, [p.id]: !m[p.id]}))}
                onOpen={()=>setDrawer(p)}
                onShortlist={()=>mutate(p.id, "shortlist")}
                onArchive={()=>mutate(p.id, "archived")}
                availableTags={paletteTags}
                onAddTag={(t)=>tagAdd(p.id, t)}
                onDropTag={(t, pid)=>{
                  const tag = t.trim(); if (!tag) return;
                  const targets = selectedIds.length ? selectedIds : [pid];
                  Promise.all(targets.map(id => tagAdd(id, tag)));
                }}
                onRemoveTag={(t)=>tagRemove(p.id, t)}
              />
            ))}
            <div className="flex justify-center p-4 border-t bg-white">
              {items.length < total && (
                <button className="rounded-xl border px-4 py-2 bg-white hover:bg-gray-50" onClick={() => setPage((p) => p + 1)} disabled={loading}>
                  {loading ? "Loading…" : "Load more"}
                </button>
              )}
            </div>
            {error && <div className="text-red-600 text-sm p-3">{error}</div>}
          </div>
        </section>

        {/* Clusters / sidebar
        <aside className="space-y-3">
          <div className="rounded-2xl border bg-white p-3">
            <div className="text-sm font-semibold mb-2">Clusters</div>
            <div className="space-y-2 max-h-[100vh] overflow-auto pr-1">
              {byCat.map(([cat, arr]) => (
                <div key={cat} className="border rounded-xl p-2">
                  <div className="text-xs font-medium mb-1">{cat} <span className="text-gray-500">({arr.length})</span></div>
                  <ul className="space-y-1 text-sm">
                    {arr.slice(0, 8).map((p) => (
                      <li key={p.id} className="truncate">
                        <a className="hover:underline" href={p.links_abs || p.links_html} target="_blank" rel="noreferrer">{p.title}</a>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </aside> */}
      </div>

      {/* Batch toolbar */}
      {anyChecked && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-white border shadow-xl rounded-2xl px-3 py-2 z-40 flex items-center gap-2">
          <div className="text-sm text-gray-600">{selectedIds.length} selected</div>
          <button className="rounded-xl border px-3 py-1 hover:bg-gray-50" onClick={batch.shortlist}>Shortlist</button>
          <button className="rounded-xl border px-3 py-1 hover:bg-gray-50" onClick={batch.archive}>Archive</button>
          <button className="rounded-xl border px-3 py-1 hover:bg-gray-50" onClick={batch.tag}>+ Tag</button>
          <div
            className={("rounded-xl border px-3 py-1 text-sm cursor-copy " + (isBatchDragOver ? "ring-2 ring-blue-300 bg-blue-50" : "hover:bg-gray-50"))}
            onDragOver={(e)=>{ e.preventDefault(); setIsBatchDragOver(true); }}
            onDragLeave={()=> setIsBatchDragOver(false)}
            onDrop={(e)=>{
              e.preventDefault(); setIsBatchDragOver(false);
              const t = e.dataTransfer.getData('text/plain').trim();
              if (!t) return;
              if (!selectedIds.length) return;
              Promise.all(selectedIds.map(id => tagAdd(id, t)));
            }}
            title="Drag a tag here to apply to all selected papers"
          >
            Drop tag here →
          </div>
        </div>
      )}

      <DetailsDrawer
        p={drawer}
        onClose={()=>setDrawer(null)}
        onTagAdd={(t)=>drawer && tagAdd(drawer.id, t)}
        onTagRemove={(t)=>drawer && tagRemove(drawer.id, t)}
      />

      {/* Shortcut legend */}
      <div className="fixed bottom-4 right-4 text-xs text-gray-600 bg-white/80 backdrop-blur rounded-xl border px-3 py-2 shadow-sm">
        <div className="font-medium">Shortcuts</div>
        <div>/ search · Esc close drawer</div>
      </div>
    </div>
  );
}

// Email login flow removed per simplification
