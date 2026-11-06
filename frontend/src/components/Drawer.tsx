import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetClose,
  SheetContent,
} from "@/components/ui/sheet"
import { crumbClass } from "../lib/navStyles"

export function Drawer({
  open,
  onOpenChange,
  crumb,
  title,
  children,
  footer,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  crumb?: string
  title: string
  children: ReactNode
  footer?: ReactNode
}) {
  const { t, i18n } = useTranslation()
  const side = (i18n.resolvedLanguage ?? i18n.language).startsWith("ar")
    ? "left"
    : "right"
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={side}
        showCloseButton={false}
        className="w-[460px]! max-w-[460px]! gap-[18px] overflow-hidden p-7 text-[13px] sm:max-w-[460px]!"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            {crumb ? <p className={crumbClass}>{crumb}</p> : null}
            <h1 className="text-[24px] font-bold leading-tight">{title}</h1>
          </div>
          <SheetClose
            render={
              <Button variant="ghost" type="button" className="shrink-0" />
            }
          >
            {t("drawer.close")}
          </SheetClose>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        {footer ? <div>{footer}</div> : null}
      </SheetContent>
    </Sheet>
  )
}
