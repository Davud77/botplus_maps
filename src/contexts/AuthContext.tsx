// src/contexts/AuthContext.tsx
import React, { createContext, useEffect, useState } from "react";
import { API_BASE, authLogin, authLogout, authMe } from "../utils/api";

export interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  setupRequired: boolean;
  startupError: string;
  completeSetup: () => void;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const [setupRequired, setSetupRequired] = useState(false);
  const [startupError, setStartupError] = useState("");

  useEffect(() => {
    // Проверяем активную сессию на сервере (HttpOnly-кука)
    (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/setup/status`, { credentials: "include", cache: "no-store" });
        if (!response.ok) throw new Error("setup unavailable");
        const setup = await response.json();
        if (typeof setup.setup_required !== "boolean") throw new Error("invalid setup state");
        setSetupRequired(setup.setup_required);
        const me = await authMe();
        setIsAuthenticated(me.authenticated === true);
      } catch {
        setStartupError("Не удалось подключиться к серверу. Проверьте, что приложение и база данных запущены.");
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      const resp = await authLogin(username, password);
      if (resp.status === "ok") {
        setIsAuthenticated(true);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  };

  const logout = async (): Promise<void> => {
    try {
      await authLogout();
    } finally {
      setIsAuthenticated(false);
    }
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, setupRequired, startupError,
      completeSetup: () => { setSetupRequired(false); setIsAuthenticated(true); }, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
