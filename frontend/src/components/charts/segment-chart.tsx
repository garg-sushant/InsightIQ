"use client";

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RfmSummary } from "@/types/api";

const COLORS = ["#2563eb", "#0891b2", "#7c3aed", "#db2777", "#ea580c", "#65a30d"];

export function SegmentChart({ rfm }: { rfm: RfmSummary }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Customer segments (RFM)</CardTitle>
      </CardHeader>
      <CardContent>
        {rfm.segments.length === 0 ? (
          <div className="flex h-56 items-center justify-center text-sm text-muted-foreground">
            {rfm.note ?? "Not enough customers in range."}
          </div>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={rfm.segments}
                  dataKey="revenue_share_pct"
                  nameKey="label"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={2}
                >
                  {rfm.segments.map((entry, index) => (
                    <Cell key={entry.cluster_id} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
            {rfm.note && <p className="mt-2 text-xs text-muted-foreground">{rfm.note}</p>}
          </>
        )}
      </CardContent>
    </Card>
  );
}
