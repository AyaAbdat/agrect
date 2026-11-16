const TOKEN_KEY = "agrect.token"

export function getToken(): string | null {
  try {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token === null || token === "") return null
    return token
  } catch {
    return null
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Storage can be blocked; later reads behave as no token.
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage can be blocked; later reads behave as no token.
  }
}
