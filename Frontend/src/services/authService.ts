import api, { tokenStorage } from "./api";
import type { User } from "../types";

export const authService = {
  async login(identifier: string, password: string): Promise<User> {
    const { data } = await api.post("/auth/login/", { username: identifier, password });
    tokenStorage.set(data.access, data.refresh);
    return this.me();
  },
  register(payload: { username: string; email: string; password: string }) {
    return api.post("/auth/register/", payload);
  },
  async me(): Promise<User> {
    const { data } = await api.get("/auth/me/");
    return data;
  },
  logout() {
    tokenStorage.clear();
  },
};
