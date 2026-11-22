/** Common module: /api/health/ */
import { api } from "./client";

export const commonApi = {
  health: () =>
    api.get<{ status: "ok" | "degraded" | "unavailable"; checks: { database: string; cache: string }; time: string }>("/health/", { skipAuth: true }),
};
