import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { chatApi } from '@/api/chat'
import { Button, ErrorState, LoadingBlock } from '@/components/ui'
import { ChatEmptyState } from './ChatEmptyState'
import { Composer } from './Composer'
import { AssistantBubble, SearchingBubble, UserBubble } from './MessageBubble'
import { SessionSidebar } from './SessionSidebar'
import { chatKeys, useChatConfig, useConversation, useSessionDetail } from './useConversation'

const FALLBACK_MAX_LENGTH = 1000

export function ChatPage() {
  const queryClient = useQueryClient()
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [showSidebar, setShowSidebar] = useState(false)

  const detail = useSessionDetail(sessionId)
  const config = useChatConfig()
  const { pending, send, stop, isStreaming, dismiss } = useConversation(sessionId)

  const createSession = useMutation({
    mutationFn: () => chatApi.createSession(),
    onSuccess: (session) => {
      void queryClient.invalidateQueries({ queryKey: chatKeys.sessions() })
      setSessionId(session.id)
      setShowSidebar(false)
    },
  })

  // Mở phiên đầu tiên khi vào trang. Bắt người dùng bấm "Cuộc trò chuyện mới"
  // trước khi gõ được chữ nào là một bước thừa.
  useEffect(() => {
    if (!sessionId && !createSession.isPending && !createSession.isError) {
      createSession.mutate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const askOrCreate = useCallback(
    async (question: string) => {
      if (sessionId) return send(question)
      const session = await createSession.mutateAsync()
      setSessionId(session.id)
      return send(question)
    },
    [sessionId, send, createSession],
  )

  const messages = detail.data?.messages ?? []
  const isEmpty = messages.length === 0 && !pending
  const maxLength = config.data?.maxQuestionLength ?? FALLBACK_MAX_LENGTH

  return (
    <div className="-m-6 flex h-[calc(100vh-3.25rem)]">
      {/* Máy tính: cột lịch sử luôn hiện. Điện thoại: mở bằng nút bên dưới. */}
      <div className="hidden w-64 shrink-0 lg:block">
        <SessionSidebar
          activeId={sessionId}
          onSelect={setSessionId}
          onNew={() => createSession.mutate()}
          isCreating={createSession.isPending}
        />
      </div>

      {showSidebar && (
        <div className="fixed inset-0 z-20 flex lg:hidden">
          <div className="w-72 bg-slate-50">
            <SessionSidebar
              activeId={sessionId}
              onSelect={(id) => {
                setSessionId(id)
                setShowSidebar(false)
              }}
              onNew={() => createSession.mutate()}
              isCreating={createSession.isPending}
            />
          </div>
          <button
            aria-label="Đóng danh sách trò chuyện"
            onClick={() => setShowSidebar(false)}
            className="flex-1 bg-slate-900/30"
          />
        </div>
      )}

      <section className="flex min-w-0 flex-1 flex-col bg-slate-50">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-2.5">
          <button
            onClick={() => setShowSidebar(true)}
            className="rounded-md px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 lg:hidden"
          >
            Lịch sử
          </button>
          <h1 className="truncate text-sm font-semibold text-slate-900">Trợ lý ảo</h1>
          {config.data && config.data.model === 'fake' && (
            // Nói thẳng khi đang chạy mô hình giả — tránh cảnh demo cho
            // Trainer mà tưởng đang gọi LLM thật.
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500">
              mô hình giả lập
            </span>
          )}
        </header>

        <MessageArea
          isLoading={detail.isLoading && Boolean(sessionId)}
          isError={detail.isError}
          error={detail.error}
          onRetry={() => void detail.refetch()}
          isEmpty={isEmpty}
          onPickSuggestion={askOrCreate}
          messages={messages}
          pending={pending}
          onDismissError={dismiss}
        />

        <Composer
          onSend={askOrCreate}
          onStop={stop}
          isStreaming={isStreaming}
          maxLength={maxLength}
          disabled={createSession.isPending}
        />
      </section>
    </div>
  )
}

type MessageAreaProps = {
  isLoading: boolean
  isError: boolean
  error: unknown
  onRetry: () => void
  isEmpty: boolean
  onPickSuggestion: (q: string) => void
  messages: NonNullable<ReturnType<typeof useSessionDetail>['data']>['messages']
  pending: ReturnType<typeof useConversation>['pending']
  onDismissError: () => void
}

function MessageArea({
  isLoading,
  isError,
  error,
  onRetry,
  isEmpty,
  onPickSuggestion,
  messages,
  pending,
  onDismissError,
}: MessageAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Cuộn xuống cuối mỗi khi có chữ mới. `auto` chứ không `smooth`: cuộn mượt
  // trong lúc token tới liên tục sẽ giật, vì mỗi lần cuộn chưa xong đã có
  // lệnh cuộn tiếp theo.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, pending?.text, pending?.phase])

  if (isLoading) return <div className="flex-1 overflow-y-auto"><LoadingBlock /></div>

  if (isError) {
    return (
      <div className="flex-1 overflow-y-auto p-4">
        <ErrorState error={error} onRetry={onRetry} />
      </div>
    )
  }

  if (isEmpty) {
    return (
      <div className="flex-1 overflow-y-auto">
        <ChatEmptyState onPick={onPickSuggestion} />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      <ul
        className="mx-auto flex max-w-3xl flex-col gap-4"
        // Trình đọc màn hình đọc câu trả lời khi nó xuất hiện. `polite` để
        // không cắt ngang thứ người dùng đang nghe.
        aria-live="polite"
        aria-busy={pending?.phase === 'searching' || pending?.phase === 'answering'}
      >
        {messages.map((m) =>
          m.role === 'USER' ? (
            <UserBubble key={m.id} text={m.content} at={m.createdAt} />
          ) : (
            <AssistantBubble
              key={m.id}
              text={m.content}
              citations={m.citations}
              at={m.createdAt}
              isRefusal={m.noContextFound}
              showCreateTicket={m.noContextFound}
            />
          ),
        )}

        {pending && (
          <>
            <UserBubble text={pending.question} />
            {pending.phase === 'searching' && <SearchingBubble />}
            {pending.phase === 'answering' && (
              <AssistantBubble
                text={pending.text}
                citations={pending.citations}
                isStreaming
                isRefusal={pending.noContextFound}
              />
            )}
            {pending.phase === 'error' && (
              <li className="flex justify-start">
                <div
                  role="alert"
                  className="max-w-[92%] rounded-lg rounded-bl-sm border border-red-200
                             bg-red-50 px-3.5 py-2.5 sm:max-w-[80%]"
                >
                  <p className="text-sm text-red-800">{pending.errorMessage}</p>
                  <div className="mt-2.5 flex gap-2">
                    {pending.canCreateTicket && (
                      <a
                        href="/tickets/new"
                        className="rounded-md bg-red-700 px-3 py-1.5 text-xs font-medium
                                   text-white hover:bg-red-800"
                      >
                        Tạo yêu cầu hỗ trợ
                      </a>
                    )}
                    <Button variant="secondary" onClick={onDismissError} className="text-xs">
                      Bỏ qua
                    </Button>
                  </div>
                </div>
              </li>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </ul>
    </div>
  )
}
