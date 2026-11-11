import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { publishPicture } from '../scripts/project-picture.js';

test('publish pictures locally and reject paths outside project', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'catalog-picture-'));
  try {
    const project = path.join(temporary, 'project');
    const publicDirectory = path.join(temporary, 'public');
    fs.mkdirSync(project);
    fs.writeFileSync(path.join(project, 'demo image.png'), 'image fixture');
    const url = publishPicture(project, 'demo image.png', 'category/application', publicDirectory);
    assert.match(url, /^project-pictures\/[\w-]+\.png$/);
    assert.equal(fs.readFileSync(path.join(publicDirectory, url), 'utf8'), 'image fixture');
    assert.equal(publishPicture(project, null, 'category/application', publicDirectory), null);
    fs.writeFileSync(path.join(temporary, 'outside.png'), 'outside');
    assert.throws(() => publishPicture(project, '../outside.png', 'category/application', publicDirectory), /inside/);
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
});