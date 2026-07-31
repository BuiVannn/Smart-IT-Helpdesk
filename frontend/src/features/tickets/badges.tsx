/**
 * Nhãn trạng thái / mức ưu tiên / SLA.
 *
 * ★ Màu KHÔNG BAO GIỜ là thông tin duy nhất: mỗi nhãn đều có chữ tiếng Việt
 * đi kèm. Khoảng 8% nam giới bị rối loạn phân biệt màu — nếu chỉ dựa vào màu
 * để phân biệt "quá hạn" với "còn hạn" thì với họ hai thứ đó là một.
 */

import { Badge } from '@/components/ui'
import { timeUntil } from '@/lib/utils'
import type { AiStatus, SlaState, TicketPriority, TicketStatus } from '@/types'

const STATUS_LABEL: Record<TicketStatus, string> = {
  NEW: 'Mới',
  ASSIGNED: 'Đã giao',
  IN_PROGRESS: 'Đang xử lý',
  PENDING_REQUESTER: 'Chờ phản hồi',
  RESOLVED: 'Đã xử lý',
  CLOSED: 'Đã đóng',
  CANCELLED: 'Đã huỷ',
}

const STATUS_CLASS: Record<TicketStatus, string> = {
  NEW: 'bg-slate-100 text-slate-700',
  ASSIGNED: 'bg-blue-100 text-blue-800',
  IN_PROGRESS: 'bg-indigo-100 text-indigo-800',
  PENDING_REQUESTER: 'bg-amber-100 text-amber-800',
  RESOLVED: 'bg-emerald-100 text-emerald-800',
  CLOSED: 'bg-slate-200 text-slate-600',
  CANCELLED: 'bg-slate-200 text-slate-500 line-through',
}

export function StatusBadge({ status }: { status: TicketStatus }) {
  return <Badge className={STATUS_CLASS[status]}>{STATUS_LABEL[status]}</Badge>
}

export function statusLabel(status: TicketStatus): string {
  return STATUS_LABEL[status]
}

const PRIORITY_LABEL: Record<TicketPriority, string> = {
  LOW: 'Thấp',
  MEDIUM: 'Trung bình',
  HIGH: 'Cao',
  URGENT: 'Khẩn cấp',
}

const PRIORITY_CLASS: Record<TicketPriority, string> = {
  LOW: 'bg-slate-100 text-slate-600',
  MEDIUM: 'bg-sky-100 text-sky-800',
  HIGH: 'bg-orange-100 text-orange-800',
  URGENT: 'bg-red-100 text-red-800',
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  return <Badge className={PRIORITY_CLASS[priority]}>{PRIORITY_LABEL[priority]}</Badge>
}

export const PRIORITY_OPTIONS = Object.entries(PRIORITY_LABEL) as [TicketPriority, string][]

const SLA_LABEL: Record<SlaState, string> = {
  ON_TRACK: 'Trong hạn',
  AT_RISK: 'Sắp trễ',
  BREACHED: 'Quá hạn',
  MET: 'Đúng hạn',
}

const SLA_CLASS: Record<SlaState, string> = {
  ON_TRACK: 'bg-emerald-50 text-emerald-700',
  AT_RISK: 'bg-amber-100 text-amber-900 font-semibold',
  BREACHED: 'bg-red-100 text-red-800 font-semibold',
  MET: 'bg-emerald-100 text-emerald-800',
}

export function SlaBadge({
  state,
  dueAt,
}: {
  state: SlaState | null
  dueAt: string | null
}) {
  if (!state) return <span className="text-xs text-slate-400">—</span>
  return (
    <Badge className={SLA_CLASS[state]} title={dueAt ? timeUntil(dueAt) : undefined}>
      {SLA_LABEL[state]}
      {dueAt && state !== 'MET' && (
        <span className="ml-1 font-normal opacity-75">· {timeUntil(dueAt)}</span>
      )}
    </Badge>
  )
}

const AI_LABEL: Partial<Record<AiStatus, string>> = {
  PENDING: 'AI đang phân loại…',
  LOW_CONFIDENCE: 'AI không chắc chắn',
  FAILED: 'AI phân loại lỗi',
}

/**
 * Chỉ hiện khi AI CHƯA cho kết quả dùng được.
 * Trạng thái APPLIED không cần nhãn: người dùng quan tâm loại sự cố là gì,
 * không quan tâm ai gán nó.
 */
export function AiStatusHint({ status }: { status: AiStatus }) {
  const label = AI_LABEL[status]
  if (!label) return null
  return (
    <Badge className="bg-violet-50 text-violet-700">
      {status === 'PENDING' && (
        <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-violet-500" />
      )}
      {label}
    </Badge>
  )
}
