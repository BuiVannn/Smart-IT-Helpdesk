# ADR-0010: Dùng React SPA (Vite) thay vì Next.js

**Trạng thái:** Accepted · **Ngày:** 2026-07-30 · **Người quyết định:** Nguyễn Văn Quang, Nguyễn Văn Dũng

## Bối cảnh
Guideline cho phép ReactJS, NextJS hoặc VueJS. Backend đã là FastAPI và toàn bộ nghiệp vụ nằm ở đó.

## Quyết định
**React 18 + TypeScript + Vite**, build ra file tĩnh, phục vụ qua Nginx. Không dùng Next.js.

## Hệ quả

### Tích cực
- Không cần chạy thêm một Node.js server ở production — chỉ là file tĩnh.
- Không có sự nhập nhằng "logic này nên ở Next API route hay ở FastAPI" — **toàn bộ nghiệp vụ ở backend, không có ngoại lệ**. Với 2 FE và 5 BE làm song song, ranh giới rõ ràng quan trọng hơn tiện lợi.
- Vite dev server khởi động và hot-reload rất nhanh.
- Deploy đơn giản, phù hợp với ngân sách hạ tầng bằng không.

### Tiêu cực
- Không có SSR ⇒ SEO kém (không liên quan: đây là hệ thống nội bộ, cần đăng nhập).
- Màn hình đầu tiên tải chậm hơn một chút ⇒ bù bằng code splitting theo route.
- Không có các tiện ích sẵn có của Next (image optimization, file-based routing).

## Cân nhắc lại khi
Có yêu cầu công khai một phần kho tri thức ra Internet và cần SEO.
