/**
 * Báo cáo tổng hợp điểm hài lòng (US-42 — F8).
 *
 * Trả lời "chất lượng dịch vụ đang thế nào" tách theo Agent, loại sự cố và
 * tháng. Chỉ Admin xem được (backend `require_admin`).
 *
 * ⚠️ avgScore / responseRate null ≠ 0:
 *   null  = chưa đủ dữ liệu để nói (chưa có đánh giá / chưa có ticket đóng)
 *   0     = có dữ liệu nhưng bằng 0
 * Các hàm hiển thị bên dưới giữ nguyên null thành "—" — không tự ý đổi thành 0.
 */

import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { defaultRange, reportsApi } from '@/api/reports'
import { Button, EmptyState, ErrorState, LoadingBlock } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { SatisfactionBucket } from '@/types'

// ── Hằng số ──────────────────────────────────────────────────────────────────

const RANGES = [
  { days: 7, label: '7 ngày' },
  { days: 30, label: '30 ngày' },
  { days: 90, label: '90 ngày' },
]

const STARS = [1, 2, 3, 4, 5]

// ── Helper ────────────────────────────────────────────────────────────────────

/** null → "—"; số → "x.x" (điểm trung bình). Đừng viết `value ?? 0`. */
function score(value: number | null): string {
  return value === null ? '—' : value.toFixed(2)
}

/** null → "—"; số → "xx.x%". */
function percent(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

/** Phân bố điểm 1-5 dạng { "1": n, ... } → mảng để vẽ biểu đồ. */
function distributionData(bucket: SatisfactionBucket) {
  return STARS.map((s) => ({
    star: `${s}★`,
    count: bucket.distribution[String(s)] ?? 0,
  }))
}

function starsText(value: number | null): string {
  return value === null ? '—' : '★'.repeat(Math.round(value))
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string | number
  hint?: string
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
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

/** Bảng chung cho các nhóm bucket — cột điểm, phân bố sao, số đánh giá. */
function BucketTable({ buckets }: { buckets: SatisfactionBucket[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[500px] text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
            <th className="pb-2 font-medium">Nhóm</th>
            <th className="pb-2 font-medium">Điểm TB</th>
            <th className="pb-2 text-right font-medium">Phân bố</th>
            <th className="pb-2 text-right font-medium">Số đánh giá</th>
            <th className="pb-2 text-right font-medium">Ticket đã đóng</th>
            <th className="pb-2 text-right font-medium">Tỉ lệ phản hồi</th>
          </tr>
        </thead>
        <tbody>
          {buckets.map((b) => (
            <tr key={b.key} className="border-b border-slate-100 last:border-0">
              <td className="py-2 font-medium text-slate-800">{b.label}</td>
              <td className="py-2 text-amber-500">{starsText(b.avgScore)}</td>
              <td className="py-2 text-right tabular-nums text-slate-500">
                {STARS.map((s) => (
                  <span key={s} className="ml-2">
                    {s}★:{b.distribution[String(s)] ?? 0}
                  </span>
                ))}
              </td>
              <td className="py-2 text-right tabular-nums text-slate-700">{b.ratingCount}</td>
              <td className="py-2 text-right tabular-nums text-slate-700">{b.closedTickets}</td>
              <td className="py-2 text-right tabular-nums font-medium text-slate-900">
                {percent(b.responseRate)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Trang chính ───────────────────────────────────────────────────────────────

export function SatisfactionReportPage() {
  const [days, setDays] = useState(30)
  const { from, to } = useMemo(() => defaultRange(days), [days])

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['reports', 'satisfaction', from, to],
    queryFn: () => reportsApi.satisfaction(from, to),
  })

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) return <LoadingBlock label="Đang tổng hợp điểm hài lòng…" />

  // ── Lỗi (403, mạng, v.v.) ────────────────────────────────────────────────
  if (isError) {
    return <ErrorState error={error} onRetry={() => void refetch()} />
  }

  const d = data!

  // ── Chưa có đánh giá nào ────────────────────────────────────────────────
  if (d.overall.ratingCount === 0) {
    return (
      <div className="space-y-5">
        <PageHeader days={days} setDays={setDays} refetch={() => void refetch()} from={d.from} to={d.to} />
        <EmptyState
          title="Chưa có đánh giá nào trong khoảng thời gian này"
          hint="Khi nhân viên đánh giá ticket đã xử lý xong, số liệu sẽ xuất hiện ở đây."
        />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <PageHeader days={days} setDays={setDays} refetch={() => void refetch()} from={d.from} to={d.to} />

      {/* ── Hàng thẻ số tổng quan ──────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Điểm trung bình"
          value={score(d.overall.avgScore)}
          hint={`${d.overall.ratingCount} đánh giá`}
        />
        <StatCard
          label="Số đánh giá"
          value={d.overall.ratingCount}
          hint={`trên ${d.overall.closedTickets} ticket đã đóng`}
        />
        <StatCard
          label="Tỉ lệ phản hồi"
          value={percent(d.overall.responseRate)}
          hint="số đánh giá / ticket đã đóng"
        />
        <StatCard label="Ticket đã đóng" value={d.overall.closedTickets} />
      </div>

      {/* ── Theo Agent ──────────────────────────────────────────────────── */}
      <Panel
        title="Điểm hài lòng theo IT Agent"
        subtitle="Tỉ lệ phản hồi kèm điểm trung bình — một Agent điểm cao mà ít người đánh giá không đáng so sánh với Agent điểm thấp hơn nhưng nhiều phản hồi."
      >
        {d.byAgent.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">Chưa có dữ liệu theo Agent.</p>
        ) : (
          <BucketTable buckets={d.byAgent} />
        )}
      </Panel>

      {/* ── Theo loại sự cố ─────────────────────────────────────────────── */}
      <Panel
        title="Điểm hài lòng theo loại sự cố"
        subtitle="Loại nào điểm thấp là nơi cần cải thiện dịch vụ trước."
      >
        {d.byCategory.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">Chưa có dữ liệu theo loại.</p>
        ) : (
          <BucketTable buckets={d.byCategory} />
        )}
      </Panel>

      {/* ── Phân bố điểm tổng thể ───────────────────────────────────────── */}
      <Panel
        title="Phân bố điểm tổng thể"
        subtitle="Số đánh giá theo từng mức sao — giúp nhìn rõ khách hàng đang chấm cao hay thấp."
      >
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={distributionData(d.overall)}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="star" fontSize={11} stroke="#94a3b8" />
            <YAxis allowDecimals={false} fontSize={11} stroke="#94a3b8" />
            <Tooltip
              formatter={(v) => [String(v), 'Số đánh giá']}
            />
            <Legend fontSize={11} />
            <Bar dataKey="count" name="Số đánh giá" fill="#2563eb" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Panel>

      {/* ── Theo tháng ──────────────────────────────────────────────────── */}
      <Panel
        title="Điểm hài lòng theo tháng"
        subtitle="So sánh chất lượng dịch vụ giữa các tháng."
      >
        {d.byMonth.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">Chưa có dữ liệu theo tháng.</p>
        ) : (
          <BucketTable buckets={d.byMonth} />
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
  from,
  to,
}: {
  days: number
  setDays: (d: number) => void
  refetch: () => void
  from: string
  to: string
}) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Điểm hài lòng sau xử lý</h1>
        <p className="text-xs text-slate-500">
          {new Date(from).toLocaleDateString('vi-VN')} –{' '}
          {new Date(to).toLocaleDateString('vi-VN')}
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
