import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import basicSsl from "@vitejs/plugin-basic-ssl";
import { loadDevHttps, useBasicSslFallback } from "./vite.https";

const devHttps = loadDevHttps();

/** Lobby Agent — https://<your-ip>:5173 (LAN + phone) */
export default defineConfig({
  plugins: [react(), ...(useBasicSslFallback() ? [basicSsl()] : [])],
  resolve: {
    dedupe: ["react", "react-dom"],
  },
  optimizeDeps: {
    include: ["react", "react-dom", "react/jsx-dev-runtime", "react-dom/client"],
  },
  server: {
    port: 5173,
    strictPort: true,
    host: true,
    allowedHosts: true,
    https: devHttps,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: "index.html",
      },
    },
  },
  preview: {
    port: 5173,
    strictPort: true,
    host: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
