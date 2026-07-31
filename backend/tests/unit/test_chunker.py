"""Unit test cho TextChunker."""

from app.modules.knowledge.chunker import TextChunker


def test_chia_theo_tieu_de_markdown():
    chunker = TextChunker()
    content = """## Bước 1
Truy cập portal.company.com và đăng nhập bằng tài khoản công ty của bạn.

## Bước 2
Chọn mục Tài khoản rồi bấm Đổi mật khẩu để bắt đầu quá trình thay đổi."""

    chunks = chunker.chunk(title="Đổi mật khẩu", content_md=content)

    assert len(chunks) == 2
    assert chunks[0].heading == "Bước 1"
    assert chunks[1].heading == "Bước 2"


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
    chunker = TextChunker(max_tokens=100)
    long_text = " ".join(["Đây là một câu tiếng Việt khá dài."] * 100)
    chunks = chunker.chunk(title="Bài dài", content_md=long_text)
    assert len(chunks) > 1
    assert all(c.token_count <= 200 for c in chunks)
