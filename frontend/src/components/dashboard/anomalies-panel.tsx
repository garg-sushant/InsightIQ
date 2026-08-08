import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { AnomalyReport, AnomalySeverity } from "@/types/api";
import { TrendingDown, TrendingUp } from "lucide-react";

const SEVERITY_VARIANT: Record<AnomalySeverity, "destructive" | "warning" | "secondary"> = {
  high: "destructive",
  medium: "warning",
  low: "secondary",
};

export function AnomaliesPanel({ anomalies }: { anomalies: AnomalyReport }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Detected anomalies</CardTitle>
      </CardHeader>
      <CardContent>
        {anomalies.anomalies.length === 0 ? (
          <div className="flex h-24 items-center justify-center text-sm text-muted-foreground">
            {anomalies.note ?? "No statistically significant anomalies in this range."}
          </div>
        ) : (
          <div className="space-y-3">
            {anomalies.anomalies.slice(0, 6).map((anomaly, index) => (
              <div key={`${anomaly.period}-${anomaly.metric}-${index}`} className="flex items-start gap-3 border-b pb-3 last:border-0 last:pb-0">
                {anomaly.direction === "spike" ? (
                  <TrendingUp className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                ) : (
                  <TrendingDown className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{anomaly.period}</span>
                    <Badge variant={SEVERITY_VARIANT[anomaly.severity]} className="text-[10px]">{anomaly.severity}</Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{anomaly.description}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
