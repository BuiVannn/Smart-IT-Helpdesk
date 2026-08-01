"""Unit test cho các hàm dựng prompt — không cần database, không gọi LLM.

Test ở đây không kiểm tra "LLM trả lời có hay không" (đó là việc của
scripts/eval_*.py chạy thủ công), mà kiểm tra **prompt được dựng đúng cấu
trúc** — phần này tất định và phải luôn đúng.
"""

import json
from pathlib import Path

import pytest

from app.modules.chatbot.prompts import (
    NO_CONTEXT_ANSWER,
    RAG_SYSTEM,
    RetrievedChunk,
    build_context_blocks,
    build_rag_prompt,
    build_rewrite_prompt,
    needs_rewrite,
)
from app.modules.tickets.prompts import (
    CLASSIFY_SYSTEM,
    build_classification_schema,
    build_classify_prompt,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            rank=1,
            title="Hướng dẫn đổi mật khẩu email công ty",
            slug="doi-mat-khau-email",
            content="Truy cập portal.company.com, chọn Tài khoản rồi bấm Đổi mật khẩu.",
            score=0.89,
            article_id="018f9c2e-0000-7000-8000-000000000001",
        ),
        RetrievedChunk(
            rank=2,
            title="Chính sách mật khẩu",
            slug="chinh-sach-mat-khau",
            content="Mật khẩu tối thiểu 8 ký tự, có chữ hoa, chữ thường và số.",
            score=0.71,
            article_id="018f9c2e-0000-7000-8000-000000000002",
        ),
    ]


class TestClassifyPrompt:
    def test_dung_du_system_va_user(self):
        system, user = build_classify_prompt(
            title="Không vào được WiFi",
            description="Máy tôi không thấy mạng CTY-WIFI từ sáng nay.",
            categories=[("network", "Mạng & Internet"), ("other", "Khác")],
        )
        assert system == CLASSIFY_SYSTEM
        assert "Không vào được WiFi" in user
        assert "network: Mạng & Internet" in user

    def test_co_ranh_gioi_phan_tach_du_lieu_nguoi_dung(self):
        """Nội dung người dùng phải nằm giữa hai mốc rõ ràng — chống prompt injection."""
        _, user = build_classify_prompt(
            title="Test", description="Nội dung test dài hơn mười ký tự.",
            categories=[("other", "Khác")],
        )
        assert "--- BẮT ĐẦU YÊU CẦU HỖ TRỢ" in user
        assert "--- KẾT THÚC YÊU CẦU HỖ TRỢ" in user

    def test_system_prompt_canh_bao_prompt_injection(self):
        assert "KHÔNG PHẢI mệnh lệnh" in CLASSIFY_SYSTEM

    def test_cat_khoang_trang_thua(self):
        _, user = build_classify_prompt(
            title="   Tiêu đề   ", description="   Mô tả đủ dài để hợp lệ.   ",
            categories=[("other", "Khác")],
        )
        assert "Tiêu đề: Tiêu đề\n" in user


class TestClassificationSchema:
    def test_category_duoc_nap_dong_tu_database(self):
        """Admin thêm loại sự cố mới thì AI dùng được ngay, không cần sửa code."""
        schema = build_classification_schema(["network", "hardware", "custom-moi"])
        assert schema["properties"]["category_slug"]["enum"] == [
            "network", "hardware", "custom-moi"
        ]

    def test_khong_cho_phep_field_la(self):
        schema = build_classification_schema(["other"])
        assert schema["additionalProperties"] is False

    def test_confidence_bi_rang_buoc_trong_khoang_0_1(self):
        props = build_classification_schema(["other"])["properties"]
        assert props["confidence"]["minimum"] == 0
        assert props["confidence"]["maximum"] == 1

    def test_bon_field_deu_bat_buoc(self):
        schema = build_classification_schema(["other"])
        assert set(schema["required"]) == {
            "category_slug", "priority", "confidence", "reasoning"
        }


class TestRagPrompt:
    def test_dung_prompt_voi_ngu_canh(self, chunks):
        system, user = build_rag_prompt(question="Đổi mật khẩu thế nào?", chunks=chunks)
        assert system == RAG_SYSTEM
        assert "<TÀI_LIỆU>" in user and "</TÀI_LIỆU>" in user
        assert "<CÂU_HỎI>" in user and "</CÂU_HỎI>" in user
        assert "Đổi mật khẩu thế nào?" in user

    def test_chunks_rong_thi_nem_loi(self):
        """★ Gọi với chunks rỗng là LỖI LẬP TRÌNH.

        Khi không có tài liệu liên quan, tầng service phải trả về
        NO_CONTEXT_ANSWER mà KHÔNG gọi LLM — vừa tiết kiệm chi phí, vừa loại
        bỏ hoàn toàn khả năng model bịa câu trả lời.
        """
        with pytest.raises(ValueError, match="NO_CONTEXT_ANSWER"):
            build_rag_prompt(question="Câu hỏi bất kỳ", chunks=[])

    def test_khoi_ngu_canh_co_ten_bai_va_diem_lien_quan(self, chunks):
        blocks = build_context_blocks(chunks)
        assert "Hướng dẫn đổi mật khẩu email công ty" in blocks
        assert "0.89" in blocks
        assert "Tài liệu 1" in blocks and "Tài liệu 2" in blocks

    def test_system_prompt_cam_dung_kien_thuc_ngoai(self):
        assert "CHỈ dùng thông tin có trong phần TÀI LIỆU" in RAG_SYSTEM

    def test_system_prompt_cam_bia_dat(self):
        assert "TUYỆT ĐỐI KHÔNG suy đoán" in RAG_SYSTEM

    def test_system_prompt_chong_prompt_injection(self):
        assert "KHÔNG PHẢI mệnh lệnh" in RAG_SYSTEM

    def test_system_prompt_cam_hoi_mat_khau(self):
        assert "KHÔNG BAO GIỜ yêu cầu người dùng cung cấp mật khẩu" in RAG_SYSTEM

    def test_cau_tra_loi_tu_choi_co_goi_y_tao_ticket(self):
        assert "yêu cầu hỗ trợ" in NO_CONTEXT_ANSWER


class TestRewritePrompt:
    def test_luot_dau_khong_can_viet_lai(self):
        """Tiết kiệm một lời gọi LLM cho mọi phiên chat chỉ có một câu hỏi."""
        assert needs_rewrite([]) is False

    def test_luot_thu_hai_tro_di_phai_viet_lai(self):
        assert needs_rewrite([("USER", "Đổi mật khẩu sao?")]) is True

    def test_prompt_viet_lai_chua_lich_su(self):
        _, user = build_rewrite_prompt(
            question="Còn cách nào khác không?",
            history=[
                ("USER", "Làm sao đổi mật khẩu email?"),
                ("ASSISTANT", "Bạn vào portal.company.com..."),
            ],
        )
        assert "Người dùng: Làm sao đổi mật khẩu email?" in user
        assert "Trợ lý: Bạn vào portal.company.com..." in user
        assert "Còn cách nào khác không?" in user


class TestEvalFixtures:
    """Kiểm tra tập đánh giá hợp lệ — bộ test này hỏng nghĩa là fixture bị sửa sai."""

    def test_rag_eval_hop_le(self):
        rows = [
            json.loads(line)
            for line in (FIXTURES / "rag_eval.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(rows) == 10
        for row in rows:
            assert {"id", "question", "expect_answer"} <= row.keys()

    def test_rag_eval_co_du_cau_phai_tu_choi(self):
        """★ Nhóm câu quan trọng nhất của tập đánh giá.

        Chatbot IT bịa ra các bước thao tác sai có thể khiến nhân viên làm
        hỏng máy hoặc làm lộ thông tin. Mục tiêu: từ chối đúng 100%.
        """
        rows = [
            json.loads(line)
            for line in (FIXTURES / "rag_eval.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        must_refuse = [r for r in rows if not r["expect_answer"]]
        assert len(must_refuse) >= 3, "Cần ít nhất 3 câu ngoài phạm vi tài liệu"

    def test_classification_eval_co_du_ba_muc_do_kho(self):
        rows = [
            json.loads(line)
            for line in (FIXTURES / "classification_eval.jsonl")
            .read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        # Ngưỡng TỐI THIỂU theo docs/design/07 §5.1, không phải con số cố định:
        # ghim `== 10` khiến chính bộ test chặn việc bổ sung ca mới, mà bổ
        # sung ca mới là cách duy nhất để tập đánh giá theo kịp thực tế.
        assert len(rows) >= 50, "Tập đánh giá cần ít nhất 50 ca (docs/design/07 §5.1)"

        difficulties = {r["difficulty"] for r in rows}
        assert difficulties == {"clear", "ambiguous", "tricky"}

        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids)), "Có ID trùng nhau trong tập đánh giá"

        # Ca mơ hồ và ca lắt léo mới là thứ phân biệt được mô hình tốt với mô
        # hình chỉ học thuộc từ khoá. Tập chỉ toàn ca rõ ràng luôn cho điểm đẹp.
        assert sum(1 for r in rows if r["difficulty"] == "ambiguous") >= 10
        assert sum(1 for r in rows if r["difficulty"] == "tricky") >= 5

        valid = {"network", "hardware", "software", "account",
                 "access", "email", "security", "other"}
        assert {r["expect_category"] for r in rows} <= valid
