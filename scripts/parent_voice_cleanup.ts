// Server-only scheduled maintenance. Never run this in a browser.
const url = Deno.env.get("SUPABASE_URL"),
  key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
if (!url || !key) throw new Error("Server environment is required");
const response = await fetch(`${url}/rest/v1/rpc/parent_voice_cleanup`, {
  method: "POST",
  headers: {
    apikey: key,
    Authorization: `Bearer ${key}`,
    "Content-Type": "application/json",
  },
  body: "{}",
  signal: AbortSignal.timeout(30000),
});
if (!response.ok) throw new Error("Parent voice cleanup failed");
const counts = await response.json();
console.log(
  JSON.stringify({ redacted: counts.redacted, purged: counts.purged }),
);
