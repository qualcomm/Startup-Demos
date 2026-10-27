# Peer-Review Check

## Reviewer Checklist

The evaluator posts one bot-authored instruction comment per PR, identified by
a hidden marker. It lists eligible peers (excluding the author) and includes
the checklist in a fenced code block with no clickable checkboxes. Later runs
do not update or repost it. Deleted comments can be recreated. Reviewers with
comment-edit permissions can edit the text, but instruction comments never
count as approval reviews. Team membership is reevaluated independently.

Each of the two counted contributors must include the complete
[review checklist](REVIEW_CHECKLIST.md) in the body of their **Approve** review.
Copy the template into the review summary and mark every item `- [x]` only after
verifying it. Keep the item text unchanged; case and whitespace are ignored.
Items cannot be missing, unchecked, duplicated, quoted, commented out, or inside
code blocks. A checklist in the PR description, a separate comment, or another
reviewer's approval does not count for your review.

Only approvals on the latest PR commit with all 18 items checked count toward
the required two. The status reports eligible approval counts and how many
current approvals have incomplete checklists. Review edits trigger reevaluation.
Maintainer approval remains a separate native GitHub requirement.

Checklist ticks are reviewer attestations, not automated inspection of code,
licenses, signatures, media rights, or CI results. Do not mark an unverified item
complete. If no suspicious code exists, the source-verification item attests that
the reviewer found no such concern. Resolve applicable reviewer threads before
checking the final item; later threads are governed by native resolution rules.

Status messages show approval progress, such as
`2 required, 1 received, 1 remaining`. Only distinct eligible approvals on the
latest PR commit count. A previously approved commit requires reapproval after
new commits are pushed.

Requires two distinct Contributors-team approvals on the current PR commit.
The PR author cannot count. Contributors do not need Write access. GitHub's
native approval rule handles maintainer approval separately; ordering does not
matter. A maintainer who also belongs to Contributors can count as a peer.

New commits require fresh peer approvals. Outstanding changes requested from the
Contributors team block approval until superseded or dismissed. Comments do not erase an
 existing review. Draft PRs cannot pass.

Review submission, edits, and dismissals trigger automatic reevaluation through
the signal workflow; queue delays may apply. The published status distinguishes
missing approvals, approval, and required reapproval after a previously approved
commit changes. The workflow job checks indicate successful execution, while
`Peer-Review Check` contains the approval decision.

## Setup

In the source repository's merge-queue ruleset:

- Require `Peer-Review Check` from GitHub Actions and keep `reverse-sync/aggregate`.
- Require one native approval from an eligible Write-or-higher reviewer.
- Keep Contributors-team native approval requirements unset.
- Review bypass actors; Always bypass remains an exception to this policy.

The evaluator uses only `SYNC_SOURCE_TOKEN`
to list the `contributors-startup-demos` team.
The credential needs organization Members read access (or an appropriately
authorized classic PAT with `read:org`). Failure to read membership blocks the
check; no token is printed. Statuses use the automatic `GITHUB_TOKEN`.

The Ubuntu source gate skips repositories without matching `SYNC_SOURCE_URL`.
Evaluation runs on `self-hosted` without checkout and loads only trusted policy
code through the GitHub API, pinned to one default-branch commit, never PR code.
The runner must have API access permitted by the organization's IP policy.
The unprivileged review-event workflow
triggers evaluation through `workflow_run`; no artifacts or scripts from that
run are consumed. Fork review workflows may need approval under repository
Actions policies. A 15-minute scheduled reconciliation also refreshes reviews
and membership; GitHub schedules are not immediate or guaranteed on time.

Merge groups are checked separately: every included open PR must satisfy the
peer policy. Approval order and maintainer membership are not checked here.
Protect policy scripts and workflows through trusted maintainer review.

## Tests

```bash
node --test scripts/review-policy/tests/*.test.cjs
```