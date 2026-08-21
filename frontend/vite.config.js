import { defineConfig } from "vite";

// 开发时前端跑在 5173，把 /api 代理到本地后端 8182（浏览器视角同源，无需 CORS）。
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8182",
    },
  },
  build: {
    outDir: "dist",
  },
});
