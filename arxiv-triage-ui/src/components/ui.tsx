import React from "react";

export function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="px-2 py-0.5 rounded-full border text-xs text-gray-700 border-gray-300">
      {children}
    </span>
  );
}

export function IconBtn({ title, onClick, children }: { title: string; onClick?: () => void; children: React.ReactNode }) {
  return (
    <button
      title={title}
      onClick={onClick}
      className="rounded-lg border px-2 py-1 hover:bg-gray-50 active:scale-[0.99]"
    >
      {children}
    </button>
  );
}

