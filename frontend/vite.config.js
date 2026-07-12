import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api/* to the FastAPI backend, so the frontend
// needs zero CORS configuration and no hardcoded backend URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
