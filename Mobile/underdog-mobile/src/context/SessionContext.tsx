import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import * as sessionStorage from '../storage/session';

type SessionContextValue = {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  isLoading: boolean;
  restoreSession: () => Promise<void>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [sessionId, setSessionIdState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const restoreSession = useCallback(async () => {
    try {
      const id = await sessionStorage.getSessionId();
      setSessionIdState(id);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  const setSessionId = useCallback(async (id: string | null) => {
    if (id) {
      await sessionStorage.setSessionId(id);
      setSessionIdState(id);
    } else {
      await sessionStorage.clearSessionId();
      setSessionIdState(null);
    }
  }, []);

  const signOut = useCallback(async () => {
    await sessionStorage.clearSessionId();
    setSessionIdState(null);
  }, []);

  const value: SessionContextValue = {
    sessionId,
    setSessionId,
    isLoading,
    restoreSession,
    signOut,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}
