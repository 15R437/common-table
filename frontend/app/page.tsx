"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Table } from "@/lib/types";
import StepProgress from "@/components/StepProgress";
import Step1TableConfig, { TableConfig } from "@/components/Step1TableConfig";
import Step2GuestInput, { GuestData } from "@/components/Step2GuestInput";
import Step3Results from "@/components/Step3Results";
import { SAMPLE_TABLE_CONFIG, buildSampleWedding } from "@/lib/sampleWedding";
import {
  clearDraft,
  getDraftServerSnapshot,
  getDraftSnapshot,
  saveDraft,
  subscribeToDraft,
} from "@/lib/storage";

function buildTables(config: TableConfig): Table[] {
  if (!config.style) return [];

  if (config.style === "theatre") {
    return [
      {
        id: 0,
        type: "theatre",
        num_seats: config.numTables * config.numSeatsPerTable,
        num_rows: config.numTables,
      },
    ];
  }

  return Array.from({ length: config.numTables }, (_, i): Table =>
    config.style === "banquet"
      ? {
          id: i,
          type: "banquet",
          num_seats: config.numSeatsPerTable,
          head_seat: config.headSeat,
          foot_seat: config.footSeat,
        }
      : {
          id: i,
          type: "cabaret",
          num_seats: config.numSeatsPerTable,
          full_circle: true,
        }
  );
}

const EMPTY_CONFIG: TableConfig = {
  style: null,
  numTables: 1,
  numSeatsPerTable: 6,
  headSeat: false,
  footSeat: false,
};

export default function Home() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [tableConfig, setTableConfig] = useState<TableConfig>(EMPTY_CONFIG);
  const [guestData, setGuestData] = useState<GuestData>({ guests: [], constraints: [] });
  const [dismissedResume, setDismissedResume] = useState(false);

  // The saved draft is read as an external store rather than copied into state
  // on mount. Copying it in an effect would mean a setState during the first
  // commit, and reading localStorage in a lazy useState initializer would make
  // the hydrated markup disagree with the server's. This way the draft stays
  // where it is until the user asks for it back -- which also means the page
  // never appears to jump ahead on its own.
  const savedDraft = useSyncExternalStore(
    subscribeToDraft,
    getDraftSnapshot,
    getDraftServerSnapshot
  );

  // Debounced so typing a name doesn't write the whole list to disk on every
  // keystroke. The guard keeps an empty initial state from overwriting a real
  // saved draft before the restore effect above has run.
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (guestData.guests.length === 0) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      saveDraft({ tableConfig, guestData });
    }, 500);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [tableConfig, guestData]);

  function resumeDraft() {
    if (!savedDraft) return;
    setTableConfig({ ...EMPTY_CONFIG, ...savedDraft.tableConfig });
    setGuestData(savedDraft.guestData);
    setStep(2);
  }

  function startFresh() {
    clearDraft();
    setDismissedResume(true);
    setTableConfig(EMPTY_CONFIG);
    setGuestData({ guests: [], constraints: [] });
    setStep(1);
  }

  function loadSample() {
    const { guests, constraints } = buildSampleWedding();
    setTableConfig(SAMPLE_TABLE_CONFIG);
    setGuestData({ guests, constraints });
    setDismissedResume(true);
    setStep(3);
  }

  const tables = buildTables(tableConfig);
  const totalSeats = tables.reduce((sum, table) => sum + table.num_seats, 0);

  // Offered only while there is nothing in progress to lose: once a list is
  // loaded, the banner would be inviting the user to overwrite their own work.
  const showResume =
    step === 1 &&
    !dismissedResume &&
    savedDraft !== null &&
    guestData.guests.length === 0;

  return (
    <main className="max-w-4xl mx-auto mt-12 mb-24 p-4 sm:p-8 bg-nav rounded-3xl shadow-brand-glow w-full print:m-0 print:p-0 print:max-w-none print:bg-page print:shadow-none print:rounded-none">
      <div className="print:hidden">
        <StepProgress currentStep={step} />
      </div>

      {showResume && (
        <div className="mb-8 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-brand-light rounded-2xl p-5">
          <p className="text-sm text-slate-600">
            <span className="font-semibold text-brand-dark">
              Your {savedDraft.guestData.guests.length}-guest list is still here.
            </span>{" "}
            Saved on this device, in this browser.
          </p>
          <div className="flex gap-3 shrink-0">
            <button
              type="button"
              onClick={resumeDraft}
              className="rounded-full bg-brand-dark text-white px-5 py-2 text-sm font-semibold hover:bg-brand-dark/90 transition-colors"
            >
              Pick up where I left off
            </button>
            <button
              type="button"
              onClick={startFresh}
              className="rounded-full border-2 border-slate-200 bg-white text-slate-600 px-5 py-2 text-sm font-semibold hover:border-brand-dark hover:text-brand-dark transition-colors"
            >
              Start fresh
            </button>
          </div>
        </div>
      )}

      {step === 1 && (
        <Step1TableConfig
          value={tableConfig}
          onChange={setTableConfig}
          onNext={() => setStep(2)}
          onLoadSample={loadSample}
        />
      )}

      {step === 2 && (
        <Step2GuestInput
          value={guestData}
          onChange={setGuestData}
          onOptimise={() => setStep(3)}
          onBack={() => setStep(1)}
          totalSeats={totalSeats}
          seatUnit="seats"
        />
      )}

      {step === 3 && (
        <Step3Results
          guests={guestData.guests}
          tables={tables}
          constraints={guestData.constraints}
          onBack={() => setStep(2)}
        />
      )}
    </main>
  );
}
