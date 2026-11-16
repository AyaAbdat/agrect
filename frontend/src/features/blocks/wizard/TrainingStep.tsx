import { useQuery } from "@tanstack/react-query"
import { useLayoutEffect, useState } from "react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { apiGet } from "../../../lib/api"
import {
  activeLang,
  cropLabel,
  localizedName,
  type CatalogTrainingSystem,
} from "../types"
import { ErrorRow, LoadingRow } from "../Status"
import {
  reasonPayload,
  reportErrors,
  requireReason,
  submitAction,
  useBlockVersion,
  type StepSaveProps,
} from "./blockWrite"
import { TRAINING_FORM_ID } from "./steps"
import { FieldError, InfoBox, fieldClass, panelClass } from "./wizardUi"

function initialChoice(block: StepSaveProps["block"], systems: CatalogTrainingSystem[]): string {
  if (
    block.training_system_id !== null &&
    systems.some((item) => item.id === block.training_system_id)
  ) {
    return block.training_system_id
  }
  if (block.training_other !== null && block.training_other.trim() !== "") return "other"
  return ""
}

function OptionCard({
  name,
  description,
  selected,
  onSelect,
  children,
}: {
  name: string
  description: string
  selected: boolean
  onSelect: () => void
  children?: ReactNode
}) {
  return (
    <label
      className={`flex cursor-pointer flex-col gap-1 rounded-xl border p-3 ${
        selected ? "border-pri bg-[#F3FAF4]" : "border-line bg-white"
      }`}
    >
      <span className="flex items-center gap-2">
        <input
          type="radio"
          name="training-system"
          className="size-4 accent-pri"
          checked={selected}
          onChange={onSelect}
        />
        <span className="text-[13px] font-bold">{name}</span>
      </span>
      <span className="ps-6 text-[12px] text-mut">{description}</span>
      {children}
    </label>
  )
}

function TrainingForm({
  block,
  reason,
  onReasonError,
  onBusy,
  systems,
  noCrop,
}: StepSaveProps & { systems: CatalogTrainingSystem[]; noCrop: boolean }) {
  const { t, i18n } = useTranslation()
  const lang = activeLang(i18n.resolvedLanguage ?? i18n.language)
  const { write, finish } = useBlockVersion(block)
  const [choice, setChoice] = useState(() => initialChoice(block, systems))
  const [otherText, setOtherText] = useState(block.training_other ?? "")
  const [formError, setFormError] = useState<string | null>(null)
  const [choiceError, setChoiceError] = useState<string | undefined>(undefined)
  const cropName = cropLabel(block.crop, lang) ?? ""
  const showOptions = !noCrop && systems.length > 0

  async function persist(event: { nativeEvent?: Event }) {
    const clearing = !showOptions
    const trainingSystemId =
      clearing || choice === "" || choice === "other" ? null : choice
    const trainingOther =
      clearing || choice !== "other" || otherText.trim() === "" ? null : otherText.trim()
    onBusy(true)
    try {
      const saved = await write("PATCH", `/v1/blocks/${block.id}`, {
        training_system_id: trainingSystemId,
        training_other: trainingOther,
        ...reasonPayload(block, reason),
      })
      await finish(saved, submitAction(event), 4)
    } catch (error) {
      const outcome = reportErrors(error, (field, key) => {
        if (field === "reason") {
          onReasonError(key)
          return true
        }
        if (field === "training_system_id") {
          setChoiceError(key)
          return true
        }
        return false
      })
      if (outcome === "version") setFormError("blocks.errors.version")
      else if (outcome === "save" || outcome === "partial") setFormError("blocks.errors.save")
    } finally {
      onBusy(false)
    }
  }

  return (
    <form
      id={TRAINING_FORM_ID}
      className={`${panelClass} flex flex-col gap-4`}
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        setFormError(null)
        setChoiceError(undefined)
        if (!requireReason(block, reason, onReasonError)) return
        void persist(event)
      }}
    >
      {showOptions ? (
        <>
          <p className="text-[13px] text-mut">{t("blocks.trainingSub", { crop: cropName })}</p>
          <div className="grid grid-cols-3 gap-3">
            {systems.map((system) => (
              <OptionCard
                key={system.id}
                name={localizedName(system.name, lang)}
                description={localizedName(system.description, lang)}
                selected={choice === system.id}
                onSelect={() => setChoice(system.id)}
              />
            ))}
            <OptionCard
              name={t("blocks.trainingOther")}
              description={t("blocks.trainingOtherHelp")}
              selected={choice === "other"}
              onSelect={() => setChoice("other")}
            >
              {choice === "other" ? (
                <input
                  className={`${fieldClass} mt-2`}
                  value={otherText}
                  placeholder={t("blocks.trainingOtherPlaceholder")}
                  autoComplete="off"
                  onChange={(event) => setOtherText(event.target.value)}
                />
              ) : null}
            </OptionCard>
          </div>
        </>
      ) : (
        <InfoBox>{t(noCrop ? "blocks.noCrop" : "blocks.trainingNone")}</InfoBox>
      )}
      <FieldError message={choiceError} />
      {formError !== null ? <p className="text-[12px] text-red">{t(formError)}</p> : null}
    </form>
  )
}

export function TrainingStep({ block, reason, onReasonError, onBusy }: StepSaveProps) {
  const cropId = block.crop?.id ?? null
  const systemsQuery = useQuery({
    queryKey: ["catalog", "training", cropId],
    queryFn: () =>
      apiGet<CatalogTrainingSystem[]>(`/v1/catalog/crops/${cropId}/training-systems`),
    enabled: cropId !== null,
  })

  useLayoutEffect(() => {
    onBusy(cropId !== null && systemsQuery.isPending)
    return () => onBusy(false)
  }, [cropId, systemsQuery.isPending, onBusy])

  const step = { block, reason, onReasonError, onBusy }
  if (cropId === null) return <TrainingForm {...step} systems={[]} noCrop />
  if (systemsQuery.isPending) {
    return (
      <form
        id={TRAINING_FORM_ID}
        className={panelClass}
        onSubmit={(event) => event.preventDefault()}
      >
        <LoadingRow />
      </form>
    )
  }
  if (systemsQuery.isError) {
    return (
      <form
        id={TRAINING_FORM_ID}
        className={panelClass}
        onSubmit={(event) => event.preventDefault()}
      >
        <ErrorRow onRetry={() => void systemsQuery.refetch()} />
      </form>
    )
  }
  return <TrainingForm {...step} systems={systemsQuery.data ?? []} noCrop={false} />
}
