import * as XLSX from "xlsx";
import { Constraint, Guest, GuestId } from "./types";
import { RELATIONSHIP_HINT, labelToRelationship } from "./relationshipLabels";

// A rectangular grid of raw cell text: grid[row][col]. Everything in this
// module works on this shape, so pasted text and uploaded workbooks share one
// code path from the header-detection step onwards.
export type Grid = string[][];

export interface DetectedTable {
  headers: string[];
  rows: string[][];
  /** Rows above the header row that were skipped (titles, blank spacers). */
  skippedLeadingRows: number;
  /** Name of the worksheet the data came from, when it came from a workbook. */
  sheetName?: string;
}

export interface ColumnMapping {
  /** Index of a single full-name column, or null when using firstName/lastName. */
  nameColumn: number | null;
  firstNameColumn: number | null;
  lastNameColumn: number | null;
  /** Column whose values become relation tags (social groups). */
  groupColumn: number | null;
  /** Column identifying a household/party, used to infer seating constraints. */
  partyColumn: number | null;
  /** Column holding an RSVP/attending status. */
  rsvpColumn: number | null;
  /** When an rsvpColumn is mapped, only import rows that read as "attending". */
  onlyAttending: boolean;
}

export interface BuiltGuestList {
  guests: Guest[];
  constraints: Constraint[];
  notes: string[];
}

// ---------------------------------------------------------------------------
// Reading
// ---------------------------------------------------------------------------

// Pasting from Excel, Numbers or Google Sheets puts tab-separated text on the
// clipboard; pasting from a .csv file or an email gives commas. Sniffing the
// header line rather than asking the user keeps the paste box a single step.
// Tabs win when present because a tab-separated paste can legitimately contain
// commas inside a cell ("Shah, Priya") while the reverse is vanishingly rare.
function detectDelimiter(text: string): string {
  const firstLine = text.split(/\r?\n/).find((l) => l.trim().length > 0) ?? "";
  if (firstLine.includes("\t")) return "\t";
  if (firstLine.includes(";") && !firstLine.includes(",")) return ";";
  return ",";
}

// A hand-rolled reader rather than a library call because the input is clipboard
// text as often as it is a file: it has to cope with quoted fields containing
// the delimiter, escaped double quotes ("" inside a quoted field), and newlines
// inside a quoted field -- all of which appear in real guest lists via address
// and notes columns.
export function parseDelimitedText(text: string, delimiter?: string): Grid {
  const delim = delimiter ?? detectDelimiter(text);
  const grid: Grid = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];

    if (inQuotes) {
      if (char === '"') {
        if (text[i + 1] === '"') {
          cell += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cell += char;
      }
      continue;
    }

    if (char === '"') {
      inQuotes = true;
    } else if (char === delim) {
      row.push(cell);
      cell = "";
    } else if (char === "\n") {
      row.push(cell);
      grid.push(row);
      row = [];
      cell = "";
    } else if (char !== "\r") {
      cell += char;
    }
  }
  row.push(cell);
  grid.push(row);

  return grid.map((r) => r.map((c) => c.trim()));
}

export async function readFileToGrid(
  file: File
): Promise<{ grid: Grid; sheetName?: string; constraintGrid?: Grid }> {
  const isText = /\.(csv|tsv|txt)$/i.test(file.name);
  if (isText) {
    return { grid: parseDelimitedText(await file.text()) };
  }

  const workbook = XLSX.read(await file.arrayBuffer(), { type: "array" });
  // Prefer a sheet that calls itself "guests", then the sheet with the most
  // rows. Picking SheetNames[0] unconditionally lands on a README or cover
  // sheet in any workbook that has one -- including this app's own template.
  const named = workbook.SheetNames.find((n) => /guest|invit|rsvp/i.test(n));
  const sheetName =
    named ??
    [...workbook.SheetNames].sort(
      (a, b) =>
        XLSX.utils.decode_range(workbook.Sheets[b]["!ref"] ?? "A1:A1").e.r -
        XLSX.utils.decode_range(workbook.Sheets[a]["!ref"] ?? "A1:A1").e.r
    )[0];

  // header:1 gives raw rows instead of objects keyed by header text, which is
  // what lets us find the header row ourselves rather than trusting row 1.
  // raw:false stringifies numbers and dates so a table number or a date of
  // birth doesn't arrive as a float needing separate handling.
  const grid = XLSX.utils.sheet_to_json<string[]>(workbook.Sheets[sheetName], {
    header: 1,
    raw: false,
    defval: "",
    blankrows: false,
  });

  // A workbook may also carry an explicit Constraints sheet (this app's own
  // template does). Dropping it on import would silently throw away work the
  // user had already done by hand.
  const constraintSheet = workbook.SheetNames.find((n) => /constraint|seating rule/i.test(n));
  const constraintGrid = constraintSheet
    ? XLSX.utils
        .sheet_to_json<string[]>(workbook.Sheets[constraintSheet], {
          header: 1,
          raw: false,
          defval: "",
          blankrows: false,
        })
        .map((row) => row.map((cell) => String(cell ?? "").trim()))
    : undefined;

  return {
    grid: grid.map((row) => row.map((cell) => String(cell ?? "").trim())),
    sheetName,
    constraintGrid,
  };
}

// ---------------------------------------------------------------------------
// Header detection
// ---------------------------------------------------------------------------

const countFilled = (row: string[]) => row.filter((c) => c.trim().length > 0).length;

// Real spreadsheets routinely open with a title ("Our Wedding Guest List") and
// a blank spacer before the real headers, so the header row is not reliably
// row 1. The widest of the first few rows is the header in practice: a title
// occupies one cell, the header row occupies one per column.
export function detectTable(grid: Grid): DetectedTable {
  const searchDepth = Math.min(grid.length, 10);
  let headerRow = 0;
  let bestFilled = 0;

  for (let i = 0; i < searchDepth; i++) {
    const filled = countFilled(grid[i] ?? []);
    // Strictly greater, so the earliest of equally wide rows wins -- the header
    // precedes its data rows, which are usually just as wide.
    if (filled > bestFilled && filled >= 2) {
      bestFilled = filled;
      headerRow = i;
    }
  }

  const rawHeaders = grid[headerRow] ?? [];
  // Trailing empty header cells come from stray formatting far to the right and
  // would otherwise show up in the mapper as unnamed columns to choose from.
  let width = rawHeaders.length;
  while (width > 0 && !rawHeaders[width - 1]?.trim()) width--;

  const headers = rawHeaders.slice(0, width).map((h, i) => h.trim() || `Column ${i + 1}`);
  const rows = grid
    .slice(headerRow + 1)
    .map((row) => Array.from({ length: width }, (_, i) => row[i] ?? ""))
    .filter((row) => countFilled(row) > 0);

  return { headers, rows, skippedLeadingRows: headerRow };
}

// ---------------------------------------------------------------------------
// Column guessing
// ---------------------------------------------------------------------------

// Compared against normalised headers, so "Guest Name", "guest_name" and
// "GUEST NAME" all reduce to the same key and match the same candidate.
const normalise = (header: string) =>
  header
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

const NAME_CANDIDATES = [
  "name", "full name", "guest name", "guest", "guest full name",
  "attendee", "attendee name", "person", "invitee", "invitee name", "names",
];
const FIRST_NAME_CANDIDATES = ["first name", "first", "forename", "given name", "firstname"];
const LAST_NAME_CANDIDATES = ["last name", "last", "surname", "family name", "lastname"];
// Ordered: an explicit grouping column beats a free-text descriptor like
// "relationship", which in real lists holds things like "Mother of the bride"
// -- unique per guest, and so useless as a shared tag.
const GROUP_CANDIDATES = [
  "tags", "tag", "group", "guest group", "side", "category", "circle",
  "connection", "how we know them", "how you know them",
  // Not every event is a wedding: a conference or company dinner groups people
  // by where they work or what they work on. Listed here rather than under
  // households because a column like "Team" or "Company" could be read either
  // way, and reading it as a group only nudges the score, where reading it as a
  // household would impose a hard must_sit_together.
  "department", "team", "company", "organisation", "organization",
  "affiliation", "institution", "school", "faculty", "track", "topic",
  "relation", "relationship",
];
const PARTY_CANDIDATES = [
  "party", "household", "party name", "invite", "invitation", "family",
  "party id", "group name", "invite group", "booking",
];
const RSVP_CANDIDATES = [
  "rsvp", "rsvp status", "attending", "status", "response", "coming", "reply",
  // An event that isn't a wedding asks people to register rather than to RSVP.
  "registered", "registration", "confirmed", "booked",
];

function bestMatch(headers: string[], candidates: string[], exclude: number[] = []): number | null {
  const normalised = headers.map(normalise);
  // Candidate order is the priority order, so scan candidates in the outer loop
  // -- the first candidate with any match wins over a later, vaguer one.
  for (const candidate of candidates) {
    const exact = normalised.findIndex((h, i) => h === candidate && !exclude.includes(i));
    if (exact !== -1) return exact;
  }
  for (const candidate of candidates) {
    const partial = normalised.findIndex(
      (h, i) => h.includes(candidate) && !exclude.includes(i)
    );
    if (partial !== -1) return partial;
  }
  return null;
}

const ATTENDING_VALUES = new Set([
  "yes", "y", "attending", "accepted", "coming", "confirmed", "true", "1",
  "rsvp yes", "will attend", "accept", "registered", "paid", "going",
]);

export function readsAsAttending(value: string): boolean {
  return ATTENDING_VALUES.has(normalise(value));
}

export function guessMapping(table: DetectedTable): ColumnMapping {
  const { headers, rows } = table;

  // First/last are resolved before the single-name column and then excluded from
  // it. Without that, the partial-match pass for "name" happily claims a column
  // headed "First Name" -- importing a list of forenames with every surname
  // silently dropped.
  const firstNameColumn = bestMatch(headers, FIRST_NAME_CANDIDATES);
  const lastNameColumn = bestMatch(headers, LAST_NAME_CANDIDATES, [firstNameColumn].filter((i): i is number => i !== null));
  const splitNameColumns = [firstNameColumn, lastNameColumn].filter(
    (i): i is number => i !== null
  );
  const nameColumn = bestMatch(headers, NAME_CANDIDATES, splitNameColumns);

  // A sheet carrying both "Full Name" and "First Name"/"Last Name" is best read
  // from the single column; keeping both would join the name to itself.
  const useSingleName = nameColumn !== null;

  const partyColumn = bestMatch(
    headers,
    PARTY_CANDIDATES,
    [nameColumn, firstNameColumn, lastNameColumn].filter((i): i is number => i !== null)
  );
  // A column already doing duty as the household must not double as the group
  // tag: it would tag every household uniquely, giving every guest a tag shared
  // with nobody outside their own party and no signal for the optimiser.
  const used = [nameColumn, firstNameColumn, lastNameColumn, partyColumn].filter(
    (i): i is number => i !== null
  );
  let groupColumn = bestMatch(headers, GROUP_CANDIDATES, used);

  // Guard against a "group" column that is really a per-guest descriptor: if
  // nearly every value is unique it cannot express a shared group, so it is
  // worse than no tags at all.
  if (groupColumn !== null && rows.length >= 4) {
    const values = rows.map((r) => (r[groupColumn as number] ?? "").trim()).filter(Boolean);
    const distinct = new Set(values.map((v) => v.toLowerCase())).size;
    if (values.length > 0 && distinct > values.length * 0.7) groupColumn = null;
  }

  const rsvpColumn = bestMatch(headers, RSVP_CANDIDATES, used);

  return {
    nameColumn,
    firstNameColumn: useSingleName ? null : firstNameColumn,
    lastNameColumn: useSingleName ? null : lastNameColumn,
    groupColumn,
    partyColumn,
    rsvpColumn,
    // Default on: a list with an RSVP column almost always contains declines,
    // and silently seating them inflates the plan in a way that is easy to miss
    // and tedious to undo by hand.
    onlyAttending: rsvpColumn !== null,
  };
}

// ---------------------------------------------------------------------------
// Building the guest list
// ---------------------------------------------------------------------------

const splitTagCell = (raw: string) =>
  raw
    .split(/[,;/|]/)
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean);

// A household of exactly two becomes a must_sit_together constraint -- a couple,
// or a pair of siblings -- because must_sit_together is satisfied only by
// genuinely adjacent seats (adjacency == 1), which is exactly what seating two
// people from one household means.
//
// A household of three or more becomes a shared *tag* instead, not a
// constraint. Three people cannot all be adjacent, so must_sit_together would
// guarantee violations; and could_sit_together is the user's own channel for
// knowledge the tags don't capture ("Alice and Bob get on particularly well").
// Filling it with dozens of inferred household pairs would bury the handful the
// user added deliberately. A household genuinely is a social group, which is
// what tags are for, and the relation score's 1/(size - 1) weighting already
// handles group size gracefully -- so no cap is needed here either.
const PAIR_SIZE = 2;

export function buildGuestList(
  table: DetectedTable,
  mapping: ColumnMapping
): BuiltGuestList {
  const notes: string[] = [];
  const cell = (row: string[], index: number | null) =>
    index === null ? "" : (row[index] ?? "").trim();

  let rows = table.rows;

  if (mapping.rsvpColumn !== null && mapping.onlyAttending) {
    const before = rows.length;
    rows = rows.filter((row) => readsAsAttending(cell(row, mapping.rsvpColumn)));
    const excluded = before - rows.length;
    if (excluded > 0) {
      // Names the column rather than saying "RSVP": at a conference or a company
      // dinner the column is called something like Registered, and the note has
      // to describe the sheet in front of the user.
      notes.push(
        `${excluded} ${excluded === 1 ? "guest" : "guests"} left out because their "${table.headers[mapping.rsvpColumn]}" isn't a yes.`
      );
    }
  }

  let unnamed = 0;
  const entries: { name: string; tags: string[]; party: string }[] = [];

  for (const row of rows) {
    const name =
      mapping.nameColumn !== null
        ? cell(row, mapping.nameColumn)
        : [cell(row, mapping.firstNameColumn), cell(row, mapping.lastNameColumn)]
            .filter(Boolean)
            .join(" ");

    if (!name) {
      unnamed++;
      continue;
    }

    entries.push({
      name,
      tags: splitTagCell(cell(row, mapping.groupColumn)),
      party: cell(row, mapping.partyColumn),
    });
  }

  if (unnamed > 0) {
    notes.push(
      `${unnamed} ${unnamed === 1 ? "row" : "rows"} had no name and ${unnamed === 1 ? "was" : "were"} skipped. Add a name (e.g. "Dan's guest") if ${unnamed === 1 ? "it's" : "they're"} a plus one.`
    );
  }

  // Duplicate names are disambiguated rather than rejected. Two guests really
  // can share a name, and the old behaviour (warn, and refuse to let either be
  // referenced by a constraint) made the list unusable until the user renamed a
  // real guest by hand.
  const counts = new Map<string, number>();
  for (const e of entries) {
    const key = e.name.toLowerCase();
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  let disambiguated = 0;
  // Two passes, because a qualifier is not guaranteed to be distinguishing: two
  // guests with the same name are quite often in the same party or group (the
  // two Dev Patels on the same work table), which would hand both the identical
  // "Dev Patel (Work)". The second pass guarantees uniqueness outright.
  const withQualifier = entries.map((entry) => {
    const key = entry.name.toLowerCase();
    if ((counts.get(key) ?? 0) <= 1) return entry.name;
    disambiguated++;
    const qualifier = entry.party || entry.tags[0] || "";
    return qualifier ? `${entry.name} (${qualifier})` : entry.name;
  });

  const finalCounts = new Map<string, number>();
  for (const name of withQualifier) {
    const key = name.toLowerCase();
    finalCounts.set(key, (finalCounts.get(key) ?? 0) + 1);
  }
  const used = new Map<string, number>();

  const guests: Guest[] = entries.map((entry, id) => {
    let name = withQualifier[id];
    const key = name.toLowerCase();
    if ((finalCounts.get(key) ?? 0) > 1) {
      const n = (used.get(key) ?? 0) + 1;
      used.set(key, n);
      // The qualifier failed to distinguish them, so it is only noise here --
      // "Dev Patel 1" reads better than "Dev Patel (Work) 1".
      name = `${entry.name} ${n}`;
    }
    return { id, name, relation_tags: entry.tags };
  });

  if (disambiguated > 0) {
    notes.push(
      `${disambiguated} guests shared a name with someone else, so a note in brackets was added to tell them apart.`
    );
  }

  const constraints: Constraint[] = [];
  if (mapping.partyColumn !== null) {
    // Indices into `guests`, grouped by household. Index rather than id,
    // because a larger household's tag is written back onto the guest below.
    const parties = new Map<string, number[]>();
    entries.forEach((entry, i) => {
      if (!entry.party) return;
      const key = entry.party.toLowerCase();
      parties.set(key, [...(parties.get(key) ?? []), i]);
    });

    // "Pairs", not "couples": a household of two is as likely to be two siblings
    // or a parent and child, and the note is shown to the user.
    let pairs = 0;
    let groupedHouseholds = 0;

    for (const [key, members] of parties.entries()) {
      if (members.length < 2) continue;

      if (members.length === PAIR_SIZE) {
        pairs++;
        constraints.push({
          guest_a_id: guests[members[0]].id,
          guest_b_id: guests[members[1]].id,
          relationship: "must_sit_together",
        });
        continue;
      }

      groupedHouseholds++;
      for (const index of members) {
        // Guarded so a household whose name already matches one of the guest's
        // group tags doesn't get counted twice in the relation score.
        if (!guests[index].relation_tags.includes(key)) {
          guests[index].relation_tags.push(key);
        }
      }
    }

    const columnName = table.headers[mapping.partyColumn];
    if (pairs > 0) {
      notes.push(
        `${pairs} ${pairs === 1 ? "pair" : "pairs"} from the "${columnName}" column will be seated next to each other.`
      );
    }
    if (groupedHouseholds > 0) {
      notes.push(
        groupedHouseholds === 1
          ? `1 larger household from the "${columnName}" column became a group, so they're seated near each other without taking up a rule of their own.`
          : `${groupedHouseholds} larger households from the "${columnName}" column became groups, so they're seated near each other without taking up a rule of their own.`
      );
    }
  }

  return { guests, constraints, notes };
}

/** True when the mapping can produce names at all -- gates the import button. */
export function mappingIsUsable(mapping: ColumnMapping): boolean {
  return (
    mapping.nameColumn !== null ||
    mapping.firstNameColumn !== null ||
    mapping.lastNameColumn !== null
  );
}


// ---------------------------------------------------------------------------
// Explicit constraint sheets
// ---------------------------------------------------------------------------

const GUEST_A_CANDIDATES = ["guest a", "guest 1", "guesta", "person a", "name a", "from", "guest"];
const GUEST_B_CANDIDATES = ["guest b", "guest 2", "guestb", "person b", "name b", "to", "with"];
const RELATIONSHIP_COLUMN_CANDIDATES = ["relationship", "relation", "rule", "type", "constraint"];

export interface BuiltConstraints {
  constraints: Constraint[];
  warnings: string[];
}

/**
 * Resolves a Constraints sheet against an already-built guest list, matching
 * guests by name. Rows that can't be resolved are reported rather than dropped
 * silently, since a constraint the user took the trouble to write down going
 * missing without a word is how a plan ends up quietly wrong.
 */
export function buildConstraintsFromGrid(
  grid: Grid,
  guests: Guest[]
): BuiltConstraints {
  const table = detectTable(grid);
  const constraints: Constraint[] = [];
  const warnings: string[] = [];

  const guestAColumn = bestMatch(table.headers, GUEST_A_CANDIDATES);
  const guestBColumn = bestMatch(
    table.headers,
    GUEST_B_CANDIDATES,
    [guestAColumn].filter((i): i is number => i !== null)
  );
  const relationshipColumn = bestMatch(
    table.headers,
    RELATIONSHIP_COLUMN_CANDIDATES,
    [guestAColumn, guestBColumn].filter((i): i is number => i !== null)
  );

  if (guestAColumn === null || guestBColumn === null || relationshipColumn === null) {
    if (table.rows.length > 0) {
      warnings.push(
        "Found a Constraints sheet but couldn't tell which columns held the two guests and the relationship, so it was skipped."
      );
    }
    return { constraints, warnings };
  }

  // Guests are matched on the name as imported. Names were made unique during
  // the guest build, so a lookup can't resolve ambiguously here.
  const idByName = new Map<string, GuestId>();
  for (const guest of guests) idByName.set(guest.name.toLowerCase(), guest.id);
  // Also index the pre-disambiguation name, so a constraint written against
  // "Dev Patel" still resolves after the import renamed them "Dev Patel 1".
  const idByBaseName = new Map<string, GuestId[]>();
  for (const guest of guests) {
    const base = guest.name.replace(/\s*(\(.*\))?\s*\d*$/, "").trim().toLowerCase();
    idByBaseName.set(base, [...(idByBaseName.get(base) ?? []), guest.id]);
  }

  const resolve = (raw: string): GuestId | undefined => {
    const key = raw.trim().toLowerCase();
    if (!key) return undefined;
    const exact = idByName.get(key);
    if (exact !== undefined) return exact;
    const candidates = idByBaseName.get(key);
    // Only unambiguous base-name matches are accepted.
    return candidates?.length === 1 ? candidates[0] : undefined;
  };

  table.rows.forEach((row, i) => {
    const rowNumber = i + table.skippedLeadingRows + 2;
    const aName = (row[guestAColumn] ?? "").trim();
    const bName = (row[guestBColumn] ?? "").trim();
    const relationshipLabel = (row[relationshipColumn] ?? "").trim();
    if (!aName && !bName && !relationshipLabel) return;

    const guestAId = resolve(aName);
    const guestBId = resolve(bName);
    const relationship = labelToRelationship(relationshipLabel);

    if (guestAId === undefined) {
      warnings.push(`Constraints row ${rowNumber}: no guest named "${aName}" in the list.`);
    }
    if (guestBId === undefined) {
      warnings.push(`Constraints row ${rowNumber}: no guest named "${bName}" in the list.`);
    }
    if (relationship === undefined) {
      warnings.push(
        `Constraints row ${rowNumber}: "${relationshipLabel}" isn't a relationship we recognise (try ${RELATIONSHIP_HINT}).`
      );
    }
    if (guestAId !== undefined && guestBId !== undefined && relationship !== undefined) {
      if (guestAId === guestBId) {
        warnings.push(`Constraints row ${rowNumber}: "${aName}" is paired with themselves.`);
        return;
      }
      constraints.push({ guest_a_id: guestAId, guest_b_id: guestBId, relationship });
    }
  });

  return { constraints, warnings };
}
