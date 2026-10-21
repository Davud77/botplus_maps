import React, { createContext, useEffect, useState } from 'react';
import { API_BASE, authLogin, authLogout, authMe } from '../utils/api';

export interface SessionUser { id: number; username: string; role: 'admin' | 'editor' | 'viewer'; exp?: number; }
export interface AuthContextType {
  isAuthenticated: boolean; isLoading: boolean; setupRequired: boolean; startupError: string;
  user: SessionUser | null;
  refreshUser: () => Promise<SessionUser | null>;
  completeSetup: () => Promise<void>;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
}
export const AuthContext = createContext<AuthContextType | null>(null);
export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [setupRequired, setSetupRequired] = useState(false);
  const [startupError, setStartupError] = useState('');
  const refreshUser = async () => {
    const result = await authMe();
    const current = result.authenticated ? result.user as SessionUser : null;
    setUser(current); return current;
  };
  useEffect(() => {
    (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/setup/status`, { credentials: 'include', cache: 'no-store' });
        if (!response.ok) throw new Error('setup unavailable');
        const setup = await response.json();
        if (typeof setup.setup_required !== 'boolean') throw new Error('invalid setup state');
        setSetupRequired(setup.setup_required);
        const me = await authMe();
        setUser(me.authenticated ? me.user as SessionUser : null);
      } catch {
        setStartupError('Не удалось подключиться к серверу. Проверьте приложение и базу данных.');
      } finally { setIsLoading(false); }
    })();
  }, []);
  const login = async (username: string, password: string) => {
    try { const result = await authLogin(username, password); return result.status === 'ok' && !!(await refreshUser()); }
    catch { return false; }
  };
  const logout = async () => { try { await authLogout(); } finally { setUser(null); } };
  const completeSetup = async () => { await refreshUser(); setSetupRequired(false); };
  return <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, setupRequired, startupError,
    refreshUser, completeSetup, login, logout }}>{children}</AuthContext.Provider>;
};
