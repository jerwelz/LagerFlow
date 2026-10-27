/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API runs separately (uvicorn on port 8000); Vite forwards API paths there.
// In production FastAPI serves the built files, so everything is same-origin.
const API = "http://127.0.0.1:8000";
const apiPaths = ["/products", "/inventory", "/reports", "/demo", "/health", "/docs", "/openapi.json"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: Object.fromEntries(apiPaths.map((path) => [path, API])),
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
