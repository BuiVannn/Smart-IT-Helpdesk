import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Định dạng ngày giờ theo giờ Việt Nam. Backend luôn trả UTC. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—'
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'vừa xong'
  if (mins < 60) return `${mins} phút trước`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} giờ trước`
  return `${Math.floor(hours / 24)} ngày trước`
}

/** Thời gian còn lại tới hạn SLA. Số âm = đã quá hạn. */
export function timeUntil(iso: string | null | undefined): string {
  if (!iso) return '—'
  const diffMs = new Date(iso).getTime() - Date.now()
  const abs = Math.abs(diffMs)
  const mins = Math.floor(abs / 60000)
  const label = mins < 60
    ? `${mins} phút`
    : mins < 1440
      ? `${Math.floor(mins / 60)} giờ`
      : `${Math.floor(mins / 1440)} ngày`
  return diffMs < 0 ? `quá hạn ${label}` : `còn ${label}`
}
