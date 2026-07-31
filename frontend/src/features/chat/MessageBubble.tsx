import { Link } from 'react-router-dom'
import { CitationList } from './CitationList'
import { formatDateTime } from '@/lib/utils'
import type { Citation } from '@/types'

/** Bong bóng câu hỏi của người dùng — canh phải, nền đậm. */
export function UserBubble({ text, at }: { text: string; at?: string }) {
  return (
    <li className="flex justify-end">
      <div className="max-w-[85%] sm:max-w-[75%]">
        <div className="rounded-lg rounded-br-sm bg-slate-800 px-3.5 py-2.5 text-sm
                        leading-relaxed text-white">
          <p className="whitespace-pre-wrap break-words">{text}</p>
        </div>
        {at && (
          <p className="mt-1 text-right text-[11px] text-slate-400">
            {formatDateTime(at)}
          </p>
        )}
      </div>
    </li>
  )
}

/**
 * Câu trả lời của trợ lý.
 *
 * `isRefusal` đổi hẳn giao diện — nền hổ phách + đề nghị tạo yêu cầu hỗ trợ.
 * Trợ lý từ chối trả lời KHÔNG phải là lỗi và cũng không phải câu trả lời
 * bình thường: đó là lúc người dùng cần một lối đi tiếp, không phải một đoạn
 * văn xin lỗi trôi lẫn giữa các câu trả lời khác.
 */
export function AssistantBubble({
  text,
  citations,
  at,
  isStreaming = false,
  isRefusal = false,
  showCreateTicket = false,
}: {
  text: string
  citations: Citation[]
  at?: string
  isStreaming?: boolean
  isRefusal?: boolean
  showCreateTicket?: boolean
}) {
  return (
    <li className="flex justify-start">
      <div className="max-w-[92%] sm:max-w-[80%]">
        <div
          className={
            isRefusal
              ? 'rounded-lg rounded-bl-sm border border-amber-200 bg-amber-50 px-3.5 py-2.5'
              : 'rounded-lg rounded-bl-sm border border-slate-200 bg-white px-3.5 py-2.5'
          }
        >
          <p
            className={`whitespace-pre-wrap break-words text-sm leading-relaxed ${
              isRefusal ? 'text-amber-900' : 'text-slate-800'
            }`}
          >
            {text}
            {isStreaming && (
              // Con trỏ nhấp nháy: dấu hiệu duy nhất cho biết chữ vẫn đang
              // tới. Không có nó, người dùng không phân biệt được "đang gõ"
              // với "đã trả lời xong nhưng cụt".
              <span
                aria-hidden="true"
                className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5
                           animate-pulse bg-slate-500"
              />
            )}
          </p>

          <CitationList citations={citations} />

          {showCreateTicket && (
            <Link
              to="/tickets/new"
              className="mt-3 inline-flex items-center rounded-md bg-amber-700 px-3 py-1.5
                         text-xs font-medium text-white transition hover:bg-amber-800
                         focus:outline-none focus:ring-2 focus:ring-amber-600
                         focus:ring-offset-1"
            >
              Tạo yêu cầu hỗ trợ
            </Link>
          )}
        </div>
        {at && <p className="mt-1 text-[11px] text-slate-400">{formatDateTime(at)}</p>}
      </div>
    </li>
  )
}

/** Trạng thái "đang tra cứu" — trước khi token đầu tiên tới. */
export function SearchingBubble() {
  return (
    <li className="flex justify-start">
      <div
        className="flex items-center gap-2 rounded-lg rounded-bl-sm border border-slate-200
                   bg-white px-3.5 py-2.5 text-sm text-slate-500"
        role="status"
      >
        <span className="flex gap-1" aria-hidden="true">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400
                           [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400
                           [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
        </span>
        Đang tra cứu tài liệu nội bộ…
      </div>
    </li>
  )
}
