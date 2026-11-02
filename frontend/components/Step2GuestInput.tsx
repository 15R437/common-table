"use client";

import { useMemo, useRef, useState } from "react";
import { Constraint, Guest, GuestId, Relationship } from "@/lib/types";
import {
  RELATIONSHIP_OPTIONS,
  relationshipToLabel,
} from "@/lib/relationshipLabels";
import GuestImporter from "./GuestImporter";

export interface GuestData {
  guests: Guest[];
  constraints: Constraint[];
}

// Mirrors MAX_GUESTS in backend/app/optimiser.py. Checked here so an oversized
// list is caught while it can still be trimmed, rather than by a 400 from the
// server after the user has pressed Optimise.
const MAX_GUESTS = 120;

// Accepts either a comma or a semicolon as the tag separator.
function splitTags(raw: string): string[] {
  return raw
    .split(/[,;]/)
    .map((t) => t.trim())
    .filter(Boolean);
}

export default function Step2GuestInput({
  value,
  onChange,
  onOptimise,
  onBack,
  totalSeats,
  seatUnit,
}: {
  value: GuestData;
  onChange: (next: GuestData) => void;
  onOptimise: () => void;
  onBack: () => void;
  totalSeats: number;
  seatUnit: string;
}) {
  const nextIdRef = useRef(value.guests.length);
  const [importSummary, setImportSummary] = useState<string[] | null>(null);
  // The tags input shows this raw, still-being-typed text rather than
  // guest.relation_tags.join("; "). Deriving the field's value straight from
  // the parsed tags array fights the user mid-keystroke: splitTags() drops
  // the empty segment after a trailing "," or ";", so the character a user
  // just typed would immediately disappear from the input on every render.
  const [tagDrafts, setTagDrafts] = useState<Record<GuestId, string>>({});
  const [constraintDraft, setConstraintDraft] = useState<{
    guestAName: string;
    guestBName: string;
    relationship: Relationship;
  }>({ guestAName: "", guestBName: "", relationship: "must_sit_together" });
  const [constraintError, setConstraintError] = useState<string | null>(null);

  function handleImport(guests: Guest[], constraints: Constraint[], summary: string[]) {
    nextIdRef.current = guests.length;
    setTagDrafts({});
    onChange({ guests, constraints });
    setImportSummary(summary);
  }

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

  function clearAll() {
    onChange({ guests: [], constraints: [] });
    setTagDrafts({});
    setImportSummary(null);
    nextIdRef.current = 0;
  }

  // Names rather than ids in the constraint draft, so the two fields can be a
  // typeahead instead of a pair of <select>s. At wedding scale a plain dropdown
  // means scrolling a list of 120 names, twice, for every constraint added.
  const guestByName = useMemo(() => {
    const map = new Map<string, Guest>();
    for (const guest of value.guests) {
      const key = guest.name.trim().toLowerCase();
      if (key) map.set(key, guest);
    }
    return map;
  }, [value.guests]);

  const knownTags = useMemo(() => {
    const tags = new Set<string>();
    for (const guest of value.guests) for (const tag of guest.relation_tags) tags.add(tag);
    return [...tags].sort();
  }, [value.guests]);

  function addConstraint() {
    const a = guestByName.get(constraintDraft.guestAName.trim().toLowerCase());
    const b = guestByName.get(constraintDraft.guestBName.trim().toLowerCase());

    if (!a || !b) {
      setConstraintError(
        `Pick two guests from your list — we couldn't find ${!a ? `"${constraintDraft.guestAName}"` : `"${constraintDraft.guestBName}"`}.`
      );
      return;
    }
    if (a.id === b.id) {
      setConstraintError("Those are the same guest.");
      return;
    }
    const exists = value.constraints.some(
      (c) =>
        (c.guest_a_id === a.id && c.guest_b_id === b.id) ||
        (c.guest_a_id === b.id && c.guest_b_id === a.id)
    );
    if (exists) {
      setConstraintError(`There's already a rule between ${a.name} and ${b.name}.`);
      return;
    }

    setConstraintError(null);
    onChange({
      ...value,
      constraints: [
        ...value.constraints,
        { guest_a_id: a.id, guest_b_id: b.id, relationship: constraintDraft.relationship },
      ],
    });
    setConstraintDraft({ guestAName: "", guestBName: "", relationship: constraintDraft.relationship });
  }

  function removeConstraint(index: number) {
    onChange({
      ...value,
      constraints: value.constraints.filter((_, i) => i !== index),
    });
  }

  function guestName(id: GuestId) {
    return value.guests.find((g) => g.id === id)?.name ?? "?";
  }

  const namedGuests = value.guests.filter((g) => g.name.trim()).length;
  const overCapacity = value.guests.length > totalSeats;
  const overMax = value.guests.length > MAX_GUESTS;
  const isValid =
    value.guests.length > 0 &&
    value.guests.every((g) => g.name.trim()) &&
    !overCapacity &&
    !overMax;

  return (
    <div>
      <h2 className="text-2xl font-display font-bold text-brand-dark text-center mb-8">
        Enter your guest list
      </h2>

      <GuestImporter onImport={handleImport} />

      {importSummary && importSummary.length > 0 && (
        <div className="mb-8 text-sm text-slate-600 bg-brand-light rounded-2xl p-5">
          <p className="font-semibold text-brand-dark mb-1">What we did with your list</p>
          <ul className="list-disc list-inside space-y-0.5">
            {importSummary.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="p-6 sm:p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100 mb-8">
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1">
          <h3 className="text-lg font-bold text-brand-dark">Guests</h3>
          <div className="flex items-center gap-3">
            <span
              className={`text-sm font-semibold ${
                overCapacity || overMax ? "text-red-600" : "text-slate-400"
              }`}
            >
              {value.guests.length} {value.guests.length === 1 ? "guest" : "guests"} ·{" "}
              {totalSeats} {seatUnit}
            </span>
            {value.guests.length > 0 && (
              <button
                type="button"
                onClick={clearAll}
                className="text-xs font-semibold text-slate-400 hover:text-red-600"
              >
                Clear all
              </button>
            )}
          </div>
        </div>

        {/* Capacity is checked here rather than on submit: the seating style was
            chosen before the guest list existed, so the first moment either
            number is known is now. */}
        {overCapacity && !overMax && (
          <p className="text-sm text-red-600 mb-4">
            That&apos;s {value.guests.length - totalSeats} more{" "}
            {value.guests.length - totalSeats === 1 ? "guest" : "guests"} than you have{" "}
            {seatUnit}. Go back and add{" "}
            {Math.ceil((value.guests.length - totalSeats) / 2)} or so more, or remove a few
            guests.
          </p>
        )}
        {overMax && (
          <p className="text-sm text-red-600 mb-4">
            {value.guests.length} guests is past the {MAX_GUESTS} this planner can arrange at
            once.
          </p>
        )}
        {value.guests.length > 0 && namedGuests < value.guests.length && (
          <p className="text-sm text-amber-700 mb-4">
            {value.guests.length - namedGuests}{" "}
            {value.guests.length - namedGuests === 1 ? "guest needs" : "guests need"} a name
            before you can carry on.
          </p>
        )}

        <div className="flex flex-col gap-3">
          {value.guests.map((guest) => (
            <div
              key={guest.id}
              className="flex flex-col sm:flex-row gap-2 sm:gap-3 sm:items-center border-b border-slate-50 sm:border-0 pb-3 sm:pb-0 last:border-0 last:pb-0"
            >
              <input
                value={guest.name}
                onChange={(e) => updateGuest(guest.id, { name: e.target.value })}
                placeholder="Name"
                className="border-2 border-slate-200 rounded-lg p-2 flex-1 min-w-0 focus:border-brand-dark outline-none"
              />
              <div className="flex gap-2 sm:gap-3 items-center flex-1 min-w-0">
                <input
                  value={tagDrafts[guest.id] ?? guest.relation_tags.join("; ")}
                  onChange={(e) => {
                    setTagDrafts((drafts) => ({ ...drafts, [guest.id]: e.target.value }));
                    updateGuest(guest.id, { relation_tags: splitTags(e.target.value) });
                  }}
                  list="known-tags"
                  placeholder="Groups, e.g. uni friends"
                  className="border-2 border-slate-200 rounded-lg p-2 flex-1 min-w-0 focus:border-brand-dark outline-none"
                />
                <button
                  type="button"
                  onClick={() => removeGuest(guest.id)}
                  className="text-slate-400 hover:text-red-600 px-2 shrink-0"
                  aria-label={`Remove ${guest.name || "guest"}`}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
        <datalist id="known-tags">
          {knownTags.map((tag) => (
            <option key={tag} value={tag} />
          ))}
        </datalist>
        <button
          type="button"
          onClick={addGuest}
          className="mt-4 text-sm font-semibold text-brand-dark hover:underline"
        >
          + Add guest
        </button>
      </div>

      <div className="p-6 sm:p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100 mb-8">
        <h3 className="text-lg font-bold text-brand-dark mb-1">Who sits with whom</h3>
        <p className="text-sm text-slate-500 mb-4">
          Optional — couples, and anyone best kept apart.
          {value.constraints.length > 0 && ` ${value.constraints.length} so far.`}
        </p>
        <div className="flex flex-col sm:flex-row flex-wrap gap-3 sm:items-center mb-2">
          <input
            value={constraintDraft.guestAName}
            onChange={(e) =>
              setConstraintDraft((d) => ({ ...d, guestAName: e.target.value }))
            }
            list="guest-names"
            placeholder="Start typing a name"
            className="border-2 border-slate-200 rounded-lg p-2 flex-1 min-w-0 focus:border-brand-dark outline-none"
          />
          <select
            value={constraintDraft.relationship}
            onChange={(e) =>
              setConstraintDraft((d) => ({
                ...d,
                relationship: e.target.value as Relationship,
              }))
            }
            className="border-2 border-slate-200 rounded-lg p-2 bg-white"
          >
            {RELATIONSHIP_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label.replaceAll("_", " ")}
              </option>
            ))}
          </select>
          <input
            value={constraintDraft.guestBName}
            onChange={(e) =>
              setConstraintDraft((d) => ({ ...d, guestBName: e.target.value }))
            }
            list="guest-names"
            placeholder="Start typing a name"
            className="border-2 border-slate-200 rounded-lg p-2 flex-1 min-w-0 focus:border-brand-dark outline-none"
          />
          <button
            type="button"
            onClick={addConstraint}
            className="text-sm font-semibold text-brand-dark hover:underline self-start sm:self-auto"
          >
            + Add
          </button>
        </div>
        <datalist id="guest-names">
          {value.guests
            .filter((g) => g.name.trim())
            .map((g) => (
              <option key={g.id} value={g.name} />
            ))}
        </datalist>
        {constraintError && <p className="text-sm text-red-600 mb-3">{constraintError}</p>}
        <ul className="flex flex-col gap-2">
          {value.constraints.map((c, i) => (
            <li
              key={i}
              className="flex justify-between items-center gap-2 text-sm bg-slate-50 rounded-lg px-3 py-2"
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
                className="text-slate-400 hover:text-red-600 shrink-0"
                aria-label="Remove this rule"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="sticky bottom-0 bg-nav pt-4 pb-2 border-t border-slate-200 flex justify-between gap-3">
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
