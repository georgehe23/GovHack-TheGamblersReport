import { defineConfig } from 'vite'
import path from 'node:path'

export default defineConfig({
  base: './',
  server: {
    fs: {
      allow: [path.resolve(__dirname)]
    }
  }
})

