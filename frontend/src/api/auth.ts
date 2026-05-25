import { api } from './client'
import type { AuthTokens, User } from '@/types'

export async function login(username: string, password: string): Promise<AuthTokens> {
  const { data } = await api.post<AuthTokens>('/auth/token/', { username, password })
  localStorage.setItem('access_token', data.access)
  localStorage.setItem('refresh_token', data.refresh)
  return data
}

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>('/users/me/')
  return data
}

export function logout() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}
