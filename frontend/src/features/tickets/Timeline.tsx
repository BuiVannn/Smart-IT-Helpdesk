import { LoadingBlock } from '@/components/ui'
import { formatDateTime } from '@/lib/utils'
import { statusLabel } from './badges'
import { useTicketEvents } from './hooks'
import type { TicketEvent, TicketEventType, TicketStatus } from '@/types'

const LABEL: Record<TicketEventType, string> = {
  CREATED: 'đã tạo yêu cầu',
  ASSIGNED: 'đã giao việc',
  UNASSIGNED: 'đã bỏ giao việc',
  STATUS_CHANGED: 'đã đổi trạng thái',
  PRIORITY_CHANGED: 'đã đổi mức ưu tiên',
  RECLASSIFIED: 'đã đổi loại sự cố',
  COMMENTED: 'đã bình luận',
  ATTACHMENT_ADDED: 'đã đính kèm tệp',
  AI_CLASSIFIED: 'AI đã phân loại',
  SLA_WARNED: 'sắp tới hạn SLA',
  SLA_BREACHED: 'đã quá hạn SLA',
  RATED: 'đã đánh giá',
  REOPENED: 'đã mở lại yêu cầu',
  AUTO_CLOSED: 'tự động đóng',
}

function describe(event: TicketEvent): string {
  const base = LABEL[event.eventType] ?? event.eventType
  if (event.eventType === 'STATUS_CHANGED' && event.oldValue && event.newValue) {
    return `${base}: ${statusLabel(event.oldValue as TicketStatus)} → ${statusLabel(
      event.newValue as TicketStatus,
    )}`
  }
  return base
}

/**
 * Lịch sử thay đổi (US-17). Dữ liệu đến từ bảng CHỈ GHI THÊM ở backend —
 * đây là nguồn sự thật khi có tranh cãi "ai đổi cái gì lúc nào".
 */
export function Timeline({ ticketId }: { ticketId: string }) {
  const events = useTicketEvents(ticketId)

  if (events.isLoading) return <LoadingBlock label="Đang tải lịch sử…" />
  if (!events.data?.length) return null

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-700">
        Lịch sử thay đổi
      </h2>
      <ol className="space-y-3 p-4">
        {events.data.map((event) => (
          <li key={event.id} className="flex gap-3 text-sm">
            <span
              aria-hidden="true"
              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-300"
            />
            <div className="min-w-0">
              <p className="text-slate-700">
                <span className="font-medium">
                  {event.actor?.fullName ?? 'Hệ thống'}
                </span>{' '}
                {describe(event)}
              </p>
              <p className="text-xs text-slate-400">{formatDateTime(event.createdAt)}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
