import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAuditLog } from '@/api/emissions'
import { format, parseISO } from 'date-fns'
import { ScrollText, User, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'

const ACTION_COLOR: Record<string, string> = {
  record_approved:   'text-esg-700 bg-esg-50 border-esg-200',
  record_flagged:    'text-red-700 bg-red-50 border-red-200',
  record_rejected:   'text-gray-600 bg-gray-100 border-gray-200',
  record_edited:     'text-blue-700 bg-blue-50 border-blue-200',
  record_created:    'text-purple-700 bg-purple-50 border-purple-200',
  bulk_approved:     'text-esg-700 bg-esg-50 border-esg-200',
  bulk_flagged:      'text-red-700 bg-red-50 border-red-200',
  run_started:       'text-blue-700 bg-blue-50 border-blue-200',
  run_completed:     'text-esg-700 bg-esg-50 border-esg-200',
  run_failed:        'text-red-700 bg-red-50 border-red-200',
}

function EventRow({ event }: { event: import('@/types').AuditEvent }) {
  const [showDiff, setShowDiff] = useState(false)
  const hasDiff = event.before_state || event.after_state

  return (
    <div className="flex gap-4 py-4 border-b last:border-b-0">
      {/* Timeline dot */}
      <div className="flex flex-col items-center pt-1">
        <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
          <User className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
        <div className="flex-1 w-px bg-border mt-2" />
      </div>

      <div className="flex-1 min-w-0 pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs font-medium rounded-full border px-2 py-0.5 ${ACTION_COLOR[event.action] || 'text-gray-600 bg-gray-100 border-gray-200'}`}>
              {event.action_display}
            </span>
            <span className="text-sm font-medium">{event.user_name}</span>
            {event.metadata?.count != null && (
              <span className="text-xs text-muted-foreground">({String(event.metadata.count)} records)</span>
            )}
          </div>
          <span className="text-xs text-muted-foreground whitespace-nowrap flex-shrink-0">
            {format(parseISO(event.timestamp), 'dd MMM yyyy HH:mm:ss')}
          </span>
        </div>

        {event.metadata?.file_name != null && (
          <p className="text-xs text-muted-foreground mt-1">
            File: {String(event.metadata.file_name)}
          </p>
        )}
        {event.metadata?.notes != null && (
          <p className="text-xs text-muted-foreground mt-1 italic">
            Note: &ldquo;{String(event.metadata.notes)}&rdquo;
          </p>
        )}

        {hasDiff && (
          <button
            onClick={() => setShowDiff(!showDiff)}
            className="flex items-center gap-1 mt-2 text-xs text-primary hover:underline"
          >
            {showDiff ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {showDiff ? 'Hide' : 'Show'} state diff
          </button>
        )}

        {showDiff && hasDiff && (
          <div className="mt-2 grid grid-cols-2 gap-2">
            {event.before_state && (
              <div className="rounded-lg bg-red-50 border border-red-200 p-3">
                <p className="text-xs font-semibold text-red-700 mb-1.5">Before</p>
                <pre className="text-xs text-red-800 overflow-auto max-h-32 whitespace-pre-wrap">
                  {JSON.stringify(event.before_state, null, 2)}
                </pre>
              </div>
            )}
            {event.after_state && (
              <div className="rounded-lg bg-esg-50 border border-esg-200 p-3">
                <p className="text-xs font-semibold text-esg-700 mb-1.5">After</p>
                <pre className="text-xs text-esg-800 overflow-auto max-h-32 whitespace-pre-wrap">
                  {JSON.stringify(event.after_state, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function AuditLogPage() {
  const [page, setPage] = useState(1)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['audit', page],
    queryFn: () => getAuditLog({ page }),
  })

  const events = data?.results || []
  const total = data?.count || 0

  return (
    <div className="p-6 space-y-4 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Audit Log</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Immutable record of all analyst actions and ingestion events
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-accent transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      <div className="rounded-xl border bg-card px-6">
        {isLoading && (
          <div className="space-y-4 py-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="flex gap-4">
                <div className="h-7 w-7 rounded-full bg-muted animate-pulse flex-shrink-0" />
                <div className="flex-1 space-y-2 pt-1">
                  <div className="h-4 bg-muted rounded animate-pulse w-64" />
                  <div className="h-3 bg-muted rounded animate-pulse w-40" />
                </div>
              </div>
            ))}
          </div>
        )}

        {!isLoading && events.length === 0 && (
          <div className="py-16 text-center">
            <ScrollText className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No audit events yet</p>
          </div>
        )}

        {events.map(event => <EventRow key={event.id} event={event} />)}
      </div>

      {total > 50 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">{total} total events</p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => p - 1)}
              disabled={page === 1}
              className="rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(p => p + 1)}
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
