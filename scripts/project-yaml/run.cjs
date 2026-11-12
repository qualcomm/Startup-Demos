const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const { execFileSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');

const categories = new Set(['CV_VR', 'GenAI', 'Others', '3rdParty', '5G+AI']);
const platforms = new Set(['AI_PC', 'Android', 'CloudAI-Playground', 'Connectivity', 'IoT-Robotics']);
const metadata = name => path.posix.basename(name).toLowerCase() === 'project.yaml';

function classify(baseEntries, headEntries, all = false) {
  const base = new Map(baseEntries.map(entry => [entry.path, entry]));
  const changes = headEntries.filter(entry => entry.type === 'blob' && (all || base.get(entry.path)?.sha !== entry.sha));
  const changedRoots = changes.filter(entry => metadata(entry.path)).map(entry => path.posix.dirname(entry.path)).sort((left, right) => right.length - left.length);
  const projects = new Map();
  const nonProject = [];
  for (const entry of changes) {
    const parts = entry.path.split('/');
    const standardRoot = parts.length >= 4 && categories.has(parts[0]) && platforms.has(parts[1]) ? parts.slice(0, 3).join('/') : undefined;
    const explicit = changedRoots.find(root => (!standardRoot || root === standardRoot || root.startsWith(`${standardRoot}/`)) && (root === '.' || entry.path.startsWith(`${root}/`)));
    const root = standardRoot ?? explicit;
    if (!root) {
      nonProject.push(entry.path);
      continue;
    }
    if (!projects.has(root)) {
      const existed = baseEntries.some(previous => previous.path === root || previous.path.startsWith(`${root}/`));
      const projectMetadata = headEntries.filter(candidate => metadata(candidate.path) && path.posix.dirname(candidate.path) === root);
      const metadataChanged = changes.some(candidate => metadata(candidate.path) && path.posix.dirname(candidate.path) === root);
      const kind = !existed ? 'new-project' : metadataChanged ? 'modified-with-metadata' : 'modified-without-metadata';
      projects.set(root, { root, kind, required: all || !existed || metadataChanged, metadata: projectMetadata.map(candidate => candidate.path), changed: [] });
    }
    projects.get(root).changed.push(entry.path);
  }
  const files = [...new Set([...projects.values()].filter(project => project.required).flatMap(project => project.metadata))].sort();
  const errors = [...projects.values()].filter(project => project.kind === 'new-project' && !project.metadata.length).map(project => ({
    file: `${project.root}/project.yaml`, line: 1, field: '$', actual: '(missing)',
    message: 'New project is missing mandatory project.yaml at its project root.',
  }));
  return { required: files.length > 0 || errors.length > 0, files, errors, projects: [...projects.values()], nonProject, changes: changes.map(entry => ({ path: entry.path, status: base.has(entry.path) ? 'modified' : 'added' })) };
}

async function run({ github, context, core, trustedSha }) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'project-yaml-api-'));
  const reportDirectory = path.join(process.env.RUNNER_TEMP || os.tmpdir(), `project-yaml-report-${context.runId}-${process.env.GITHUB_RUN_ATTEMPT || '1'}`);
  fs.mkdirSync(reportDirectory, { recursive: true });
  const download = async (file, ref, destination = file) => {
    const response = await github.rest.repos.getContent({ ...context.repo, path: file, ref });
    if (Array.isArray(response.data) || response.data.type !== 'file' || response.data.encoding !== 'base64') throw new Error(`Cannot safely download ${file}: expected a regular base64 file.`);
    const target = path.resolve(root, destination);
    const relative = path.relative(root, target);
    if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error(`Unsafe download path: ${destination}`);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, Buffer.from(response.data.content, 'base64'));
    core.info(`Fetched ${file} at ${ref}`);
  };
  let result;
  try {
    const headSha = context.payload.pull_request?.head.sha ?? context.sha;
    let baseSha = context.payload.pull_request?.base.sha ?? context.payload.merge_group?.base_sha ?? context.payload.before;
    const all = context.eventName === 'workflow_dispatch';
    if (context.payload.pull_request) {
      const comparison = await github.rest.repos.compareCommits({ ...context.repo, base: baseSha, head: headSha });
      baseSha = comparison.data.merge_base_commit.sha;
    }
    const tree = async sha => {
      if (!sha || /^0+$/.test(sha)) return [];
      const response = await github.rest.git.getTree({ ...context.repo, tree_sha: sha, recursive: '1' });
      if (response.data.truncated) throw new Error('Repository tree is truncated; cannot safely classify projects.');
      return response.data.tree;
    };
    const [baseEntries, headEntries] = await Promise.all([all ? [] : tree(baseSha), tree(headSha)]);
    const selection = classify(baseEntries, headEntries, all);
    core.info(JSON.stringify(selection, null, 2));
    result = { ...selection, status: selection.errors.length ? 'failed' : selection.files.length ? 'passed' : 'skipped' };
    if (selection.files.length || selection.errors.length) {
      await download('.github/PROJECT_YAML_GUIDELINES.md', trustedSha);
      await download('.github/project-yaml-schema.yaml', trustedSha);
    }
    if (selection.files.length) {
      for (const file of ['website/package.json', 'website/package-lock.json', 'website/scripts/validate-project-yaml.js']) await download(file, trustedSha);
      execFileSync('npm', ['ci', '--prefix', path.join(root, 'website'), '--ignore-scripts', '--no-audit', '--no-fund'], { stdio: 'inherit' });
      const validator = await import(pathToFileURL(path.join(root, 'website/scripts/validate-project-yaml.js')).href);
      const regularFiles = selection.files.filter(file => {
        const entry = headEntries.find(candidate => candidate.path === file);
        if (entry?.type === 'blob' && ['100644', '100755'].includes(entry.mode)) return true;
        result.errors.push({ file, line: 1, field: '$', actual: entry?.mode, message: 'Project metadata must be a regular file, not a symlink.' });
        return false;
      });
      for (const file of regularFiles) await download(file, headSha);
      const checked = validator.validateProjects(root, regularFiles, undefined, { tree: headEntries, checkIdentifiers: false });
      result.errors.push(...checked.errors);
      result.status = result.errors.length ? 'failed' : 'passed';
    }
    result.report = result.errors.length
      ? fs.readFileSync(path.join(root, '.github/PROJECT_YAML_GUIDELINES.md'), 'utf8')
      : result.status === 'skipped' ? 'Project YAML: SKIP. No metadata evaluation required.' : 'Project YAML: PASS.';
    await core.summary.addRaw(result.report).write();
    for (const error of result.errors) core.warning(`${error.field}: ${error.message} Actual: ${error.actual}`, { file: error.file, startLine: error.line });
    if (result.errors.length) core.info(`${result.errors.length} Project YAML issue(s) reported for contributor attention; validation execution completed successfully.`);
  } catch (error) {
    result = { ...result, status: 'failed', infrastructureError: error.message };
    await core.summary.addRaw(`# Project YAML Validation\n\n**Failed before completion:** ${String(error.message).replaceAll('<', '&lt;')}\n`).write();
    core.setFailed(error.message);
  } finally {
    fs.writeFileSync(path.join(reportDirectory, 'project-yaml-validation.json'), `${JSON.stringify(result, null, 2)}\n`);
    fs.writeFileSync(path.join(reportDirectory, 'project-yaml-validation.md'), result.report || result.infrastructureError || 'Validation did not complete.');
    for (const file of ['.github/PROJECT_YAML_GUIDELINES.md', '.github/project-yaml-schema.yaml']) {
      if (fs.existsSync(path.join(root, file))) fs.copyFileSync(path.join(root, file), path.join(reportDirectory, path.basename(file)));
    }
    fs.rmSync(root, { recursive: true, force: true });
  }
  return result;
}

module.exports = { classify, run };
