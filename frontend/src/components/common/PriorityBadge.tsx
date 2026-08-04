import { cn } from '@/lib/utils'
import type { TicketPriority } from '@/types'

const PRIORITY_CONFIG: Record<TicketPriority, { label: string; className: string }> = {
    LOW: { label: 'Thấp', className: 'bg-slate-100 text-slate-600' },
    MEDIUM: { label: 'Bình thường', className: 'bg-blue-100 text-blue-700' },
    HIGH: { label: 'Cao', className: 'bg-orange-100 text-orange-700' },
    URGENT: { label: 'Khẩn cấp', className: 'bg-red-100 text-red-700' },
}

export function PriorityBadge({ priority, className }: { priority: TicketPriority; className?: string }) {
    const config = PRIORITY_CONFIG[priority]
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
