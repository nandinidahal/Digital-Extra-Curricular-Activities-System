import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { authService } from "../services/authService";
import { tokenStorage } from "../services/api";
import type { User } from "../types";

interface AuthValue {
  user: User | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // On first load, if a token exists, ask the backend who the user is
  useEffect(() => {
    if (!tokenStorage.access) {
      setLoading(false);
      return;
    }
    authService.me().then(setUser).catch(() => tokenStorage.clear()).finally(() => setLoading(false));
  }, []);

  const login = async (identifier: string, password: string) => {
    const me = await authService.login(identifier, password);
    setUser(me);
    return me;
  };

  const logout = () => {
    authService.logout();
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
