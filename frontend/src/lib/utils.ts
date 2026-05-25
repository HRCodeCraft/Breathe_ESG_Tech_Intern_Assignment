import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCO2e(kg: string | number | null | undefined): string {
  if (kg === null || kg === undefined || kg === '') return '—'
  const val = typeof kg === 'string' ? parseFloat(kg) : kg
  if (isNaN(val)) return '—'
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(2)} ktCO₂e`
  if (val >= 1_000) return `${(val / 1_000).toFixed(2)} tCO₂e`
  return `${val.toFixed(2)} kgCO₂e`
}

export function formatNumber(val: string | number | null | undefined, decimals = 2): string {
  if (val === null || val === undefined || val === '') return '—'
  const n = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(n)) return '—'
  return n.toLocaleString('en-GB', { maximumFractionDigits: decimals })
}

export function scopeColor(scope: number): string {
  switch (scope) {
    case 1: return 'text-orange-600 bg-orange-50 border-orange-200'
    case 2: return 'text-blue-600 bg-blue-50 border-blue-200'
    case 3: return 'text-purple-600 bg-purple-50 border-purple-200'
    default: return 'text-gray-600 bg-gray-50 border-gray-200'
  }
}

export function scopeColorDot(scope: number): string {
  switch (scope) {
    case 1: return 'bg-orange-500'
    case 2: return 'bg-blue-500'
    case 3: return 'bg-purple-500'
    default: return 'bg-gray-400'
  }
}

export function statusColor(status: string): string {
  switch (status) {
    case 'approved':  return 'text-esg-700 bg-esg-50 border-esg-200'
    case 'pending':   return 'text-yellow-700 bg-yellow-50 border-yellow-200'
    case 'flagged':   return 'text-red-700 bg-red-50 border-red-200'
    case 'rejected':  return 'text-gray-600 bg-gray-100 border-gray-200'
    default:          return 'text-gray-600 bg-gray-50 border-gray-200'
  }
}

export function flagColor(flag: string): string {
  switch (flag) {
    case 'outlier':        return 'text-red-700 bg-red-50'
    case 'duplicate':      return 'text-orange-700 bg-orange-50'
    case 'missing_factor': return 'text-purple-700 bg-purple-50'
    case 'unit_mismatch':  return 'text-yellow-700 bg-yellow-50'
    case 'zero_value':     return 'text-gray-600 bg-gray-100'
    default:               return 'text-gray-600 bg-gray-100'
  }
}

export function categoryIcon(category: string): string {
  const map: Record<string, string> = {
    stationary_combustion: '🔥',
    mobile_combustion: '🚗',
    purchased_electricity: '⚡',
    business_travel_air: '✈️',
    business_travel_hotel: '🏨',
    business_travel_ground: '🚌',
    procurement: '📦',
    waste: '🗑️',
  }
  return map[category] || '📊'
}

export function sourceTypeLabel(source: string): string {
  const map: Record<string, string> = {
    sap_fuel: 'SAP Fuel',
    sap_procurement: 'SAP Procurement',
    utility_electricity: 'Utility',
    travel: 'Travel',
  }
  return map[source] || source
}

export function runStatusColor(status: string): string {
  switch (status) {
    case 'completed': return 'text-esg-700 bg-esg-50 border-esg-200'
    case 'completed_with_errors': return 'text-yellow-700 bg-yellow-50 border-yellow-200'
    case 'processing': return 'text-blue-700 bg-blue-50 border-blue-200'
    case 'failed': return 'text-red-700 bg-red-50 border-red-200'
    case 'pending': return 'text-gray-600 bg-gray-100 border-gray-200'
    default: return 'text-gray-600 bg-gray-100'
  }
}
