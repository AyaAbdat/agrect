import { useEffect, useRef, useState } from "react"
import { ApiError, apiSend } from "../../../lib/api"
import { blockErrorKey } from "../errors"

export function useCalcPreview<T>(path: string, body: unknown): {
  data: T | null
  fieldErrors: Record<string, string>
  error: string | null
} {
  const [data, setData] = useState<T | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const requestRef = useRef(0)
  const bodyRef = useRef(body)
  bodyRef.current = body
  const key = JSON.stringify(body)

  useEffect(() => {
    const request = ++requestRef.current
    const payload = bodyRef.current
    setFieldErrors({})
    setError(null)
    const timer = window.setTimeout(() => {
      void apiSend<T>("POST", path, payload)
        .then((result) => {
          if (requestRef.current !== request) return
          setData(result)
          setFieldErrors({})
          setError(null)
        })
        .catch((caught: unknown) => {
          if (requestRef.current !== request) return
          setData(null)
          if (caught instanceof ApiError && caught.code === "validation_error") {
            const next: Record<string, string> = {}
            for (const [field, code] of Object.entries(caught.fields)) {
              next[field] = blockErrorKey(code)
            }
            setFieldErrors(next)
            setError(null)
            return
          }
          setFieldErrors({})
          setError("blocks.errors.previewCalc")
        })
    }, 300)
    return () => window.clearTimeout(timer)
  }, [key, path])

  return { data, fieldErrors, error }
}
