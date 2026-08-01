/**
 * Dashboard vận hành (F7 — US-37, US-38, US-39, US-40).
 *
 * Đây là màn hình mặc định của Admin, nên nó phải trả lời được câu hỏi đầu
 * tiên của một người quản lý trong vòng ba giây: "có gì đang cháy không?".
 * Vì vậy hàng thẻ số đứng trên cùng và thẻ "trễ hạn" luôn đổi màu đỏ khi
 * khác 0 — biểu đồ đẹp nhưng phải cuộn xuống mới thấy thì không dùng để
 * quyết định được.
 */

import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { defaultRange, reportsApi } from '@/api/reports'
import { Button, ErrorState, LoadingBlock } from '@/components/ui'
import { cn } from '@/lib/utils'

const RANGES = [
  { days: 7, label: '7 ngày' },
  { days: 30, label: '30 ngày' },
  { days: 90, label: '90 ngày' },
]

/** Màu theo mức ưu tiên — giữ đúng bảng màu đã dùng ở badge của ticket, để
 *  người dùng không phải học hai hệ màu cho cùng một khái niệm. */
const PRIORITY_COLORS: Record<string, string> = {
  URGENT: '#dc2626',
  HIGH: '#ea580c',
  MEDIUM: '#2563eb',
  LOW: '#64748b',
}

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

function Panel({ title, subtitle, children }: {
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

/** Phút → chuỗi người đọc được. `null` giữ nguyên là gạch ngang, KHÔNG đổi
 *  thành 0: "chưa có dữ liệu" khác hẳn "xử lý xong trong 0 phút". */
function minutes(value: number | null): string {
  if (value === null) return '—'
  if (value < 60) return `${value} phút`
  if (value < 1440) return `${(value / 60).toFixed(1)} giờ`
  return `${(value / 1440).toFixed(1)} ngày`
}

function percent(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

export function DashboardPage() {
  const [days, setDays] = useState(30)
  const [exporting, setExporting] = useState(false)
  const { from, to } = useMemo(() => defaultRange(days), [days])

  const overview = useQuery({
    queryKey: ['reports', 'overview', from, to],
    queryFn: () => reportsApi.overview(from, to),
  })
  const durations = useQuery({
    queryKey: ['reports', 'resolution-time', from, to],
    queryFn: () => reportsApi.resolutionTime(from, to),
  })
  const workload = useQuery({
    queryKey: ['reports', 'agent-workload', from, to],
    queryFn: () => reportsApi.agentWorkload(from, to),
  })

  const exportCsv = async () => {
    setExporting(true)
    try {
      await reportsApi.exportCsv(from, to)
    } finally {
      setExporting(false)
    }
  }

  if (overview.isLoading) return <LoadingBlock label="Đang tổng hợp báo cáo…" />
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />

  const data = overview.data!

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Báo cáo vận hành</h1>
          <p className="text-xs text-slate-500">
            {new Date(data.from).toLocaleDateString('vi-VN')} –{' '}
            {new Date(data.to).toLocaleDateString('vi-VN')}
            {/* Nói rõ số đang xem là số cache: người dùng vừa đóng một ticket
                mà bảng không đổi sẽ tưởng hệ thống hỏng. */}
            {data.cached && ' · số liệu từ bộ nhớ đệm'}
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
          <Button variant="secondary" onClick={() => void overview.refetch()}>
            Làm mới
          </Button>
          <Button variant="secondary" loading={exporting} onClick={() => void exportCsv()}>
            Xuất CSV
          </Button>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard label="Tổng ticket" value={data.total} />
        <StatCard label="Đang mở" value={data.openTotal} />
        <StatCard label="Đã xử lý" value={data.resolvedTotal} />
        <StatCard
          label="Trễ hạn SLA"
          value={data.breachedTotal}
          hint={`Tỉ lệ ${percent(data.breachRate)}`}
          tone={data.breachedTotal > 0 ? 'danger' : 'normal'}
        />
        <StatCard
          label="Chưa có người xử lý"
          value={data.unassignedTotal}
          tone={data.unassignedTotal > 0 ? 'warning' : 'normal'}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Panel title="Ticket tạo mới theo ngày">
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={data.daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" fontSize={11} stroke="#94a3b8" />
                <YAxis allowDecimals={false} fontSize={11} stroke="#94a3b8" />
                <Tooltip formatter={(v) => [`${v} ticket`, 'Số lượng']} />
                <Line
                  type="monotone"
                  dataKey="count"
                  name="Ticket"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </Panel>
        </div>

        <Panel title="Theo mức ưu tiên">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={data.byPriority}
                dataKey="count"
                nameKey="label"
                innerRadius={45}
                outerRadius={80}
                paddingAngle={2}
              >
                {data.byPriority.map((bucket) => (
                  <Cell key={bucket.key} fill={PRIORITY_COLORS[bucket.key] ?? '#94a3b8'} />
                ))}
              </Pie>
              <Tooltip />
              <Legend fontSize={11} />
            </PieChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Theo trạng thái">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.byStatus}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="label" fontSize={11} stroke="#94a3b8" interval={0} angle={-15} dy={8} />
              <YAxis allowDecimals={false} fontSize={11} stroke="#94a3b8" />
              <Tooltip />
              <Bar dataKey="count" name="Ticket" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Theo loại sự cố">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.byCategory.slice(0, 8)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" allowDecimals={false} fontSize={11} stroke="#94a3b8" />
              <YAxis type="category" dataKey="label" width={120} fontSize={11} stroke="#94a3b8" />
              <Tooltip />
              <Bar dataKey="count" name="Ticket" fill="#0ea5e9" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel
        title="Thời gian xử lý theo loại sự cố"
        subtitle="Trung vị (p50) và p90 — không dùng trung bình, vì một ticket bị bỏ quên sẽ kéo lệch cả bảng. Đã trừ thời gian chờ người yêu cầu phản hồi."
      >
        {durations.isLoading ? (
          <LoadingBlock />
        ) : durations.data?.rows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th className="pb-2 font-medium">Loại sự cố</th>
                  <th className="pb-2 text-right font-medium">Ticket</th>
                  <th className="pb-2 text-right font-medium">Phản hồi p50</th>
                  <th className="pb-2 text-right font-medium">Phản hồi p90</th>
                  <th className="pb-2 text-right font-medium">Xử lý p50</th>
                  <th className="pb-2 text-right font-medium">Xử lý p90</th>
                </tr>
              </thead>
              <tbody>
                {durations.data.rows.map((row) => (
                  <tr key={row.key} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 text-slate-800">{row.label}</td>
                    <td className="py-2 text-right tabular-nums text-slate-600">{row.tickets}</td>
                    <td className="py-2 text-right tabular-nums text-slate-600">
                      {minutes(row.firstResponseP50Minutes)}
                    </td>
                    <td className="py-2 text-right tabular-nums text-slate-600">
                      {minutes(row.firstResponseP90Minutes)}
                    </td>
                    <td className="py-2 text-right tabular-nums text-slate-600">
                      {minutes(row.resolutionP50Minutes)}
                    </td>
                    <td className="py-2 text-right tabular-nums text-slate-600">
                      {minutes(row.resolutionP90Minutes)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="py-6 text-center text-sm text-slate-500">
            Chưa có ticket nào được xử lý xong trong kỳ này.
          </p>
        )}
      </Panel>

      <Panel title="Khối lượng công việc theo IT Agent">
        {workload.isLoading ? (
          <LoadingBlock />
        ) : workload.data?.rows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th className="pb-2 font-medium">Nhân sự</th>
                  <th className="pb-2 text-right font-medium">Đang mở</th>
                  <th className="pb-2 text-right font-medium">Khẩn cấp</th>
                  <th className="pb-2 text-right font-medium">Xong trong kỳ</th>
                  <th className="pb-2 text-right font-medium">Thời gian TB</th>
                  <th className="pb-2 text-right font-medium">Tỉ lệ trễ</th>
                  <th className="pb-2 text-right font-medium">Hài lòng</th>
                </tr>
              </thead>
              <tbody>
                {workload.data.rows.map((row) => (
                  <tr key={row.agentId} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 text-slate-800">{row.agentName}</td>
                    <td className="py-2 text-right tabular-nums text-slate-600">
                      {row.openTickets}
                    </td>
                    <td
                      className={cn(
                        'py-2 text-right tabular-nums',
                        row.urgentOpen > 0 ? 'font-medium text-red-600' : 'text-slate-600',
                      )}
                    >
                      {row.urgentOpen}
                    </td>
                    <td className="py-2 text-right tabular-nums text-slate-600">
                      {row.resolvedInPeriod}
                    </td>
                    <td className="py-2 text-right tabular-nums text-slate-600">
                      {minutes(row.avgResolutionMinutes)}
                    </td>
                    <td
                      className={cn(
                        'py-2 text-right tabular-nums',
                        (row.slaBreachRate ?? 0) > 0 ? 'text-red-600' : 'text-slate-600',
                      )}
                    >
                      {percent(row.slaBreachRate)}
                    </td>
                    <td className="py-2 text-right tabular-nums text-slate-600">
                      {row.avgRating === null ? '—' : `${row.avgRating} ★ (${row.ratingCount})`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-slate-400">
              Cột “Hài lòng” sẽ có số khi F8 — đánh giá sau xử lý — được hoàn thiện.
            </p>
          </div>
        ) : (
          <p className="py-6 text-center text-sm text-slate-500">
            Chưa có IT Agent nào đang hoạt động.
          </p>
        )}
      </Panel>
    </div>
  )
}
