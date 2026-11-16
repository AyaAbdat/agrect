import { zodResolver } from "@hookform/resolvers/zod"
import { useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"
import { Navigate, useLocation, useNavigate } from "react-router"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { useAuth } from "../app/auth"
import { LangSwitcher } from "../components/LangSwitcher"
import { LogoMark } from "../components/LogoMark"
import { ApiError } from "../lib/api"

const fieldClass =
  "h-10 w-full rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px] outline-none focus:ring-2 focus:ring-mint"

const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "login.emailRequired")
    .pipe(z.email("login.emailInvalid")),
  password: z.string().min(1, "login.passwordRequired"),
})

type LoginValues = z.infer<typeof loginSchema>
type FormErrorKey = "login.invalidCredentials" | "login.serverUnreachable"

function pathAfterLogin(state: unknown): string {
  if (typeof state !== "object" || state === null || !("from" in state)) {
    return "/today"
  }
  const from = (state as { from?: unknown }).from
  if (typeof from !== "object" || from === null || !("pathname" in from)) {
    return "/today"
  }
  const pathname = (from as { pathname?: unknown }).pathname
  const search = (from as { search?: unknown }).search
  const hash = (from as { hash?: unknown }).hash
  if (typeof pathname !== "string" || pathname === "" || pathname === "/login") {
    return "/today"
  }
  const searchText = typeof search === "string" ? search : ""
  const hashText = typeof hash === "string" ? hash : ""
  return `${pathname}${searchText}${hashText}`
}

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const { user, login, sessionPending } = useAuth()
  const loggingIn = useRef(false)
  const [formError, setFormError] = useState<FormErrorKey | null>(null)
  const [requestPending, setRequestPending] = useState(false)
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  })

  if (sessionPending && !loggingIn.current) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-3 bg-bg text-text">
        <span
          className="size-5 shrink-0 animate-spin rounded-full border-2 border-line border-t-pri"
          aria-hidden="true"
        />
        <p>{t("common.loading")}</p>
      </div>
    )
  }
  if (user !== null && !loggingIn.current) {
    return <Navigate to="/today" replace />
  }

  const emailError = form.formState.errors.email?.message
  const passwordError = form.formState.errors.password?.message

  async function onSubmit(values: LoginValues) {
    loggingIn.current = true
    setRequestPending(true)
    setFormError(null)
    try {
      await login(values.email, values.password)
      void navigate(pathAfterLogin(location.state))
    } catch (error) {
      loggingIn.current = false
      setRequestPending(false)
      if (!(error instanceof ApiError)) return
      if (error.code === "auth.invalid_credentials") {
        setFormError("login.invalidCredentials")
      } else if (error.code === "network_error" || error.status >= 500) {
        setFormError("login.serverUnreachable")
      }
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-6">
      <div className="flex w-[420px] flex-col gap-4 rounded-[20px] border border-line bg-white p-9">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <LogoMark size={36} />
            <span className="text-[20px] font-bold">{t("app.name")}</span>
          </div>
          <LangSwitcher />
        </div>
        <div>
          <h1 className="text-[22px] font-bold leading-tight">
            {t("login.title")}
          </h1>
          <p className="mt-1 text-mut">{t("login.subtitle")}</p>
        </div>
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(event) => {
            setFormError(null)
            void form.handleSubmit(onSubmit)(event)
          }}
        >
          <label className="flex flex-col gap-1.5 text-[12px] font-medium">
            {t("login.email")}
            <input
              type="email"
              autoComplete="username"
              aria-invalid={emailError ? true : undefined}
              className={fieldClass}
              {...form.register("email")}
            />
            {emailError ? (
              <span className="font-normal text-red" role="alert">
                {t(emailError)}
              </span>
            ) : null}
          </label>
          <label className="flex flex-col gap-1.5 text-[12px] font-medium">
            {t("login.password")}
            <input
              type="password"
              autoComplete="current-password"
              aria-invalid={passwordError ? true : undefined}
              className={fieldClass}
              {...form.register("password")}
            />
            {passwordError ? (
              <span className="font-normal text-red" role="alert">
                {t(passwordError)}
              </span>
            ) : null}
          </label>
          {formError ? (
            <p className="text-[12px] text-red" role="alert">
              {t(formError)}
            </p>
          ) : null}
          <Button
            type="submit"
            disabled={form.formState.isSubmitting || requestPending}
            className="h-[46px] w-full rounded-[10px] text-[14px] font-semibold"
          >
            {requestPending ? t("login.submitting") : t("login.submit")}
          </Button>
        </form>
        <p className="text-center text-grn">{t("login.forgot")}</p>
      </div>
    </div>
  )
}
