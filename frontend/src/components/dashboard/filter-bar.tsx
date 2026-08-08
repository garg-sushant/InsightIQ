"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import type { AnalyticsFilters, ComparisonMode, FilterOptionsOut, Granularity } from "@/types/api";
import { RotateCcw } from "lucide-react";

interface FilterBarProps {
  filters: AnalyticsFilters;
  options: FilterOptionsOut | undefined;
  onChange: (next: AnalyticsFilters) => void;
  onReset: () => void;
}

function MultiValueChips({
  label,
  values,
  selected,
  onToggle,
}: {
  label: string;
  values: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  if (values.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <div className="flex flex-wrap gap-1.5">
        {values.map((value) => {
          const active = selected.includes(value);
          return (
            <button
              key={value}
              type="button"
              onClick={() => onToggle(value)}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                active ? "border-primary bg-primary text-primary-foreground" : "border-input bg-background text-muted-foreground hover:bg-accent"
              }`}
            >
              {value}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function FilterBar({ filters, options, onChange, onReset }: FilterBarProps) {
  function toggle(key: "regions" | "categories" | "sub_categories" | "segments", value: string) {
    const current = filters[key];
    const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
    onChange({ ...filters, [key]: next });
  }

  function applyPreset(type: "all" | "30d" | "90d" | "ytd") {
    if (type === "all") {
      onChange({ ...filters, date_from: null, date_to: null });
      return;
    }
    const maxDate = options?.date_max ? new Date(options.date_max) : new Date();
    const toStr = maxDate.toISOString().split("T")[0];
    let fromDate = new Date(maxDate);

    if (type === "30d") {
      fromDate.setDate(fromDate.getDate() - 30);
    } else if (type === "90d") {
      fromDate.setDate(fromDate.getDate() - 90);
    } else if (type === "ytd") {
      fromDate = new Date(maxDate.getFullYear(), 0, 1);
    }

    const fromStr = fromDate.toISOString().split("T")[0];
    onChange({ ...filters, date_from: fromStr, date_to: toStr });
  }

  return (
    <div className="space-y-4 rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2 border-b pb-3 text-xs">
        <span className="font-semibold text-muted-foreground">Quick Presets:</span>
        <button
          type="button"
          onClick={() => applyPreset("all")}
          className="rounded border bg-background px-2 py-1 font-medium hover:bg-accent hover:text-accent-foreground"
        >
          Full Range
        </button>
        <button
          type="button"
          onClick={() => applyPreset("30d")}
          className="rounded border bg-background px-2 py-1 font-medium hover:bg-accent hover:text-accent-foreground"
        >
          Last 30 Days
        </button>
        <button
          type="button"
          onClick={() => applyPreset("90d")}
          className="rounded border bg-background px-2 py-1 font-medium hover:bg-accent hover:text-accent-foreground"
        >
          Last 90 Days
        </button>
        <button
          type="button"
          onClick={() => applyPreset("ytd")}
          className="rounded border bg-background px-2 py-1 font-medium hover:bg-accent hover:text-accent-foreground"
        >
          Year to Date
        </button>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">From</Label>
          <Input
            type="date"
            className="w-40"
            value={filters.date_from ?? ""}
            min={options?.date_min ?? undefined}
            max={options?.date_max ?? undefined}
            onChange={(e) => onChange({ ...filters, date_from: e.target.value || null })}
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">To</Label>
          <Input
            type="date"
            className="w-40"
            value={filters.date_to ?? ""}
            min={options?.date_min ?? undefined}
            max={options?.date_max ?? undefined}
            onChange={(e) => onChange({ ...filters, date_to: e.target.value || null })}
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Granularity</Label>
          <Select value={filters.granularity} onValueChange={(v) => onChange({ ...filters, granularity: v as Granularity })}>
            <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="day">Day</SelectItem>
              <SelectItem value="week">Week</SelectItem>
              <SelectItem value="month">Month</SelectItem>
              <SelectItem value="quarter">Quarter</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Compare to</Label>
          <Select value={filters.comparison} onValueChange={(v) => onChange({ ...filters, comparison: v as ComparisonMode })}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="previous_period">Previous period</SelectItem>
              <SelectItem value="previous_year">Previous year</SelectItem>
              <SelectItem value="none">No comparison</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" size="sm" onClick={onReset} className="gap-1.5">
          <RotateCcw className="h-3.5 w-3.5" /> Reset
        </Button>
      </div>

      {options && (
        <div className="grid grid-cols-1 gap-4 border-t pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <MultiValueChips label="Region" values={options.regions} selected={filters.regions} onToggle={(v) => toggle("regions", v)} />
          <MultiValueChips label="Category" values={options.categories} selected={filters.categories} onToggle={(v) => toggle("categories", v)} />
          <MultiValueChips label="Sub-category" values={options.sub_categories} selected={filters.sub_categories} onToggle={(v) => toggle("sub_categories", v)} />
          <MultiValueChips label="Segment" values={options.segments} selected={filters.segments} onToggle={(v) => toggle("segments", v)} />
        </div>
      )}
    </div>
  );
}
