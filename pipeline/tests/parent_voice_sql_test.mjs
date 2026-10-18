// Executes the production HTTP handler against PostgreSQL (PGlite); synthetic data only.
// npm install --prefix /tmp/openedu-parent-sql @electric-sql/pglite@0.5.10 tsx@4.23.15
// PGLITE_MODULE=/tmp/openedu-parent-sql/node_modules/@electric-sql/pglite/dist/index.js node --import /tmp/openedu-parent-sql/node_modules/tsx/dist/loader.mjs pipeline/tests/parent_voice_sql_test.mjs
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  createHandler,
  normalizeSubmit,
  VoiceError,
} from "../../supabase/functions/parent-voice/handler.ts";
const { PGlite } = await import(
  process.env.PGLITE_MODULE || "@electric-sql/pglite"
);
const db = new PGlite();
const admin = "00000000-0000-0000-0000-000000000001";
await db.exec(
  `create role anon;create role authenticated;create role service_role bypassrls;
create schema auth;
create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
create function auth.role() returns text language sql stable as $$select current_setting('request.jwt.claim.role',true)$$;
create function public.is_admin() returns boolean language sql stable security definer as $$select coalesce(auth.uid()='${admin}'::uuid,false)$$;
create table academies(aca_asnum text primary key); insert into academies values('123');
create table academy_actions(action text constraint academy_actions_action_check check(action in ('call','reserve','copy_tel','map')));`,
);
const migration = await readFile(
  new URL("../../supabase/16_parent_voice.sql", import.meta.url),
  "utf8",
);
await db.exec(migration);
await db.exec(migration);
await db.exec("insert into academy_actions values('reserve'),('homepage')");
assert.equal((await db.query("select * from academy_actions")).rows.length, 2);
const role = async (name, user = "") => {
  await db.exec("reset role");
  await db.query(
    "select set_config('request.jwt.claim.role',$1,false),set_config('request.jwt.claim.sub',$2,false)",
    [name, user],
  );
  await db.exec(`set role ${name}`);
};
const rpc = async (name, args) => {
  try {
    return (await db.query(
      `select public.${name}(${
        Object.keys(args).map((k, i) => `${k} => $${i + 1}`).join(",")
      }) as result`,
      Object.values(args),
    )).rows[0].result;
  } catch (e) {
    if (e.message.includes("REQUEST_CONFLICT")) {
      throw new VoiceError("REQUEST_CONFLICT", 409);
    }
    if (e.message.includes("RECEIPT_NOT_FOUND")) {
      throw new VoiceError("RECEIPT_NOT_FOUND", 404);
    }
    if (e.message.includes("UNKNOWN_ACADEMY")) {
      throw new VoiceError("INVALID_INPUT");
    }
    throw e;
  }
};
const deps = {
  origins: ["https://openedu4u.com"],
  enabled: true,
  rateSecret: "synthetic-rate-key-only-for-local-tests-0000",
  clientIp: () => "127.0.0.1",
  rpc,
};
const handler = createHandler(deps);
const invoke = async (action, body, options = {}) =>
  handler(
    new Request(`https://test.invalid/functions/v1/parent-voice/${action}`, {
      method: "POST",
      headers: {
        Origin: "https://openedu4u.com",
        "Content-Type": "application/json",
        ...options.headers,
      },
      body: JSON.stringify(body),
    }),
  );
const input = {
  requestId: "00000000-0000-4000-8000-000000000010",
  receiptSecret: "a".repeat(43),
  category: "feature_request",
  note: "후보를 비교하고 싶어요.",
  context: { pageType: "compare", academyId: "123" },
};
await role("service_role");
let response = await invoke("submit", input);
assert.equal(response.status, 201);
const receipt = await response.json();
assert.ok(receipt.receiptId);
assert.equal("receiptSecret" in receipt, false);
response = await invoke("submit", input);
assert.equal(response.status, 200);
assert.equal((await response.json()).receiptId, receipt.receiptId);
assert.equal(
  (await invoke("submit", { ...input, note: "다른 내용" })).status,
  409,
);
assert.equal(
  (await invoke("status", {
    receiptId: receipt.receiptId,
    receiptSecret: "b".repeat(43),
  })).status,
  404,
);
response = await invoke("status", {
  receiptId: receipt.receiptId,
  receiptSecret: input.receiptSecret,
});
assert.equal(response.status, 200);
assert.deepEqual(Object.keys(await response.json()).sort(), [
  "safeResolution",
  "status",
  "updatedAt",
]);
await role("anon");
for (
  const table of [
    "parent_feedback",
    "parent_feedback_audit",
    "parent_voice_limits",
    "parent_improvement_feedback",
  ]
) {
  await assert.rejects(
    () => db.query(`select * from ${table}`),
    /permission denied/,
  );
}
await assert.rejects(
  () =>
    db.query(
      "insert into parent_feedback(request_id,category) values(gen_random_uuid(),'other')",
    ),
  /permission denied/,
);
await assert.rejects(
  () =>
    db.query("select parent_voice_receipt($1,$2,false)", [
      receipt.receiptId,
      "a".repeat(64),
    ]),
  /permission denied/,
);
await assert.rejects(
  () => db.query("select parent_voice_admin_queue(0)"),
  /permission denied/,
);
assert.equal(
  (await db.query("select * from parent_improvements")).rows.length,
  0,
);
await role("authenticated", "00000000-0000-0000-0000-000000000002");
await assert.rejects(
  () => db.query("select * from parent_feedback"),
  /permission denied/,
);
await assert.rejects(
  () => db.query("select parent_voice_admin_queue(0)"),
  /ADMIN_REQUIRED/,
);
await assert.rejects(
  () => db.query("update parent_feedback set status='resolved'"),
  /permission denied/,
);
await role("authenticated", admin);
const queue =
  (await db.query("select * from parent_voice_admin_queue(0)")).rows;
assert.equal(queue.length, 1);
assert.equal(queue[0].receipt_secret_hash, null);
assert.equal(queue[0].payload_hash, null);
const transition = (state, version) =>
  db.query("select parent_voice_transition($1,$2,$3,$4,$5,$6)", [
    receipt.receiptId,
    version,
    state,
    "검토 결과를 안내합니다.",
    "검토용 메모",
    null,
  ]);
await assert.rejects(() => transition("resolved", 1), /INVALID_TRANSITION/);
await transition("triaged", 1);
await assert.rejects(() => transition("planned", 1), /VERSION_CONFLICT/);
await assert.rejects(
  () => transition("duplicate", 2),
  /DUPLICATE_TARGET_REQUIRED/,
);
await transition("planned", 2);
await transition("in_progress", 3);
await transition("resolved", 4);
const publish = (id = receipt.receiptId) =>
  db.query("select parent_voice_publish($1,$2,$3,$4,$5,$6)", [
    id,
    "비교 화면 개선",
    "공개되는 개선 요약입니다.",
    "123abcd",
    "local-synthetic-deployment",
    "https://openedu4u.com/",
  ]);
await publish();
await assert.rejects(() => publish(), /ALREADY_PUBLISHED/);
await role("anon");
const publicRows = (await db.query("select * from parent_improvements")).rows;
assert.equal(publicRows.length, 1);
assert.equal("note" in publicRows[0], false);
assert.equal("feedback_id" in publicRows[0], false);
await role("service_role");
// Valid independent requests with identical words remain separate; only request IDs deduplicate.
await db.exec("delete from parent_voice_limits");
const second = { ...input, requestId: "00000000-0000-4000-8000-000000000011" };
const r2 = await (await invoke("submit", second)).json();
assert.notEqual(r2.receiptId, receipt.receiptId);
assert.equal((await db.query("select * from parent_feedback")).rows.length, 2);
response = await invoke("delete", {
  receiptId: receipt.receiptId,
  receiptSecret: input.receiptSecret,
});
assert.equal(response.status, 204);
const removed = (await db.query("select * from parent_feedback where id=$1", [
  receipt.receiptId,
])).rows[0];
assert.equal(removed.note, null);
assert.equal(removed.receipt_secret_hash, null);
assert.equal(removed.internal_resolution, null);
assert.equal(
  (await invoke("status", {
    receiptId: receipt.receiptId,
    receiptSecret: input.receiptSecret,
  })).status,
  404,
);
// Retention and limit cleanup operate on actual stored rows.
await db.query(
  "update parent_feedback set created_at=now()-interval '100 days' where id=$1",
  [r2.receiptId],
);
await db.query("select parent_voice_cleanup()");
assert.equal(
  (await db.query("select note from parent_feedback where id=$1", [
    r2.receiptId,
  ])).rows[0].note,
  null,
);
await db.query(
  "update parent_feedback set created_at=now()-interval '181 days' where id=$1",
  [r2.receiptId],
);
await db.query("select parent_voice_cleanup()");
assert.equal(
  (await db.query("select * from parent_feedback where id=$1", [r2.receiptId]))
    .rows.length,
  0,
);
// Gate-specific request validation executes before storage, including Unicode length.
for (
  const note of ["이메일 parent@example.com", "010-1234-5678", "😀".repeat(401)]
) assert.throws(() => normalizeSubmit({ ...input, note }), VoiceError);
assert.equal(
  [...normalizeSubmit({ ...input, note: "😀".repeat(400) }).note].length,
  400,
);
assert.throws(() => normalizeSubmit({ ...input, budget: 100 }), VoiceError);
assert.equal(
  (await createHandler({ ...deps, enabled: false })(
    new Request("https://test/submit", { method: "POST", body: "{}" }),
  )).status,
  503,
);
assert.equal(
  (await invoke("submit", input, {
    headers: { Origin: "https://evil.invalid" },
  })).status,
  403,
);
await db.exec("delete from parent_voice_limits");
for (let i = 0; i < 5; i++) {
  assert.equal(
    (await invoke("submit", {
      ...input,
      requestId: `00000000-0000-4000-8000-${
        (100 + i).toString().padStart(12, "0")
      }`,
    })).status,
    201,
  );
}
assert.equal(
  (await invoke("submit", {
    ...input,
    requestId: "00000000-0000-4000-8000-000000000200",
  })).status,
  429,
);
const failed = createHandler({
  ...deps,
  rpc: async () => {
    throw new Error("private database details");
  },
});
response = await failed(
  new Request("https://test/submit", { method: "POST", body: "{}" }),
);
assert.equal(response.status, 503);
assert.equal((await response.text()).includes("private database"), false);
console.log(
  "PASS: production HTTP handler + PostgreSQL migration, idempotency, RLS/GRANT/RPC authorization, receipt isolation/deletion, admin state/version/publication, retention, Unicode/input limits, rate limits and fail-closed errors. No hosted gateway or remote database was used.",
);
await db.close();
