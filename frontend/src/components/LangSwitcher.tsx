import { useTranslation } from "react-i18next"
import { LANGS } from "../i18n"

export function LangSwitcher() {
  const { t, i18n } = useTranslation()
  const current = i18n.resolvedLanguage ?? i18n.language
  return (
    <div className="flex items-center gap-1 text-[12px] font-semibold">
      {LANGS.map((code, index) => (
        <span key={code} className="flex items-center gap-1">
          {index > 0 ? <span className="text-mut">·</span> : null}
          <button
            type="button"
            className={current === code ? "text-pri" : "text-mut"}
            onClick={() => {
              void i18n.changeLanguage(code)
            }}
          >
            {t(`langShort.${code}`)}
          </button>
        </span>
      ))}
    </div>
  )
}
