import React, { useEffect, useMemo, useState } from "react";
import TopBar from "./components/TopBar";
import PaperRow from "./components/PaperRow";
import DetailsDrawer from "./components/DetailsDrawer";
import CategoryBar from "./components/CategoryBar";
import Calendar from "./components/Calendar";
import type { Paper, ListResp, StatsResp, Rubric, HistoResp } from "./types";
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
// Allow overriding API base via query param `?api=` for easy LAN wiring.
const PARAM_API = (() => {
  try {
    if (typeof window !== "undefined") {
      const u = new URL(window.location.href);
      return u.searchParams.get("api");
    }
  } catch {}
  return null;
})();
const API_BASE = PARAM_API ||
  (import.meta as any)?.env?.VITE_ARX_API ||
  (typeof process !== "undefined" ? (process as any).env?.NEXT_PUBLIC_ARX_API : null) ||
  "http://192.168.50.153:8787";

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

async function fetchStats({ state, query }: { state?: string; query?: string; }): Promise<StatsResp> {
  const params = new URLSearchParams();
  if (state) params.set("state", state);
  if (query) params.set("query", query);
  const r = await fetch(`${API_BASE}/v1/papers/stats?${params.toString()}`);
  if (!r.ok) throw new Error(`fetchStats: ${r.status}`);
  return r.json();
}

async function setStateByArxiv(arxivId: string, state: Paper["state"]) {
  const r = await fetch(`${API_BASE}/v1/papers/by_arxiv/${arxivId}/state`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  });
  if (!r.ok) throw new Error(`setState: ${r.status}`);
  return r.json();
}

async function addTagsByArxiv(arxivId: string, tags: string[]) {
  const r = await fetch(`${API_BASE}/v1/papers/by_arxiv/${arxivId}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ add: tags }),
  });
  if (!r.ok) throw new Error(`tags: ${r.status}`);
  return r.json();
}

async function removeTagsByArxiv(arxivId: string, tags: string[]) {
  const r = await fetch(`${API_BASE}/v1/papers/by_arxiv/${arxivId}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ remove: tags }),
  });
  if (!r.ok) throw new Error(`tags-remove: ${r.status}`);
  return r.json();
}

async function fetchHistogram({ state, query, month }: { state?: string; query?: string; month?: string; }): Promise<HistoResp> {
  const params = new URLSearchParams();
  if (state) params.set("state", state);
  if (query) params.set("query", query);
  if (month) params.set("month", month);
  const r = await fetch(`${API_BASE}/v1/papers/histogram_by_day?${params.toString()}`);
  if (!r.ok) throw new Error(`fetchHistogram: ${r.status}`);
  return r.json();
}

async function scorePaperByArxivAPI(arxivId: string, provider?: string): Promise<{ ok: boolean; data: { arxiv_id: string; rubric: Rubric } }>{
  const qs = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  const r = await fetch(`${API_BASE}/v1/papers/by_arxiv/${arxivId}/score${qs}`, { method: "POST" });
  if (!r.ok) throw new Error(`score: ${r.status}`);
  return r.json();
}

async function suggestTagsByArxivAPI(arxivId: string, provider?: string): Promise<{ ok: boolean; data: { arxiv_id: string; suggested: string[] } }>{
  const qs = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  const r = await fetch(`${API_BASE}/v1/papers/by_arxiv/${arxivId}/suggest-tags${qs}`, { method: "POST" });
  if (!r.ok) throw new Error(`suggest: ${r.status}`);
  return r.json();
}

async function setRubricByArxivAPI(arxivId: string, rubric: Rubric): Promise<{ ok: boolean; data: { arxiv_id: string; rubric: Rubric } }>{
  const r = await fetch(`${API_BASE}/v1/papers/by_arxiv/${arxivId}/rubric`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rubric),
  });
  if (!r.ok) throw new Error(`rubric: ${r.status}`);
  return r.json();
}

async function setNoteByArxivAPI(arxivId: string, body: string): Promise<{ ok: boolean; data: { arxiv_id: string; note: string } }>{
  const r = await fetch(`${API_BASE}/v1/papers/by_arxiv/${arxivId}/note`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
  if (!r.ok) throw new Error(`note: ${r.status}`);
  return r.json();
}

export default function App() {
  // Show a small connectivity banner so misconfig is obvious
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "fail">("checking");
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/`, { mode: "cors" });
        if (!cancelled) setApiStatus(r.ok ? "ok" : "fail");
      } catch {
        if (!cancelled) setApiStatus("fail");
      }
    })();
    return () => { cancelled = true; };
  }, []);
  const [query, setQuery] = useState("");
  const q = useDebounced(query, 250);
  const [stateFilter, setStateFilter] = useState<Paper["state"]|"">("triage");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(40);
  const [items, setItems] = useState<Paper[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<StatsResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<Paper|null>(null);
  const [checked, setChecked] = useState<Record<number, boolean>>({});
  const [category, setCategory] = useState<string | "">("");
  const [selectedTag, setSelectedTag] = useState<string | "">("");
  const [userTags, setUserTags] = useState<string[]>([]);
  const [isBatchDragOver, setIsBatchDragOver] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | "">("");
  const [cursorId, setCursorId] = useState<number | null>(null);
  const [autoOpenOnMove, setAutoOpenOnMove] = useState<boolean>(false);
  const [singleStatus, setSingleStatus] = useState<{ text: string; error?: boolean } | null>(null);
  const [batchProg, setBatchProg] = useState<{ total: number; done: number; label: string } | null>(null);
  const [pdfModal, setPdfModal] = useState<{ arxivId: string } | null>(null);
  const [calendarMonth, setCalendarMonth] = useState<string>(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
    
  });
  const [histo, setHisto] = useState<Record<string, number>>({});

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

  useEffect(() => {
    if (page !== 1) setPage(1);
    else load(true);
    /* eslint-disable-next-line */
  }, [q, stateFilter]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await fetchStats({ state: stateFilter || undefined, query: q || undefined });
        if (!cancelled) setStats(s);
      } catch (e: any) {
        if (!cancelled) setStats(null);
      }
    })();
    return () => { cancelled = true; };
  }, [q, stateFilter]);
  useEffect(() => { load(true); /* eslint-disable-next-line */ }, [page]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await fetchHistogram({ state: stateFilter || undefined, query: q || undefined, month: calendarMonth });
        if (!cancelled) setHisto(h.counts || {});
      } catch (e) {
        if (!cancelled) setHisto({});
      }
    })();
    return () => { cancelled = true; };
  }, [q, stateFilter, calendarMonth]);

  function refresh() { setPage(1); load(true); }

  async function mutateByPaper(paper: Paper, newState: Paper["state"]) {
    await setStateByArxiv(paper.arxiv_id, newState);
    setItems((prev) => prev.filter((x) => x.id !== paper.id));
    setChecked((m)=>{ const n={...m}; delete n[paper.id]; return n; });
  }

  async function tagAdd(paperId: number, t: string) {
    // Optimistic update first
    setItems((prev) => prev.map((p) => p.id === paperId ? { ...p, tags: { list: Array.from(new Set([...(p.tags?.list || []), t])) } } : p));
    setDrawer((d)=> d && d.id===paperId ? { ...d, tags: { list: Array.from(new Set([...(d.tags?.list || []), t])) } } : d);
    try {
      const p = items.find(x=>x.id===paperId);
      if (p) await addTagsByArxiv(p.arxiv_id, [t]);
    } catch (e: any) {
      // Revert on failure and surface error
      setItems((prev) => prev.map((p) => p.id === paperId ? { ...p, tags: { list: (p.tags?.list || []).filter(x=>x!==t) } } : p));
      setDrawer((d)=> d && d.id===paperId ? { ...d, tags: { list: (d.tags?.list || []).filter(x=>x!==t) } } : d);
      setError(e?.message || 'Failed to add tag');
    }
  }
  async function tagRemove(paperId: number, t: string) {
    // Optimistic remove
    setItems((prev) => prev.map((p) => p.id === paperId ? { ...p, tags: { list: (p.tags?.list || []).filter(x=>x!==t) } } : p));
    setDrawer((d)=> d && d.id===paperId ? { ...d, tags: { list: (d.tags?.list || []).filter(x=>x!==t) } } : d);
    try {
      const p = items.find(x=>x.id===paperId);
      if (p) await removeTagsByArxiv(p.arxiv_id, [t]);
    } catch (e: any) {
      // Revert on failure and surface error
      setItems((prev) => prev.map((p) => p.id === paperId ? { ...p, tags: { list: Array.from(new Set([...(p.tags?.list || []), t])) } } : p));
      setDrawer((d)=> d && d.id===paperId ? { ...d, tags: { list: Array.from(new Set([...(d.tags?.list || []), t])) } } : d);
      setError(e?.message || 'Failed to remove tag');
    }
  }

  async function scoreNow(paper: Paper, provider?: string) {
    try {
      setSingleStatus({ text: 'Scoring…' });
      const res = await scorePaperByArxivAPI(paper.arxiv_id, provider);
      setItems((prev) => prev.map((x) => x.id === paper.id ? { ...x, signals: { ...(x.signals||{}), rubric: (res as any).data.rubric } } : x));
      setDrawer((d)=> d && d.id===paper.id ? { ...d, signals: { ...(d.signals||{}), rubric: (res as any).data.rubric } } : d);
      setSingleStatus({ text: 'Scored' });
      setTimeout(()=> setSingleStatus(null), 1200);
    } catch (e: any) {
      setError(e?.message || 'Failed to score');
      setSingleStatus({ text: 'Score failed', error: true });
      setTimeout(()=> setSingleStatus(null), 2000);
    } finally { /* no global spinner */ }
  }

  async function suggestNow(paper: Paper, provider?: string) {
    try {
      setSingleStatus({ text: 'Suggesting…' });
      const res = await suggestTagsByArxivAPI(paper.arxiv_id, provider);
      const suggested = (res as any).data.suggested || [];
      setItems((prev) => prev.map((x) => x.id === paper.id ? { ...x, signals: { ...(x.signals||{}), suggested_tags: suggested } } : x));
      setDrawer((d)=> d && d.id===paper.id ? { ...d, signals: { ...(d.signals||{}), suggested_tags: suggested } } : d);
      setSingleStatus({ text: 'Suggested' });
      setTimeout(()=> setSingleStatus(null), 1200);
    } catch (e: any) {
      setError(e?.message || 'Failed to suggest tags');
      setSingleStatus({ text: 'Suggest failed', error: true });
      setTimeout(()=> setSingleStatus(null), 2000);
    } finally { /* no global spinner */ }
  }

  // Visible list after client-side filters (category, tag, date)
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
    if (selectedDate) {
      arr = arr.filter((p) =>
        (p.submitted_at && p.submitted_at.startsWith(selectedDate)) ||
        (p.updated_at && p.updated_at.startsWith(selectedDate))
      );
    }
    return arr;
  }, [items, category, selectedTag, selectedDate]);

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: any) {
      if ((e.target as HTMLElement)?.tagName === 'INPUT' || (e.target as HTMLElement)?.tagName === 'TEXTAREA') return;
      if (e.key === "/") { e.preventDefault(); const inp = document.querySelector<HTMLInputElement>("input"); inp?.focus(); return; }
      if (e.key === "Escape") { if (pdfModal) { setPdfModal(null); return; } setDrawer(null); return; }

      const ids = (visibleItems || []).map(p=>p.id);
      if (!ids.length) return;
      const currentIdx = cursorId ? ids.indexOf(cursorId) : -1;

      function moveTo(idx: number) {
        const clamped = Math.max(0, Math.min(ids.length - 1, idx));
        const id = ids[clamped];
        setCursorId(id);
        const el = typeof document !== 'undefined' ? document.querySelector(`[data-paper-id="${id}"]`) : null;
        if (el && 'scrollIntoView' in el) { (el as any).scrollIntoView({ block: 'nearest' }); }
        if (autoOpenOnMove) {
          const p = visibleItems[clamped];
          if (p) setDrawer(p);
        }
      }

      if (e.key === 'j' || e.key === 'ArrowDown') { e.preventDefault(); moveTo((currentIdx < 0 ? 0 : currentIdx + 1)); return; }
      if (e.key === 'k' || e.key === 'ArrowUp') { e.preventDefault(); moveTo((currentIdx < 0 ? 0 : currentIdx - 1)); return; }
      if (e.key === 'l') { e.preventDefault(); const maxPage = Math.max(1, Math.ceil(total / pageSize) || 1); if (page < maxPage) setPage(page + 1); return; }
      if (e.key === 'h') { e.preventDefault(); if (page > 1) setPage(page - 1); return; }

      const currentId = cursorId ?? ids[0];
      if (!currentId) return;
      if (e.key === 'o' || e.key === 'Enter') { e.preventDefault(); const p = visibleItems.find(p=>p.id===currentId); if (p) { setDrawer(p); setAutoOpenOnMove(true); } return; }
      if (e.key === 's') { e.preventDefault(); const p = visibleItems.find(p=>p.id===currentId); if (p) mutateByPaper(p, 'shortlist'); return; }
      if (e.key === 'a') { e.preventDefault(); const p = visibleItems.find(p=>p.id===currentId); if (p) mutateByPaper(p, 'archived'); return; }
      if (e.key === 'x' || e.key === ' ') { e.preventDefault(); setChecked((m)=>({ ...m, [currentId]: !m[currentId] })); return; }
      if (e.key === 'r') { e.preventDefault(); const p = visibleItems.find(p=>p.id===currentId); if (p) scoreNow(p); return; }
      if (e.key === 't') { e.preventDefault(); const p = visibleItems.find(p=>p.id===currentId); if (p) suggestNow(p); return; }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visibleItems, cursorId, autoOpenOnMove, page, pageSize, total, pdfModal]);

  // Derived
  const anyChecked = useMemo(()=> Object.values(checked).some(Boolean), [checked]);
  const selectedIds = useMemo(()=> Object.keys(checked).filter(k=>checked[Number(k)]).map(Number), [checked]);

  // Category clusters (brief)
  const categoryOptions = useMemo(() => {
    const entries = stats ? Object.entries(stats.categories) : [];
    return entries
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [stats]);

  // Tag counts and palette (auto-remove tags with zero association)
  const tagCounts = useMemo(() => {
    const m = new Map<string, number>();
    if (stats?.tags) {
      for (const [t, c] of Object.entries(stats.tags)) m.set(t, c);
    }
    return m;
  }, [stats]);

  // Cleanup user-only tags that are not associated with any paper
  useEffect(() => {
    setUserTags((prev) => prev.filter((t) => (tagCounts.get(t) || 0) > 0));
  }, [tagCounts]);

  const paletteTags = useMemo(() => {
    const used = Array.from(tagCounts.keys());
    const hasEmpty = (stats?.empty_tag_count || 0) > 0;
    return Array.from(new Set([...(hasEmpty ? ["empty"] : []), ...used, ...userTags]));
  }, [tagCounts, userTags, stats]);

  // Toggle tag filter (client-side)
  const toggleFilter = (t: string) => setSelectedTag((prev) => prev === t ? "" : t);

  

  // Ensure cursor points to a visible item
  useEffect(() => {
    const ids = visibleItems.map(p=>p.id);
    if (!ids.length) { setCursorId(null); return; }
    if (!cursorId || !ids.includes(cursorId)) {
      setCursorId(ids[0]);
    }
  }, [visibleItems]);

  // Batch ops
  const batch = {
    shortlist: async () => { await Promise.all(selectedIds.map(id => setState(id, "shortlist"))); refresh(); },
    archive: async () => { await Promise.all(selectedIds.map(id => setState(id, "archived"))); refresh(); },
    tag: async () => {
      const t = prompt("Add tag to selected"); if (!t) return;
      await Promise.all(selectedIds.map(id => addTags(id, [t])));
      refresh();
    },
    score: async () => {
      const targets = items.filter(p => selectedIds.includes(p.id));
      if (!targets.length) return;
      setBatchProg({ total: targets.length, done: 0, label: 'Scoring' });
      let done = 0;
      for (const p of targets) {
        try {
          const res = await scorePaperByArxivAPI(p.arxiv_id);
          setItems((prev) => prev.map((x) => x.id === p.id ? { ...x, signals: { ...(x.signals||{}), rubric: (res as any).data.rubric } } : x));
          setDrawer((d)=> d && d.id===p.id ? { ...d, signals: { ...(d.signals||{}), rubric: (res as any).data.rubric } } : d);
        } catch {}
        done += 1;
        setBatchProg({ total: targets.length, done, label: 'Scoring' });
      }
      setTimeout(()=> setBatchProg(null), 600);
    },
    suggest: async () => {
      const targets = items.filter(p => selectedIds.includes(p.id));
      if (!targets.length) return;
      setBatchProg({ total: targets.length, done: 0, label: 'Suggesting' });
      let done = 0;
      for (const p of targets) {
        try {
          const res = await suggestTagsByArxivAPI(p.arxiv_id);
          const suggested = (res as any).data.suggested || [];
          setItems((prev) => prev.map((x) => x.id === p.id ? { ...x, signals: { ...(x.signals||{}), suggested_tags: suggested } } : x));
          setDrawer((d)=> d && d.id===p.id ? { ...d, signals: { ...(d.signals||{}), suggested_tags: suggested } } : d);
        } catch {}
        done += 1;
        setBatchProg({ total: targets.length, done, label: 'Suggesting' });
      }
      setTimeout(()=> setBatchProg(null), 600);
    },
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* API status banner */}
      <div className="fixed top-3 right-3 z-50 text-xs">
        <a
          href={`${API_BASE}/docs`}
          target="_blank"
          rel="noreferrer"
          className={
            "inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 shadow-sm " +
            (apiStatus === "ok" ? "bg-green-50 border-green-200 text-green-700" :
             apiStatus === "checking" ? "bg-yellow-50 border-yellow-200 text-yellow-700" :
             "bg-red-50 border-red-200 text-red-700")
          }
          title="Click to open API docs"
        >
          <span className="font-medium">API</span>
          <span className="truncate max-w-[22ch]" style={{direction: 'ltr'}}>{API_BASE}</span>
          <span>· {apiStatus === "checking" ? "checking…" : apiStatus === "ok" ? "ok" : "unreachable"}</span>
        </a>
        {apiStatus === "fail" && (
          <div className="mt-1 text-[10px] text-gray-600">
            Hint: pass ?api=http://LAN_IP:8787 in the URL
          </div>
        )}
      </div>
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

      <div className={"max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-[1fr,5fr] gap-4 p-4"}>
        {/* Left sidebar: Calendar */}
        <aside className="hidden lg:block sticky top-[92px] self-start">
          <Calendar selected={selectedDate} onSelect={setSelectedDate} viewMonth={calendarMonth} onViewMonth={setCalendarMonth} counts={histo} />
        </aside>
        {/* List column */}
        <section className="rounded-2xl border bg-white overflow-hidden">
          <div className="px-3 py-2 text-sm text-gray-600 border-b flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-3">
              <span>{visibleItems.length} / {total} results</span>
              <span>· Page {page} of {Math.max(1, Math.ceil(total / pageSize) || 1)} · {pageSize} per page</span>
              <button className="text-xs underline" onClick={()=>setChecked(Object.fromEntries(visibleItems.map(p=>[p.id,true])))}>Select page</button>
              <button className="text-xs underline" onClick={()=>setChecked({})}>Clear</button>
            </div>
            <div className="flex items-center gap-2">
              <button
                className="rounded-xl border px-3 py-1 hover:bg-gray-50 disabled:opacity-50"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={loading || page <= 1}
              >Prev</button>
              <button
                className="rounded-xl border px-3 py-1 hover:bg-gray-50 disabled:opacity-50"
                onClick={() => setPage((p) => Math.min(Math.max(1, Math.ceil(total / pageSize) || 1), p + 1))}
                disabled={loading || page >= Math.max(1, Math.ceil(total / pageSize) || 1)}
              >Next</button>
              <select
                className="ml-2 rounded-xl border px-2 py-1"
                value={pageSize}
                onChange={(e)=>{ const v = Number(e.target.value)||40; setPageSize(v); setPage(1); }}
              >
                <option value={20}>20</option>
                <option value={40}>40</option>
                <option value={80}>80</option>
                <option value={120}>120</option>
              </select>
            </div>
          </div>
          <div>
            {visibleItems.map((p) => (
              <PaperRow key={p.id}
                p={p}
                checked={!!checked[p.id]}
                active={cursorId === p.id}
                onToggle={()=>setChecked((m)=>({...m, [p.id]: !m[p.id]}))}
                onOpen={()=>{ setCursorId(p.id); setDrawer(p); setAutoOpenOnMove(true); }}
                onShortlist={()=>mutateByPaper(p, "shortlist")}
                onArchive={()=>mutateByPaper(p, "archived")}
                onScore={()=>scoreNow(p)}
                availableTags={paletteTags}
                onAddTag={(t)=>tagAdd(p.id, t)}
                onDropTag={(t, pid)=>{
                  const tag = t.trim(); if (!tag) return;
                  const targets = selectedIds.length ? selectedIds : [pid];
                  Promise.all(targets.map(id => tagAdd(id, tag)));
                }}
                onRemoveTag={(t)=>tagRemove(p.id, t)}
                onSuggest={()=>suggestNow(p)}
              />
            ))}
            <div className="flex items-center justify-between gap-3 p-4 border-t bg-white text-sm">
              <div>
                Page {page} of {Math.max(1, Math.ceil(total / pageSize) || 1)} · {pageSize} per page
              </div>
              <div className="flex items-center gap-2">
                <button
                  className="rounded-xl border px-3 py-1 hover:bg-gray-50 disabled:opacity-50"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={loading || page <= 1}
                >Prev</button>
                <button
                  className="rounded-xl border px-3 py-1 hover:bg-gray-50 disabled:opacity-50"
                  onClick={() => setPage((p) => Math.min(Math.max(1, Math.ceil(total / pageSize) || 1), p + 1))}
                  disabled={loading || page >= Math.max(1, Math.ceil(total / pageSize) || 1)}
                >Next</button>
                <select
                  className="ml-2 rounded-xl border px-2 py-1"
                  value={pageSize}
                  onChange={(e)=>{ const v = Number(e.target.value)||40; setPageSize(v); setPage(1); }}
                >
                  <option value={20}>20</option>
                  <option value={40}>40</option>
                  <option value={80}>80</option>
                  <option value={120}>120</option>
                </select>
              </div>
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
          <button className="rounded-xl border px-3 py-1 hover:bg-gray-50" onClick={batch.score}>Score</button>
          <button className="rounded-xl border px-3 py-1 hover:bg-gray-50" onClick={batch.suggest}>Suggest</button>
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

      {/* Status / Progress (bottom-left) */}
      <div className="fixed bottom-4 left-4 z-40 space-y-2">
        {batchProg && (
          <div className="w-64 rounded-xl border bg-white shadow-sm p-2">
            <div className="text-xs text-gray-600 mb-1">{batchProg.label} {batchProg.done}/{batchProg.total}</div>
            <div className="h-2 bg-gray-100 rounded">
              <div className="h-2 bg-blue-500 rounded" style={{ width: `${Math.max(0, Math.min(100, (batchProg.done / Math.max(1, batchProg.total)) * 100))}%` }} />
            </div>
          </div>
        )}
        {!batchProg && singleStatus && (
          <div className={"rounded-xl border px-3 py-1.5 text-xs shadow-sm " + (singleStatus.error ? "bg-red-50 border-red-200 text-red-700" : "bg-white border-gray-200 text-gray-700")}>{singleStatus.text}</div>
        )}
      </div>

      <DetailsDrawer
        p={drawer}
        onClose={()=>{ setDrawer(null); }}
        onTagAdd={(t)=>drawer && tagAdd(drawer.id, t)}
        onTagRemove={(t)=>drawer && tagRemove(drawer.id, t)}
        onScore={(provider)=> drawer && scoreNow(drawer, provider)}
        onSuggest={(provider)=> drawer && suggestNow(drawer, provider)}
        onRubricSave={async (rb)=>{
          if (!drawer) return;
          try {
            setLoading(true);
            const res = await setRubricByArxivAPI(drawer.arxiv_id, rb);
            const updated = res.data.rubric;
            setItems((prev) => prev.map((p) => p.id === drawer.id ? { ...p, signals: { ...(p.signals||{}), rubric: updated } } : p));
            setDrawer((d)=> d ? { ...d, signals: { ...(d.signals||{}), rubric: updated } } : d);
          } catch (e: any) {
            setError(e?.message || 'Failed to save rubric');
          } finally { setLoading(false); }
        }}
        onNoteSave={async (text)=>{
          if (!drawer) return;
          try {
            setLoading(true);
            await setNoteByArxivAPI(drawer.arxiv_id, text);
            setItems((prev) => prev.map((x) => x.id === drawer.id ? { ...x, extra: { ...(x.extra||{}), note: text } } : x));
            setDrawer((d)=> d ? { ...d, extra: { ...(d.extra||{}), note: text } } : d);
          } catch (e: any) {
            setError(e?.message || 'Failed to save note');
          } finally { setLoading(false); }
        }}
        apiBase={API_BASE}
        onOpenPdf={(arxivId)=> setPdfModal({ arxivId })}
      />

      {/* Shortcut legend */}
      <div className="fixed bottom-4 right-4 text-xs text-gray-600 bg-white/80 backdrop-blur rounded-xl border px-3 py-2 shadow-sm">
        <div className="font-medium">Shortcuts</div>
        <div>/ search · Esc close drawer</div>
        <div>j/k move · o open · x select</div>
        <div>s shortlist · a archive · r score · t suggest</div>
        <div>h prev page · l next page</div>
      </div>

      {/* PDF modal (popup, not full-screen) */}
      {pdfModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center" onClick={()=> setPdfModal(null)}>
          <div className="bg-white rounded-2xl shadow-2xl border w-[96vw] h-[90vh] md:w-[88vw] lg:w-[75vw] relative overflow-hidden" onClick={(e)=>e.stopPropagation()}>
            <div className="absolute top-2 right-2 z-10 flex items-center gap-2">
              <a
                href={`${API_BASE}/v1/papers/by_arxiv/${pdfModal.arxivId}/pdf`}
                target="_blank"
                rel="noreferrer"
                className="rounded-xl border px-3 py-1.5 bg-white hover:bg-gray-50"
              >Open ↗</a>
              <button
                className="rounded-xl border px-3 py-1.5 bg-white hover:bg-gray-50"
                onClick={()=> setPdfModal(null)}
              >Close</button>
            </div>
            <iframe
              title="PDF preview"
              src={`${API_BASE}/v1/papers/by_arxiv/${pdfModal.arxivId}/pdf`}
              className="w-full h-full"
            />
          </div>
        </div>
      )}
    </div>
  );
}

// Email login flow removed per simplification
