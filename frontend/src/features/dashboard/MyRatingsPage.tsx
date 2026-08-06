/**
 * Danh sách đánh giá về tôi (US-43 — F8).
 *
 * Chỉ IT Agent/Admin xem được (backend `require_agent`). Mỗi người chỉ thấy
 * đánh giá của ticket CHÍNH MÌNH xử lý — backend lọc theo người đang đăng
 * nhập. CỐ Ý không có thông tin người chấm: ẩn danh là AC của US-43.
 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { feedbackApi } from '@/api/feedback'
import { Button, EmptyState, ErrorState, LoadingBlock } from '@/components/ui'
import { formatDateTime } from '@/lib/utils'

function stars(value: number): string {
  return '★'.repeat(value)
}

export function MyRatingsPage() {
  const [page, setPage] = useState(1)

  const query = useQuery({
    queryKey: ['my-ratings', page],
    queryFn: () => feedbackApi.listMyRatings(page),
  })

  if (query.isLoading) return <LoadingBlock label="Đang tải đánh giá…" />

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  }

  const { data: items, pagination } = query.data!

  if (items.length === 0) {
    return (
      <div className="space-y-5">
        <h1 className="text-lg font-semibold text-slate-900">Đánh giá về tôi</h1>
        <EmptyState
          title="Chưa có đánh giá nào"
          hint="Khi nhân viên đánh giá ticket bạn đã xử lý, kết quả sẽ xuất hiện ở đây."
        />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Đánh giá về tôi</h1>
          <p className="text-xs text-slate-500">Ẩn danh người chấm — chỉ thấy đánh giá của ticket bạn xử lý.</p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[600px] text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
              <th className="px-4 py-3 font-medium">Ticket</th>
              <th className="px-4 py-3 font-medium">Tiêu đề</th>
              <th className="px-4 py-3 font-medium">Điểm</th>
              <th className="px-4 py-3 font-medium">Nhận xét</th>
              <th className="px-4 py-3 font-medium">Thời điểm</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.ratingId} className="border-b border-slate-100 last:border-0">
                <td className="px-4 py-3">
                  <Link
                    to={`/tickets/${item.ticketId}`}
                    className="font-mono text-xs text-blue-600 hover:underline"
                  >
                    {item.ticketCode}
                  </Link>
                </td>
                <td className="max-w-[260px] truncate px-4 py-3 text-slate-700">
                  {item.ticketTitle}
                </td>
                <td className="px-4 py-3 text-amber-500">{stars(item.score)}</td>
                <td className="max-w-[280px] px-4 py-3 text-slate-700">
                  {item.comment || <span className="text-slate-400">—</span>}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                  {formatDateTime(item.createdAt)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pagination.totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">
            Trang {pagination.page} / {pagination.totalPages} · {pagination.totalItems} đánh giá
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={pagination.page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Trước
            </Button>
            <Button
              variant="secondary"
              disabled={pagination.page >= pagination.totalPages}
              onClick={() => setPage((p) => Math.min(pagination.totalPages, p + 1))}
            >
              Sau
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
