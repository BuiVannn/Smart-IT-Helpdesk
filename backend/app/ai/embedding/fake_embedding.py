"""Embedding giả — vector TẤT ĐỊNH mang thông tin TỪ VỰNG thật.

★★ ĐỌC TRƯỚC KHI SỬA. Bản đầu tiên sinh vector từ `sha256(text)` và docstring
tự khẳng định "văn bản giống nhau cho vector gần nhau". Khẳng định đó SAI, và
sai theo hướng nguy hiểm nhất — nó nghe hợp lý nên không ai kiểm. Đo thật:

    'Cách đổi mật khẩu email công ty' ↔ 'Hướng dẫn đổi mật khẩu email công ty'  = -0,21
    'Cách đổi mật khẩu email công ty' ↔ 'Máy in tầng 3 bị kẹt giấy'             = -0,04

Hai câu gần đồng nghĩa XA NHAU HƠN hai câu không liên quan. SHA-256 theo
thiết kế là hàm khuếch tán: đổi một ký tự thì toàn bộ digest đổi. Hậu quả đo
được trên kho tài liệu thật: **recall@5 = 0/10**, và 0/3 câu ngoài phạm vi bị
từ chối — chatbot trích dẫn tài liệu ngẫu nhiên và trả lời cả câu tấn công.

Bản này dùng **hashing trick** trên túi từ và cụm ký tự:

    chuẩn hoá (bỏ dấu, thường hoá) → tách từ + cụm 3 ký tự
    → băm mỗi đặc trưng vào một chiều, cộng dồn có dấu → chuẩn hoá L2

Nhờ vậy hai văn bản dùng chung nhiều từ sẽ gần nhau thật, và **tiếng Việt
không dấu khớp với có dấu** ("quen mat khau" ↔ "quên mật khẩu") — đúng nhóm
rủi ro mà `docs/design/07` §7 gọi tên.

★ VẪN KHÔNG PHẢI EMBEDDING NGỮ NGHĨA. Nó khớp theo TỪ, không hiểu nghĩa:
"máy tính chạy chậm" và "laptop ì ạch" vẫn xa nhau. Dùng để test tất định và
để demo trung thực khi chưa có API key; con số chất lượng RAG dùng để báo cáo
phải đo với embedding thật (`LLM_PROVIDER=openai`).
"""

import hashlib
import math
import re
import unicodedata

from app.core.config import settings

# Cụm 3 ký tự bắt được biến thể gõ thiếu/thừa dấu và lỗi chính tả nhẹ, thứ mà
# tách từ thuần không bắt được. Trọng số thấp hơn từ nguyên vẹn để từ vẫn là
# tín hiệu chính.
#
# ★ Cụm ký tự lấy TRONG TỪNG TỪ, không lấy trên cả chuỗi đã nối. Đo trên kho
# tài liệu thật (65 chunk, 10 câu hỏi đánh giá):
#
#   cụm trên cả chuỗi, w=0,35        điểm thấp nhất của ca ĐÚNG 0,340
#                                    điểm cao nhất của ca NGOÀI PHẠM VI 0,356  → chồng lấn
#   cụm trong từng từ, w=0,25 + bỏ   0,415  /  0,278                            → tách biệt +0,137
#   từ dừng
#
# Cụm bắc cầu qua ranh giới từ tạo ra hàng loạt đặc trưng chung vô nghĩa
# ("ng ", " ca", "ho ") khiến hai văn bản không liên quan vẫn giống nhau —
# đủ để câu "Lương tháng này khi nào được trả?" vượt ngưỡng và lấy về tài liệu
# IT. Giới hạn trong từ thì cụm chỉ còn phục vụ đúng việc của nó: khớp biến
# thể chính tả.
NGRAM_SIZE = 3
NGRAM_WEIGHT = 0.25
TU_PATTERN = re.compile(r"[a-z0-9]+")

# Từ dừng tiếng Việt — xuất hiện ở gần như mọi câu nên không phân biệt được
# gì, mà lại chiếm trọng số ngang từ khoá thật. Danh sách cố ý NGẮN và không
# chứa từ phủ định ("không", "chưa"): "wifi không kết nối được" và "wifi kết
# nối được" là hai sự việc trái ngược nhau.
TU_DUNG = frozenset("""
    toi lam sao gi cua cho khi nao phai thi la va co de voi tren trong mot cac
    nay ay o bi da se hay muon can xin giup the nhu tu den ra vao minh ban a
    """.split())


def _bo_dau(text: str) -> str:
    """Bỏ dấu tiếng Việt. Cùng bài toán với `classifier.normalize()`.

    `đ` phải xử lý riêng: nó là một ký tự Latin độc lập, không phải `d` cộng
    dấu, nên NFD không tách ra được.
    """
    text = text.lower().replace("đ", "d")
    tach = unicodedata.normalize("NFD", text)
    return "".join(c for c in tach if unicodedata.category(c) != "Mn")


def _dac_trung(text: str) -> list[tuple[str, float]]:
    tu = TU_PATTERN.findall(_bo_dau(text))

    # Bỏ từ dừng, NHƯNG nếu bỏ xong không còn gì thì giữ nguyên: câu hỏi chỉ
    # gồm từ dừng vẫn phải cho ra một vector, không được trả về vector rỗng
    # rồi khớp với mọi thứ.
    co_nghia = [t for t in tu if t not in TU_DUNG] or tu

    dac_trung: list[tuple[str, float]] = [(t, 1.0) for t in co_nghia]

    for t in co_nghia:
        # Đệm khoảng trắng hai đầu để cụm đầu/cuối từ cũng là một đặc trưng —
        # nhờ đó "mật khẩu" và "matkhau" vẫn chia sẻ cụm bên trong.
        dem = f" {t} "
        for i in range(len(dem) - NGRAM_SIZE + 1):
            dac_trung.append((dem[i : i + NGRAM_SIZE], NGRAM_WEIGHT))

    return dac_trung


class FakeEmbeddingClient:
    def __init__(self, dimensions: int | None = None) -> None:
        self._dimensions = dimensions or settings.EMBEDDING_DIMENSIONS

    @property
    def model_name(self) -> str:
        return "fake-embedding-hashing"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self._dimensions

        for dac_trung, trong_so in _dac_trung(text):
            # blake2b nhanh hơn sha256 và cho đủ bit cho cả chỉ số lẫn dấu.
            digest = hashlib.blake2b(dac_trung.encode(), digest_size=8).digest()
            so = int.from_bytes(digest, "big")
            chi_so = so % self._dimensions
            # Dấu tất định theo đặc trưng: hai đặc trưng khác nhau va vào cùng
            # một chiều sẽ triệt tiêu lẫn nhau thay vì luôn cộng dồn, nhờ đó
            # nhiễu không tích luỹ theo độ dài văn bản.
            dau = 1.0 if (so >> 63) & 1 else -1.0
            vec[chi_so] += dau * trong_so

        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:  # văn bản rỗng hoặc chỉ có ký tự đặc biệt
            return vec
        return [x / norm for x in vec]
