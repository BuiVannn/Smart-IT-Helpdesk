"""Unit test cho TextChunker."""

from app.modules.knowledge.chunker import TextChunker


def test_chia_theo_tieu_de_markdown():
    """Mỗi mục ## đủ dài trở thành một chunk riêng, giữ được tiêu đề mục."""
    chunker = TextChunker()
    body = " ".join(["Đây là nội dung hướng dẫn chi tiết cho bước này."] * 30)
    content = f"## Bước 1\n{body}\n\n## Bước 2\n{body}"

    chunks = chunker.chunk(title="Đổi mật khẩu", content_md=content)

    assert len(chunks) == 2
    assert chunks[0].heading == "Bước 1"
    assert chunks[1].heading == "Bước 2"


def test_hai_muc_qua_ngan_duoc_gop_lam_mot():
    """Chunk 30 token quá nhỏ để hữu ích khi truy xuất — gộp lại là đúng."""
    chunker = TextChunker()
    content = """## Bước 1
Truy cập portal.company.com và đăng nhập.

## Bước 2
Chọn mục Tài khoản rồi bấm Đổi mật khẩu."""

    chunks = chunker.chunk(title="Đổi mật khẩu", content_md=content)

    assert len(chunks) == 1
    assert "Bước 1" in chunks[0].content and "Bước 2" in chunks[0].content


def test_moi_chunk_deu_co_tien_to_ngu_canh():
    """Chunk tách khỏi ngữ cảnh sẽ mất chủ đề — tiền tố là bắt buộc."""
    chunker = TextChunker()
    chunks = chunker.chunk(
        title="Hướng dẫn kết nối WiFi",
        content_md="## Cách 1\nVào Settings, chọn mạng CTY-WIFI rồi nhập mật khẩu được cấp.",
    )
    assert "[Bài viết: Hướng dẫn kết nối WiFi]" in chunks[0].content
    assert "[Mục: Cách 1]" in chunks[0].content


def test_bai_khong_co_tieu_de_van_chay_duoc():
    chunker = TextChunker()
    chunks = chunker.chunk(title="Ghi chú", content_md="Đây là một đoạn văn bản không có tiêu đề.")
    assert len(chunks) == 1
    assert chunks[0].heading is None


def test_chunk_qua_ngan_duoc_gop():
    chunker = TextChunker(min_tokens=50)
    content = "## A\nNgắn.\n\n## B\nCũng ngắn."
    chunks = chunker.chunk(title="Test", content_md=content)
    assert len(chunks) == 1   # hai mục ngắn được gộp làm một


def test_bai_rat_dai_bi_cat_nho():
    """★ Bước gộp chunk ngắn KHÔNG được hoàn tác bước cắt chunk dài.

    Lỗi cũ: gộp vô điều kiện khiến 100 câu bị nhập lại thành MỘT chunk
    8934 token, dù giới hạn là 100.
    """
    max_tokens = 100
    chunker = TextChunker(max_tokens=max_tokens)
    long_text = " ".join(["Đây là một câu tiếng Việt khá dài."] * 100)

    chunks = chunker.chunk(title="Bài dài", content_md=long_text)

    assert len(chunks) > 1, "văn bản dài phải bị cắt nhỏ"
    # Cho phép vượt một chút vì tiền tố ngữ cảnh được chèn thêm sau khi cắt
    assert all(c.token_count <= max_tokens * 1.5 for c in chunks), (
        f"chunk lớn nhất: {max(c.token_count for c in chunks)} token"
    )
