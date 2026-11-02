import { Constraint, Guest } from "./types";

// A plausible mid-size wedding: enough guests and overlapping groups that the
// optimiser has real work to do, and small enough that the resulting chart
// stays readable on one screen. Seats deliberately exceed guests (60 vs 58) so
// the sample also demonstrates what empty seats look like.
const SAMPLE_GROUPS: { tag: string; names: string[] }[] = [
  {
    tag: "bride's family",
    names: [
      "Linda Whitfield", "Geoff Whitfield", "Emma Whitfield", "Dan Whitfield",
      "Jean Whitfield", "Rosie Whitfield", "Alan Price", "Carol Price",
      "Hannah Price", "Nick Price",
    ],
  },
  {
    tag: "groom's family",
    names: [
      "Patricia Osei", "Michael Osei", "Yaa Osei", "Kwame Osei",
      "Afia Mensah", "Kofi Mensah", "Abena Osei", "Joseph Osei",
      "Adwoa Boateng", "Daniel Boateng",
    ],
  },
  {
    tag: "university friends",
    names: [
      "Priya Shah", "Rahul Shah", "Jess Allen", "Tom Barker", "Sophie Clarke",
      "Marcus Reid", "Nina Kowalski", "Ben Fletcher", "Leila Haddad",
      "Chris Donnelly",
    ],
  },
  {
    tag: "work friends",
    names: [
      "Angela Price", "Dev Patel", "Sam Okoro", "Ruth Levy", "Ian Mcbride",
      "Fiona Gallagher", "Tariq Ahmed", "Claire Dunn",
    ],
  },
  {
    tag: "school friends",
    names: [
      "Katie Nolan", "Liam Nolan", "Rachel Finch", "Joe Finch",
      "Amara Eze", "Victor Eze", "Megan Doyle", "Paul Doyle",
      "Steph Carter", "Alex Carter",
    ],
  },
  {
    tag: "neighbours",
    names: [
      "Margaret Hill", "Derek Hill", "Sunita Rao", "Vikram Rao",
      "Eileen Murphy", "Brendan Murphy", "Gail Thompson", "Roy Thompson",
      "Petra Novak", "Milan Novak",
    ],
  },
];

// Couples get a hard "sit together"; the exes and the divorced parents get a
// hard "sit apart". These are exactly the cases a couple reaches for the tool
// to solve, so the sample should show them being honoured on the results page.
const SAMPLE_PAIRS: { a: string; b: string; relationship: Constraint["relationship"] }[] = [
  { a: "Linda Whitfield", b: "Geoff Whitfield", relationship: "must_sit_together" },
  { a: "Alan Price", b: "Carol Price", relationship: "must_sit_together" },
  { a: "Katie Nolan", b: "Liam Nolan", relationship: "must_sit_together" },
  { a: "Margaret Hill", b: "Derek Hill", relationship: "must_sit_together" },
  { a: "Sunita Rao", b: "Vikram Rao", relationship: "must_sit_together" },
  { a: "Priya Shah", b: "Rahul Shah", relationship: "must_sit_together" },
  { a: "Patricia Osei", b: "Michael Osei", relationship: "must_sit_apart" },
  { a: "Jess Allen", b: "Tom Barker", relationship: "must_sit_apart" },
  { a: "Jean Whitfield", b: "Margaret Hill", relationship: "could_sit_together" },
  { a: "Dev Patel", b: "Marcus Reid", relationship: "could_sit_together" },
];

// Two tags for a handful of guests, so the plan isn't a trivial partition into
// six tables of one group each -- the overlaps are what make the optimiser's
// output interesting to look at.
const EXTRA_TAGS: Record<string, string[]> = {
  "Emma Whitfield": ["university friends"],
  "Kwame Osei": ["university friends"],
  "Dev Patel": ["school friends"],
  "Marcus Reid": ["work friends"],
  "Sunita Rao": ["work friends"],
  "Amara Eze": ["university friends"],
};

export const SAMPLE_TABLE_CONFIG = {
  style: "cabaret" as const,
  numTables: 6,
  numSeatsPerTable: 10,
  headSeat: false,
  footSeat: false,
};

export function buildSampleWedding(): { guests: Guest[]; constraints: Constraint[] } {
  const guests: Guest[] = [];
  for (const group of SAMPLE_GROUPS) {
    for (const name of group.names) {
      guests.push({
        id: guests.length,
        name,
        relation_tags: [group.tag, ...(EXTRA_TAGS[name] ?? [])],
      });
    }
  }

  const idByName = new Map(guests.map((g) => [g.name, g.id]));
  const constraints: Constraint[] = [];
  for (const pair of SAMPLE_PAIRS) {
    const a = idByName.get(pair.a);
    const b = idByName.get(pair.b);
    if (a === undefined || b === undefined) continue;
    constraints.push({ guest_a_id: a, guest_b_id: b, relationship: pair.relationship });
  }

  return { guests, constraints };
}
