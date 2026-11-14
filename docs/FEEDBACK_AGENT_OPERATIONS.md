# OpenEdu comment and correction review

One local reviewer handles non-empty user board posts/comments, academy reviews,
private parent feedback and correction requests. Official generated posts, hidden,
deleted and already closed requests are excluded. Replies are labelled 학원실록 AI;
no AI reply changes a review rating, evidence weight or ranking.

The database queues each current source revision. One claim authorizes one local
classification attempt. At most 12 claims per Korean calendar day are admitted,
including attempts on old backlog entries. The pinned Qwen adapter uses 2,048
context / 96 output tokens, background admission and a 90-second request deadline.
The Mac launcher has a 180-second outer deadline. There is no cloud-model fallback.
Idle polls make no model calls. Model output selects an intent only: it cannot
provide tools, fact values, destinations or permission. Replies use bounded templates.

The first automatic fact type is a telephone-number correction: one unambiguous
requested number, exact NEIS registration/name/street-address identity, and a fresh
NEIS record agreeing with that number. The worker makes one fixed-endpoint official
lookup without redirects or retries. SQL validates the evidence envelope and writes
the reviewed phone overlay and request reply atomically. The app reads this dated
overlay for contact cards; a read is not evidence that a telephone actually connects.
Other facts, branch identity/address changes, removal, disputed information and
ranking changes are held for the owner. They do not become facts from user prose.

The requesting owner selected the existing itdo Jae work-status Slack channel.
The private installation config binds its existing channel mapping; no channel or
bot credentials belong in Git. Exception notices contain a request ID, a short
reason and the administrator link, not contact details or request text. An ambiguous
Slack send is never replayed automatically. Pending/sending/unknown/sent are distinct.

Anonymous correction receipts use a random 256-bit capability, stored hashed in the
database. The device session stores only receipt ID, secret and academy key, not
request text or contact. Receipt lookup returns only processing status and the
short reply. Reopening the correction sheet permits checking that receipt. Private
parent feedback keeps its existing receipt/deletion flow. Public replies appear
beside the corresponding post/comment/review.

## Operation

`pipeline/install_feedback_agent.py` installs `work.itdo.openedu-feedback`, initially
paused. The launcher polls every five minutes while this Mac is awake, the account
is signed in and ORICO is mounted. Acceptance precedes activation. Reinstalling
refuses source/schedule drift. The active config is
`pipeline/.cache/feedback-agent/config.json` (private, excluded from Git).

Pause by changing only `paused` to true in that config; resume with false. Source,
SQL, model or shared-adapter changes require explicit binding migration after tests.
`python -m pipeline.edutree.feedback_agent` performs one bounded tick. Model failure
uses a truthful held-for-review reply; interruption or lease expiry preserves an
uncertain attempt. Editing/deleting/hiding a source supersedes unfinished work.
Do not clear an uncertain attempt or resend a Slack notice to manufacture success.

Rollback: pause the installed job first. Existing reply/receipt columns and audit
records can remain. Revert the app to the preceding release; disable the five
`ai_feedback_queue` triggers if intake must stop. Preserve accepted fact receipts
and unknown Slack outcomes; do not delete source submissions or evidence.

Verification: `pipeline/tests/feedback_agent_sql_test.mjs` covers migration replay,
roles, forged replies, receipt secrecy/retries, evidence enforcement, edit races,
lease expiry and the daily limit against PostgreSQL/PGlite. Python tests cover
source matching, prompt injection boundaries and conservative decisions. Flutter
checks cover the real bundled apartment beyond the former top40 and dated phone
projection. The map Node checks fail on the old source and pass on the new one.
Runtime/browser/model and real Slack delivery are separate acceptance observations.
