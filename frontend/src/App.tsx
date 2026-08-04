import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { UsersPage } from '@/features/admin/UsersPage'
import { AppLayout } from '@/components/layout/AppLayout'
import { LoadingBlock } from '@/components/ui'
import { AuthProvider, useAuth } from '@/features/auth/AuthProvider'
import { LoginPage } from '@/features/auth/LoginPage'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { ChatPage } from '@/features/chat/ChatPage'
import { KbListPage } from '@/features/knowledge/KbListPage'
import { KbDetailPage } from '@/features/knowledge/KbDetailPage'


/**
 * Dashboard tải theo yêu cầu vì `recharts` nặng ~500 kB.
 *
 * Chỉ Admin mở màn hình này, nhưng nếu import tĩnh thì MỌI người dùng — kể cả
 * nhân viên chỉ vào tạo một ticket — đều phải tải chỗ đó về trước khi thấy
 * được gì. Tách ra giữ gói chính nhẹ cho đúng nhóm đông nhất.
 */
const DashboardPage = lazy(() =>
  import('@/features/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })),
)
const AiAccuracyPage = lazy(() =>
  import('@/features/dashboard/AiAccuracyPage').then((m) => ({ default: m.AiAccuracyPage })),
)
import { CreateTicketPage } from '@/features/tickets/CreateTicketPage'
import { MyTicketsPage } from '@/features/tickets/MyTicketsPage'
import { QueuePage } from '@/features/tickets/QueuePage'
import { TicketDetailPage } from '@/features/tickets/TicketDetailPage'
import { KbEditorPage } from './features/knowledge/KbEditorPage'

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
              <Route path="/kb" element={<KbListPage />} />
              <Route path="/kb/new" element={<KbEditorPage />} />
              <Route path="/kb/:slug" element={<KbDetailPage />} />
              <Route path="/kb/:slug/edit" element={<KbEditorPage />} />

              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute roles={['ADMIN']}>
                    <Suspense fallback={<LoadingBlock label="Đang tải báo cáo…" />}>
                      <DashboardPage />
                    </Suspense>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/users"
                element={
                  <ProtectedRoute roles={['ADMIN']}>
                    <UsersPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/reports/ai-accuracy"
                element={
                  <ProtectedRoute roles={['IT_AGENT', 'ADMIN']}>
                    <Suspense fallback={<LoadingBlock label="Đang tải báo cáo AI…" />}>
                      <AiAccuracyPage />
                    </Suspense>
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
