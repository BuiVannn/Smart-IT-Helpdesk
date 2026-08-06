import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError } from '@/api/client'
import { feedbackApi } from '@/api/feedback'
import { Button, LoadingBlock, inputClass } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { TicketStatus } from '@/types'

const RATEABLE_STATUSES: TicketStatus[] = ['RESOLVED', 'CLOSED']
const SCORES = [1, 2, 3, 4, 5]

export function RatingPanel({
  ticketId,
  status,
  requesterId,
  currentUserId,
}: {
  ticketId: string
  status: TicketStatus
  requesterId: string
  currentUserId: string
}) {
  const queryClient = useQueryClient()
  const [score, setScore] = useState(0)
  const [comment, setComment] = useState('')
  const [editing, setEditing] = useState(false)

  // Chỉ người gửi yêu cầu đánh giá được, và chỉ khi ticket đã xử lý xong/đóng.
  const visible = RATEABLE_STATUSES.includes(status) && currentUserId === requesterId

  const ratingQuery = useQuery({
    queryKey: ['ticket', ticketId, 'rating'],
    queryFn: async () => {
      try {
        return await feedbackApi.getRating(ticketId)
      } catch (err) {
        // 404 = chưa đánh giá — đây là trạng thái hợp lệ, không phải lỗi
        if (err instanceof ApiError && err.status === 404) return null
        throw err
      }
    },
    enabled: visible,
  })

  const save = useMutation({
    mutationFn: () => {
      const payload = { score, comment: comment.trim() || undefined }
      return ratingQuery.data
        ? feedbackApi.updateRating(ticketId, payload.score, payload.comment)
        : feedbackApi.createRating(ticketId, payload.score, payload.comment)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['ticket', ticketId, 'rating'] })
      setEditing(false)
    },
  })

  function startEditing() {
    if (!ratingQuery.data) return
    setScore(ratingQuery.data.score)
    setComment(ratingQuery.data.comment ?? '')
    setEditing(true)
  }

  if (!visible) return null

  const existing = ratingQuery.data

  if (ratingQuery.isLoading) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-2 text-sm font-medium text-slate-700">Đánh giá</h2>
        <LoadingBlock />
      </section>
    )
  }

  if (ratingQuery.isError) {
    return (
      <section className="rounded-lg border border-red-200 bg-red-50 p-4">
        <h2 className="mb-2 text-sm font-medium text-red-800">Đánh giá</h2>
        <p className="text-sm text-red-700">
          {ratingQuery.error instanceof ApiError
            ? ratingQuery.error.message
            : 'Không tải được đánh giá'}
        </p>
        <Button variant="secondary" className="mt-3" onClick={() => void ratingQuery.refetch()}>
          Thử lại
        </Button>
      </section>
    )
  }

  // ── Đã đánh giá và không còn sửa được ───────────────────────────────
  if (existing && !existing.isEditable && !editing) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-2 text-sm font-medium text-slate-700">Đánh giá của bạn</h2>
        <p className="text-lg text-amber-500">{'★'.repeat(existing.score)}</p>
        {existing.comment && (
          <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{existing.comment}</p>
        )}
        <p className="mt-3 text-xs text-slate-400">Không thể sửa sau 24 giờ kể từ lúc đánh giá.</p>
      </section>
    )
  }

  // ── Đã đánh giá, còn sửa được ───────────────────────────────────────
  if (existing && !editing) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-2 text-sm font-medium text-slate-700">Đánh giá của bạn</h2>
        <p className="text-lg text-amber-500">{'★'.repeat(existing.score)}</p>
        {existing.comment && (
          <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{existing.comment}</p>
        )}
        <Button variant="secondary" className="mt-3" onClick={startEditing}>
          Sửa đánh giá
        </Button>
      </section>
    )
  }

  // ── Chưa đánh giá, hoặc đang sửa ────────────────────────────────────
  const initialScore = existing ? existing.score : 0
  const displayedScore = editing ? score : score || initialScore

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-medium text-slate-700">
        {existing ? 'Sửa đánh giá' : 'Đánh giá dịch vụ'}
      </h2>

      {save.isError && (
        <div role="alert" className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {save.error instanceof ApiError ? save.error.message : 'Không lưu được đánh giá'}
        </div>
      )}

      <div className="mb-3 flex gap-1">
        {SCORES.map((s) => (
          <button
            key={s}
            type="button"
            aria-label={`${s} sao`}
            onClick={() => setScore(s)}
            className={cn(
              'text-2xl leading-none transition',
              s <= displayedScore ? 'text-amber-500' : 'text-slate-300 hover:text-amber-300',
            )}
          >
            ★
          </button>
        ))}
      </div>

      <label htmlFor={`rating-comment-${ticketId}`} className="sr-only">Nhận xét</label>
      <textarea
        id={`rating-comment-${ticketId}`}
        rows={3}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        className={inputClass}
        placeholder="Nhận xét thêm (tuỳ chọn)…"
      />

      <div className="mt-3 flex gap-2">
        <Button
          type="button"
          onClick={() => save.mutate()}
          loading={save.isPending}
          disabled={displayedScore === 0}
        >
          {existing ? 'Lưu thay đổi' : 'Gửi đánh giá'}
        </Button>
        {existing && (
          <Button type="button" variant="secondary" onClick={() => setEditing(false)}>
            Huỷ
          </Button>
        )}
      </div>
    </section>
  )
}
