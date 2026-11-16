import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef } from "react"
import { useNavigate } from "react-router"
import { useAuth } from "../../../app/auth"
import { ApiError, apiSend } from "../../../lib/api"
import { blockErrorKey } from "../errors"
import type { BlockDetail } from "../types"

export type SaveAction = "draft" | "next"

export type StepSaveProps = {
  block: BlockDetail
  reason: string
  onReasonError: (message: string | null) => void
  onBusy: (busy: boolean) => void
}

export function submitAction(event?: { nativeEvent?: Event }): SaveAction {
  const submitter =
    event?.nativeEvent instanceof SubmitEvent ? event.nativeEvent.submitter : null
  if (submitter instanceof HTMLElement && submitter.dataset.action === "draft") return "draft"
  return "next"
}

export function useBlockVersion(block: BlockDetail) {
  const versionRef = useRef(block.version)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { currentFarmId } = useAuth()

  useEffect(() => {
    if (block.version > versionRef.current) versionRef.current = block.version
  }, [block.version])

  async function write(method: string, path: string, body: unknown): Promise<BlockDetail> {
    const saved = await apiSend<BlockDetail>(method, path, body, {
      "If-Match": String(versionRef.current),
    })
    versionRef.current = saved.version
    queryClient.setQueryData(["block", saved.id], saved)
    return saved
  }

  async function finish(saved: BlockDetail, action: SaveAction, nextStep: number): Promise<void> {
    if (currentFarmId !== null) {
      await queryClient.invalidateQueries({ queryKey: ["blocks", currentFarmId] })
    }
    if (action === "draft") {
      void navigate("/blocks")
      return
    }
    void navigate(`/blocks/${saved.id}/edit?step=${nextStep}`)
  }

  return { write, finish }
}

export function reasonPayload(block: BlockDetail, reason: string): { reason?: string } {
  if (block.status !== "complete") return {}
  return { reason: reason.trim() }
}

export function requireReason(
  block: BlockDetail,
  reason: string,
  onReasonError: (message: string | null) => void,
): boolean {
  if (block.status === "complete" && reason.trim() === "") {
    onReasonError("blocks.errors.reasonRequired")
    return false
  }
  onReasonError(null)
  return true
}

export function reportErrors(
  error: unknown,
  apply: (field: string, messageKey: string) => boolean,
): "version" | "fields" | "save" | "partial" {
  if (error instanceof ApiError && (error.status === 409 || error.status === 428)) return "version"
  if (!(error instanceof ApiError) || error.code !== "validation_error") return "save"
  let matched = false
  let unmatched = false
  for (const [field, code] of Object.entries(error.fields)) {
    if (apply(field, blockErrorKey(code))) matched = true
    else unmatched = true
  }
  if (unmatched) return matched ? "partial" : "save"
  return "fields"
}
