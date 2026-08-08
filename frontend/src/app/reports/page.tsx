"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { AnalysisRunOut, Page, ReportFormat } from "@/types/api";
import { FileDown, FileText, Loader2 } from "lucide-react";

export default function ReportsPage() {
  const [selectedRun, setSelectedRun] = useState<string>("");
  const [format, setFormat] = useState<ReportFormat>("pdf");
  const [title, setTitle] = useState("");
  const [includeAI, setIncludeAI] = useState(true);
  const [includeCharts, setIncludeCharts] = useState(true);

  const runs = useQuery({
    queryKey: ["analysis-runs"],
    queryFn: () => api.get<Page<AnalysisRunOut>>("/analytics/runs", { limit: 20 }),
  });

  const exportReport = useMutation({
    mutationFn: async () => {
      const blob = await api.download("/reports/export", {
        analysis_run_id: selectedRun,
        format,
        title: title || null,
        include_ai_narrative: includeAI,
        include_charts: includeCharts,
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `insightiq-report.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    },
  });

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Reports</h1>
        <p className="text-sm text-muted-foreground">Export an analysis run as an executive PDF or PowerPoint deck.</p>
      </div>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle className="text-base">Export a report</CardTitle>
          <CardDescription>Charts are rendered server-side; the AI narrative section is optional.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Analysis run</Label>
            <Select value={selectedRun} onValueChange={setSelectedRun}>
              <SelectTrigger><SelectValue placeholder="Select a computed analysis" /></SelectTrigger>
              <SelectContent>
                {runs.data?.items.map((run) => (
                  <SelectItem key={run.id} value={run.id}>
                    {run.period_start} → {run.period_end} ({formatDate(run.created_at)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {runs.data?.items.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No analysis runs yet. Visit the dashboard first to compute one.
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Format</Label>
            <Select value={format} onValueChange={(v) => setFormat(v as ReportFormat)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="pdf">PDF</SelectItem>
                <SelectItem value="pptx">PowerPoint</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Title (optional)</Label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Executive Business Review" />
          </div>

          <div className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={includeCharts} onChange={(e) => setIncludeCharts(e.target.checked)} className="h-4 w-4" />
            <span>Include charts</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={includeAI} onChange={(e) => setIncludeAI(e.target.checked)} className="h-4 w-4" />
            <span>Include AI narrative (if generated)</span>
          </div>

          <Button
            className="w-full gap-2"
            disabled={!selectedRun || exportReport.isPending}
            onClick={() => exportReport.mutate()}
          >
            {exportReport.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : format === "pdf" ? <FileText className="h-4 w-4" /> : <FileDown className="h-4 w-4" />}
            {exportReport.isPending ? "Generating…" : `Export ${format.toUpperCase()}`}
          </Button>

          {exportReport.isError && (
            <p className="text-sm text-destructive">
              {exportReport.error instanceof ApiError ? exportReport.error.message : "Export failed."}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
