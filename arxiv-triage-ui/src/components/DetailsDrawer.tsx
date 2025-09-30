import React from "react";
import type { Paper } from "../types";
import { Pill } from "./ui";
import { timeAgo } from "../utils";

function TagEditor({ tags, onAdd, onRemove }: { tags: string[]; onAdd: (t:string)=>void; onRemove: (t:string)=>void }){
  const [v,setV] = React.useState("");
  return (
    <div className="flex flex-wrap gap-2">
      {tags.map(t => (
        <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs">
          {t}
          <button onClick={()=>onRemove(t)} className="text-gray-500 hover:text-gray-800">×</button>
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
};

export default function DetailsDrawer({ p, onClose, onTagAdd, onTagRemove }: Props){
  if (!p) return null;
  const tags = p.tags?.list || [];
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
        </div>
        <div className="mt-4">
          <div className="text-xs font-semibold text-gray-500 mb-1">Notes</div>
          <textarea className="w-full border rounded-xl p-2 text-sm" rows={4} placeholder="Your quick notes (persist later via API)…"/>
        </div>
      </div>
    </aside>
  );
}

