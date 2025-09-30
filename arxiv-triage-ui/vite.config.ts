import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Simple HTTP Basic Auth middleware for Vite dev/preview
const basicAuth = () => {
  const user = process.env.BASIC_AUTH_USER || ''
  const pass = process.env.BASIC_AUTH_PASS || ''
  const enabled = !!(user && pass)

  const authMiddleware = (req: any, res: any, next: any) => {
    // Allow health checks and asset requests before auth if needed
    if (!enabled) return next()

    const header = req.headers['authorization'] || req.headers['Authorization']
    if (typeof header === 'string' && header.startsWith('Basic ')) {
      const token = header.slice(6)
      const decoded = Buffer.from(token, 'base64').toString('utf8')
      const [u, p] = decoded.split(':')
      if (u === user && p === pass) return next()
    }
    res.statusCode = 401
    res.setHeader('WWW-Authenticate', 'Basic realm="arxiv-triage"')
    res.end('Authentication required')
  }

  return {
    name: 'vite-basic-auth',
    configureServer(server: any) {
      if (!enabled) return
      server.middlewares.use(authMiddleware)
    },
    configurePreviewServer(server: any) {
      if (!enabled) return
      server.middlewares.use(authMiddleware)
    },
  }
}

export default defineConfig({
  plugins: [react(), basicAuth()],
  server: { port: 5173, host: true, allowedHosts: ['read.xuenan.net'] }
})
