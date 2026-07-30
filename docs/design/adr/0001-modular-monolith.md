# ADR-0001: Dùng Modular Monolith thay vì Microservices

**Trạng thái:** Accepted · **Ngày:** 2026-07-30 · **Người quyết định:** Bùi Mậu Văn, Lại Duy Đông, Cao Mạnh Hà

## Bối cảnh
- Tải đỉnh ước tính ~1,5 rps; yêu cầu bắt buộc là "≥ 100 người dùng đồng thời" ≈ 10 rps (tài liệu 01 §8).
- Dữ liệu sau 3 năm ≈ 1,1 GB.
- Đội 9 người, thời gian 4 tuần, chưa ai vận hành Kubernetes/service mesh.
- Guideline yêu cầu Layered Architecture, Repository Pattern, DI — không yêu cầu microservices.

## Quyết định
Xây dựng **một ứng dụng FastAPI duy nhất** với các module nghiệp vụ được phân tách rõ ràng bên trong (`auth`, `users`, `tickets`, `knowledge`, `chatbot`, `notifications`, `reports`, `feedback`), dùng **một PostgreSQL**, cộng thêm Celery worker chạy cùng codebase.

Ranh giới module được cưỡng chế bằng công cụ `import-linter` trong CI, không chỉ bằng quy ước.

## Hệ quả

### Tích cực
- Không có gọi mạng giữa các module ⇒ không có lỗi phân tán, không có transaction phân tán.
- Một transaction database bao trọn một thao tác nghiệp vụ (ví dụ: đổi trạng thái ticket + ghi `ticket_events`).
- Deploy đơn giản: một image, một migration, một lần deploy.
- 9 người làm việc trên một repo, review chéo dễ dàng.
- Nếu về sau cần tách service thật, ranh giới module đã sẵn sàng.

### Tiêu cực
- Không scale từng phần riêng biệt được (không cần ở quy mô này).
- Một lỗi nghiêm trọng ở bất kỳ module nào có thể làm sập cả ứng dụng ⇒ bù bằng việc chạy ≥ 2 replica ở production.
- Ranh giới module dễ bị phá nếu không có công cụ chặn ⇒ bắt buộc có `import-linter` trong CI.

## Phương án đã cân nhắc
- **Microservices** (auth-service, ticket-service, ai-service): mua về toàn bộ chi phí của hệ phân tán mà không có bất kỳ áp lực nào bắt buộc phải trả. Với 4 tuần, gần như chắc chắn không kịp deadline.
- **Serverless**: cold start phá vỡ mục tiêu p95 < 500 ms; kết nối PostgreSQL cần pooler; khó chạy job nền.

## Cân nhắc lại khi
- Tải vượt 150 rps liên tục, **hoặc**
- Có nhiều hơn 4 nhóm phát triển độc lập cần deploy theo nhịp khác nhau, **hoặc**
- Một module có yêu cầu cách ly riêng (compliance, dữ liệu nhạy cảm đặc thù).
