import { useEffect, useMemo, useState } from "react";

import { getCurrentUser, loginUser, logoutUser, registerUser } from "./api/client";
import { AuthContext } from "./useAuth";

export function AuthProvider({ children }) {
  const [authState, setAuthState] = useState({
    loading: true,
    user: null,
    error: null,
  });

  useEffect(() => {
    let ignore = false;

    getCurrentUser()
      .then((user) => {
        if (!ignore) {
          setAuthState({ loading: false, user, error: null });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setAuthState({
            loading: false,
            user: null,
            error: error.status === 401 ? null : error,
          });
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  async function login(credentials) {
    const user = await loginUser(credentials);
    setAuthState({ loading: false, user, error: null });
    return user;
  }

  async function register(credentials) {
    return registerUser(credentials);
  }

  async function logout() {
    try {
      await logoutUser();
    } finally {
      setAuthState({ loading: false, user: null, error: null });
    }
  }

  const value = useMemo(
    () => ({
      ...authState,
      isAuthenticated: Boolean(authState.user),
      login,
      logout,
      register,
    }),
    [authState],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
