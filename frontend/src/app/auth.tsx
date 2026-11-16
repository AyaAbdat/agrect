import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createContext, useCallback, useContext, useLayoutEffect, useState } from "react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Navigate, Outlet, useLocation, useNavigate } from "react-router"
import { Button } from "@/components/ui/button"
import { ApiError, apiGet, apiSend, setUnauthorizedHandler } from "../lib/api"
import { clearToken, getToken, setToken } from "../lib/auth"

type FarmSummary = {
  id: string
  name: string
}

type Me = {
  id: string
  email: string
  farms: FarmSummary[]
}

type TokenResponse = {
  access_token: string
}

type AuthContextValue = {
  user: Me | null
  currentFarmId: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  sessionPending: boolean
  meError: unknown
  refetchMe: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [hasToken, setHasToken] = useState(() => getToken() !== null)

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: () => apiGet<Me>("/v1/me"),
    enabled: hasToken,
  })

  useLayoutEffect(() => {
    setUnauthorizedHandler(() => {
      setHasToken(false)
      void navigate("/login", { replace: true })
    })
  }, [navigate])

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await apiSend<TokenResponse>("POST", "/v1/auth/login", {
        email,
        password,
      })
      setToken(result.access_token)
      setHasToken(true)
      await queryClient.invalidateQueries({ queryKey: ["me"] })
    },
    [queryClient],
  )

  const logout = useCallback(() => {
    clearToken()
    setHasToken(false)
    queryClient.clear()
    void navigate("/login", { replace: true })
  }, [navigate, queryClient])

  const user = meQuery.data ?? null
  const value: AuthContextValue = {
    user,
    currentFarmId: user?.farms[0]?.id ?? null,
    login,
    logout,
    sessionPending: hasToken && meQuery.isPending,
    meError: meQuery.error,
    refetchMe: async () => {
      await meQuery.refetch()
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (value === null) {
    throw new Error("useAuth must be used within AuthProvider")
  }
  return value
}

function Spinner() {
  return (
    <span
      className="size-5 shrink-0 animate-spin rounded-full border-2 border-line border-t-pri"
      aria-hidden="true"
    />
  )
}

export function RequireAuth() {
  const { t } = useTranslation()
  const location = useLocation()
  const { user, sessionPending, meError, refetchMe } = useAuth()

  if (getToken() === null) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  if (sessionPending) {
    return (
      <div className="flex h-screen items-center justify-center gap-3 bg-bg text-text">
        <Spinner />
        <p>{t("common.loading")}</p>
      </div>
    )
  }
  if (meError) {
    if (meError instanceof ApiError && meError.status === 401) {
      return <Navigate to="/login" replace state={{ from: location }} />
    }
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-bg px-6 text-center text-text">
        <p>{t("common.loadError")}</p>
        <Button type="button" onClick={() => void refetchMe()}>
          {t("common.retry")}
        </Button>
      </div>
    )
  }
  if (user === null || user.farms.length === 0) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg px-6 text-center text-text">
        <p>{t("auth.noFarm")}</p>
      </div>
    )
  }
  return <Outlet />
}
