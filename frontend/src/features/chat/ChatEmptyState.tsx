/**
 * Màn hình khi chưa có câu hỏi nào.
 *
 * ★ Gợi ý câu hỏi CÓ CHỦ ĐÍCH: người dùng đứng trước ô nhập trống thường
 * không biết trợ lý này biết gì. Bốn câu dưới đây đều khớp với bài viết có
 * thật trong kho tài liệu, nên bấm vào là chắc chắn nhận được câu trả lời có
 * trích dẫn — ấn tượng đầu tiên quyết định người dùng có quay lại hay không.
 */
const SUGGESTIONS = [
  'Làm sao để đổi mật khẩu email công ty?',
  'Máy tính của tôi chạy chậm, tự kiểm tra thế nào?',
  'Cách kết nối WiFi công ty trên laptop?',
  'Tôi nghi ngờ nhận được email lừa đảo, phải làm gì?',
]

export function ChatEmptyState({ onPick }: { onPick: (question: string) => void }) {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-10 text-center">
      <span
        aria-hidden="true"
        className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg
                   border border-slate-200 bg-white text-lg"
      >
        💬
      </span>

      <h2 className="text-base font-semibold text-slate-900">
        Trợ lý ảo hỗ trợ IT
      </h2>
      <p className="mt-1.5 max-w-md text-sm leading-relaxed text-slate-600">
        Hỏi trước khi tạo yêu cầu — nhiều sự cố có thể tự xử lý trong vài phút.
        Trợ lý chỉ trả lời dựa trên tài liệu hướng dẫn nội bộ và luôn dẫn nguồn.
      </p>

      <div className="mt-6 w-full">
        <p className="mb-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400">
          Thử hỏi
        </p>
        <ul className="space-y-2">
          {SUGGESTIONS.map((q) => (
            <li key={q}>
              <button
                onClick={() => onPick(q)}
                className="w-full rounded-md border border-slate-200 bg-white px-3.5 py-2.5
                           text-left text-sm text-slate-700 transition
                           hover:border-slate-300 hover:bg-slate-50
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {q}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-6 text-xs leading-relaxed text-slate-400">
        Không tìm thấy hướng dẫn phù hợp? Trợ lý sẽ nói thẳng là chưa có, và
        gợi ý bạn tạo yêu cầu để đội IT xử lý trực tiếp.
      </p>
    </div>
  )
}
