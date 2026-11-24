import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate, useParams, useSearchParams } from "react-router"
import { Button } from "@/components/ui/button"
import { apiGet } from "../../../lib/api"
import { crumbClass } from "../../../lib/navStyles"
import { ErrorRow, LoadingRow } from "../Status"
import type { BlockDetail } from "../types"
import { IrrigationStep } from "./IrrigationStep"
import { LocationStep } from "./LocationStep"
import { PlantingStep } from "./PlantingStep"
import { ReviewStep } from "./ReviewStep"
import {
  IRRIGATION_FORM_ID,
  LOCATION_FORM_ID,
  PLANTING_FORM_ID,
  REVIEW_FORM_ID,
  TRAINING_FORM_ID,
  VALVES_FORM_ID,
  WIZARD_STEPS,
  wizardStep,
} from "./steps"
import { ValvesStep } from "./ValvesStep"
import { TrainingStep } from "./TrainingStep"
import { FieldError, FieldLabel, fieldClass } from "./wizardUi"
import { WizardStepper } from "./WizardStepper"

export function BlockWizardPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { blockId } = useParams()
  const [searchParams] = useSearchParams()
  const step = wizardStep(blockId, searchParams.get("step"))
  const [busy, setBusy] = useState(false)
  const [reason, setReason] = useState("")
  const [reasonError, setReasonError] = useState<string | null>(null)
  const blockQuery = useQuery({
    queryKey: ["block", blockId],
    queryFn: () => apiGet<BlockDetail>(`/v1/blocks/${blockId}`),
    enabled: blockId !== undefined,
  })
  const current = WIZARD_STEPS[step - 1] ?? WIZARD_STEPS[0]
  const block = blockQuery.data
  const locationReady = blockId === undefined || blockQuery.isSuccess
  const showReason = block?.status === "complete" && step >= 1 && step <= 5
  const formId =
    step === 1
      ? LOCATION_FORM_ID
      : step === 2
        ? PLANTING_FORM_ID
        : step === 3
          ? TRAINING_FORM_ID
          : step === 4
            ? IRRIGATION_FORM_ID
            : step === 5
              ? VALVES_FORM_ID
              : REVIEW_FORM_ID
  const actionsReady = step === 1 ? locationReady : blockQuery.isSuccess

  function goStep(next: number) {
    if (blockId === undefined) return
    void navigate(`/blocks/${blockId}/edit?step=${next}`)
  }

  function goBack() {
    if (step <= 1) {
      void navigate("/blocks")
      return
    }
    goStep(step - 1)
  }

  let body = (
    <section className="flex min-w-0 flex-1 items-center justify-center rounded-2xl border border-line bg-white">
      <p>{t("blocks.comingNext")}</p>
    </section>
  )
  if (blockId !== undefined && blockQuery.isPending) {
    body = (
      <section className="min-w-0 flex-1 rounded-2xl border border-line bg-white">
        <LoadingRow />
      </section>
    )
  } else if (blockId !== undefined && blockQuery.isError) {
    body = (
      <section className="min-w-0 flex-1 rounded-2xl border border-line bg-white">
        <ErrorRow onRetry={() => void blockQuery.refetch()} />
      </section>
    )
  } else if (step === 1) {
    body = (
      <LocationStep
        blockId={blockId}
        block={block ?? null}
        reason={reason}
        onReasonError={setReasonError}
        onBusy={setBusy}
      />
    )
  } else if (block !== undefined && step === 2) {
    body = (
      <PlantingStep block={block} reason={reason} onReasonError={setReasonError} onBusy={setBusy} />
    )
  } else if (block !== undefined && step === 3) {
    body = (
      <TrainingStep block={block} reason={reason} onReasonError={setReasonError} onBusy={setBusy} />
    )
  } else if (block !== undefined && step === 4) {
    body = (
      <IrrigationStep
        block={block}
        reason={reason}
        onReasonError={setReasonError}
        onBusy={setBusy}
      />
    )
  } else if (block !== undefined && step === 5) {
    body = (
      <ValvesStep block={block} reason={reason} onReasonError={setReasonError} onBusy={setBusy} />
    )
  } else if (block !== undefined && step === 6) {
    body = (
      <ReviewStep block={block} reason={reason} onReasonError={setReasonError} onBusy={setBusy} />
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <header>
        <p className={crumbClass}>
          {blockId === undefined
            ? t("blocks.wizardCrumb")
            : t("blocks.wizardEditCrumb", { name: block?.name ?? t("common.loading") })}
        </p>
        <h1 className="text-[24px] font-bold leading-tight">{t(current.titleKey)}</h1>
        <p className="mt-1 text-mut">
          {t("blocks.stepOf", { n: step, name: t(current.labelKey) })}
        </p>
      </header>
      <div className="flex items-start gap-4">
        <WizardStepper step={step} editing={blockId !== undefined} onStep={goStep} />
        {body}
      </div>
      {showReason ? (
        <label className="block max-w-[480px]">
          <FieldLabel label={t("blocks.reason")} tag="required" />
          <input
            className={fieldClass}
            value={reason}
            autoComplete="off"
            onChange={(event) => {
              setReason(event.target.value)
              setReasonError(null)
            }}
          />
          <FieldError message={reasonError ?? undefined} />
        </label>
      ) : null}
      <footer className="flex items-center justify-between gap-3 border-t border-line pt-4">
        <Button type="button" variant="outline" className="h-9 rounded-full px-4" onClick={goBack}>
          {step === 1 ? t("blocks.cancel") : t("blocks.back")}
        </Button>
        <div className="flex items-center gap-2">
          {step === 6 ? (
            <Button
              type="submit"
              form={REVIEW_FORM_ID}
              disabled={busy || !actionsReady}
              className="h-9 rounded-full bg-pri px-4 text-white"
            >
              {t("blocks.saveBlock")}
            </Button>
          ) : (
            <>
              <Button
                type="submit"
                form={formId}
                variant="ghost"
                data-action="draft"
                disabled={busy || !actionsReady}
                className="h-9 rounded-full px-4"
              >
                {t("blocks.saveDraft")}
              </Button>
              <Button
                type="submit"
                form={formId}
                data-action="next"
                disabled={busy || !actionsReady}
                className="h-9 rounded-full bg-pri px-4 text-white"
              >
                {t("blocks.next")}
              </Button>
            </>
          )}
        </div>
      </footer>
    </div>
  )
}
