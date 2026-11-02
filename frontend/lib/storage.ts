import { Constraint, Guest, TableStyle } from "./types";

// Bumped whenever the shape below changes incompatibly. A saved draft from an
// older version is discarded rather than migrated -- a half-understood guest
// list is worse than a clean start.
const STORAGE_KEY = "commontable.draft.v1";

export interface SavedDraft {
  savedAt: string;
  tableConfig: {
    style: TableStyle | null;
    numTables: number;
    numSeatsPerTable: number;
    headSeat: boolean;
    footSeat: boolean;
  };
  guestData: {
    guests: Guest[];
    constraints: Constraint[];
  };
}

// `undefined` means "not read yet"; `null` means "read, and there is no draft".
// Cached because useSyncExternalStore calls getSnapshot on every render and
// compares by identity -- parsing the JSON afresh each time would return a new
// object every call and spin forever.
let cachedDraft: SavedDraft | null | undefined;
const listeners = new Set<() => void>();

function notify() {
  cachedDraft = undefined;
  for (const listener of listeners) listener();
}

// Every access is wrapped: localStorage throws rather than returning null in a
// private window and when site data is blocked, and a draft is a convenience,
// so a failure here must never take the planner down with it.
export function saveDraft(draft: Omit<SavedDraft, "savedAt">): void {
  try {
    const payload: SavedDraft = { ...draft, savedAt: new Date().toISOString() };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    notify();
  } catch {
    // Out of quota, or storage unavailable -- nothing useful to tell the user.
  }
}

/**
 * Subscribes to the saved draft, for useSyncExternalStore. The `storage` event
 * covers the same list being edited in a second tab, which is easy to do when a
 * plan is worked on alongside the spreadsheet it came from.
 */
export function subscribeToDraft(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY || event.key === null) notify();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function getDraftSnapshot(): SavedDraft | null {
  if (cachedDraft === undefined) cachedDraft = loadDraft();
  return cachedDraft;
}

// There is no localStorage while server-rendering, so the server always renders
// as though no draft exists and the resume banner appears once hydrated.
export function getDraftServerSnapshot(): SavedDraft | null {
  return null;
}

export function loadDraft(): SavedDraft | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);

    // Hand-validated rather than trusted: this JSON survives across deploys, so
    // it can have been written by an older build of the app.
    if (typeof parsed !== "object" || parsed === null) return null;
    const draft = parsed as Partial<SavedDraft>;
    if (!draft.guestData || !Array.isArray(draft.guestData.guests)) return null;
    if (!draft.tableConfig) return null;

    const guests = draft.guestData.guests.filter(
      (g): g is Guest =>
        typeof g === "object" && g !== null && typeof g.name === "string"
    );
    if (guests.length === 0) return null;

    return {
      savedAt: typeof draft.savedAt === "string" ? draft.savedAt : "",
      tableConfig: draft.tableConfig,
      guestData: {
        guests,
        constraints: Array.isArray(draft.guestData.constraints)
          ? draft.guestData.constraints
          : [],
      },
    };
  } catch {
    return null;
  }
}

export function clearDraft(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
    notify();
  } catch {
    // Nothing to do -- the draft simply stays until the browser clears it.
  }
}
