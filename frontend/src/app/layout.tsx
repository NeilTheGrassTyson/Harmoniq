import type { Metadata } from "next";
import { Geist } from "next/font/google";
import Link from "next/link";
import { ClerkProvider } from "@clerk/nextjs";
import SearchBar from "@/components/SearchBar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Harmoniq",
  description: "A social music discovery network built around trust and musical identity.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className={`${geistSans.variable} h-full antialiased`}>
        <body className="flex min-h-full flex-col">
          <header className="border-b border-neutral-200 px-4 py-3 dark:border-neutral-800">
            <nav className="mx-auto flex max-w-4xl items-center gap-4">
              <Link
                href="/"
                className="text-sm font-light tracking-widest text-neutral-900 dark:text-neutral-100"
              >
                harmoniq
              </Link>
              <div className="flex-1">
                <SearchBar />
              </div>
            </nav>
          </header>
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
