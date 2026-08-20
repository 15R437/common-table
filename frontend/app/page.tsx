"use client";

import { useState } from "react";
import { Table } from "@/lib/types";
import StepProgress from "@/components/StepProgress";
import Step1TableConfig, { TableConfig } from "@/components/Step1TableConfig";
import Step2GuestInput, { GuestData } from "@/components/Step2GuestInput";
import Step3Results from "@/components/Step3Results";

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

export default function Home() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [tableConfig, setTableConfig] = useState<TableConfig>({
    style: null,
    numTables: 1,
    numSeatsPerTable: 6,
    headSeat: false,
    footSeat: false,
  });
  const [guestData, setGuestData] = useState<GuestData>({
    guests: [],
    constraints: [],
  });

  const tables = buildTables(tableConfig);

  return (
    <main className="max-w-4xl mx-auto mt-12 mb-24 p-8 bg-nav rounded-3xl shadow-brand-glow w-full">
      <StepProgress currentStep={step} />

      {step === 1 && (
        <Step1TableConfig
          value={tableConfig}
          onChange={setTableConfig}
          onNext={() => setStep(2)}
        />
      )}

      {step === 2 && (
        <Step2GuestInput
          value={guestData}
          onChange={setGuestData}
          onOptimise={() => setStep(3)}
          onBack={() => setStep(1)}
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
