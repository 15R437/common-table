import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "How it works — Common Table",
  description: "A plain-language look at how Common Table plans your seating.",
};

export default function About() {
  return (
    <main className="max-w-3xl mx-auto mt-12 mb-24 p-8 bg-nav rounded-3xl shadow-brand-glow w-full">
      <h1 className="text-3xl font-display font-bold text-brand-dark mb-6 text-center">
        How it works
      </h1>

      <div className="space-y-6 text-slate-700 leading-relaxed">
        <p>
          Common Table takes the headache out of planning a seating chart. Tell it your
          tables, your guests, and who should (or shouldn&apos;t) sit together, and it works
          out a layout for you.
        </p>

        <section>
          <h2 className="text-lg font-bold text-brand-dark mb-2">1. Set up your tables</h2>
          <p>
            Choose a table style — banquet, cabaret, or theatre-style rows — and how many
            seats each one has.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-brand-dark mb-2">2. Add your guests</h2>
          <p>
            Enter your guest list and describe the relationships that matter: who{" "}
            <em>must</em> sit together (like a couple), who <em>could</em> sit together
            (like old friends), and who <em>must</em> sit apart. You can type these in
            directly or upload a spreadsheet.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-brand-dark mb-2">3. Let it optimise</h2>
          <p>
            Behind the scenes, Common Table treats seating as a puzzle: it searches through
            possible arrangements, scoring each one by how many of your preferences it
            satisfies, and keeps refining the layout until it finds a strong solution. Your
            &quot;must&quot; constraints are prioritised — the solver will always try
            hardest to honour those first, and will tell you plainly if one couldn&apos;t
            be satisfied (for example, if two people who must sit apart can&apos;t both fit
            at a conflict-free table).
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-brand-dark mb-2">4. Review and download</h2>
          <p>
            You get the finished plan as a chart or a simple list, can search for any guest
            to find their seat, and can download the whole thing as a CSV to keep, print, or
            share.
          </p>
        </section>

        <p className="text-sm text-slate-500 pt-4 border-t border-slate-200">
          Nothing you enter is saved anywhere — it lives in your browser for the session and
          is sent to the server only to calculate your plan.
        </p>
      </div>
    </main>
  );
}
