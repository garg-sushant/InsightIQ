"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { MarkdownLite } from "@/components/dashboard/markdown-lite";
import { api, ApiError } from "@/lib/api-client";
import type { InsightBundle } from "@/types/api";
import { Sparkles, RefreshCw, AlertCircle } from "lucide-react";

export function AIInsightsPanel({ analysisRunId }: { analysisRunId: string }) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["ai-insights", analysisRunId],
    queryFn: async () => {
      try {
        return await api.get<InsightBundle>(`/ai/insights/${analysisRunId}`);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
  });

  const generate = useMutation({
    mutationFn: (refresh: boolean) => api.post<InsightBundle>("/ai/generate", { analysis_run_id: analysisRunId, refresh }),
    onSuccess: (bundle) => {
      queryClient.setQueryData(["ai-insights", analysisRunId], bundle);
    },
  });

  const bundle = data ?? generate.data;

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-primary/[0.03] to-transparent">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <CardTitle className="text-base">AI-generated narrative</CardTitle>
          {bundle?.degraded && (
            <Badge variant="secondary" className="gap-1 text-[10px]">
              <AlertCircle className="h-3 w-3" /> Offline analyst
            </Badge>
          )}
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => generate.mutate(Boolean(bundle))}
          disabled={generate.isPending}
          className="gap-1.5"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${generate.isPending ? "animate-spin" : ""}`} />
          {bundle ? "Regenerate" : "Generate insights"}
        </Button>
      </CardHeader>
      <CardContent>
        {bundle?.degraded_reason && (
          <p className="mb-3 rounded-md bg-muted/70 px-3 py-2 text-xs text-muted-foreground">{bundle.degraded_reason}</p>
        )}

        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
          </div>
        ) : !bundle ? (
          <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
            <Sparkles className="h-8 w-8 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">
              Generate an executive summary, root-cause analysis, and recommendations from this period&apos;s
              computed metrics.
            </p>
            <Button onClick={() => generate.mutate(false)} disabled={generate.isPending} className="gap-1.5">
              <Sparkles className="h-4 w-4" />
              {generate.isPending ? "Generating…" : "Generate insights"}
            </Button>
            {generate.isError && (
              <p className="text-xs text-destructive">
                {generate.error instanceof ApiError ? generate.error.message : "Could not generate insights."}
              </p>
            )}
          </div>
        ) : (
          <Tabs defaultValue="summary">
            <TabsList>
              <TabsTrigger value="summary">Summary</TabsTrigger>
              <TabsTrigger value="root-cause">Root cause</TabsTrigger>
              <TabsTrigger value="recommendations">Recommendations</TabsTrigger>
              <TabsTrigger value="risks">Risks</TabsTrigger>
            </TabsList>
            <TabsContent value="summary">
              {bundle.executive_summary ? <MarkdownLite content={bundle.executive_summary.content} /> : <EmptySection />}
            </TabsContent>
            <TabsContent value="root-cause">
              {bundle.root_cause ? <MarkdownLite content={bundle.root_cause.content} /> : <EmptySection />}
            </TabsContent>
            <TabsContent value="recommendations">
              {bundle.recommendations ? <MarkdownLite content={bundle.recommendations.content} /> : <EmptySection />}
            </TabsContent>
            <TabsContent value="risks">
              {bundle.risks ? <MarkdownLite content={bundle.risks.content} /> : <EmptySection />}
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}

function EmptySection() {
  return <p className="py-6 text-center text-sm text-muted-foreground">This section is not available yet.</p>;
}
