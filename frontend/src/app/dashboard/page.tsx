"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { FilterBar } from "@/components/dashboard/filter-bar";
import { RevenueTrendChart } from "@/components/charts/revenue-trend-chart";
import { BreakdownChart } from "@/components/charts/breakdown-chart";
import { SegmentChart } from "@/components/charts/segment-chart";
import { HealthPanel } from "@/components/dashboard/health-panel";
import { ProductTable } from "@/components/dashboard/product-table";
import { AnomaliesPanel } from "@/components/dashboard/anomalies-panel";
import { AIInsightsPanel } from "@/components/dashboard/ai-insights-panel";
import { api, ApiError } from "@/lib/api-client";
import { formatCompactCurrency, formatNumber, formatPercent } from "@/lib/utils";
import type { AnalysisRunDetailOut, AnalyticsFilters, DataInventoryOut, FilterOptionsOut } from "@/types/api";
import { Database, FileOutput, RefreshCw } from "lucide-react";

const DEFAULT_FILTERS: AnalyticsFilters = {
  date_from: null,
  date_to: null,
  regions: [],
  categories: [],
  sub_categories: [],
  segments: [],
  granularity: "month",
  comparison: "previous_period",
  top_n: 10,
};

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<AnalyticsFilters>(DEFAULT_FILTERS);

  const inventory = useQuery({
    queryKey: ["inventory"],
    queryFn: () => api.get<DataInventoryOut>("/datasets/inventory"),
  });

  const filterOptions = useQuery({
    queryKey: ["filter-options"],
    queryFn: () => api.get<FilterOptionsOut>("/analytics/filter-options"),
    enabled: Boolean(inventory.data?.has_data),
  });

  const analysis = useQuery({
    queryKey: ["analysis-run", filters],
    queryFn: () => api.post<AnalysisRunDetailOut>("/analytics/run", filters),
    enabled: Boolean(inventory.data?.has_data),
    retry: (count, err) => !(err instanceof ApiError && err.status === 422) && count < 1,
  });

  const result = analysis.data?.result;

  const kpiFormats = useMemo(
    () => ({
      currency: formatCompactCurrency,
      count: formatNumber,
      percent: (v: number) => formatPercent(v),
    }),
    [],
  );

  if (inventory.isLoading) {
    return (
      <div className="space-y-6 p-8">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }

  if (!inventory.data?.has_data) {
    return (
      <div className="flex min-h-[calc(100vh-2rem)] flex-col items-center justify-center gap-4 p-8 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
          <Database className="h-8 w-8 text-muted-foreground" />
        </div>
        <h2 className="text-xl font-semibold">No data yet</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          Upload your Orders, Customers, Products and Returns files to see your executive dashboard,
          computed KPIs, anomaly detection and AI-written insights.
        </p>
        <Button asChild>
          <Link href="/datasets">Upload data</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Executive dashboard</h1>
          <p className="text-sm text-muted-foreground">
            {inventory.data.orders.toLocaleString()} order lines
            {result && ` · ${result.period.start} to ${result.period.end}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button asChild variant="outline" size="sm" className="gap-1.5">
            <Link href="/reports">
              <FileOutput className="h-3.5 w-3.5" />
              Export Report
            </Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5"
            onClick={() => queryClient.invalidateQueries({ queryKey: ["analysis-run"] })}
            disabled={analysis.isFetching}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${analysis.isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      <FilterBar filters={filters} options={filterOptions.data} onChange={setFilters} onReset={() => setFilters(DEFAULT_FILTERS)} />

      {analysis.isLoading && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      )}

      {analysis.isError && (
        <div className="rounded-md bg-destructive/10 p-4 text-sm text-destructive">
          {analysis.error instanceof ApiError ? analysis.error.message : "Could not compute analytics for this range."}
        </div>
      )}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <KpiCard label="Revenue" metric={result.kpis.revenue} format={kpiFormats.currency} />
            <KpiCard label="Profit" metric={result.kpis.profit} format={kpiFormats.currency} />
            <KpiCard label="Margin" metric={result.kpis.margin_pct} format={kpiFormats.percent} usePoints />
            <KpiCard label="Orders" metric={result.kpis.orders} format={kpiFormats.count} />
            <KpiCard label="Avg order value" metric={result.kpis.aov} format={kpiFormats.currency} />
            <KpiCard label="Units sold" metric={result.kpis.units} format={kpiFormats.count} />
            <KpiCard label="Return rate" metric={result.kpis.return_rate_pct} format={kpiFormats.percent} higherIsBetter={false} usePoints />
            <KpiCard label="Repeat rate" metric={result.kpis.repeat_rate_pct} format={kpiFormats.percent} usePoints />
          </div>

          <AIInsightsPanel analysisRunId={analysis.data!.id} />

          <RevenueTrendChart timeseries={result.timeseries} />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <BreakdownChart title="Revenue by region" breakdown={result.breakdowns.region} />
            <BreakdownChart title="Revenue by category" breakdown={result.breakdowns.category} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <AnomaliesPanel anomalies={result.anomalies} />
            </div>
            <SegmentChart rfm={result.rfm} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ProductTable title="Most profitable products" products={result.top_products} />
            <ProductTable title="Least profitable products" products={result.bottom_products} />
          </div>

          <HealthPanel health={result.health} />
        </>
      )}
    </div>
  );
}
