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
): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, "network_error")
  }
  if (!response.ok) throw await errorFromResponse(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function apiGet<T>(path: string): Promise<T> {
  return apiSend<T>("GET", path)
}
