/**
 * Auth Store
 *
 * Zustand store for authentication state management.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/types';
import { authApi, tokenManager } from '@/services/api';
import { connectWebSocket, disconnectWebSocket } from '@/services/websocket';

interface AuthState {
  // State
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string, confirmPassword: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  updateUser: (user: Partial<User>) => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Login action
      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          const { user } = await authApi.login({ email, password });

          set({
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          // Connect WebSocket after login
          connectWebSocket();
        } catch (error) {
          const message =
            error instanceof Error ? error.message : 'Login failed';
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
            error: message,
          });
          throw error;
        }
      },

      // Register action
      register: async (email: string, username: string, password: string, confirmPassword: string) => {
        set({ isLoading: true, error: null });

        try {
          await authApi.register({
            email,
            username,
            password,
            confirm_password: confirmPassword,
          });

          // Auto-login after registration
          await get().login(email, password);
        } catch (error) {
          const message =
            error instanceof Error ? error.message : 'Registration failed';
          set({
            isLoading: false,
            error: message,
          });
          throw error;
        }
      },

      // Logout action
      logout: async () => {
        try {
          await authApi.logout();
        } catch {
          // Ignore logout errors
        } finally {
          disconnectWebSocket();
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,
          });
        }
      },

      // Check authentication status
      checkAuth: async () => {
        // If we don't have tokens, we are definitely logged out
        if (!tokenManager.hasTokens()) {
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
          });
          return;
        }

        const { user: currentUser } = get();

        // If we already have a user and tokens, don't set loading to true immediately
        // Just verify in background if needed (optional optimization)
        if (currentUser) {
          // We already have user data, no need to block the UI
          // But we might want to refresh it quietly?
          // For now, let's assume if we have user in store + token, we are good.
          connectWebSocket();
          set({ isAuthenticated: true, isLoading: false });
          return;
        }

        // Only set loading if we don't have data yet
        set({ isLoading: true });

        try {
          const user = await authApi.getCurrentUser();

          set({
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          // Connect WebSocket if authenticated
          connectWebSocket();
        } catch (error) {
          console.error("Auth check failed:", error);
          tokenManager.clearTokens();
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,
          });
        }
      },

      // Update user
      updateUser: (updates: Partial<User>) => {
        const currentUser = get().user;
        if (currentUser) {
          set({ user: { ...currentUser, ...updates } });
        }
      },

      // Clear error
      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        // Only persist minimal data, not the full user object
        isAuthenticated: state.isAuthenticated,
        user: state.user,
      }),
    }
  )
);
