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
  ChatMessage,
  ChatSession,
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
  sessions: [] as ChatSession[],
  chatMessages: {} as Record<string, ChatMessage[]>,
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/** Y HỆT chuỗi ở backend (chatbot/prompts.py). Lệch nhau thì giao diện được
 *  thử với một câu từ chối khác câu thật, và ta không kiểm được cách nó hiển thị. */
const NO_CONTEXT_ANSWER =
  'Tôi chưa tìm thấy hướng dẫn cho vấn đề này trong kho tài liệu nội bộ.\n\n' +
  'Bạn có thể tạo một yêu cầu hỗ trợ để đội IT xử lý trực tiếp — ' +
  'đội IT thường phản hồi trong vòng vài giờ làm việc.'

/** Vài câu trả lời mẫu bám theo bài viết CÓ THẬT trong seeds/kb/. */
const KB_ANSWERS = [
  {
    keywords: ['mật khẩu email', 'đổi mật khẩu', 'mat khau'],
    answer:
      'Bạn đổi mật khẩu email công ty theo các bước sau:\n\n' +
      '1. Truy cập cổng tự phục vụ của công ty và đăng nhập bằng tài khoản hiện tại.\n' +
      '2. Chọn mục "Đổi mật khẩu".\n' +
      '3. Nhập mật khẩu cũ, rồi nhập mật khẩu mới hai lần.\n' +
      '4. Mật khẩu mới phải dài tối thiểu 12 ký tự, có chữ hoa, chữ thường và số.\n\n' +
      'Lưu ý: đội IT không bao giờ hỏi mật khẩu của bạn qua email hay điện thoại.',
    citations: [
      { articleId: 'a1', title: 'Hướng dẫn đổi mật khẩu email công ty',
        slug: 'doi-mat-khau-email', score: 0.87, rank: 1 },
      { articleId: 'a2', title: 'Chính sách mật khẩu công ty',
        slug: 'chinh-sach-mat-khau', score: 0.71, rank: 2 },
    ],
  },
  {
    keywords: ['wifi', 'mạng', 'internet'],
    answer:
      'Để kết nối WiFi công ty:\n\n' +
      '1. Bật WiFi và chọn mạng CTY-WIFI trong danh sách.\n' +
      '2. Nhập tài khoản domain của bạn (không phải email cá nhân).\n' +
      '3. Chấp nhận chứng chỉ bảo mật khi được hỏi.\n\n' +
      'Nếu không thấy tên mạng, hãy thử tắt/bật lại WiFi hoặc khởi động lại máy.',
    citations: [
      { articleId: 'a3', title: 'Hướng dẫn kết nối WiFi công ty',
        slug: 'ket-noi-wifi', score: 0.84, rank: 1 },
      { articleId: 'a4', title: 'Khắc phục khi mất kết nối mạng',
        slug: 'mat-ket-noi-mang', score: 0.66, rank: 2 },
    ],
  },
  {
    keywords: ['chậm', 'cham', 'lag'],
    answer:
      'Máy tính chạy chậm, bạn có thể tự kiểm tra vài bước trước:\n\n' +
      '1. Mở Task Manager xem ứng dụng nào chiếm nhiều CPU hoặc RAM.\n' +
      '2. Kiểm tra ổ đĩa còn trống ít nhất 15% dung lượng.\n' +
      '3. Khởi động lại máy — nhiều sự cố hết sau bước này.\n' +
      '4. Gỡ các phần mềm tự khởi động mà bạn không dùng.',
    citations: [
      { articleId: 'a5', title: 'Máy tính chạy chậm — cách tự kiểm tra',
        slug: 'may-tinh-cham', score: 0.79, rank: 1 },
    ],
  },
  {
    keywords: ['lừa đảo', 'lua dao', 'phishing', 'email lạ'],
    answer:
      'Dấu hiệu nhận biết email lừa đảo:\n\n' +
      '1. Địa chỉ người gửi gần giống nhưng không đúng tên miền công ty.\n' +
      '2. Nội dung tạo cảm giác gấp gáp: "tài khoản sẽ bị khoá trong 24 giờ".\n' +
      '3. Yêu cầu bạn nhập mật khẩu qua một đường dẫn lạ.\n\n' +
      'Nếu nghi ngờ: KHÔNG bấm vào liên kết, không trả lời, và báo ngay cho đội IT.',
    citations: [
      { articleId: 'a6', title: 'Nhận diện và xử lý email lừa đảo',
        slug: 'email-lua-dao', score: 0.91, rank: 1 },
    ],
  },
]

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

  /* ── Trợ lý ảo ─────────────────────────────────────────────── */

  http.post(`${BASE}/chat/sessions`, async ({ request }) => {
    const body = (await request.json()) as { title?: string | null }
    const session: ChatSession = {
      id: nextId('cs'),
      title: body.title ?? null,
      messageCount: 0,
      ledToTicket: false,
      createdAt: new Date().toISOString(),
      lastMessageAt: null,
    }
    db.sessions.unshift(session)
    db.chatMessages[session.id] = []
    return HttpResponse.json(session, { status: 201 })
  }),

  http.get(`${BASE}/chat/sessions`, ({ request }) => {
    const url = new URL(request.url)
    return HttpResponse.json(
      paginate(db.sessions, Number(url.searchParams.get('page') ?? 1), 30),
    )
  }),

  http.get(`${BASE}/chat/sessions/:id`, ({ params }) => {
    const session = db.sessions.find((s) => s.id === params.id)
    if (!session) return error('NOT_FOUND', 'Không tìm thấy cuộc trò chuyện', 404)
    return HttpResponse.json({ ...session, messages: db.chatMessages[session.id] ?? [] })
  }),

  http.get(`${BASE}/chat/config`, () =>
    HttpResponse.json({
      maxQuestionLength: 1000,
      rateLimitPerWindow: 30,
      rateLimitWindowSeconds: 300,
      model: 'fake',
    }),
  ),

  /**
   * Luồng SSE giả lập.
   *
   * ★ Phát token CHẬM DẦN theo từng mẩu chứ không trả một cục: chỉ khi chữ
   * thực sự chảy ra ta mới thấy được lỗi tự cuộn, lỗi con trỏ nhấp nháy, hay
   * lỗi tách khung SSE. Mock trả một lần thì mọi thứ trông hoàn hảo cho tới
   * lúc nối backend thật.
   */
  http.post(`${BASE}/chat/sessions/:id/messages`, async ({ params, request }) => {
    const session = db.sessions.find((s) => s.id === params.id)
    if (!session) return error('NOT_FOUND', 'Không tìm thấy cuộc trò chuyện', 404)

    const { question } = (await request.json()) as { question: string }
    const known = KB_ANSWERS.find((a) =>
      a.keywords.some((k) => question.toLowerCase().includes(k)),
    )

    const messages = db.chatMessages[session.id]
    messages.push({
      id: nextId('msg'), role: 'USER', content: question,
      noContextFound: false, citations: [], latencyMs: null,
      createdAt: new Date().toISOString(),
    })

    const answer = known?.answer ?? NO_CONTEXT_ANSWER
    const citations = known?.citations ?? []

    const stream = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder()
        const frame = (event: string, data: unknown) =>
          controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`))

        await sleep(400)                       // thời gian "tra cứu tài liệu"
        frame('citations', { citations })

        for (const piece of answer.match(/\S+\s*/g) ?? []) {
          await sleep(28)
          frame('token', { delta: piece })
        }

        const saved = {
          id: nextId('msg'), role: 'ASSISTANT' as const, content: answer,
          noContextFound: !known, citations, latencyMs: 1200,
          createdAt: new Date().toISOString(),
        }
        messages.push(saved)
        session.messageCount = messages.length
        session.lastMessageAt = saved.createdAt
        if (!session.title) session.title = question.slice(0, 60)

        frame('done', {
          messageId: saved.id,
          noContextFound: !known,
          canCreateTicket: !known,
          latencyMs: 1200,
        })
        controller.close()
      },
    })

    return new HttpResponse(stream, {
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
    })
  }),

  http.get(`${BASE}/notifications/unread-count`, () => HttpResponse.json({ count: 3 })),
]
