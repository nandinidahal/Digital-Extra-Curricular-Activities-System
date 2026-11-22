import axios from "axios";
import type { ApiErrorBody } from "@/types/api";

/** Normalised error for every failed request. `code` comes from the backend error envelope. */
export class ApiError extends Error {
  status: number;
  code: string;
  fieldErrors: Record<string, string[]>;
  body: Partial<ApiErrorBody>;

  constructor(status: number, code: string, message: string, fieldErrors: Record<string, string[]> = {}, body: Partial<ApiErrorBody> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
    this.body = body;
  }
}

function flatten(errors: unknown, prefix = ""): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  if (!errors || typeof errors !== "object") return out;
  for (const [key, value] of Object.entries(errors as Record<string, unknown>)) {
    const name = prefix ? `${prefix}.${key}` : key;
    if (Array.isArray(value)) {
      const strings = value.filter((v) => typeof v === "string") as string[];
      if (strings.length) out[name] = strings;
      value.forEach((v, i) => {
        if (v && typeof v === "object") Object.assign(out, flatten(v, `${name}.${i}`));
      });
    } else if (typeof value === "string") {
      out[name] = [value];
    } else if (value && typeof value === "object") {
      Object.assign(out, flatten(value, name));
    }
  }
  return out;
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return new ApiError(0, "network_error", "Cannot reach the DEAS server. Check your connection and try again.");
    }
    const status = error.response.status;
    const body = (error.response.data ?? {}) as Partial<ApiErrorBody>;
    if (typeof body === "object" && body && "code" in body) {
      return new ApiError(status, String(body.code), String(body.message || "Request failed."), flatten(body.errors), body);
    }
    const generic: Record<number, string> = {
      404: "Not found.",
      413: "The upload is too large.",
      429: "Too many requests. Please slow down.",
      500: "Something went wrong on the server. Please try again later.",
    };
    return new ApiError(status, `http_${status}`, generic[status] ?? `Request failed (${status}).`);
  }
  return new ApiError(0, "unknown_error", error instanceof Error ? error.message : "Something went wrong.");
}

/** Human message for toasts: the first field error if the summary is generic. */
export function errorMessage(error: unknown): string {
  const e = toApiError(error);
  if (e.code === "validation_error") {
    const first = Object.entries(e.fieldErrors)[0];
    if (first) {
      const [field, messages] = first;
      const label = field === "non_field_errors" ? "" : `${field.replace(/_/g, " ")}: `;
      return `${label}${messages[0]}`;
    }
  }
  if (e.code === "throttled" && e.body.retry_after) return `Too many requests. Try again in ${e.body.retry_after}s.`;
  return e.message;
}
