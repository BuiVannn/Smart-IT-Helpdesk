import { useState } from 'react'
import { ApiError } from '@/api/client'
import { Button, LoadingBlock, inputClass } from '@/components/ui'
import { formatDateTime } from '@/lib/utils'
import { useAddComment, useTicketComments } from './hooks'
import type { UserRole } from '@/types'

export function CommentThread({
  ticketId,
  role,
}: {
  ticketId: string
  role: UserRole
}) {
  const comments = useTicketComments(ticketId)
  const addComment = useAddComment(ticketId)
  const [body, setBody] = useState('')
  const [isInternal, setIsInternal] = useState(false)

  const canWriteInternal = role === 'IT_AGENT' || role === 'ADMIN'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!body.trim()) return
    try {
      await addComment.mutateAsync({ body: body.trim(), isInternal })
      setBody('')
      setIsInternal(false)
    } catch {
      // Giữ nguyên nội dung đang gõ để người dùng không mất bài viết
    }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-700">
        Trao đổi
      </h2>

      {comments.isLoading ? (
        <LoadingBlock />
      ) : comments.data && comments.data.length > 0 ? (
        <ul className="divide-y divide-slate-100">
          {comments.data.map((c) => (
            <li
              key={c.id}
              className={c.isInternal ? 'bg-amber-50/60 px-4 py-3' : 'px-4 py-3'}
            >
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
                <span className="font-medium text-slate-800">{c.author.fullName}</span>
                <span className="text-slate-400">{formatDateTime(c.createdAt)}</span>
                {c.isInternal && (
                  // Nhãn phải rõ ràng: Agent gõ nhầm ô rồi để lộ trao đổi nội
                  // bộ cho người dùng là sự cố không rút lại được.
                  <span className="rounded bg-amber-200 px-1.5 py-0.5 font-medium text-amber-900">
                    Nội bộ — người gửi yêu cầu không thấy
                  </span>
                )}
              </div>
              <p className="whitespace-pre-wrap text-sm text-slate-700">{c.body}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="px-4 py-6 text-center text-sm text-slate-500">
          Chưa có trao đổi nào.
        </p>
      )}

      <form onSubmit={submit} className="border-t border-slate-200 p-4">
        {addComment.isError && (
          <div role="alert" className="mb-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {addComment.error instanceof ApiError
              ? addComment.error.message
              : 'Không gửi được bình luận'}
          </div>
        )}

        <label htmlFor="comment-body" className="sr-only">Nội dung trao đổi</label>
        <textarea
          id="comment-body"
          rows={3}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          className={inputClass}
          placeholder={
            isInternal
              ? 'Ghi chú nội bộ, chỉ đội IT đọc được…'
              : 'Nhập nội dung trao đổi…'
          }
        />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          {canWriteInternal && (
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={isInternal}
                onChange={(e) => setIsInternal(e.target.checked)}
                className="rounded border-slate-300"
              />
              Ghi chú nội bộ
            </label>
          )}
          <Button
            type="submit"
            loading={addComment.isPending}
            disabled={!body.trim()}
            className="ml-auto"
          >
            Gửi
          </Button>
        </div>
      </form>
    </section>
  )
}
