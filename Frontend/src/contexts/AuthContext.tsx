import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { authApi } from "@/services/api/auth";
import { SESSION_EXPIRED_EVENT } from "@/services/api/client";
import { profilesApi } from "@/services/api/profiles";
import { tokenStorage } from "@/services/auth/tokenStorage";
import type { OwnProfile, Tokens, User } from "@/types/api";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthValue {
  status: Status;
  /** True after an explicit logout (until the next login): guards send the user home, not to /login. */
  signedOut: boolean;
  user: User | null;
  profile: OwnProfile | null;
  isModerator: boolean;
  isAdmin: boolean;
  login: (email: string, password: string, remember: boolean) => Promise<User>;
  logout: (options?: { silent?: boolean }) => Promise<void>;
  setUser: (user: User) => void;
  setProfile: (profile: OwnProfile) => void;
  replaceTokens: (tokens: Tokens) => void;
  reloadProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [signedOut, setSignedOut] = useState(false);
  const [status, setStatus] = useState<Status>(tokenStorage.get() ? "loading" : "anonymous");
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<OwnProfile | null>(null);

  const loadSession = useCallback(async () => {
    const [me, own] = await Promise.all([authApi.me(), profilesApi.me()]);
    setUser(me.data.user);
    setProfile(own.data.profile);
    setStatus("authenticated");
    return me.data.user;
  }, []);

  useEffect(() => {
    if (!tokenStorage.get()) return;
    loadSession().catch(() => {
      tokenStorage.clear();
      setStatus("anonymous");
    });
  }, [loadSession]);

  const reset = useCallback(() => {
    tokenStorage.clear();
    setUser(null);
    setProfile(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    const onExpired = () => {
      reset();
      toast.error("Your session has expired. Please log in again.");
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [reset]);

  const login = useCallback(async (email: string, password: string, remember: boolean) => {
    const result = await authApi.login(email, password);
    tokenStorage.set(result.data.tokens, remember);
    setSignedOut(false);
    setUser(result.data.user);
    try {
      const own = await profilesApi.me();
      setProfile(own.data.profile);
    } catch {
      /* profile is optional for rendering; retried later */
    }
    setStatus("authenticated");
    return result.data.user;
  }, []);

  const logout = useCallback(async (options?: { silent?: boolean }) => {
    const refresh = tokenStorage.get()?.refresh;
    if (refresh) {
      try {
        await authApi.logout(refresh); // blacklists the refresh token on the server
      } catch {
        /* already invalid: logging out locally is still correct */
      }
    }
    // A deliberate logout goes to the landing page; RequireAuth reads `signedOut` so it sends the
    // user to "/" rather than to /login?next=<the page they were on>.
    setSignedOut(true);
    reset();
    if (!options?.silent) toast.success("You have been logged out.");
  }, [reset]);

  const value = useMemo<AuthValue>(() => ({
    status,
    signedOut,
    user,
    profile,
    isModerator: user?.role === "admin" || user?.role === "coordinator",
    isAdmin: user?.role === "admin",
    login,
    logout,
    setUser,
    setProfile,
    replaceTokens: (tokens) => tokenStorage.set(tokens),
    reloadProfile: async () => {
      const own = await profilesApi.me();
      setProfile(own.data.profile);
    },
  }), [status, signedOut, user, profile, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}
