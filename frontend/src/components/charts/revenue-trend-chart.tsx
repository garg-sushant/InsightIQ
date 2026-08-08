"use client";

import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCompactCurrency, formatDateShort } from "@/lib/utils";
import type { TimeSeries } from "@/types/api";

const COLORS = { revenue: "#2563eb", profit: "#059669", ma: "#64748b" };

export function RevenueTrendChart({ timeseries }: { timeseries: TimeSeries }) {
  const data = timeseries.points.map((p) => ({ ...p, label: formatDateShort(p.period) }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Revenue &amp; profit trend</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length < 2 ? (
          <div className="flex h-72 items-center justify-center text-sm text-muted-foreground">
            Not enough periods in range to draw a trend.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={288}>
            <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS.revenue} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={COLORS.revenue} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={(v) => formatCompactCurrency(v)} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} width={64} />
              <Tooltip
                formatter={(value: number, name: string) => [formatCompactCurrency(value), name]}
                contentStyle={{ borderRadius: 8, border: "1px solid hsl(var(--border))", fontSize: 12 }}
              />
              <Area type="monotone" dataKey="revenue" name="Revenue" stroke={COLORS.revenue} fill="url(#revenueFill)" strokeWidth={2} />
              <Line type="monotone" dataKey="profit" name="Profit" stroke={COLORS.profit} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="revenue_ma" name="Trend" stroke={COLORS.ma} strokeWidth={1.5} strokeDasharray="4 3" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
