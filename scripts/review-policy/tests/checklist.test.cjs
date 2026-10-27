//===--checklist.test.cjs---------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { sections, validateChecklist } = require('../checklist.cjs');
const items = Object.values(sections).flat();
const checked = items.map(item => `- [x] ${item}`).join('\n');

test('all 18 items must be checked', () => {
  assert.equal(items.length, 18);
  assert.deepEqual(validateChecklist(checked), { complete: true, missing: [] });
});
test('missing and non-string review bodies fail closed', () => {
  for (const body of [undefined, null, '', 42]) assert.equal(validateChecklist(body).complete, false);
});
test('each individual missing or unchecked item blocks', () => {
  for (const item of items) {
    for (const replacement of ['', `- [ ] ${item}`]) {
      assert.deepEqual(validateChecklist(checked.replace(`- [x] ${item}`, replacement)).missing, [item]);
    }
  }
});
test('supports uppercase ticks, CRLF, and surrounding text', () => {
  assert.equal(validateChecklist(`Reviewed carefully.\r\n${checked.replace(/\[x\]/g, '[X]').replace(/\n/g, '\r\n')}\r\nReady.`).complete, true);
});
test('case and extra whitespace do not change item identity', () => {
  const body = items.map(item => `- [X] ${item.toUpperCase().replace(/ /g, '  ')}`).join('\n');
  assert.equal(validateChecklist(body).complete, true);
});
test('quoted, indented, commented, and fenced checklists do not count', () => {
  const hidden = [
    checked.split('\n').map(line => `> ${line}`).join('\n'),
    checked.split('\n').map(line => `    ${line}`).join('\n'),
    `<!--\n${checked}\n-->`, `<!--\n${checked}`,
    `\`\`\`markdown\n${checked}\n\`\`\``, `~~~\n${checked}\n~~~`,
  ];
  for (const body of hidden) assert.equal(validateChecklist(body).complete, false);
});
test('duplicate items do not count as complete', () => {
  assert.equal(validateChecklist(`${checked}\n- [x] ${items[0]}`).complete, false);
  assert.equal(validateChecklist(`${checked}\n- [ ] ${items[0]}`).complete, false);
});
test('unrelated checked tasks cannot replace required items', () => {
  assert.equal(validateChecklist(items.map((item, index) => `- [x] Task ${index}`).join('\n')).complete, false);
});
test('distributed items and review explanations are supported', () => {
  const body = Object.entries(sections).map(([heading, tasks]) =>
    `## ${heading}\n\n${tasks.map(item => `- [x] ${item}`).join('\n')}\n\nReviewed this section.`).join('\n');
  assert.equal(validateChecklist(body).complete, true);
});
test('published template exactly matches canonical items', () => {
  const template = readFileSync(`${__dirname}/../REVIEW_CHECKLIST.md`, 'utf8');
  assert.equal(validateChecklist(template).missing.length, 18);
  assert.equal(validateChecklist(template.replace(/\[ \]/g, '[x]')).complete, true);
  assert.equal(template.match(/^- \[ \]/gm).length, 18);
});