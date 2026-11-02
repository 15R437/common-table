"use client";

import { useMemo, useRef, useState } from "react";
import { Constraint, Guest } from "@/lib/types";
import {
  ColumnMapping,
  DetectedTable,
  Grid,
  buildConstraintsFromGrid,
  buildGuestList,
  detectTable,
  guessMapping,
  mappingIsUsable,
  parseDelimitedText,
  readFileToGrid,
} from "@/lib/importGuests";

type Mode = "paste" | "upload";

interface Staged {
  table: DetectedTable;
  mapping: ColumnMapping;
  source: string;
  /** Rows from an explicit Constraints sheet, when the workbook had one. */
  constraintGrid?: Grid;
}

function ColumnSelect({
  label,
  hint,
  headers,
  value,
  onChange,
  allowNone = true,
}: {
  label: string;
  hint?: string;
  headers: string[];
  value: number | null;
  onChange: (next: number | null) => void;
  allowNone?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1 min-w-0">
      <span className="text-xs font-bold text-slate-400 uppercase">{label}</span>
      <select
        value={value === null ? "" : String(value)}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className="border-2 border-slate-200 rounded-lg p-2 text-sm focus:border-brand-dark outline-none bg-white"
      >
        {allowNone && <option value="">None</option>}
        {headers.map((header, i) => (
          <option key={i} value={i}>
            {header}
          </option>
        ))}
      </select>
      {hint && <span className="text-xs text-slate-400">{hint}</span>}
    </label>
  );
}

export default function GuestImporter({
  onImport,
}: {
  onImport: (guests: Guest[], constraints: Constraint[], summary: string[]) => void;
}) {
  const [mode, setMode] = useState<Mode>("paste");
  const [pasteText, setPasteText] = useState("");
  const [staged, setStaged] = useState<Staged | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Recomputed on every mapping change so the preview and the guest count below
  // the mapper always describe exactly what the Import button will produce.
  const preview = useMemo(() => {
    if (!staged) return null;
    const built = buildGuestList(staged.table, staged.mapping);
    if (!staged.constraintGrid) return built;

    // Constraints written out by hand express intent more precisely than the
    // ones inferred from a household column, so where both describe the same
    // pair the explicit one wins.
    const explicit = buildConstraintsFromGrid(staged.constraintGrid, built.guests);
    const pairKey = (a: string | number, b: string | number) =>
      [String(a), String(b)].sort().join("\u0000");
    const claimed = new Set(
      explicit.constraints.map((c) => pairKey(c.guest_a_id, c.guest_b_id))
    );

    return {
      guests: built.guests,
      constraints: [
        ...explicit.constraints,
        ...built.constraints.filter(
          (c) => !claimed.has(pairKey(c.guest_a_id, c.guest_b_id))
        ),
      ],
      notes: [...built.notes, ...explicit.warnings],
    };
  }, [staged]);

  function stage(table: DetectedTable, source: string, constraintGrid?: Grid) {
    if (table.rows.length === 0) {
      setError(
        "That looks empty. There's a header row, but no guests underneath it."
      );
      setStaged(null);
      return;
    }
    setError(null);
    setStaged({ table, mapping: guessMapping(table), source, constraintGrid });
  }

  function handlePaste() {
    const text = pasteText.trim();
    if (!text) {
      setError("Paste your guest list into the box first.");
      return;
    }

    const grid = parseDelimitedText(text);
    const table = detectTable(grid);

    // A list pasted as one name per line has no header row to find: the first
    // name would otherwise be eaten as a column heading. One column and no
    // delimiter in sight is the giveaway.
    const looksHeaderless =
      table.headers.length === 1 && !/[\t,;]/.test(text.split(/\r?\n/)[0] ?? "");
    if (looksHeaderless) {
      const names = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
      stage(
        {
          headers: ["Name"],
          rows: names.map((name) => [name]),
          skippedLeadingRows: 0,
        },
        `${names.length} pasted lines`
      );
      return;
    }

    stage(table, "pasted list");
  }

  async function handleFile(file: File) {
    setError(null);
    try {
      const { grid, sheetName, constraintGrid } = await readFileToGrid(file);
      if (grid.length === 0) {
        setError("That file looks empty.");
        return;
      }
      stage(
        detectTable(grid),
        sheetName ? `${file.name}, sheet "${sheetName}"` : file.name,
        constraintGrid
      );
    } catch {
      setError(
        "Couldn't read that file. A .xlsx, .xls or .csv exported from your spreadsheet should work, or you can paste the list in instead."
      );
    }
  }

  function updateMapping(patch: Partial<ColumnMapping>) {
    setStaged((current) => (current ? { ...current, mapping: { ...current.mapping, ...patch } } : current));
  }

  function confirmImport() {
    if (!staged || !preview) return;
    onImport(preview.guests, preview.constraints, preview.notes);
    setStaged(null);
    setPasteText("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  const headers = staged?.table.headers ?? [];
  const usable = staged ? mappingIsUsable(staged.mapping) : false;

  return (
    <div className="p-6 sm:p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100 mb-8">
      <h3 className="text-lg font-bold text-brand-dark mb-1">Bring in your guest list</h3>
      <p className="text-sm text-slate-500 mb-5">
        Already have it in a spreadsheet? Paste it in as it is. Whatever your columns are
        called, you&apos;ll get a chance to confirm what&apos;s what.
      </p>

      <div className="inline-flex rounded-full border border-slate-200 p-1 bg-slate-50 mb-5">
        {(["paste", "upload"] as Mode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => {
              setMode(m);
              setError(null);
            }}
            className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
              mode === m ? "bg-brand-dark text-white" : "text-slate-500"
            }`}
          >
            {m === "paste" ? "Paste" : "Upload a file"}
          </button>
        ))}
      </div>

      {mode === "paste" ? (
        <div>
          <textarea
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            rows={6}
            placeholder={
              "Select your guests in Excel, Google Sheets or Numbers, copy, and paste here.\n\nOne name per line works too:\nLinda Whitfield\nGeoff Whitfield"
            }
            className="w-full border-2 border-slate-200 rounded-lg p-3 text-sm font-mono focus:border-brand-dark outline-none resize-y"
          />
          <button
            type="button"
            onClick={handlePaste}
            className="mt-3 rounded-full bg-brand-dark text-white px-5 py-2 text-sm font-semibold hover:bg-brand-dark/90 transition-colors"
          >
            Read this list
          </button>
        </div>
      ) : (
        <div>
          <label
            htmlFor="guest-file-upload"
            className="flex flex-col items-center justify-center w-full h-28 border-2 border-dashed border-slate-300 rounded-lg cursor-pointer hover:border-brand-dark transition-colors text-center px-4"
          >
            <span className="text-sm text-slate-600">
              <span className="font-semibold text-brand-dark">Click to upload</span> a
              spreadsheet
            </span>
            <span className="text-xs text-slate-400 mt-1">
              .xlsx, .xls or .csv, exported from anywhere. Your own column names are fine.
            </span>
            <input
              ref={fileInputRef}
              id="guest-file-upload"
              type="file"
              accept=".xlsx,.xls,.csv,.tsv,.txt"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
            />
          </label>
          <a
            href="/guest-list-template.xlsx"
            download
            className="block text-center text-sm text-slate-400 hover:text-brand-dark hover:underline mt-3"
          >
            Haven&apos;t got a list yet? Start from our template
          </a>
        </div>
      )}

      {error && <p className="text-sm text-red-600 mt-3">{error}</p>}

      {staged && preview && (
        <div className="mt-6 pt-6 border-t border-slate-200">
          <p className="text-sm font-semibold text-brand-dark mb-1">
            Found {staged.table.rows.length}{" "}
            {staged.table.rows.length === 1 ? "row" : "rows"} in {staged.source}.
          </p>
          <p className="text-sm text-slate-500 mb-4">
            Check we&apos;ve read your columns correctly:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
            <ColumnSelect
              label="Name"
              headers={headers}
              value={staged.mapping.nameColumn}
              onChange={(next) =>
                updateMapping({
                  nameColumn: next,
                  // A single name column and a first/last pair are alternatives,
                  // not additions -- keeping both would join a name to itself.
                  firstNameColumn: next === null ? staged.mapping.firstNameColumn : null,
                  lastNameColumn: next === null ? staged.mapping.lastNameColumn : null,
                })
              }
            />
            {staged.mapping.nameColumn === null && (
              <>
                <ColumnSelect
                  label="First name"
                  headers={headers}
                  value={staged.mapping.firstNameColumn}
                  onChange={(next) => updateMapping({ firstNameColumn: next })}
                />
                <ColumnSelect
                  label="Last name"
                  headers={headers}
                  value={staged.mapping.lastNameColumn}
                  onChange={(next) => updateMapping({ lastNameColumn: next })}
                />
              </>
            )}
            <ColumnSelect
              label="Group"
              hint="Guests who share a value sit closer together, e.g. a social group or an interest"
              headers={headers}
              value={staged.mapping.groupColumn}
              onChange={(next) => updateMapping({ groupColumn: next })}
            />
            <ColumnSelect
              label="Keep together"
              hint="For guests who must sit next to each other, e.g. couples and families"
              headers={headers}
              value={staged.mapping.partyColumn}
              onChange={(next) => updateMapping({ partyColumn: next })}
            />
            <ColumnSelect
              label="RSVP"
              headers={headers}
              value={staged.mapping.rsvpColumn}
              onChange={(next) =>
                updateMapping({ rsvpColumn: next, onlyAttending: next !== null })
              }
            />
          </div>

          {staged.mapping.rsvpColumn !== null && (
            <label className="flex items-center gap-2 text-sm text-slate-600 mb-4">
              <input
                type="checkbox"
                checked={staged.mapping.onlyAttending}
                onChange={(e) => updateMapping({ onlyAttending: e.target.checked })}
                className="w-4 h-4 accent-brand-dark"
              />
              Only include guests whose &quot;{headers[staged.mapping.rsvpColumn]}&quot; is a
              yes
            </label>
          )}

          {!usable ? (
            <p className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3">
              Pick which column holds the guest&apos;s name to carry on.
            </p>
          ) : (
            <>
              <div className="overflow-x-auto rounded-lg border border-slate-200 mb-4">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left">
                    <tr>
                      <th className="px-3 py-2 font-semibold text-slate-500">Guest</th>
                      <th className="px-3 py-2 font-semibold text-slate-500">Groups</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {preview.guests.slice(0, 5).map((guest) => (
                      <tr key={guest.id}>
                        <td className="px-3 py-2 whitespace-nowrap">{guest.name}</td>
                        <td className="px-3 py-2 text-slate-500">
                          {guest.relation_tags.join(", ") || "None"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {preview.notes.length > 0 && (
                <ul className="text-sm text-slate-500 list-disc list-inside space-y-1 mb-4">
                  {preview.notes.map((note, i) => (
                    <li key={i}>{note}</li>
                  ))}
                </ul>
              )}

              <button
                type="button"
                onClick={confirmImport}
                disabled={preview.guests.length === 0}
                className="rounded-full bg-brand-dark text-white px-6 py-3 font-semibold hover:bg-brand-dark/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Import {preview.guests.length}{" "}
                {preview.guests.length === 1 ? "guest" : "guests"}
                {preview.constraints.length > 0 &&
                  ` and ${preview.constraints.length} constraint${preview.constraints.length === 1 ? "" : "s"}`}
              </button>
              <p className="text-xs text-slate-400 mt-2">
                This replaces the list below. You can edit everything afterwards.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
