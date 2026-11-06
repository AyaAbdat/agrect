import { useTranslation } from "react-i18next"

export function LogoMark({ size }: { size: 30 | 36 }) {
  const { t } = useTranslation()
  const box =
    size === 30
      ? "size-[30px] rounded-[9px] text-[14px]"
      : "size-9 rounded-[11px] text-[16px]"
  return (
    <div
      className={`flex shrink-0 items-center justify-center bg-pri font-bold text-white ${box}`}
    >
      {t("app.mark")}
    </div>
  )
}
