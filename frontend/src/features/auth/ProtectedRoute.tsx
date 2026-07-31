import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from './AuthProvider'
import type { UserRole } from '@/types'

/**
 * ⚠️ Route guard chỉ là TRẢI NGHIỆM NGƯỜI DÙNG, KHÔNG PHẢI BẢO MẬT.
 * Bảo mật nằm ở backend. Frontend ẩn nút không phải để chặn, mà để không
 * hiển thị thứ người dùng không dùng được.
 */
export function ProtectedRoute({
  children,
  roles,
}: {
  children: ReactNode
  roles?: UserRole[]
}) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500">
        Đang tải…
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
