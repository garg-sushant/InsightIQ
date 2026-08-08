"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api, clearTokens, getAccessToken, setTokens } from "@/lib/api-client";
import type { CurrentUserOut, OrganizationOut, Permission, UserOut } from "@/types/api";

interface AuthContextValue {
  user: UserOut | null;
  organization: OrganizationOut | null;
  permissions: Permission[];
  isLoading: boolean;
  isAuthenticated: boolean;
  hasPermission: (permission: Permission) => boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, fullName: string, organizationName: string) => Promise<void>;
  logout: () => void;
  refetchUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserOut | null>(null);
  const [organization, setOrganization] = useState<OrganizationOut | null>(null);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadCurrentUser = useCallback(async () => {
    if (!getAccessToken()) {
      setIsLoading(false);
      return;
    }
    try {
      const me = await api.get<CurrentUserOut>("/auth/me");
      setUser(me.user);
      setOrganization(me.organization);
      setPermissions(me.permissions);
    } catch {
      clearTokens();
      setUser(null);
      setOrganization(null);
      setPermissions([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCurrentUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await api.post<{ tokens: { access_token: string; refresh_token: string }; user: UserOut; organization: OrganizationOut }>(
        "/auth/login",
        { email, password },
      );
      setTokens(response.tokens.access_token, response.tokens.refresh_token);
      await loadCurrentUser();
      router.push("/dashboard");
    },
    [loadCurrentUser, router],
  );

  const signup = useCallback(
    async (email: string, password: string, fullName: string, organizationName: string) => {
      const response = await api.post<{ tokens: { access_token: string; refresh_token: string }; user: UserOut; organization: OrganizationOut }>(
        "/auth/signup",
        { email, password, full_name: fullName, organization_name: organizationName },
      );
      setTokens(response.tokens.access_token, response.tokens.refresh_token);
      await loadCurrentUser();
      router.push("/dashboard");
    },
    [loadCurrentUser, router],
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    setOrganization(null);
    setPermissions([]);
    router.push("/login");
  }, [router]);

  const hasPermission = useCallback((permission: Permission) => permissions.includes(permission), [permissions]);

  const value = useMemo(
    () => ({
      user,
      organization,
      permissions,
      isLoading,
      isAuthenticated: Boolean(user),
      hasPermission,
      login,
      signup,
      logout,
      refetchUser: loadCurrentUser,
    }),
    [user, organization, permissions, isLoading, hasPermission, login, signup, logout, loadCurrentUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
