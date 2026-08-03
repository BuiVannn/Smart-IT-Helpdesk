"""Chia bài viết thành chunk cho RAG — LỚP THUẦN, không I/O.

Chiến lược: chia theo TIÊU ĐỀ MARKDOWN trước, rồi mới theo độ dài. Một mục
hướng dẫn thường là một đơn vị ngữ nghĩa trọn vẹn; chia máy móc theo số ký
tự sẽ cắt đôi các bước hướng dẫn.

Mỗi chunk được chèn tiền tố "[Bài viết: ...] [Mục: ...]" — RẤT QUAN TRỌNG:
chunk tách khỏi ngữ cảnh sẽ mất chủ đề, khiến embedding kém và LLM không
biết đoạn đó nói về cái gì.
"""

import re
from dataclasses import dataclass

TARGET_TOKENS = 500
MAX_TOKENS = 800
OVERLAP_TOKENS = 80
MIN_TOKENS = 100

HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


@dataclass
class Chunk:
    index: int
    content: str
    token_count: int
    heading: str | None = None


def estimate_tokens(text: str) -> int:
    """Ước lượng số token. Tiếng Việt ~1,5 token/từ với tokenizer phổ biến.

    Đây là ƯỚC LƯỢNG, không phải con số chính xác — đủ dùng để quyết định
    chỗ cắt. Muốn chính xác thì dùng tiktoken, nhưng không đáng thêm dependency.
    """
    return max(1, int(len(text.split()) * 1.5))


def _split_by_heading(markdown: str) -> list[tuple[str | None, str]]:
    """Tách văn bản thành các cặp (tiêu đề, nội dung)."""
    matches = list(HEADING_RE.finditer(markdown))
    if not matches:
        return [(None, markdown.strip())]

    sections: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        preamble = markdown[: matches[0].start()].strip()
        if preamble:
            sections.append((None, preamble))

    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()
        if body:
            sections.append((heading, body))
    return sections


def _split_long_text(text: str, max_tokens: int, overlap: int) -> list[str]:
    """Cắt đoạn quá dài theo câu, có chồng lấn để không mất ý ở ranh giới."""
    sentences = re.split(r"(?<=[.!?…])\s+|\n\n", text)
    parts: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        t = estimate_tokens(s)
        if current_tokens + t > max_tokens and current:
            parts.append(" ".join(current))
            # giữ lại phần cuối làm chồng lấn
            keep: list[str] = []
            kept_tokens = 0
            for prev in reversed(current):
                kept_tokens += estimate_tokens(prev)
                keep.insert(0, prev)
                if kept_tokens >= overlap:
                    break
            current, current_tokens = keep, kept_tokens
        current.append(s)
        current_tokens += t

    if current:
        parts.append(" ".join(current))
    return parts


class TextChunker:
    def __init__(
        self,
        target_tokens: int = TARGET_TOKENS,
        max_tokens: int = MAX_TOKENS,
        overlap_tokens: int = OVERLAP_TOKENS,
        min_tokens: int = MIN_TOKENS,
    ) -> None:
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.min_tokens = min_tokens

    def chunk(self, *, title: str, content_md: str) -> list[Chunk]:
        raw: list[tuple[str | None, str]] = []

        for heading, body in _split_by_heading(content_md):
            if estimate_tokens(body) <= self.max_tokens:
                raw.append((heading, body))
            else:
                for part in _split_long_text(body, self.max_tokens, self.overlap_tokens):
                    raw.append((heading, part))

        # Gộp chunk quá ngắn với chunk trước — tránh chunk rác.
        #
        # ⚠️ CHỈ gộp khi kết quả VẪN dưới max_tokens. Không có điều kiện này,
        # bước gộp sẽ hoàn tác cả bước cắt chunk dài ở trên và tạo ra một
        # chunk khổng lồ (lỗi đã bị test bắt: 8934 token với giới hạn 100).
        merged: list[tuple[str | None, str]] = []
        for heading, body in raw:
            if merged and estimate_tokens(body) < self.min_tokens:
                prev_heading, prev_body = merged[-1]
                # Giữ lại tiêu đề của mục bị gộp vào trong phần nội dung.
                # Nếu bỏ đi, chunk sẽ chứa nội dung "Bước 2" nhưng chỉ được
                # gắn nhãn "Mục: Bước 1" — sai lệch, làm hỏng cả embedding
                # lẫn khả năng LLM hiểu đoạn đó nói về cái gì.
                addition = f"## {heading}\n{body}" if heading else body
                combined = f"{prev_body}\n\n{addition}"
                if estimate_tokens(combined) <= self.max_tokens:
                    merged[-1] = (prev_heading, combined)
                    continue
            merged.append((heading, body))

        chunks: list[Chunk] = []
        for i, (heading, body) in enumerate(merged):
            prefix = f"[Bài viết: {title}]"
            if heading:
                prefix += f" [Mục: {heading}]"
            text = f"{prefix}\n{body}"
            chunks.append(
                Chunk(index=i, content=text, token_count=estimate_tokens(text), heading=heading)
            )
        return chunks
