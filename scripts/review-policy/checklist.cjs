//===--checklist.cjs--------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

const sections = {
  'Commits & PR Hygiene': [
    'Clear PR title and brief description',
    'Commit messages follow standards',
    'All commits are signed',
    'Project information file meets the standards',
    'CI / QC Preflight checks are green',
  ],
  'Code Quality & Authenticity': [
    'No copied code without proper source and license attribution',
    'Author has provided sources for any suspicious code',
    'No ML models, datasets, or binaries are checked in',
    'Code belongs in source files, not in the README',
  ],
  'Documentation Discipline': [
    'README is simple, clean, and minimal',
    'No long code blocks in the README',
    'Reusable documentation is in the common README or docs',
    'Git clone and setup instructions are clear',
    'Repeatable setup uses scripts',
  ],
  'Compliance & Safety': [
    'Dependencies and licenses are validated',
    'No secrets or sensitive data are included',
    'No copyrighted media is included without appropriate permission or licensing',
    'All reviewer comments are resolved before merge',
  ],
};

function validateChecklist(body) {
  const normalize = text => text.trim().replace(/\s+/g, ' ').toLowerCase();
  const expected = Object.values(sections).flat();
  const entries = new Map();
  let fence = null;
  const visible = String(body || '').replace(/<!--[\s\S]*?(?:-->|$)/g, '');
  for (const line of visible.split(/\r?\n/)) {
    const marker = line.match(/^ {0,3}(`{3,}|~{3,})/);
    if (marker) {
      if (!fence) fence = marker[1];
      else if (marker[1][0] === fence[0] && marker[1].length >= fence.length &&
        /^ {0,3}(?:`+|~+)\s*$/.test(line)) fence = null;
      continue;
    }
    if (fence) continue;
    const task = line.match(/^ {0,3}[-*+] \[([ xX])\]\s+(.+?)\s*$/);
    if (!task) continue;
    const key = normalize(task[2]);
    const values = entries.get(key) || [];
    values.push(task[1].toLowerCase() === 'x');
    entries.set(key, values);
  }
  const missing = expected.filter(item => {
    const values = entries.get(normalize(item));
    return !values || values.length !== 1 || !values[0];
  });
  return { complete: missing.length === 0, missing };
}

module.exports = { sections, validateChecklist };