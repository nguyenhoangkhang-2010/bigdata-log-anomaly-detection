import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: frontend :5173 gọi /api -> backend :8000 (không cần CORS khi chạy qua proxy).
// Muốn trỏ backend khác: đặt VITE_API_URL khi build/chạy (xem src/api/client.ts).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
