import { Link, useParams } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { Button, EmptyState, ErrorState, LoadingBlock } from '@/components/ui'
import { useAuth } from '@/features/auth/AuthProvider'
import { formatDateTime } from '@/lib/utils'
import { AiStatusHint, PriorityBadge, SlaBadge, StatusBadge } from './badges'
import { AiSuggestionPanel } from './AiSuggestionPanel'
import { AssigneeSuggestionPanel } from './AssigneeSuggestionPanel'
import { CommentThread } from './CommentThread'
import { StatusActions } from './StatusActions'
import { Timeline } from './Timeline'
import { useTicket } from './hooks'

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-2 text-sm">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="text-right text-slate-800">{children}</dd>
    </div>
  )
}

export function TicketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const query = useTicket(id)

  if (query.isLoading) return <LoadingBlock />

  if (query.isError) {
    // Backend trả 404 cho cả "không tồn tại" lẫn "không phải của bạn" — cố ý,
    // để không xác nhận sự tồn tại của ticket người khác. Frontend vì vậy
    // cũng chỉ được nói đúng một điều.
    if (query.error instanceof ApiError && query.error.status === 404) {
      return (
        <EmptyState
          title="Không tìm thấy yêu cầu này"
          hint="Yêu cầu không tồn tại hoặc bạn không có quyền xem."
          action={
            <Link to="/my-tickets">
              <Button variant="secondary">Về danh sách yêu cầu</Button>
            </Link>
          }
        />
      )
    }
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  }

  const ticket = query.data!
  const isAgent = user?.role === 'IT_AGENT' || user?.role === 'ADMIN'

  return (
    <div>
      <div className="mb-4">
        <Link to="/my-tickets" className="text-sm text-slate-500 hover:text-slate-800">
          ← Danh sách yêu cầu
        </Link>
      </div>

      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-xs text-slate-500">{ticket.code}</p>
          <h1 className="mt-1 text-xl font-semibold text-slate-900">{ticket.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <StatusBadge status={ticket.status} />
            <PriorityBadge priority={ticket.priority} />
            <SlaBadge state={ticket.slaState} dueAt={ticket.slaResolutionDueAt} />
            <AiStatusHint status={ticket.aiStatus} />
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-2 text-sm font-medium text-slate-700">Mô tả</h2>
            <p className="whitespace-pre-wrap text-sm text-slate-700">{ticket.description}</p>
          </section>

          {ticket.resolutionNote && (
            <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
              <h2 className="mb-2 text-sm font-medium text-emerald-900">Cách xử lý</h2>
              <p className="whitespace-pre-wrap text-sm text-emerald-900">
                {ticket.resolutionNote}
              </p>
            </section>
          )}

          {user && <CommentThread ticketId={ticket.id} role={user.role} />}
        </div>

        <div className="space-y-5">
          {user && <StatusActions ticket={ticket} role={user.role} />}

          {/* Chi tiết phân loại của AI chỉ dành cho người xử lý — người gửi
              yêu cầu đã có nhãn tóm tắt ở đầu trang. */}
          {isAgent && <AiSuggestionPanel ticket={ticket} />}
          {user && <AssigneeSuggestionPanel ticket={ticket} role={user.role} />}

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-1 text-sm font-medium text-slate-700">Thông tin</h2>
            <dl className="divide-y divide-slate-100">
              <InfoRow label="Người gửi">{ticket.requester.fullName}</InfoRow>
              <InfoRow label="Người xử lý">
                {ticket.assignee?.fullName ?? (
                  <span className="text-slate-400">Chưa giao</span>
                )}
              </InfoRow>
              <InfoRow label="Loại sự cố">
                {ticket.category?.name ?? <span className="text-slate-400">Chưa phân loại</span>}
              </InfoRow>
              <InfoRow label="Tạo lúc">{formatDateTime(ticket.createdAt)}</InfoRow>
              <InfoRow label="Hạn xử lý">
                {formatDateTime(ticket.slaResolutionDueAt)}
              </InfoRow>
              {ticket.resolvedAt && (
                <InfoRow label="Xử lý xong">{formatDateTime(ticket.resolvedAt)}</InfoRow>
              )}
            </dl>
          </section>

          <Timeline ticketId={ticket.id} />
        </div>
      </div>
    </div>
  )
}
