import { useEffect, useState } from 'react'

/**
 * Hoãn cập nhật giá trị cho tới khi người dùng ngừng thay đổi `delay` ms.
 *
 * Dùng cho ô tìm kiếm: không có nó thì gõ "mật khẩu" bắn 8 request, và câu
 * trả lời về không đúng thứ tự nên kết quả hiển thị có thể là của từ khoá cũ.
 */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}
