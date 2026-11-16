import { clearToken, getToken } from "./auth"

let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

export class ApiError extends Error {
  status: number
  code: string
  fields: Record<string, string>

  constructor(
    status: number,
    code: string,
    fields: Record<string, string> = {},
  ) {
    super(code)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.fields = fields
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json()
    if (!isRecord(body)) {
      return new ApiError(response.status, "network_error")
    }
    const code =
      typeof body.code === "string" && body.code !== ""
        ? body.code
        : "network_error"
    const fields: Record<string, string> = {}
    if (isRecord(body.fields)) {
      for (const [key, value] of Object.entries(body.fields)) {
        if (typeof value === "string") fields[key] = value
      }
    }
    return new ApiError(response.status, code, fields)
  } catch {
    return new ApiError(response.status, "network_error")
  }
}

export async function apiSend<T>(
  method: string,
  path: string,
  body?: unknown,
  extraHeaders?: Record<string, string>,
): Promise<T> {
  const headers: Record<string, string> = { ...extraHeaders }
  if (body !== undefined) headers["Content-Type"] = "application/json"
  const token = getToken()
  if (token !== null) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers: Object.keys(headers).length > 0 ? headers : undefined,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, "network_error")
  }
  if (!response.ok) {
    const error = await errorFromResponse(response)
    if (response.status === 401) {
      clearToken()
      onUnauthorized?.()
    }
    throw error
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function apiGet<T>(path: string): Promise<T> {
  return apiSend<T>("GET", path)
}
