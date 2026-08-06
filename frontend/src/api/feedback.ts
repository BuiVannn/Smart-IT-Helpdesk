import { api } from '@/api/client'
import type { AgentRatingItem, Page, TicketRating } from '@/types'

export const feedbackApi = {
  getRating: (ticketId: string) => api.get<TicketRating>(`/tickets/${ticketId}/rating`),

  createRating: (ticketId: string, score: number, comment?: string) =>
    api.post<TicketRating>(`/tickets/${ticketId}/rating`, { score, comment }),

  updateRating: (ticketId: string, score: number, comment?: string) =>
    api.patch<TicketRating>(`/tickets/${ticketId}/rating`, { score, comment }),

  /** Agent xem đánh giá về mình, ẩn danh người chấm (US-43). */
  listMyRatings: (page = 1) =>
    api.get<Page<AgentRatingItem>>(`/tickets/ratings/mine?page=${page}&pageSize=20`),
}
