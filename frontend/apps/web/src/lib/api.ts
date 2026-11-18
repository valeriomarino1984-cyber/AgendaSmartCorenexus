/**
 * Client per l'API /api/v1. Stesso dominio del sito: la sessione viaggia nel cookie HttpOnly,
 * il codice JavaScript non vede mai il token.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

type Json = Record<string, unknown> | unknown[];

export async function api<T = unknown>(
  path: string,
  options: { method?: string; body?: Json } = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method: options.method ?? (options.body ? "POST" : "GET"),
      credentials: "same-origin",
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "rete", "Connessione non riuscita. Controlla la rete e riprova.");
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = data?.error ?? {};
    throw new ApiError(
      response.status,
      error.code ?? "errore",
      friendlyMessage(response.status, error.code, error.message, error.details),
      error.details,
    );
  }
  return data as T;
}

function friendlyMessage(status: number, code?: string, message?: string, details?: unknown): string {
  if (code === "validation_error" && Array.isArray(details) && details.length) {
    const first = details[0] as { msg?: string };
    // I messaggi dei nostri validatori sono già in italiano ("Value error, ...").
    if (first.msg) return first.msg.replace(/^Value error, /, "");
  }
  if (message) return message;
  if (status >= 500) return "Si è verificato un errore. Riprova tra qualche minuto.";
  return "Richiesta non riuscita.";
}

export interface Me {
  user: { id: string; email: string; full_name: string };
  tenant: {
    id: string;
    name: string;
    slug: string;
    business_type: string;
    status: string;
    trial_ends_at: string | null;
  };
  role: "owner" | "professional" | "secretary";
  role_label: string;
  tenants: { id: string; name: string; role: string; role_label: string }[];
}
