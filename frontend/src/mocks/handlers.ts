/**
 * Mock API theo đúng hợp đồng ở docs/design/06-api-design.md.
 *
 * ★ ĐÂY LÀ THỨ GỠ CHẶN CHO FRONTEND: 2 FE dev code được toàn bộ màn hình
 * trước khi backend xong. Khi backend sẵn sàng chỉ cần đặt VITE_USE_MOCK=false.
 *
 * CÁCH THÊM ENDPOINT MỚI: copy một http.get/http.post bên dưới, giữ đúng
 * hình dạng response như trong tài liệu 06 — sai hình dạng ở đây nghĩa là
 * frontend sẽ hỏng khi nối vào backend thật.
 */

import { HttpResponse, http } from 'msw'
import type { Page, Ticket, UserBrief } from '@/types'

const BASE = '/api/v1'

const MOCK_USER: UserBrief = {
  id: '018f9c2e-0000-7000-8000-000000000001',
  email: 'employee1@company.com',
  fullName: 'Lê Văn Nhân Viên',
  role: 'EMPLOYEE',
}

const MOCK_AGENT: UserBrief = {
  id: '018f9c2e-0000-7000-8000-000000000002',
  email: 'agent1@company.com',
  fullName: 'Nguyễn Văn Kỹ Thuật',
  role: 'IT_AGENT',
}

const MOCK_TICKETS: Ticket[] = [
  {
    id: '018f9c2e-0000-7000-8000-00000000t001',
    code: 'HD-202607-00142',
    title: 'Không kết nối được WiFi công ty tại tầng 5',
    description: 'Từ sáng nay máy tôi không thấy mạng CTY-WIFI trong danh sách khả dụng.',
    status: 'IN_PROGRESS',
    priority: 'URGENT',
    aiStatus: 'APPLIED',
    requester: MOCK_USER,
    assignee: MOCK_AGENT,
    category: { id: 'c1', slug: 'network', name: 'Mạng & Internet' },
    slaResolutionDueAt: new Date(Date.now() + 45 * 60_000).toISOString(),
    firstResponseAt: new Date(Date.now() - 30 * 60_000).toISOString(),
    resolvedAt: null,
    createdAt: new Date(Date.now() - 2 * 3600_000).toISOString(),
    updatedAt: new Date().toISOString(),
    version: 3,
  },
  {
    id: '018f9c2e-0000-7000-8000-00000000t002',
    code: 'HD-202607-00139',
    title: 'Yêu cầu cấp quyền truy cập thư mục Dự án X',
    description: 'Tôi cần quyền đọc ghi vào thư mục chung của dự án X trên file server.',
    status: 'ASSIGNED',
    priority: 'MEDIUM',
    aiStatus: 'APPLIED',
    requester: MOCK_USER,
    assignee: MOCK_AGENT,
    category: { id: 'c2', slug: 'access', name: 'Cấp quyền truy cập' },
    slaResolutionDueAt: new Date(Date.now() + 3 * 3600_000).toISOString(),
    firstResponseAt: null,
    resolvedAt: null,
    createdAt: new Date(Date.now() - 5 * 3600_000).toISOString(),
    updatedAt: new Date().toISOString(),
    version: 1,
  },
  {
    id: '018f9c2e-0000-7000-8000-00000000t003',
    code: 'HD-202607-00131',
    title: 'Máy in tầng 3 bị kẹt giấy liên tục',
    description: 'Máy in HP tầng 3 kẹt giấy mỗi lần in quá 5 trang, đã thử gỡ giấy nhưng vẫn lỗi.',
    status: 'CLOSED',
    priority: 'MEDIUM',
    aiStatus: 'APPLIED',
    requester: MOCK_USER,
    assignee: MOCK_AGENT,
    category: { id: 'c3', slug: 'hardware', name: 'Phần cứng & Thiết bị' },
    slaResolutionDueAt: new Date(Date.now() - 20 * 3600_000).toISOString(),
    firstResponseAt: new Date(Date.now() - 26 * 3600_000).toISOString(),
    resolvedAt: new Date(Date.now() - 22 * 3600_000).toISOString(),
    createdAt: new Date(Date.now() - 28 * 3600_000).toISOString(),
    updatedAt: new Date(Date.now() - 22 * 3600_000).toISOString(),
    version: 6,
  },
]

function paginate<T>(items: T[], page = 1, pageSize = 20): Page<T> {
  const start = (page - 1) * pageSize
  return {
    data: items.slice(start, start + pageSize),
    pagination: {
      page,
      pageSize,
      totalItems: items.length,
      totalPages: Math.ceil(items.length / pageSize),
    },
  }
}

export const handlers = [
  http.post(`${BASE}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string }
    if (!body.email || !body.password) {
      return HttpResponse.json(
        { error: { code: 'INVALID_CREDENTIALS', message: 'Email hoặc mật khẩu không đúng',
                   requestId: 'mock-request-id' } },
        { status: 401 },
      )
    }
    const user = body.email.includes('agent') ? MOCK_AGENT : MOCK_USER
    return HttpResponse.json({
      accessToken: 'mock-access-token',
      tokenType: 'Bearer',
      expiresIn: 900,
      user,
    })
  }),

  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ accessToken: 'mock-access-token', expiresIn: 900, user: MOCK_USER }),
  ),

  http.post(`${BASE}/auth/logout`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${BASE}/users/me`, () => HttpResponse.json(MOCK_USER)),

  http.get(`${BASE}/tickets`, ({ request }) => {
    const url = new URL(request.url)
    const page = Number(url.searchParams.get('page') ?? 1)
    const pageSize = Number(url.searchParams.get('pageSize') ?? 20)
    const statuses = url.searchParams.getAll('status')
    const filtered = statuses.length
      ? MOCK_TICKETS.filter((t) => statuses.includes(t.status))
      : MOCK_TICKETS
    return HttpResponse.json(paginate(filtered, page, pageSize))
  }),

  http.get(`${BASE}/tickets/:id`, ({ params }) => {
    const ticket = MOCK_TICKETS.find((t) => t.id === params.id)
    if (!ticket) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Không tìm thấy yêu cầu',
                   requestId: 'mock-request-id' } },
        { status: 404 },
      )
    }
    return HttpResponse.json(ticket)
  }),

  http.post(`${BASE}/tickets`, async ({ request }) => {
    const body = (await request.json()) as { title: string; description: string }
    return HttpResponse.json(
      {
        ...MOCK_TICKETS[0],
        id: `mock-${Date.now()}`,
        code: `HD-202607-${String(Math.floor(Math.random() * 99999)).padStart(5, '0')}`,
        title: body.title,
        description: body.description,
        status: 'NEW',
        aiStatus: 'PENDING',   // ← phân loại AI chạy nền, chưa có kết quả
        assignee: null,
        category: null,
        version: 1,
      },
      { status: 201 },
    )
  }),

  http.get(`${BASE}/notifications/unread-count`, () => HttpResponse.json({ count: 3 })),
]
