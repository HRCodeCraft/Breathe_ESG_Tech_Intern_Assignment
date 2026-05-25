import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getEmissions, approveRecord, flagRecord, bulkAction
} from '@/api/emissions'
import {
  formatCO2e, formatNumber, scopeColor, statusColor, flagColor,
  categoryIcon, sourceTypeLabel
} from '@/lib/utils'
import {
  CheckCircle2, Flag, Filter, Search, ChevronUp, ChevronDown,
  AlertTriangle, CheckSquare, Square, MoreHorizontal, X, SlidersHorizontal,
  ArrowUpDown
} from 'lucide-react'
import { format, parseISO } from 'date-fns'
import type { EmissionRecord, EmissionStatus } from '@/types'

const FLAG_LABELS: Record<string, string> = {
  outlier: 'Outlier',
  duplicate: 'Duplicate',
  missing_factor: 'No factor',
  unit_mismatch: 'Unit mismatch',
  zero_value: 'Zero value',
  incomplete: 'Incomplete',
  future_date: 'Future date',
}

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'flagged', label: 'Flagged' },
  { value: 'rejected', label: 'Rejected' },
]

const SCOPE_OPTIONS = [
  { value: '', label: 'All scopes' },
  { value: '1', label: 'Scope 1' },
  { value: '2', label: 'Scope 2' },
  { value: '3', label: 'Scope 3' },
]

function FlagBadge({ flag }: { flag: string }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs rounded-full px-2 py-0.5 font-medium ${flagColor(flag)}`}>
      <AlertTriangle className="h-2.5 w-2.5" />
      {FLAG_LABELS[flag] || flag}
    </span>
  )
}

function RecordRow({
  record,
  selected,
  onSelect,
  onApprove,
  onFlag,
}: {
  record: EmissionRecord
  selected: boolean
  onSelect: (id: string) => void
  onApprove: (id: string) => void
  onFlag: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <>
      <tr
        className={`emission-row border-b last:border-b-0 cursor-pointer ${
          selected ? 'bg-primary/5' : 'hover:bg-muted/40'
        } ${record.flags.length > 0 ? 'border-l-2 border-l-orange-300' : ''}`}
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => onSelect(record.id)}
            className="text-muted-foreground hover:text-primary"
          >
            {selected
              ? <CheckSquare className="h-4 w-4 text-primary" />
              : <Square className="h-4 w-4" />
            }
          </button>
        </td>
        <td className="px-3 py-3">
          <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${scopeColor(record.scope)}`}>
            S{record.scope}
          </span>
        </td>
        <td className="px-3 py-3 max-w-[180px]">
          <div className="flex items-center gap-1.5">
            <span className="text-base leading-none">{categoryIcon(record.category)}</span>
            <div className="min-w-0">
              <p className="text-xs font-medium truncate">{record.category_display}</p>
              <p className="text-xs text-muted-foreground truncate">{record.subcategory}</p>
            </div>
          </div>
        </td>
        <td className="px-3 py-3 text-xs text-muted-foreground whitespace-nowrap">
          {format(parseISO(record.activity_date), 'dd MMM yyyy')}
        </td>
        <td className="px-3 py-3 max-w-[140px]">
          <p className="text-xs truncate">{record.facility || record.supplier || '—'}</p>
        </td>
        <td className="px-3 py-3 text-right">
          <p className="text-sm font-semibold tabular-nums">{formatCO2e(record.co2e_kg)}</p>
          <p className="text-xs text-muted-foreground">{formatNumber(record.quantity_normalized)} {record.unit_normalized}</p>
        </td>
        <td className="px-3 py-3">
          <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${statusColor(record.status)}`}>
            {record.status_display}
          </span>
        </td>
        <td className="px-3 py-3">
          <div className="flex flex-wrap gap-1">
            {record.flags.slice(0, 2).map(f => <FlagBadge key={f} flag={f} />)}
            {record.flags.length > 2 && (
              <span className="text-xs text-muted-foreground">+{record.flags.length - 2}</span>
            )}
          </div>
        </td>
        <td className="px-3 py-3">
          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            {record.status !== 'approved' && (
              <button
                onClick={() => onApprove(record.id)}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-esg-100 hover:text-esg-700 transition-colors"
                title="Approve"
              >
                <CheckCircle2 className="h-4 w-4" />
              </button>
            )}
            {record.status !== 'flagged' && (
              <button
                onClick={() => onFlag(record.id)}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-red-100 hover:text-red-600 transition-colors"
                title="Flag for review"
              >
                <Flag className="h-4 w-4" />
              </button>
            )}
            <button className="rounded-md p-1.5 text-muted-foreground hover:bg-accent transition-colors">
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-muted/30">
          <td colSpan={9} className="px-6 py-3">
            <div className="grid grid-cols-3 gap-6 text-xs">
              <div className="space-y-2">
                <p className="font-semibold text-xs uppercase tracking-wide text-muted-foreground">Activity</p>
                <div className="space-y-1">
                  <p><span className="text-muted-foreground">Description:</span> {record.description || '—'}</p>
                  <p><span className="text-muted-foreground">Period:</span> {
                    record.period_start
                      ? `${format(parseISO(record.period_start), 'dd MMM')} – ${record.period_end ? format(parseISO(record.period_end), 'dd MMM yyyy') : '?'}`
                      : format(parseISO(record.activity_date), 'dd MMM yyyy')
                  }</p>
                  <p><span className="text-muted-foreground">Source:</span> {sourceTypeLabel(record.source_type || '')}</p>
                </div>
              </div>
              <div className="space-y-2">
                <p className="font-semibold text-xs uppercase tracking-wide text-muted-foreground">Emission Calc</p>
                <div className="space-y-1">
                  <p><span className="text-muted-foreground">Raw qty:</span> {formatNumber(record.quantity)} {record.unit}</p>
                  <p><span className="text-muted-foreground">Normalized:</span> {formatNumber(record.quantity_normalized)} {record.unit_normalized}</p>
                  <p><span className="text-muted-foreground">Factor:</span> {record.emission_factor ? `${record.emission_factor} kgCO₂e/${record.unit_normalized}` : '—'}</p>
                  <p><span className="text-muted-foreground">Source:</span> {record.emission_factor_source || '—'}</p>
                </div>
              </div>
              <div className="space-y-2">
                <p className="font-semibold text-xs uppercase tracking-wide text-muted-foreground">Gas Breakdown</p>
                <div className="space-y-1">
                  <p><span className="text-muted-foreground">CO₂:</span> {formatCO2e(record.co2_kg)}</p>
                  <p><span className="text-muted-foreground">CH₄:</span> {formatCO2e(record.ch4_kg)}</p>
                  <p><span className="text-muted-foreground">N₂O:</span> {formatCO2e(record.n2o_kg)}</p>
                  {record.is_edited && (
                    <p className="text-orange-600 font-medium">Edited by analyst</p>
                  )}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export function ReviewQueuePage() {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState({
    status: 'pending',
    scope: '',
    search: '',
    has_flags: false,
    ordering: '-activity_date',
    page: 1,
  })
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkNote, setBulkNote] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['emissions', filters],
    queryFn: () => getEmissions({
      status: filters.status || undefined,
      scope: filters.scope ? parseInt(filters.scope) : undefined,
      search: filters.search || undefined,
      has_flags: filters.has_flags || undefined,
      ordering: filters.ordering,
      page: filters.page,
    }),
    placeholderData: (prev) => prev,
  })

  const approveMutation = useMutation({
    mutationFn: (id: string) => approveRecord(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['emissions'] }),
  })

  const flagMutation = useMutation({
    mutationFn: (id: string) => flagRecord(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['emissions'] }),
  })

  const bulkMutation = useMutation({
    mutationFn: ({ action, notes }: { action: 'approve' | 'flag' | 'reject'; notes: string }) =>
      bulkAction(Array.from(selected), action, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emissions'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      setSelected(new Set())
      setBulkNote('')
    },
  })

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (!data?.results) return
    if (selected.size === data.results.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(data.results.map(r => r.id)))
    }
  }

  const records = data?.results || []
  const total = data?.count || 0
  const allSelected = records.length > 0 && selected.size === records.length

  return (
    <div className="flex h-full flex-col">
      {/* Header + filters */}
      <div className="border-b bg-card px-6 py-4 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">Review Queue</h1>
            <p className="text-sm text-muted-foreground">{total} records</p>
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
              showFilters ? 'border-primary bg-primary/5 text-primary' : 'hover:bg-accent'
            }`}
          >
            <SlidersHorizontal className="h-4 w-4" />
            Filters
          </button>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Status tabs */}
          <div className="flex rounded-lg border bg-background p-0.5 gap-0.5">
            {STATUS_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setFilters(f => ({ ...f, status: opt.value, page: 1 }))}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  filters.status === opt.value
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative flex-1 min-w-48 max-w-72">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search facility, supplier…"
              value={filters.search}
              onChange={e => setFilters(f => ({ ...f, search: e.target.value, page: 1 }))}
              className="w-full rounded-md border bg-background py-2 pl-8 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          {/* Flags toggle */}
          <button
            onClick={() => setFilters(f => ({ ...f, has_flags: !f.has_flags, page: 1 }))}
            className={`flex items-center gap-1.5 rounded-md border px-3 py-2 text-xs font-medium transition-colors ${
              filters.has_flags ? 'border-orange-300 bg-orange-50 text-orange-700' : 'hover:bg-accent text-muted-foreground'
            }`}
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            Flagged only
          </button>
        </div>

        {showFilters && (
          <div className="flex items-center gap-3 pt-1">
            <select
              value={filters.scope}
              onChange={e => setFilters(f => ({ ...f, scope: e.target.value, page: 1 }))}
              className="rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {SCOPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <select
              value={filters.ordering}
              onChange={e => setFilters(f => ({ ...f, ordering: e.target.value }))}
              className="rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="-activity_date">Date (newest)</option>
              <option value="activity_date">Date (oldest)</option>
              <option value="-co2e_kg">CO₂e (highest)</option>
              <option value="co2e_kg">CO₂e (lowest)</option>
            </select>
          </div>
        )}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 border-b bg-primary/5 px-6 py-2.5">
          <span className="text-sm font-medium text-primary">{selected.size} selected</span>
          <div className="flex items-center gap-2 ml-auto">
            <input
              type="text"
              placeholder="Optional note for audit log"
              value={bulkNote}
              onChange={e => setBulkNote(e.target.value)}
              className="rounded-md border bg-background px-3 py-1.5 text-sm w-56 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            <button
              onClick={() => bulkMutation.mutate({ action: 'approve', notes: bulkNote })}
              disabled={bulkMutation.isPending}
              className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Approve all
            </button>
            <button
              onClick={() => bulkMutation.mutate({ action: 'flag', notes: bulkNote })}
              disabled={bulkMutation.isPending}
              className="flex items-center gap-1.5 rounded-md border border-red-300 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
            >
              <Flag className="h-3.5 w-3.5" />
              Flag all
            </button>
            <button onClick={() => setSelected(new Set())} className="text-muted-foreground hover:text-foreground p-1">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-muted/80 backdrop-blur-sm border-b z-10">
            <tr>
              <th className="px-3 py-2.5 text-left">
                <button onClick={toggleAll}>
                  {allSelected
                    ? <CheckSquare className="h-4 w-4 text-primary" />
                    : <Square className="h-4 w-4 text-muted-foreground" />
                  }
                </button>
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Scope</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Category</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Date</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Facility / Supplier</th>
              <th className="px-3 py-2.5 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wide">CO₂e</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Status</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Flags</th>
              <th className="px-3 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              [...Array(8)].map((_, i) => (
                <tr key={i} className="border-b">
                  {[...Array(9)].map((_, j) => (
                    <td key={j} className="px-3 py-3">
                      <div className="h-4 rounded bg-muted animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))
            )}
            {!isLoading && records.length === 0 && (
              <tr>
                <td colSpan={9} className="py-20 text-center">
                  <CheckCircle2 className="h-8 w-8 text-esg-500 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">No records found for this filter</p>
                </td>
              </tr>
            )}
            {records.map(record => (
              <RecordRow
                key={record.id}
                record={record}
                selected={selected.has(record.id)}
                onSelect={toggleSelect}
                onApprove={approveMutation.mutate}
                onFlag={flagMutation.mutate}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="flex items-center justify-between border-t bg-card px-6 py-3">
          <p className="text-xs text-muted-foreground">
            Showing {Math.min((filters.page - 1) * 50 + 1, total)}–{Math.min(filters.page * 50, total)} of {total}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}
              disabled={filters.page === 1}
              className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}
              disabled={!data?.next}
              className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
