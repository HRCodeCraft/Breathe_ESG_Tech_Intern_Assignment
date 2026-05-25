import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getIngestionRuns, uploadFile } from '@/api/emissions'
import { formatNumber, runStatusColor, sourceTypeLabel } from '@/lib/utils'
import {
  Upload, FileText, CheckCircle2, XCircle, AlertTriangle,
  ChevronDown, ChevronUp, Info
} from 'lucide-react'
import { format, parseISO } from 'date-fns'
import type { SourceType } from '@/types'

const SOURCE_TYPES: Array<{
  value: SourceType
  label: string
  description: string
  format: string
  example: string
}> = [
  {
    value: 'sap_fuel',
    label: 'SAP Fuel & Combustion',
    description: 'Scope 1 — stationary and mobile combustion from SAP MIGO/SE16N exports',
    format: 'CSV (SAP SE16N / ME2M report)',
    example: 'WERKS, MATNR, MENGE, MEINS, BLDAT, BWART',
  },
  {
    value: 'sap_procurement',
    label: 'SAP Procurement',
    description: 'Scope 3 Cat. 1 — purchased goods from SAP ME2M purchase order export',
    format: 'CSV (SAP ME2M report)',
    example: 'WERKS, LIFNR, MATNR, TXZ01, MENGE, MEINS, BEDAT',
  },
  {
    value: 'utility_electricity',
    label: 'Utility Electricity',
    description: 'Scope 2 — grid electricity from Green Button CSV or portal export',
    format: 'Green Button CSV or portal variant',
    example: 'TYPE, DATE, USAGE, UNITS, COST',
  },
  {
    value: 'travel',
    label: 'Corporate Travel',
    description: 'Scope 3 Cat. 6 — flights, hotels, ground transport from Concur/Navan',
    format: 'SAP Concur Trip Detail Export CSV',
    example: 'Employee ID, Booking Type, Origin, Destination, Class of Service',
  },
]

function DropZone({
  sourceType,
  onUpload,
  uploading,
}: {
  sourceType: SourceType | null
  onUpload: (file: File, type: SourceType) => void
  uploading: boolean
}) {
  const [selected, setSelected] = useState<SourceType | null>(sourceType)

  const onDrop = useCallback((files: File[]) => {
    if (files[0] && selected) {
      onUpload(files[0], selected)
    }
  }, [selected, onUpload])

  const { getRootProps, getInputProps, isDragActive, acceptedFiles } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.txt', '.csv'] },
    maxFiles: 1,
    disabled: !selected || uploading,
  })

  return (
    <div className="space-y-4">
      {/* Source type selector */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {SOURCE_TYPES.map(st => (
          <button
            key={st.value}
            onClick={() => setSelected(st.value)}
            className={`rounded-xl border p-4 text-left transition-all ${
              selected === st.value
                ? 'border-primary bg-primary/5 ring-1 ring-primary'
                : 'border-border hover:border-primary/40 hover:bg-accent'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold">{st.label}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{st.description}</p>
              </div>
              {selected === st.value && (
                <CheckCircle2 className="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
              )}
            </div>
            <div className="mt-2 rounded-md bg-muted px-2 py-1">
              <p className="text-xs font-mono text-muted-foreground">{st.example}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`rounded-xl border-2 border-dashed p-10 text-center transition-all cursor-pointer ${
          !selected || uploading
            ? 'border-border opacity-50 cursor-not-allowed'
            : isDragActive
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-primary/50 hover:bg-accent'
        }`}
      >
        <input {...getInputProps()} />
        <Upload className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
        {uploading ? (
          <>
            <p className="text-sm font-medium">Processing file…</p>
            <p className="text-xs text-muted-foreground mt-1">Parsing, normalizing, detecting duplicates</p>
            <div className="mt-4 h-1.5 rounded-full bg-muted overflow-hidden mx-auto max-w-xs">
              <div className="h-full w-1/2 bg-primary rounded-full animate-pulse" />
            </div>
          </>
        ) : !selected ? (
          <p className="text-sm text-muted-foreground">Select a source type above first</p>
        ) : isDragActive ? (
          <p className="text-sm font-medium text-primary">Drop it here</p>
        ) : acceptedFiles[0] ? (
          <p className="text-sm font-medium">{acceptedFiles[0].name}</p>
        ) : (
          <>
            <p className="text-sm font-medium">
              Drop your CSV here, or <span className="text-primary">click to browse</span>
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {SOURCE_TYPES.find(s => s.value === selected)?.format}
            </p>
          </>
        )}
      </div>

      {selected && (
        <div className="flex items-start gap-2 rounded-lg bg-muted p-3">
          <Info className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
          <p className="text-xs text-muted-foreground">
            Download a{' '}
            <a href={`/api/sample/${selected}/`} className="text-primary hover:underline">
              sample file
            </a>{' '}
            to see the expected format. Headers are flexible — the parser handles German/English SAP columns,
            date format variants, and unit aliases automatically.
          </p>
        </div>
      )}
    </div>
  )
}

function RunRow({ run }: { run: import('@/types').IngestionRun }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="flex items-center gap-4 px-4 py-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium">{sourceTypeLabel(run.source_type)}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${runStatusColor(run.status)}`}>
              {run.status_display}
            </span>
            {run.error_count > 0 && (
              <span className="text-xs text-red-600 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                {run.error_count} errors
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
            <FileText className="h-3 w-3" />
            <span className="truncate">{run.file_name}</span>
            <span>·</span>
            <span>{format(parseISO(run.uploaded_at), 'dd MMM yyyy HH:mm')}</span>
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground flex-shrink-0">
          <div className="text-right">
            <p className="text-esg-700 font-semibold">{formatNumber(run.success_count, 0)} created</p>
            <p>{formatNumber(run.row_count, 0)} rows total</p>
          </div>
          {run.error_count > 0 && (
            <button onClick={() => setExpanded(!expanded)} className="text-muted-foreground hover:text-foreground">
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      {expanded && run.error_log.length > 0 && (
        <div className="border-t bg-red-50/50 p-4 space-y-2">
          <p className="text-xs font-semibold text-red-700">Parse errors:</p>
          <div className="max-h-48 overflow-y-auto space-y-1">
            {run.error_log.map((err, i) => (
              <div key={i} className="rounded-md bg-red-100/60 px-3 py-2 text-xs">
                <span className="font-medium text-red-700">Row {err.row}:</span>{' '}
                <span className="text-red-800">{err.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function IngestionPage() {
  const queryClient = useQueryClient()
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  const { data: runs, isLoading } = useQuery({
    queryKey: ['ingestion-runs'],
    queryFn: () => getIngestionRuns(),
  })

  const mutation = useMutation({
    mutationFn: ({ file, type }: { file: File; type: SourceType }) => uploadFile(file, type),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ['ingestion-runs'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['emissions'] })
      setSuccessMsg(
        `${run.success_count} records created from "${run.file_name}".` +
        (run.error_count > 0 ? ` ${run.error_count} rows had errors.` : '')
      )
      setErrorMsg('')
    },
    onError: () => {
      setErrorMsg('Upload failed. Check that the file is a valid CSV for the selected source.')
      setSuccessMsg('')
    },
  })

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-xl font-semibold">Data Ingestion</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Upload CSV exports from SAP, utility portals, or corporate travel platforms.
          The pipeline parses, normalizes units, applies emission factors, and flags anomalies automatically.
        </p>
      </div>

      {successMsg && (
        <div className="flex items-start gap-3 rounded-xl border border-esg-200 bg-esg-50 px-4 py-3">
          <CheckCircle2 className="h-5 w-5 text-esg-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-esg-800">Upload successful</p>
            <p className="text-sm text-esg-700">{successMsg}</p>
          </div>
          <button onClick={() => setSuccessMsg('')} className="ml-auto text-esg-500 hover:text-esg-700">×</button>
        </div>
      )}

      {errorMsg && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
          <XCircle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-800">Upload failed</p>
            <p className="text-sm text-red-700">{errorMsg}</p>
          </div>
          <button onClick={() => setErrorMsg('')} className="ml-auto text-red-400 hover:text-red-600">×</button>
        </div>
      )}

      <div className="rounded-xl border bg-card p-6">
        <h2 className="text-sm font-semibold mb-5">Upload New File</h2>
        <DropZone
          sourceType={null}
          onUpload={(file, type) => mutation.mutate({ file, type })}
          uploading={mutation.isPending}
        />
      </div>

      {/* History */}
      <div>
        <h2 className="text-sm font-semibold mb-3">Ingestion History</h2>
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded-xl border h-16 animate-pulse bg-card" />
            ))}
          </div>
        ) : runs?.results?.length === 0 ? (
          <div className="rounded-xl border bg-card p-10 text-center">
            <Upload className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No ingestion runs yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {runs?.results?.map(run => <RunRow key={run.id} run={run} />)}
          </div>
        )}
      </div>
    </div>
  )
}
