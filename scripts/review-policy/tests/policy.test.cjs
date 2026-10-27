//===--policy.test.cjs------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { evaluateReviews } = require('../policy.cjs');
const { sections } = require('../checklist.cjs');
const checklist = Object.values(sections).flat().map(item => `- [x] ${item}`).join('\n');

function review(login, order, state = 'APPROVED', commit = 'head') {
  return {
    id: order, user: { login }, state, commit_id: commit, body: checklist,
    submitted_at: new Date(Date.UTC(2026, 9, 27, 0, order)).toISOString(),
  };
}

function evaluate(reviews, overrides = {}) {
  return evaluateReviews({
    author: 'author', headSha: 'head', reviews,
    contributors: ['peer1', 'peer2', 'peer3', 'author'], ...overrides,
  }).approved;
}

test('accepts two peers without any maintainer review', () => {
  assert.equal(evaluate([review('peer1', 1), review('peer2', 2)]), true);
});
test('does not count the author', () => {
  assert.equal(evaluate([review('author', 1), review('peer2', 2), review('owner', 3)]), false);
});
test('does not count duplicate peer reviews', () => {
  assert.equal(evaluate([review('peer1', 1), review('peer1', 2), review('owner', 3)]), false);
});
test('maintainer approval before peers does not affect the peer gate', () => {
  assert.equal(evaluate([review('owner', 1), review('peer1', 2), review('peer2', 3)]), true);
});
test('maintainer reapproval is not needed', () => {
  assert.equal(evaluate([review('owner', 1), review('peer1', 2), review('peer2', 3), review('owner', 4)]), true);
});
test('non-contributor maintainer does not count as a peer', () => {
  assert.equal(evaluate([review('peer1', 1), review('owner', 2)]), false);
});
test('old commit approvals do not count', () => {
  assert.equal(evaluate([review('peer1', 1, 'APPROVED', 'old'), review('peer2', 2), review('owner', 3)]), false);
});
test('dismissal invalidates approval', () => {
  assert.equal(evaluate([review('peer1', 1), review('peer2', 2), review('owner', 3), review('peer1', 4, 'DISMISSED')]), false);
});
test('outstanding changes requested blocks even on an earlier commit', () => {
  assert.equal(evaluate([review('peer1', 1), review('peer2', 2), review('peer3', 4, 'CHANGES_REQUESTED', 'old')]), false);
});
test('comments do not erase an approval', () => {
  assert.equal(evaluate([review('peer1', 1), review('peer2', 2), review('owner', 3), review('peer1', 4, 'COMMENTED')]), true);
});
test('outsiders cannot satisfy peer membership', () => {
  assert.equal(evaluate([review('outsider', 1), review('peer2', 2), review('owner', 3)]), false);
});
test('membership matching is case insensitive', () => {
  assert.equal(evaluate([review('PEER1', 1), review('peer2', 2), review('OWNER', 3)]), true);
});
test('peer approvals can have the same timestamp', () => {
  assert.equal(evaluate([review('peer1', 1), { ...review('peer2', 2), submitted_at: review('peer1', 1).submitted_at }]), true);
});
test('missing approvals fails closed', () => {
  assert.equal(evaluate([]), false);
});

function decision(reviews) {
  return evaluateReviews({
    author: 'author', headSha: 'head', reviews,
    contributors: ['peer1', 'peer2', 'author'],
  });
}

test('initial review request has a formal message', () => {
  assert.equal(decision([]).reason,
    'Contributor approvals for the latest PR commit: 2 required, 0 received, 2 remaining.');
});
test('two current approvals produce the approved message', () => {
  assert.equal(decision([review('peer1', 1), review('peer2', 2)]).reason,
    'Approved. Contributor approvals with complete checklists: 2 required, 2 received, 0 remaining.');
});
test('previously approved commit requires reapproval after a push', () => {
  const result = decision([review('peer1', 1, 'APPROVED', 'old'), review('peer2', 2, 'APPROVED', 'old')]);
  assert.equal(result.approved, false);
  assert.equal(result.reason,
    'Reapproval required for the latest PR commit. Contributor approvals: 2 required, 0 received, 2 remaining.');
});
test('one reapproval does not clear the reapproval request', () => {
  assert.match(decision([
    review('peer1', 1, 'APPROVED', 'old'), review('peer2', 2, 'APPROVED', 'old'),
    review('peer1', 3),
  ]).reason, /^Reapproval required.*2 required, 1 received, 1 remaining\.$/);
});
test('two reapprovals restore approval', () => {
  const result = decision([
    review('peer1', 1, 'APPROVED', 'old'), review('peer2', 2, 'APPROVED', 'old'),
    review('peer1', 3), review('peer2', 4),
  ]);
  assert.equal(result.approved, true);
  assert.match(result.reason, /^Approved\./);
});
test('author and duplicate reviews do not imply prior peer approval', () => {
  assert.doesNotMatch(decision([
    review('author', 1, 'APPROVED', 'old'), review('peer1', 2, 'APPROVED', 'old'),
    review('peer1', 3, 'APPROVED', 'old'),
  ]).reason, /^Reapproval/);
});

test('one distinct approval reports one remaining', () => {
  assert.equal(decision([review('peer1', 1), review('peer1', 2)]).reason,
    'Contributor approvals for the latest PR commit: 2 required, 1 received, 1 remaining.');
});

test('policy progress messages fit the GitHub status description limit', () => {
  const histories = [[], [review('peer1', 1)],
    [review('peer1', 1), review('peer2', 2)],
    [review('peer1', 1, 'APPROVED', 'old'), review('peer2', 2, 'APPROVED', 'old'), review('peer1', 3)]];
  for (const history of histories) assert.ok(decision(history).reason.length <= 140);
});

test('approval without a checklist does not count', () => {
  const result = decision([{ ...review('peer1', 1), body: '' }, review('peer2', 2)]);
  assert.equal(result.approved, false);
  assert.equal(result.reason, 'Checklist not completed as part of review approval. 2 required, 1 received, 1 remaining. 1 incomplete.');
});

test('an unchecked item invalidates the approval', () => {
  assert.equal(decision([
    { ...review('peer1', 1), body: checklist.replace('[x]', '[ ]') }, review('peer2', 2),
  ]).approved, false);
});

test('a later incomplete approving review replaces a complete approval', () => {
  assert.equal(decision([review('peer1', 1), review('peer2', 2),
    { ...review('peer1', 3), body: '' }]).approved, false);
});

test('editing the latest approving review to complete its checklist permits approval', () => {
  assert.equal(decision([review('peer1', 1), review('peer2', 2)]).approved, true);
});