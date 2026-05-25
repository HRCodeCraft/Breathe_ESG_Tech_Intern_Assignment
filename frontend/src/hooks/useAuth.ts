import { useState, useEffect } from 'react'
import type { User } from '@/types'
import { getMe, logout as apiLogout } from '@/api/auth'

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
