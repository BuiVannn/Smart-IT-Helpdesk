import { cn } from '@/lib/utils'

interface LoadingSkeletonProps {
  variant?: 'list' | 'card'
  /** Chỉ dùng khi variant="list". Mặc định: 5 dòng. */
  rows?: number
  className?: string
}

// ── Skeleton một dòng danh sách ──────────────────────────────────────────────
function ListRowSkeleton() {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-100 bg-white p-4">
      {/* Avatar */}
      <div className="h-9 w-9 shrink-0 rounded-full bg-slate-200" />

      <div className="flex flex-1 flex-col gap-2">
        {/* Tiêu đề */}
        <div className="h-3.5 w-2/3 rounded bg-slate-200" />
        {/* Mô tả */}
        <div className="h-3 w-1/3 rounded bg-slate-100" />
      </div>

      {/* Badge trạng thái */}
      <div className="h-5 w-16 shrink-0 rounded-full bg-slate-200" />
      {/* Ngày */}
      <div className="h-3 w-20 shrink-0 rounded bg-slate-100" />
    </div>
  )
}

// ── Skeleton thẻ card ─────────────────────────────────────────────────────────
function CardSkeleton() {
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-5 shadow-sm">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="h-5 w-1/2 rounded bg-slate-200" />
        <div className="h-5 w-16 rounded-full bg-slate-200" />
      </div>

      {/* Nội dung */}
      <div className="flex flex-col gap-2">
        <div className="h-3 w-full rounded bg-slate-100" />
        <div className="h-3 w-4/5 rounded bg-slate-100" />
        <div className="h-3 w-3/5 rounded bg-slate-100" />
      </div>

      {/* Footer */}
      <div className="mt-5 flex items-center gap-3">
        <div className="h-7 w-7 rounded-full bg-slate-200" />
        <div className="h-3 w-24 rounded bg-slate-100" />
        <div className="ml-auto h-3 w-20 rounded bg-slate-100" />
      </div>
    </div>
  )
}

/**
 * Khung xám nhấp nháy thay thế nội dung khi đang tải.
 *
 * - `variant="list"` — dùng ở màn hình danh sách ticket, thông báo, ...
 * - `variant="card"` — dùng ở màn hình dashboard, thẻ thống kê, ...
 *
 * ⚠️ Skeleton phải có hình dạng giống nội dung sắp hiện, không phải spinner tròn.
 */
export function LoadingSkeleton({ variant = 'list', rows = 5, className }: LoadingSkeletonProps) {
  return (
    <div
      className={cn('animate-pulse', className)}
      role="status"
      aria-label="Đang tải dữ liệu..."
    >
      {variant === 'list' ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: rows }, (_, i) => (
            <ListRowSkeleton key={i} />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      )}

      {/* Accessibility: thông báo ẩn cho screen reader */}
      <span className="sr-only">Đang tải...</span>
    </div>
  )
}
