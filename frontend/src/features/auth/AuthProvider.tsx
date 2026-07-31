import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, setUnauthenticatedHandler, tokenStore } from '@/api/client'
import type { CurrentUser } from '@/types'

interface AuthState {
  user: CurrentUser | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

interface LoginResponse {
  accessToken: string
  expiresIn: number
  user: CurrentUser
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      tokenStore.set(null)
      setUser(null)
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post<LoginResponse>('/auth/login', { email, password }, {
      skipAuth: true,
    })
    tokenStore.set(res.accessToken)
    setUser(res.user)
  }, [])

  // Khôi phục phiên khi tải lại trang (F5).
  // Access token nằm trong bộ nhớ nên mất khi refresh — cookie refresh token
  // vẫn còn, nên gọi /auth/refresh để lấy access token mới.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await api.post<LoginResponse>('/auth/refresh', undefined, { skipAuth: true })
        if (!cancelled) {
          tokenStore.set(res.accessToken)
          setUser(res.user)
        }
      } catch {
        // Chưa đăng nhập — bình thường, không phải lỗi
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    setUnauthenticatedHandler(() => {
      tokenStore.set(null)
      setUser(null)
    })
  }, [])

  const value = useMemo(
    () => ({ user, isLoading, login, logout }),
    [user, isLoading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth phải nằm trong AuthProvider')
  return ctx
}
