import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SalesAgents AI — LAP Voice Agent",
  description: "AI voice agent dashboard for Home Credit Loan Against Property offers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
