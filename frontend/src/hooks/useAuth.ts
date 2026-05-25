import { create } from 'zustand'
import type { User } from '@/types'
import { getMe, logout as apiLogout } from '@/api/auth'

interface AuthState {
  user: User | null
  loading: boolean
  setUser: (user: User | null) => void
  initialize: () => Promise<void>
  logout: () => void
}

// Using a simple module-level store instead of zustand to avoid extra dep
// (zustand isn't in our deps yet — use React context)
import { useState, useEffect } from 'react'

export function useAuthStore() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setLoading(false)
      return
    }
    getMe()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      })
      .finally(() => setLoading(false))
  }, [])

  const logout = () => {
    apiLogout()
    setUser(null)
  }

  return { user, setUser, loading, logout }
}
