// Thin client for the StockPilot API.
// - Same-origin only; the session cookie is HttpOnly and never touched here.
// - Unsafe methods send the CSRF token from the __Host-csrf cookie.
// - 401 sends the user to /login (a fixed path; no user-controlled redirect).

export type Role = "viewer" | "member" | "manager" | "owner";
export type User = { id: string; email: string; display_name: string; is_platform_admin: boolean };
export type Session = { user: User; csrf_token: string };
export type Workspace = { id: string; name: string; description: string; role: Role };
export type Member = { user_id: string; display_name: string; email: string; job_title: string | null; role: Role; joined_at: string };
export type Invitation = { id: string; email: string; role: Role; expires_at: string; created_at: string; invite_url?: string };
export type Location = { id: string; code: string; name: string };
export type StockLevelRow = { location_id: string; location_code: string; quantity: number };
export type Product = {
  id: string; sku: string; name: string; unit: string; reorder_level: number; total_quantity: number; low_stock: boolean; levels: StockLevelRow[];
};
export type Transfer = {
  id: string; reference: string; product_id: string; from_location_id: string; to_location_id: string; quantity: number; status: string; created_at: string;
};
export type PurchaseOrder = { id: string; reference: string; supplier: string; product_id: string; location_id: string; quantity: number; status: string; created_at: string };
export type ActivityItem = { id: number; at: string; actor_name: string | null; verb: string; object_type: string; summary: string; link: string | null };
export type Dashboard = { products: number; locations: number; total_units: number; low_stock: number; open_purchase_orders: number;
  recent_activity: { id: number; at: string; actor_name: string | null; summary: string }[] };
export type Alert = { id: number; at: string; rule: string; severity: string; summary: string; status: string };


export const RANK: Record<Role, number> = { viewer: 0, member: 1, manager: 2, owner: 3 };

export class ApiError extends Error {
  constructor(public status: number, public code: string, public requestId?: string) {
    super(code);
  }
}

const SAFE = new Set(["GET", "HEAD", "OPTIONS"]);

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)__Host-csrf=([^;]+)/);
  return m?.[1] ? decodeURIComponent(m[1]) : "";
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  if (!path.startsWith("/api/")) throw new Error("api() only calls this site's /api/ routes");
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  if (!SAFE.has(method)) headers.set("X-CSRF-Token", csrfToken());

  const res = await fetch(path, { ...init, method, headers, body, credentials: "same-origin", cache: "no-store" });
  if (res.status === 401 && !path.endsWith("/auth/login") && !path.includes("/invitations/")) {
    window.location.assign("/login");
    throw new ApiError(401, "authentication_required");
  }
  if (!res.ok) {
    let code = "error";
    let rid: string | undefined;
    try {
      const j = await res.json();
      code = j.error ?? code;
      rid = j.request_id;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, rid);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const known: Record<string, string> = {
      invalid_credentials: "Incorrect email or password.",
      too_many_requests: "Too many attempts. Please wait a few minutes and try again.",
      forbidden: "You don't have permission to do that.",
      not_found: "Not found.",
      file_type_not_allowed: "That file type isn't allowed. Use PNG, JPEG, PDF or plain text (including Markdown).",
      file_too_large: "That file is too large.",
      validation_error: "Please check the form and try again.",
      last_owner: "A workspace needs at least one owner.",
      already_member: "That person is already a member.",
      invitation_invalid: "This invitation link is invalid, already used, or expired.",
      invitation_for_other_email: "This invitation was sent to a different email address.",
      account_exists: "An account with this email already exists. Sign in to accept the invitation.",
      weak_password: "Choose a stronger password: at least 12 characters, not a common one.",
      sku_taken: "That SKU is already used in this warehouse.",
      location_exists: "That location code already exists.",
      insufficient_stock: "Not enough stock at that location.",
      already_closed: "That purchase order is already closed.",
      internal_error: "Something went wrong on our side.",
    };
    return (known[e.code] ?? "Request failed.") + (e.requestId ? ` (ref ${e.requestId.slice(0, 8)})` : "");
  }
  return "Network error. Please try again.";
}

export function fmtDate(d: string | null): string {
  if (!d) return "—";
  return new Date(d.length === 10 ? d + "T00:00:00" : d).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function timeAgo(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
