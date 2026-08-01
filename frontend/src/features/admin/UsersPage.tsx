/**
 * Quản trị người dùng (US-07).
 *
 * Màn hình này là con đường DUY NHẤT để hệ thống có IT Agent và Admin: đăng
 * ký tự phục vụ luôn tạo ra EMPLOYEE. Thiếu nó thì mô hình ba vai trò của
 * US-06 chỉ chạy được bằng cách sửa thẳng database.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { adminApi, type UserFilters } from '@/api/admin'
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Field,
  LoadingBlock,
  inputClass,
} from '@/components/ui'
import { useAuth } from '@/features/auth/AuthProvider'
import { useDebounced } from '@/hooks/useDebounced'
import { cn } from '@/lib/utils'
import type { AdminUser, UserRole } from '@/types'

const ROLE_LABELS: Record<UserRole, string> = {
  EMPLOYEE: 'Nhân viên',
  IT_AGENT: 'IT Agent',
  ADMIN: 'Quản trị viên',
}

const ROLE_STYLES: Record<UserRole, string> = {
  EMPLOYEE: 'bg-slate-100 text-slate-700',
  IT_AGENT: 'bg-blue-100 text-blue-700',
  ADMIN: 'bg-violet-100 text-violet-700',
}

const SORTABLE = [
  { key: 'fullName', label: 'Họ tên' },
  { key: 'email', label: 'Email' },
  { key: 'role', label: 'Vai trò' },
  { key: 'lastLoginAt', label: 'Đăng nhập gần nhất' },
  { key: 'createdAt', label: 'Ngày tạo' },
]

function formatDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString('vi-VN') : '—'
}

/* ── Biểu mẫu tạo người dùng ──────────────────────────────────────── */

function CreateUserForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    email: '',
    password: '',
    fullName: '',
    role: 'EMPLOYEE' as UserRole,
    departmentId: '',
  })

  const departments = useQuery({
    queryKey: ['admin', 'departments'],
    queryFn: adminApi.listDepartments,
  })

  const create = useMutation({
    mutationFn: () =>
      adminApi.createUser({
        ...form,
        // Chuỗi rỗng KHÔNG phải là UUID hợp lệ — gửi nguyên sẽ nhận 422.
        departmentId: form.departmentId || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      onDone()
    },
  })

  const set = (key: keyof typeof form) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }))

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        create.mutate()
      }}
      className="rounded-lg border border-slate-200 bg-white p-5"
    >
      <h2 className="mb-4 text-sm font-medium text-slate-800">Tạo tài khoản mới</h2>

      <div className="grid gap-x-4 md:grid-cols-2">
        <Field label="Họ và tên" htmlFor="fullName" required>
          <input
            id="fullName"
            className={inputClass}
            value={form.fullName}
            onChange={(e) => set('fullName')(e.target.value)}
            minLength={2}
            required
          />
        </Field>

        <Field label="Email" htmlFor="email" required>
          <input
            id="email"
            type="email"
            className={inputClass}
            value={form.email}
            onChange={(e) => set('email')(e.target.value)}
            required
          />
        </Field>

        <Field
          label="Mật khẩu khởi tạo"
          htmlFor="password"
          required
          hint="Tối thiểu 8 ký tự, có chữ hoa, chữ thường và chữ số"
        >
          <input
            id="password"
            type="password"
            className={inputClass}
            value={form.password}
            onChange={(e) => set('password')(e.target.value)}
            minLength={8}
            required
          />
        </Field>

        <Field label="Vai trò" htmlFor="role" required>
          <select
            id="role"
            className={inputClass}
            value={form.role}
            onChange={(e) => set('role')(e.target.value)}
          >
            {Object.entries(ROLE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Phòng ban" htmlFor="departmentId">
          <select
            id="departmentId"
            className={inputClass}
            value={form.departmentId}
            onChange={(e) => set('departmentId')(e.target.value)}
          >
            <option value="">— Không thuộc phòng ban nào —</option>
            {departments.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </Field>
      </div>

      {create.isError && (
        <p role="alert" className="mb-3 text-sm text-red-600">
          {(create.error as { message?: string })?.message ?? 'Không tạo được tài khoản'}
        </p>
      )}

      <div className="flex gap-2">
        <Button type="submit" loading={create.isPending}>
          Tạo tài khoản
        </Button>
        <Button type="button" variant="secondary" onClick={onDone}>
          Huỷ
        </Button>
      </div>
    </form>
  )
}

/* ── Trang chính ──────────────────────────────────────────────────── */

export function UsersPage() {
  const { user: me } = useAuth()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState<UserFilters>({
    role: '',
    isActive: '',
    sortBy: 'createdAt',
    sortDir: 'desc',
    page: 1,
  })

  const q = useDebounced(search)
  const query = useQuery({
    queryKey: ['admin', 'users', { ...filters, q }],
    queryFn: () => adminApi.listUsers({ ...filters, q }),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })

  const toggleActive = useMutation({
    mutationFn: (user: AdminUser) =>
      user.isActive ? adminApi.deactivate(user.id) : adminApi.activate(user.id),
    onSuccess: () => void invalidate(),
  })

  const changeRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: UserRole }) =>
      adminApi.updateUser(id, { role }),
    onSuccess: () => void invalidate(),
  })

  const sortBy = (key: string) =>
    setFilters((f) => ({
      ...f,
      sortBy: key,
      sortDir: f.sortBy === key && f.sortDir === 'asc' ? 'desc' : 'asc',
      page: 1,
    }))

  const patch = (next: Partial<UserFilters>) => setFilters((f) => ({ ...f, ...next, page: 1 }))

  // Lỗi từ backend (khoá chính mình, hạ vai trò Admin cuối cùng) hiện ở đây
  // thay vì trong một alert: người dùng cần đọc được lý do ngay cạnh bảng.
  const actionError =
    (toggleActive.error as { message?: string })?.message ??
    (changeRole.error as { message?: string })?.message

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-semibold text-slate-900">Quản trị người dùng</h1>
        {!showCreate && <Button onClick={() => setShowCreate(true)}>Tạo tài khoản</Button>}
      </header>

      {showCreate && <CreateUserForm onDone={() => setShowCreate(false)} />}

      <div className="flex flex-wrap gap-2">
        <input
          className={cn(inputClass, 'max-w-xs')}
          placeholder="Tìm theo tên hoặc email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className={cn(inputClass, 'max-w-[10rem]')}
          value={filters.role}
          onChange={(e) => patch({ role: e.target.value as UserRole | '' })}
        >
          <option value="">Mọi vai trò</option>
          {Object.entries(ROLE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          className={cn(inputClass, 'max-w-[10rem]')}
          value={String(filters.isActive)}
          onChange={(e) =>
            patch({ isActive: e.target.value === '' ? '' : e.target.value === 'true' })
          }
        >
          <option value="">Mọi trạng thái</option>
          <option value="true">Đang hoạt động</option>
          <option value="false">Đã khoá</option>
        </select>
      </div>

      {actionError && (
        <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {actionError}
        </p>
      )}

      {query.isLoading && <LoadingBlock />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.data && query.data.data.length === 0 && (
        <EmptyState title="Không tìm thấy người dùng nào" hint="Thử đổi từ khoá hoặc bộ lọc." />
      )}

      {query.data && query.data.data.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full min-w-[820px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                {SORTABLE.map((col) => (
                  <th key={col.key} className="px-4 py-2 font-medium">
                    <button
                      onClick={() => sortBy(col.key)}
                      className="inline-flex items-center gap-1 hover:text-slate-800"
                    >
                      {col.label}
                      {filters.sortBy === col.key && (
                        <span aria-hidden>{filters.sortDir === 'asc' ? '↑' : '↓'}</span>
                      )}
                    </button>
                  </th>
                ))}
                <th className="px-4 py-2 font-medium">Trạng thái</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {query.data.data.map((user) => {
                const isMe = user.id === me?.id
                return (
                  <tr key={user.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-2 text-slate-800">
                      {user.fullName}
                      {isMe && <span className="ml-1 text-xs text-slate-400">(bạn)</span>}
                    </td>
                    <td className="px-4 py-2 text-slate-600">{user.email}</td>
                    <td className="px-4 py-2">
                      <select
                        value={user.role}
                        disabled={changeRole.isPending}
                        onChange={(e) =>
                          changeRole.mutate({ id: user.id, role: e.target.value as UserRole })
                        }
                        className={cn(
                          'rounded-full border-0 px-2 py-0.5 text-xs font-medium',
                          ROLE_STYLES[user.role],
                        )}
                      >
                        {Object.entries(ROLE_LABELS).map(([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-2 text-slate-600">{formatDate(user.lastLoginAt)}</td>
                    <td className="px-4 py-2 text-slate-600">{formatDate(user.createdAt)}</td>
                    <td className="px-4 py-2">
                      <Badge
                        className={
                          user.isActive
                            ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-slate-200 text-slate-600'
                        }
                      >
                        {user.isActive ? 'Hoạt động' : 'Đã khoá'}
                      </Badge>
                    </td>
                    <td className="px-4 py-2 text-right">
                      <Button
                        variant={user.isActive ? 'secondary' : 'primary'}
                        className="px-2 py-1 text-xs"
                        // Nút tự khoá mình bị vô hiệu hoá ngay ở giao diện —
                        // backend vẫn chặn, nhưng để người dùng bấm rồi mới
                        // báo lỗi là thiết kế tệ.
                        disabled={isMe || toggleActive.isPending}
                        title={isMe ? 'Không thể tự khoá tài khoản của chính mình' : undefined}
                        onClick={() => toggleActive.mutate(user)}
                      >
                        {user.isActive ? 'Khoá' : 'Mở khoá'}
                      </Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {query.data && query.data.pagination.totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button
            variant="secondary"
            disabled={(filters.page ?? 1) <= 1}
            onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}
          >
            Trước
          </Button>
          <span className="text-slate-600">
            Trang {query.data.pagination.page} / {query.data.pagination.totalPages}
          </span>
          <Button
            variant="secondary"
            disabled={(filters.page ?? 1) >= query.data.pagination.totalPages}
            onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
          >
            Sau
          </Button>
        </div>
      )}
    </div>
  )
}
