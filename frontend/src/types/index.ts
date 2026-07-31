/**
 * Kiểu dữ liệu dùng chung.
 *
 * ⚠️ Sau khi backend xuất openapi.json (task T17), chạy `npm run gen:api`
 * để sinh types.gen.ts và dần thay thế file này. Khi đó đổi API mà quên
 * sửa frontend sẽ LỖI LÚC BIÊN DỊCH thay vì lỗi lúc chạy.
 */

export type UserRole = 'EMPLOYEE' | 'IT_AGENT' | 'ADMIN'

export type TicketStatus =
  | 'NEW' | 'ASSIGNED' | 'IN_PROGRESS' | 'PENDING_REQUESTER'
  | 'RESOLVED' | 'CLOSED' | 'CANCELLED'

export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'
export type SlaState = 'ON_TRACK' | 'AT_RISK' | 'BREACHED' | 'MET'
export type AiStatus = 'PENDING' | 'APPLIED' | 'LOW_CONFIDENCE' | 'SKIPPED' | 'FAILED'

export interface UserBrief {
  id: string
  email: string
  fullName: string
  role: UserRole
}

export interface Category {
  id: string
  slug: string
  name: string
}

export interface Ticket {
  id: string
  code: string
  title: string
  description: string
  status: TicketStatus
  priority: TicketPriority
  aiStatus: AiStatus
  requester: UserBrief
  assignee: UserBrief | null
  category: Category | null
  slaResolutionDueAt: string | null
  firstResponseAt: string | null
  resolvedAt: string | null
  createdAt: string
  updatedAt: string
  version: number
}

export interface PaginationMeta {
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}

export interface Page<T> {
  data: T[]
  pagination: PaginationMeta
}

/** Định dạng lỗi thống nhất — MỌI lỗi từ backend đều có hình dạng này */
export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: unknown
    requestId: string
  }
}
