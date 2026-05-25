export interface Organization {
  id: string
  name: string
  slug: string
  industry: string
  reporting_year: number
}

export interface User {
  id: string
  username: string
  email: string
  first_name: string
  last_name: string
  role: 'admin' | 'analyst' | 'auditor'
  organization: Organization
}

export interface AuthTokens {
  access: string
  refresh: string
  user: User
}

export type EmissionScope = 1 | 2 | 3
export type EmissionStatus = 'pending' | 'approved' | 'flagged' | 'rejected'
export type EmissionCategory =
  | 'stationary_combustion'
  | 'mobile_combustion'
  | 'purchased_electricity'
  | 'business_travel_air'
  | 'business_travel_hotel'
  | 'business_travel_ground'
  | 'procurement'
  | 'waste'

export type EmissionFlag =
  | 'outlier'
  | 'duplicate'
  | 'missing_factor'
  | 'unit_mismatch'
  | 'future_date'
  | 'zero_value'
  | 'incomplete'

export interface EmissionRecord {
  id: string
  scope: EmissionScope
  scope_display: string
  category: EmissionCategory
  category_display: string
  subcategory: string
  activity_date: string
  period_start: string | null
  period_end: string | null
  facility: string
  cost_center: string
  supplier: string
  description: string
  quantity: string
  unit: string
  quantity_normalized: string
  unit_normalized: string
  emission_factor: string | null
  emission_factor_source: string
  emission_factor_unit: string
  co2e_kg: string | null
  co2e_tonnes: string | null
  co2_kg: string | null
  ch4_kg: string | null
  n2o_kg: string | null
  status: EmissionStatus
  status_display: string
  flags: EmissionFlag[]
  reviewed_by: string | null
  reviewed_by_name: string | null
  reviewed_at: string | null
  review_notes: string
  is_edited: boolean
  original_values: Record<string, string> | null
  ingestion_run: string | null
  source_type: string | null
  created_at: string
  updated_at: string
}

export type SourceType = 'sap_fuel' | 'sap_procurement' | 'utility_electricity' | 'travel'
export type RunStatus = 'pending' | 'processing' | 'completed' | 'completed_with_errors' | 'failed'

export interface IngestionRun {
  id: string
  source_type: SourceType
  source_type_display: string
  status: RunStatus
  status_display: string
  uploaded_by: string | null
  uploaded_by_name: string | null
  uploaded_at: string
  completed_at: string | null
  file_name: string
  row_count: number
  success_count: number
  error_count: number
  skipped_count: number
  error_log: Array<{ row: number; error_type: string; message: string }>
}

export interface DashboardSummary {
  scope_1_co2e_kg: string
  scope_2_co2e_kg: string
  scope_3_co2e_kg: string
  total_co2e_kg: string
  total_co2e_tonnes: string
  category_breakdown: Array<{ category: string; total: string }>
  status_counts: Record<EmissionStatus, number>
  flagged_count: number
  total_records: number
  approved_records: number
  pending_records: number
  monthly_trend: Array<{ month: string; scope: number; total: string }>
  recent_runs: IngestionRun[]
}

export interface AuditEvent {
  id: string
  action: string
  action_display: string
  timestamp: string
  user: string | null
  user_name: string
  emission_record_id: string | null
  ingestion_run_id: string | null
  before_state: Record<string, unknown> | null
  after_state: Record<string, unknown> | null
  metadata: Record<string, unknown>
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
