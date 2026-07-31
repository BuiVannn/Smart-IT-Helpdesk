/**
 * Cấu hình ESLint (flat config, chuẩn của ESLint 9).
 *
 * File này bị THIẾU từ lúc dựng base nên `npm run lint` luôn hỏng — chưa ai
 * chạy nên chưa ai biết. CI sẽ chạy lệnh này, thiếu nó là CI đỏ ngay từ đầu.
 *
 * Luật quan trọng nhất ở đây là `react-hooks/exhaustive-deps`: thiếu phần tử
 * trong mảng phụ thuộc của useEffect gây ra loại lỗi khó nhất — giao diện
 * hiển thị dữ liệu cũ mà không có thông báo lỗi nào.
 */

import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'src/api/types.gen.ts'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Cho phép `_` ở đầu tên biến để bỏ qua có chủ đích khi destructure
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
)
