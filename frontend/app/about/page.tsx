import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "How it works — Common Table",
  description: "A plain-language look at how Common Table plans your seating.",
};

function StepBadge({ number }: { number: number }) {
  return (
    <div className="w-8 h-8 shrink-0 rounded-full flex items-center justify-center text-lg font-bold bg-brand-dark text-white">
      {number}
    </div>
  );
}

function ForTheCurious({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-sm text-slate-500 leading-relaxed mt-3 pt-3 border-t border-slate-100">
      <span className="font-semibold text-slate-600">For the curious: </span>
      {children}
    </p>
  );
}

export default function About() {
  return (
    <main className="max-w-3xl mx-auto mt-12 mb-24 p-8 bg-nav rounded-3xl shadow-brand-glow w-full">
      <h1 className="text-3xl font-display font-bold text-brand-dark mb-3 text-center">
        How it works
      </h1>
      <div className="w-16 h-1 bg-brand-dark rounded-full mx-auto mb-8" />

      <p className="text-lg text-slate-600 leading-relaxed text-center mb-10">
        Common Table takes the headache out of planning a seating chart. Give it your
        tables, your guest list together with who should (or shouldn&apos;t) sit together, and it
        suggests a seating arrangement as a starting point for you to work with and edit as you wish.
      </p>

      <div className="space-y-6">
        <section className="p-6 sm:p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100">
          <div className="flex items-center gap-3 mb-4">
            <StepBadge number={1} />
            <h2 className="text-xl font-bold text-brand-dark">Table Style</h2>
          </div>
          <p className="text-slate-700 leading-relaxed">
            Common Table supports three seating styles: banquet tables, cabaret tables, and theatre-style rows.
            Each one of these has its own notion of which seats count as &apos;near&apos; each other, with seats
            right next to you nearer than ones across the table, and those in turn nearer than seats on different
            tables. Intuitively, we want people who would get on well to be sat near each other.
          </p>
          <ForTheCurious>
            each style defines this with a graded adjacency value: e.g. on a banquet table, adjacent seats
            score 1, directly opposite seats score 0.75, and diagonally-opposite seats score 0.5. Pairs of
            seats that are further appart (e.g. on opposite ends of the table) will have an adjacency value of 0.
          </ForTheCurious>
        </section>

        <section className="p-6 sm:p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100">
          <div className="flex items-center gap-3 mb-4">
            <StepBadge number={2} />
            <h2 className="text-xl font-bold text-brand-dark">Guest List</h2>
          </div>
          <p className="text-slate-700 leading-relaxed">
            You can enter your guest list manually or upload a spreadsheet. Every pair of guests is assigned a score
            indicating their relation to each other so that pairs of guests with higher scores are more likely to be
            seated near each other. Common Table provides two mechanisms for generating these scores.
          </p>

          <div className="grid sm:grid-cols-2 gap-4 mt-6">
            <div className="bg-slate-50 rounded-xl border border-slate-100 p-5">
              <span className="inline-block text-xs font-bold uppercase tracking-wide text-brand-dark bg-brand-light rounded-full px-3 py-1 mb-3">
                Tags
              </span>
              <p className="text-sm text-slate-600 leading-relaxed mb-3">
                Each guest has a (possibly empty) list of tags which may indicate e.g. the social groups they belong to
                or their interests, so that guests who have lots of specific tags in common generally have a higher
                score. Users should pick their tags carefully to reflect the social groups or sets of interest that
                are relevant to their application.
              </p>
              <div className="flex flex-wrap gap-2 mb-3">
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-brand-light text-brand-dark">
                  work_friends
                </span>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-brand-light text-brand-dark">
                  school_friends
                </span>
              </div>
              <ForTheCurious>
                suppose C guests share the tag &apos;work_friends&apos;, including Alice and Bob. Then this tag
                contributes 1/(C-1) to their pairwise score. If D guests share the tag &apos;school_friends&apos; and
                Alice and Bob are amongst these too, a further 1/(D-1) is added to their pairwise score.
              </ForTheCurious>
            </div>

            <div className="bg-slate-50 rounded-xl border border-slate-100 p-5">
              <span className="inline-block text-xs font-bold uppercase tracking-wide text-brand-dark bg-brand-light rounded-full px-3 py-1 mb-3">
                Constraints
              </span>
              <p className="text-sm text-slate-600 leading-relaxed mb-3">
                Constraints describe relationships that may not be captured by tags or relationships that we want
                to emphasise: who <em>must</em> sit together (e.g. couples), who <em>could</em> sit together (e.g. people who particularly get along),
                and who <em>must</em> sit apart (e.g. exes).
              </p>
              <div className="flex flex-wrap gap-2 mb-3">
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
                  must sit together
                </span>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                  could sit together
                </span>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-rose-50 text-rose-700 border border-rose-100">
                  must sit apart
                </span>
              </div>
              <ForTheCurious>
                if Alice and Bob must sit together, a large positive number is added to their pairwise score
                (e.g. 10). If they merely could sit together, a smaller positive number is added (e.g. 5). But
                if they must sit apart, a large negative number is added instead (e.g. -10).
              </ForTheCurious>
            </div>
          </div>
        </section>

        <section className="p-6 sm:p-8 bg-white rounded-2xl shadow-brand-glow border border-slate-100">
          <div className="flex items-center gap-3 mb-4">
            <StepBadge number={3} />
            <h2 className="text-xl font-bold text-brand-dark">Optimisation</h2>
          </div>
          <p className="text-slate-700 leading-relaxed">
            Behind the scenes, Common Table quickly learns an arrangement that sits guests with high pairwise
            scores near each other. You can take this seating chart as a starting point and add your own finishing touches.
          </p>
          <ForTheCurious>
            it does this using a gradient-based optimisation algorithm, a standard technique for quickly finding
            a good (though not always perfect) arrangement out of a large number of possible ones.
          </ForTheCurious>
        </section>
      </div>

      <p className="text-sm text-slate-500 mt-6 p-4 rounded-xl bg-white border border-slate-100">
        Nothing you enter is saved anywhere: it lives in your browser for the session and
        is sent to the server only to calculate your plan.
      </p>
    </main>
  );
}
