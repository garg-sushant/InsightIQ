import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn, formatDelta, isImproving } from "@/lib/utils";
import type { MetricValue } from "@/types/api";

interface KpiCardProps {
  label: string;
  metric: MetricValue;
  format: (value: number) => string;
  higherIsBetter?: boolean;
  usePoints?: boolean;
}

export function KpiCard({ label, metric, format, higherIsBetter = true, usePoints = false }: KpiCardProps) {
  const delta = usePoints ? metric.delta_abs : metric.delta_pct;
  const improving = isImproving(delta, higherIsBetter);

  return (
    <Card>
      <CardContent className="p-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="mt-2 text-2xl font-bold tabular-nums">{format(metric.current)}</p>
        <div className="mt-1.5 flex items-center gap-1 text-xs">
          {improving === null ? (
            <span className="flex items-center gap-1 text-muted-foreground">
              <Minus className="h-3 w-3" /> no comparison
            </span>
          ) : (
            <span className={cn("flex items-center gap-1 font-medium", improving ? "text-success" : "text-destructive")}>
              {improving ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
              {formatDelta(delta, usePoints)}
            </span>
          )}
          <span className="text-muted-foreground">vs comparison period</span>
        </div>
      </CardContent>
    </Card>
  );
}
