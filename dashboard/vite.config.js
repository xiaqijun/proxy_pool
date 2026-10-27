import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/dashboard/",
  build: {
    outDir: "../monitor/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/dashboard/api": "http://127.0.0.1:5010",
    },
  },
});
