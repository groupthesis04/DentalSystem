import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const apiTarget = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

const securityHeaders = {
  "Content-Security-Policy": [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self' data:",
    "connect-src 'self' ws://localhost:* ws://127.0.0.1:* wss://borjadentalclinic.up.railway.app wss://www.borjadentalclinic.site wss://borjadentalclinic.site",
    "form-action 'self'",
  ].join("; "),
  "Strict-Transport-Security": "max-age=3600",
  "X-Frame-Options": "DENY",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "same-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

export default defineConfig({
  plugins: [vue()],

  // Local development
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,

    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
      "/ws": {
        target: apiTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },

  // Railway production preview
  preview: {
    host: "0.0.0.0",
    port: Number(process.env.PORT) || 8080,
    strictPort: true,
    headers: securityHeaders,

    // Allowed production domains
    allowedHosts: [
      "borjadentalclinic.up.railway.app",
      "www.borjadentalclinic.site",
      "borjadentalclinic.site",
    ],

    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
      "/ws": {
        target: apiTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },

  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
