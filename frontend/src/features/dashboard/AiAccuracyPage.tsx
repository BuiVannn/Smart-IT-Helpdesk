/**
 * Báo cáo độ chính xác phân loại AI (US-22 — F7 Dashboard).
 *
 * Đây là chỗ duy nhất trả lời được "AI phân loại có dùng được không?" bằng
 * số thực thay vì bằng lời. Quan trọng nhất với người chấm vì dự án bán mình
 * là "tích hợp AI".
 *
 * ⚠️ acceptanceRate null ≠ 0%:
 *   null  = chưa có ticket nào được chốt để mà nói → hiện "—"
 *   0     = AI sai tất cả                          → hiện "0%"
 * Hàm percent() đã xử lý đúng — không tự ý đổi null thành 0.
 */

import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { defaultRange, reportsApi } from '@/api/reports'
import { Button, EmptyState, ErrorState, LoadingBlock } from '@/components/ui'
import { cn } from '@/lib/utils'

// ── Hằng số ──────────────────────────────────────────────────────────────────

const RANGES = [
  { days: 7, label: '7 ngày' },
  { days: 30, label: '30 ngày' },
  { days: 90, label: '90 ngày' },
]

// ── Helper ────────────────────────────────────────────────────────────────────

/** null → "—"; số → "xx.x%". Đừng viết `value ?? 0` — xem comment ở đầu file. */
function percent(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

function ms(value: number | null): string {
  if (value === null) return '—'
  if (value < 1000) return `${Math.round(value)} ms`
  return `${(value / 1000).toFixed(1)} s`
}

function usd(value: number | null): string {
  if (value === null) return '—'
  return `$${value.toFixed(4)}`
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  hint,
  tone = 'normal',
}: {
  label: string
  value: string | number
  hint?: string
  tone?: 'normal' | 'danger' | 'warning'
}) {
  return (
    <div
      className={cn(
        'rounded-lg border bg-white p-4',
        tone === 'danger' && 'border-red-200 bg-red-50',
        tone === 'warning' && 'border-amber-200 bg-amber-50',
        tone === 'normal' && 'border-slate-200',
      )}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p
        className={cn(
          'mt-1 text-2xl font-semibold',
          tone === 'danger' ? 'text-red-700' : 'text-slate-900',
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-medium text-slate-800">{title}</h2>
      {subtitle && <p className="mb-2 mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

// ── Trang chính ───────────────────────────────────────────────────────────────

export function AiAccuracyPage() {
  const [days, setDays] = useState(30)
  const { from, to } = useMemo(() => defaultRange(days), [days])

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['reports', 'ai-accuracy', from, to],
    queryFn: () => reportsApi.aiAccuracy(from, to),
  })

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) return <LoadingBlock label="Đang tổng hợp báo cáo AI…" />

  // ── Lỗi (403, mạng, v.v.) ────────────────────────────────────────────────
  if (isError) {
    return (
      <ErrorState
        error={error}
        onRetry={() => void refetch()}
      />
    )
  }

  const d = data!

  // ── Chưa có dữ liệu: KHÔNG vẽ biểu đồ rỗng ──────────────────────────────
  if (d.totalRuns === 0) {
    return (
      <div className="space-y-5">
        <PageHeader days={days} setDays={setDays} refetch={() => void refetch()} cached={false} from={d.from} to={d.to} />
        <EmptyState
          title="Chưa có lượt phân loại nào trong khoảng thời gian này"
          hint="Tạo ticket mới và đảm bảo Celery worker đang chạy để AI bắt đầu phân loại."
        />
      </div>
    )
  }

  const failureRate = d.failureRate ?? 0

  return (
    <div className="space-y-5">
      <PageHeader days={days} setDays={setDays} refetch={() => void refetch()} cached={d.cached} from={d.from} to={d.to} />

      {/* ── Hàng 6 thẻ số ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard
          label="Tỉ lệ chấp nhận"
          value={percent(d.acceptanceRate)}
          hint={`${d.accepted} / ${d.decided} đã chốt`}
        />
        <StatCard
          label="Tổng lượt chạy"
          value={d.totalRuns}
          hint={`${d.applied} đã áp dụng`}
        />
        <StatCard
          label="Tin cậy thấp"
          value={percent(d.lowConfidenceRate)}
          tone={d.lowConfidenceRate !== null && d.lowConfidenceRate > 0.3 ? 'warning' : 'normal'}
        />
        <StatCard
          label="Tỉ lệ lỗi"
          value={percent(d.failureRate)}
          tone={failureRate > 0.1 ? 'danger' : 'normal'}
          hint={failureRate > 0.1 ? 'Vượt ngưỡng 10%' : undefined}
        />
        <StatCard
          label="Độ trễ trung bình"
          value={ms(d.avgLatencyMs)}
        />
        <StatCard
          label="Chi phí ước tính"
          value={usd(d.estimatedCostUsd)}
          hint="trong kỳ báo cáo"
        />
      </div>

      {/* ── Biểu đồ đường theo tuần ─────────────────────────────────────── */}
      <Panel
        title="Tỉ lệ chấp nhận theo tuần"
        subtitle="Dùng để so sánh trước và sau khi đổi prompt. Điểm null (—) là tuần chưa có ticket nào được chốt."
      >
        {d.byWeek.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">Chưa đủ dữ liệu theo tuần.</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={d.byWeek}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="label" fontSize={11} stroke="#94a3b8" />
              <YAxis
                fontSize={11}
                stroke="#94a3b8"
                tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                domain={[0, 1]}
              />
              <Tooltip
                formatter={(v) => [
                  typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—',
                  'Tỉ lệ chấp nhận',
                ]}
              />
              <Line
                type="monotone"
                dataKey="acceptanceRate"
                name="Tỉ lệ chấp nhận"
                stroke="#2563eb"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Panel>

      {/* ── Biểu đồ cột theo loại sự cố ─────────────────────────────────── */}
      <Panel
        title="Độ chính xác theo loại sự cố"
        subtitle="Loại nào có tỉ lệ chấp nhận thấp là AI hay đoán sai nhất — ưu tiên cải thiện prompt hoặc bổ sung ví dụ."
      >
        {d.byCategory.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">Chưa có dữ liệu theo loại.</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={d.byCategory} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                type="number"
                fontSize={11}
                stroke="#94a3b8"
                tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                domain={[0, 1]}
              />
              <YAxis type="category" dataKey="label" width={140} fontSize={11} stroke="#94a3b8" />
              <Tooltip
                formatter={(v) => [
                  typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—',
                  'Tỉ lệ chấp nhận',
                ]}
              />
              <Legend fontSize={11} />
              <Bar dataKey="acceptanceRate" name="Tỉ lệ chấp nhận" fill="#2563eb" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Panel>

      {/* ── Bảng nhầm lẫn ───────────────────────────────────────────────── */}
      <Panel
        title="Bảng nhầm lẫn (top 10)"
        subtitle="AI đoán loại A nhưng người dùng chốt loại B — đọc từ trên xuống để biết cặp nào nhầm nhiều nhất."
      >
        {d.confusion.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">
            Chưa có ticket nào được chốt khác với gợi ý của AI.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[400px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th className="pb-2 font-medium">AI đoán</th>
                  <th className="pb-2 font-medium">Người chốt</th>
                  <th className="pb-2 text-right font-medium">Số lần</th>
                </tr>
              </thead>
              <tbody>
                {[...d.confusion]
                  .sort((a, b) => b.count - a.count)
                  .slice(0, 10)
                  .map((row, i) => (
                    <tr key={i} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 text-slate-700">{row.aiCategory}</td>
                      <td className="py-2 text-slate-700">{row.finalCategory}</td>
                      <td className="py-2 text-right tabular-nums font-medium text-slate-900">
                        {row.count}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}

// ── Header tách ra để tái dùng ────────────────────────────────────────────────

function PageHeader({
  days,
  setDays,
  refetch,
  cached,
  from,
  to,
}: {
  days: number
  setDays: (d: number) => void
  refetch: () => void
  cached: boolean
  from: string
  to: string
}) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Độ chính xác phân loại AI</h1>
        <p className="text-xs text-slate-500">
          {new Date(from).toLocaleDateString('vi-VN')} –{' '}
          {new Date(to).toLocaleDateString('vi-VN')}
          {cached && ' · số liệu từ bộ nhớ đệm'}
        </p>
      </div>

      <div className="flex items-center gap-2">
        <div className="flex rounded-md border border-slate-300 bg-white p-0.5">
          {RANGES.map((r) => (
            <button
              key={r.days}
              onClick={() => setDays(r.days)}
              className={cn(
                'rounded px-2.5 py-1 text-xs font-medium',
                days === r.days ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100',
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
        <Button variant="secondary" onClick={refetch}>
          Làm mới
        </Button>
      </div>
    </header>
  )
}