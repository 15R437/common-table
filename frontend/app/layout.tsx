import type { Metadata } from "next";
import Link from "next/link";
import { Inter, Oswald } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const oswald = Oswald({
  variable: "--font-oswald",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Common Table",
  description: "Your go-to app for optimising seating plans.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${oswald.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-page font-sans">
        <nav className="sticky top-0 z-50 bg-nav backdrop-blur-md border-b border-slate-100 h-20 flex items-center justify-center gap-8">
          <Link
            href="/"
            className="tracking-widest uppercase text-3xl font-display font-bold text-brand-dark"
          >
            Common Table
          </Link>
          <Link
            href="/about"
            className="text-sm font-semibold text-slate-500 hover:text-brand-dark transition-colors"
          >
            How it works
          </Link>
        </nav>
        <div className="flex-1 flex flex-col">{children}</div>
        <footer className="border-t border-slate-100 py-6 text-center text-sm text-slate-400">
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
