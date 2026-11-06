import { useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"
import { LangSwitcher } from "../components/LangSwitcher"
import { LogoMark } from "../components/LogoMark"
import { Button } from "@/components/ui/button"

const fieldClass =
  "h-10 w-full rounded-[10px] border border-[#C7D2C9] bg-white px-3 text-[13px] outline-none focus:ring-2 focus:ring-mint"

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState(false)

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (email.trim() === "" || password.trim() === "") {
      setError(true)
      return
    }
    setError(false)
    void navigate("/today")
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
        <form className="flex flex-col gap-4" noValidate onSubmit={onSubmit}>
          <label className="flex flex-col gap-1.5 text-[12px] font-medium">
            {t("login.email")}
            <input
              type="email"
              name="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={fieldClass}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-[12px] font-medium">
            {t("login.password")}
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={fieldClass}
            />
          </label>
          {error ? (
            <p className="text-[12px] text-red" role="alert">
              {t("login.error")}
            </p>
          ) : null}
          <Button
            type="submit"
            className="h-[46px] w-full rounded-[10px] text-[14px] font-semibold"
          >
            {t("login.submit")}
          </Button>
        </form>
        <p className="text-center text-grn">{t("login.forgot")}</p>
      </div>
    </div>
  )
}
