/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Màu trạng thái ticket — dùng nhất quán toàn hệ thống
        status: {
          new: '#64748b',
          assigned: '#3b82f6',
          progress: '#f59e0b',
          pending: '#a855f7',
          resolved: '#10b981',
          closed: '#475569',
          cancelled: '#94a3b8',
        },
        priority: {
          low: '#64748b',
          medium: '#3b82f6',
          high: '#f97316',
          urgent: '#ef4444',
        },
      },
    },
  },
  plugins: [],
}
