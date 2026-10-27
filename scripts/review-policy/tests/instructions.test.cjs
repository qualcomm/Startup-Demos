//===--instructions.test.cjs------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { marker, renderInstructions, postInstructionsOnce } = require('../instructions.cjs');
const { validateChecklist } = require('../checklist.cjs');

test('reviewer list excludes author, deduplicates, and sorts members', () => {
  const body = renderInstructions('AUTHOR', ['peer2', 'author', 'Peer1', 'peer1']);
  assert.match(body, /@peer1, @peer2/);
  assert.doesNotMatch(body, /@author/);
});

test('all 18 tasks are fenced and cannot satisfy an approval checklist', () => {
  const body = renderInstructions('author', ['peer1']);
  const code = body.match(/```markdown\n([\s\S]*?)\n```/)[1];
  assert.equal(code.match(/^- \[ \]/gm).length, 18);
  assert.equal(validateChecklist(code.replace(/\[ \]/g, '[x]')).complete, true);
  assert.equal(validateChecklist(body.replace(/\[ \]/g, '[x]')).complete, false);
  assert.doesNotMatch(body.replace(/```markdown\n[\s\S]*?\n```/, ''), /^- \[[ x]\]/m);
});

test('empty eligible list has an actionable explanation', () => {
  assert.match(renderInstructions('author', ['author']), /No eligible contributors were found/);
});

test('user-authored marker cannot suppress the bot instruction comment', async () => {
  const posted = [];
  const github = {
    rest: { issues: {
      listComments: async () => [{ user: { login: 'author' }, body: marker }],
      createComment: async parameters => posted.push(parameters),
    } },
    paginate: async (method, parameters) => method(parameters),
  };
  await postInstructionsOnce({ github, repository: { owner: 'org', repo: 'repo' },
    request: { number: 1, user: { login: 'author' } }, contributors: ['peer1'] });
  assert.equal(posted.length, 1);
});