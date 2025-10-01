import React from "react";

type Props = {
  selected: string | "";
  onSelect: (date: string | "") => void;
  viewMonth: string; // YYYY-MM
  onViewMonth: (month: string) => void;
  counts?: Record<string, number>;
};

function fmt(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function Calendar({ selected, onSelect, viewMonth, onViewMonth, counts = {} }: Props) {
  const today = new Date();
  const [view, setView] = React.useState<Date>(() => {
    const [y,m] = viewMonth.split("-").map(Number);
    return new Date(y, (m||1)-1, 1);
  });
  React.useEffect(() => {
    const [y,m] = viewMonth.split("-").map(Number);
    setView(new Date(y, (m||1)-1, 1));
  }, [viewMonth]);

  const year = view.getFullYear();
  const month = view.getMonth(); // 0-11
  const start = new Date(year, month, 1);
  const end = new Date(year, month + 1, 0);
  const startWeekday = (start.getDay() + 6) % 7; // make Monday=0
  const daysInMonth = end.getDate();

  const cells: (Date | null)[] = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
  while (cells.length % 7 !== 0) cells.push(null);

  function prevMonth() {
    const d = new Date(year, month - 1, 1);
    onViewMonth(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`);
  }
  function nextMonth() {
    const d = new Date(year, month + 1, 1);
    onViewMonth(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`);
  }

  const isSelected = (d: Date) => selected && fmt(d) === selected;
  const isToday = (d: Date) => fmt(d) === fmt(today);

  // compute max count in this month for intensity buckets
  const monthPrefix = `${year}-${String(month+1).padStart(2,'0')}`;
  const monthCounts = Object.entries(counts).filter(([k]) => k.startsWith(monthPrefix)).map(([,v]) => v);
  const maxCount = monthCounts.length ? Math.max(...monthCounts) : 0;

  return (
    <div className="rounded-2xl border bg-white p-3">
      <div className="flex items-center justify-between mb-2">
        <button className="rounded border px-2 py-1 text-sm hover:bg-gray-50" onClick={prevMonth}>
          ←
        </button>
        <div className="text-sm font-medium">
          {start.toLocaleString(undefined, { month: "long", year: "numeric" })}
        </div>
        <button className="rounded border px-2 py-1 text-sm hover:bg-gray-50" onClick={nextMonth}>
          →
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-[11px] text-gray-500 mb-1">
        {["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((d)=> (
          <div key={d} className="text-center">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((d, i) => {
          const key = d ? fmt(d) : "";
          const c = key ? (counts[key] || 0) : 0;
          let intensity = "";
          if (d && c > 0 && maxCount > 0) {
            const ratio = c / maxCount;
            if (ratio > 0.66) intensity = " bg-emerald-200 border-emerald-400 text-emerald-900";
            else if (ratio > 0.33) intensity = " bg-emerald-100 border-emerald-300 text-emerald-800";
            else intensity = " bg-emerald-50 border-emerald-200 text-emerald-700";
          } else if (d && c === 0) {
            intensity = " text-gray-400";
          }
          const base = d && isSelected(d)
            ? " bg-gray-900 text-white border-gray-900"
            : d && isToday(d)
            ? " bg-gray-100 border-gray-300"
            : " bg-white hover:bg-gray-50 border-gray-300";
          return (
            <button
              key={i}
              disabled={!d}
              onClick={() => d && onSelect(fmt(d))}
              className={
                "h-8 rounded text-sm border " +
                (!d ? "opacity-0 pointer-events-none" : "") +
                (d ? base : "") +
                (d ? intensity : "")
              }
              title={d ? (c ? `${key}: ${c} papers` : key) : undefined}
            >
              {d ? d.getDate() : ""}
            </button>
          );
        })}
      </div>
      <div className="mt-2 flex items-center gap-2">
        <button
          className="rounded-xl border px-2 py-1 text-xs hover:bg-gray-50"
          onClick={() => onSelect("")}
        >
          Clear
        </button>
        <button
          className="rounded-xl border px-2 py-1 text-xs hover:bg-gray-50"
          onClick={() => onSelect(fmt(today))}
        >
          Today
        </button>
      </div>
    </div>
  );
}
