"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Constraint, Guest, SeatAssignment, SeatingResponse, Table } from "@/lib/types";
import {
  ApiError,
  evaluateSeating,
  optimiseSeating,
  sendFeedback,
  shuffleSeating,
} from "@/lib/api";
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
  const rows: {
    rowIndex: number;
    seats: { colIndex: number; seatIndex: number; guest: Guest }[];
  }[] = Array.from(
    { length: table.num_rows },
    (_, rowIndex) => ({ rowIndex, seats: [] })
  );
  for (const { seatIndex, guest } of seatRowsForTable(result, table.id)) {
    const rowIndex = Math.floor(seatIndex / seatsPerRow);
    const colIndex = seatIndex % seatsPerRow;
    rows[rowIndex]?.seats.push({ colIndex, seatIndex, guest });
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

/** A seat's address. Table ids are compared as strings: once the response has
 *  crossed JSON, table_assignments is keyed by the string form regardless of
 *  whether the id was a number on the Python side. */
interface SeatRef {
  tableId: string;
  seatIndex: number;
}

const sameSeat = (a: SeatRef, b: SeatRef) =>
  a.tableId === b.tableId && a.seatIndex === b.seatIndex;

/** Exchanges the occupants of two seats, either of which may be empty. */
function withSeatsSwapped(
  assignments: SeatingResponse["table_assignments"],
  a: SeatRef,
  b: SeatRef
): SeatingResponse["table_assignments"] {
  const next: SeatingResponse["table_assignments"] = {};
  for (const [tableId, seats] of Object.entries(assignments)) {
    next[tableId] = { ...seats };
  }
  next[a.tableId] ??= {};
  next[b.tableId] ??= {};

  const guestA = next[a.tableId][String(a.seatIndex)];
  const guestB = next[b.tableId][String(b.seatIndex)];

  // An empty seat has no entry at all rather than a null one, so moving a guest
  // onto one has to delete the seat they came from.
  if (guestB) next[a.tableId][String(a.seatIndex)] = guestB;
  else delete next[a.tableId][String(a.seatIndex)];

  if (guestA) next[b.tableId][String(b.seatIndex)] = guestA;
  else delete next[b.tableId][String(b.seatIndex)];

  return next;
}

function toAssignmentPayload(
  assignments: SeatingResponse["table_assignments"]
): SeatAssignment {
  const payload: SeatAssignment = {};
  for (const [tableId, seats] of Object.entries(assignments)) {
    payload[tableId] = {};
    for (const [seatIndex, guest] of Object.entries(seats)) {
      payload[tableId][Number(seatIndex)] = guest.id;
    }
  }
  return payload;
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

/** Asked at the point the plan exists, rather than in the footer: this is the
 *  one moment the visitor knows whether the tool worked for them. */
function FeedbackPrompt({
  guestCount,
  tableCount,
  constraintCount,
}: {
  guestCount: number;
  tableCount: number;
  constraintCount: number;
}) {
  const [verdict, setVerdict] = useState<"up" | "down" | null>(null);
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState(false);

  async function choose(next: "up" | "down") {
    setVerdict(next);
    // Sent straight away, so a verdict still counts even if the comment box is
    // then ignored -- which it usually will be.
    await sendFeedback({
      verdict: next,
      guest_count: guestCount,
      table_count: tableCount,
      constraint_count: constraintCount,
    });
  }

  async function submitComment() {
    if (!verdict) return;
    await sendFeedback({
      verdict,
      message: message.trim(),
      guest_count: guestCount,
      table_count: tableCount,
      constraint_count: constraintCount,
    });
    setSent(true);
  }

  if (sent) {
    return (
      <div className="print:hidden mt-10 text-center text-sm text-slate-500">
        Thank you — that&apos;s genuinely useful.
      </div>
    );
  }

  return (
    <div className="print:hidden mt-10 pt-6 border-t border-slate-200 text-center">
      {verdict === null ? (
        <div className="flex flex-wrap items-center justify-center gap-3">
          <span className="text-sm text-slate-500">Did this give you a usable plan?</span>
          <button
            type="button"
            onClick={() => choose("up")}
            className="rounded-full border-2 border-slate-200 px-4 py-1.5 text-sm font-semibold text-slate-600 hover:border-brand-dark hover:text-brand-dark transition-colors"
          >
            Yes
          </button>
          <button
            type="button"
            onClick={() => choose("down")}
            className="rounded-full border-2 border-slate-200 px-4 py-1.5 text-sm font-semibold text-slate-600 hover:border-brand-dark hover:text-brand-dark transition-colors"
          >
            Not really
          </button>
        </div>
      ) : (
        <div className="max-w-md mx-auto">
          <label htmlFor="feedback-message" className="block text-sm text-slate-500 mb-2">
            {verdict === "up"
              ? "Thanks! Anything that would have made it easier?"
              : "Sorry about that — what went wrong?"}
          </label>
          <textarea
            id="feedback-message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            maxLength={2000}
            className="w-full border-2 border-slate-200 rounded-lg p-3 text-sm focus:border-brand-dark outline-none resize-y"
          />
          <div className="flex items-center justify-center gap-3 mt-3">
            <button
              type="button"
              onClick={submitComment}
              disabled={!message.trim()}
              className="rounded-full bg-brand-dark text-white px-5 py-2 text-sm font-semibold hover:bg-brand-dark/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Send
            </button>
            <button
              type="button"
              onClick={() => setSent(true)}
              className="text-sm text-slate-400 hover:text-brand-dark"
            >
              No thanks
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** One guest in the list view: tappable to swap, and draggable with a mouse. */
function SeatListRow({
  seat,
  position,
  guest,
  isMatch,
  selectedSeat,
  onActivate,
  onDropOn,
}: {
  seat: SeatRef;
  position: number;
  guest: Guest;
  isMatch: boolean;
  selectedSeat: SeatRef | null;
  onActivate: (seat: SeatRef) => void;
  onDropOn: (from: SeatRef, to: SeatRef) => void;
}) {
  const isSelected = selectedSeat != null && sameSeat(selectedSeat, seat);

  return (
    <li
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", JSON.stringify(seat));
        e.dataTransfer.effectAllowed = "move";
      }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        try {
          const from = JSON.parse(e.dataTransfer.getData("text/plain")) as SeatRef;
          if (!sameSeat(from, seat)) onDropOn(from, seat);
        } catch {
          // Something other than a seat was dropped -- ignore it.
        }
      }}
      onClick={() => onActivate(seat)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onActivate(seat);
        }
      }}
      role="button"
      tabIndex={0}
      aria-pressed={isSelected}
      className={`flex justify-between py-1.5 -mx-2 px-2 rounded cursor-grab print:cursor-auto transition-colors ${
        isSelected
          ? "bg-amber-100 ring-2 ring-amber-400"
          : isMatch
            ? "bg-brand-light"
            : "hover:bg-slate-50"
      }`}
    >
      <span className="text-slate-400 w-8">{position}</span>
      <span className="flex-1">{guest.name}</span>
    </li>
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
  // The last plan the optimiser produced, kept so hand-edits can be undone
  // without paying for another solve.
  const [optimisedResult, setOptimisedResult] = useState<SeatingResponse | null>(null);
  const [selectedSeat, setSelectedSeat] = useState<SeatRef | null>(null);
  const [edited, setEdited] = useState(false);
  const [rescoreFailed, setRescoreFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    optimiseSeating({ guests, tables, constraints })
      .then((response) => {
        if (cancelled) return;
        setResult(response);
        setOptimisedResult(response);
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
      setOptimisedResult(response);
      setSelectedSeat(null);
      setEdited(false);
      setRescoreFailed(false);
    } catch (e) {
      setShuffleError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setShuffling(false);
    }
  }

  // Tap one seat then another, rather than drag only: the same gesture has to
  // work on a phone, where a wedding plan is as likely to be tweaked as on a
  // laptop, and HTML5 drag events don't fire on touch at all.
  async function handleSeatActivate(seat: SeatRef) {
    if (!result) return;
    if (suppressNextClick.current) return;

    if (!selectedSeat) {
      // An empty seat can't start a swap -- there's nobody in it to move.
      if (!result.table_assignments[seat.tableId]?.[String(seat.seatIndex)]) return;
      setSelectedSeat(seat);
      return;
    }
    if (sameSeat(selectedSeat, seat)) {
      setSelectedSeat(null);
      return;
    }
    await applySwap(selectedSeat, seat);
  }

  async function applySwap(from: SeatRef, to: SeatRef) {
    if (!result) return;
    const swapped = withSeatsSwapped(result.table_assignments, from, to);
    setSelectedSeat(null);
    setEdited(true);
    // Shown immediately, then re-scored: the seats are the user's to move, so
    // the chart should never wait on the network to reflect what they just did.
    setResult({ ...result, table_assignments: swapped });

    try {
      const rescored = await evaluateSeating({
        guests,
        tables,
        constraints,
        assignment: toAssignmentPayload(swapped),
      });
      setResult(rescored);
      setRescoreFailed(false);
    } catch {
      // The arrangement on screen is still the user's; only the counts are now
      // out of date, which the banner says explicitly rather than quietly
      // showing stale numbers as if they were current.
      setRescoreFailed(true);
    }
  }

  // Dragging in the chart is handled here rather than per-seat, because one
  // handler on the grid can resolve any seat in any table from the data
  // attributes TableDiagram stamps on. HTML5 drag-and-drop isn't used: it is
  // unreliable on SVG and never fires on touch at all.
  const dragFrom = useRef<SeatRef | null>(null);
  // A drag ends in a click event too. Without this the swap would be followed
  // by the tap handler picking the dropped-on seat straight back up.
  const suppressNextClick = useRef(false);

  function seatRefFromPoint(x: number, y: number): SeatRef | null {
    const element = document.elementFromPoint(x, y);
    const seat = element?.closest<HTMLElement>("[data-seat-index]");
    const table = element?.closest<HTMLElement>("[data-table-id]");
    if (!seat || !table) return null;
    const tableId = table.dataset.tableId;
    const seatIndex = Number(seat.dataset.seatIndex);
    if (tableId === undefined || Number.isNaN(seatIndex)) return null;
    return { tableId, seatIndex };
  }

  function handleChartPointerDown(e: React.PointerEvent) {
    // Cleared at the start of every interaction rather than when the suppressed
    // click arrives, because a drag between two different elements fires no
    // click at all -- the flag would otherwise survive and swallow the next
    // genuine tap instead.
    suppressNextClick.current = false;
    // Mouse only. On touch, starting a drag would have to cancel page
    // scrolling to work, and tapping two seats already does the job there.
    if (e.pointerType !== "mouse") return;
    const target = (e.target as HTMLElement).closest<HTMLElement>("[data-seat-index]");
    if (!target || target.dataset.seatFilled !== "true") return;
    dragFrom.current = seatRefFromPoint(e.clientX, e.clientY);
  }

  function handleChartPointerUp(e: React.PointerEvent) {
    const from = dragFrom.current;
    dragFrom.current = null;
    if (!from) return;
    const to = seatRefFromPoint(e.clientX, e.clientY);
    // Released on the same seat (or outside any seat): leave it to the click
    // handler, so a plain click still means "pick this guest up".
    if (!to || sameSeat(from, to)) return;
    suppressNextClick.current = true;
    void applySwap(from, to);
  }

  function resetToOptimised() {
    if (!optimisedResult) return;
    setResult(optimisedResult);
    setSelectedSeat(null);
    setEdited(false);
    setRescoreFailed(false);
  }

  const selectedGuestName =
    selectedSeat && result
      ? result.table_assignments[selectedSeat.tableId]?.[String(selectedSeat.seatIndex)]?.name
      : undefined;

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
        <p className="print:hidden text-center text-slate-500 mb-6">
          Now make it your own — drag a guest onto another seat to swap them over, or
          tap one seat and then the other.
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
          {selectedSeat && (
            <div
              role="status"
              className="print:hidden fixed inset-x-0 bottom-0 z-50 flex justify-center px-4 pb-4"
            >
              <div className="flex flex-wrap items-center justify-center gap-3 bg-amber-50 border border-amber-200 shadow-brand-glow rounded-full px-5 py-3 text-sm">
                <span className="text-amber-800">
                  <strong>{selectedGuestName}</strong> picked up — now choose the seat to swap
                  them with.
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedSeat(null)}
                  className="font-semibold text-amber-800 hover:underline"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Height is reserved whether or not there is anything to say, so the
              chart below doesn't jump the first time a message appears. */}
          <div className="print:hidden mb-4 min-h-6 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-sm text-slate-500">
            {edited && (
              <>
                <span>You&apos;ve edited this plan by hand.</span>
                <button
                  type="button"
                  onClick={resetToOptimised}
                  className="font-semibold text-brand-dark hover:underline"
                >
                  Reset to the optimised plan
                </button>
              </>
            )}
            {rescoreFailed && (
              <span className="text-amber-700">
                Your change is saved on screen, but the counts couldn&apos;t be rechecked just
                now.
              </span>
            )}
          </div>

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
            <div
              className="grid grid-cols-1 md:grid-cols-2 print:grid-cols-1 gap-8 print:gap-6"
              onPointerDown={handleChartPointerDown}
              onPointerUp={handleChartPointerUp}
            >
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
                      tableId={String(table.id)}
                      seatNames={seatNamesForTable(result, table.id)}
                      highlightedSeats={
                        matchingGuestIds
                          ? matchingSeatsForTable(result, table.id, matchingGuestIds)
                          : null
                      }
                      selectedSeat={
                        selectedSeat?.tableId === String(table.id)
                          ? selectedSeat.seatIndex
                          : null
                      }
                      onSeatClick={(seatIndex) =>
                        handleSeatActivate({ tableId: String(table.id), seatIndex })
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
                              {row.seats.map(({ colIndex, seatIndex, guest }) => (
                                <SeatListRow
                                  key={colIndex}
                                  seat={{ tableId: String(table.id), seatIndex }}
                                  position={colIndex + 1}
                                  guest={guest}
                                  isMatch={matchingGuestIds?.has(guest.id) ?? false}
                                  selectedSeat={selectedSeat}
                                  onActivate={handleSeatActivate}
                                  onDropOn={applySwap}
                                />
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
                        <SeatListRow
                          key={seatIndex}
                          seat={{ tableId: String(table.id), seatIndex }}
                          position={seatIndex}
                          guest={guest}
                          isMatch={matchingGuestIds?.has(guest.id) ?? false}
                          selectedSeat={selectedSeat}
                          onActivate={handleSeatActivate}
                          onDropOn={applySwap}
                        />
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {status === "done" && result && violationCount > 0 && (
        <div className="print:hidden">
            <div className="mt-8 text-sm text-amber-700 bg-amber-50 rounded-lg p-4 max-w-2xl mx-auto">
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
        </div>
      )}

      {status === "done" && result && (
        <FeedbackPrompt
          guestCount={guests.length}
          tableCount={tables.length}
          constraintCount={constraints.length}
        />
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
