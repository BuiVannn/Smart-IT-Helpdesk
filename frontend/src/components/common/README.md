# Component dùng chung

Thư mục này chứa các component được dùng lại ở nhiều màn hình.

## Đã có
_(chưa có — đây là phần được giao cho nhóm ở task ngày 31/07/2026)_

## Cần xây dựng

| Component | Ai làm | Mô tả |
|---|---|---|
| `StatusBadge` | Nguyễn Văn Quang | Nhãn trạng thái ticket, 7 trạng thái, mỗi trạng thái một màu |
| `PriorityBadge` | Nguyễn Văn Quang | Nhãn mức ưu tiên, 4 mức |
| `SlaBadge` | Nguyễn Văn Quang | Chỉ báo SLA kèm thời gian còn lại |
| `EmptyState` | Nguyễn Văn Dũng | Màn hình khi danh sách rỗng |
| `ErrorState` | Nguyễn Văn Dũng | Màn hình khi gọi API lỗi, có nút thử lại |
| `LoadingSkeleton` | Nguyễn Văn Dũng | Khung xám khi đang tải |
| `Pagination` | Nguyễn Văn Dũng | Điều hướng trang |

## Quy tắc chung

1. **Không dùng CHỈ màu để truyền tải trạng thái** — luôn kèm chữ hoặc icon.
   Quan trọng với người mù màu, và với chỉ báo SLA.
2. Dùng `cn()` từ `@/lib/utils` để gộp class Tailwind.
3. Component nhận props tối thiểu, không tự gọi API.
4. Dùng thẻ ngữ nghĩa: `<button>` chứ không phải `<div onClick>`.
