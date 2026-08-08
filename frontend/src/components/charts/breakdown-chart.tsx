"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCompactCurrency } from "@/lib/utils";
import type { Breakdown } from "@/types/api";

const BAR_COLOR = "#2563eb";

export function BreakdownChart({ title, breakdown }: { title: string; breakdown: Breakdown | undefined }) {
  const items = (breakdown?.items ?? []).slice(0, 8);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="flex h-56 items-center justify-center text-sm text-muted-foreground">No data in range.</div>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(220, items.length * 34)}>
            <BarChart data={items} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
              <XAxis type="number" tickFormatter={(v) => formatCompactCurrency(v)} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="label" width={110} tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
              <Tooltip formatter={(value: number) => formatCompactCurrency(value)} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="revenue" name="Revenue" fill={BAR_COLOR} radius={[0, 4, 4, 0]} maxBarSize={22} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
