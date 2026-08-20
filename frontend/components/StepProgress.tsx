const STEP_LABELS = ["Table setup", "Guest list", "Result"];

export default function StepProgress({ currentStep }: { currentStep: 1 | 2 | 3 }) {
  return (
    <div className="mb-12">
      <div className="relative flex justify-between items-center">
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-1 bg-slate-100 -z-10 rounded-full" />
        <div
          className="absolute left-0 top-1/2 -translate-y-1/2 h-1 bg-brand-dark -z-10 rounded-full transition-all duration-500"
          style={{ width: `${((currentStep - 1) / 2) * 100}%` }}
        />
        {STEP_LABELS.map((label, i) => {
          const step = i + 1;
          const isActive = step <= currentStep;
          return (
            <div key={label} className="flex flex-col items-center gap-2">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-lg font-bold ${
                  isActive
                    ? "bg-brand-dark text-white"
                    : "bg-page border border-slate-200 text-slate-400"
                }`}
              >
                {step}
              </div>
              <span
                className={`text-xs font-semibold ${
                  isActive ? "text-brand-dark" : "text-slate-400"
                }`}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
