import { api, tokenStore } from '@/api/client'
import type {
  AgentWorkloadReport,
  AiAccuracyReport,
  Overview,
  ResolutionTimeReport,
  SatisfactionReport,
} from '@/types'

/** Khoảng thời gian mặc định của dashboard: 30 ngày gần nhất (US-37). */
export function defaultRange(days = 30): { from: string; to: string } {
  const to = new Date()
  const from = new Date(to.getTime() - days * 24 * 60 * 60 * 1000)
  return { from: from.toISOString(), to: to.toISOString() }
}

function range(from: string, to: string): string {
  return `from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`
}

export const reportsApi = {
  overview: (from: string, to: string, refresh = false) =>
    api.get<Overview>(`/reports/overview?${range(from, to)}&refresh=${refresh}`),

  resolutionTime: (from: string, to: string) =>
    api.get<ResolutionTimeReport>(`/reports/resolution-time?${range(from, to)}`),

  agentWorkload: (from: string, to: string) =>
    api.get<AgentWorkloadReport>(`/reports/agent-workload?${range(from, to)}`),

  /** Báo cáo độ chính xác phân loại AI (US-22).
   *  Quyền: IT_AGENT và ADMIN. */
  aiAccuracy: (from: string, to: string) =>
    api.get<AiAccuracyReport>(`/reports/ai-accuracy?${range(from, to)}`),

  /** Tổng hợp điểm hài lòng theo Agent, loại sự cố, tháng (US-42).
   *  Quyền: ADMIN. */
  satisfaction: (from: string, to: string) =>
    api.get<SatisfactionReport>(`/reports/satisfaction?${range(from, to)}`),

  /**
   * Tải file CSV.
   *
   * Không dùng `api.get` được: hàm đó `res.json()` còn đây là văn bản thuần.
   * Cũng không đặt được `<a href>` thẳng vì tải file qua thẻ a không mang
   * theo Authorization header — endpoint này chỉ Admin gọi được nên request
   * sẽ nhận 401. Nên phải fetch có header rồi tạo blob URL.
   */
  async exportCsv(from: string, to: string): Promise<void> {
    const base = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
    const res = await fetch(`${base}/reports/tickets/export?${range(from, to)}`, {
      headers: { Authorization: `Bearer ${tokenStore.get() ?? ''}` },
      credentials: 'include',
    })
    if (!res.ok) throw new Error('Không xuất được báo cáo')

    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `tickets-${from.slice(0, 10)}-${to.slice(0, 10)}.csv`
    link.click()
    // Thu hồi ngay sau khi bấm, nếu không mỗi lần xuất giữ lại một bản sao
    // của file trong bộ nhớ tab cho tới khi tải lại trang.
    URL.revokeObjectURL(url)
  },
}
