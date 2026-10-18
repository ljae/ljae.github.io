// No request/body/error logging: notes and receipt secrets are private.
export class VoiceError extends Error {
  constructor(
    public code: string,
    public status = 422,
    public retryable = false,
  ) {
    super(code);
  }
}
const categories = new Set([
  "missing_info",
  "discovery_compare",
  "contact",
  "feature_request",
  "other",
]);
const pages = new Set(["home", "search", "compare", "academy", "other"]);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function object(
  value: unknown,
  keys: string[],
): Record<string, unknown> {
  if (
    !value || typeof value !== "object" || Array.isArray(value) ||
    Object.keys(value).some((k) => !keys.includes(k))
  ) throw new VoiceError("INVALID_INPUT");
  return value as Record<string, unknown>;
}
export function receipt(value: Record<string, unknown>, key: string) {
  if (
    typeof value[key] !== "string" || !uuid.test(value[key] as string) ||
    typeof value.receiptSecret !== "string" ||
    !/^[A-Za-z0-9_-]{43}$/.test(value.receiptSecret)
  ) throw new VoiceError("INVALID_INPUT");
}
export function normalizeSubmit(value: unknown) {
  const v = object(value, [
    "requestId",
    "receiptSecret",
    "category",
    "note",
    "context",
  ]);
  receipt(v, "requestId");
  if (
    typeof v.category !== "string" || !categories.has(v.category) ||
    (v.note !== undefined && typeof v.note !== "string")
  ) throw new VoiceError("INVALID_INPUT");
  const note = ((v.note ?? "") as string).normalize("NFC").replace(/\s+/gu, " ")
    .trim();
  if (
    [...note].length > 400 ||
    /[\p{L}\p{N}._%+-]+@[\p{L}\p{N}.-]+\.[\p{L}]{2,}/u.test(note) ||
    /(?:\+82[- .]?)?0?1[016789][- .]?\d{3,4}[- .]?\d{4}|0\d{1,2}[- .]?\d{3,4}[- .]?\d{4}/u
      .test(note)
  ) throw new VoiceError("NEEDS_EDIT");
  const context = v.context === undefined
    ? {}
    : object(v.context, ["pageType", "academyId"]);
  if (
    context.pageType !== undefined &&
    (typeof context.pageType !== "string" || !pages.has(context.pageType))
  ) throw new VoiceError("INVALID_INPUT");
  if (
    context.academyId !== undefined && context.academyId !== null &&
    (typeof context.academyId !== "string" ||
      !/^\d{1,20}$/.test(context.academyId))
  ) throw new VoiceError("INVALID_INPUT");
  return {
    requestId: v.requestId as string,
    receiptSecret: v.receiptSecret as string,
    category: v.category,
    note,
    pageType: context.pageType ?? null,
    academyId: context.academyId ?? null,
  };
}
export async function hash(s: string) {
  return [
    ...new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)),
    ),
  ].map((b) => b.toString(16).padStart(2, "0")).join("");
}
export async function clientHash(ip: string, secret: string) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return [
    ...new Uint8Array(
      await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(ip)),
    ),
  ].map((b) => b.toString(16).padStart(2, "0")).join("");
}
export interface Dependencies {
  origins: string[];
  enabled: boolean;
  rateSecret: string;
  clientIp: (request: Request) => string | null;
  rpc: (name: string, args: Record<string, unknown>) => Promise<unknown>;
}
const messages: Record<string, string> = {
  NEEDS_EDIT: "개인 연락처를 빼고 400자 이내로 적어주세요.",
  RATE_LIMITED: "요청이 많습니다. 잠시 뒤 다시 시도해주세요.",
  UNAVAILABLE: "현재 의견 접수를 준비 중입니다.",
  RETRY_LATER: "보내지 못했습니다. 같은 요청으로 다시 시도해주세요.",
  RECEIPT_NOT_FOUND: "확인 코드가 맞지 않거나 보관 기한이 지났습니다.",
  REQUEST_CONFLICT: "이미 사용된 요청입니다. 새 의견으로 작성해주세요.",
};
export function createHandler(deps: Dependencies) {
  return async (request: Request) => {
    const origin = request.headers.get("Origin");
    const headers: Record<string, string> = {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "Vary": "Origin",
    };
    if (origin && deps.origins.includes(origin)) {
      headers["Access-Control-Allow-Origin"] = origin;
      headers["Access-Control-Allow-Headers"] =
        "authorization, apikey, content-type, x-client-info";
      headers["Access-Control-Allow-Methods"] = "POST, OPTIONS";
    }
    const send = (status: number, body: unknown) =>
      new Response(status === 204 ? null : JSON.stringify(body), {
        status,
        headers,
      });
    try {
      if (origin && !deps.origins.includes(origin)) {
        throw new VoiceError("ORIGIN_DENIED", 403);
      }
      if (request.method === "OPTIONS") return send(204, null);
      if (request.method !== "POST") {
        throw new VoiceError("METHOD_NOT_ALLOWED", 405);
      }
      if (!deps.enabled || deps.rateSecret.length < 32) {
        throw new VoiceError("UNAVAILABLE", 503, true);
      }
      const action = new URL(request.url).pathname.split("/").filter(Boolean)
        .at(-1);
      if (!["submit", "status", "delete"].includes(action ?? "")) {
        throw new VoiceError("NOT_FOUND", 404);
      }
      const ip = deps.clientIp(request);
      if (!ip) throw new VoiceError("UNAVAILABLE", 503, true);
      const allowed = await deps.rpc("parent_voice_rate", {
        p_key: await clientHash(ip, deps.rateSecret),
        p_lane: action === "submit" ? "submit" : "access",
        p_limit: action === "submit" ? 5 : 30,
        p_global_limit: action === "submit" ? 200 : 1000,
      });
      if (allowed !== true) {
        headers["Retry-After"] = "600";
        throw new VoiceError("RATE_LIMITED", 429, true);
      }
      // Bound streamed bytes too; Content-Length alone is not a security boundary.
      const reader = request.body?.getReader();
      let bytes = 0;
      const parts: Uint8Array[] = [];
      if (reader) {
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            bytes += value.length;
            if (bytes > 8192) {
              await reader.cancel();
              throw new VoiceError("TOO_LARGE", 413);
            }
            parts.push(value);
          }
        } finally {
          reader.releaseLock();
        }
      }
      const buffer = new Uint8Array(bytes);
      let offset = 0;
      for (const p of parts) {
        buffer.set(p, offset);
        offset += p.length;
      }
      let body: unknown;
      try {
        body = JSON.parse(
          new TextDecoder("utf-8", { fatal: true }).decode(buffer),
        );
      } catch {
        throw new VoiceError("INVALID_INPUT");
      }
      if (action === "submit") {
        const v = normalizeSubmit(body);
        const secretHash = await hash(v.receiptSecret);
        const payloadHash = await hash(
          JSON.stringify([v.category, v.note, v.pageType, v.academyId]),
        );
        const row = await deps.rpc("parent_voice_submit", {
          p_request_id: v.requestId,
          p_secret_hash: secretHash,
          p_payload_hash: payloadHash,
          p_category: v.category,
          p_note: v.note,
          p_page_type: v.pageType,
          p_academy_id: v.academyId,
        }) as Record<string, unknown>;
        return send(row.created ? 201 : 200, {
          receiptId: row.receiptId,
          status: row.status,
          createdAt: row.createdAt,
        });
      }
      const v = object(body, ["receiptId", "receiptSecret"]);
      receipt(v, "receiptId");
      const result = await deps.rpc("parent_voice_receipt", {
        p_id: v.receiptId,
        p_secret_hash: await hash(v.receiptSecret as string),
        p_delete: action === "delete",
      });
      return send(action === "delete" ? 204 : 200, result);
    } catch (error) {
      const e = error instanceof VoiceError
        ? error
        : new VoiceError("RETRY_LATER", 503, true);
      return send(e.status, {
        code: e.code,
        message: messages[e.code] ?? "입력 내용을 확인해주세요.",
        retryable: e.retryable,
      });
    }
  };
}
