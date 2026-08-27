"use client";

import { useRef, useState } from "react";
import * as XLSX from "xlsx";
import { Constraint, Guest, GuestId, Relationship } from "@/lib/types";
import {
  RELATIONSHIP_OPTIONS,
  labelToRelationship,
  relationshipToLabel,
} from "@/lib/relationshipLabels";

export interface GuestData {
  guests: Guest[];
  constraints: Constraint[];
}

interface ParsedSpreadsheet extends GuestData {
  warnings: string[];
}

// Accepts either a comma or a semicolon as the tag separator.
function splitTags(raw: string): string[] {
  return raw
    .split(/[,;]/)
    .map((t) => t.trim())
    .filter(Boolean);
}

async function parseSpreadsheet(file: File): Promise<ParsedSpreadsheet> {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const warnings: string[] = [];

  const guestSheetName =
    workbook.SheetNames.find((n) => /guest/i.test(n)) ?? workbook.SheetNames[0];
  const guestRows = XLSX.utils.sheet_to_json<Record<string, unknown>>(
    workbook.Sheets[guestSheetName]
  );

  const guests: Guest[] = guestRows
    .map((row, i) => ({
      id: i,
      name: String(row.name ?? row.Name ?? "").trim(),
      relation_tags: splitTags(String(row.tags ?? row.Tags ?? "")),
    }))
    .filter((g) => g.name.length > 0);

  // Names that appear more than once (case-insensitive) are ambiguous for
  // constraint matching -- excluded from the lookup entirely rather than
  // silently resolving to "whichever guest happened to be added last".
  const nameCounts = new Map<string, number>();
  for (const g of guests) {
    const key = g.name.toLowerCase();
    nameCounts.set(key, (nameCounts.get(key) ?? 0) + 1);
  }
  const duplicateNames = [...nameCounts.entries()]
    .filter(([, count]) => count > 1)
    .map(([name]) => name);
  if (duplicateNames.length > 0) {
    warnings.push(
      `These guest names appear more than once, so constraints can't reliably reference them: ${duplicateNames.join(", ")}. Make names unique (e.g. add a last initial) to fix this.`
    );
  }

  const nameToId = new Map<string, GuestId>();
  for (const g of guests) {
    const key = g.name.toLowerCase();
    if (!duplicateNames.includes(key)) {
      nameToId.set(key, g.id);
    }
  }

  const constraintSheetName = workbook.SheetNames.find((n) =>
    /constraint/i.test(n)
  );
  const constraints: Constraint[] = [];
  if (constraintSheetName) {
    const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(
      workbook.Sheets[constraintSheetName]
    );
    rows.forEach((row, i) => {
      const rowNumber = i + 2; // header is row 1, so first data row is row 2
      const aName = String(row.guest_a ?? row["Guest A"] ?? "").trim();
      const bName = String(row.guest_b ?? row["Guest B"] ?? "").trim();
      const relationshipLabel = String(row.relationship ?? row.Relationship ?? "").trim();
      const guestAId = nameToId.get(aName.toLowerCase());
      const guestBId = nameToId.get(bName.toLowerCase());
      const relationship = labelToRelationship(relationshipLabel);

      if (guestAId === undefined) {
        warnings.push(`Constraints row ${rowNumber}: couldn't find a guest named "${aName}" (guest_a).`);
      }
      if (guestBId === undefined) {
        warnings.push(`Constraints row ${rowNumber}: couldn't find a guest named "${bName}" (guest_b).`);
      }
      if (relationship === undefined) {
        const expected = RELATIONSHIP_OPTIONS.map((o) => o.label).join(", ");
        warnings.push(
          `Constraints row ${rowNumber}: "${relationshipLabel}" isn't a valid relationship (expected ${expected}).`
        );
      }

      if (guestAId !== undefined && guestBId !== undefined && relationship !== undefined) {
        constraints.push({
          guest_a_id: guestAId,
          guest_b_id: guestBId,
          relationship,
        });
      }
    });
  }

  return { guests, constraints, warnings };
}

export default function Step2GuestInput({
  value,
  onChange,
  onOptimise,
  onBack,
}: {
  value: GuestData;
  onChange: (next: GuestData) => void;
  onOptimise: () => void;
  onBack: () => void;
}) {
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadWarnings, setUploadWarnings] = useState<string[]>([]);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const nextIdRef = useRef(value.guests.length);
  // The tags input shows this raw, still-being-typed text rather than
  // guest.relation_tags.join("; "). Deriving the field's value straight from
  // the parsed tags array fights the user mid-keystroke: splitTags() drops
  // the empty segment after a trailing "," or ";", so the character a user
  // just typed would immediately disappear from the input on every render.
  const [tagDrafts, setTagDrafts] = useState<Record<GuestId, string>>({});
  const [constraintDraft, setConstraintDraft] = useState<{
    guestAId: GuestId | "";
    guestBId: GuestId | "";
    relationship: Relationship;
  }>({ guestAId: "", guestBId: "", relationship: "must_sit_together" });

  function addGuest() {
    const id = nextIdRef.current++;
    onChange({
      ...value,
      guests: [...value.guests, { id, name: "", relation_tags: [] }],
    });
  }

  function updateGuest(id: GuestId, patch: Partial<Guest>) {
    onChange({
      ...value,
      guests: value.guests.map((g) => (g.id === id ? { ...g, ...patch } : g)),
    });
  }

  function removeGuest(id: GuestId) {
    onChange({
      guests: value.guests.filter((g) => g.id !== id),
      constraints: value.constraints.filter(
        (c) => c.guest_a_id !== id && c.guest_b_id !== id
      ),
    });
    setTagDrafts((drafts) => {
      if (!(id in drafts)) return drafts;
      const rest = { ...drafts };
      delete rest[id];
      return rest;
    });
  }

  function addConstraint() {
    if (constraintDraft.guestAId === "" || constraintDraft.guestBId === "") return;
    if (constraintDraft.guestAId === constraintDraft.guestBId) return;
    onChange({
      ...value,
      constraints: [
        ...value.constraints,
        {
          guest_a_id: constraintDraft.guestAId,
          guest_b_id: constraintDraft.guestBId,
          relationship: constraintDraft.relationship,
        },
      ],
    });
    setConstraintDraft({ guestAId: "", guestBId: "", relationship: "must_sit_together" });
  }

  function removeConstraint(index: number) {
    onChange({
      ...value,
      constraints: value.constraints.filter((_, i) => i !== index),
    });
  }

  async function handleFile(file: File) {
    setUploadError(null);
    setUploadWarnings([]);
    setUploadSuccess(null);
    try {
      const parsed = await parseSpreadsheet(file);
      if (parsed.guests.length === 0) {
        setUploadError(
          "No guests found. Expect a sheet (tab) with a 'name' column, and optionally a 'tags' column."
        );
        return;
      }
      nextIdRef.current = parsed.guests.length;
      setTagDrafts({});
      onChange({ guests: parsed.guests, constraints: parsed.constraints });
      setUploadWarnings(parsed.warnings);
      setUploadSuccess(
        `Uploaded ${parsed.guests.length} guest${parsed.guests.length === 1 ? "" : "s"}` +
          (parsed.constraints.length > 0
            ? ` and ${parsed.constraints.length} constraint${parsed.constraints.length === 1 ? "" : "s"}.`
            : ".")
      );
    } catch {
      setUploadError("Couldn't read that file. Make sure it's a .xlsx file.");
    }
  }

  function guestName(id: GuestId) {
    return value.guests.find((g) => g.id === id)?.name ?? "?";
  }

  // <select> options always report their value as a string via
  // e.target.value, regardless of the type passed into value={...} on the
  // <option>. Guest IDs can be string | number, so we look the guest back up
  // by matching its stringified id, rather than assuming a type and
  // reconstructing it (which is what caused the original bug: assuming
  // "always a number" silently sent a string id to the backend).
  function findGuestId(rawSelectValue: string): GuestId | "" {
    if (rawSelectValue === "") return "";
    const guest = value.guests.find((g) => String(g.id) === rawSelectValue);
    return guest ? guest.id : "";
  }

  const isValid = value.guests.length > 0 && value.guests.every((g) => g.name.trim());

  return (
    <div>
      <h2 className="text-2xl font-display font-bold text-brand-dark text-center mb-8">
        Enter your guest list
      </h2>

      <div className="p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100 mb-8">
        <label
          htmlFor="guest-file-upload"
          className="flex flex-col items-center justify-center w-full h-28 border-2 border-dashed border-slate-300 rounded-lg cursor-pointer hover:border-brand-dark transition-colors text-center"
        >
          <span className="text-sm text-slate-600">
            <span className="font-semibold text-brand-dark">Click to upload</span> a .xlsx
            spreadsheet
          </span>
          <span className="text-xs text-slate-400 mt-1">
            One sheet named &quot;Guests&quot; (columns: name, tags — separate multiple
            tags with a comma or semicolon, e.g. &quot;friends, university&quot;), optionally a
            &quot;Constraints&quot; sheet (columns: guest_a, guest_b, relationship).
            Uploading replaces the list below.
          </span>
          <input
            id="guest-file-upload"
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
        </label>
        <a
          href="/guest-list-template.xlsx"
          download
          className="block text-center text-sm font-semibold text-brand-dark hover:underline mt-3"
        >
          Download the guest list template
        </a>
        {uploadError && (
          <p className="text-sm text-red-600 mt-3">{uploadError}</p>
        )}
        {uploadSuccess && (
          <p className="text-sm text-green-700 bg-green-50 rounded-lg p-3 mt-3 font-semibold">
            ✓ {uploadSuccess}
          </p>
        )}
        {uploadWarnings.length > 0 && (
          <div className="mt-3 text-sm text-amber-700 bg-amber-50 rounded-lg p-3">
            <p className="font-semibold mb-1">
              Uploaded, but {uploadWarnings.length === 1 ? "one thing" : `${uploadWarnings.length} things`} needs a look:
            </p>
            <ul className="list-disc list-inside space-y-0.5">
              {uploadWarnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100 mb-8">
        <h3 className="text-lg font-bold text-brand-dark mb-4">Guests</h3>
        <div className="flex flex-col gap-3">
          {value.guests.map((guest) => (
            <div key={guest.id} className="flex gap-3 items-center">
              <input
                value={guest.name}
                onChange={(e) => updateGuest(guest.id, { name: e.target.value })}
                placeholder="Name"
                className="border-2 border-slate-200 rounded-lg p-2 flex-1 focus:border-brand-dark outline-none"
              />
              <input
                value={tagDrafts[guest.id] ?? guest.relation_tags.join("; ")}
                onChange={(e) => {
                  setTagDrafts((drafts) => ({ ...drafts, [guest.id]: e.target.value }));
                  updateGuest(guest.id, {
                    relation_tags: splitTags(e.target.value),
                  });
                }}
                placeholder="Tags (comma or semicolon separated, e.g. friends, university)"
                className="border-2 border-slate-200 rounded-lg p-2 flex-1 focus:border-brand-dark outline-none"
              />
              <button
                type="button"
                onClick={() => removeGuest(guest.id)}
                className="text-slate-400 hover:text-red-600 px-2"
                aria-label={`Remove ${guest.name || "guest"}`}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addGuest}
          className="mt-4 text-sm font-semibold text-brand-dark hover:underline"
        >
          + Add guest
        </button>
      </div>

      <div className="p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100 mb-8">
        <h3 className="text-lg font-bold text-brand-dark mb-4">Constraints (optional)</h3>
        <div className="flex flex-wrap gap-3 items-center mb-4">
          <select
            value={constraintDraft.guestAId}
            onChange={(e) =>
              setConstraintDraft((d) => ({
                ...d,
                guestAId: findGuestId(e.target.value),
              }))
            }
            className="border-2 border-slate-200 rounded-lg p-2"
          >
            <option value="">Guest A</option>
            {value.guests.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name || `Guest ${g.id}`}
              </option>
            ))}
          </select>
          <select
            value={constraintDraft.relationship}
            onChange={(e) =>
              setConstraintDraft((d) => ({
                ...d,
                relationship: e.target.value as Relationship,
              }))
            }
            className="border-2 border-slate-200 rounded-lg p-2"
          >
            {RELATIONSHIP_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label.replaceAll("_", " ")}
              </option>
            ))}
          </select>
          <select
            value={constraintDraft.guestBId}
            onChange={(e) =>
              setConstraintDraft((d) => ({
                ...d,
                guestBId: findGuestId(e.target.value),
              }))
            }
            className="border-2 border-slate-200 rounded-lg p-2"
          >
            <option value="">Guest B</option>
            {value.guests.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name || `Guest ${g.id}`}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={addConstraint}
            className="text-sm font-semibold text-brand-dark hover:underline"
          >
            + Add
          </button>
        </div>
        <ul className="flex flex-col gap-2">
          {value.constraints.map((c, i) => (
            <li
              key={i}
              className="flex justify-between items-center text-sm bg-slate-50 rounded-lg px-3 py-2"
            >
              <span>
                {guestName(c.guest_a_id)}{" "}
                <span className="text-slate-400">
                  {relationshipToLabel(c.relationship).replaceAll("_", " ")}
                </span>{" "}
                {guestName(c.guest_b_id)}
              </span>
              <button
                type="button"
                onClick={() => removeConstraint(i)}
                className="text-slate-400 hover:text-red-600"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="sticky bottom-0 bg-nav pt-4 pb-2 border-t border-slate-200 flex justify-between">
        <button
          type="button"
          onClick={onBack}
          className="rounded-full border-2 border-slate-200 text-slate-600 px-6 py-3 font-semibold hover:border-brand-dark hover:text-brand-dark transition-colors bg-white"
        >
          Back
        </button>
        <button
          type="button"
          disabled={!isValid}
          onClick={onOptimise}
          className="rounded-full bg-brand-dark text-white px-6 py-3 font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-brand-dark/90 transition-colors shadow-lg"
        >
          Optimise
        </button>
      </div>
    </div>
  );
}
