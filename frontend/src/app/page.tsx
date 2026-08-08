"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  Database,
  FileCheck,
  FileSpreadsheet,
  Layers,
  Lock,
  PieChart,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";

export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const [activeTab, setActiveTab] = useState<"kpi" | "ai" | "privacy" | "exports">("kpi");

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary/20">
      {/* Top Navbar */}
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md shadow-primary/20">
              <BarChart3 className="h-5 w-5" />
            </div>
            <span className="text-xl font-bold tracking-tight">InsightIQ</span>
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle className="h-9 w-9" />
            {isAuthenticated ? (
              <Button asChild className="gap-2 shadow-sm">
                <Link href="/dashboard">
                  Go to Dashboard <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            ) : (
              <>
                <Button variant="ghost" asChild>
                  <Link href="/login">Sign in</Link>
                </Button>
                <Button asChild className="gap-1.5 shadow-md shadow-primary/20">
                  <Link href="/dashboard">
                    Live Demo <ChevronRight className="h-4 w-4" />
                  </Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      <main>
        {/* Hero Section */}
        <section className="relative overflow-hidden py-20 lg:py-28">
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-transparent to-transparent" />
          
          <div className="mx-auto max-w-7xl px-6 text-center">
            <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-xs font-medium text-primary backdrop-blur-sm">
              <Sparkles className="h-3.5 w-3.5" />
              <span>AI-Powered Decision Support Engine for Enterprise Sales Data</span>
            </div>

            <h1 className="mx-auto mt-6 max-w-4xl text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl">
              Turn Raw Sales Data Into <br />
              <span className="bg-gradient-to-r from-primary via-indigo-500 to-purple-600 bg-clip-text text-transparent">
                Executive Financial Intelligence
              </span>
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
              Upload orders, customers, products and returns. InsightIQ computes exact financial KPIs, anomaly detection, and RFM customer segments using SQL & scikit-learn — then generates executive-ready AI narratives with zero raw PII exposure.
            </p>

            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <Button size="lg" asChild className="gap-2 px-8 text-base shadow-lg shadow-primary/25">
                <Link href={isAuthenticated ? "/dashboard" : "/login"}>
                  {isAuthenticated ? "Open Dashboard" : "Launch Demo Platform"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild className="gap-2 text-base">
                <Link href="#architecture">
                  <ShieldCheck className="h-4 w-4 text-emerald-500" />
                  The AI Boundary Guarantee
                </Link>
              </Button>
            </div>

            {/* Quick Metrics Bar */}
            <div className="mx-auto mt-16 grid max-w-4xl grid-cols-2 gap-4 sm:grid-cols-4">
              <div className="rounded-2xl border bg-card/50 p-4 text-center backdrop-blur-sm shadow-sm">
                <p className="text-2xl font-bold tracking-tight text-primary">100%</p>
                <p className="text-xs text-muted-foreground">Deterministic Math</p>
              </div>
              <div className="rounded-2xl border bg-card/50 p-4 text-center backdrop-blur-sm shadow-sm">
                <p className="text-2xl font-bold tracking-tight text-emerald-600 dark:text-emerald-400">Zero</p>
                <p className="text-xs text-muted-foreground">PII Leaks to AI</p>
              </div>
              <div className="rounded-2xl border bg-card/50 p-4 text-center backdrop-blur-sm shadow-sm">
                <p className="text-2xl font-bold tracking-tight text-indigo-600 dark:text-indigo-400">PDF & PPTX</p>
                <p className="text-xs text-muted-foreground">Server-Side Export</p>
              </div>
              <div className="rounded-2xl border bg-card/50 p-4 text-center backdrop-blur-sm shadow-sm">
                <p className="text-2xl font-bold tracking-tight text-purple-600 dark:text-purple-400">&lt; 100ms</p>
                <p className="text-xs text-muted-foreground">KPI Engine Speed</p>
              </div>
            </div>
          </div>
        </section>

        {/* Interactive Feature Preview Tabs */}
        <section className="border-t bg-muted/30 py-20">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center">
              <h2 className="text-3xl font-bold tracking-tight">Explore Platform Capabilities</h2>
              <p className="mt-2 text-muted-foreground">Experience how InsightIQ combines exact math with language models.</p>
            </div>

            <div className="mt-8 flex justify-center">
              <div className="inline-flex rounded-xl bg-card p-1.5 border shadow-sm">
                <button
                  onClick={() => setActiveTab("kpi")}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                    activeTab === "kpi" ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <TrendingUp className="h-4 w-4" /> Deterministic KPIs
                </button>
                <button
                  onClick={() => setActiveTab("ai")}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                    activeTab === "ai" ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <BrainCircuit className="h-4 w-4" /> AI Executive Analyst
                </button>
                <button
                  onClick={() => setActiveTab("privacy")}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                    activeTab === "privacy" ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <Lock className="h-4 w-4" /> AI Privacy Boundary
                </button>
                <button
                  onClick={() => setActiveTab("exports")}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                    activeTab === "exports" ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <FileSpreadsheet className="h-4 w-4" /> PDF & PPTX Reports
                </button>
              </div>
            </div>

            <div className="mt-8">
              {activeTab === "kpi" && (
                <Card className="border-primary/20 shadow-lg">
                  <CardContent className="p-8">
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                      <div className="rounded-xl border bg-muted/40 p-5">
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>TOTAL REVENUE</span>
                          <Badge variant="outline" className="text-emerald-600 bg-emerald-500/10">+14.2% YoY</Badge>
                        </div>
                        <p className="mt-2 text-3xl font-extrabold">$2,849,120</p>
                        <p className="mt-1 text-xs text-muted-foreground">Derived strictly via SQL aggregations</p>
                      </div>
                      <div className="rounded-xl border bg-muted/40 p-5">
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>PROFIT MARGIN</span>
                          <Badge variant="outline" className="text-emerald-600 bg-emerald-500/10">34.8%</Badge>
                        </div>
                        <p className="mt-2 text-3xl font-extrabold">$991,493</p>
                        <p className="mt-1 text-xs text-muted-foreground">Exact Decimal math; zero float drift</p>
                      </div>
                      <div className="rounded-xl border bg-muted/40 p-5">
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>ANOMALIES DETECTED</span>
                          <Badge variant="destructive">Isolation Forest</Badge>
                        </div>
                        <p className="mt-2 text-3xl font-extrabold">3 Outliers</p>
                        <p className="mt-1 text-xs text-muted-foreground">Return rate spikes in West region</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {activeTab === "ai" && (
                <Card className="border-indigo-500/20 shadow-lg">
                  <CardContent className="p-8">
                    <div className="rounded-xl bg-muted/50 p-6 border">
                      <div className="flex items-center gap-2 text-sm font-semibold text-primary">
                        <Sparkles className="h-4 w-4" /> AI Executive Summary
                      </div>
                      <p className="mt-3 text-sm leading-relaxed text-foreground">
                        &quot;Revenue grew 14.2% quarter-over-quarter driven primarily by Corporate segment expansion in Technology categories. However, return rates in the West region increased by 4.1 percentage points, impacting net profitability.&quot;
                      </p>
                      <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> Grounded exclusively in verified computed numbers. No halluncinated metrics.
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {activeTab === "privacy" && (
                <Card className="border-emerald-500/20 shadow-lg">
                  <CardContent className="p-8">
                    <div className="space-y-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600">
                          <ShieldCheck className="h-6 w-6" />
                        </div>
                        <div>
                          <h4 className="font-semibold">Pydantic Privacy Payload Boundary</h4>
                          <p className="text-xs text-muted-foreground"><code>AIPayload</code> uses <code>extra=&quot;forbid&quot;</code> and contains only aggregate numbers.</p>
                        </div>
                      </div>
                      <div className="rounded-lg bg-zinc-950 p-4 text-xs font-mono text-emerald-400 overflow-x-auto">
                        <pre>{`{
  "period": { "start": "2024-01-01", "end": "2024-12-31" },
  "kpis": { "revenue": 2849120.00, "profit": 991493.00, "margin_pct": 34.8 },
  "top_region": "West",
  "anomalies_count": 3
  // STRICTLY EXCLUDED: Customer Names, Emails, Phone Numbers, Order UUIDs
}`}</pre>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {activeTab === "exports" && (
                <Card className="border-purple-500/20 shadow-lg">
                  <CardContent className="p-8">
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
                      <div>
                        <h4 className="font-semibold text-lg">Server-Side ReportLab & PPTX Generator</h4>
                        <p className="mt-1 text-sm text-muted-foreground">
                          Generate publication-quality vector PDFs or editable PowerPoint presentations instantly.
                        </p>
                      </div>
                      <div className="flex gap-3">
                        <Button variant="outline" className="gap-2">
                          <FileCheck className="h-4 w-4 text-red-500" /> Export PDF
                        </Button>
                        <Button variant="outline" className="gap-2">
                          <FileSpreadsheet className="h-4 w-4 text-amber-500" /> Export PPTX
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </section>

        {/* AI Boundary Section */}
        <section id="architecture" className="py-20">
          <div className="mx-auto max-w-7xl px-6">
            <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-2">
              <div>
                <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-600">
                  <ShieldCheck className="h-3.5 w-3.5" /> Core Guarantee
                </div>
                <h2 className="mt-4 text-3xl font-bold tracking-tight">The AI Never Calculates. <br />The AI Never Sees Raw Data.</h2>
                <p className="mt-4 text-muted-foreground">
                  Language models are notorious for math errors and PII leakage. InsightIQ solves this by cleanly separating deterministic computation from natural language narrative generation.
                </p>

                <ul className="mt-6 space-y-3">
                  <li className="flex items-start gap-3 text-sm">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500 shrink-0" />
                    <span><strong>SQL & Pandas Engine:</strong> Computes revenue, margins, customer LTV, and anomalies with 100% mathematical precision.</span>
                  </li>
                  <li className="flex items-start gap-3 text-sm">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500 shrink-0" />
                    <span><strong>Pydantic Strict Boundary:</strong> Aggregate numbers are serialized into an immutable payload model that strips out all names, emails, and transaction IDs.</span>
                  </li>
                  <li className="flex items-start gap-3 text-sm">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500 shrink-0" />
                    <span><strong>AI Narrative Layer:</strong> Writes executive summaries over exact aggregates using xAI Grok or the built-in offline analyst.</span>
                  </li>
                </ul>
              </div>

              <div className="rounded-2xl border bg-card p-6 shadow-xl">
                <div className="space-y-4">
                  <div className="flex items-center justify-between rounded-xl border bg-muted/30 p-4">
                    <div className="flex items-center gap-3">
                      <Database className="h-5 w-5 text-primary" />
                      <div>
                        <p className="text-sm font-semibold">1. Data Ingestion</p>
                        <p className="text-xs text-muted-foreground">Postgres / Pandas</p>
                      </div>
                    </div>
                    <Badge variant="outline">Row Level</Badge>
                  </div>

                  <div className="flex justify-center text-muted-foreground">↓</div>

                  <div className="flex items-center justify-between rounded-xl border bg-emerald-500/10 border-emerald-500/20 p-4">
                    <div className="flex items-center gap-3">
                      <Layers className="h-5 w-5 text-emerald-600" />
                      <div>
                        <p className="text-sm font-semibold text-emerald-950 dark:text-emerald-200">2. Deterministic Analytics Engine</p>
                        <p className="text-xs text-emerald-700 dark:text-emerald-400">scikit-learn Isolation Forest & RFM</p>
                      </div>
                    </div>
                    <Badge className="bg-emerald-600 text-white">Aggregates Only</Badge>
                  </div>

                  <div className="flex justify-center text-muted-foreground">↓</div>

                  <div className="flex items-center justify-between rounded-xl border bg-indigo-500/10 border-indigo-500/20 p-4">
                    <div className="flex items-center gap-3">
                      <BrainCircuit className="h-5 w-5 text-indigo-600" />
                      <div>
                        <p className="text-sm font-semibold text-indigo-950 dark:text-indigo-200">3. AI Provider Layer</p>
                        <p className="text-xs text-indigo-700 dark:text-indigo-400">GrokProvider / MockProvider</p>
                      </div>
                    </div>
                    <Badge variant="secondary">Zero PII Leak</Badge>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t bg-card py-12">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 px-6 sm:flex-row">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <BarChart3 className="h-4 w-4" />
            </div>
            <span className="font-bold tracking-tight">InsightIQ</span>
            <span className="text-xs text-muted-foreground">© {new Date().getFullYear()} All rights reserved.</span>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
            <Badge variant="outline">Next.js 15 App Router</Badge>
            <Badge variant="outline">FastAPI</Badge>
            <Badge variant="outline">SQLAlchemy Async</Badge>
            <Badge variant="outline">Tailwind CSS</Badge>
          </div>
        </div>
      </footer>
    </div>
  );
}
