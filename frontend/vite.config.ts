import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development we serve the JSON artifacts from `public/data/` directly
// (Vite serves anything under `public/` at the site root). In production the
// React bundle is static and the data files are co-located next to it. The
// `base` flag matches the local parity preview server used by Playwright.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 700,
  },
});