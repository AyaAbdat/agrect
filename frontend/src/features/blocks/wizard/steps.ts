export const WIZARD_STEPS = [
  { id: 1, labelKey: "blocks.steps.location", titleKey: "blocks.whereTitle" },
  { id: 2, labelKey: "blocks.steps.planting", titleKey: "blocks.plantedTitle" },
  { id: 3, labelKey: "blocks.steps.training", titleKey: "blocks.trainedTitle" },
  { id: 4, labelKey: "blocks.steps.irrigation", titleKey: "blocks.irrigatedTitle" },
  { id: 5, labelKey: "blocks.steps.valves", titleKey: "blocks.valvesTitle" },
  { id: 6, labelKey: "blocks.steps.review", titleKey: "blocks.reviewTitle" },
] as const

export const LOCATION_FORM_ID = "block-location"
export const PLANTING_FORM_ID = "block-planting"
export const TRAINING_FORM_ID = "block-training"
export const IRRIGATION_FORM_ID = "block-irrigation"
export const VALVES_FORM_ID = "block-valves"
export const REVIEW_FORM_ID = "block-review"

export function wizardStep(blockId: string | undefined, raw: string | null): number {
  if (blockId === undefined) return 1
  const parsed = Number(raw ?? "1")
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > WIZARD_STEPS.length) return 1
  return parsed
}
