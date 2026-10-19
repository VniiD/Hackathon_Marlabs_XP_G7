import { httpApi } from "./http";
import { mockApi } from "./mock";
import type { Api } from "./types";

// Usa o FastAPI por padrão; defina VITE_USE_MOCKS=true apenas para forçar mocks.
export const USING_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";
export const API_MODE: "live" | "partial" | "mock" = USING_MOCKS
  ? import.meta.env.VITE_USE_MOCKS === "partial"
    ? "partial"
    : "mock"
  : "live";

export const api: Api = USING_MOCKS ? mockApi : httpApi;

export * from "./types";
