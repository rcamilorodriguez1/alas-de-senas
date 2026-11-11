import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { searchForWorkspaceRoot } from "vite";
import { defineConfig } from "vitest/config";

// Las pruebas de compatibilidad de TensorFlow.js (0.9) y de paridad (H11) leen ml/fixtures con node:fs.
const NODE_TESTS = [
  "src/camera/tfjs-compat.test.ts",
  "src/camera/dense.test.ts",
  "src/camera/holistic/parity.test.ts",
  "src/camera/holistic/published-model.test.ts",
];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    // El importador lee content/dataset-mapping.csv (?raw), fuera de apps/web.
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), "../../content"] },
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
