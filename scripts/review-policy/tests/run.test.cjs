//===--run.test.cjs---------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

const { test } = require('node:test');
const assert = require('node:assert/strict');
const run = require('../run.cjs');
const { sections } = require('../checklist.cjs');
const checklist = Object.values(sections).flat().map(item => `- [x] ${item}`).join('\n');

function fixture(options = {}) {
  const statuses = [];
  const errors = [];
  const comments = [];
  const request = { number: 1, user: { login: 'author' }, head: { sha: 'head' }, base: { ref: 'main' } };
  const reviews = ['peer1', 'peer2'].map((login, index) => ({
    id: index + 1, user: { login }, state: 'APPROVED', commit_id: 'head', body: checklist,
    submitted_at: new Date(Date.UTC(2026, 9, 27, 0, index)).toISOString(),
  }));
  const github = {
    rest: {
      issues: {
        listComments: async () => comments,
        createComment: async ({ body }) => { comments.push({ body, user: { login: 'github-actions[bot]' } }); },
      },
      pulls: {
        list: async () => options.empty ? [] : [request],
        listReviews: async () => options.reviews || reviews,
        get: async () => ({ data: { ...request, state: 'open', draft: options.draft, head: { sha: options.changed ? 'new-head' : 'head' } } }),
      },
      repos: {
        createCommitStatus: async status => { statuses.push(status); },
        compareCommitsWithBasehead: async () => ({ data: { status: options.unrelated ? 'diverged' : 'ahead' } }),
      },
    },
    paginate: async (method, parameters) => method(parameters),
  };
  const membership = {
    rest: { teams: { listMembersInOrg: async ({ team_slug: slug }) => {
      if (options.membershipError) throw new Error('Team membership access denied');
      assert.equal(slug, 'contributors', 'Only contributor membership should be queried');
      return ['peer1', 'peer2'].map(login => ({ login }));
    } } },
    paginate: async (method, parameters) => method(parameters),
  };
  const context = {
    repo: { owner: 'example', repo: 'source' }, serverUrl: 'https://github.com', runId: 1,
    payload: options.group ? { merge_group: { head_sha: 'group-head', base_ref: 'refs/heads/main' } } : { pull_request: request },
  };
  process.env.SOURCE_BRANCH = 'main';
  process.env.CONTRIBUTORS_TEAM = 'contributors';
  return {
    statuses, errors, comments,
    execute: () => run({ github, membership, context, core: { info() {}, error() {}, setFailed: message => errors.push(message) } }),
  };
}

test('publishes pending then success on the current PR head', async () => {
  const setup = fixture();
  await setup.execute();
  assert.deepEqual(setup.statuses.map(status => status.state), ['pending', 'success']);
  assert.equal(setup.statuses.at(-1).context, 'Peer-Review Check');
});
test('missing reviews publishes failure rather than success or skipped', async () => {
  const setup = fixture({ reviews: [] });
  await setup.execute();
  assert.equal(setup.statuses.at(-1).state, 'failure');
});
test('approval with an incomplete checklist publishes the missing-checklist result', async () => {
  const setup = fixture({ reviews: ['peer1', 'peer2'].map((login, index) => ({
    id: index + 1, user: { login }, state: 'APPROVED', commit_id: 'head',
    submitted_at: new Date(Date.UTC(2026, 9, 27, 0, index)).toISOString(),
    body: index === 0 ? checklist : checklist.replace('[x]', '[ ]'),
  })) });
  await setup.execute();
  assert.equal(setup.statuses.at(-1).state, 'failure');
  assert.equal(setup.statuses.at(-1).description,
    'Checklist not completed as part of review approval. 2 required, 1 received, 1 remaining. 1 incomplete.');
});
test('team API failure clears pending with an error and fails the job', async () => {
  const setup = fixture({ membershipError: true });
  await setup.execute();
  assert.equal(setup.statuses.at(-1).state, 'error');
  assert.equal(setup.errors.length, 1);
});
test('merge group gets a separate successful aggregate status', async () => {
  const setup = fixture({ group: true });
  await setup.execute();
  assert.equal(setup.statuses.at(-1).sha, 'group-head');
  assert.equal(setup.statuses.at(-1).state, 'success');
});
test('unrelated PRs cannot approve a merge group', async () => {
  const setup = fixture({ group: true, unrelated: true });
  await setup.execute();
  assert.equal(setup.statuses.at(-1).state, 'error');
  assert.equal(setup.errors.length, 1);
});
test('a head change during evaluation fails closed', async () => {
  const setup = fixture({ changed: true });
  await setup.execute();
  assert.equal(setup.statuses.at(-1).state, 'error');
});
test('draft PRs cannot pass', async () => {
  const setup = fixture({ draft: true });
  await setup.execute();
  assert.equal(setup.statuses.at(-1).state, 'failure');
});

test('instructions are posted only once across repeated evaluations', async () => {
  const setup = fixture();
  await setup.execute();
  await setup.execute();
  assert.equal(setup.comments.length, 1);
  assert.match(setup.comments[0].body, /@peer1, @peer2/);
});

test('instruction-comment checkboxes never count as approval reviews', async () => {
  const setup = fixture({ reviews: [] });
  await setup.execute();
  setup.comments[0].body = setup.comments[0].body.replace(/\[ \]/g, '[x]');
  await setup.execute();
  assert.equal(setup.comments.length, 1);
  assert.equal(setup.statuses.at(-1).state, 'failure');
});