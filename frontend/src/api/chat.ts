/**
 * API trợ lý ảo, gồm bộ đọc luồng SSE.
 *
 * ★ PHẢI TỰ TÁCH KHUNG SSE: `ReadableStream` cắt dữ liệu theo gói mạng, KHÔNG
 * theo ranh giới sự kiện. Một khung có thể tới làm hai lần, và hai khung có
 * thể tới cùng một lần. Không đệm lại thì token bị mất hoặc JSON vỡ giữa chừng
 * — lỗi này chỉ xuất hiện khi mạng chậm, tức là đúng lúc đang demo.
 */

import { api, fetchStream } from '@/api/client'
import type { ChatEvent, ChatSession, ChatSessionDetail, Page } from '@/types'

export const chatApi = {
  createSession: (title?: string) =>
    api.post<ChatSession>('/chat/sessions', { title: title ?? null }),

  listSessions: (page = 1, pageSize = 20) =>
    api.get<Page<ChatSession>>(`/chat/sessions?page=${page}&pageSize=${pageSize}`),

  getSession: (id: string) => api.get<ChatSessionDetail>(`/chat/sessions/${id}`),

  config: () =>
    api.get<{
      maxQuestionLength: number
      rateLimitPerWindow: number
      rateLimitWindowSeconds: number
      model: string
    }>('/chat/config'),
}

/** Đọc một khung SSE thô thành `ChatEvent`. Bỏ qua khung không hợp lệ. */
function parseFrame(frame: string): ChatEvent | null {
  let name: string | null = null
  let data: string | null = null

  for (const line of frame.split('\n')) {
    if (line.startsWith('event: ')) name = line.slice(7).trim()
    else if (line.startsWith('data: ')) data = line.slice(6)
  }
  if (!name || data === null) return null

  try {
    return { type: name, data: JSON.parse(data) } as ChatEvent
  } catch {
    return null
  }
}

/**
 * Hỏi trợ lý và nhận sự kiện theo luồng.
 *
 * Thứ tự backend cam kết: `citations` → `token`* → `done`, hoặc `error`.
 */
export async function* streamAnswer(
  sessionId: string,
  question: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetchStream(
    `/chat/sessions/${sessionId}/messages`,
    { question },
    signal,
  )
  if (!response.body) throw new Error('Trình duyệt không hỗ trợ đọc luồng dữ liệu')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break

      // stream: true để ký tự tiếng Việt bị cắt đôi giữa hai gói vẫn ghép
      // lại đúng, thay vì thành dấu hỏi.
      buffer += decoder.decode(value, { stream: true })

      // Khung SSE kết thúc bằng một dòng trống. Phần đuôi chưa đủ khung thì
      // GIỮ LẠI trong buffer, chờ gói tiếp theo.
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''

      for (const frame of frames) {
        const event = parseFrame(frame)
        if (event) yield event
      }
    }

    const last = parseFrame(buffer)
    if (last) yield last
  } finally {
    reader.releaseLock()
  }
}
