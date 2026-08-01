import { cn } from '@/lib/utils'
import type { TicketStatus } from '@/types'

const STATUS_CONFIG: Record<TicketStatus, { label: string; className: string }> = {
    NEW: { label: 'Mới', className: 'bg-slate-100 text-slate-700' },
    ASSIGNED: { label: 'Đã giao', className: 'bg-blue-100 text-blue-700' },
    IN_PROGRESS: { label: 'Đang xử lý', className: 'bg-amber-100 text-amber-800' },
    PENDING_REQUESTER: { label: 'Chờ phản hồi', className: 'bg-purple-100 text-purple-700' },
    RESOLVED: { label: 'Đã xử lý', className: 'bg-emerald-100 text-emerald-700' },
    CLOSED: { label: 'Đã đóng', className: 'bg-slate-200 text-slate-600' },
    CANCELLED: { label: 'Đã huỷ', className: 'bg-slate-100 text-slate-500' },
}

export function StatusBadge({ status, className }: { status: TicketStatus; className?: string }) {
    const config = STATUS_CONFIG[status]
    return (
        <span
            className={cn(
                'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                config.className,
                className,
            )}
        >
            {config.label}
        </span>
    )
}
