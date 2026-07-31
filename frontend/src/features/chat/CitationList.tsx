import { Link } from 'react-router-dom'
import type { Citation } from '@/types'

/**
 * Nguồn tham chiếu của câu trả lời (US-24).
 *
 * ★ Đây là thứ phân biệt trợ lý nội bộ với một chatbot chung chung: người
 * dùng kiểm chứng được câu trả lời đến từ tài liệu nào của công ty. Không có
 * nó, mọi câu trả lời đều phải tin bằng niềm tin.
 *
 * Điểm tương đồng CỐ TÌNH không hiển thị dạng số: "0.82" không có nghĩa gì
 * với người dùng cuối, chỉ có nghĩa với người hiệu chỉnh ngưỡng.
 */
export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null

  return (
    <div className="mt-3 border-t border-slate-200 pt-3">
      <p className="mb-1.5 text-xs font-medium text-slate-500">
        Dựa trên {citations.length} tài liệu nội bộ
      </p>
      <ul className="flex flex-wrap gap-1.5">
        {citations.map((c) => (
          <li key={`${c.articleId}-${c.rank}`}>
            <Link
              to={`/kb/${c.slug}`}
              className="inline-flex max-w-full items-center gap-1.5 rounded border
                         border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700
                         transition hover:border-slate-300 hover:bg-slate-100
                         focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <span
                aria-hidden="true"
                className="flex h-4 w-4 shrink-0 items-center justify-center rounded-sm
                           bg-slate-200 text-[10px] font-medium text-slate-600"
              >
                {c.rank}
              </span>
              <span className="truncate">{c.title}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
