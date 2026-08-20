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

export function labelToRelationship(label: string): Relationship | undefined {
  return RELATIONSHIP_OPTIONS.find((o) => o.label === label)?.value;
}
