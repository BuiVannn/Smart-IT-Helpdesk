import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthProvider'
import { NotificationBell } from '@/features/notifications/NotificationBell'
import { cn } from '@/lib/utils'
import type { UserRole } from '@/types'

interface NavItem {
  to: string
  label: string
  roles: UserRole[]
}

const NAV_ITEMS: NavItem[] = [
  { to: '/my-tickets', label: 'Yêu cầu của tôi', roles: ['EMPLOYEE', 'IT_AGENT', 'ADMIN'] },
  { to: '/queue', label: 'Hàng chờ xử lý', roles: ['IT_AGENT', 'ADMIN'] },
  { to: '/chat', label: 'Trợ lý ảo', roles: ['EMPLOYEE', 'IT_AGENT', 'ADMIN'] },
  { to: '/kb', label: 'Tài liệu hướng dẫn', roles: ['EMPLOYEE', 'IT_AGENT', 'ADMIN'] },
  { to: '/dashboard', label: 'Báo cáo', roles: ['ADMIN'] },
  { to: '/reports/ai-accuracy', label: 'Độ chính xác AI', roles: ['IT_AGENT', 'ADMIN'] },
  { to: '/reports/satisfaction', label: 'Hài lòng', roles: ['ADMIN'] },
  { to: '/my-ratings', label: 'Đánh giá của tôi', roles: ['IT_AGENT', 'ADMIN'] },
  { to: '/admin/users', label: 'Quản trị người dùng', roles: ['ADMIN'] },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const items = NAV_ITEMS.filter((i) => user && i.roles.includes(user.role))

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 border-r border-slate-200 bg-white md:block">
        <div className="px-5 py-4 text-sm font-semibold">Smart IT Helpdesk</div>
        <nav className="px-2">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'block rounded-md px-3 py-2 text-sm',
                  isActive
                    ? 'bg-blue-50 font-medium text-blue-700'
                    : 'text-slate-700 hover:bg-slate-100',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200
                           bg-white px-6 py-3">
          <Link to="/" className="text-sm font-medium md:hidden">Smart IT Helpdesk</Link>
          <div className="ml-auto flex items-center gap-4 text-sm">
            <NotificationBell />
            <span className="text-slate-600">{user?.fullName}</span>
            <button
              onClick={() => void logout()}
              className="text-slate-500 hover:text-slate-900"
            >
              Đăng xuất
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
