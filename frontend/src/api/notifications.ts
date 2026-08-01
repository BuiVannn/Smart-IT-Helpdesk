import { api } from '@/api/client'
import type { AppNotification, Page } from '@/types'

export const notificationsApi = {
  list: (page = 1, unreadOnly = false) =>
    api.get<Page<AppNotification>>(
      `/notifications?page=${page}&pageSize=20&unreadOnly=${unreadOnly}`,
    ),

  /** Endpoint bị gọi 30 giây/lần cho mọi người đang online — giữ nó chỉ một số. */
  unreadCount: () => api.get<{ count: number }>('/notifications/unread-count'),

  markRead: (id: string) => api.post<{ updated: number }>(`/notifications/${id}/read`),

  markAllRead: () => api.post<{ updated: number }>('/notifications/read-all'),
}
