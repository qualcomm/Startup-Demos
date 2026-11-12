import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { inspect, parseArgs } from 'node:util';
import Ajv from 'ajv';
import fg from 'fast-glob';
import yaml from 'js-yaml';

const defaultRoot = fileURLToPath(new URL('../../', import.meta.url));
const imageExtensions = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.avif']);

export function selectMetadataFiles(names) {
  return [...new Set(names.filter(name => path.posix.basename(name).toLowerCase() === 'project.yaml'))].sort();
}

export function changedMetadataFiles(root, base, head) {
  const output = execFileSync('git', ['diff', '--name-only', '-z', '--no-renames', '--diff-filter=ACMT', base, head, '--'], { cwd: root, encoding: 'utf8' });
  return selectMetadataFiles(output.split('\0').filter(Boolean));
}

export function allMetadataFiles(root) {
  return selectMetadataFiles(fg.sync('**/project.yaml', {
    cwd: root,
    caseSensitiveMatch: false,
    followSymbolicLinks: false,
    ignore: ['**/node_modules/**', '**/.git/**'],
  }));
}

function inside(directory, candidate) {
  const relative = path.relative(directory, candidate);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

function display(value) {
  if (value === undefined) return '(missing)';
  try {
    return JSON.stringify(value, (key, item) => {
      if (item && typeof item === 'object') return inspect(item, { depth: 2, maxArrayLength: 10, maxStringLength: 200 });
      return item;
    }).slice(0, 1000);
  } catch {
    return '(value cannot be displayed)';
  }
}

function valueAt(data, pointer) {
  return pointer.split('/').slice(1).reduce((value, key) => value?.[key.replace(/~1/g, '/').replace(/~0/g, '~')], data);
}

export function validateProjects(root, files, schemaFile = path.join(root, '.github/project-yaml-schema.yaml'), options = {}) {
  const schema = yaml.load(fs.readFileSync(schemaFile, 'utf8'));
  const validate = new Ajv({ allErrors: true, strict: false }).compile(schema);
  const tree = options.tree && new Map(options.tree.map(entry => [entry.path, entry]));
  const errors = [];
  const identifiers = new Map();
  for (const file of options.checkIdentifiers === false ? [] : allMetadataFiles(root)) {
    try {
      const data = yaml.load(fs.readFileSync(path.join(root, file), 'utf8'));
      if (typeof data?.shortname === 'string') {
        const matches = identifiers.get(data.shortname) ?? [];
        matches.push(file);
        identifiers.set(data.shortname, matches);
      }
    } catch {}
  }
  for (const file of files) {
    const addError = (field, message, actual, line = 1) => errors.push({ file, line, field, actual: display(actual), message });
    const absoluteFile = path.resolve(root, file);
    if (!inside(root, absoluteFile)) {
      addError('$', 'Metadata path must stay inside the repository.', file);
      continue;
    }
    let data;
    try {
      if (!inside(fs.realpathSync(root), fs.realpathSync(absoluteFile))) throw new Error('Metadata must stay inside the repository.');
      data = yaml.load(fs.readFileSync(absoluteFile, 'utf8'));
    } catch (error) {
      addError('$', `Cannot read or parse YAML: ${error.reason ?? error.message}`, undefined, (error.mark?.line ?? 0) + 1);
      continue;
    }
    if (!validate(data)) {
      for (const error of validate.errors) {
        const field = error.instancePath || '$';
        const property = error.params.missingProperty ?? error.params.additionalProperty;
        const actual = property ? data?.[property] : valueAt(data, error.instancePath);
        const expected = error.keyword === 'enum' ? ` Allowed values: ${JSON.stringify(error.params.allowedValues)}.` : ` Constraint: ${JSON.stringify(error.params)}.`;
        addError(property ? `${field}/${property}` : field, `${error.message}.${expected}`, actual);
      }
    }
    if (typeof data?.shortname === 'string') {
      const duplicates = (identifiers.get(data.shortname) ?? []).filter(other => other !== file);
      if (duplicates.length) addError('/shortname', `Identifier must be unique; also used by ${duplicates.join(', ')}.`, data.shortname);
    }
    if (typeof data?.picture === 'string' && !data.picture.trim()) {
      addError('/picture', 'Picture must reference an existing project-local image.', data.picture);
    }
    if (typeof data?.picture === 'string' && data.picture.trim()) {
      try {
        if (tree) {
          const directory = path.posix.dirname(file);
          const picture = path.posix.normalize(path.posix.join(directory, data.picture));
          if (path.posix.isAbsolute(data.picture) || (directory !== '.' && !picture.startsWith(`${directory}/`)) || picture === '..' || picture.startsWith('../')) throw new Error('Picture must be a relative path inside this project.');
          const entry = tree.get(picture);
          if (!entry || entry.type !== 'blob' || entry.mode === '120000') throw new Error('Picture must be an existing regular file; API validation does not follow symlinks.');
          if (!imageExtensions.has(path.posix.extname(picture).toLowerCase())) throw new Error('Picture must be a PNG, JPEG, GIF, WebP, SVG, or AVIF image.');
        } else {
        const projectDirectory = fs.realpathSync(path.dirname(absoluteFile));
        const picture = path.resolve(projectDirectory, data.picture);
        if (path.isAbsolute(data.picture) || !inside(projectDirectory, picture) || !inside(projectDirectory, fs.realpathSync(picture))) {
          throw new Error('Picture must be a relative path inside this project (including symlink targets).');
        }
        if (!imageExtensions.has(path.extname(picture).toLowerCase())) throw new Error('Picture must be a PNG, JPEG, GIF, WebP, SVG, or AVIF image.');
        if (!fs.statSync(picture).isFile()) throw new Error('Picture must reference a file.');
        }
      } catch (error) {
        addError('/picture', `Invalid picture: ${error.message}`, data.picture);
      }
    }
    if (Array.isArray(data?.related_projects)) {
      for (const [index, related] of data.related_projects.entries()) {
        if (typeof related !== 'string') continue;
        try {
          if (tree) {
            const target = path.posix.normalize(related);
            if (path.posix.isAbsolute(related) || target === '..' || target.startsWith('../') || tree.get(target)?.type !== 'tree') throw new Error('Related project must be an existing repository-relative directory.');
            if (![...tree.keys()].some(name => path.posix.dirname(name) === target && path.posix.basename(name).toLowerCase() === 'project.yaml')) throw new Error('Related directory must contain project.yaml.');
          } else {
          const target = path.resolve(root, related);
          if (path.isAbsolute(related) || !inside(root, target) || !inside(fs.realpathSync(root), fs.realpathSync(target)) || !fs.statSync(target).isDirectory()) {
            throw new Error('Related project must be an existing repository-relative directory.');
          }
          if (!fs.readdirSync(target).some(name => name.toLowerCase() === 'project.yaml')) throw new Error('Related directory must contain project.yaml.');
          }
        } catch (error) {
          addError(`/related_projects/${index}`, error.message, related);
        }
      }
    }
  }
  return { status: files.length === 0 ? 'skipped' : errors.length ? 'failed' : 'passed', files, errors };
}

function escapeCommand(value) {
  return String(value).replaceAll('%', '%25').replaceAll('\r', '%0D').replaceAll('\n', '%0A').replaceAll(':', '%3A').replaceAll(',', '%2C');
}

function escapeMarkdown(value) {
  return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('|', '&#124;').replaceAll('`', '&#96;').replaceAll('\r', ' ').replaceAll('\n', ' ');
}

export function renderReport(result, repositoryUrl) {
  const lines = ['# Project YAML Validation', '', `Result: **${result.status}**. Selected metadata files: ${result.files.length}. Errors: ${result.errors.length}.`, ''];
  if (!result.files.length) lines.push('No added or modified Project.yaml files. Project source-only changes and metadata deletions are skipped.', '');
  else lines.push('## Checked Files', '', ...result.files.map(file => `- ${escapeMarkdown(file)}`), '');
  if (result.errors.length) {
    lines.push('## Failures', '', '| File | Line | Field | Actual | Why / Expected |', '| --- | --- | --- | --- | --- |', ...result.errors.map(error => `| ${[error.file, error.line, error.field, error.actual, error.message].map(escapeMarkdown).join(' | ')} |`), '');
  }
  const prefix = repositoryUrl ? `${repositoryUrl}/` : '';
  lines.push('## Guidelines', '', `See [Project YAML guidelines](${prefix}.github/PROJECT_YAML_GUIDELINES.md) and [the allowed-value schema](${prefix}.github/project-yaml-schema.yaml).`, '');
  return lines.join('\n');
}

export function main() {
  const { values } = parseArgs({ options: {
    root: { type: 'string', default: defaultRoot },
    base: { type: 'string' },
    head: { type: 'string', default: 'HEAD' },
    all: { type: 'boolean', default: false },
    schema: { type: 'string' },
    report: { type: 'string', default: 'project-yaml-validation' },
  } });
  const root = path.resolve(values.root);
  if (!values.all && !values.base) throw new Error('Specify --base <commit> --head <commit>, or --all.');
  const files = values.all ? allMetadataFiles(root) : changedMetadataFiles(root, values.base, values.head);
  const result = validateProjects(root, files, values.schema);
  const repositoryUrl = process.env.GITHUB_REPOSITORY
    ? `${process.env.GITHUB_SERVER_URL || 'https://github.com'}/${process.env.GITHUB_REPOSITORY}/blob/${execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()}`
    : undefined;
  const report = renderReport(result, repositoryUrl);
  fs.writeFileSync(`${values.report}.json`, `${JSON.stringify(result, null, 2)}\n`);
  fs.writeFileSync(`${values.report}.md`, report);
  console.log(report);
  if (process.env.GITHUB_STEP_SUMMARY) {
    const guidelines = fs.readFileSync(path.join(root, '.github/PROJECT_YAML_GUIDELINES.md'), 'utf8');
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `${report}\n${guidelines}\n`);
  }
  if (process.env.GITHUB_ACTIONS === 'true') {
    for (const error of result.errors) console.log(`::error file=${escapeCommand(error.file)},line=${error.line},title=Invalid Project YAML::${escapeCommand(`${error.field}: ${error.message} Actual: ${error.actual}`)}`);
  }
  process.exitCode = result.errors.length ? 1 : 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
