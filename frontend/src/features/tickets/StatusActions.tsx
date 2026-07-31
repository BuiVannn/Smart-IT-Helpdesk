import { useState } from 'react'
import { ApiError } from '@/api/client'
import { Button, Field, inputClass } from '@/components/ui'
import { statusLabel } from './badges'
import { useAllowedTransitions, useChangeStatus, useClaimTicket } from './hooks'
import type { Ticket, TicketStatus, UserRole } from '@/types'

const MIN_RESOLUTION_NOTE = 10

/** Trạng thái nào bắt buộc phải có ghi chú xử lý — khớp TicketStateMachine. */
const NEEDS_NOTE: TicketStatus[] = ['RESOLVED']

/**
 * Nút thao tác trạng thái.
 *
 * ★ Danh sách nút KHÔNG được viết cứng ở frontend. Nó lấy từ
 * `GET /tickets/{id}/allowed-transitions` — máy trạng thái nằm ở backend,
 * frontend chỉ hỏi. Viết cứng ở đây thì mỗi lần backend đổi luật là frontend
 * hiện nút vô nghĩa rồi báo lỗi khi bấm.
 */
export function StatusActions({ ticket, role }: { ticket: Ticket; role: UserRole }) {
  const transitions = useAllowedTransitions(ticket.id)
  const changeStatus = useChangeStatus(ticket.id)
  const claim = useClaimTicket(ticket.id)

  const [pending, setPending] = useState<TicketStatus | null>(null)
  const [note, setNote] = useState('')

  const canClaim = role === 'IT_AGENT' && ticket.assignee === null
  const allowed = transitions.data?.allowedStatuses ?? []

  const error = changeStatus.error ?? claim.error
  const conflict = error instanceof ApiError && error.status === 409

  function start(status: TicketStatus) {
    if (NEEDS_NOTE.includes(status)) {
      setPending(status)
      setNote('')
    } else {
      void changeStatus.mutateAsync({ status, version: ticket.version }).catch(() => {})
    }
  }

  async function confirm() {
    if (!pending) return
    try {
      await changeStatus.mutateAsync({
        status: pending,
        resolutionNote: note.trim(),
        version: ticket.version,
      })
      setPending(null)
    } catch {
      // Lỗi đã hiển thị bên dưới; giữ nguyên form để người dùng sửa lại
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-medium text-slate-700">Thao tác</h2>

      {error && (
        <div role="alert" className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error instanceof ApiError ? error.message : 'Thao tác không thành công'}
          {conflict && (
            <p className="mt-1 text-xs">
              Người khác vừa cập nhật ticket này. Hãy tải lại trang để thấy trạng thái mới nhất.
            </p>
          )}
        </div>
      )}

      {pending ? (
        <div>
          <Field
            label="Ghi chú xử lý"
            htmlFor="resolution-note"
            required
            hint={`Mô tả cách đã khắc phục, tối thiểu ${MIN_RESOLUTION_NOTE} ký tự. Người gửi yêu cầu sẽ đọc được nội dung này.`}
          >
            <textarea
              id="resolution-note"
              rows={4}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className={inputClass}
              placeholder="Đã reset lại cấu hình DHCP trên switch tầng 5."
            />
          </Field>
          <div className="flex gap-2">
            <Button
              onClick={() => void confirm()}
              loading={changeStatus.isPending}
              disabled={note.trim().length < MIN_RESOLUTION_NOTE}
            >
              Xác nhận {statusLabel(pending)}
            </Button>
            <Button variant="secondary" onClick={() => setPending(null)}>
              Huỷ
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {canClaim && (
            <Button
              onClick={() => void claim.mutateAsync(ticket.version).catch(() => {})}
              loading={claim.isPending}
            >
              Nhận xử lý
            </Button>
          )}

          {transitions.isLoading && (
            <span className="text-sm text-slate-500">Đang tải thao tác…</span>
          )}

          {allowed.map((status) => (
            <Button
              key={status}
              variant={status === 'CANCELLED' ? 'danger' : 'secondary'}
              onClick={() => start(status)}
              loading={changeStatus.isPending}
            >
              {statusLabel(status)}
            </Button>
          ))}

          {!canClaim && allowed.length === 0 && !transitions.isLoading && (
            <p className="text-sm text-slate-500">
              Không có thao tác nào khả dụng với vai trò của bạn ở trạng thái hiện tại.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
