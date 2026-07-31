import { useCallback, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '@/api/client'
import { chatApi, streamAnswer } from '@/api/chat'
import type { Citation } from '@/types'

export const chatKeys = {
  all: ['chat'] as const,
  sessions: () => [...chatKeys.all, 'sessions'] as const,
  session: (id: string) => [...chatKeys.all, 'session', id] as const,
  config: () => [...chatKeys.all, 'config'] as const,
}

/** Lượt đang được trả lời — sống ở state cục bộ, không nằm trong cache. */
export interface PendingTurn {
  question: string
  citations: Citation[]
  text: string
  /** searching = đã gửi, chưa có token nào. Người dùng cần thấy hệ thống đang làm gì. */
  phase: 'searching' | 'answering' | 'error'
  errorMessage?: string
  canCreateTicket: boolean
  noContextFound: boolean
}

export function useSessionDetail(sessionId: string | undefined) {
  return useQuery({
    queryKey: chatKeys.session(sessionId!),
    queryFn: () => chatApi.getSession(sessionId!),
    enabled: Boolean(sessionId),
  })
}

export function useChatConfig() {
  return useQuery({
    queryKey: chatKeys.config(),
    queryFn: () => chatApi.config(),
    staleTime: 10 * 60_000,
  })
}

/**
 * Quản lý một lượt hỏi–đáp theo luồng.
 *
 * ★ Câu trả lời đang stream KHÔNG được đưa vào cache React Query. Cache là để
 * chứa dữ liệu đã ổn định; ghi vào đó 200 lần/giây sẽ khiến mọi component
 * đang đọc cache render lại theo. Khi stream xong mới nạp lại lịch sử từ
 * server — lúc đó dữ liệu mới là sự thật.
 */
export function useConversation(sessionId: string | undefined) {
  const queryClient = useQueryClient()
  const [pending, setPending] = useState<PendingTurn | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const stop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  const send = useCallback(
    async (question: string) => {
      if (!sessionId || !question.trim()) return

      const controller = new AbortController()
      abortRef.current = controller

      setPending({
        question: question.trim(),
        citations: [],
        text: '',
        phase: 'searching',
        canCreateTicket: false,
        noContextFound: false,
      })

      try {
        for await (const event of streamAnswer(sessionId, question.trim(), controller.signal)) {
          if (event.type === 'citations') {
            // Trích dẫn tới TRƯỚC nội dung: người dùng thấy ngay câu trả lời
            // dựa trên tài liệu nào, trong khi chữ còn đang chạy.
            setPending((p) => (p ? { ...p, citations: event.data.citations } : p))
          } else if (event.type === 'token') {
            setPending((p) =>
              p ? { ...p, phase: 'answering', text: p.text + event.data.delta } : p,
            )
          } else if (event.type === 'done') {
            setPending((p) =>
              p
                ? {
                    ...p,
                    noContextFound: event.data.noContextFound,
                    canCreateTicket: Boolean(event.data.canCreateTicket),
                  }
                : p,
            )
          } else {
            setPending((p) =>
              p
                ? {
                    ...p,
                    phase: 'error',
                    errorMessage: event.data.message,
                    canCreateTicket: Boolean(event.data.canCreateTicket),
                  }
                : p,
            )
            return
          }
        }

        // Stream kết thúc bình thường ⇒ nạp lại lịch sử từ server rồi mới xoá
        // lượt tạm. Xoá trước khi dữ liệu mới về sẽ làm câu trả lời biến mất
        // trong chớp mắt rồi hiện lại.
        await queryClient.invalidateQueries({ queryKey: chatKeys.session(sessionId) })
        await queryClient.invalidateQueries({ queryKey: chatKeys.sessions() })
        setPending(null)
      } catch (err) {
        if (controller.signal.aborted) {
          // Người dùng chủ động dừng — không phải lỗi
          setPending(null)
          return
        }
        setPending((p) =>
          p
            ? {
                ...p,
                phase: 'error',
                errorMessage:
                  err instanceof ApiError
                    ? err.message
                    : 'Không kết nối được tới trợ lý ảo. Vui lòng thử lại.',
                canCreateTicket: true,
              }
            : p,
        )
      } finally {
        abortRef.current = null
      }
    },
    [sessionId, queryClient],
  )

  const isStreaming = pending !== null && pending.phase !== 'error'

  return { pending, send, stop, isStreaming, dismiss: () => setPending(null) }
}
