const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { classify, run } = require('../run.cjs');

const entry = (name, sha = 'old', type = 'blob') => ({ path: name, sha, type, mode: '100644' });
const base = [entry('GenAI/AI_PC/demo/project.yaml'), entry('GenAI/AI_PC/demo/main.py')];

test('source-only and non-project changes select no metadata', () => {
  const result = classify(base, [...base.slice(0, 1), entry('GenAI/AI_PC/demo/main.py', 'new'), entry('website/src/app.js', 'new')]);
  assert.deepEqual(result.files, []);
  assert.deepEqual(result.errors, []);
  assert.equal(result.projects[0].kind, 'modified-without-metadata');
  assert.equal(result.required, false);
  assert.deepEqual(result.nonProject, ['website/src/app.js']);
});

test('new standard project without metadata fails even without README', () => {
  const result = classify(base, [...base, entry('CV_VR/IoT-Robotics/new-demo/source/main.c', 'new')]);
  assert.equal(result.errors.length, 1);
  assert.equal(result.errors[0].file, 'CV_VR/IoT-Robotics/new-demo/project.yaml');
});

test('parent metadata cannot mask a new project missing its own metadata', () => {
  const result = classify([], [entry('GenAI/project.yaml'), entry('GenAI/AI_PC/new-demo/main.py')]);
  assert.ok(result.errors.some(error => error.file === 'GenAI/AI_PC/new-demo/project.yaml'));
});

test('nested metadata cannot replace mandatory metadata at a new project root', () => {
  const result = classify([], [entry('GenAI/AI_PC/new-demo/sub/project.yaml')]);
  assert.equal(result.errors[0].file, 'GenAI/AI_PC/new-demo/project.yaml');
});

test('API rejects symlink metadata without downloading its target', async context => {
  const file = 'GenAI/AI_PC/demo/project.yaml';
  const fixture = apiFixture(context, [], [{ ...entry(file), mode: '120000' }]);
  const result = await run(fixture);
  assert.equal(result.status, 'failed');
  assert.ok(result.errors.some(error => error.message.includes('regular file')));
  assert.ok(!fixture.downloads.some(download => download.ref === 'head'));
});

test('new metadata, modified metadata and case variants are selected', () => {
  const result = classify(base, [entry('GenAI/AI_PC/demo/project.yaml', 'changed'), entry('CV_VR/Android/new-demo/Project.yaml', 'new')]);
  assert.deepEqual(result.files, ['CV_VR/Android/new-demo/Project.yaml', 'GenAI/AI_PC/demo/project.yaml']);
  assert.deepEqual(result.errors, []);
});

test('existing metadata-less project is not treated as new', () => {
  const previous = [entry('Others/AI_PC/legacy/source.py')];
  assert.deepEqual(classify(previous, [...previous, entry('Others/AI_PC/legacy/README.md', 'new')]).errors, []);
});

test('nested directories belong to an existing metadata-defined project', () => {
  const result = classify(base, [...base, entry('GenAI/AI_PC/demo/new-library/README.md', 'new')]);
  assert.equal(result.projects[0].root, 'GenAI/AI_PC/demo');
  assert.deepEqual(result.errors, []);
});

test('deletions skip and metadata rename destination validates', () => {
  assert.deepEqual(classify(base, []).files, []);
  assert.deepEqual(classify(base, [entry('GenAI/AI_PC/demo/PROJECT.YAML')]).files, ['GenAI/AI_PC/demo/PROJECT.YAML']);
});

test('category/platform documentation and tooling are non-project changes', () => {
  const result = classify([], ['CV_VR/README.md', 'GenAI/AI_PC/README.md', 'Hardware/board/README.md', 'Tools/sdk/new/script.sh'].map(name => entry(name)));
  assert.equal(result.nonProject.length, 4);
  assert.deepEqual(result.errors, []);
});

test('mixed PR classifies four cases independently and evaluates only required projects', () => {
  const before = [...base, entry('Others/AI_PC/existing/project.yaml'), entry('Others/AI_PC/existing/main.py')];
  const after = [
    entry('GenAI/AI_PC/demo/project.yaml', 'updated'), entry('GenAI/AI_PC/demo/main.py'),
    entry('Others/AI_PC/existing/project.yaml'), entry('Others/AI_PC/existing/main.py', 'updated'),
    entry('CV_VR/Android/new-project/source.py', 'new'), entry('website/README.md', 'new'),
  ];
  const result = classify(before, after);
  assert.equal(result.required, true);
  assert.deepEqual(result.files, ['GenAI/AI_PC/demo/project.yaml']);
  assert.deepEqual(result.projects.map(project => [project.kind, project.required]), [
    ['modified-with-metadata', true], ['modified-without-metadata', false], ['new-project', true],
  ]);
  assert.deepEqual(result.nonProject, ['website/README.md']);
  assert.equal(result.errors[0].file, 'CV_VR/Android/new-project/project.yaml');
});

function apiFixture(context, baseEntries, headEntries, candidate = {}, truncated = false) {
  const reportRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'project-yaml-test-'));
  const previousTemp = process.env.RUNNER_TEMP;
  process.env.RUNNER_TEMP = reportRoot;
  context.after(() => {
    if (previousTemp === undefined) delete process.env.RUNNER_TEMP;
    else process.env.RUNNER_TEMP = previousTemp;
    fs.rmSync(reportRoot, { recursive: true, force: true });
  });
  const downloads = [];
  const failures = [];
  const summaries = [];
  const repository = path.resolve(__dirname, '../../..');
  const github = { rest: {
    git: { getTree: async ({ tree_sha }) => ({ data: { tree: tree_sha === 'base' ? baseEntries : headEntries, truncated } }) },
    repos: { getContent: async ({ path: file, ref }) => {
      downloads.push({ file, ref });
      const content = ref === 'trusted' ? fs.readFileSync(path.join(repository, file)) : candidate[file];
      assert.ok(content !== undefined, `Unexpected candidate download: ${file}`);
      return { data: { type: 'file', encoding: 'base64', content: Buffer.from(content).toString('base64') } };
    } },
  } };
  const core = {
    info() {}, warning() {}, error() {}, setFailed(message) { failures.push(message); },
    summary: { addRaw(text) { summaries.push(text); return this; }, async write() {} },
  };
  const event = { repo: { owner: 'owner', repo: 'repo' }, sha: 'head', runId: 'test', eventName: 'push', payload: { before: 'base' } };
  return { github, core, context: event, trustedSha: 'trusted', downloads, failures, summaries, reportRoot };
}

test('API source-only and non-project skips download zero files', async context => {
  const fixture = apiFixture(context, base, [...base, entry('website/README.md', 'new'), entry('GenAI/AI_PC/demo/code.py', 'new')]);
  const result = await run(fixture);
  assert.equal(result.status, 'skipped');
  assert.deepEqual(fixture.downloads, []);
  assert.deepEqual(fixture.failures, []);
});

test('API missing-new-project failure fetches only schema and guidelines', async context => {
  const fixture = apiFixture(context, base, [...base, entry('Others/AI_PC/new-project/main.py', 'new')]);
  const result = await run(fixture);
  assert.equal(result.status, 'failed');
  assert.ok(result.errors[0].message.includes('missing mandatory project.yaml'));
  assert.deepEqual(fixture.downloads.map(download => download.file).sort(), ['.github/PROJECT_YAML_GUIDELINES.md', '.github/project-yaml-schema.yaml']);
  assert.ok(fixture.summaries.join('').includes('# Project YAML Guidelines'));
  assert.equal(fixture.failures.length, 0);
});

test('API tree truncation fails closed rather than skipping', async context => {
  const fixture = apiFixture(context, [], [], {}, true);
  const result = await run(fixture);
  assert.equal(result.status, 'failed');
  assert.ok(result.infrastructureError.includes('truncated'));
  assert.deepEqual(fixture.downloads, []);
});

test('API metadata validation downloads no project sources or pictures', async context => {
  const file = 'GenAI/AI_PC/demo/project.yaml';
  const candidate = {
    [file]: 'long_name: Example\nshortname: example-project\ndescription: Example\ntechnology: [Connectivity]\nplatforms: [AI PC]\nhardware: []\nsoftware_tools: [Windows]\nai_models: [Brand New Model]\ntopics_tools: [Brand New Topic]\nperipherals_sensors: [Brand New Sensor]\npicture: image.png\n',
  };
  const fixture = apiFixture(context, [entry('Others/AI_PC/unrelated/project.yaml')], [entry(file, 'new'), entry('GenAI/AI_PC/demo/image.png'), entry('GenAI/AI_PC/demo/main.py'), entry('Others/AI_PC/unrelated/project.yaml')], candidate);
  const result = await run(fixture);
  assert.equal(result.status, 'passed', JSON.stringify(result));
  assert.deepEqual(fixture.failures, []);
  assert.deepEqual(fixture.downloads.filter(download => download.ref === 'head').map(download => download.file), [file]);
  assert.ok(fixture.downloads.filter(download => download.ref === 'trusted').every(download => !download.file.includes('GenAI/')));
});

test('legacy PR metadata fails with mandatory-field and closed-list diagnostics', async context => {
  const file = 'CV_VR/IoT-Robotics/depth_object_detection/project.yaml';
  const fixture = apiFixture(context, [], [entry(file, 'new')], {
    [file]: 'name: depth_object_detection\ndescription: A 2.5D Vision demo\ncategory: [CV_VR, IoT-Robotics]\nplatforms: [IQ9, Qualcomm AI Hub]\ntags: [MiDaS, YOLO]\n',
  });
  const result = await run(fixture);
  assert.equal(result.status, 'failed');
  for (const field of ['long_name', 'shortname', 'technology', 'hardware', 'software_tools', 'ai_models', 'topics_tools', 'peripherals_sensors', 'picture']) assert.ok(result.errors.some(error => error.field === `$/` + field), field);
  assert.ok(result.errors.some(error => error.field === '/platforms/0' && error.actual.includes('IQ9')));
  assert.ok(result.errors.some(error => error.field === '/platforms/1' && error.actual.includes('Qualcomm AI Hub')));
  assert.ok(result.report.includes('# Project YAML Guidelines'));
  assert.equal(fixture.failures.length, 0);
});
