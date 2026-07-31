/**
 * Wrapper fetch dùng chung cho toàn bộ ứng dụng.
 *
 * Xử lý ở MỘT CHỖ DUY NHẤT:
 *  - Gắn Authorization header
 *  - Timeout 10 giây
 *  - Parse lỗi theo định dạng chuẩn của backend
 *  - Tự refresh token khi gặp 401 (nhiều request 401 đồng thời chỉ refresh MỘT lần)
 *  - Chỉ retry GET, không bao giờ retry POST
 */

import type { ApiErrorBody } from '@/types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
const TIMEOUT_MS = 10_000

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public requestId?: string,
    public details?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

let accessToken: string | null = null
let refreshPromise: Promise<boolean> | null = null
let onUnauthenticated: (() => void) | null = null

export const tokenStore = {
  /** Access token nằm TRONG BỘ NHỚ, không phải localStorage.
   *  localStorage bị đọc bởi bất kỳ lỗ hổng XSS nào. */
  set: (t: string | null) => { accessToken = t },
  get: () => accessToken,
}

export function setUnauthenticatedHandler(fn: () => void) {
  onUnauthenticated = fn
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as ApiErrorBody
    return new ApiError(
      body.error?.code ?? 'UNKNOWN',
      body.error?.message ?? 'Đã có lỗi xảy ra',
      res.status,
      body.error?.requestId,
      body.error?.details,
    )
  } catch {
    return new ApiError('UNKNOWN', `Lỗi ${res.status}`, res.status)
  }
}

/** Gọi /auth/refresh. Nhiều request cùng lúc chỉ gây MỘT lần refresh. */
async function refreshToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',   // gửi cookie HttpOnly chứa refresh token
      })
      if (!res.ok) return false
      const data = await res.json()
      tokenStore.set(data.accessToken)
      return true
    } catch {
      return false
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  skipAuth?: boolean
  _isRetry?: boolean
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, skipAuth, _isRetry, headers, ...rest } = options

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)

  const finalHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(headers as Record<string, string>),
  }
  if (!skipAuth && accessToken) {
    finalHeaders.Authorization = `Bearer ${accessToken}`
  }

  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...rest,
      headers: finalHeaders,
      credentials: 'include',
      signal: controller.signal,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })

    if (res.status === 401 && !skipAuth && !_isRetry) {
      const ok = await refreshToken()
      if (ok) return request<T>(path, { ...options, _isRetry: true })
      onUnauthenticated?.()
      throw new ApiError('UNAUTHENTICATED', 'Phiên đăng nhập đã hết hạn', 401)
    }

    if (!res.ok) throw await parseError(res)
    if (res.status === 204) return undefined as T
    return (await res.json()) as T
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('TIMEOUT', 'Yêu cầu quá thời gian chờ. Vui lòng thử lại.', 408)
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: 'GET' }),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: 'POST', body }),
  patch: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: 'PATCH', body }),
  delete: <T>(path: string, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: 'DELETE' }),
}
