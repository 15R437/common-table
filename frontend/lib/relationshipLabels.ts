import { Relationship } from "./types";

// The backend's canonical Relationship values (must_sit_together, etc.) are
// stable identifiers used in API payloads and code -- not meant to read as a
// sentence. Anywhere a relationship is shown to a user (the manual-entry
// dropdown, the constraint list, the spreadsheet template) uses these
// friendlier, grammatically-complete labels instead, translated back to the
// canonical value at the UI boundary (see labelToRelationship).
export const RELATIONSHIP_OPTIONS: { value: Relationship; label: string }[] = [
  { value: "must_sit_together", label: "must_sit_together_with" },
  { value: "could_sit_together", label: "could_sit_together_with" },
  { value: "must_sit_apart", label: "must_sit_apart_from" },
];

export function relationshipToLabel(relationship: Relationship): string {
  return (
    RELATIONSHIP_OPTIONS.find((o) => o.value === relationship)?.label ??
    relationship
  );
}

// Strips case, spaces, underscores and hyphens so every way a person might
// write a relationship in a spreadsheet collapses to one key. The previous
// exact-string match rejected everything except the three template labels
// verbatim -- including "must_sit_together" (the backend's own name for it),
// any capitalisation, and a value with a trailing space, which is what Excel
// leaves behind when someone retypes over a dropdown cell.
const canonicalise = (label: string) => label.toLowerCase().replace(/[^a-z]/g, "");

const SYNONYMS: Record<string, Relationship> = {};
const register = (relationship: Relationship, ...spellings: string[]) => {
  for (const spelling of spellings) SYNONYMS[canonicalise(spelling)] = relationship;
};

register(
  "must_sit_together",
  "must_sit_together_with", "must_sit_together", "must sit together",
  "must sit with", "sit together", "together", "must be together",
  "seat together", "same seat area", "must"
);
register(
  "could_sit_together",
  "could_sit_together_with", "could_sit_together", "could sit together",
  "could sit with", "could", "prefer together", "would like to sit together",
  "nice to sit together", "same table"
);
register(
  "must_sit_apart",
  "must_sit_apart_from", "must_sit_apart", "must sit apart",
  "must sit apart from", "apart", "keep apart", "do not sit together",
  "dont sit together", "not together", "avoid", "separate"
);

export function labelToRelationship(label: string): Relationship | undefined {
  return SYNONYMS[canonicalise(label)];
}

/** Human-readable list of what a relationship cell may say, for error messages. */
export const RELATIONSHIP_HINT = RELATIONSHIP_OPTIONS.map((o) =>
  o.label.replaceAll("_", " ")
).join(", ");
