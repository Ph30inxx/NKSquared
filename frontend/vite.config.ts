import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // In Docker the api service is reachable as http://api:8000.
  // Locally the user typically sets VITE_API_URL=http://localhost:8000.
  const apiTarget = env.VITE_API_URL || "http://api:8000";

  return {
    plugins: [react()],
    server: {
      host: true,
      port: 5173,
      watch: {
        usePolling: true,
      },
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
        "/chat-api": {
          target: env.VITE_CHATBOT_URL || "http://chatbot:8001",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/chat-api/, ""),
        },
      },
    },
  };
});
