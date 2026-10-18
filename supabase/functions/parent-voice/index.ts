import { createHandler, VoiceError } from "./handler.ts";
const url = Deno.env.get("SUPABASE_URL") ?? "";
const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
// The gateway must overwrite this header. Never trust a caller-supplied header.
const ipHeader = Deno.env.get("PARENT_VOICE_TRUSTED_IP_HEADER") ?? "";
const origins = (Deno.env.get("PARENT_VOICE_ORIGINS") ?? "").split(",").map(
  (x) => x.trim(),
).filter(Boolean);
Deno.serve(createHandler({
  enabled: Deno.env.get("PARENT_VOICE_ENABLED") === "true" && !!url && !!key &&
    !!ipHeader && origins.length > 0,
  rateSecret: Deno.env.get("PARENT_VOICE_RATE_SECRET") ?? "",
  origins,
  clientIp: (request) => {
    const ip = ipHeader ? request.headers.get(ipHeader)?.trim() : null;
    return ip && /^[0-9a-fA-F:.]{3,64}$/.test(ip) ? ip : null;
  },
  rpc: async (name, args) => {
    const response = await fetch(`${url}/rest/v1/rpc/${name}`, {
      method: "POST",
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(args),
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) {
      const raw = await response.text();
      if (raw.includes("REQUEST_CONFLICT")) {
        throw new VoiceError("REQUEST_CONFLICT", 409);
      }
      if (raw.includes("RECEIPT_NOT_FOUND")) {
        throw new VoiceError("RECEIPT_NOT_FOUND", 404);
      }
      if (raw.includes("UNKNOWN_ACADEMY")) {
        throw new VoiceError("INVALID_INPUT");
      }
      throw new VoiceError("RETRY_LATER", 503, true);
    }
    return await response.json();
  },
}));
