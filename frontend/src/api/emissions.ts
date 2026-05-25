import { api } from './client'
import type {
  EmissionRecord, IngestionRun, DashboardSummary, AuditEvent, PaginatedResponse
} from '@/types'

export interface EmissionFilters {
  scope?: number
  category?: string
  status?: string
  facility?: string
  supplier?: string
  activity_date_after?: string
  activity_date_before?: string
  ingestion_run?: string
  has_flags?: boolean
  search?: string
  ordering?: string
  page?: number
}

export async function getEmissions(filters: EmissionFilters = {}): Promise<PaginatedResponse<EmissionRecord>> {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== '' && v !== null)
  )
  const { data } = await api.get<PaginatedResponse<EmissionRecord>>('/emissions/', { params })
  return data
}

export async function getEmission(id: string): Promise<EmissionRecord> {
  const { data } = await api.get<EmissionRecord>(`/emissions/${id}/`)
  return data
}

export async function approveRecord(id: string, notes = ''): Promise<EmissionRecord> {
  const { data } = await api.post<EmissionRecord>(`/emissions/${id}/approve/`, { notes })
  return data
}

export async function flagRecord(id: string, notes = ''): Promise<EmissionRecord> {
  const { data } = await api.post<EmissionRecord>(`/emissions/${id}/flag/`, { notes })
  return data
}

export async function bulkAction(
  ids: string[],
  action: 'approve' | 'flag' | 'reject',
  notes = ''
): Promise<{ updated: number }> {
  const { data } = await api.post<{ updated: number }>('/emissions/bulk/', { ids, action, notes })
  return data
}

export async function updateRecord(id: string, payload: Partial<EmissionRecord>): Promise<EmissionRecord> {
  const { data } = await api.patch<EmissionRecord>(`/emissions/${id}/`, payload)
  return data
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await api.get<DashboardSummary>('/dashboard/summary/')
  return data
}

export async function uploadFile(file: File, sourceType: string): Promise<IngestionRun> {
  const form = new FormData()
  form.append('file', file)
  form.append('source_type', sourceType)
  const { data } = await api.post<IngestionRun>('/ingestion/upload/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getIngestionRuns(filters: { source_type?: string; status?: string } = {}): Promise<PaginatedResponse<IngestionRun>> {
  const { data } = await api.get<PaginatedResponse<IngestionRun>>('/ingestion/', { params: filters })
  return data
}

export async function getIngestionRun(id: string): Promise<IngestionRun> {
  const { data } = await api.get<IngestionRun>(`/ingestion/${id}/`)
  return data
}

export async function getAuditLog(filters: {
  emission_record?: string
  ingestion_run?: string
  page?: number
} = {}): Promise<PaginatedResponse<AuditEvent>> {
  const { data } = await api.get<PaginatedResponse<AuditEvent>>('/audit/', { params: filters })
  return data
}
