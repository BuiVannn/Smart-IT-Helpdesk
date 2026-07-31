import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/index.css'

async function bootstrap() {
  // Mock API bằng MSW — cho phép frontend chạy HOÀN TOÀN không cần backend.
  // Tắt bằng cách đặt VITE_USE_MOCK=false trong .env
  if (import.meta.env.VITE_USE_MOCK === 'true') {
    const { worker } = await import('./mocks/browser')
    await worker.start({ onUnhandledRequest: 'bypass' })
  }

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}

void bootstrap()
