import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { BusinessHealth, RiskLevel } from "@/types/api";
import { AlertTriangle, CheckCircle2, TrendingDown } from "lucide-react";

const LEVEL_STYLES: Record<RiskLevel, { badge: "success" | "warning" | "destructive" | "secondary"; label: string }> = {
  ok: { badge: "success", label: "OK" },
  watch: { badge: "secondary", label: "Watch" },
  elevated: { badge: "warning", label: "Elevated" },
  critical: { badge: "destructive", label: "Critical" },
};

const GRADE_COLOR: Record<string, string> = {
  A: "text-success", B: "text-success", C: "text-warning", D: "text-warning", F: "text-destructive",
};

export function HealthPanel({ health }: { health: BusinessHealth }) {
  const flagged = health.indicators.filter((i) => i.level !== "ok");

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Business health</CardTitle>
        <div className="flex items-center gap-2">
          <span className={cn("text-3xl font-bold tabular-nums", GRADE_COLOR[health.grade])}>{health.grade}</span>
          <span className="text-sm text-muted-foreground">{health.score}/100</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-start gap-2 rounded-md bg-muted/50 p-3 text-sm">
          {flagged.length === 0 ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
          ) : (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          )}
          <span>{health.headline}</span>
        </div>

        <div className="space-y-2.5">
          {health.indicators.map((indicator) => {
            const style = LEVEL_STYLES[indicator.level];
            return (
              <div key={indicator.key} className="flex items-start justify-between gap-3 border-b pb-2.5 last:border-0 last:pb-0">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{indicator.label}</span>
                    <Badge variant={style.badge} className="text-[10px]">{style.label}</Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{indicator.description}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1 text-sm font-semibold tabular-nums">
                  {indicator.level !== "ok" && <TrendingDown className="h-3.5 w-3.5 text-muted-foreground" />}
                  {indicator.value.toFixed(1)}
                  {indicator.unit === "percent" ? "%" : ""}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
