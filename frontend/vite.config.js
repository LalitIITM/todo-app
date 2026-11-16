import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // Local dev: proxy API calls to the FastAPI dev server
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
