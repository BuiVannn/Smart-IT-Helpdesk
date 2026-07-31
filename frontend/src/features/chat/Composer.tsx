import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui'

const NEAR_LIMIT_RATIO = 0.9

/**
 * Ô nhập câu hỏi.
 *
 * Enter gửi, Shift+Enter xuống dòng — quy ước quen thuộc của mọi ứng dụng
 * nhắn tin. Làm ngược lại thì người dùng gửi nhầm câu hỏi dở dang suốt.
 */
export function Composer({
  onSend,
  onStop,
  isStreaming,
  maxLength,
  disabled,
}: {
  onSend: (text: string) => void
  onStop: () => void
  isStreaming: boolean
  maxLength: number
  disabled?: boolean
}) {
  const [value, setValue] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  // Ô nhập cao theo nội dung, tối đa ~5 dòng. Ô cố định một dòng khiến người
  // dùng không đọc lại được câu hỏi dài mình vừa gõ.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`
  }, [value])

  // Trả lời xong thì con trỏ quay lại ô nhập, không bắt người dùng bấm chuột
  useEffect(() => {
    if (!isStreaming) ref.current?.focus()
  }, [isStreaming])

  function submit() {
    const text = value.trim()
    if (!text || isStreaming || disabled) return
    onSend(text)
    setValue('')
  }

  const remaining = maxLength - value.length
  const nearLimit = value.length > maxLength * NEAR_LIMIT_RATIO

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      className="border-t border-slate-200 bg-white p-3"
    >
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label htmlFor="chat-input" className="sr-only">
            Câu hỏi cho trợ lý ảo
          </label>
          <textarea
            id="chat-input"
            ref={ref}
            rows={1}
            value={value}
            maxLength={maxLength}
            disabled={disabled}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
            placeholder="Ví dụ: Làm sao để đổi mật khẩu email công ty?"
            className="w-full resize-none rounded-md border border-slate-300 px-3 py-2
                       text-sm leading-relaxed focus:border-blue-500 focus:outline-none
                       focus:ring-1 focus:ring-blue-500 disabled:bg-slate-50"
          />
        </div>

        {isStreaming ? (
          <Button type="button" variant="secondary" onClick={onStop}>
            Dừng
          </Button>
        ) : (
          <Button type="submit" disabled={!value.trim() || disabled}>
            Gửi
          </Button>
        )}
      </div>

      <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-400">
        <span>Enter để gửi · Shift + Enter để xuống dòng</span>
        {/* Chỉ hiện khi sắp chạm giới hạn — bộ đếm luôn hiện là nhiễu thị giác */}
        {nearLimit && (
          <span className={remaining < 0 ? 'text-red-600' : 'text-amber-600'}>
            còn {remaining} ký tự
          </span>
        )}
      </div>
    </form>
  )
}
