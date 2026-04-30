import axios from "axios";

// All requests go through Vite's dev-server proxy (`/api/*` → backend),
// so no host is needed at the axios level.
export const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});
