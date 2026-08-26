"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Constraint, Guest, SeatingResponse, Table } from "@/lib/types";
import { ApiError, optimiseSeating, shuffleSeating } from "@/lib/api";
import TableDiagram from "./TableDiagram";

function seatNamesForTable(result: SeatingResponse, tableId: Table["id"]) {
  const seatMap = result.table_assignments[String(tableId)] ?? {};
  const names: Record<number, string> = {};
  for (const [seatIndex, guest] of Object.entries(seatMap)) {
    names[Number(seatIndex)] = guest.name;
  }
  return names;
}

// Flattened {table, seat, guestName} rows, sorted by seat -- used by the list
// view and by name search. A dense SVG chart with 100+ small seat labels
// doesn't stay legible; a plain sortable/searchable list does.
function seatRowsForTable(result: SeatingResponse, tableId: Table["id"]) {
  const seatMap = result.table_assignments[String(tableId)] ?? {};
  return Object.entries(seatMap)
    .map(([seatIndex, guest]) => ({ seatIndex: Number(seatIndex), guest }))
    .sort((a, b) => a.seatIndex - b.seatIndex);
}

// "Table 3" reads fine for banquet/cabaret, but theatre seating isn't
// organised around tables at all -- it's rows facing a stage.
function tableLabel(table: Table) {
  return table.type === "theatre" ? `Section ${table.id}` : `Table ${table.id}`;
}

// Theatre seat indices run row-major (row * seatsPerRow + col), so grouping
// by row and showing seat position *within* the row is how a guest would
// actually look themselves up ("row 3, seat 2"), not a flat, meaningless
// running seat count.
function rowGroupsForTheatre(
  result: SeatingResponse,
  table: Extract<Table, { type: "theatre" }>
) {
  const seatsPerRow = table.num_seats / table.num_rows;
  const rows: { rowIndex: number; seats: { colIndex: number; guest: Guest }[] }[] = Array.from(
    { length: table.num_rows },
    (_, rowIndex) => ({ rowIndex, seats: [] })
  );
  for (const { seatIndex, guest } of seatRowsForTable(result, table.id)) {
    const rowIndex = Math.floor(seatIndex / seatsPerRow);
    const colIndex = seatIndex % seatsPerRow;
    rows[rowIndex]?.seats.push({ colIndex, guest });
  }
  for (const row of rows) row.seats.sort((a, b) => a.colIndex - b.colIndex);
  return rows;
}

function matchingSeatsForTable(
  result: SeatingResponse,
  tableId: Table["id"],
  matchingGuestIds: Set<Guest["id"]>
) {
  const seatMap = result.table_assignments[String(tableId)] ?? {};
  const seats = new Set<number>();
  for (const [seatIndex, guest] of Object.entries(seatMap)) {
    if (matchingGuestIds.has(guest.id)) seats.add(Number(seatIndex));
  }
  return seats;
}

function csvCell(value: string) {
  return `"${value.replace(/"/g, '""')}"`;
}

const TABLE_TYPE_LABEL: Record<Table["type"], string> = {
  banquet: "Banquet",
  cabaret: "Cabaret",
  theatre: "Theatre",
};

function downloadSeatingCsv(result: SeatingResponse, tables: Table[]) {
  const header = ["Table", "Table Type", "Seat", "Guest Name"];
  const rows = tables.flatMap((table) =>
    seatRowsForTable(result, table.id).map(({ seatIndex, guest }) => [
      String(table.id),
      TABLE_TYPE_LABEL[table.type],
      String(seatIndex),
      guest.name,
    ])
  );
  const csv = [header, ...rows]
    .map((row) => row.map(csvCell).join(","))
    .join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "seating-plan.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function ExportMenu({
  onDownloadCsv,
  onPrint,
}: {
  onDownloadCsv: () => void;
  onPrint: () => void;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function onPointerDown(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative print:hidden" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-full border-2 border-slate-200 text-slate-600 px-4 py-2 text-sm font-semibold hover:border-brand-dark hover:text-brand-dark transition-colors whitespace-nowrap"
      >
        Export ▾
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-brand-glow border border-slate-100 py-1 z-20"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onDownloadCsv();
            }}
            className="block w-full text-left px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-brand-dark transition-colors"
          >
            Download CSV
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onPrint();
            }}
            className="block w-full text-left px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-brand-dark transition-colors"
          >
            Print / Save as PDF
          </button>
        </div>
      )}
    </div>
  );
}

export default function Step3Results({
  guests,
  tables,
  constraints,
  onBack,
}: {
  guests: Guest[];
  tables: Table[];
  constraints: Constraint[];
  onBack: () => void;
}) {
  const [status, setStatus] = useState<"loading" | "error" | "done">("loading");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SeatingResponse | null>(null);
  const [view, setView] = useState<"chart" | "list">("chart");
  const [search, setSearch] = useState("");
  const [shuffling, setShuffling] = useState(false);
  const [shuffleError, setShuffleError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    optimiseSeating({ guests, tables, constraints })
      .then((response) => {
        if (cancelled) return;
        setResult(response);
        setStatus("done");
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : "Something went wrong.");
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleShuffle() {
    setShuffling(true);
    setShuffleError(null);
    try {
      const response = await shuffleSeating({ guests, tables, constraints });
      setResult(response);
    } catch (e) {
      setShuffleError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setShuffling(false);
    }
  }

  const query = search.trim().toLowerCase();
  const violationCount =
    (result?.must_sit_together_violations.length ?? 0) +
    (result?.must_sit_apart_violations.length ?? 0);

  // Theatre seats only connect within a row (see TheatreSection.adjacency in
  // schema.py), so two guests in the same section but different rows already
  // count as "apart" -- what a must_sit_apart violation actually means there
  // is "same row", not "same section". All tables share one style per plan
  // (see buildTables in app/page.tsx), so checking the first table is enough.
  const sharedSeatingUnit = tables[0]?.type === "theatre" ? "in the same row" : "on the same table";

  const matchingGuestIds = useMemo(() => {
    if (!query) return null;
    return new Set(
      guests.filter((g) => g.name.toLowerCase().includes(query)).map((g) => g.id)
    );
  }, [query, guests]);

  return (
    <div>
      <h2 className="text-2xl font-display font-bold text-brand-dark text-center mb-2">
        {status === "done" ? "Your seating plan" : "Optimising your seating plan..."}
      </h2>
      {status === "done" && (
        <p className="print:hidden text-center text-slate-500 mb-8">
          Now make it your own — have a look through and see if anything needs a personal touch.
        </p>
      )}

      {status !== "done" && (
        <div className="p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100 text-center">
          <p className="text-slate-600">
            {guests.length} guests across {tables.length}{" "}
            {tables.length === 1 ? "table" : "tables"}, {constraints.length}{" "}
            constraint{constraints.length === 1 ? "" : "s"}.
          </p>
          {status === "error" && (
            <p className="text-sm text-red-600 mt-4">{error}</p>
          )}
        </div>
      )}

      {status === "done" && result && (
        <>
          <div className="flex flex-wrap gap-4 justify-center mb-6 text-sm">
            <span className="bg-slate-50 rounded-lg px-3 py-2">
              Must sit together: {result.must_sit_together.satisfied}/
              {result.must_sit_together.total}
            </span>
            <span className="bg-slate-50 rounded-lg px-3 py-2">
              Could sit together: {result.could_sit_together.satisfied}/
              {result.could_sit_together.total}
            </span>
            <span className="bg-slate-50 rounded-lg px-3 py-2">
              Must sit apart: {result.must_sit_apart.satisfied}/
              {result.must_sit_apart.total}
            </span>
          </div>

          {violationCount > 0 && (
            <div className="mb-8 text-sm text-amber-700 bg-amber-50 rounded-lg p-4 max-w-2xl mx-auto">
              <p className="font-semibold mb-2">
                {violationCount} &quot;must&quot; constraint{violationCount === 1 ? "" : "s"} couldn&apos;t be
                satisfied:
              </p>
              <ul className="list-disc list-inside space-y-1 max-h-48 overflow-y-auto">
                {result.must_sit_together_violations.map((v, i) => (
                  <li key={`together-${i}`}>
                    <strong>{v.guest_a.name}</strong> and <strong>{v.guest_b.name}</strong> should
                    sit together, but don&apos;t.
                  </li>
                ))}
                {result.must_sit_apart_violations.map((v, i) => (
                  <li key={`apart-${i}`}>
                    <strong>{v.guest_a.name}</strong> and <strong>{v.guest_b.name}</strong> should
                    sit apart, but are {sharedSeatingUnit}.
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="print:hidden flex flex-wrap gap-3 items-center justify-between mb-6">
            <div className="inline-flex rounded-full border border-slate-200 p-1 bg-white">
              <button
                type="button"
                onClick={() => setView("chart")}
                className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
                  view === "chart" ? "bg-brand-dark text-white" : "text-slate-500"
                }`}
              >
                Chart
              </button>
              <button
                type="button"
                onClick={() => setView("list")}
                className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
                  view === "list" ? "bg-brand-dark text-white" : "text-slate-500"
                }`}
              >
                List
              </button>
            </div>
            <div className="flex gap-3 items-center">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Find a guest by name..."
                className="border-2 border-slate-200 rounded-lg p-2 text-sm w-56 focus:border-brand-dark outline-none"
              />
              <button
                type="button"
                onClick={handleShuffle}
                disabled={shuffling}
                className="rounded-full border-2 border-slate-200 text-slate-600 px-4 py-2 text-sm font-semibold hover:border-brand-dark hover:text-brand-dark transition-colors whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {shuffling ? "Shuffling..." : "Shuffle"}
              </button>
              <ExportMenu
                onDownloadCsv={() => downloadSeatingCsv(result, tables)}
                onPrint={() => window.print()}
              />
            </div>
          </div>

          {shuffleError && (
            <p className="print:hidden text-sm text-red-600 text-center -mt-3 mb-6">{shuffleError}</p>
          )}

          {view === "chart" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 print:grid-cols-1 gap-8 print:gap-6">
              {tables.map((table) => (
                <div
                  key={table.id}
                  className="p-6 bg-white rounded-2xl shadow-brand-glow border border-slate-100 print:shadow-none print:break-inside-avoid"
                >
                  <h3 className="text-sm font-bold text-slate-500 mb-2 text-center">
                    {tableLabel(table)}
                  </h3>
                  <div className="h-72">
                    <TableDiagram
                      type={table.type}
                      numSeats={table.num_seats}
                      numRows={table.type === "theatre" ? table.num_rows : undefined}
                      headSeat={table.type === "banquet" ? table.head_seat : undefined}
                      footSeat={table.type === "banquet" ? table.foot_seat : undefined}
                      seatNames={seatNamesForTable(result, table.id)}
                      highlightedSeats={
                        matchingGuestIds
                          ? matchingSeatsForTable(result, table.id, matchingGuestIds)
                          : null
                      }
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {tables.map((table) => {
                if (table.type === "theatre") {
                  const rowGroups = rowGroupsForTheatre(result, table)
                    .map((row) => ({
                      ...row,
                      seats: row.seats.filter(
                        ({ guest }) => !matchingGuestIds || matchingGuestIds.has(guest.id)
                      ),
                    }))
                    .filter((row) => row.seats.length > 0);
                  if (matchingGuestIds && rowGroups.length === 0) return null;
                  return (
                    <div
                      key={table.id}
                      className="p-5 bg-white rounded-2xl shadow-brand-glow border border-slate-100 print:shadow-none print:break-inside-avoid"
                    >
                      <h3 className="text-sm font-bold text-slate-500 mb-3">{tableLabel(table)}</h3>
                      <div className="space-y-3">
                        {rowGroups.map((row) => (
                          <div key={row.rowIndex}>
                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">
                              Row {row.rowIndex + 1}
                            </p>
                            <ul className="text-sm divide-y divide-slate-100">
                              {row.seats.map(({ colIndex, guest }) => (
                                <li
                                  key={colIndex}
                                  className={`flex justify-between py-1.5 ${
                                    matchingGuestIds?.has(guest.id)
                                      ? "bg-brand-light -mx-2 px-2 rounded"
                                      : ""
                                  }`}
                                >
                                  <span className="text-slate-400 w-8">{colIndex + 1}</span>
                                  <span className="flex-1">{guest.name}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                }

                const rows = seatRowsForTable(result, table.id).filter(
                  (row) => !matchingGuestIds || matchingGuestIds.has(row.guest.id)
                );
                if (matchingGuestIds && rows.length === 0) return null;
                return (
                  <div
                    key={table.id}
                    className="p-5 bg-white rounded-2xl shadow-brand-glow border border-slate-100 print:shadow-none print:break-inside-avoid"
                  >
                    <h3 className="text-sm font-bold text-slate-500 mb-3">{tableLabel(table)}</h3>
                    <ul className="text-sm divide-y divide-slate-100">
                      {rows.map(({ seatIndex, guest }) => (
                        <li
                          key={seatIndex}
                          className={`flex justify-between py-1.5 ${
                            matchingGuestIds?.has(guest.id) ? "bg-brand-light -mx-2 px-2 rounded" : ""
                          }`}
                        >
                          <span className="text-slate-400 w-8">{seatIndex}</span>
                          <span className="flex-1">{guest.name}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      <div className="print:hidden mt-8 flex justify-start">
        <button
          type="button"
          onClick={onBack}
          className="rounded-full border-2 border-slate-200 text-slate-600 px-6 py-3 font-semibold hover:border-brand-dark hover:text-brand-dark transition-colors"
        >
          Back
        </button>
      </div>
    </div>
  );
}
