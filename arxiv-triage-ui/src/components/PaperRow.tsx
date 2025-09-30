import React, { useMemo, useRef, useState, useEffect } from "react";
import type { Paper } from "../types";
import { IconBtn, Pill } from "./ui";
import { timeAgo } from "../utils";

type Props = {
  p: Paper;
  checked: boolean;
  onToggle: () => void;
  onOpen: () => void;
  onShortlist: () => void;
  onArchive: () => void;
  availableTags?: string[];
  onAddTag?: (t: string) => void;
  onDropTag?: (t: string, paperId: number) => void;
  onRemoveTag?: (t: string) => void;
};

export default function PaperRow({ p, checked, onToggle, onOpen, onShortlist, onArchive, availableTags = [], onAddTag, onDropTag, onRemoveTag }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [tagOpen, setTagOpen] = useState(false);
  const [tagInput, setTagInput] = useState("");
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const preview = useMemo(() => (p.abstract || "").slice(0, 320), [p.abstract]);
  const showEllipsis = (p.abstract || "").length > preview.length;
  const existing = p.tags?.list || [];
  const suggestions = useMemo(() => availableTags.filter(t => t !== 'empty' && !existing.includes(t)), [availableTags, existing]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!menuRef.current) return;
      if (!(e.target instanceof Node)) return;
      if (!menuRef.current.contains(e.target)) setTagOpen(false);
    }
    if (tagOpen) document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [tagOpen]);

  function addTag(t: string) {
    if (!t.trim() || !onAddTag) return;
    onAddTag(t.trim());
    setTagOpen(false);
    setTagInput("");
  }
  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragOver(false);
    const t = e.dataTransfer.getData('text/plain');
    if (t && onDropTag) onDropTag(t, p.id);
  }

  return (
    <div
      className={"group grid grid-cols-[24px_1fr_auto] gap-3 items-start px-3 py-3 border-b bg-white hover:bg-gray-50 relative " + (isDragOver?"ring-2 ring-blue-300":"")}
      onDragOver={(e)=>{ e.preventDefault(); setIsDragOver(true); }}
      onDragLeave={()=>setIsDragOver(false)}
      onDrop={handleDrop}
    >
      <input type="checkbox" checked={checked} onChange={onToggle} className="mt-1" />
      <div className="min-w-0">
        <div className="text-sm text-gray-500 truncate">{p.authors}</div>
        <button onClick={onOpen} className="text-left font-semibold leading-snug group-hover:underline">
          {p.title}
        </button>
        <div className="mt-1 flex items-center gap-2 text-xs text-gray-600">
          <Pill>{p.primary_category}</Pill>
          {p.updated_at && <span>{timeAgo(p.updated_at)}</span>}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1 text-xs">
          {(existing.length > 0) ? (
            existing.map(t => (
              <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs text-gray-700 border-gray-300">
                #{t}
                {onRemoveTag && (
                  <button
                    title="Remove tag"
                    onClick={(e)=>{ e.stopPropagation(); onRemoveTag(t); }}
                    className="text-gray-400 hover:text-gray-700"
                  >×</button>
                )}
              </span>
            ))
          ) : (
            <span className="px-2 py-0.5 rounded-full border text-xs text-red-600 border-red-300 bg-red-50">empty</span>
          )}
        </div>
        {(p.abstract) && (
          <div className="mt-2 text-sm text-gray-800">
            {expanded ? p.abstract : (<>
              {preview}{showEllipsis && "…"}
            </>)}
            {showEllipsis && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="ml-2 text-xs text-blue-600 hover:underline align-baseline"
                title={expanded ? "Show less" : "Show more"}
              >{expanded ? "Less" : "More"}</button>
            )}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition">
        <IconBtn title="Shortlist" onClick={onShortlist}>✔︎</IconBtn>
        <IconBtn title="Archive" onClick={onArchive}>🗂</IconBtn>
        <IconBtn title="Tag" onClick={() => setTagOpen((v)=>!v)}>🏷️</IconBtn>
        <a title="Abs" href={p.links_abs} target="_blank" className="rounded-lg border px-2 py-1 hover:bg-gray-50">abs ↗</a>
      </div>
      {tagOpen && (
        <div ref={menuRef} className="absolute right-3 top-10 z-20 w-56 bg-white border rounded-xl shadow-lg p-2">
          <div className="text-xs text-gray-500 px-1 pb-1">Add tag</div>
          <div className="max-h-48 overflow-auto">
            {suggestions.length > 0 ? (
              suggestions.map(t => (
                <button key={t} onClick={() => addTag(t)} className="w-full text-left px-2 py-1 rounded hover:bg-gray-50 text-sm">
                  #{t}
                </button>
              ))
            ) : (
              <div className="px-2 py-1 text-xs text-gray-500">No suggestions</div>
            )}
          </div>
          <div className="mt-2 flex items-center gap-1">
            <input
              value={tagInput}
              onChange={(e)=>setTagInput(e.target.value)}
              onKeyDown={(e)=>{ if (e.key==='Enter') addTag(tagInput); }}
              placeholder="New tag"
              className="flex-1 border rounded px-2 py-1 text-sm"
            />
            <button className="text-sm rounded border px-2 py-1 hover:bg-gray-50" onClick={()=>addTag(tagInput)}>Add</button>
          </div>
        </div>
      )}
    </div>
  );
}
