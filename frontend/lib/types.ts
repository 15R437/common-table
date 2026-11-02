// Mirrors backend/app/schema.py. Keep in sync by hand for now -- see the
// openapi-typescript note in api.ts for the longer-term fix.

export type GuestId = string | number;

export interface Guest {
  id: GuestId;
  name: string;
  relation_tags: string[];
}

export type TableStyle = "banquet" | "cabaret" | "theatre";

interface TableBase {
  id: GuestId;
  num_seats: number;
}

export interface BanquetTable extends TableBase {
  type: "banquet";
  head_seat: boolean;
  foot_seat: boolean;
}

export interface CabaretTable extends TableBase {
  type: "cabaret";
  full_circle: boolean;
}

export interface TheatreSection extends TableBase {
  type: "theatre";
  num_rows: number;
}

export type Table = BanquetTable | CabaretTable | TheatreSection;

export type Relationship =
  | "must_sit_together"
  | "could_sit_together"
  | "must_sit_apart";

export interface Constraint {
  guest_a_id: GuestId;
  guest_b_id: GuestId;
  relationship: Relationship;
}

export interface SeatingRequest {
  guests: Guest[];
  tables: Table[];
  constraints: Constraint[];
}

interface ConstraintStats {
  satisfied: number;
  total: number;
}

export interface ConstraintViolation {
  guest_a: Guest;
  guest_b: Guest;
}

export interface SeatingResponse {
  // table_assignments[tableId][seatIndex] -> guest. Both keys come back as
  // strings once this crosses JSON, even though seat index is an int on the
  // Python side.
  table_assignments: Record<string, Record<string, Guest>>;
  relation_score: number;
  constraint_score: number;
  must_sit_together: ConstraintStats;
  could_sit_together: ConstraintStats;
  must_sit_apart: ConstraintStats;
  must_sit_together_violations: ConstraintViolation[];
  must_sit_apart_violations: ConstraintViolation[];
}

/** table id -> seat index -> guest id, mirroring SeatingResponse.table_assignments. */
export type SeatAssignment = Record<string, Record<number, GuestId>>;

export interface EvaluateRequest extends SeatingRequest {
  assignment: SeatAssignment;
}

export interface FeedbackRequest {
  verdict: "up" | "down";
  message?: string;
  guest_count?: number;
  table_count?: number;
  constraint_count?: number;
}
