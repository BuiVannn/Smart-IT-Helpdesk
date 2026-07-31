import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { AuthProvider, useAuth } from '@/features/auth/AuthProvider'
import { LoginPage } from '@/features/auth/LoginPage'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { ChatPage } from '@/features/chat/ChatPage'
import { CreateTicketPage } from '@/features/tickets/CreateTicketPage'
import { MyTicketsPage } from '@/features/tickets/MyTicketsPage'
import { QueuePage } from '@/features/tickets/QueuePage'
import { TicketDetailPage } from '@/features/tickets/TicketDetailPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      retry: (failureCount, error) => {
        // Chỉ retry lỗi mạng/5xx, không retry 4xx
        const status = (error as { status?: number })?.status
        if (status && status < 500) return false
        return failureCount < 2
      },
    },
  },
})

/** Điều hướng theo vai trò — mỗi vai trò có màn hình mặc định khác nhau */
function HomeRedirect() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (user.role === 'ADMIN') return <Navigate to="/dashboard" replace />
  if (user.role === 'IT_AGENT') return <Navigate to="/queue" replace />
  return <Navigate to="/my-tickets" replace />
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center">
      <h2 className="text-lg font-medium text-slate-700">{title}</h2>
      <p className="mt-1 text-sm text-slate-500">Màn hình này sẽ được xây dựng ở task tiếp theo.</p>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<HomeRedirect />} />

              <Route path="/my-tickets" element={<MyTicketsPage />} />
              {/* "/tickets/new" phải đứng TRƯỚC "/tickets/:id", nếu không
                  react-router khớp "new" như một id và gọi API với id sai */}
              <Route path="/tickets/new" element={<CreateTicketPage />} />
              <Route path="/tickets/:id" element={<TicketDetailPage />} />
              <Route
                path="/queue"
                element={
                  <ProtectedRoute roles={['IT_AGENT', 'ADMIN']}>
                    <QueuePage />
                  </ProtectedRoute>
                }
              />

              <Route path="/chat" element={<ChatPage />} />
              <Route path="/kb" element={<Placeholder title="Tài liệu hướng dẫn" />} />
              <Route path="/dashboard" element={<Placeholder title="Báo cáo" />} />
              <Route
                path="/admin/users"
                element={
                  <ProtectedRoute roles={['ADMIN']}>
                    <Placeholder title="Quản trị người dùng" />
                  </ProtectedRoute>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
