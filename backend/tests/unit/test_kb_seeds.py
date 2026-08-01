"""Kiểm tra tính toàn vẹn của bộ bài viết kho tri thức trong seeds/kb/.

Bộ test này chạy trong CI, không cần database. Nó bắt các lỗi mà chỉ đến
lúc seed vào DB mới lộ ra — hoặc tệ hơn, đến lúc demo chatbot mới lộ ra:

- Frontmatter sai cú pháp
- Slug lệch tên file, hoặc trùng nhau
- Chủ đề (category) không nằm trong danh sách hợp lệ
- ★ Tập đánh giá RAG trỏ tới bài viết KHÔNG TỒN TẠI
"""

import json
import re
from pathlib import Path

import pytest

from app.modules.knowledge.chunker import TextChunker

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
KB_DIR = BACKEND_DIR / "seeds" / "kb"
RAG_EVAL = BACKEND_DIR / "tests" / "fixtures" / "rag_eval.jsonl"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

# Phải khớp với dữ liệu seed trong scripts/seed.py
VALID_KB_CATEGORIES = {"huong-dan-chung", "mang", "phan-mem", "tai-khoan", "bao-mat"}
VALID_TICKET_CATEGORIES = {
    "network",
    "hardware",
    "software",
    "account",
    "access",
    "email",
    "security",
    "other",
}

MIN_WORDS = 200
MAX_WORDS = 1200


def parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if match is None:
        raise ValueError("Thiếu khối frontmatter")
    raw, body = match.groups()
    meta: dict = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value.strip("'\"")
    return meta, body.strip()


ARTICLE_FILES = sorted(KB_DIR.glob("*.md"))


def test_co_du_bai_viet():
    """Thiết kế yêu cầu tối thiểu 15 bài để chatbot RAG có đủ dữ liệu."""
    assert len(ARTICLE_FILES) >= 15, (
        f"Chỉ có {len(ARTICLE_FILES)} bài. Kho tài liệu quá mỏng thì chatbot "
        f"sẽ thường xuyên trả lời 'không biết' — rủi ro số 1 của dự án."
    )


@pytest.mark.parametrize("path", ARTICLE_FILES, ids=lambda p: p.stem)
class TestTungBaiViet:
    def test_frontmatter_hop_le(self, path: Path):
        meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        for field in ("slug", "title", "category", "summary"):
            assert meta.get(field), f"thiếu trường {field!r}"

    def test_slug_khop_ten_file(self, path: Path):
        meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        assert meta["slug"] == path.stem

    def test_category_hop_le(self, path: Path):
        meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        assert meta["category"] in VALID_KB_CATEGORIES
        ticket_cat = meta.get("ticket_category")
        if ticket_cat:
            assert ticket_cat in VALID_TICKET_CATEGORIES

    def test_do_dai_hop_ly(self, path: Path):
        _, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        words = len(body.split())
        assert MIN_WORDS <= words <= MAX_WORDS, f"{words} từ, nằm ngoài khoảng cho phép"

    def test_co_tieu_de_markdown_de_chia_chunk(self, path: Path):
        """Chunker chia theo tiêu đề Markdown. Bài không có ## sẽ thành một
        chunk khổng lồ, làm giảm chất lượng truy xuất."""
        _, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        assert body.count("\n## ") >= 2, "cần ít nhất 3 mục ## để chia chunk tốt"

    def test_chia_chunk_duoc(self, path: Path):
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        chunks = TextChunker().chunk(title=meta["title"], content_md=body)
        assert len(chunks) >= 1
        # Mỗi chunk phải mang theo ngữ cảnh, nếu không sẽ vô nghĩa khi tách khỏi bài
        for chunk in chunks:
            assert chunk.content.startswith("[Bài viết:")


def test_khong_co_slug_trung():
    slugs = [p.stem for p in ARTICLE_FILES]
    duplicates = {s for s in slugs if slugs.count(s) > 1}
    assert not duplicates, f"Slug bị trùng: {duplicates}"


def test_tap_danh_gia_rag_tro_toi_bai_co_that():
    """★ Test quan trọng nhất của file này.

    Nếu rag_eval.jsonl trỏ tới một bài không tồn tại, script đánh giá sẽ
    báo chatbot 'trả lời sai' trong khi thực ra là thiếu tài liệu — chẩn
    đoán nhầm hướng và mất rất nhiều thời gian tìm nguyên nhân.
    """
    available = {p.stem for p in ARTICLE_FILES}
    rows = [
        json.loads(line)
        for line in RAG_EVAL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    missing = [
        (row["id"], row["expect_article_slug"])
        for row in rows
        if row["expect_answer"] and row.get("expect_article_slug") not in available
    ]
    assert not missing, f"Tập đánh giá trỏ tới bài không tồn tại: {missing}"


# Các cụm từ TUYỆT ĐỐI không được xuất hiện dưới dạng hướng dẫn trong bài KB.
# Bài viết là nguồn dữ liệu của chatbot — nội dung sai ở đây sẽ được chatbot
# lặp lại cho toàn công ty, với giọng điệu đáng tin cậy.
FORBIDDEN_PHRASES = (
    "gửi mật khẩu cho",
    "cung cấp mật khẩu cho",
    "chia sẻ mật khẩu với",
    "đọc mật khẩu qua điện thoại",
    "tắt phần mềm diệt virus",
    "tắt tường lửa",
    "bỏ qua cảnh báo bảo mật",
)


NEGATION_WORDS = ("không", "đừng", "tránh", "cấm")


def _appears_as_instruction(text: str, phrase: str) -> bool:
    """Cụm từ có xuất hiện như một HƯỚNG DẪN không, hay chỉ là lời cảnh báo?

    "không tắt phần mềm diệt virus" là lời khuyên đúng — không được tính là
    vi phạm. Chỉ tính khi cụm từ đứng độc lập, không có từ phủ định ngay trước.
    """
    for match in re.finditer(re.escape(phrase), text):
        preceding = text[max(0, match.start() - 25) : match.start()]
        if not any(neg in preceding for neg in NEGATION_WORDS):
            return True
    return False


@pytest.mark.parametrize("path", ARTICLE_FILES, ids=lambda p: p.stem)
def test_khong_chua_huong_dan_nguy_hiem(path: Path):
    """Không bài nào được hướng dẫn người dùng làm việc gây rủi ro bảo mật."""
    text = path.read_text(encoding="utf-8").lower()
    found = [p for p in FORBIDDEN_PHRASES if _appears_as_instruction(text, p)]
    assert not found, f"{path.name}: chứa hướng dẫn nguy hiểm {found}"


def test_bai_ve_mat_khau_co_canh_bao_it_khong_hoi_mat_khau():
    """Các bài trực tiếp hướng dẫn về mật khẩu phải nhắc rằng đội IT không
    bao giờ hỏi mật khẩu — đây là lá chắn quan trọng nhất chống lừa đảo."""
    password_articles = {
        "doi-mat-khau-email",
        "chinh-sach-mat-khau",
        "quen-mat-khau-may-tinh",
        "nhan-dien-email-lua-dao",
    }
    for path in ARTICLE_FILES:
        if path.stem not in password_articles:
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert (
            "không bao giờ" in text and "hỏi mật khẩu" in text
        ), f"{path.name}: thiếu cảnh báo 'đội IT không bao giờ hỏi mật khẩu'"
