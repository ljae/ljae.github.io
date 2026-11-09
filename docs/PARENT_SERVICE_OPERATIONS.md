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
