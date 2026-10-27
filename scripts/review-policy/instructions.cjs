//===--instructions.cjs-----------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

const { sections } = require('./checklist.cjs');
const marker = '<!-- peer-review-check:instructions:v1 -->';

function renderInstructions(author, contributors) {
  const reviewers = [...new Set(contributors.map(login => login.toLowerCase()))]
    .filter(login => login !== author.toLowerCase()).sort();
  const checklist = Object.entries(sections).map(([heading, items]) =>
    `## ${heading}\n${items.map(item => `- [ ] ${item}`).join('\n')}`).join('\n\n');
  return `${marker}
## Peer Review Instructions

This PR requires **two distinct contributor approvals**, each with a completed
checklist, on the **latest PR commit**. Maintainer approval is handled separately
by the repository's merge rules.

### Eligible Peer Reviewers

${reviewers.length ? reviewers.map(login => `@${login}`).join(', ') : 'No eligible contributors were found. Contact a repository maintainer.'}

The PR author cannot count toward the required approvals. This list reflects
team membership when this comment was posted; evaluation uses current membership.

### How to Submit Your Review

1. Review the latest changes under **Files changed**.
2. Select **Review changes** and choose **Approve**.
3. Paste the checklist below into your **review summary**.
4. Mark each item \`[x]\` only after verifying it, then submit your review.

Each reviewer must submit their own completed checklist. A checklist in the PR
description, a separate comment, or another reviewer's submission does not count.

### Reviewer Checklist

\`\`\`markdown
${checklist}
\`\`\`

If an item cannot be verified, raise the concern before approving. For the
suspicious-code item, a tick confirms either that no concern was found or that
the author supplied satisfactory sources.

### Check Results

**Peer-Review Check** reports the number of qualifying approvals received and
remaining. Missing or unchecked checklist items prevent an approval from counting.

New commits, including force-pushed changes, require fresh approvals and completed
checklists on the latest commit. Review submissions, edits, and dismissals trigger
automatic reevaluation; queue delays may apply.

Checklist completion records reviewer attestations. It does not replace CI,
license checks, signature verification, or maintainer review.

The checklist above is a non-interactive copy template. Editing this instruction
comment does not submit a review or affect the approval result.
`;
}

async function postInstructionsOnce({ github, repository, request, contributors }) {
  const comments = await github.paginate(github.rest.issues.listComments, {
    ...repository, issue_number: request.number, per_page: 100,
  });
  if (comments.some(comment => comment.user?.login === 'github-actions[bot]' &&
    comment.body?.startsWith(marker))) return;
  await github.rest.issues.createComment({
    ...repository, issue_number: request.number,
    body: renderInstructions(request.user.login, contributors),
  });
}

module.exports = { marker, renderInstructions, postInstructionsOnce };