import { useQuery } from '@tanstack/react-query'
import { chatApi } from '@/api/chat'
import { Button, LoadingBlock } from '@/components/ui'
import { formatRelative } from '@/lib/utils'
import { chatKeys } from './useConversation'

export function SessionSidebar({
  activeId,
  onSelect,
  onNew,
  isCreating,
}: {
  activeId?: string
  onSelect: (id: string) => void
  onNew: () => void
  isCreating: boolean
}) {
  const sessions = useQuery({
    queryKey: chatKeys.sessions(),
    queryFn: () => chatApi.listSessions(1, 30),
  })

  return (
    <aside className="flex h-full w-full flex-col border-r border-slate-200 bg-slate-50">
      <div className="p-3">
        <Button onClick={onNew} loading={isCreating} className="w-full">
          Cuộc trò chuyện mới
        </Button>
      </div>

      <nav aria-label="Lịch sử trò chuyện" className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {sessions.isLoading ? (
          <LoadingBlock label="Đang tải…" />
        ) : sessions.data && sessions.data.data.length > 0 ? (
          <ul className="space-y-0.5">
            {sessions.data.data.map((s) => {
              const isActive = s.id === activeId
              return (
                <li key={s.id}>
                  <button
                    onClick={() => onSelect(s.id)}
                    aria-current={isActive ? 'true' : undefined}
                    className={`w-full rounded-md px-2.5 py-2 text-left text-sm transition
                      focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        isActive
                          ? 'bg-white font-medium text-slate-900 shadow-sm'
                          : 'text-slate-600 hover:bg-slate-100'
                      }`}
                  >
                    <span className="block truncate">
                      {s.title ?? 'Cuộc trò chuyện chưa đặt tên'}
                    </span>
                    <span className="mt-0.5 block text-[11px] text-slate-400">
                      {formatRelative(s.lastMessageAt ?? s.createdAt)}
                      {s.ledToTicket && ' · đã tạo ticket'}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="px-2.5 py-4 text-xs text-slate-500">
            Chưa có cuộc trò chuyện nào.
          </p>
        )}
      </nav>
    </aside>
  )
}
