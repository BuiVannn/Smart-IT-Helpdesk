/**
 * Khối "AI đã nghĩ gì" trên trang chi tiết ticket (US-19, US-21).
 *
 * ★ CHỈ HIỆN VỚI IT AGENT VÀ ADMIN. Người gửi yêu cầu không cần biết model
 * nào chấm, độ trễ bao nhiêu — với họ chỉ có "loại sự cố là gì". Họ đã có
 * nhãn `AiStatusHint` ở đầu trang.
 *
 * ★ HIỆN CẢ KHI AI KHÔNG ÁP DỤNG. Đây chính là giá trị của tầng độ tin cậy
 * thấp: "AI nghĩ là Mạng nhưng chỉ chắc 45%" giúp Agent quyết định trong hai
 * giây. Giấu đi thì tầng LOW_CONFIDENCE trở thành vô dụng và ticket rơi vào
 * hàng chờ thủ công mà không mang theo thông tin nào.
 */

import { ApiError } from '@/api/client'
import { Badge, Button } from '@/components/ui'
import { PriorityBadge } from './badges'
import { useAiClassification, useReclassify } from './hooks'
import type { Ticket } from '@/types'

function ConfidenceMeter({ value }: { value: number }) {
  const percent = Math.round(value * 100)
  // Ngưỡng 60% khớp AI_CONFIDENCE_THRESHOLD ở backend. Màu KHÔNG phải thông
  // tin duy nhất — con số phần trăm luôn hiện kèm.
  const tone = value >= 0.6 ? 'bg-emerald-500' : 'bg-amber-500'
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full ${tone}`} style={{ width: `${percent}%` }} />
      </div>
      <span className="text-xs tabular-nums text-slate-600">{percent}%</span>
    </div>
  )
}

export function AiSuggestionPanel({ ticket }: { ticket: Ticket }) {
  const query = useAiClassification(ticket.id, true)
  const reclassify = useReclassify(ticket.id)
  const record = query.data

  if (query.isLoading) {
    return <Panel>{<p className="text-sm text-slate-500">Đang tải gợi ý…</p>}</Panel>
  }

  // `null` = worker chưa chạy xong. Không phải lỗi — hook tự hỏi lại.
  if (!record) {
    return (
      <Panel>
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-violet-500" />
          AI đang phân loại, thường mất vài giây…
        </p>
        <p className="mt-2 text-xs text-slate-400">
          Yêu cầu vẫn dùng được bình thường trong lúc chờ.
        </p>
      </Panel>
    )
  }

  // Không có category gợi ý = mọi tầng dự phòng đều không cho kết quả.
  if (!record.suggestedCategory) {
    return (
      <Panel>
        <p className="text-sm text-slate-700">AI không phân loại được yêu cầu này.</p>
        <p className="mt-1 text-xs text-slate-500">
          Vui lòng chọn loại sự cố thủ công. {record.errorMessage && 'Lý do kỹ thuật đã được ghi log.'}
        </p>
      </Panel>
    )
  }

  const suggestedIsCurrent = ticket.category?.id === record.suggestedCategory.id
  const canApply = !suggestedIsCurrent

  return (
    <Panel>
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="bg-violet-100 text-violet-800">
          {record.suggestedCategory.name}
        </Badge>
        {record.suggestedPriority && <PriorityBadge priority={record.suggestedPriority} />}
        {record.wasApplied ? (
          <Badge className="bg-emerald-50 text-emerald-700">Đã áp dụng</Badge>
        ) : (
          <Badge className="bg-amber-50 text-amber-800">Chỉ là gợi ý</Badge>
        )}
        {record.wasAccepted === false && (
          <Badge className="bg-slate-100 text-slate-600">Đã được sửa lại</Badge>
        )}
      </div>

      {record.confidence !== null && (
        <div className="mt-3">
          <ConfidenceMeter value={record.confidence} />
          {!record.wasApplied && record.confidence < 0.6 && (
            <p className="mt-1 text-xs text-amber-700">
              Dưới ngưỡng tin cậy nên hệ thống KHÔNG tự áp dụng — bạn quyết định.
            </p>
          )}
        </div>
      )}

      {record.reasoning && (
        <p className="mt-3 border-l-2 border-slate-200 pl-3 text-sm italic text-slate-600">
          {record.reasoning}
        </p>
      )}

      {canApply && (
        <div className="mt-3">
          <Button
            variant="secondary"
            loading={reclassify.isPending}
            onClick={() =>
              void reclassify
                .mutateAsync({
                  categoryId: record.suggestedCategory!.id,
                  version: ticket.version,
                })
                .catch(() => {})
            }
          >
            Áp dụng gợi ý này
          </Button>
          {reclassify.error && (
            <p role="alert" className="mt-2 text-xs text-red-700">
              {reclassify.error instanceof ApiError
                ? reclassify.error.message
                : 'Không áp dụng được gợi ý'}
            </p>
          )}
        </div>
      )}

      <p className="mt-3 text-xs text-slate-400">
        {record.modelName} · {record.promptVersion}
        {record.latencyMs !== null && ` · ${(record.latencyMs / 1000).toFixed(1)}s`}
      </p>
    </Panel>
  )
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-medium text-slate-700">Phân loại bằng AI</h2>
      {children}
    </section>
  )
}
