import { defineConfig } from "vite";
import { worldBridge } from "./server/bridge";

// Tailnet hosts (Tailscale Serve) may reach the local dev server; nothing is exposed publicly.
const allowedHosts = [".ts.net"];

export default defineConfig({
  plugins: [worldBridge()],
  build: { target: "es2022", chunkSizeWarningLimit: 1500 },
  server: { allowedHosts },
  preview: { allowedHosts },
});
