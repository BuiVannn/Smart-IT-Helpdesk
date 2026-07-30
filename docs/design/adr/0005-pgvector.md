# ADR-0005: Dùng pgvector thay vì vector database riêng

**Trạng thái:** Accepted · **Ngày:** 2026-07-30 · **Người quyết định:** Bùi Mậu Văn, Cao Mạnh Hà

## Bối cảnh
Chatbot RAG (F4) cần tìm kiếm vector trên các đoạn văn bản của kho tài liệu. Ước tính: ~300 bài viết × ~12 chunk = **3.600 vector**, mỗi vector 1.536 chiều × 4 byte ≈ **22 MB**.

Tài liệu phân công ban đầu có task "Setup vector DB & hạ tầng cho AI — 3 ngày".

## Quyết định
Dùng extension **`pgvector`** trên chính PostgreSQL đang có, với index HNSW (`m=16, ef_construction=64`) và toán tử cosine distance.

## Hệ quả

### Tích cực
- **Không thêm hệ thống nào.** Không có service mới, không có backup mới, không có điểm hỏng mới.
- Chunk và bài viết nằm cùng transaction ⇒ publish bài và tạo chunk là **một** thao tác nguyên tử. Không bao giờ có chunk mồ côi hay bài viết chưa được index mà tưởng đã index.
- Lọc theo `status = 'PUBLISHED'` chỉ là một JOIN SQL — với vector DB riêng phải dùng metadata filtering, phức tạp hơn và dễ sai.
- Ở 3.600 vector, thời gian truy vấn vài mili-giây — không khác biệt so với vector DB chuyên dụng.
- **Task 3 ngày rút xuống còn ~0,5 ngày**, thời gian dôi ra chuyển sang dựng staging (đang nằm trên đường găng).

### Tiêu cực
- Không có các tính năng nâng cao: hybrid search dựng sẵn, quantization, sharding vector.
- Chiều vector cố định trong schema ⇒ đổi model embedding là một migration, không phải đổi config.
- Ở quy mô hàng triệu vector, pgvector sẽ chậm hơn hệ chuyên dụng.

## Phương án đã cân nhắc
- **Qdrant / Milvus / Weaviate**: được thiết kế cho hàng triệu vector. Dùng cho 22 MB dữ liệu là thêm một hệ thống phải vận hành, một pipeline đồng bộ, và một thứ đội chưa từng chạy — để giải quyết một vấn đề chưa tồn tại.
- **FAISS trong bộ nhớ**: mất khi restart, không chia sẻ được giữa nhiều worker, không có persistence.

## Cân nhắc lại khi
Số chunk vượt **500.000**, hoặc thời gian truy xuất p95 vượt **200 ms**.
