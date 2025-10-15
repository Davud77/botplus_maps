// src/hooks/useAuth.ts
import { useContext } from 'react';
import { AuthContext, AuthContextType } from '../contexts/AuthContext'; // Добавлен импорт AuthContext

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth должен использоваться внутри AuthProvider');
  }
  return context;
};