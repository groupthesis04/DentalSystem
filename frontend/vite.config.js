import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const apiTarget =
  process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [vue()],

  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },

  preview: {
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});