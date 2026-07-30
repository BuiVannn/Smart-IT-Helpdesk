# 09 — Thiết kế Frontend (Wireframe, Component, State)

| | |
|---|---|
| Phiên bản | 1.0 (bản khung — FE team hoàn thiện chi tiết) |
| PIC | Nguyễn Văn Quang, Nguyễn Văn Dũng |
| Công nghệ | React 18 + TypeScript + Vite · TanStack Query · React Router · Tailwind CSS · shadcn/ui · Recharts |

> Tài liệu này định nghĩa **khung sườn và các quyết định không được tự ý đổi** (routing, state, hợp đồng với API, phân quyền hiển thị). Chi tiết pixel, màu sắc, và các component nhỏ do FE team quyết định và bổ sung vào tài liệu này.

---

## 1. Quyết định công nghệ

| Hạng mục | Chọn | Lý do |
|---|---|---|
| Framework | **React + Vite** (không dùng Next.js) | Backend đã là FastAPI, không cần SSR. SPA thuần đơn giản hơn, build nhanh hơn, deploy chỉ là file tĩnh sau Nginx |
| Ngôn ngữ | TypeScript, `strict: true` | Type sinh từ `openapi.json` ⇒ đổi API mà quên sửa FE sẽ lỗi lúc biên dịch |
| State máy chủ | **TanStack Query** | Cache, tự làm mới, trạng thái loading/error, polling — thay thế phần lớn nhu cầu Redux |
| State giao diện | `useState` + Context (chỉ cho auth và theme) | **Không dùng Redux.** Gần như toàn bộ state của ứng dụng này là state của máy chủ |
| Form | React Hook Form + Zod | Zod schema khớp với ràng buộc backend, hiển thị lỗi ngay |
| UI | Tailwind + shadcn/ui | Nhanh, nhất quán, không phải tự viết design system |
| Biểu đồ | Recharts | Đủ cho 6 biểu đồ của dashboard |
| Gọi API | `fetch` + wrapper mỏng (interceptor refresh token) | Không cần axios |

**Quy tắc phân định state:** dữ liệu đến từ API ⇒ TanStack Query. Dữ liệu chỉ tồn tại trên màn hình (modal đang mở, tab đang chọn, nội dung form đang gõ) ⇒ `useState`. Nếu định đưa dữ liệu API vào một store toàn cục, đó là dấu hiệu đang dùng sai công cụ.

---

## 2. Bản đồ route

```
/login                          Công khai
/register                       Công khai

/                               → chuyển hướng theo vai trò
                                  EMPLOYEE  → /my-tickets
                                  IT_AGENT  → /queue
                                  ADMIN     → /dashboard

── Nhân viên ────────────────────────────────────────────
/my-tickets                     Danh sách ticket của tôi
/my-tickets/new                 Tạo ticket (có gợi ý bài viết KB)
/tickets/:id                    Chi tiết ticket (dùng chung mọi vai trò, hiển thị theo quyền)
/chat                           Chatbot
/chat/:sessionId                Phiên chat cụ thể
/kb                             Kho tài liệu — tìm kiếm & duyệt
/kb/:slug                       Đọc bài viết

── IT Agent ─────────────────────────────────────────────
/queue                          Hàng chờ (Của tôi / Chưa giao / Tất cả)
/queue/triage                   Ticket AI chưa phân loại được
/chat/quality                   Câu hỏi chatbot trả lời kém (US-27)

── Admin ────────────────────────────────────────────────
/dashboard                      Dashboard & báo cáo
/admin/users                    Quản trị người dùng
/admin/kb                       Quản lý bài viết (soạn thảo, publish)
/admin/categories               Danh mục sự cố & chủ đề KB
/admin/ai-quality               Độ chính xác phân loại AI (US-22)

── Chung ────────────────────────────────────────────────
/notifications                  Danh sách thông báo
/profile                        Hồ sơ, đổi mật khẩu
```

**Bảo vệ route:** `<ProtectedRoute roles={['ADMIN']}>`. Nhưng lưu ý: **route guard chỉ là trải nghiệm người dùng, không phải bảo mật.** Bảo mật nằm ở backend. Frontend ẩn nút không phải để chặn, mà để không hiển thị thứ người dùng không dùng được.

---

## 3. Wireframe các màn hình chính

### 3.1 Tạo ticket — `/my-tickets/new`

```
┌──────────────────────────────────────────────────────────────────────┐
│  Smart IT Helpdesk        [🔍]      [🔔 3]  [Nguyễn Văn A ▾]         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ← Quay lại        Tạo yêu cầu hỗ trợ                                │
│                                                                      │
│  Tiêu đề *                                                           │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Không kết nối được WiFi công ty tại tầng 5                     │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Mô tả chi tiết *                                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Từ sáng nay máy tôi không thấy mạng CTY-WIFI trong danh sách…  │  │
│  │                                                                │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ╭─ 💡 Có thể bạn tự xử lý được ────────────────────────────────╮   │
│  │  • Hướng dẫn kết nối lại WiFi công ty                        │   │
│  │  • Xử lý khi không thấy tên mạng CTY-WIFI                    │   │
│  │                              [Bài viết này đã giải quyết ✓]  │   │
│  ╰──────────────────────────────────────────────────────────────╯   │
│      ↑ hiện sau khi gõ ≥ 30 ký tự, debounce 500 ms (US-32)          │
│                                                                      │
│  Loại sự cố            Mức ưu tiên                                   │
│  [ Để AI tự chọn ▾ ]   [ Bình thường ▾ ]                            │
│                                                                      │
│  Đính kèm  [📎 Chọn tệp]   ảnh-loi.png (245 KB) ✕                   │
│  Tối đa 5 tệp, mỗi tệp ≤ 10 MB                                      │
│                                                                      │
│  ⚠️ Không dán mật khẩu vào mô tả. Đội IT không bao giờ hỏi mật khẩu. │
│                                                                      │
│                                  [ Huỷ ]      [ Gửi yêu cầu ]        │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 Hàng chờ IT Agent — `/queue`

```
┌──────────────────────────────────────────────────────────────────────┐
│  [Của tôi (7)] [Chưa giao (12)] [Chờ phân loại (3)] [Tất cả]        │
│                                                                      │
│  Lọc: [Trạng thái ▾][Ưu tiên ▾][Loại ▾]   Sắp xếp: [SLA gần nhất ▾] │
├──────────────────────────────────────────────────────────────────────┤
│ 🔴 HD-202607-00142  Không kết nối được WiFi tầng 5                  │
│    Mạng · Nguyễn Văn A (Kế toán) · Đang xử lý                       │
│    ⏰ Còn 45 phút                                    [Xem] [Nhận]    │
├──────────────────────────────────────────────────────────────────────┤
│ 🟠 HD-202607-00139  Yêu cầu cấp quyền vào thư mục Dự án X           │
│    Cấp quyền · Trần Thị B (Kinh doanh) · Đã giao                    │
│    ⏰ Còn 3 giờ                                      [Xem]           │
├──────────────────────────────────────────────────────────────────────┤
│ ⚫ HD-202607-00131  Máy in tầng 3 kẹt giấy               ✅ ĐÃ ĐÓNG   │
│    Phần cứng · Đã giải quyết 2 giờ trước · ⭐⭐⭐⭐⭐                  │
└──────────────────────────────────────────────────────────────────────┘
       ‹ 1 2 3 ... 8 ›            Hiển thị 1–20 / 142
```

Chỉ báo SLA: 🔴 quá hạn hoặc còn < 25% · 🟠 sắp tới hạn · 🟢 còn nhiều thời gian · ⚫ đã đóng.

### 3.3 Chi tiết ticket — `/tickets/:id`

```
┌─────────────────────────────────────────────┬────────────────────────┐
│ HD-202607-00142    🔴 URGENT   ĐANG XỬ LÝ   │  THÔNG TIN             │
│ Không kết nối được WiFi công ty tại tầng 5  │  Người yêu cầu         │
│                                             │   Nguyễn Văn A         │
│ Từ sáng nay máy tôi không thấy mạng…        │   Kế toán              │
│ 📎 ảnh-loi.png                              │                        │
│                                             │  Người xử lý           │
│ 🤖 AI phân loại: Mạng & Internet (92%)      │   Chu Quang Vũ    [Đổi]│
│    Ưu tiên: URGENT — "ảnh hưởng cả tầng"    │                        │
│                                    [Sửa]    │  Loại: Mạng            │
├─────────────────────────────────────────────┤  Tạo: 30/07 09:30      │
│ TRAO ĐỔI                                    │  Hạn SLA: 30/07 13:30  │
│                                             │   ⏰ Còn 45 phút        │
│ 👤 Nguyễn Văn A · 09:30                     │                        │
│    Máy tôi vẫn không vào được ạ             │  ── THAO TÁC ──        │
│                                             │  [ Đánh dấu đã xử lý ] │
│ 🔧 Chu Quang Vũ · 09:45                     │  [ Chờ người dùng    ] │
│    Tôi đang kiểm tra switch tầng 5          │  [ Chuyển người khác ] │
│                                             │                        │
│ 🔒 Chu Quang Vũ · 09:46 (ghi chú nội bộ)    │  ── LỊCH SỬ ──         │
│    Nghi do cổng 12 trên switch bị lỗi        │  09:46 Ghi chú nội bộ │
│                                             │  09:45 → Đang xử lý    │
│ ┌─────────────────────────────────────────┐ │  09:32 Giao cho C.Q.Vũ │
│ │ Nhập nội dung trao đổi…                 │ │  09:31 🤖 AI phân loại │
│ └─────────────────────────────────────────┘ │  09:30 Tạo ticket      │
│ ☐ Ghi chú nội bộ (chỉ IT thấy)   [Gửi]     │                        │
└─────────────────────────────────────────────┴────────────────────────┘
```

Khác biệt theo vai trò trên cùng một màn hình:
- **Employee**: không thấy khối 🔒 nội bộ, không thấy nhóm nút "THAO TÁC" (chỉ có "Huỷ yêu cầu" khi ticket còn `NEW`/`ASSIGNED`), không sửa được phân loại AI.
- **IT Agent**: thấy tất cả; nút thao tác lấy từ `GET /tickets/{id}/allowed-transitions`.

### 3.4 Chatbot — `/chat`

```
┌──────────────────────────────────────────────────────────────────────┐
│  🤖 Trợ lý IT                                    [+ Cuộc trò chuyện] │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                          Làm sao để đổi mật khẩu email công ty? 👤   │
│                                                                      │
│  🤖 Dựa trên tài liệu nội bộ, bạn có thể đổi mật khẩu như sau:      │
│                                                                      │
│     1. Truy cập portal.company.com                                   │
│     2. Chọn "Tài khoản" → "Đổi mật khẩu"                            │
│     3. Nhập mật khẩu cũ và mật khẩu mới (≥ 8 ký tự)                 │
│                                                                      │
│     📄 Nguồn: Hướng dẫn đổi mật khẩu email công ty                   │
│                                                     [👍] [👎]        │
│                                                                      │
│  ─────────────────────────────────────────────────────────────       │
│  Chưa giải quyết được vấn đề?     [ Tạo ticket từ cuộc trò chuyện ]  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────┐ [Gửi]   │
│  │ Nhập câu hỏi của bạn…                                  │         │
│  └────────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────────┘
```

**Ba yêu cầu bắt buộc về trải nghiệm chatbot:**
1. **Trích dẫn hiển thị TRƯỚC khi câu trả lời sinh xong** (sự kiện SSE `citations` đến trước) — người dùng thấy ngay câu trả lời dựa trên tài liệu nào.
2. **Có chỉ báo đang soạn** trong lúc chờ token đầu tiên; nếu > 5 giây thì hiện "Đang tra cứu tài liệu…".
3. **Khi lỗi**: hiển thị thông điệp thân thiện + nút "Tạo ticket ngay", **không** hiện lỗi kỹ thuật.

### 3.5 Dashboard — `/dashboard`

```
┌──────────────────────────────────────────────────────────────────────┐
│  Dashboard          Khoảng thời gian: [30 ngày qua ▾]   [Xuất CSV]  │
├──────────┬──────────┬──────────┬──────────┬──────────────────────────┤
│ Tổng     │ Đang mở  │ Quá hạn  │ TB xử lý │ Hài lòng                │
│  142     │   23     │    4     │  4,2 giờ │  ⭐ 4,3 / 5             │
│  ▲ 12%   │          │  ▼ 2     │  ▼ 0,8h  │  (68% phản hồi)         │
├──────────┴──────────┴──────────┴──────────┴──────────────────────────┤
│  Ticket theo trạng thái          │  Ticket theo loại sự cố           │
│  ▇▇▇▇▇▇▇▇▇▇ (biểu đồ tròn)      │  ▇▇▇▇▇▇▇▇▇▇ (biểu đồ cột)        │
├──────────────────────────────────┴───────────────────────────────────┤
│  Thời gian xử lý theo loại sự cố (p50 / p90)                         │
│  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇ (biểu đồ cột ngang)                       │
├──────────────────────────────────────────────────────────────────────┤
│  Khối lượng công việc theo IT Agent                                  │
│  Tên              Đang mở  Đã đóng  TB xử lý  Vi phạm SLA  Hài lòng  │
│  Chu Quang Vũ        7        34      3,8h        1         4,5      │
│  Nguyễn Đăng Trường  5        28      4,6h        2         4,1      │
└──────────────────────────────────────────────────────────────────────┘
```

**Quy tắc hiển thị số liệu:**
- Điểm hài lòng **luôn hiển thị kèm tỉ lệ phản hồi**. "4,3 sao" từ 3 lượt đánh giá không nói lên điều gì.
- Thời gian xử lý dùng **p50/p90**, không dùng trung bình (một ticket kéo dài 3 tuần sẽ làm méo trung bình).
- Mỗi thẻ số liệu có tooltip giải thích cách tính.

---

## 4. Cây component

```
App
├── AuthProvider                    Context: user, token, login, logout
├── QueryProvider                   TanStack Query client
├── ToastProvider
└── Router
    ├── PublicLayout
    │   ├── LoginPage
    │   └── RegisterPage
    └── AppLayout                              (yêu cầu đã đăng nhập)
        ├── Sidebar                            menu lọc theo vai trò
        ├── TopBar
        │   ├── GlobalSearch
        │   ├── NotificationBell                polling 30 s
        │   └── UserMenu
        └── <Outlet/>
            ├── MyTicketsPage
            │   ├── TicketFilters
            │   ├── TicketList → TicketListItem → SlaBadge, PriorityBadge, StatusBadge
            │   └── Pagination
            ├── CreateTicketPage
            │   ├── TicketForm                 React Hook Form + Zod
            │   ├── KbSuggestionPanel          debounce 500 ms
            │   └── AttachmentUploader
            ├── TicketDetailPage
            │   ├── TicketHeader → StatusBadge, PriorityBadge, SlaCountdown
            │   ├── AiClassificationCard       hiện độ tin cậy + nút sửa
            │   ├── CommentThread → CommentItem, CommentComposer
            │   ├── AttachmentList
            │   ├── TicketSidebar → AssigneeSelector, ActionButtons, EventTimeline
            │   └── RatingDialog               hiện khi RESOLVED và là requester
            ├── AgentQueuePage
            │   ├── QueueTabs
            │   └── TicketList (dùng lại)
            ├── ChatPage
            │   ├── SessionList
            │   ├── MessageList → MessageBubble, CitationList, FeedbackButtons
            │   └── ChatComposer               xử lý SSE stream
            ├── KbPage / KbArticlePage / KbEditorPage
            ├── DashboardPage
            │   ├── StatCard × 5
            │   ├── StatusPieChart, CategoryBarChart
            │   ├── ResolutionTimeChart
            │   └── AgentWorkloadTable
            └── AdminUsersPage / AiQualityPage
```

**Component dùng lại nhiều nhất** (làm trước, ngày 1–2): `StatusBadge`, `PriorityBadge`, `SlaBadge`, `TicketListItem`, `Pagination`, `EmptyState`, `ErrorState`, `LoadingSkeleton`, `ConfirmDialog`.

---

## 5. Quản lý state và tương tác với API

```typescript
// hooks/useTickets.ts
export function useTickets(filters: TicketFilters) {
  return useQuery({
    queryKey: ['tickets', filters],
    queryFn: () => api.tickets.list(filters),
    staleTime: 30_000,
    refetchOnWindowFocus: true,      // Agent chuyển tab về là thấy dữ liệu mới
  });
}

export function useTicketDetail(id: string) {
  return useQuery({
    queryKey: ['tickets', id],
    queryFn: () => api.tickets.get(id),
    refetchInterval: (q) =>
      document.visibilityState === 'visible' && isOpen(q.state.data) ? 20_000 : false,
    // Chỉ polling khi tab đang hiển thị VÀ ticket còn mở — tiết kiệm request
  });
}

export function useChangeStatus(ticketId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input) => api.tickets.changeStatus(ticketId, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tickets'] });
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
    onError: (e) => {
      if (e.code === 'CONFLICT') {
        toast.error('Ticket đã được người khác cập nhật. Đang tải lại…');
        qc.invalidateQueries({ queryKey: ['tickets', ticketId] });
      }
    },
  });
}
```

| Quy ước | Nội dung |
|---|---|
| `queryKey` | `['tickets']` · `['tickets', id]` · `['tickets', filters]` — hierarchy rõ ràng để invalidate đúng phạm vi |
| Sau mutation | Luôn `invalidateQueries`, **không tự sửa cache bằng tay** (dễ lệch với server) |
| Optimistic update | Chỉ dùng cho thao tác nhỏ, không sợ sai: đánh dấu thông báo đã đọc |
| Xử lý `409` | Hiện toast + tải lại dữ liệu — **không** ép ghi đè |
| Polling | Chỉ khi tab đang hiển thị (Page Visibility API) |

**Xử lý hết hạn token** (một chỗ duy nhất, trong wrapper `fetch`):
```typescript
if (res.status === 401 && !isRetry) {
  await refreshToken();          // gọi 1 lần, các request khác cùng lúc chờ chung
  return request(config, { isRetry: true });
}
// vẫn 401 ⇒ xoá state auth, chuyển về /login
```

---

## 6. Xử lý trạng thái giao diện

Mọi màn hình có dữ liệu **phải** xử lý đủ 4 trạng thái. Đây là điểm hay bị quên và là thứ tạo cảm giác "sản phẩm chưa hoàn thiện":

| Trạng thái | Cách hiển thị |
|---|---|
| **Đang tải** | Skeleton đúng hình dạng nội dung sắp hiện, **không** dùng spinner toàn trang |
| **Rỗng** | Minh hoạ + câu giải thích + hành động gợi ý ("Bạn chưa có yêu cầu nào. **Tạo yêu cầu đầu tiên**") |
| **Lỗi** | Thông điệp tiếng Việt + nút "Thử lại" + `requestId` hiển thị nhỏ ở góc |
| **Có dữ liệu** | Nội dung thật |

Ngoài ra:
- Nút bấm gọi API phải bị **vô hiệu hoá trong lúc chờ** — chống bấm hai lần tạo hai ticket.
- Thao tác không hoàn tác được (huỷ ticket, xoá bài viết) phải có hộp thoại xác nhận.
- Form dài (soạn bài KB) phải cảnh báo khi rời trang mà chưa lưu.

---

## 7. Khả năng tiếp cận và responsive

| Hạng mục | Yêu cầu |
|---|---|
| Bàn phím | Toàn bộ luồng chính thao tác được bằng bàn phím; có viền focus rõ |
| Ngữ nghĩa | Dùng `<button>`, `<nav>`, `<main>`; không dùng `<div onClick>` |
| Nhãn | Mọi input có `<label>`; icon-only button có `aria-label` |
| Màu | Không dùng **chỉ** màu để truyền tải trạng thái — luôn kèm chữ hoặc icon (quan trọng với người mù màu, và với chỉ báo SLA) |
| Tương phản | Tối thiểu 4.5:1 cho chữ thường |
| Breakpoint | Mobile < 768 px (danh sách dạng thẻ, menu ẩn) · Tablet 768–1024 px · Desktop > 1024 px |
| Ưu tiên | Desktop trước (người dùng chính là nhân viên văn phòng), nhưng **màn hình tạo ticket và chatbot phải dùng tốt trên điện thoại** — đó là lúc máy tính đang hỏng |

---

## 8. Cấu trúc thư mục frontend

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── client.ts            # fetch wrapper: auth, refresh, xử lý lỗi
│   │   ├── types.ts             # ★ SINH TỰ ĐỘNG từ openapi.json — không sửa tay
│   │   ├── tickets.ts · auth.ts · kb.ts · chat.ts · reports.ts
│   ├── hooks/                   # useTickets, useAuth, useNotifications, useSSE
│   ├── components/
│   │   ├── ui/                  # shadcn/ui
│   │   ├── common/              # StatusBadge, EmptyState, Pagination, ...
│   │   └── layout/              # AppLayout, Sidebar, TopBar
│   ├── features/                # ★ chia theo TÍNH NĂNG, khớp với module backend
│   │   ├── auth/ · tickets/ · chat/ · knowledge/ · dashboard/ · admin/
│   ├── lib/                     # format ngày giờ, sla, permission helper
│   ├── types/
│   └── styles/
├── .env.example                 # VITE_API_BASE_URL
└── vite.config.ts
```

**Chia theo tính năng, không chia theo loại file.** `features/tickets/` chứa page, component, hook của ticket. Việc này khớp với cách chia module ở backend và giúp FE–BE nói cùng một ngôn ngữ khi trao đổi.

---

## 9. Việc cần làm trước, ngày 1–2 của Sprint 1

Frontend bị chặn bởi backend nếu không chuẩn bị. Thứ tự đề xuất:

| Thứ tự | Việc | Vì sao trước |
|---|---|---|
| 1 | Dựng dự án, Tailwind, shadcn/ui, router, layout | Không phụ thuộc API |
| 2 | `api/client.ts` + luồng auth + `ProtectedRoute` | Mọi thứ khác phụ thuộc vào đây |
| 3 | Bộ component chung (`StatusBadge`, `EmptyState`, ...) | Dùng ở khắp nơi |
| 4 | **Mock API bằng MSW** theo đúng hợp đồng ở tài liệu 06 | **Gỡ chặn hoàn toàn cho FE** — code được toàn bộ màn hình trước khi backend xong. Khi backend sẵn sàng chỉ cần tắt MSW |
| 5 | Màn hình đăng nhập → danh sách ticket → chi tiết ticket | Luồng demo cốt lõi |
| 6 | Tạo ticket, bình luận, đổi trạng thái | Hoàn thiện luồng chính |
| 7 | Chatbot (SSE), dashboard, admin | Phần còn lại |

> Bước 4 là quyết định quan trọng nhất của tài liệu này. Không có mock API, 2 FE dev sẽ ngồi chờ 5 BE dev trong tuần đầu — mất 1/4 thời gian của cả dự án.
