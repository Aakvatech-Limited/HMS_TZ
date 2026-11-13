import path from "node:path";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    frappeui({
      frappeProxy: true,
      jinjaBootData: true,
      lucideIcons: true,
      buildConfig: {
        indexHtmlPath: "../hms_tz/www/frontend.html",
        emptyOutDir: true,
        sourcemap: true,
      },
    }),
    vue(),
  ],
  build: {
    chunkSizeWarningLimit: 1500,
    outDir: "../hms_tz/public/frontend",
    emptyOutDir: true,
    target: "es2015",
    sourcemap: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@desk": path.resolve(__dirname, "../hms_tz/public/js"),
      WebSdk: path.resolve(__dirname, "src/shims/websdk.js"),
      "tailwind.config.js": path.resolve(__dirname, "tailwind.config.js"),
    },
  },
  optimizeDeps: {
    include: ["feather-icons", "showdown", "highlight.js/lib/core"],
  },
  server: {
    allowedHosts: true,
  },
});
