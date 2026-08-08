// Mirrors backend Pydantic schemas (app/schemas/*.py). Kept hand-in-sync
// deliberately rather than codegen'd, since the schema surface is stable and
// codegen would add a build step for little benefit at this scale.

export type Role = "owner" | "admin" | "analyst" | "viewer";

export type Permission =
  | "dataset:read" | "dataset:write" | "dataset:delete"
  | "analytics:read" | "analytics:run" | "ai:generate" | "report:export"
  | "member:read" | "member:invite" | "member:role_assign" | "member:remove"
  | "org:update" | "org:delete" | "audit:read";

export interface ErrorResponse {
  error: { code: string; message: string; details?: Record<string, unknown> | null; request_id?: string | null };
}

export interface PageMeta { total: number; limit: number; offset: number; has_more: boolean }
export interface Page<T> { items: T[]; meta: PageMeta }

// --- Auth --------------------------------------------------------------
export interface OrganizationOut {
  id: string; name: string; slug: string; industry: string | null; is_active: boolean; created_at: string;
}
export interface UserOut {
  id: string; email: string; full_name: string; role: Role; is_active: boolean;
  organization_id: string; last_login_at: string | null; created_at: string;
}
export interface TokenPair { access_token: string; refresh_token: string; token_type: string; expires_in: number }
export interface AuthResponse { tokens: TokenPair; user: UserOut; organization: OrganizationOut }
export interface CurrentUserOut { user: UserOut; organization: OrganizationOut; permissions: Permission[] }
export interface InviteUserResponse { user: UserOut; temporary_password: string }

// --- Datasets ------------------------------------------------------------
export type EntityType = "orders" | "customers" | "products" | "returns";
export type DatasetStatus = "pending" | "validating" | "ingested" | "partial" | "failed";

export interface RowError {
  row_number: number; column: string | null; error_type: string; message: string;
  severity: "row" | "critical" | "warning"; value: string | null;
}
export interface ColumnReport {
  name: string; present: boolean; required: boolean; inferred_type: string | null;
  null_count: number; error_count: number;
}
export interface ValidationReport {
  entity_type: EntityType; is_valid: boolean; rows_total: number; rows_accepted: number;
  rows_rejected: number; duplicate_keys_dropped: number; missing_required_columns: string[];
  unexpected_columns: string[]; columns: ColumnReport[]; errors: RowError[];
  error_counts: Record<string, number>; errors_truncated: boolean; warnings: string[];
  referential_issues: Record<string, number>;
}
export interface DatasetOut {
  id: string; organization_id: string; entity_type: EntityType; status: DatasetStatus;
  original_filename: string; file_size_bytes: number; rows_total: number; rows_accepted: number;
  rows_rejected: number; error_message: string | null; uploaded_by_user_id: string | null;
  created_at: string; completed_at: string | null; duration_ms: number | null;
}
export interface UploadResponse { dataset: DatasetOut; report: ValidationReport }
export interface EntitySchemaColumn {
  name: string; required: boolean; data_type: string; description: string; aliases: string[];
}
export interface EntitySchemaOut { entity_type: EntityType; columns: EntitySchemaColumn[]; primary_key: string[] }
export interface DataInventoryOut {
  orders: number; customers: number; products: number; returns: number;
  earliest_order_date: string | null; latest_order_date: string | null; has_data: boolean;
}

// --- Analytics -------------------------------------------------------------
export type Granularity = "day" | "week" | "month" | "quarter";
export type ComparisonMode = "previous_period" | "previous_year" | "none";

export interface AnalyticsFilters {
  date_from?: string | null; date_to?: string | null; regions: string[]; categories: string[];
  sub_categories: string[]; segments: string[]; granularity: Granularity; comparison: ComparisonMode; top_n: number;
}
export interface MetricValue { current: number; previous: number | null; delta_abs: number | null; delta_pct: number | null }
export interface KpiSet {
  revenue: MetricValue; profit: MetricValue; margin_pct: MetricValue; orders: MetricValue; aov: MetricValue;
  units: MetricValue; return_rate_pct: MetricValue; customers: MetricValue; new_customers: MetricValue;
  repeat_customers: MetricValue; repeat_rate_pct: MetricValue; avg_discount_pct: MetricValue;
}
export interface TimeSeriesPoint {
  period: string; revenue: number; profit: number; margin_pct: number; orders: number; units: number;
  revenue_ma: number | null; profit_ma: number | null; revenue_pop_pct: number | null;
}
export interface TimeSeries { granularity: Granularity; moving_average_window: number; points: TimeSeriesPoint[] }
export interface BreakdownItem {
  key: string; label: string; revenue: number; profit: number; margin_pct: number; orders: number; units: number;
  revenue_share_pct: number; previous_revenue: number | null; revenue_delta_pct: number | null;
}
export interface Breakdown { dimension: string; items: BreakdownItem[] }
export interface ProductPerformance {
  product_ref: string; name: string; category: string | null; sub_category: string | null;
  revenue: number; profit: number; margin_pct: number; units: number; orders: number;
}
export type AnomalySeverity = "low" | "medium" | "high";
export interface AnomalyPoint {
  period: string; metric: "revenue" | "margin_pct" | "profit"; value: number; expected: number;
  deviation_pct: number; z_score: number | null; severity: AnomalySeverity; direction: "spike" | "drop";
  method: "isolation_forest" | "zscore_rule"; description: string;
}
export interface AnomalyReport { granularity: Granularity; points_analysed: number; contamination: number; anomalies: AnomalyPoint[]; note: string | null }
export interface CustomerSegment {
  cluster_id: number; label: string; customer_count: number; customer_share_pct: number; revenue: number;
  revenue_share_pct: number; avg_recency_days: number; avg_frequency: number; avg_monetary: number; avg_rfm_score: number;
}
export interface RfmSummary { customers_scored: number; clusters: number; segments: CustomerSegment[]; note: string | null }
export type RiskLevel = "ok" | "watch" | "elevated" | "critical";
export interface RiskIndicator {
  key: string; label: string; level: RiskLevel; value: number; threshold: number;
  unit: "percent" | "ratio" | "count" | "currency"; description: string; evidence: Record<string, number>;
}
export interface BusinessHealth { score: number; grade: "A" | "B" | "C" | "D" | "F"; level: RiskLevel; indicators: RiskIndicator[]; headline: string }
export interface PeriodInfo {
  start: string; end: string; days: number; comparison_start: string | null; comparison_end: string | null; comparison_mode: ComparisonMode;
}
export interface ReturnsView {
  returned_orders: number; total_orders: number; return_rate_pct: number; revenue_at_risk: number;
  by_category: BreakdownItem[]; by_region: BreakdownItem[]; trend: TimeSeriesPoint[];
}
export interface AnalyticsResult {
  period: PeriodInfo; filters: AnalyticsFilters; row_count: number; kpis: KpiSet; timeseries: TimeSeries;
  breakdowns: Record<string, Breakdown>; top_products: ProductPerformance[]; bottom_products: ProductPerformance[];
  anomalies: AnomalyReport; rfm: RfmSummary; returns: ReturnsView; health: BusinessHealth; computed_at: string;
}
export interface AnalysisRunOut {
  id: string; organization_id: string; status: string; period_start: string; period_end: string;
  comparison_start: string | null; comparison_end: string | null; source_row_count: number;
  duration_ms: number | null; created_at: string; created_by_user_id: string | null; error_message: string | null;
}
export interface AnalysisRunDetailOut extends AnalysisRunOut { result: AnalyticsResult | null }
export interface FilterOptionsOut {
  regions: string[]; categories: string[]; sub_categories: string[]; segments: string[];
  date_min: string | null; date_max: string | null;
}

// --- AI --------------------------------------------------------------------
export interface InsightOut {
  id: string; analysis_run_id: string; insight_type: string; content: string;
  structured: Record<string, unknown> | null; provider: string; model: string; prompt_version: string;
  is_fallback: boolean; latency_ms: number | null; created_at: string;
}
export interface InsightBundle {
  analysis_run_id: string; provider: string; model: string; degraded: boolean; degraded_reason: string | null;
  executive_summary: InsightOut | null; root_cause: InsightOut | null; recommendations: InsightOut | null;
  risks: InsightOut | null; generated_at: string;
}
export interface AIStatusOut { provider: string; model: string; configured: boolean; is_mock: boolean; message: string }
export interface RecommendationItem {
  title: string; rationale: string; priority: "high" | "medium" | "low"; impact: "high" | "medium" | "low";
  effort: "high" | "medium" | "low"; owner: string | null; metric_to_watch: string | null;
}
export interface RootCauseItem {
  metric: string; movement: string; hypothesis: string; supporting_evidence: string[]; confidence: "high" | "medium" | "low";
}

// --- Reports -----------------------------------------------------------
export type ReportFormat = "pdf" | "pptx";
export interface ReportRequest {
  analysis_run_id: string; format: ReportFormat; title?: string | null;
  include_ai_narrative: boolean; include_charts: boolean;
}
