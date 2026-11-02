import { TableStyle } from "@/lib/types";

interface TableDiagramProps {
  type: TableStyle;
  numSeats: number;
  numRows?: number; // theatre only
  headSeat?: boolean; // banquet only
  footSeat?: boolean; // banquet only
  seatNames?: Record<number, string>; // seat index -> guest name
  compact?: boolean; // small, unlabeled preview (used in the step 1 style picker)
  onSeatClick?: (seatIndex: number) => void;
  // Non-null (even if empty) means a search is active: seats in the set are
  // highlighted, other filled seats are dimmed so the match actually stands
  // out at high seat counts. Null/undefined means no search -- render as normal.
  highlightedSeats?: Set<number> | null;
  // The seat the user has picked up, mid-swap. Styled distinctly from a search
  // match: a match is "look here", a selection is "this one is in your hand".
  selectedSeat?: number | null;
  // Stamped onto the rendered SVG as data-table-id so a pointer landing
  // anywhere inside it can be traced back to this table (see Step3Results).
  tableId?: string;
}

type Anchor = "start" | "middle" | "end";
type Baseline = "hanging" | "central" | "auto";

interface SeatPosition {
  seatIndex: number;
  x: number;
  y: number;
  labelX: number;
  labelY: number;
  anchor: Anchor;
  baseline: Baseline;
}

const SEAT_R = 14;
const LABEL_GAP = 8; // gap between seat circle edge and where label text starts

function banquetLayout(numSeats: number, headSeat: boolean, footSeat: boolean) {
  const rowH = 40;
  const tableW = 70;
  const numSideSeats = numSeats - Number(headSeat) - Number(footSeat);
  const numRows = Math.ceil(numSideSeats / 2);
  const tableH = numRows * rowH;

  const seats: SeatPosition[] = [];
  let offset = 0;
  if (headSeat) {
    const y = -28;
    seats.push({
      seatIndex: 0,
      x: 0,
      y,
      labelX: 0,
      labelY: y - SEAT_R - LABEL_GAP,
      anchor: "middle",
      baseline: "auto",
    });
    offset = 1;
  }
  for (let i = 0; i < numSideSeats; i++) {
    const idx = i + offset;
    const row = Math.floor(i / 2);
    const side = i % 2 === 0 ? 1 : -1;
    const x = side * (tableW / 2 + 24);
    const y = row * rowH + rowH / 2;
    // Label goes further out to the side (away from the table), never above
    // or below -- that's what stops it colliding with the next row's seat.
    seats.push({
      seatIndex: idx,
      x,
      y,
      labelX: x + side * (SEAT_R + LABEL_GAP),
      labelY: y,
      anchor: side > 0 ? "start" : "end",
      baseline: "central",
    });
  }
  if (footSeat) {
    const y = tableH + 28;
    seats.push({
      seatIndex: numSeats - 1,
      x: 0,
      y,
      labelX: 0,
      labelY: y + SEAT_R + LABEL_GAP,
      anchor: "middle",
      baseline: "hanging",
    });
  }

  return {
    seats,
    table: { shape: "rect" as const, x: -tableW / 2, y: 0, w: tableW, h: tableH },
    viewBox: `${-tableW / 2 - 95} ${-70} ${tableW + 190} ${tableH + 140}`,
  };
}

function cabaretLayout(numSeats: number) {
  const tableR = 42;
  const orbitR = tableR + 26;
  const labelOrbitR = orbitR + SEAT_R + LABEL_GAP;
  const seats: SeatPosition[] = [];
  for (let i = 0; i < numSeats; i++) {
    const angle = Math.PI / 2 - (2 * Math.PI * i) / numSeats;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    // Label sits further along the same angle as the seat -- i.e. pointing
    // away from the table center, into open space, instead of a fixed
    // "always below" offset that would point into a neighboring seat for
    // anything not at the very top of the circle.
    seats.push({
      seatIndex: i,
      x: orbitR * cos,
      y: -orbitR * sin,
      labelX: labelOrbitR * cos,
      labelY: -labelOrbitR * sin,
      anchor: cos > 0.15 ? "start" : cos < -0.15 ? "end" : "middle",
      baseline: sin > 0.15 ? "auto" : sin < -0.15 ? "hanging" : "central",
    });
  }
  const half = labelOrbitR + 55;
  return {
    seats,
    table: { shape: "circle" as const, r: tableR },
    viewBox: `${-half} ${-half} ${half * 2} ${half * 2}`,
  };
}

function theatreLayout(numSeats: number, numRows: number) {
  const colW = 42;
  const LABEL_LINE_H = 14; // vertical stagger step between adjacent columns' labels
  const rowH = 62 + LABEL_LINE_H; // tall enough that a staggered label can't reach the next row
  const numCols = numSeats / numRows;
  const seats: SeatPosition[] = [];
  for (let i = 0; i < numSeats; i++) {
    const row = Math.floor(i / numCols);
    const col = i % numCols;
    const x = col * colW - ((numCols - 1) * colW) / 2;
    const y = row * rowH + 50;
    // Adjacent seats are only colW apart -- not enough room for two full
    // names side by side at any real font size. Staggering alternating
    // columns' labels onto a second line means neighbours never fight for
    // the same vertical space, regardless of name length.
    const stagger = col % 2 === 0 ? 0 : LABEL_LINE_H;
    seats.push({
      seatIndex: i,
      x,
      y,
      labelX: x,
      labelY: y + SEAT_R + LABEL_GAP + stagger,
      anchor: "middle",
      baseline: "hanging",
    });
  }
  const width = numCols * colW + 80;
  const height = numRows * rowH + 90;
  return {
    seats,
    table: { shape: "stage" as const, width: numCols * colW },
    viewBox: `${-width / 2} ${0} ${width} ${height}`,
  };
}

export default function TableDiagram({
  type,
  numSeats,
  numRows = 1,
  headSeat = false,
  footSeat = false,
  seatNames,
  compact = false,
  onSeatClick,
  highlightedSeats = null,
  selectedSeat = null,
  tableId,
}: TableDiagramProps) {
  const layout =
    type === "banquet"
      ? banquetLayout(numSeats, headSeat, footSeat)
      : type === "cabaret"
        ? cabaretLayout(numSeats)
        : theatreLayout(numSeats, numRows);

  return (
    <svg
      data-table-id={tableId ?? undefined}
      viewBox={layout.viewBox}
      className="w-full h-full"
    >
      {layout.table.shape === "rect" && (
        <rect
          x={layout.table.x}
          y={layout.table.y}
          width={layout.table.w}
          height={layout.table.h}
          rx={4}
          className="fill-slate-100 stroke-slate-400"
        />
      )}
      {layout.table.shape === "circle" && (
        <circle
          cx={0}
          cy={0}
          r={layout.table.r}
          className="fill-slate-100 stroke-slate-400"
        />
      )}
      {layout.table.shape === "stage" && (
        <rect
          x={-layout.table.width / 2}
          y={0}
          width={layout.table.width}
          height={20}
          rx={3}
          className="fill-slate-300 stroke-slate-400"
        />
      )}

      {layout.seats.map((seat) => {
        const name = seatNames?.[seat.seatIndex];
        const filled = Boolean(name);
        const searchActive = highlightedSeats != null;
        const isMatch = searchActive && highlightedSeats.has(seat.seatIndex);
        const isDimmed = searchActive && filled && !isMatch;
        const isSelected = selectedSeat === seat.seatIndex;
        const radius = isMatch || isSelected ? SEAT_R * 1.3 : SEAT_R;
        return (
          <g
            key={seat.seatIndex}
            data-seat-index={onSeatClick ? seat.seatIndex : undefined}
            data-seat-filled={onSeatClick && filled ? "true" : undefined}
            onClick={onSeatClick ? () => onSeatClick(seat.seatIndex) : undefined}
            onKeyDown={
              onSeatClick
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSeatClick(seat.seatIndex);
                    }
                  }
                : undefined
            }
            role={onSeatClick ? "button" : undefined}
            tabIndex={onSeatClick ? 0 : undefined}
            aria-label={
              onSeatClick
                ? `Seat ${seat.seatIndex}${name ? `, ${name}` : ", empty"}`
                : undefined
            }
            className={onSeatClick ? "cursor-grab" : undefined}
          >
            <circle
              cx={seat.x}
              cy={seat.y}
              r={radius}
              className={
                isSelected
                  ? "fill-brand-dark stroke-amber-500"
                  : isMatch
                    ? "fill-amber-500 stroke-amber-600"
                    : filled
                      ? `fill-brand-dark stroke-brand-dark ${isDimmed ? "opacity-25" : ""}`
                      : "fill-white stroke-slate-400"
              }
              strokeWidth={isMatch || isSelected ? 3 : 1.5}
            />
            {!compact && (
              <text
                x={seat.x}
                y={seat.y}
                textAnchor="middle"
                dominantBaseline="central"
                className={`${filled ? "fill-white" : "fill-slate-400"} ${isDimmed ? "opacity-25" : ""}`}
                fontSize={10}
              >
                {seat.seatIndex}
              </text>
            )}
            {!compact && name && (
              <text
                x={seat.labelX}
                y={seat.labelY}
                textAnchor={seat.anchor}
                dominantBaseline={seat.baseline}
                className={`fill-slate-700 ${isDimmed ? "opacity-25" : ""}`}
                fontSize={isMatch ? 12 : 11}
                fontWeight={isMatch ? 700 : 500}
              >
                {name}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
