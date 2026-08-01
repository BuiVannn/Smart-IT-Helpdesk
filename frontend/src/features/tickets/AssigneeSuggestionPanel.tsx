/**
 * Gợi ý người xử lý (US-20) — CHỈ GỢI Ý, KHÔNG TỰ GIAO.
 *
 * ★ Danh sách chỉ được tải khi người dùng bấm "Xem gợi ý". Endpoint này quét
 * tải công việc của toàn đội IT; gọi nó mỗi lần ai đó mở một ticket là biến
 * một truy vấn tổng hợp thành truy vấn chạy trên mọi lượt xem trang.
 *
 * ★ Luôn hiển thị LÝ DO bằng chữ, không chỉ điểm số. "0,72" không giúp Agent
 * trưởng quyết định gì; "chuyên môn Mạng (mức 3), đang mở 2 ticket, đang
 * trong ca trực" thì có. Điểm số chỉ để giải thích thứ tự.
 */

import { useState } from 'react'
import { ApiError } from '@/api/client'
import { Badge, Button } from '@/components/ui'
import { useAssignTicket, useAssigneeSuggestions } from './hooks'
import type { Ticket, UserRole } from '@/types'

export function AssigneeSuggestionPanel({
  ticket,
  role,
}: {
  ticket: Ticket
  role: UserRole
}) {
  const [open, setOpen] = useState(false)
  const query = useAssigneeSuggestions(ticket.id, open)
  const assign = useAssignTicket(ticket.id)

  if (role !== 'IT_AGENT' && role !== 'ADMIN') return null
  // Ticket đã đóng/huỷ thì không còn ai để giao.
  if (ticket.status === 'CLOSED' || ticket.status === 'CANCELLED') return null

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium text-slate-700">Gợi ý người xử lý</h2>
        {!open && (
          <Button variant="secondary" onClick={() => setOpen(true)}>
            Xem gợi ý
          </Button>
        )}
      </div>

      {open && (
        <div className="mt-3">
          {query.isLoading && <p className="text-sm text-slate-500">Đang tính điểm…</p>}

          {query.isError && (
            <p role="alert" className="text-sm text-red-700">
              {query.error instanceof ApiError
                ? query.error.message
                : 'Không tải được gợi ý'}
            </p>
          )}

          {query.data && query.data.suggestions.length === 0 && (
            <p className="text-sm text-slate-500">
              Chưa có IT Agent nào đang hoạt động để gợi ý.
            </p>
          )}

          {query.data && query.data.suggestions.length > 0 && (
            <>
              {!query.data.category && (
                <p className="mb-2 text-xs text-amber-700">
                  Yêu cầu chưa được phân loại nên chưa xét chuyên môn — thứ hạng
                  hiện chỉ dựa trên khối lượng công việc.
                </p>
              )}
              <ul className="divide-y divide-slate-100">
                {query.data.suggestions.map((item, index) => (
                  <li key={item.agentId} className="flex items-start gap-3 py-3">
                    <span className="mt-0.5 w-5 shrink-0 text-sm tabular-nums text-slate-400">
                      {index + 1}.
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-slate-800">
                          {item.fullName}
                        </span>
                        <Badge className="bg-slate-100 text-slate-600">
                          {item.score.toFixed(2)} điểm
                        </Badge>
                        {!item.onDuty && (
                          <Badge className="bg-slate-100 text-slate-500">Ngoài ca</Badge>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{item.reason}</p>
                    </div>
                    <Button
                      variant="secondary"
                      loading={assign.isPending}
                      disabled={ticket.assignee?.id === item.agentId}
                      onClick={() =>
                        void assign
                          .mutateAsync({
                            assigneeId: item.agentId,
                            version: ticket.version,
                          })
                          .catch(() => {})
                      }
                    >
                      {ticket.assignee?.id === item.agentId ? 'Đang xử lý' : 'Giao việc'}
                    </Button>
                  </li>
                ))}
              </ul>
            </>
          )}

          {assign.error && (
            <p role="alert" className="mt-2 text-sm text-red-700">
              {assign.error instanceof ApiError
                ? assign.error.message
                : 'Giao việc không thành công'}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
