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

/** Người dùng khi xuất hiện lồng trong tài nguyên khác.
 *  KHÔNG có email — danh sách ticket không phải chỗ lộ email toàn công ty. */
export interface UserBrief {
  id: string
  fullName: string
  role: UserRole
  avatarUrl?: string | null
}

/** Thông tin đầy đủ, chỉ trả cho chính chủ hoặc Admin (GET /users/me). */
export interface CurrentUser extends UserBrief {
  email: string
  department?: { id: string; code: string; name: string } | null
  isActive: boolean
  createdAt: string
}

export interface Category {
  id: string
  slug: string
  name: string
}

/** Bản rút gọn dùng cho danh sách — KHÔNG có `description`. */
export interface TicketListItem {
  id: string
  code: string
  title: string
  status: TicketStatus
  priority: TicketPriority
  aiStatus: AiStatus
  requester: UserBrief
  assignee: UserBrief | null
  category: Category | null
  slaState: SlaState | null
  slaResolutionDueAt: string | null
  createdAt: string
  updatedAt: string
  version: number
}

export interface Ticket extends TicketListItem {
  description: string
  source: 'WEB' | 'CHATBOT' | 'API'
  resolutionNote: string | null
  slaResponseDueAt: string | null
  firstResponseAt: string | null
  resolvedAt: string | null
  closedAt: string | null
}

export interface TicketComment {
  id: string
  body: string
  isInternal: boolean
  author: UserBrief
  createdAt: string
  editedAt: string | null
}

export type TicketEventType =
  | 'CREATED' | 'ASSIGNED' | 'UNASSIGNED' | 'STATUS_CHANGED' | 'PRIORITY_CHANGED'
  | 'RECLASSIFIED' | 'COMMENTED' | 'ATTACHMENT_ADDED' | 'AI_CLASSIFIED'
  | 'SLA_WARNED' | 'SLA_BREACHED' | 'RATED' | 'REOPENED' | 'AUTO_CLOSED'

export interface TicketEvent {
  id: string
  eventType: TicketEventType
  actor: UserBrief | null
  fieldName: string | null
  oldValue: string | null
  newValue: string | null
  createdAt: string
}

export interface AllowedTransitions {
  currentStatus: TicketStatus
  allowedStatuses: TicketStatus[]
  version: number
}

export interface QueueStats {
  unassigned: number
  assignedToMe: number
  inProgress: number
  atRisk: number
  breached: number
}

/* ── Trợ lý ảo (F4) ──────────────────────────────────────────────── */

export interface Citation {
  articleId: string
  title: string
  slug: string
  score: number
  rank: number
}

export interface ChatSession {
  id: string
  title: string | null
  messageCount: number
  ledToTicket: boolean
  createdAt: string
  lastMessageAt: string | null
}

export interface ChatMessage {
  id: string
  role: 'USER' | 'ASSISTANT' | 'SYSTEM'
  content: string
  noContextFound: boolean
  citations: Citation[]
  latencyMs: number | null
  createdAt: string
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[]
}

/**
 * Sự kiện trong luồng SSE. Backend cam kết thứ tự:
 *   citations → token* → done   |   hoặc error rồi dừng
 */
export type ChatEvent =
  | { type: 'citations'; data: { citations: Citation[] } }
  | { type: 'token'; data: { delta: string } }
  | {
      type: 'done'
      data: {
        messageId: string
        noContextFound: boolean
        canCreateTicket?: boolean
        latencyMs: number
        promptVersion?: string
      }
    }
  | {
      type: 'error'
      data: { code: string; message: string; canCreateTicket?: boolean }
    }

export interface CreateTicketInput {
  title: string
  description: string
  categoryId?: string | null
  priority?: TicketPriority | null
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
