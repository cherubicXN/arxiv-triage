import React from "react";
import type { Paper, Rubric } from "../types";
import { Pill } from "./ui";
import { timeAgo } from "../utils";

function TagEditor({ tags, onAdd, onRemove }: { tags: string[]; onAdd: (t:string)=>void; onRemove: (t:string)=>void }){
  const [v,setV] = React.useState("");
  return (
    <div className="flex flex-wrap gap-2">
      {tags.map(t => (
        <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs text-green-700 border-green-300 bg-green-50">
          {t}
          <button onClick={()=>onRemove(t)} className="text-green-700/70 hover:text-green-900">×</button>
        </span>
      ))}
      <input value={v} onChange={(e)=>setV(e.target.value)} onKeyDown={(e)=>{ if(e.key==='Enter'&&v.trim()){ onAdd(v.trim()); setV(""); } }}
        placeholder="+ tag" className="text-xs border rounded px-2 py-1 w-24" />
    </div>
  );
}

type Props = {
  p: Paper | null;
  onClose: ()=>void;
  onTagAdd:(t:string)=>void;
  onTagRemove:(t:string)=>void;
  onScore:(provider?: string)=>void;
  onSuggest:(provider?: string)=>void;
  onRubricSave:(rb: Rubric)=>void;
  onNoteSave:(text: string)=>void;
};

export default function DetailsDrawer({ p, onClose, onTagAdd, onTagRemove, onScore, onSuggest, onRubricSave, onNoteSave }: Props){
  if (!p) return null;
  const tags = p.tags?.list || [];
  const rb = (p.signals?.rubric || { novelty:3, evidence:3, clarity:3, reusability:2, fit:3, total:14 }) as Rubric;
  const [r, setR] = React.useState<Rubric>(rb);
  React.useEffect(()=>{ setR(rb); }, [p?.id]);
  const recompute = (partial: Partial<Rubric>) => {
    const next = { ...r, ...partial } as Rubric;
    const total = (next.novelty|0) + (next.evidence|0) + (next.clarity|0) + (next.reusability|0) + (next.fit|0);
    setR({ ...next, total });
  };
  const [note, setNote] = React.useState<string>(String((p.extra as any)?.note || ""));
  React.useEffect(()=>{ setNote(String((p.extra as any)?.note || "")); }, [p?.id]);
  const suggested: string[] = (p.signals?.suggested_tags || []) as any;
  return (
    <aside className="fixed inset-y-0 right-0 w-full sm:w-[520px] bg-white border-l shadow-xl z-30 flex flex-col">
      <div className="p-3 border-b flex items-center justify-between">
        <div className="text-sm text-gray-500 truncate">{p.authors}</div>
        <button onClick={onClose} className="rounded-lg border px-2 py-1">Esc</button>
      </div>
      <div className="p-4 overflow-y-auto">
        <h2 className="font-semibold text-lg leading-snug">{p.title}</h2>
        <div className="mt-2 flex items-center gap-2 text-xs text-gray-600">
          <Pill>{p.primary_category}</Pill>
          {p.updated_at && <span>{timeAgo(p.updated_at)}</span>}
        </div>
        <p className="mt-3 text-sm text-gray-800 whitespace-pre-wrap">{p.abstract}</p>
        <div className="mt-3 flex items-center gap-3 text-sm">
          <a className="text-blue-600 hover:underline" href={p.links_abs} target="_blank" rel="noreferrer">abs ↗</a>
          <a className="text-blue-600 hover:underline" href={p.links_pdf} target="_blank" rel="noreferrer">pdf ↗</a>
          <a className="text-blue-600 hover:underline" href={p.links_html} target="_blank" rel="noreferrer">html ↗</a>
        </div>
        <div className="mt-4">
          <div className="text-xs font-semibold text-gray-500 mb-1">Tags</div>
          <TagEditor
            tags={tags}
            onAdd={onTagAdd}
            onRemove={onTagRemove}
          />
          {suggested && suggested.length > 0 && (
            <div className="mt-2 text-xs text-gray-600">
              <div className="mb-1">Suggestions</div>
              <div className="flex flex-wrap gap-2">
                {suggested.map(t => (
                  <button key={t} onClick={()=>onTagAdd(t)} className="px-2 py-0.5 rounded-full border text-xs text-sky-700 border-sky-300 bg-sky-50 border-dashed hover:bg-sky-100">#{t}</button>
                ))}
              </div>
            </div>
          )}
          <div className="mt-2 flex items-center gap-2">
            <button onClick={()=>onSuggest(undefined)} className="rounded-xl border px-3 py-1.5 hover:bg-gray-50">Suggest tags</button>
            <button onClick={()=>onSuggest('deepseek')} className="rounded-xl border px-3 py-1.5 hover:bg-gray-50">Suggest (DeepSeek)</button>
          </div>
        </div>
        <div className="mt-4">
          <div className="text-xs font-semibold text-gray-500 mb-1">Scores</div>
          <div className="text-sm grid grid-cols-2 gap-3 items-center">
            <div className="rounded-lg border p-2 col-span-2">Total <span className="font-semibold">{r.total}</span></div>
            <label className="text-xs text-gray-600">Novelty {r.novelty}</label>
            <input type="range" min={1} max={5} value={r.novelty} onChange={(e)=>recompute({novelty: Number(e.target.value)})} />
            <label className="text-xs text-gray-600">Evidence {r.evidence}</label>
            <input type="range" min={1} max={5} value={r.evidence} onChange={(e)=>recompute({evidence: Number(e.target.value)})} />
            <label className="text-xs text-gray-600">Clarity {r.clarity}</label>
            <input type="range" min={1} max={5} value={r.clarity} onChange={(e)=>recompute({clarity: Number(e.target.value)})} />
            <label className="text-xs text-gray-600">Reusability {r.reusability}</label>
            <input type="range" min={1} max={5} value={r.reusability} onChange={(e)=>recompute({reusability: Number(e.target.value)})} />
            <label className="text-xs text-gray-600">Fit {r.fit}</label>
            <input type="range" min={1} max={5} value={r.fit} onChange={(e)=>recompute({fit: Number(e.target.value)})} />
          </div>
          <div className="mt-3 flex items-center gap-2">
            <button onClick={()=>onRubricSave(r)} className="rounded-xl border px-3 py-1.5 hover:bg-gray-50">Save</button>
            <button onClick={()=>onScore(undefined)} className="rounded-xl border px-3 py-1.5 hover:bg-gray-50">Score</button>
            <button onClick={()=>onScore('deepseek')} className="rounded-xl border px-3 py-1.5 hover:bg-gray-50">Score (DeepSeek)</button>
          </div>
        </div>

        <div className="mt-6">
          <div className="text-xs font-semibold text-gray-500 mb-1">Notes</div>
          <textarea className="w-full border rounded-xl p-2 text-sm" rows={4}
            placeholder="Your notes"
            value={note}
            onChange={(e)=>setNote(e.target.value)}
          />
          <div className="mt-2 flex items-center gap-2">
            <button onClick={()=>onNoteSave(note)} className="rounded-xl border px-3 py-1.5 hover:bg-gray-50">Save note</button>
            <div className="text-[11px] text-gray-500">{note.length} chars</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
