import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import basicSsl from "@vitejs/plugin-basic-ssl";
import { loadDevHttps, useBasicSslFallback } from "./vite.https";

const devHttps = loadDevHttps();

/** Serve admin.html as / so the Admin React app feels like a normal SPA. */
function adminRootPlugin(): Plugin {
  return {
    name: "admin-root-spa",
    configureServer(server) {
      server.middlewares.use((req, _res, next) => {
        const url = req.url ?? "";
        if (url === "/" || url.startsWith("/?")) {
          req.url = "/admin.html";
        }
        next();
      });
    },
    transformIndexHtml: {
      order: "pre",
      handler(html, ctx) {
        if (ctx.path?.endsWith("admin.html") || ctx.filename?.endsWith("admin.html")) {
          return html.replace(
            "<title>Admin · Kannada Voice Banking</title>",
            "<title>ನಿರ್ವಹಣೆ · ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್</title>",
          );
        }
        return html;
      },
    },
    generateBundle(_options, bundle) {
      const adminChunk = bundle["admin.html"];
      if (adminChunk && adminChunk.type === "asset") {
        this.emitFile({
          type: "asset",
          fileName: "index.html",
          source: adminChunk.source,
        });
      }
    },
  };
}

/** Staff Admin React SPA — https://<your-ip>:5174/ */
export default defineConfig({
  // Separate from agent (:5173) — shared .vite/deps omitted lottie-react and broke admin.
  cacheDir: "node_modules/.vite-admin",
  plugins: [react(), adminRootPlugin(), ...(useBasicSslFallback() ? [basicSsl()] : [])],
  resolve: {
    dedupe: ["react", "react-dom"],
  },
  optimizeDeps: {
    include: ["react", "react-dom", "react/jsx-dev-runtime", "react-dom/client", "lottie-react"],
  },
  server: {
    port: 5174,
    strictPort: true,
    host: true,
    allowedHosts: true,
    https: devHttps,
    open: "/",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: "dist-admin",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        admin: "admin.html",
      },
    },
  },
  preview: {
    port: 5174,
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
