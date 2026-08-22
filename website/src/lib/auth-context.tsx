"use client";

import * as React from "react";

interface User {
  user_id: string;
  email: string;
  name?: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  mode: "demo" | "user";
  setMode: (mode: "demo" | "user") => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = React.useState<"demo" | "user">("demo");

  // Always return demo mode - no authentication
  return (
    <AuthContext.Provider
      value={{
        user: null,
        isLoading: false,
        isAuthenticated: false,
        mode,
        setMode,
        login: async () => {},
        register: async () => {},
        logout: async () => {},
        refreshUser: async () => {},
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}