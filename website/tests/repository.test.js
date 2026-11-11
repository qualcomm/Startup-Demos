import test from 'node:test';
import assert from 'node:assert/strict';
import { repositoryInfo } from '../scripts/repository.js';

test('publishing context wins over a different origin, including enterprise hosts', () => {
  const info = repositoryInfo({ GITHUB_SERVER_URL: 'https://git.example.com', GITHUB_REPOSITORY: 'team/catalog', REPOSITORY_DEFAULT_BRANCH: 'release' }, '.', () => '');
  assert.equal(info.url, 'https://git.example.com/team/catalog');
  assert.equal(info.documentBase, 'https://git.example.com/team/catalog/blob/release/');
});

test('local builds use origin and its default branch without leaking credentials', () => {
  const info = repositoryInfo({}, '.', args => args[0] === 'config' ? 'https://user:secret@github.com/owner/fork.git' : 'origin/master');
  assert.equal(info.sourceBase, 'https://github.com/owner/fork/tree/master/');
  assert.equal(repositoryInfo({}, '.', args => args[0] === 'config' ? 'git@github.com:another/project.git' : '').url, 'https://github.com/another/project');
});

test('missing repository fails explicitly instead of linking to a fixed repository', () => {
  assert.throws(() => repositoryInfo({}, '.', () => ''), /Cannot determine/);
});