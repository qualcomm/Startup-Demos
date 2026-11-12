import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';
import { selectMetadataFiles, changedMetadataFiles, validateProjects, renderReport } from '../scripts/validate-project-yaml.js';

const schemaFile = fileURLToPath(new URL('../../.github/project-yaml-schema.yaml', import.meta.url));
const valid = {
  long_name: 'Project Example', shortname: 'project-example', description: 'A project.',
  technology: ['Generative AI'], platforms: ['AI PC', 'Snapdragon X Elite'],
  hardware: ['Snapdragon X Elite'], software_tools: ['Windows'], ai_models: [],
  topics_tools: ['Python'], peripherals_sensors: [], picture: 'image.png',
};

function fixture(context) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'project-yaml-'));
  context.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const write = (file, content) => {
    fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true });
    fs.writeFileSync(path.join(root, file), content);
  };
  write('demo/image.png', Buffer.from([137, 80, 78, 71]));
  write('demo/project.yaml', yaml.dump(valid));
  const check = (data = valid, file = 'demo/project.yaml') => {
    write(file, typeof data === 'string' ? data : yaml.dump(data));
    return validateProjects(root, [file], schemaFile);
  };
  return { root, write, check };
}

test('selection is case insensitive and ignores source-only paths', () => {
  assert.deepEqual(selectMetadataFiles(['demo/main.c', 'demo/Project.yaml', 'demo/Project.yaml', 'other/PROJECT.YAML', 'project.yaml.bak']), ['demo/Project.yaml', 'other/PROJECT.YAML']);
});

test('valid metadata passes and empty selection skips', context => {
  const { root, check } = fixture(context);
  assert.equal(check().status, 'passed');
  assert.equal(validateProjects(root, [], schemaFile).status, 'skipped');
});

test('reports all missing fields, types, unknown keys and unacceptable values', context => {
  const { check } = fixture(context);
  const result = check({ ...valid, long_name: undefined, description: 'x'.repeat(201), hardware: ['unsupported'], ai_models: 'YOLO', status: 'new' });
  assert.equal(result.status, 'failed');
  for (const field of ['$/long_name', '/description', '/hardware/0', '/ai_models', '$/status']) assert.ok(result.errors.some(error => error.field === field), field);
  assert.ok(result.errors.find(error => error.field === '/hardware/0').message.includes('QCS6490'));
  assert.ok(renderReport(result).includes('Guidelines'));
});

test('YAML syntax, duplicate keys and multiple documents fail', context => {
  const { check } = fixture(context);
  for (const content of ['long_name: [broken', 'shortname: one\nshortname: two', '---\nlong_name: one\n---\nlong_name: two']) assert.equal(check(content).status, 'failed');
});

test('cyclic YAML values produce bounded validation diagnostics', context => {
  const { check } = fixture(context);
  const result = check('technology: &items [*items]\n');
  assert.equal(result.status, 'failed');
  assert.ok(result.errors.every(error => error.actual.length <= 1000));
});

test('closed vocabulary, identifier length and optional fields are validated', context => {
  const { check } = fixture(context);
  for (const replacement of [
    { technology: ['Edge AI'] }, { platforms: ['Unknown platform'] },
    { hardware: null }, { software_tools: ['Unknown tool'] }, { shortname: 'Bad' },
    { shortname: 'x'.repeat(21) }, { difficulty_level: 'expert' }, { homepage: 'javascript:alert(1)' },
  ]) assert.equal(check({ ...valid, ...replacement }).status, 'failed', JSON.stringify(replacement));
  assert.equal(check({ ...valid, difficulty_level: 'advanced', homepage: 'https://example.com', demo_video: 'https://example.com/video' }).status, 'passed');
});

test('only shortname and description have length limits; open vocabularies accept new strings', context => {
  const { check } = fixture(context);
  assert.equal(check({ ...valid, long_name: 'x'.repeat(500), shortname: 'AbC_123456', description: '', technology: ['Connectivity'], ai_models: ['New Model'], topics_tools: ['New Topic'], peripherals_sensors: ['New Sensor'], estimated_setup_time: 'x'.repeat(500) }).status, 'passed');
  for (const length of [10, 20]) assert.equal(check({ ...valid, shortname: 'x'.repeat(length), description: 'x'.repeat(200) }).status, 'passed');
  assert.equal(check({ ...valid, shortname: 'x'.repeat(9) }).status, 'failed');
  assert.equal(check({ ...valid, description: 'x'.repeat(201) }).status, 'failed');
});

test('API tree validates references without downloading picture or related-project contents', context => {
  const { root, write } = fixture(context);
  write('demo/project.yaml', yaml.dump({ ...valid, picture: 'remote.png', related_projects: ['other'] }));
  const tree = [
    { path: 'demo/remote.png', type: 'blob', mode: '100644' },
    { path: 'other', type: 'tree' },
    { path: 'other/project.yaml', type: 'blob', mode: '100644' },
  ];
  assert.equal(validateProjects(root, ['demo/project.yaml'], schemaFile, { tree }).status, 'passed');
  assert.equal(validateProjects(root, ['demo/project.yaml'], schemaFile, { tree: [] }).errors.length, 2);
  tree[0].mode = '120000';
  assert.ok(validateProjects(root, ['demo/project.yaml'], schemaFile, { tree }).errors.some(error => error.field === '/picture'));
});

test('pictures must exist and stay inside the project, including symlink targets', context => {
  const { root, write, check } = fixture(context);
  write('outside.png', 'image');
  fs.symlinkSync(path.join(root, 'outside.png'), path.join(root, 'demo/link.png'));
  for (const picture of ['', '   ', 'missing.png', '../outside.png', 'link.png', path.join(root, 'outside.png'), null]) assert.equal(check({ ...valid, picture }).status, 'failed');
  write('demo/source.txt', 'source');
  assert.equal(check({ ...valid, picture: 'source.txt' }).status, 'failed');
});

test('duplicate identifiers are checked against unchanged projects without validating their other fields', context => {
  const { write, check } = fixture(context);
  write('other/project.yaml', yaml.dump({ shortname: valid.shortname }));
  const result = check();
  assert.equal(result.errors.length, 1);
  assert.ok(result.errors[0].message.includes('other/project.yaml'));
});

test('related projects must be existing metadata directories inside the repository', context => {
  const { write, check } = fixture(context);
  write('other/Project.yaml', yaml.dump({ shortname: 'other-project' }));
  assert.equal(check({ ...valid, related_projects: ['other'] }).status, 'passed');
  for (const related of ['missing', '../outside', 'demo/image.png']) assert.equal(check({ ...valid, related_projects: [related] }).status, 'failed');
});

test('git selection skips source-only changes and deletions; selects additions, modifications and renames', context => {
  const { root, write } = fixture(context);
  const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim();
  git('init', '-q');
  git('add', '.');
  git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Initial');
  const base = git('rev-parse', 'HEAD');
  write('demo/main.c', 'source');
  git('add', '.');
  git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Code only');
  assert.deepEqual(changedMetadataFiles(root, base, 'HEAD'), []);
  write('demo/project.yaml', yaml.dump({ ...valid, description: 'Updated' }));
  write('new/Project.yaml', yaml.dump({ ...valid, shortname: 'new-project' }));
  git('add', '.');
  git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Metadata');
  assert.deepEqual(changedMetadataFiles(root, base, 'HEAD'), ['demo/project.yaml', 'new/Project.yaml']);
  const beforeRename = git('rev-parse', 'HEAD');
  git('mv', 'new/Project.yaml', 'new/PROJECT.YAML');
  git('rm', 'demo/project.yaml');
  git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Rename and delete');
  assert.deepEqual(changedMetadataFiles(root, beforeRename, 'HEAD'), ['new/PROJECT.YAML']);
});

test('reports cannot inject Markdown tables or HTML', () => {
  const report = renderReport({ status: 'failed', files: [], errors: [{ file: 'bad|name', line: 1, field: '$', actual: '<script>\n|', message: '`bad`' }] });
  assert.ok(!report.includes('<script>'));
  assert.ok(report.includes('&#124;'));
});

test('report guideline links target the checked commit', () => {
  const report = renderReport({ status: 'skipped', files: [], errors: [] }, 'https://github.com/owner/repo/blob/commit-sha');
  assert.ok(report.includes('https://github.com/owner/repo/blob/commit-sha/.github/PROJECT_YAML_GUIDELINES.md'));
  assert.ok(report.includes('https://github.com/owner/repo/blob/commit-sha/.github/project-yaml-schema.yaml'));
});

test('CLI publishes reports, guidelines, annotations, and a failing exit code', context => {
  const { root, write } = fixture(context);
  write('.github/PROJECT_YAML_GUIDELINES.md', '# Project YAML Guidelines\n');
  write('demo/project.yaml', yaml.dump({ ...valid, hardware: ['unsupported'] }));
  const script = fileURLToPath(new URL('../scripts/validate-project-yaml.js', import.meta.url));
  const reportPrefix = path.join(root, 'report');
  const summary = path.join(root, 'summary.md');
  let failure;
  try {
    execFileSync(process.execPath, [script, '--root', root, '--schema', schemaFile, '--all', '--report', reportPrefix], {
      encoding: 'utf8',
      env: { ...process.env, GITHUB_ACTIONS: 'true', GITHUB_REPOSITORY: '', GITHUB_STEP_SUMMARY: summary },
      stdio: 'pipe',
    });
  } catch (error) {
    failure = error;
  }
  assert.equal(failure?.status, 1);
  assert.ok(failure.stdout.includes('::error file=demo/project.yaml'));
  assert.ok(failure.stdout.includes('/hardware/0'));
  assert.equal(JSON.parse(fs.readFileSync(`${reportPrefix}.json`, 'utf8')).status, 'failed');
  assert.ok(fs.readFileSync(`${reportPrefix}.md`, 'utf8').includes('unsupported'));
  assert.ok(fs.readFileSync(summary, 'utf8').includes('# Project YAML Guidelines'));
});
