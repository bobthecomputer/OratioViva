import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const isTauri = !!process.env.TAURI_PLATFORM;

export default defineConfig({
  // Use /app/ when served by FastAPI; use relative paths when bundled by Tauri.
  base: isTauri ? "./" : "/app/",
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
  envPrefix: ["VITE_", "TAURI_"],
  build: {
    target: process.env.TAURI_PLATFORM === "windows" ? "chrome105" : "safari13",
    minify: !process.env.TAURI_DEBUG,
    sourcemap: !!process.env.TAURI_DEBUG,
  },
});
