import React from "react";

type Category = { name: string; count: number };

type Props = {
  categories: Category[];
  selected: string | "";
  onSelect: (name: string | "") => void;
};

export default function CategoryBar({ categories, selected, onSelect }: Props) {
  if (!categories.length) return null;
  return (
    <div className="sticky top-[48px] sm:top-[56px] z-10 bg-white/80 backdrop-blur border-b">
      <div className="max-w-7xl mx-auto px-4 py-2 flex flex-wrap gap-2 items-center">
        <span className="text-xs text-gray-500 mr-1">Categories:</span>
        <button
          className={`px-2 py-1 rounded-full border text-xs ${selected===""?"bg-gray-900 text-white border-gray-900":"hover:bg-gray-50"}`}
          onClick={() => onSelect("")}
        >All</button>
        {categories.map(c => (
          <button
            key={c.name}
            onClick={() => onSelect(selected === c.name ? "" : c.name)}
            className={`px-2 py-1 rounded-full border text-xs ${selected===c.name?"bg-gray-900 text-white border-gray-900":"hover:bg-gray-50"}`}
            title={`${c.count} papers`}
          >{c.name} ({c.count})</button>
        ))}
      </div>
    </div>
  );
}

