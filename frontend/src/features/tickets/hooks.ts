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
}

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
