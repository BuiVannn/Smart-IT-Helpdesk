/**
 * Mock API theo đúng hợp đồng ở docs/design/06-api-design.md.
 *
 * ★ ĐÂY LÀ THỨ GỠ CHẶN CHO FRONTEND: code được toàn bộ màn hình trước khi
 * backend xong. Khi backend sẵn sàng, đặt VITE_USE_MOCK=false là xong.
 *
 * ★ MOCK CÓ TRẠNG THÁI (biến `db` bên dưới) chứ không trả hằng số cứng.
 * Mock trả hằng số thì bấm "Nhận xử lý" xong danh sách vẫn y nguyên, và ta
 * chỉ phát hiện luồng bị hỏng khi nối vào backend thật.
 *
 * ★ Hình dạng response ở đây PHẢI khớp backend. Sai một tên field là frontend
 * chạy ngon với mock rồi vỡ khi nối thật — đúng lúc sắp demo.
 */

import { HttpResponse, http } from 'msw'
import type {
  AllowedTransitions,
  CurrentUser,
  Page,
  QueueStats,
  Ticket,
  TicketComment,
  TicketEvent,
  TicketListItem,
  TicketStatus,
  UserBrief,
} from '@/types'

const BASE = '/api/v1'

const EMPLOYEE: CurrentUser = {
  id: '018f9c2e-0000-7000-8000-000000000001',
  email: 'employee1@company.com',
  fullName: 'Lê Văn Nhân Viên',
  role: 'EMPLOYEE',
  isActive: true,
  createdAt: new Date(Date.now() - 90 * 86400_000).toISOString(),
}

const AGENT: CurrentUser = {
  id: '018f9c2e-0000-7000-8000-000000000002',
  email: 'agent1@company.com',
  fullName: 'Nguyễn Văn Kỹ Thuật',
  role: 'IT_AGENT',
  isActive: true,
  createdAt: new Date(Date.now() - 200 * 86400_000).toISOString(),
}

function brief(user: CurrentUser): UserBrief {
  return { id: user.id, fullName: user.fullName, role: user.role }
}

/** Máy trạng thái rút gọn — bản đầy đủ nằm ở backend (state_machine.py). */
const TRANSITIONS: Record<TicketStatus, TicketStatus[]> = {
  NEW: ['ASSIGNED', 'CANCELLED'],
  ASSIGNED: ['IN_PROGRESS', 'CANCELLED'],
  IN_PROGRESS: ['PENDING_REQUESTER', 'RESOLVED'],
  PENDING_REQUESTER: ['IN_PROGRESS', 'RESOLVED'],
  RESOLVED: ['IN_PROGRESS', 'CLOSED'],
  CLOSED: [],
  CANCELLED: [],
}

/* ── Trạng thái trong bộ nhớ ─────────────────────────────────────── */

let currentUser: CurrentUser = EMPLOYEE
let sequence = 143

const db = {
  tickets: [] as Ticket[],
  comments: {} as Record<string, TicketComment[]>,
  events: {} as Record<string, TicketEvent[]>,
}

function nextId(prefix: string): string {
  return `${prefix}-${Math.random().toString(16).slice(2, 10)}`
}

function seedTicket(partial: Partial<Ticket> & Pick<Ticket, 'title' | 'description'>): Ticket {
  const now = new Date()
  const ticket: Ticket = {
    id: nextId('tk'),
    code: `HD-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}-${String(
      sequence++,
    ).padStart(5, '0')}`,
    status: 'NEW',
    priority: 'MEDIUM',
    aiStatus: 'APPLIED',
    requester: brief(EMPLOYEE),
    assignee: null,
    category: null,
    slaState: 'ON_TRACK',
    slaResolutionDueAt: new Date(Date.now() + 8 * 3600_000).toISOString(),
    slaResponseDueAt: new Date(Date.now() + 3600_000).toISOString(),
    firstResponseAt: null,
    resolvedAt: null,
    closedAt: null,
    resolutionNote: null,
    source: 'WEB',
    createdAt: now.toISOString(),
    updatedAt: now.toISOString(),
    version: 1,
    ...partial,
  }
  db.tickets.push(ticket)
  db.comments[ticket.id] = []
  db.events[ticket.id] = [
    {
      id: nextId('ev'),
      eventType: 'CREATED',
      actor: ticket.requester,
      fieldName: null,
      oldValue: null,
      newValue: ticket.code,
      createdAt: ticket.createdAt,
    },
  ]
  return ticket
}

seedTicket({
  title: 'Không kết nối được WiFi công ty tại tầng 5',
  description: 'Từ sáng nay máy tôi không thấy mạng CTY-WIFI trong danh sách khả dụng.',
  status: 'IN_PROGRESS',
  priority: 'URGENT',
  assignee: brief(AGENT),
  category: { id: 'c1', slug: 'network', name: 'Mạng & Internet' },
  slaState: 'AT_RISK',
  slaResolutionDueAt: new Date(Date.now() + 45 * 60_000).toISOString(),
  version: 3,
})
seedTicket({
  title: 'Yêu cầu cấp quyền truy cập thư mục Dự án X',
  description: 'Tôi cần quyền đọc ghi vào thư mục chung của dự án X trên file server.',
  category: { id: 'c2', slug: 'access', name: 'Cấp quyền truy cập' },
})
seedTicket({
  title: 'Máy in tầng 3 bị kẹt giấy liên tục',
  description: 'Máy in HP tầng 3 kẹt giấy mỗi lần in quá 5 trang, đã thử gỡ giấy nhưng vẫn lỗi.',
  status: 'CLOSED',
  assignee: brief(AGENT),
  category: { id: 'c3', slug: 'hardware', name: 'Phần cứng & Thiết bị' },
  slaState: 'MET',
  resolvedAt: new Date(Date.now() - 22 * 3600_000).toISOString(),
  closedAt: new Date(Date.now() - 20 * 3600_000).toISOString(),
  resolutionNote: 'Đã thay trục cuốn giấy và vệ sinh khay nạp.',
  version: 6,
})

/* ── Tiện ích ────────────────────────────────────────────────────── */

function toListItem(t: Ticket): TicketListItem {
  const { description: _d, source: _s, resolutionNote: _r, ...rest } = t
  return rest
}

function paginate<T>(items: T[], page: number, pageSize: number): Page<T> {
  const start = (page - 1) * pageSize
  return {
    data: items.slice(start, start + pageSize),
    pagination: {
      page,
      pageSize,
      totalItems: items.length,
      totalPages: Math.max(1, Math.ceil(items.length / pageSize)),
    },
  }
}

function error(code: string, message: string, status: number, details?: unknown) {
  return HttpResponse.json(
    { error: { code, message, requestId: 'mock-request-id', details } },
    { status },
  )
}

/** Bắt chước bộ lọc quyền của backend: nhân viên chỉ thấy ticket của mình. */
function visible(t: Ticket): boolean {
  if (currentUser.role === 'EMPLOYEE') return t.requester.id === currentUser.id
  return true
}

function findVisible(id: string): Ticket | undefined {
  return db.tickets.find((t) => t.id === id && visible(t))
}

function record(ticket: Ticket, event: Omit<TicketEvent, 'id' | 'createdAt' | 'actor'>) {
  db.events[ticket.id].push({
    ...event,
    id: nextId('ev'),
    actor: brief(currentUser),
    createdAt: new Date().toISOString(),
  })
}

function touch(ticket: Ticket) {
  ticket.version += 1
  ticket.updatedAt = new Date().toISOString()
}

/* ── Handler ─────────────────────────────────────────────────────── */

export const handlers = [
  http.post(`${BASE}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string }
    if (!body.email || !body.password) {
      return error('INVALID_CREDENTIALS', 'Email hoặc mật khẩu không đúng', 401)
    }
    // Đăng nhập bằng email chứa "agent" để thử vai IT Agent
    currentUser = body.email.includes('agent') ? AGENT : EMPLOYEE
    return HttpResponse.json({
      accessToken: 'mock-access-token',
      tokenType: 'Bearer',
      expiresIn: 900,
      user: currentUser,
    })
  }),

  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({
      accessToken: 'mock-access-token',
      tokenType: 'Bearer',
      expiresIn: 900,
      user: currentUser,
    }),
  ),

  http.post(`${BASE}/auth/logout`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${BASE}/users/me`, () => HttpResponse.json(currentUser)),

  http.get(`${BASE}/tickets`, ({ request }) => {
    const url = new URL(request.url)
    const page = Number(url.searchParams.get('page') ?? 1)
    const pageSize = Number(url.searchParams.get('pageSize') ?? 20)
    const statuses = url.searchParams.getAll('status')
    const q = (url.searchParams.get('q') ?? '').trim().toLowerCase()
    const mine = url.searchParams.get('mine') === 'true'
    const unassigned = url.searchParams.get('unassigned') === 'true'

    let rows = db.tickets.filter(visible)
    if (statuses.length) rows = rows.filter((t) => statuses.includes(t.status))
    if (mine) rows = rows.filter((t) => t.assignee?.id === currentUser.id)
    if (unassigned) rows = rows.filter((t) => t.assignee === null)
    if (q) {
      rows = rows.filter(
        (t) =>
          t.title.toLowerCase().includes(q) || t.description.toLowerCase().includes(q),
      )
    }
    rows = [...rows].sort((a, b) => b.createdAt.localeCompare(a.createdAt))

    return HttpResponse.json(paginate(rows.map(toListItem), page, pageSize))
  }),

  http.get(`${BASE}/tickets/stats/queue`, () => {
    if (currentUser.role === 'EMPLOYEE') {
      return error('FORBIDDEN', 'Chỉ IT Agent và Admin xem được hàng chờ', 403)
    }
    const open = db.tickets.filter(
      (t) => !['RESOLVED', 'CLOSED', 'CANCELLED'].includes(t.status),
    )
    const mine = open.filter((t) => t.assignee?.id === currentUser.id)
    const stats: QueueStats = {
      unassigned: open.filter((t) => t.assignee === null).length,
      assignedToMe: mine.length,
      inProgress: mine.filter((t) => t.status === 'IN_PROGRESS').length,
      atRisk: mine.filter((t) => t.slaState === 'AT_RISK').length,
      breached: mine.filter((t) => t.slaState === 'BREACHED').length,
    }
    return HttpResponse.json(stats)
  }),

  http.post(`${BASE}/tickets`, async ({ request }) => {
    const body = (await request.json()) as {
      title: string
      description: string
      priority?: string | null
    }
    if (!body.title || body.title.trim().length < 5) {
      return error('VALIDATION_ERROR', 'Dữ liệu không hợp lệ', 422, [
        { field: 'title', message: 'Tiêu đề phải từ 5 ký tự' },
      ])
    }
    const ticket = seedTicket({
      title: body.title,
      description: body.description,
      priority: (body.priority as Ticket['priority']) || 'MEDIUM',
      requester: brief(currentUser),
      aiStatus: 'PENDING',   // phân loại chạy nền, sẽ có kết quả sau
      category: null,
    })
    return HttpResponse.json(ticket, { status: 201 })
  }),

  http.get(`${BASE}/tickets/:id`, ({ params }) => {
    const ticket = findVisible(params.id as string)
    // 404 chứ không phải 403 — không xác nhận sự tồn tại của ticket người khác
    if (!ticket) return error('NOT_FOUND', 'Không tìm thấy ticket', 404)
    return HttpResponse.json(ticket)
  }),

  http.get(`${BASE}/tickets/:id/allowed-transitions`, ({ params }) => {
    const ticket = findVisible(params.id as string)
    if (!ticket) return error('NOT_FOUND', 'Không tìm thấy ticket', 404)

    let allowed = TRANSITIONS[ticket.status]
    if (currentUser.role === 'EMPLOYEE') {
      // Nhân viên chỉ được huỷ ticket của mình và đóng ticket đã xử lý xong
      allowed = allowed.filter((s) => s === 'CANCELLED' || s === 'CLOSED')
    }
    const body: AllowedTransitions = {
      currentStatus: ticket.status,
      allowedStatuses: allowed,
      version: ticket.version,
    }
    return HttpResponse.json(body)
  }),

  http.post(`${BASE}/tickets/:id/claim`, async ({ params, request }) => {
    const ticket = findVisible(params.id as string)
    if (!ticket) return error('NOT_FOUND', 'Không tìm thấy ticket', 404)

    const { version } = (await request.json()) as { version: number }
    if (version !== ticket.version) {
      return error('CONFLICT', 'Ticket đã được người khác cập nhật. Vui lòng tải lại.', 409, {
        currentVersion: ticket.version,
      })
    }
    if (ticket.assignee) {
      return error('CONFLICT', 'Ticket đã có người nhận', 409, {
        assigneeId: ticket.assignee.id,
      })
    }

    ticket.assignee = brief(currentUser)
    ticket.status = 'ASSIGNED'
    record(ticket, {
      eventType: 'ASSIGNED', fieldName: 'assignee_id',
      oldValue: null, newValue: currentUser.id,
    })
    touch(ticket)
    return HttpResponse.json(ticket)
  }),

  http.post(`${BASE}/tickets/:id/status`, async ({ params, request }) => {
    const ticket = findVisible(params.id as string)
    if (!ticket) return error('NOT_FOUND', 'Không tìm thấy ticket', 404)

    const body = (await request.json()) as {
      status: TicketStatus
      resolutionNote?: string
      version: number
    }

    if (body.version !== ticket.version) {
      return error('CONFLICT', 'Ticket đã được người khác cập nhật. Vui lòng tải lại.', 409, {
        currentVersion: ticket.version,
      })
    }
    if (!TRANSITIONS[ticket.status].includes(body.status)) {
      return error(
        'INVALID_STATUS_TRANSITION',
        `Không thể chuyển từ ${ticket.status} sang ${body.status}`,
        422,
        { currentStatus: ticket.status, allowedStatuses: TRANSITIONS[ticket.status] },
      )
    }
    if (body.status === 'RESOLVED' && (body.resolutionNote ?? '').trim().length < 10) {
      return error('INVALID_STATUS_TRANSITION', 'Phải nhập ghi chú xử lý ít nhất 10 ký tự', 422)
    }

    const old = ticket.status
    ticket.status = body.status
    if (body.resolutionNote) ticket.resolutionNote = body.resolutionNote
    if (body.status === 'RESOLVED') {
      ticket.resolvedAt = new Date().toISOString()
      ticket.slaState = 'MET'
    }
    if (body.status === 'CLOSED') ticket.closedAt = new Date().toISOString()

    record(ticket, {
      eventType: 'STATUS_CHANGED', fieldName: 'status', oldValue: old, newValue: body.status,
    })
    touch(ticket)
    return HttpResponse.json(ticket)
  }),

  http.get(`${BASE}/tickets/:id/comments`, ({ params }) => {
    const ticket = findVisible(params.id as string)
    if (!ticket) return error('NOT_FOUND', 'Không tìm thấy ticket', 404)

    const all = db.comments[ticket.id] ?? []
    // Nhân viên KHÔNG thấy bình luận nội bộ — lọc ở đây để mock phản ánh
    // đúng hành vi backend, nếu không lỗi rò rỉ chỉ lộ ra khi nối thật.
    const rows = currentUser.role === 'EMPLOYEE' ? all.filter((c) => !c.isInternal) : all
    return HttpResponse.json(rows)
  }),

  http.post(`${BASE}/tickets/:id/comments`, async ({ params, request }) => {
    const ticket = findVisible(params.id as string)
    if (!ticket) return error('NOT_FOUND', 'Không tìm thấy ticket', 404)

    const body = (await request.json()) as { body: string; isInternal?: boolean }
    const comment: TicketComment = {
      id: nextId('cm'),
      body: body.body,
      // Nhân viên gửi isInternal=true thì BỎ QUA, không báo lỗi (BR-10)
      isInternal: Boolean(body.isInternal) && currentUser.role !== 'EMPLOYEE',
      author: brief(currentUser),
      createdAt: new Date().toISOString(),
      editedAt: null,
    }
    db.comments[ticket.id].push(comment)
    record(ticket, {
      eventType: 'COMMENTED', fieldName: null, oldValue: null, newValue: null,
    })
    return HttpResponse.json(comment, { status: 201 })
  }),

  http.get(`${BASE}/tickets/:id/events`, ({ params }) => {
    const ticket = findVisible(params.id as string)
    if (!ticket) return error('NOT_FOUND', 'Không tìm thấy ticket', 404)
    return HttpResponse.json(db.events[ticket.id] ?? [])
  }),

  http.get(`${BASE}/notifications/unread-count`, () => HttpResponse.json({ count: 3 })),
]
