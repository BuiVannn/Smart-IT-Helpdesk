/**
 * React Query hook cho ticket.
 *
 * ★ QUY TẮC LÀM MỚI CACHE: sau mỗi thao tác thay đổi, PHẢI invalidate cả
 * ticket đó lẫn danh sách và hàng chờ. Chỉ invalidate chi tiết thì danh sách
 * vẫn hiển thị trạng thái cũ, và người dùng tưởng thao tác của mình thất bại.
 *
 * ★ VÌ SAO KHÔNG DÙNG optimistic update: mọi thao tác đều có khoá lạc quan
 * (`version`). Vẽ trước kết quả rồi server trả 409 sẽ khiến giao diện nháy
 * qua lại giữa hai trạng thái — tệ hơn hẳn việc chờ 200 ms.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ticketsApi, type TicketListParams } from '@/api/tickets'
import type { CreateTicketInput, TicketStatus } from '@/types'

export const ticketKeys = {
  all: ['tickets'] as const,
  lists: () => [...ticketKeys.all, 'list'] as const,
  list: (params: TicketListParams) => [...ticketKeys.lists(), params] as const,
  details: () => [...ticketKeys.all, 'detail'] as const,
  detail: (id: string) => [...ticketKeys.details(), id] as const,
  comments: (id: string) => [...ticketKeys.detail(id), 'comments'] as const,
  events: (id: string) => [...ticketKeys.detail(id), 'events'] as const,
  transitions: (id: string) => [...ticketKeys.detail(id), 'transitions'] as const,
  queueStats: () => [...ticketKeys.all, 'queue-stats'] as const,
  aiClassification: (id: string) => [...ticketKeys.detail(id), 'ai'] as const,
  assigneeSuggestions: (id: string) => [...ticketKeys.detail(id), 'suggestions'] as const,
}

/** Nhịp hỏi lại khi AI còn đang phân loại (US-19: mục tiêu ≤ 30 giây). */
const AI_POLL_MS = 3_000

export function useTickets(params: TicketListParams) {
  return useQuery({
    queryKey: ticketKeys.list(params),
    queryFn: () => ticketsApi.list(params),
    // Giữ dữ liệu trang cũ trong lúc tải trang mới — bảng không bị nháy trắng
    placeholderData: (previous) => previous,
  })
}

export function useTicket(id: string | undefined) {
  return useQuery({
    queryKey: ticketKeys.detail(id!),
    queryFn: () => ticketsApi.get(id!),
    enabled: Boolean(id),
    // ★ Việc phân loại chạy ở worker, KHÔNG nằm trong response của
    // `POST /tickets`. Không hỏi lại thì người vừa gửi yêu cầu nhìn thấy
    // "Đang phân loại…" đứng im cho tới khi họ tự bấm F5 — trông y hệt một
    // tính năng hỏng. Ngừng hỏi ngay khi AI đã chốt, để không có trang nào
    // gọi API mỗi 3 giây suốt cả ngày.
    refetchInterval: (query) =>
      query.state.data?.aiStatus === 'PENDING' ? AI_POLL_MS : false,
  })
}

export function useTicketComments(id: string | undefined) {
  return useQuery({
    queryKey: ticketKeys.comments(id!),
    queryFn: () => ticketsApi.comments(id!),
    enabled: Boolean(id),
  })
}

export function useTicketEvents(id: string | undefined) {
  return useQuery({
    queryKey: ticketKeys.events(id!),
    queryFn: () => ticketsApi.events(id!),
    enabled: Boolean(id),
  })
}

export function useAllowedTransitions(id: string | undefined) {
  return useQuery({
    queryKey: ticketKeys.transitions(id!),
    queryFn: () => ticketsApi.allowedTransitions(id!),
    enabled: Boolean(id),
  })
}

export function useQueueStats(enabled: boolean) {
  return useQuery({
    queryKey: ticketKeys.queueStats(),
    queryFn: () => ticketsApi.queueStats(),
    enabled,
    refetchInterval: 60_000,
  })
}

// ─────────────── F3 — AI phân loại & gợi ý người xử lý ───────────────

/** Gợi ý phân loại của AI (US-19). Chỉ gọi khi người xem là Agent/Admin. */
export function useAiClassification(id: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ticketKeys.aiClassification(id!),
    queryFn: () => ticketsApi.aiClassification(id!),
    enabled: Boolean(id) && enabled,
    refetchInterval: (query) => (query.state.data === null ? AI_POLL_MS : false),
  })
}

/**
 * Top 3 người xử lý phù hợp (US-20).
 *
 * Chỉ gọi khi người dùng thật sự sắp giao việc — endpoint này quét tải của
 * toàn đội IT, không nên chạy mỗi lần ai đó mở một ticket.
 */
export function useAssigneeSuggestions(id: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ticketKeys.assigneeSuggestions(id!),
    queryFn: () => ticketsApi.assigneeSuggestions(id!),
    enabled: Boolean(id) && enabled,
    // Tải của Agent đổi liên tục; số liệu quá cũ dẫn tới giao sai người.
    staleTime: 30_000,
  })
}

export function useAssignTicket(id: string) {
  const invalidate = useInvalidateTicket()
  return useMutation({
    mutationFn: (input: { assigneeId: string; version: number }) =>
      ticketsApi.assign(id, input.assigneeId, input.version),
    onSuccess: () => invalidate(id),
  })
}

/**
 * Agent sửa lại loại sự cố AI đã gán (US-21).
 *
 * Bắt buộc invalidate cả `aiClassification`: backend vừa đánh dấu bản ghi đó
 * là `wasAccepted = false`, mà khối "AI đã gợi ý" trên màn hình đang hiển thị
 * chính giá trị ấy.
 */
export function useReclassify(id: string) {
  const queryClient = useQueryClient()
  const invalidate = useInvalidateTicket()
  return useMutation({
    mutationFn: (input: { categoryId: string; version: number }) =>
      ticketsApi.reclassify(id, input.categoryId, input.version),
    onSuccess: () => {
      invalidate(id)
      void queryClient.invalidateQueries({ queryKey: ticketKeys.aiClassification(id) })
    },
  })
}

/** Làm mới mọi thứ liên quan tới một ticket sau khi nó thay đổi. */
function useInvalidateTicket() {
  const queryClient = useQueryClient()
  return (id: string) => {
    void queryClient.invalidateQueries({ queryKey: ticketKeys.detail(id) })
    void queryClient.invalidateQueries({ queryKey: ticketKeys.lists() })
    void queryClient.invalidateQueries({ queryKey: ticketKeys.queueStats() })
  }
}

export function useCreateTicket() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateTicketInput) => ticketsApi.create(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ticketKeys.lists() })
      void queryClient.invalidateQueries({ queryKey: ticketKeys.queueStats() })
    },
  })
}

export function useClaimTicket(id: string) {
  const invalidate = useInvalidateTicket()
  return useMutation({
    mutationFn: (version: number) => ticketsApi.claim(id, version),
    onSuccess: () => invalidate(id),
  })
}

export function useChangeStatus(id: string) {
  const invalidate = useInvalidateTicket()
  return useMutation({
    mutationFn: (input: {
      status: TicketStatus
      resolutionNote?: string
      version: number
    }) => ticketsApi.changeStatus(id, input),
    onSuccess: () => invalidate(id),
  })
}

export function useAddComment(id: string) {
  const invalidate = useInvalidateTicket()
  return useMutation({
    mutationFn: (input: { body: string; isInternal: boolean }) =>
      ticketsApi.addComment(id, input.body, input.isInternal),
    onSuccess: () => invalidate(id),
  })
}
