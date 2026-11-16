import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"

export function LoadingRow() {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-text">
      <span
        className="size-5 shrink-0 animate-spin rounded-full border-2 border-line border-t-pri"
        aria-hidden="true"
      />
      <p>{t("common.loading")}</p>
    </div>
  )
}

export function ErrorRow({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <p>{t("common.loadError")}</p>
      <Button type="button" onClick={onRetry}>
        {t("common.retry")}
      </Button>
    </div>
  )
}
