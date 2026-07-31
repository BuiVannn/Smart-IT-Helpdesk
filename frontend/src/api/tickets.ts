/**
 * Lời gọi API ticket. Tầng này CHỈ dịch tham số sang HTTP — không có state,
 * không có logic hiển thị. React Query lo cache và trạng thái tải.
 *
 * ★ MỌI thao tác thay đổi ticket đều gửi kèm `version` (khoá lạc quan).
 * Thiếu nó, hai người cùng sửa một ticket sẽ ghi đè nhau trong im lặng.
 */

import { api } from '@/api/client'
import type {
  AllowedTransitions,
  CreateTicketInput,
  Page,
  QueueStats,
  Ticket,
  TicketComment,
  TicketEvent,
  TicketListItem,
  TicketPriority,
  TicketStatus,
} from '@/types'

export interface TicketListParams {
  page?: number
  pageSize?: number
  status?: TicketStatus[]
  priority?: TicketPriority[]
  mine?: boolean
  unassigned?: boolean
  q?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

function toQuery(params: TicketListParams): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    // status và priority là danh sách: lặp lại tham số thay vì nối bằng dấu
    // phẩy, vì FastAPI đọc `?status=NEW&status=ASSIGNED`.
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)))
    else search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export const ticketsApi = {
  list: (params: TicketListParams = {}) =>
    api.get<Page<TicketListItem>>(`/tickets${toQuery(params)}`),

  get: (id: string) => api.get<Ticket>(`/tickets/${id}`),

  create: (input: CreateTicketInput) => api.post<Ticket>('/tickets', input),

  queueStats: () => api.get<QueueStats>('/tickets/stats/queue'),

  allowedTransitions: (id: string) =>
    api.get<AllowedTransitions>(`/tickets/${id}/allowed-transitions`),

  claim: (id: string, version: number) =>
    api.post<Ticket>(`/tickets/${id}/claim`, { version }),

  assign: (id: string, assigneeId: string, version: number) =>
    api.post<Ticket>(`/tickets/${id}/assign`, { assigneeId, version }),

  changeStatus: (
    id: string,
    input: { status: TicketStatus; resolutionNote?: string; version: number },
  ) => api.post<Ticket>(`/tickets/${id}/status`, input),

  comments: (id: string) => api.get<TicketComment[]>(`/tickets/${id}/comments`),

  addComment: (id: string, body: string, isInternal = false) =>
    api.post<TicketComment>(`/tickets/${id}/comments`, { body, isInternal }),

  events: (id: string) => api.get<TicketEvent[]>(`/tickets/${id}/events`),
}
