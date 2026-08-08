import { Badge } from "@/components/ui/badge";
import type { ValidationReport } from "@/types/api";
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

export function ValidationReportView({ report }: { report: ValidationReport }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        {report.is_valid ? (
          <CheckCircle2 className="h-5 w-5 text-success" />
        ) : (
          <XCircle className="h-5 w-5 text-destructive" />
        )}
        <span className="font-medium">{report.is_valid ? "Upload accepted" : "Upload rejected"}</span>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center text-sm">
        <div className="rounded-md bg-muted/50 p-3">
          <p className="text-2xl font-bold tabular-nums">{report.rows_total}</p>
          <p className="text-xs text-muted-foreground">Total rows</p>
        </div>
        <div className="rounded-md bg-success/10 p-3">
          <p className="text-2xl font-bold tabular-nums text-success">{report.rows_accepted}</p>
          <p className="text-xs text-muted-foreground">Accepted</p>
        </div>
        <div className="rounded-md bg-destructive/10 p-3">
          <p className="text-2xl font-bold tabular-nums text-destructive">{report.rows_rejected}</p>
          <p className="text-xs text-muted-foreground">Rejected</p>
        </div>
      </div>

      {report.missing_required_columns.length > 0 && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm">
          <p className="font-medium text-destructive">Missing required columns</p>
          <p className="mt-1 text-muted-foreground">{report.missing_required_columns.join(", ")}</p>
        </div>
      )}

      {report.warnings.length > 0 && (
        <div className="space-y-1.5">
          {report.warnings.map((warning, index) => (
            <div key={index} className="flex items-start gap-2 rounded-md bg-warning/10 p-2.5 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}

      {Object.keys(report.error_counts).length > 0 && (
        <div>
          <p className="mb-2 text-sm font-medium">Error breakdown</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(report.error_counts).map(([type, count]) => (
              <Badge key={type} variant="outline">
                {type.replace(/_/g, " ")}: {count}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {report.errors.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-medium">
            Row errors {report.errors_truncated && `(showing first ${report.errors.length})`}
          </p>
          <div className="max-h-64 overflow-y-auto rounded-md border">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-muted">
                <tr className="text-left">
                  <th className="p-2 font-medium">Row</th>
                  <th className="p-2 font-medium">Column</th>
                  <th className="p-2 font-medium">Error</th>
                  <th className="p-2 font-medium">Value</th>
                </tr>
              </thead>
              <tbody>
                {report.errors.map((error, index) => (
                  <tr key={index} className="border-t">
                    <td className="p-2 tabular-nums">{error.row_number}</td>
                    <td className="p-2">{error.column ?? "—"}</td>
                    <td className="p-2">{error.message}</td>
                    <td className="max-w-[140px] truncate p-2 text-muted-foreground">{error.value ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
