import { Link } from 'react-router-dom'
import { EmptyState, LoadingBlock } from '@/components/ui'
import { AiStatusHint, PriorityBadge, SlaBadge, StatusBadge } from './badges'
import { formatRelative } from '@/lib/utils'
import type { Page, TicketListItem } from '@/types'

/**
 * Bảng ticket dùng chung cho "Yêu cầu của tôi" và "Hàng chờ xử lý".
 *
 * Trên màn hình hẹp bảng đổi thành danh sách thẻ: bảng 7 cột cuộn ngang trên
 * điện thoại là thứ không ai dùng được, mà nhân viên báo sự cố thường đang
 * cầm điện thoại chứ không ngồi trước máy tính.
 */
export function TicketTable({
  page,
  isLoading,
  emptyTitle,
  emptyHint,
  emptyAction,
  showRequester = false,
}: {
  page?: Page<TicketListItem>
  isLoading: boolean
  emptyTitle: string
  emptyHint?: string
  emptyAction?: React.ReactNode
  showRequester?: boolean
}) {
  if (isLoading && !page) return <LoadingBlock />
  if (!page || page.data.length === 0) {
    return <EmptyState title={emptyTitle} hint={emptyHint} action={emptyAction} />
  }

  return (
    <>
      {/* Điện thoại: danh sách thẻ */}
      <ul className="space-y-2 md:hidden">
        {page.data.map((t) => (
          <li key={t.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <Link to={`/tickets/${t.id}`} className="block">
              <div className="flex items-start justify-between gap-2">
                <span className="font-mono text-xs text-slate-500">{t.code}</span>
                <StatusBadge status={t.status} />
              </div>
              <p className="mt-1 font-medium text-slate-900">{t.title}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <PriorityBadge priority={t.priority} />
                <SlaBadge state={t.slaState} dueAt={t.slaResolutionDueAt} />
                <AiStatusHint status={t.aiStatus} />
              </div>
              <p className="mt-2 text-xs text-slate-500">
                {formatRelative(t.createdAt)}
                {t.assignee ? ` · ${t.assignee.fullName}` : ' · chưa có người xử lý'}
              </p>
            </Link>
          </li>
        ))}
      </ul>

      {/* Máy tính: bảng */}
      <div className="hidden overflow-x-auto rounded-lg border border-slate-200 bg-white md:block">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
            <tr>
              <th scope="col" className="px-4 py-2.5 font-medium">Mã</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Tiêu đề</th>
              {showRequester && (
                <th scope="col" className="px-4 py-2.5 font-medium">Người gửi</th>
              )}
              <th scope="col" className="px-4 py-2.5 font-medium">Trạng thái</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Ưu tiên</th>
              <th scope="col" className="px-4 py-2.5 font-medium">SLA</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Người xử lý</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Tạo lúc</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {page.data.map((t) => (
              <tr key={t.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-slate-500">
                  {t.code}
                </td>
                <td className="px-4 py-2.5">
                  <Link
                    to={`/tickets/${t.id}`}
                    className="font-medium text-slate-900 hover:text-blue-700 hover:underline"
                  >
                    {t.title}
                  </Link>
                  <div className="mt-0.5 flex items-center gap-2">
                    {t.category && (
                      <span className="text-xs text-slate-500">{t.category.name}</span>
                    )}
                    <AiStatusHint status={t.aiStatus} />
                  </div>
                </td>
                {showRequester && (
                  <td className="whitespace-nowrap px-4 py-2.5 text-slate-600">
                    {t.requester.fullName}
                  </td>
                )}
                <td className="px-4 py-2.5"><StatusBadge status={t.status} /></td>
                <td className="px-4 py-2.5"><PriorityBadge priority={t.priority} /></td>
                <td className="px-4 py-2.5">
                  <SlaBadge state={t.slaState} dueAt={t.slaResolutionDueAt} />
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-slate-600">
                  {t.assignee?.fullName ?? (
                    <span className="text-slate-400">Chưa giao</span>
                  )}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-slate-500">
                  {formatRelative(t.createdAt)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

export function Pagination({
  page,
  onChange,
}: {
  page: Page<TicketListItem>
  onChange: (next: number) => void
}) {
  const { page: current, totalPages, totalItems } = page.pagination
  if (totalItems === 0) return null

  return (
    <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
      <span>
        Trang {current}/{totalPages} · {totalItems} yêu cầu
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => onChange(current - 1)}
          disabled={current <= 1}
          className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40"
        >
          Trước
        </button>
        <button
          onClick={() => onChange(current + 1)}
          disabled={current >= totalPages}
          className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40"
        >
          Sau
        </button>
      </div>
    </div>
  )
}
