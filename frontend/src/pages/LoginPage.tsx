import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Leaf, Eye, EyeOff, ArrowRight, Lock } from 'lucide-react'
import { login } from '@/api/auth'
import { useAuth } from '@/App'
import { getMe } from '@/api/auth'

export function LoginPage() {
  const [username, setUsername] = useState('analyst')
  const [password, setPassword] = useState('analyst123')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { setUser } = useAuth()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const tokens = await login(username, password)
      setUser(tokens.user)
      navigate('/dashboard', { replace: true })
    } catch {
      setError('Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between bg-esg-950 p-12 text-white">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-esg-600">
            <Leaf className="h-5 w-5 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-xl font-semibold">Breathe ESG</span>
        </div>

        <div className="space-y-6">
          <div className="space-y-3">
            <h1 className="text-4xl font-bold leading-tight">
              Emissions data,<br />
              <span className="text-esg-400">audit-ready.</span>
            </h1>
            <p className="text-esg-200 text-lg leading-relaxed max-w-sm">
              Ingest from SAP, utility portals, and travel platforms.
              Normalize. Review. Sign off.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Scope 1', desc: 'Direct combustion' },
              { label: 'Scope 2', desc: 'Purchased energy' },
              { label: 'Scope 3', desc: 'Value chain' },
            ].map(({ label, desc }) => (
              <div key={label} className="rounded-xl bg-esg-900 p-4 border border-esg-800">
                <p className="text-sm font-semibold text-esg-300">{label}</p>
                <p className="text-xs text-esg-500 mt-1">{desc}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="text-esg-600 text-xs">
          DEFRA 2024 emission factors · GHG Protocol · ISO 14064
        </p>
      </div>

      {/* Right panel — form */}
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="w-full max-w-sm space-y-8">
          <div className="lg:hidden flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary">
              <Leaf className="h-4 w-4 text-primary-foreground" strokeWidth={2.5} />
            </div>
            <span className="font-semibold">Breathe ESG</span>
          </div>

          <div>
            <h2 className="text-2xl font-bold">Welcome back</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Sign in to your analyst account
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full rounded-md border bg-background px-3 py-2.5 text-sm ring-offset-background transition placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="analyst"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">Password</label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2.5 pr-10 text-sm ring-offset-background transition placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2.5 text-sm text-destructive">
                <Lock className="h-4 w-4 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {loading ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
              ) : (
                <>Sign in <ArrowRight className="h-4 w-4" /></>
              )}
            </button>
          </form>

          <div className="rounded-lg bg-muted p-4 space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Demo credentials</p>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground"><span className="font-mono text-foreground">analyst</span> / <span className="font-mono text-foreground">analyst123</span> — Analyst</p>
              <p className="text-xs text-muted-foreground"><span className="font-mono text-foreground">admin</span> / <span className="font-mono text-foreground">admin123</span> — Admin</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
