import { cn, timeUntil } from '@/lib/utils'

interface SlaBadgeProps {
    dueAt: string | null
    resolvedAt?: string | null
    className?: string
}

export function SlaBadge({ dueAt, resolvedAt, className }: SlaBadgeProps) {
    if (!dueAt) return null

    if (resolvedAt) {
        return (
            <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium bg-slate-100 text-slate-500', className)}>
                ✅ Đã xử lý
            </span>
        )
    }

    const diffMs = new Date(dueAt).getTime() - Date.now()
    const isBreached = diffMs < 0
    const totalMs = 8 * 60 * 60 * 1000
    const percentLeft = diffMs / totalMs

    let icon = '🟢'
    let colorClass = 'bg-emerald-100 text-emerald-700'

    if (isBreached) {
        icon = '🔴'
        colorClass = 'bg-red-100 text-red-700'
    } else if (percentLeft <= 0.25) {
        icon = '🟠'
        colorClass = 'bg-amber-100 text-amber-800'
    }

    return (
        <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium', colorClass, className)}>
            {icon} {timeUntil(dueAt)}
        </span>
    )
}
