# Parent service maintenance pilot

Approved direction: ranking attracts parents; evidence-backed comparison helps
them choose questions and a shortlist. Pilot: Mokdong × maths × elementary
(`elem_low` and `elem_high`). One OpenEdu task owner coordinates existing tools;
these jobs do not introduce additional autonomous agent identities.

## Active contracts introduced by this change

1. Nightly collection retains its existing 04:00 KST schedule, identity gates,
   deduplication, scoring formula, correction intake, tests and data publishing.
   Built-in setup-python pip caching is removed after the setup stack overflow
   in run 42531171510. The essential collected-source cache remains intact.
2. New public-health workflow: 07:30 KST daily and after successful deployment.
   It reads the public dataset, reports generation age and actual source-check
   ages, and generates up to 20 research tasks. Generation older than three days,
   blog/cafe checks older than seven days, unknown source health, demo data or
   invalid identities fail the health job. A fresh rebuild cannot make an old
   collection pass. Failed/unknown checks remain visible in Actions.
3. The report/artifact includes the branch ID, address, recorded subject-specific
   grade basis, gaps, official-source query and consultation questions. Ranked,
   unranked and grade-unknown strata share the work budget. Unknown grades do not
   become matches. `fitVerdict: not_assessed` is deliberate.
4. Rankings show their dataset generation date and delayed-update warning. This
   date does not certify that every underlying statement was verified then.
5. New paid summary, claim and profile model calls are capped at zero for this
   pilot. Cached results survive. No new external LLM provider is enabled.
   Local-model summary support is not implemented by this release.

Run a read-only public audit:

```sh
python -m pipeline.edutree.parent_service_audit --live \
  --output parent-service-health.json --fail-unhealthy
```

The public audit uses no credentials, model calls or child profiles. It never
writes rankings or sends messages. Research tasks are candidates, not verified
academy facts. Actions artifacts expire after 30 days; important verified
outcomes and correction fixtures belong in the existing scoped project wiki.

## Existing workflows to use for the pilot

| Work | Existing tool/contract | Completion evidence |
| --- | --- | --- |
| Review research | `run.py --agents plan` / reviewed browser collection | branch-matched source receipts; duplicates excluded |
| Official grade research | `grade_research` → candidate source ledger → verified grade sources | registered address and branch match; date and review expiry |
| Corrections | `run.py --cases`, `docs/AGENTS.md` | original report, resolution, regression fixture, successful replay |
| Comparison and questions | existing parent journey + comparison projection | source-linked context or explicit unknown; up to three candidates |
| Search growth | `search-growth.yml`, existing GSC/analytics contracts | complete-period impressions, visits, comparisons and contact-click events |
| Publication | existing collection → deployment workflow chain | successful run plus public bytes/data dates, rather than commit alone |

## Rollout after the first audit

- Verify the 20-branch worklist against official branch sources. Record each
  field as confirmed, conflicted, missing or expired. Do not infer suitability
  from buzz, entrance difficulty or a single parent's description.
- Verify a separate stratified sample of review attribution and dates. Existing
  correction fixtures prevent regressions; they are not a representative
  accuracy benchmark.
- Reuse existing source-note and grade ledgers for accepted evidence. Ambiguous
  branch matches, disputes, scoring changes and new progression links remain in
  review. Do not overwrite reviewed facts from untrusted web prose.
- Improve a small number of existing regional/subject pages using verified
  distinctions and unanswered consultation questions. Avoid mass template pages.
- Review monthly: profile → comparison → contact-click funnel, returning visits,
  stale facts, attribution errors and correction turnaround. Contact clicks do
  not prove consultations or enrolments. Missing analytics stays unknown.
- Expand beyond the pilot only after the shortlist reasons are traceable and
  public freshness is sustained. Daily generation of a worklist alone does not
  establish that its research or product outcomes were completed.

## Failure and recovery

Network failure means unknown health; never substitute sample data or invent a
verification date. Keep the previous published dataset if collection/validation
fails. Correct a source or rule through the existing case workflow, rerun the
relevant tests, and verify the public result. Keep scoring weights unchanged.

Schedules become active only after the workflow reaches the default branch.
Actual deployment and run outcomes are recorded in the dated pilot report.

## Evidence continuity and recovery

The 2026-11-09 recovery found that the GitHub source cache had expired during the
collection outage. A new empty collection must never be treated as a replacement
for the accumulated source history. The recovery seed contains the available
ORICO snapshot (94,577 raw records, last written October 17), not a complete
reconstruction of the later October 20 source cache. Existing exports and wiki
history remain preserved in Git.

- `evidence_backup restore` runs before collection. It restores an authenticated,
  encrypted durable checkpoint when the ordinary cache cannot prove continuity.
  Existing independently collected records are merged, and original first-seen
  dates are preserved. Missing keys, invalid archives and insufficient evidence
  stop the run before new collection.
- `evidence_backup checkpoint` runs after validation and before public data or
  mirror writes. It uploads an encrypted checkpoint to the dedicated
  `evidence-checkpoints` prerelease, downloads it again to verify the exact bytes,
  then retains the newest three successful checkpoints. Cleanup failures are
  reported; a failed/unverified upload never authorizes pruning or publication.
- Only whitelisted cache files are backed up. No `.env` or credentials enter the
  archive. The repository stores only encrypted recovery parts; the 32-byte key
  is held in `OPENEDU_EVIDENCE_BACKUP_KEY` and private local key backups.
- Collection receives the existing Supabase credentials so reviewed rules and
  verdicts can be read, rather than making them available only to mirror upload.
- For recovery review, run `rescore_only=true`, specify at most 20 target academy
  IDs, refresh NEIS if needed, and set `publish_data=false`. Inspect the ranked-data
  artifact and cohort/evidence changes. This retains encrypted evidence but skips
  public ranking commits and mirror writes. A subsequent reviewed cache rescore
  with publication enabled can publish without repeating the API research.
- An archive creation date is not a collection date or a post publication date.
  Source-health dates and unknown publication dates keep their original meaning.
- Public ranking and mirror writes also require the source-freshness audit to
  pass. A fresh generation timestamp cannot disguise stale/unavailable blog or
  cafe collection. Failed publication checks retain a health artifact and leave
  the existing public dataset in place; encrypted evidence is still preserved.

- The prepublication audit also compares accepted-evidence coverage against the
  deployed snapshot. A drop of more than 30%, or an unknown baseline, holds public
  writes for investigation. This is a release guard, not proof that old evidence
  was correct; attribution filters must never be loosened to make counts pass.
  A legitimate large correction needs a separately reviewed migration and replay.

## Low-token local daily review (2026-11-09)

The user authorised a daily update routine with local inference and small budgets.
The existing GitHub 04:00 collector and 07:30 public freshness audit remain the
collection/publication owners. New local job `work.itdo.openedu-daily` is a small
research review, not a second full ranking collector or an additional persona.

- 08:00 Asia/Seoul, once per date, beginning the day after installation. The local
  five-minute scheduler can catch up later that day if the Mac was asleep.
- Public Mokdong × elementary maths pilot only. Rotate two branches from the
  existing 20-item gap worklist. No family, child, Gmail or customer context.
- Python calls the existing Naver web-search API directly: two branch queries,
  three results each, at most four HTTP requests including connection detection.
  No paging, automatic retries, result-page crawling or new search subscription.
- Hash returned content. Unchanged branches need no local-model call. Changed
  snippets receive at most one digest-pinned local Qwen call per date: 3,072-token
  context, 256 output tokens, conservative byte admission and no thinking mode.
  Actual input/output counts are retained; local API spend is distinct from
  electricity, equipment and any existing search-service costs.
- The shared local-model admission queue gives routine and interactive requests
  priority. Busy, held, unavailable or changed models stop this attempt. There is
  no cloud fallback, model download, paid escalation or repeated same-day retry.
- Qwen can only select supplied result IDs for follow-up. It cannot publish facts,
  change scores, promote search snippets into verified grade claims, send messages,
  invoke tools or change its search/permission limits. Official branch verification
  remains a separate evidence step. The existing coverage publication hold remains.
- Atomic daily receipts and a readable latest report stay on ORICO in
  `pipeline/.cache/parent-daily/`. Interrupted attempts are retained and do not replay.
  A stale public service makes the local report partial, never a successful update.
- Installation pins source/adapter hashes and the model ID/digest. A changed binding
  requires a reviewed migration. The launcher has a 300-second outer watchdog;
  the local request has the shared adapter's 90-second timeout.

```sh
/Volumes/ORICO/wixxim/runtime/.venv/bin/python pipeline/install_parent_daily.py
/Volumes/ORICO/wixxim/runtime/.venv/bin/python -m pipeline.edutree.parent_daily status
/Volumes/ORICO/wixxim/runtime/.venv/bin/python -m pipeline.edutree.parent_daily pause
/Volumes/ORICO/wixxim/runtime/.venv/bin/python -m pipeline.edutree.parent_daily resume
```

Read `pipeline/.cache/parent-daily/latest.md` and `latest.json` for the observed
result. `run` performs one explicit acceptance attempt for the current date; it
shares the once-per-day receipt. Rollback: pause, then boot out
`gui/$(id -u)/work.itdo.openedu-daily`; preserve receipts and history. Installation
and a manual run do not prove a future 08:00 run or a reboot. The Mac must be
signed in and ORICO mounted; absent storage does not create an internal copy.
