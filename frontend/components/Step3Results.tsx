"use client";

import { useEffect, useMemo, useState } from "react";
import { Constraint, Guest, SeatingResponse, Table } from "@/lib/types";
import { ApiError, optimiseSeating } from "@/lib/api";
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

function downloadSeatingCsv(result: SeatingResponse, tables: Table[]) {
  const header = ["Table", "Seat", "Guest Name"];
  const rows = tables.flatMap((table) =>
    seatRowsForTable(result, table.id).map(({ seatIndex, guest }) => [
      String(table.id),
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

  const query = search.trim().toLowerCase();
  const violationCount =
    (result?.must_sit_together_violations.length ?? 0) +
    (result?.must_sit_apart_violations.length ?? 0);

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
        <p className="text-center text-slate-500 mb-8">
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
              Score: <strong>{result.avg_score.toFixed(2)}</strong>
            </span>
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
                    sit apart, but are seated together.
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-3 items-center justify-between mb-6">
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
                onClick={() => downloadSeatingCsv(result, tables)}
                className="rounded-full border-2 border-slate-200 text-slate-600 px-4 py-2 text-sm font-semibold hover:border-brand-dark hover:text-brand-dark transition-colors whitespace-nowrap"
              >
                Download CSV
              </button>
            </div>
          </div>

          {view === "chart" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {tables.map((table) => (
                <div
                  key={table.id}
                  className="p-6 bg-white rounded-2xl shadow-brand-glow border border-slate-100"
                >
                  <h3 className="text-sm font-bold text-slate-500 mb-2 text-center">
                    Table {table.id}
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
                const rows = seatRowsForTable(result, table.id).filter(
                  (row) => !matchingGuestIds || matchingGuestIds.has(row.guest.id)
                );
                if (matchingGuestIds && rows.length === 0) return null;
                return (
                  <div
                    key={table.id}
                    className="p-5 bg-white rounded-2xl shadow-brand-glow border border-slate-100"
                  >
                    <h3 className="text-sm font-bold text-slate-500 mb-3">Table {table.id}</h3>
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

      <div className="mt-8 flex justify-start">
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
