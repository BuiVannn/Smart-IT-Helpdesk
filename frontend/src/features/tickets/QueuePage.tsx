import { useState } from 'react'
import { ErrorState, inputClass } from '@/components/ui'
import { useAuth } from '@/features/auth/AuthProvider'
import { useDebounced } from '@/hooks/useDebounced'
import { useQueueStats, useTickets } from './hooks'
import { Pagination, TicketTable } from './TicketTable'
import type { TicketStatus } from '@/types'

type Tab = 'unassigned' | 'mine' | 'all'

const TABS: { key: Tab; label: string; hint: string }[] = [
  { key: 'unassigned', label: 'Chưa có người nhận', hint: 'Ticket mới chưa ai xử lý' },
  { key: 'mine', label: 'Việc của tôi', hint: 'Ticket đang giao cho bạn' },
  { key: 'all', label: 'Tất cả', hint: 'Toàn bộ ticket trong hệ thống' },
]

const OPEN: TicketStatus[] = ['NEW', 'ASSIGNED', 'IN_PROGRESS', 'PENDING_REQUESTER']

function StatCard({
  label,
  value,
  emphasis,
}: {
  label: string
  value: number
  emphasis?: 'warn' | 'danger'
}) {
  const tone =
    emphasis === 'danger'
      ? 'border-red-200 bg-red-50 text-red-800'
      : emphasis === 'warn'
        ? 'border-amber-200 bg-amber-50 text-amber-900'
        : 'border-slate-200 bg-white text-slate-800'
  return (
    <div className={`rounded-lg border p-4 ${tone}`}>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      <p className="mt-0.5 text-xs">{label}</p>
    </div>
  )
}

/**
 * Hàng chờ của IT Agent (US-12).
 *
 * Số đếm được tách khỏi bảng và làm mới mỗi 60 giây: Agent cần biết "có
 * ticket mới chưa ai nhận" mà không phải bấm F5 liên tục.
 */
export function QueuePage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<Tab>('unassigned')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const q = useDebounced(search, 350)

  const isAgent = user?.role === 'IT_AGENT' || user?.role === 'ADMIN'
  const stats = useQueueStats(Boolean(isAgent))

  const query = useTickets({
    page,
    pageSize: 20,
    status: OPEN,
    unassigned: tab === 'unassigned',
    mine: tab === 'mine',
    q: q || undefined,
    sortBy: 'slaResolutionDueAt',
    sortOrder: 'asc',   // sắp hết hạn lên đầu — đó là thứ Agent cần xử lý trước
  })

  function changeTab(next: Tab) {
    setTab(next)
    setPage(1)
  }

  return (
    <div>
      <h1 className="mb-5 text-xl font-semibold text-slate-900">Hàng chờ xử lý</h1>

      {stats.data && (
        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Chưa ai nhận" value={stats.data.unassigned} />
          <StatCard label="Việc của tôi" value={stats.data.assignedToMe} />
          <StatCard label="Đang xử lý" value={stats.data.inProgress} />
          <StatCard label="Sắp trễ hạn" value={stats.data.atRisk} emphasis="warn" />
          <StatCard label="Đã quá hạn" value={stats.data.breached} emphasis="danger" />
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex rounded-md border border-slate-300 bg-white p-0.5" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              title={t.hint}
              onClick={() => changeTab(t.key)}
              className={
                tab === t.key
                  ? 'rounded px-3 py-1.5 text-sm font-medium bg-slate-900 text-white'
                  : 'rounded px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100'
              }
            >
              {t.label}
            </button>
          ))}
        </div>

        <input
          type="search"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          placeholder="Tìm theo tiêu đề hoặc nội dung…"
          aria-label="Tìm kiếm trong hàng chờ"
          className={`${inputClass} max-w-xs`}
        />
      </div>

      {query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <>
          <TicketTable
            page={query.data}
            isLoading={query.isLoading}
            showRequester
            emptyTitle={
              tab === 'unassigned'
                ? 'Không còn ticket nào chờ nhận'
                : tab === 'mine'
                  ? 'Bạn chưa được giao ticket nào đang mở'
                  : 'Không có ticket nào đang mở'
            }
            emptyHint="Mở một ticket để nhận xử lý và trao đổi với người gửi."
          />
          {query.data && <Pagination page={query.data} onChange={setPage} />}
        </>
      )}
    </div>
  )
}
