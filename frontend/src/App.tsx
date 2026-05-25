import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { createContext, useContext } from 'react'
import { Toaster } from '@/components/ui/toaster'
import { useAuthStore } from '@/hooks/useAuth'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { IngestionPage } from '@/pages/IngestionPage'
import { ReviewQueuePage } from '@/pages/ReviewQueuePage'
import { AuditLogPage } from '@/pages/AuditLogPage'
import type { User } from '@/types'

interface AuthContextValue {
  user: User | null
  setUser: (u: User | null) => void
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  setUser: () => {},
  logout: () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuthStore()
  if (loading) return (
    <div className="flex h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    </div>
  )
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const auth = useAuthStore()

  return (
    <AuthContext.Provider value={{ user: auth.user, setUser: auth.setUser, logout: auth.logout }}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="ingestion" element={<IngestionPage />} />
            <Route path="review" element={<ReviewQueuePage />} />
            <Route path="audit" element={<AuditLogPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster />
    </AuthContext.Provider>
  )
}
