import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Job Atlas — Your local job workspace", description: "Explore public employer job feeds. Search, save, and export jobs from your local collection." };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
