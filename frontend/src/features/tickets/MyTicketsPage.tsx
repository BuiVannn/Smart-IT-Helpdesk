import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, ErrorState, inputClass } from '@/components/ui'
import { useDebounced } from '@/hooks/useDebounced'
import { useTickets } from './hooks'
import { Pagination, TicketTable } from './TicketTable'
import { statusLabel } from './badges'
import type { TicketStatus } from '@/types'

const FILTERS: { key: string; label: string; status?: TicketStatus[] }[] = [
  { key: 'open', label: 'Đang mở', status: ['NEW', 'ASSIGNED', 'IN_PROGRESS', 'PENDING_REQUESTER'] },
  { key: 'resolved', label: 'Đã xử lý', status: ['RESOLVED', 'CLOSED'] },
  { key: 'all', label: 'Tất cả' },
]

export function MyTicketsPage() {
  const [filter, setFilter] = useState('open')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  // Chờ người dùng ngừng gõ rồi mới gọi API — không có bước này thì gõ
  // "mật khẩu" là bắn 8 request, và kết quả về không đúng thứ tự.
  const q = useDebounced(search, 350)

  const active = FILTERS.find((f) => f.key === filter)!
  const query = useTickets({ page, pageSize: 20, status: active.status, q: q || undefined })

  function changeFilter(key: string) {
    setFilter(key)
    setPage(1)   // đổi bộ lọc mà giữ nguyên trang 5 thì thường ra bảng rỗng
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-slate-900">Yêu cầu của tôi</h1>
        <Link to="/tickets/new">
          <Button>Tạo yêu cầu mới</Button>
        </Link>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex rounded-md border border-slate-300 bg-white p-0.5" role="tablist">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              role="tab"
              aria-selected={filter === f.key}
              onClick={() => changeFilter(f.key)}
              className={
                filter === f.key
                  ? 'rounded px-3 py-1.5 text-sm font-medium bg-slate-900 text-white'
                  : 'rounded px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100'
              }
            >
              {f.label}
            </button>
          ))}
        </div>

        <input
          type="search"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          placeholder="Tìm theo tiêu đề hoặc nội dung…"
          aria-label="Tìm kiếm yêu cầu"
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
            emptyTitle={
              q
                ? `Không tìm thấy yêu cầu nào khớp “${q}”`
                : `Bạn chưa có yêu cầu nào ở mục “${active.label}”`
            }
            emptyHint={
              q
                ? 'Thử từ khoá ngắn hơn, hoặc bỏ dấu.'
                : 'Gặp sự cố với máy tính, mạng hay phần mềm? Hãy gửi yêu cầu để đội IT hỗ trợ.'
            }
            emptyAction={
              !q && (
                <Link to="/tickets/new">
                  <Button>Tạo yêu cầu mới</Button>
                </Link>
              )
            }
          />
          {query.data && <Pagination page={query.data} onChange={setPage} />}
        </>
      )}

      {/* Cho người dùng biết bộ lọc đang áp dụng là gì — tránh tình huống
          "tôi vừa tạo ticket mà không thấy đâu" khi đang ở tab Đã xử lý */}
      {active.status && query.data && query.data.data.length > 0 && (
        <p className="mt-3 text-xs text-slate-500">
          Đang hiển thị: {active.status.map(statusLabel).join(', ')}
        </p>
      )}
    </div>
  )
}
