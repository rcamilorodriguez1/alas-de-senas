import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// La prueba de compatibilidad de TensorFlow.js lee archivos de ml/fixtures con node:fs (0.9).
const NODE_TESTS = ["src/camera/tfjs-compat.test.ts"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    testTimeout: 30_000,
    projects: [
      {
        extends: true,
        test: {
          name: "dom",
          environment: "jsdom",
          setupFiles: ["./src/test/setup.ts"],
          include: ["src/**/*.test.{ts,tsx}"],
          exclude: NODE_TESTS,
        },
      },
      {
        extends: true,
        test: { name: "node", environment: "node", include: NODE_TESTS },
      },
    ],
  },
});
