import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Big_Shoulders, Libre_Franklin } from "next/font/google";
import "./globals.css";

// Brand typefaces, per common-table-brand-assets/README.md: Libre Franklin for
// the wordmark and body text, Big Shoulders for headlines.
const libreFranklin = Libre_Franklin({
  variable: "--font-libre-franklin",
  subsets: ["latin"],
});

// Next ships no metric overrides for Big Shoulders, so it can't build a
// size-matched fallback (the build warns about this). Naming condensed faces
// here keeps the pre-load swap from jumping as wide as plain Arial would.
const bigShoulders = Big_Shoulders({
  variable: "--font-big-shoulders",
  subsets: ["latin"],
  fallback: ["Arial Narrow", "Helvetica Neue", "sans-serif"],
});

export const metadata: Metadata = {
  title: "Common Table",
  description: "Your go-to app for optimising seating plans.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${libreFranklin.variable} ${bigShoulders.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-page font-sans">
        <nav className="print:hidden sticky top-0 z-50 bg-nav backdrop-blur-md border-b border-slate-100 h-20 grid grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 sm:px-6">
          <Link href="/" aria-label="Common Table home" className="justify-self-start">
            <Image
              src="/brand/common-table-emblem-colour.svg"
              alt=""
              width={40}
              height={40}
              priority
              className="h-10 w-10"
            />
          </Link>
          <Link
            href="/"
            className="tracking-widest uppercase text-lg sm:text-2xl md:text-3xl font-sans font-bold text-brand-dark justify-self-center whitespace-nowrap"
          >
            Common Table
          </Link>
          <div className="justify-self-end">
            <Link
              href="/about"
              className="text-sm font-semibold text-slate-500 hover:text-brand-dark transition-colors whitespace-nowrap"
            >
              How it works
            </Link>
          </div>
        </nav>
        <div className="flex-1 flex flex-col">{children}</div>
        <footer className="print:hidden border-t border-slate-100 py-6 text-center text-sm text-slate-400">
          <p>
            Made by{" "}
            <a
              href="https://www.linkedin.com/in/israel-s-5a9546125"
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-slate-500 hover:text-brand-dark transition-colors"
            >
              Israel Shitta
            </a>
          </p>
          <p className="mt-1">
            Free to use.{" "}
            <a
              href="https://ko-fi.com/israelshitta"
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-slate-500 hover:text-brand-dark transition-colors"
            >
              Buy me a meal deal
            </a>{" "}
            if it saved you some stress.
          </p>
        </footer>
      </body>
    </html>
  );
}
