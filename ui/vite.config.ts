import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
  },
  resolve: {
    alias: {
      "@shared": path.resolve(__dirname, "src/shared"),
      "@workspaces": path.resolve(__dirname, "src/workspaces"),
      "@app": path.resolve(__dirname, "src/app"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Forward API requests to the FastAPI backend (default port 8000).
      // Covers all known backend route prefixes so the React dev server
      // can call the API without CORS issues.
      "/health": "http://localhost:8000",
      "/watchlist": "http://localhost:8000",
      "/triage": "http://localhost:8000",
      "/journey": "http://localhost:8000",
      "/journal": "http://localhost:8000",
      "/review": "http://localhost:8000",
      "/analyse": "http://localhost:8000",
      "/feeder": "http://localhost:8000",
      "/runs": "http://localhost:8000",
      "/metrics": "http://localhost:8000",
      "/dashboard": "http://localhost:8000",
      "/analytics": "http://localhost:8000",
      "/backtest": "http://localhost:8000",
      "/e2e": "http://localhost:8000",
      "/plugins": "http://localhost:8000",
    },
  },
});
