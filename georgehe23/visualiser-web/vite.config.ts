import { defineConfig } from 'vite'
import path from 'node:path'

// https://vitejs.dev/config/
export default defineConfig({
  base: './',
  server: {
    fs: {
      // allow serving files from repo root so we can fetch ../../data/*.geojson in dev
      allow: [path.resolve(__dirname, '..', '..')]
    }
  }
})

