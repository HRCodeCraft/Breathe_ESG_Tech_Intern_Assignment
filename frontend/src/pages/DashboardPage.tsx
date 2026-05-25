import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { getDashboardSummary } from '@/api/emissions'
import { formatCO2e, formatNumber, scopeColorDot, categoryIcon, runStatusColor, sourceTypeLabel } from '@/lib/utils'
import { TrendingDown, Clock, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { useNavigate } from 'react-router-dom'

const SCOPE_COLORS = ['#f97316', '#3b82f6', '#a855f7']
const CATEGORY_COLORS = ['#22c55e', '#16a34a', '#15803d', '#166534', '#14532d', '#f97316', '#3b82f6', '#a855f7']

function StatCard({
  label, value, sub, icon: Icon, color
}: { label: string; value: string; sub?: string; icon: React.ElementType; color: string }) {
  return (
    <div className="rounded-xl border bg-card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground font-medium">{label}</p>
        <div className={`rounded-lg p-2 ${color}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <div>
        <p className="text-2xl font-bold leading-tight">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboardSummary,
  })
  const navigate = useNavigate()

  if (isLoading || !data) {
    return (
      <div className="p-6 space-y-4">
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-xl border bg-card h-28 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  const scopePieData = [
    { name: 'Scope 1', value: parseFloat(data.scope_totals?.scope_1_co2e_kg || '0') },
    { name: 'Scope 2', value: parseFloat(data.scope_totals?.scope_2_co2e_kg || '0') },
    { name: 'Scope 3', value: parseFloat(data.scope_totals?.scope_3_co2e_kg || '0') },
  ].filter(d => d.value > 0)

  const categoryData = data.category_breakdown
    ?.slice(0, 6)
    .map(c => ({
      name: c.category.replace(/_/g, ' ').replace('business travel ', ''),
      value: parseFloat(c.total || '0'),
    })) || []

  const trendData = (() => {
    const byMonth: Record<string, Record<string, number>> = {}
    for (const item of data.monthly_trend || []) {
      const month = format(parseISO(item.month), 'MMM')
      if (!byMonth[month]) byMonth[month] = {}
      byMonth[month][`scope${item.scope}`] = parseFloat(item.total || '0') / 1000
    }
    return Object.entries(byMonth).map(([month, scopes]) => ({ month, ...scopes }))
  })()

  const pendingCount = data.status_counts?.pending || 0
  const totalTonnes = parseFloat(data.total_co2e_tonnes || '0')

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {data.approved_records} approved records · {data.total_records} total
        </p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total CO₂e (approved)"
          value={totalTonnes >= 1000 ? `${(totalTonnes / 1000).toFixed(1)} ktCO₂e` : `${totalTonnes.toFixed(1)} tCO₂e`}
          sub="Scopes 1, 2 & 3 combined"
          icon={TrendingDown}
          color="bg-esg-100 text-esg-700"
        />
        <StatCard
          label="Pending Review"
          value={formatNumber(pendingCount, 0)}
          sub={`${data.flagged_count} flagged records`}
          icon={Clock}
          color="bg-yellow-100 text-yellow-700"
        />
        <StatCard
          label="Approved Records"
          value={formatNumber(data.approved_records, 0)}
          sub={`${Math.round((data.approved_records / Math.max(data.total_records, 1)) * 100)}% of total`}
          icon={CheckCircle2}
          color="bg-esg-100 text-esg-700"
        />
        <StatCard
          label="Flagged / Issues"
          value={formatNumber(data.flagged_count, 0)}
          sub="Needs analyst attention"
          icon={AlertTriangle}
          color="bg-red-100 text-red-600"
        />
      </div>

      {/* Scope breakdown + category bar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Scope pie */}
        <div className="rounded-xl border bg-card p-5">
          <h2 className="text-sm font-semibold mb-4">Scope Breakdown</h2>
          {scopePieData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={scopePieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    dataKey="value"
                    paddingAngle={3}
                  >
                    {scopePieData.map((_, i) => (
                      <Cell key={i} fill={SCOPE_COLORS[i]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatCO2e(v)} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-2">
                {[1, 2, 3].map((s, i) => {
                  const kg = parseFloat((data.scope_totals as Record<string, string>)[`scope_${s}_co2e_kg`] || '0')
                  return (
                    <div key={s} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <div className={`h-2.5 w-2.5 rounded-full`} style={{ background: SCOPE_COLORS[i] }} />
                        <span className="text-muted-foreground">Scope {s}</span>
                      </div>
                      <span className="font-medium tabular-nums">{formatCO2e(kg)}</span>
                    </div>
                  )
                })}
              </div>
            </>
          ) : (
            <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
              No approved records yet
            </div>
          )}
        </div>

        {/* Category bar */}
        <div className="rounded-xl border bg-card p-5 lg:col-span-2">
          <h2 className="text-sm font-semibold mb-4">By Category</h2>
          {categoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={categoryData} layout="vertical" margin={{ left: 0, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} className="stroke-border" />
                <XAxis
                  type="number"
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}t`}
                  tick={{ fontSize: 11 }}
                  className="text-muted-foreground"
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={110}
                  tick={{ fontSize: 11 }}
                  className="text-muted-foreground capitalize"
                />
                <Tooltip formatter={(v: number) => formatCO2e(v)} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {categoryData.map((_, i) => (
                    <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
              No approved records yet
            </div>
          )}
        </div>
      </div>

      {/* Monthly trend + recent runs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Trend */}
        <div className="rounded-xl border bg-card p-5 lg:col-span-2">
          <h2 className="text-sm font-semibold mb-4">Monthly Emissions Trend (tCO₂e)</h2>
          {trendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={trendData}>
                <defs>
                  {[1, 2, 3].map((s, i) => (
                    <linearGradient key={s} id={`g${s}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={SCOPE_COLORS[i]} stopOpacity={0.15} />
                      <stop offset="95%" stopColor={SCOPE_COLORS[i]} stopOpacity={0} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => `${v.toFixed(2)} tCO₂e`} />
                <Legend iconType="circle" iconSize={8} />
                {[1, 2, 3].map((s, i) => (
                  <Area
                    key={s}
                    type="monotone"
                    dataKey={`scope${s}`}
                    name={`Scope ${s}`}
                    stroke={SCOPE_COLORS[i]}
                    fill={`url(#g${s})`}
                    strokeWidth={2}
                    dot={false}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
              Upload data to see trends
            </div>
          )}
        </div>

        {/* Recent runs */}
        <div className="rounded-xl border bg-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold">Recent Ingestion</h2>
            <button
              onClick={() => navigate('/ingestion')}
              className="text-xs text-primary hover:underline"
            >
              View all
            </button>
          </div>
          <div className="space-y-2">
            {data.recent_runs?.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-6">
                No ingestion runs yet
              </p>
            )}
            {data.recent_runs?.map(run => (
              <div key={run.id} className="flex flex-col gap-1 rounded-lg border p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium">{sourceTypeLabel(run.source_type)}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${runStatusColor(run.status)}`}>
                    {run.status_display}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground truncate">{run.file_name}</p>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="text-esg-600 font-medium">{run.success_count} ok</span>
                  {run.error_count > 0 && <span className="text-red-600">{run.error_count} err</span>}
                  {run.skipped_count > 0 && <span>{run.skipped_count} skip</span>}
                </div>
              </div>
            ))}
          </div>
          {pendingCount > 0 && (
            <button
              onClick={() => navigate('/review')}
              className="mt-4 w-full rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-sm font-medium text-primary hover:bg-primary/10 transition-colors"
            >
              Review {pendingCount} pending records →
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
