//===--policy.cjs-----------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

const { validateChecklist } = require('./checklist.cjs');

function evaluateReviews({ author, headSha, reviews, contributors }) {
  const normalize = login => login.toLowerCase();
  const authorLogin = normalize(author);
  const peers = new Set(contributors.map(normalize));
  const latest = new Map();
  const approvalsByCommit = new Map();
  const ordered = [...reviews].sort((first, second) =>
    Date.parse(first.submitted_at) - Date.parse(second.submitted_at) || first.id - second.id);

  for (const review of ordered) {
    if (!review.user?.login || !review.submitted_at) continue;
    if (!['APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'].includes(review.state)) continue;
    const login = normalize(review.user.login);
    if (login === authorLogin || !peers.has(login)) continue;
    latest.set(login, review);
    if (review.commit_id) {
      const approved = approvalsByCommit.get(review.commit_id) || new Set();
      if (review.state === 'APPROVED' && validateChecklist(review.body).complete) approved.add(login);
      else approved.delete(login);
      approvalsByCommit.set(review.commit_id, approved);
    }
  }

  const blockers = [...latest.entries()]
    .filter(([, review]) => review.state === 'CHANGES_REQUESTED')
    .map(([login]) => login);
  if (blockers.length) {
    return { approved: false, reason: `Changes requested by ${blockers.join(', ')}` };
  }

  const currentApprovals = [...latest.entries()].filter(([, review]) =>
    review.state === 'APPROVED' && review.commit_id === headSha);
  const approvals = currentApprovals.filter(([, review]) => validateChecklist(review.body).complete);
  const incomplete = currentApprovals.length - approvals.length;
  const progress = `2 required, ${approvals.length} received, ${Math.max(0, 2 - approvals.length)} remaining.`;
  if (approvals.length >= 2) {
    return {
      approved: true,
      reason: `Approved. Contributor approvals with complete checklists: ${progress}`,
    };
  }
  const previouslyApproved = [...approvalsByCommit.entries()].some(([commit, approved]) =>
    commit !== headSha && approved.size >= 2);
  if (incomplete > 0) {
    return {
      approved: false,
      reason: `Checklist not completed as part of review approval. ${progress} ${incomplete} incomplete.`,
    };
  }
  return {
    approved: false,
    reason: previouslyApproved
      ? `Reapproval required for the latest PR commit. Contributor approvals: ${progress}`
      : `Contributor approvals for the latest PR commit: ${progress}`,
  };
}

module.exports = { evaluateReviews };