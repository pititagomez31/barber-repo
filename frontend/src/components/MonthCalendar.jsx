import { useState } from "react";
import { MONTHS, WEEKDAYS, fmtDate, jsDayToKey } from "@/lib/api";
import { ChevronLeft, ChevronRight } from "lucide-react";

/**
 * Reusable month grid.
 * props:
 *  - anchor: Date (any date in the visible month)
 *  - onAnchorChange(Date)
 *  - selected: "YYYY-MM-DD" | null
 *  - onSelect(dateStr)
 *  - markedDates: Set<string> (gold dot)
 *  - offDates: Set<string> (closed marker)
 *  - disablePast: bool
 */
export default function MonthCalendar({
  anchor,
  onAnchorChange,
  selected,
  onSelect,
  markedDates = new Set(),
  offDates = new Set(),
  disablePast = false,
}) {
  const [internal, setInternal] = useState(anchor || new Date());
  const cur = anchor || internal;
  const setCur = onAnchorChange || setInternal;

  const year = cur.getFullYear();
  const month = cur.getMonth();
  const firstDay = new Date(year, month, 1);
  const leadKey = Number(jsDayToKey(firstDay.getDay())); // 0=Mon
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const todayStr = fmtDate(new Date());
  const cells = [];
  for (let i = 0; i < leadKey; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const go = (delta) => setCur(new Date(year, month + delta, 1));

  return (
    <div data-testid="month-calendar">
      <div className="flex items-center justify-between mb-4">
        <button
          type="button"
          onClick={() => go(-1)}
          data-testid="cal-prev"
          className="p-2 rounded-full hover:bg-[#242017] transition-colors"
        >
          <ChevronLeft size={18} />
        </button>
        <div className="display text-2xl" data-testid="cal-title">
          {MONTHS[month]} {year}
        </div>
        <button
          type="button"
          onClick={() => go(1)}
          data-testid="cal-next"
          className="p-2 rounded-full hover:bg-[#242017] transition-colors"
        >
          <ChevronRight size={18} />
        </button>
      </div>
      <div className="cal-grid mb-2">
        {WEEKDAYS.map((w) => (
          <div key={w.key} className="cal-dow">{w.short}</div>
        ))}
      </div>
      <div className="cal-grid">
        {cells.map((d, i) => {
          if (d === null) return <div key={`e${i}`} className="cal-cell empty" />;
          const ds = fmtDate(new Date(year, month, d));
          const isPast = disablePast && ds < todayStr;
          const classes = ["cal-cell"];
          if (selected === ds) classes.push("selected");
          if (ds === todayStr) classes.push("today");
          if (isPast) classes.push("muted");
          if (offDates.has(ds)) classes.push("off");
          return (
            <button
              key={ds}
              type="button"
              disabled={isPast}
              data-testid={`cal-day-${ds}`}
              className={classes.join(" ")}
              onClick={() => onSelect(ds)}
            >
              {d}
              {markedDates.has(ds) && <span className="cal-dot" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
