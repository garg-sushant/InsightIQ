import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/lib/query-provider";
import { AuthProvider } from "@/lib/auth-context";

export const metadata: Metadata = {
  title: "InsightIQ — AI Business Analytics & Financial Decision Support Engine",
  description:
    "Upload retail sales data to derive 100% deterministic financial KPIs, RFM customer segments, anomaly detection, and AI narrative summaries with zero PII leakage.",
  keywords: [
    "Business Intelligence",
    "AI Analytics",
    "Retail Data",
    "Financial Intelligence",
    "Anomaly Detection",
    "RFM Segmentation",
    "Next.js 15",
    "FastAPI",
  ],
  authors: [{ name: "InsightIQ Team" }],
  openGraph: {
    title: "InsightIQ — AI Business Analytics",
    description:
      "Deterministic math engine + AI narrative summaries for enterprise sales data.",
    type: "website",
  },
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
    apple: "/icon.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                  document.documentElement.classList.add('dark');
                } else {
                  document.documentElement.classList.remove('dark');
                }
              } catch (_) {}
            `,
          }}
        />
      </head>
      <body>
        <QueryProvider>
          <AuthProvider>{children}</AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
