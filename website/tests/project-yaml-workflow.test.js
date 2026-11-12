import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import yaml from 'js-yaml';

const workflow = yaml.load(fs.readFileSync(new URL('../../.github/workflows/project-yaml-validation.yml', import.meta.url), 'utf8'));

test('every PR gets trusted validation without path or branch filters', () => {
  const trigger = workflow.on.pull_request_target;
  assert.ok(trigger);
  for (const event of ['opened', 'synchronize', 'reopened', 'ready_for_review', 'converted_to_draft', 'edited']) assert.ok(trigger.types.includes(event));
  assert.equal(trigger.paths, undefined);
  assert.equal(trigger.branches, undefined);
  assert.ok(workflow.on.merge_group);
  assert.ok(workflow.on.workflow_dispatch.inputs.pull_request_number);
});

test('required result is published on candidate SHA with pass fail skip outcomes', () => {
  const job = workflow.jobs.validate;
  assert.equal(job['runs-on'], 'self-hosted');
  assert.equal(job.if, undefined);
  assert.equal(workflow.permissions.contents, 'read');
  assert.equal(workflow.permissions.statuses, 'write');
  assert.equal(workflow.permissions.checks, undefined);
  assert.equal(workflow.permissions['pull-requests'], 'write');
  assert.ok(!job.steps.some(step => step.uses?.includes('checkout')));
  const script = job.steps.find(step => step.uses?.includes('github-script')).with.script;
  assert.ok(script.includes("context: 'Project YAML Validity'"));
  assert.ok(script.includes('sha: evaluationContext.sha'));
  assert.ok(!script.includes('github.rest.checks.create'));
  assert.ok(!script.includes('github.rest.checks'));
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  assert.doesNotThrow(() => new AsyncFunction('github', 'context', 'core', 'require', script));
});

test('optional upload cannot block or override mandatory validation', () => {
  const job = workflow.jobs.validate;
  assert.equal(job['timeout-minutes'], 15);
  const upload = job.steps.find(step => step.uses?.includes('upload-artifact'));
  assert.equal(upload['timeout-minutes'], 2);
  assert.equal(upload['continue-on-error'], true);
  assert.notEqual(job.steps.find(step => step.uses?.includes('github-script'))['continue-on-error'], true);
});

test('publisher completes a head-commit check for pass, fail, skip and bootstrap failure', async context => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'project-yaml-publisher-'));
  const previousTemp = process.env.RUNNER_TEMP;
  const previousPr = process.env.RECHECK_PR;
  process.env.RUNNER_TEMP = directory;
  process.env.RECHECK_PR = '';
  context.after(() => {
    if (previousTemp === undefined) delete process.env.RUNNER_TEMP;
    else process.env.RUNNER_TEMP = previousTemp;
    if (previousPr === undefined) delete process.env.RECHECK_PR;
    else process.env.RECHECK_PR = previousPr;
    fs.rmSync(directory, { recursive: true, force: true });
  });
  const script = workflow.jobs.validate.steps.find(step => step.uses?.includes('github-script')).with.script;
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  const execute = new AsyncFunction('github', 'context', 'core', 'require', script);
  const require = createRequire(import.meta.url);
  const statuses = [['passed', 'success'], ['failed', 'failure'], ['skipped', 'success'], ['bootstrap-error', 'error']];
  for (const [status, conclusion] of statuses) {
    const calls = [];
    const comments = [];
    const github = { rest: {
      pulls: { get: async () => ({ data: { head: { sha: 'candidate-sha' } } }) },
      checks: { listForRef() {}, update: async () => { throw new Error('Unrelated checks must not be modified.'); } },
      issues: {
        listComments() {},
        createComment: async parameters => { comments.push(parameters); },
        updateComment: async parameters => { comments.push(parameters); },
      },
      repos: {
        createCommitStatus: async parameters => { calls.push(parameters); },
        getBranch: async () => ({ data: { commit: { sha: 'trusted-sha' } } }),
        getContent: async parameters => {
          assert.equal(parameters.ref, 'trusted-sha');
          if (status === 'bootstrap-error') throw new Error('API unavailable');
          const errors = status === 'failed' ? [{ file: 'demo/project.yaml', line: 1, field: '$/picture', message: 'Missing required picture.', actual: '(missing)' }] : [];
          return { data: { type: 'file', encoding: 'base64', content: Buffer.from(`module.exports = { run: async () => ({status: ${JSON.stringify(status)}, errors: ${JSON.stringify(errors)}, report: 'test report'}) };`).toString('base64') } };
        },
      },
    } };
    github.paginate = async method => method === github.rest.checks.listForRef ? [] : status === 'failed' ? [{ id: 456, user: { type: 'Bot' }, body: '<!-- project-yaml-validation --> old report' }] : [];
    const event = { repo: { owner: 'owner', repo: 'repo' }, runId: status, sha: 'base-sha', eventName: 'pull_request_target', payload: { repository: { default_branch: 'main' }, pull_request: { number: 66, head: { sha: 'candidate-sha' } } } };
    await execute(github, event, { setFailed() {} }, require);
    assert.equal(calls[0].sha, 'candidate-sha');
    assert.equal(calls[0].context, 'Project YAML Validity');
    assert.equal(calls[0].state, 'pending');
    assert.ok(calls[0].target_url.startsWith('https://'));
    assert.ok(!calls[0].target_url.includes('undefined'));
    assert.equal(calls[1].state, conclusion);
    assert.equal(comments.length, 1);
    assert.ok(comments[0].body.startsWith('<!-- project-yaml-validation -->'));
    assert.ok(!comments[0].body.includes('Checked commit:'));
    if (status === 'failed') {
      assert.equal(calls[1].description, 'Project YAML: FAIL (1 errors)');
      assert.equal(comments[0].comment_id, 456);
    } else assert.equal(comments[0].issue_number, 66);
  }
});
