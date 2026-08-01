import { api } from '@/api/client'
import type { AdminUser, CreateUserInput, Department, Page, UserRole } from '@/types'

export interface UserFilters {
  q?: string
  role?: UserRole | ''
  isActive?: boolean | ''
  sortBy?: string
  sortDir?: 'asc' | 'desc'
  page?: number
}

function toQuery(filters: UserFilters): string {
  const params = new URLSearchParams()
  params.set('page', String(filters.page ?? 1))
  params.set('pageSize', '20')
  // Bỏ qua chuỗi rỗng: `?role=` sẽ bị Pydantic từ chối vì '' không phải một
  // giá trị hợp lệ của enum, và cả màn hình sẽ đỏ chỉ vì người dùng chọn
  // "Tất cả" trong ô lọc.
  if (filters.q) params.set('q', filters.q)
  if (filters.role) params.set('role', filters.role)
  if (filters.isActive !== '' && filters.isActive !== undefined) {
    params.set('isActive', String(filters.isActive))
  }
  if (filters.sortBy) params.set('sortBy', filters.sortBy)
  if (filters.sortDir) params.set('sortDir', filters.sortDir)
  return params.toString()
}

export const adminApi = {
  listUsers: (filters: UserFilters) => api.get<Page<AdminUser>>(`/users?${toQuery(filters)}`),

  listDepartments: () => api.get<Department[]>('/users/departments'),

  createUser: (input: CreateUserInput) => api.post<AdminUser>('/users', input),

  updateUser: (id: string, input: Partial<CreateUserInput>) =>
    api.patch<AdminUser>(`/users/${id}`, input),

  activate: (id: string) => api.post<AdminUser>(`/users/${id}/activate`),

  deactivate: (id: string) => api.post<AdminUser>(`/users/${id}/deactivate`),
}
