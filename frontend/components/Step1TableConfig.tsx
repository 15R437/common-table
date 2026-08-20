"use client";

import { useState } from "react";
import { TableStyle } from "@/lib/types";
import TableDiagram from "./TableDiagram";

// A plain `value={n}` + `onChange={e => onChange(Number(e.target.value))}`
// number input has a well-known bug: clearing the field commits Number("")=0
// straight back into state, so the field immediately re-displays "0" -- and
// the next digit you type lands *after* that lingering zero ("0" + "3" =
// "03"), every time. Tracking what the user actually typed as a local string
// (only committing a parsed number up to the parent when it's a real one)
// avoids that round-trip entirely.
function NumberField({
  label,
  value,
  min,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  onChange: (n: number) => void;
}) {
  const [raw, setRaw] = useState(String(value));

  return (
    <label className="flex flex-col gap-2">
      <span className="text-xs font-bold text-slate-400 uppercase">{label}</span>
      <input
        type="number"
        min={min}
        value={raw}
        onChange={(e) => {
          setRaw(e.target.value);
          const n = Number(e.target.value);
          if (e.target.value !== "" && !Number.isNaN(n)) {
            onChange(n);
          }
        }}
        onBlur={() => setRaw(String(value))}
        className="border-2 border-slate-200 rounded-lg p-2 w-32 focus:border-brand-dark outline-none"
      />
    </label>
  );
}

export interface TableConfig {
  style: TableStyle | null;
  numTables: number; // for theatre, this is "number of rows"
  numSeatsPerTable: number; // for theatre, this is "seats per row"
  headSeat: boolean;
  footSeat: boolean;
}

const STYLES: { style: TableStyle; label: string }[] = [
  { style: "banquet", label: "Banquet" },
  { style: "cabaret", label: "Cabaret" },
  { style: "theatre", label: "Theatre" },
];

export default function Step1TableConfig({
  value,
  onChange,
  onNext,
}: {
  value: TableConfig;
  onChange: (next: TableConfig) => void;
  onNext: () => void;
}) {
  const isValid = value.style !== null && value.numTables > 0 && value.numSeatsPerTable > 0;

  const tableLabel = value.style === "theatre" ? "Number of rows" : "Number of tables";
  const seatLabel = value.style === "theatre" ? "Seats per row" : "Seats per table";

  return (
    <div>
      <h2 className="text-2xl font-display font-bold text-brand-dark text-center mb-8">
        Select your seating style
      </h2>

      <div className="grid grid-cols-3 gap-6">
        {STYLES.map(({ style, label }) => {
          const selected = value.style === style;
          return (
            <button
              key={style}
              type="button"
              onClick={() =>
                onChange({
                  ...value,
                  style,
                  headSeat: style === "banquet" ? value.headSeat : false,
                  footSeat: style === "banquet" ? value.footSeat : false,
                })
              }
              className={`flex flex-col items-center justify-between h-56 p-4 rounded-xl border-2 transition-all ${
                selected
                  ? "border-brand-dark bg-brand-light"
                  : "border-slate-200 hover:border-brand-dark/50"
              }`}
            >
              <div className="w-full h-36">
                <TableDiagram type={style} numSeats={6} compact />
              </div>
              <span
                className={`font-bold ${selected ? "text-brand-dark" : "text-slate-500"}`}
              >
                {label}
              </span>
            </button>
          );
        })}
      </div>

      {value.style && (
        <div className="mt-10 p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100">
          <h3 className="text-lg font-bold text-brand-dark mb-6">
            Enter details for {value.style} style
          </h3>
          <div className="flex flex-wrap gap-8 items-start">
            <NumberField
              label={tableLabel}
              min={1}
              value={value.numTables}
              onChange={(n) => onChange({ ...value, numTables: n })}
            />
            <NumberField
              label={seatLabel}
              min={2}
              value={value.numSeatsPerTable}
              onChange={(n) => onChange({ ...value, numSeatsPerTable: n })}
            />

            {value.style === "banquet" && (
              <div className="flex items-center gap-6 pt-8">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={value.headSeat}
                    onChange={(e) =>
                      onChange({
                        ...value,
                        headSeat: e.target.checked,
                        footSeat: e.target.checked ? value.footSeat : false,
                      })
                    }
                    className="w-5 h-5 accent-brand-dark"
                  />
                  <span className="text-sm font-semibold text-slate-600">
                    Head seat
                  </span>
                </label>
                <label
                  className={`flex items-center gap-2 ${
                    value.headSeat ? "cursor-pointer" : "cursor-not-allowed opacity-50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={value.footSeat}
                    disabled={!value.headSeat}
                    onChange={(e) => onChange({ ...value, footSeat: e.target.checked })}
                    className="w-5 h-5 accent-brand-dark"
                  />
                  <span className="text-sm font-semibold text-slate-600">
                    Foot seat
                  </span>
                </label>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mt-8 flex justify-end">
        <button
          type="button"
          disabled={!isValid}
          onClick={onNext}
          className="rounded-full bg-brand-dark text-white px-6 py-3 font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-brand-dark/90 transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  );
}
