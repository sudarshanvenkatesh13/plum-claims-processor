import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Plum Claims Processor",
  description: "AI-powered health insurance claims processing",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-gray-50">
        <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
          <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="w-7 h-7 rounded-lg bg-teal-600 flex items-center justify-center shrink-0">
                <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4 text-white" stroke="currentColor" strokeWidth="2.5">
                  <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <span className="font-semibold text-gray-900 text-sm tracking-tight group-hover:text-teal-700 transition-colors">
                Plum Claims Processor
              </span>
            </Link>

            <nav className="flex items-center gap-1">
              <Link href="/" className="px-3 py-1.5 text-sm text-gray-600 hover:text-teal-700 hover:bg-teal-50 rounded-md transition-colors font-medium">
                Submit Claim
              </Link>
              <Link href="/claims" className="px-3 py-1.5 text-sm text-gray-600 hover:text-teal-700 hover:bg-teal-50 rounded-md transition-colors font-medium">
                All Claims
              </Link>
              <Link href="/documents" className="px-3 py-1.5 text-sm text-gray-600 hover:text-teal-700 hover:bg-teal-50 rounded-md transition-colors font-medium">
                Sample Docs
              </Link>
              <Link href="/eval" className="px-3 py-1.5 text-sm text-gray-600 hover:text-teal-700 hover:bg-teal-50 rounded-md transition-colors font-medium">
                Eval Suite
              </Link>
            </nav>
          </div>
        </header>

        <main className="flex-1">{children}</main>

        <footer className="border-t border-gray-200 bg-white mt-auto">
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between text-xs text-gray-400">
            <span>Plum Health Insurance Claims Processor</span>
            <span>Built by Sudarshan Venkatesh</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
