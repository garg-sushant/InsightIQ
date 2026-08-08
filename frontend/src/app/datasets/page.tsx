"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { UploadDropzone } from "@/components/forms/upload-dropzone";
import { ValidationReportView } from "@/components/forms/validation-report-view";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { DatasetOut, DatasetStatus, EntityType, Page, UploadResponse } from "@/types/api";
import { Loader2, Download, FileSpreadsheet } from "lucide-react";
import { downloadSampleCsv, SAMPLE_CUSTOMERS_CSV, SAMPLE_ORDERS_CSV, SAMPLE_PRODUCTS_CSV, SAMPLE_RETURNS_CSV } from "@/lib/sample-data";

const ENTITY_TABS: { value: EntityType; label: string }[] = [
  { value: "orders", label: "Orders" },
  { value: "customers", label: "Customers" },
  { value: "products", label: "Products" },
  { value: "returns", label: "Returns" },
];

const STATUS_VARIANT: Record<DatasetStatus, "success" | "warning" | "destructive" | "secondary"> = {
  ingested: "success",
  partial: "warning",
  failed: "destructive",
  pending: "secondary",
  validating: "secondary",
};

function UploadPanel({ entityType }: { entityType: EntityType }) {
  const queryClient = useQueryClient();
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [lastResult, setLastResult] = useState<UploadResponse | null>(null);

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.upload<UploadResponse>(`/datasets/upload/${entityType}`, formData);
    },
    onSuccess: (response) => {
      setLastResult(response);
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
  });

  return (
    <div className="space-y-4">
      <UploadDropzone
        disabled={upload.isPending}
        onFileSelected={(file) => {
          setPendingFile(file);
          setLastResult(null);
          upload.mutate(file);
        }}
      />
      {upload.isPending && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Validating and importing {pendingFile?.name}…
        </div>
      )}
      {upload.isError && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {upload.error instanceof ApiError ? upload.error.message : "Upload failed."}
        </div>
      )}
      {lastResult && (
        <Card>
          <CardContent className="pt-6">
            <ValidationReportView report={lastResult.report} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function DatasetHistory() {
  const { data, isLoading } = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api.get<Page<DatasetOut>>("/datasets", { limit: 20 }),
  });

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (!data || data.items.length === 0) return <p className="text-sm text-muted-foreground">No uploads yet.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th className="pb-2 pr-2 font-medium">File</th>
            <th className="pb-2 pr-2 font-medium">Entity</th>
            <th className="pb-2 pr-2 font-medium">Status</th>
            <th className="pb-2 pr-2 text-right font-medium">Accepted</th>
            <th className="pb-2 pr-2 text-right font-medium">Rejected</th>
            <th className="pb-2 font-medium">Uploaded</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((dataset) => (
            <tr key={dataset.id} className="border-b last:border-0">
              <td className="max-w-[200px] truncate py-2 pr-2" title={dataset.original_filename}>{dataset.original_filename}</td>
              <td className="py-2 pr-2 capitalize">{dataset.entity_type}</td>
              <td className="py-2 pr-2">
                <Badge variant={STATUS_VARIANT[dataset.status]} className="capitalize">{dataset.status}</Badge>
              </td>
              <td className="py-2 pr-2 text-right tabular-nums">{dataset.rows_accepted}</td>
              <td className="py-2 pr-2 text-right tabular-nums">{dataset.rows_rejected}</td>
              <td className="py-2 text-muted-foreground">{formatDate(dataset.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}



export default function DatasetsPage() {
  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Datasets</h1>
        <p className="text-sm text-muted-foreground">
          Upload CSV or XLSX files for Orders, Customers, Products and Returns.
        </p>
      </div>

      <Card className="border-primary/20 bg-primary/5">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">Sample CSV Templates</CardTitle>
          </div>
          <CardDescription>
            Need test data? Download formatted sample CSV files to test ingestion and analytics validation.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button variant="outline" size="sm" className="gap-2 bg-card shadow-sm" onClick={() => downloadSampleCsv("orders_sample.csv", SAMPLE_ORDERS_CSV)}>
            <Download className="h-3.5 w-3.5" /> Orders.csv
          </Button>
          <Button variant="outline" size="sm" className="gap-2 bg-card shadow-sm" onClick={() => downloadSampleCsv("customers_sample.csv", SAMPLE_CUSTOMERS_CSV)}>
            <Download className="h-3.5 w-3.5" /> Customers.csv
          </Button>
          <Button variant="outline" size="sm" className="gap-2 bg-card shadow-sm" onClick={() => downloadSampleCsv("products_sample.csv", SAMPLE_PRODUCTS_CSV)}>
            <Download className="h-3.5 w-3.5" /> Products.csv
          </Button>
          <Button variant="outline" size="sm" className="gap-2 bg-card shadow-sm" onClick={() => downloadSampleCsv("returns_sample.csv", SAMPLE_RETURNS_CSV)}>
            <Download className="h-3.5 w-3.5" /> Returns.csv
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Upload a file</CardTitle>
          <CardDescription>
            Orders files with inline customer/product names automatically create the matching master records.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="orders">
            <TabsList>
              {ENTITY_TABS.map((tab) => (
                <TabsTrigger key={tab.value} value={tab.value}>{tab.label}</TabsTrigger>
              ))}
            </TabsList>
            {ENTITY_TABS.map((tab) => (
              <TabsContent key={tab.value} value={tab.value}>
                <UploadPanel entityType={tab.value} />
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Upload history</CardTitle>
        </CardHeader>
        <CardContent>
          <DatasetHistory />
        </CardContent>
      </Card>
    </div>
  );
}
