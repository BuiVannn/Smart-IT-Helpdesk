import { cn } from '@/lib/utils'

interface PaginationProps {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  className?: string
}

/** Số trang tối đa hiển thị trong dãy số (không tính nút ... và đầu/cuối) */
const MAX_VISIBLE = 5

/**
 * Tính dãy số trang cần hiển thị.
 * Ví dụ: page=5, totalPages=10 → [3, 4, 5, 6, 7]
 */
function getPageRange(current: number, total: number): number[] {
  if (total <= MAX_VISIBLE) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  const half = Math.floor(MAX_VISIBLE / 2)
  let start = Math.max(1, current - half)
  let end = start + MAX_VISIBLE - 1

  if (end > total) {
    end = total
    start = Math.max(1, end - MAX_VISIBLE + 1)
  }

  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
}

/**
 * Component phân trang.
 *
 * - Nút **Trước** bị vô hiệu ở trang 1.
 * - Nút **Sau** bị vô hiệu ở trang cuối.
 * - Hiển thị dấu `…` khi dãy số không liên tục từ đầu/cuối.
 */
export function Pagination({ page, totalPages, onPageChange, className }: PaginationProps) {
  // Không render gì nếu chỉ có 1 trang hoặc không có trang nào
  if (totalPages <= 1) return null

  const range = getPageRange(page, totalPages)
  const showStartEllipsis = range[0] > 2
  const showEndEllipsis = range[range.length - 1] < totalPages - 1

  const isFirst = page === 1
  const isLast = page === totalPages

  // ── Styles tái sử dụng ──────────────────────────────────────────────────
  const btnBase =
    'inline-flex h-9 min-w-[2.25rem] items-center justify-center rounded-md px-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1'
  const btnActive = 'bg-blue-600 text-white shadow-sm hover:bg-blue-700'
  const btnDefault = 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
  const btnDisabled = 'bg-white text-slate-300 border border-slate-200 cursor-not-allowed'

  return (
    <nav
      aria-label="Phân trang"
      className={cn('flex items-center justify-center gap-1', className)}
    >
      {/* Nút Trước */}
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={isFirst}
        aria-label="Trang trước"
        className={cn(btnBase, isFirst ? btnDisabled : btnDefault)}
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
        </svg>
      </button>

      {/* Trang 1 (luôn hiển thị nếu nằm ngoài range) */}
      {range[0] > 1 && (
        <button
          type="button"
          onClick={() => onPageChange(1)}
          aria-label="Trang 1"
          className={cn(btnBase, page === 1 ? btnActive : btnDefault)}
        >
          1
        </button>
      )}

      {/* Dấu ... đầu */}
      {showStartEllipsis && (
        <span className="flex h-9 w-9 items-center justify-center text-sm text-slate-400" aria-hidden>
          …
        </span>
      )}

      {/* Dãy số trang chính */}
      {range.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onPageChange(p)}
          aria-label={`Trang ${p}`}
          aria-current={p === page ? 'page' : undefined}
          className={cn(btnBase, p === page ? btnActive : btnDefault)}
        >
          {p}
        </button>
      ))}

      {/* Dấu ... cuối */}
      {showEndEllipsis && (
        <span className="flex h-9 w-9 items-center justify-center text-sm text-slate-400" aria-hidden>
          …
        </span>
      )}

      {/* Trang cuối (luôn hiển thị nếu nằm ngoài range) */}
      {range[range.length - 1] < totalPages && (
        <button
          type="button"
          onClick={() => onPageChange(totalPages)}
          aria-label={`Trang ${totalPages}`}
          className={cn(btnBase, page === totalPages ? btnActive : btnDefault)}
        >
          {totalPages}
        </button>
      )}

      {/* Nút Sau */}
      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={isLast}
        aria-label="Trang sau"
        className={cn(btnBase, isLast ? btnDisabled : btnDefault)}
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
        </svg>
      </button>
    </nav>
  )
}
