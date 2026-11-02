//===--run.cjs--------------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//

const { evaluateReviews } = require('./policy.cjs');
const { postInstructionsOnce } = require('./instructions.cjs');

module.exports = async function run({ github, membership, context, core }) {
  const repository = context.repo;
  const statusContext = 'Peer-Review Check';
  const targetUrl = `${context.serverUrl}/${repository.owner}/${repository.repo}/actions/runs/${context.runId}`;
  const group = context.payload.merge_group;
  const targets = new Set(group ? [group.head_sha] : []);
  if (context.payload.pull_request) targets.add(context.payload.pull_request.head.sha);
  const publish = async (sha, state, description) => github.rest.repos.createCommitStatus({
    ...repository, sha, state, context: statusContext,
    description: description.slice(0, 140), target_url: targetUrl,
  });

  try {
    const branch = process.env.SOURCE_BRANCH;
    const eventBranch = group?.base_ref.replace(/^refs\/heads\//, '') || context.payload.pull_request?.base.ref;
    if (eventBranch && eventBranch !== branch) {
      core.info('Skipping PRs outside the configured source branch.');
      return;
    }
    const targetPullRequestNumber = process.env.REVIEW_PR_NUMBER || context.payload.pull_request?.number;
    let requests;
    if (targetPullRequestNumber) {
      const number = Number(targetPullRequestNumber);
      if (!Number.isSafeInteger(number) || number < 1) {
        throw new Error('Review signal must contain a valid pull request number');
      }
      const response = await github.rest.pulls.get({ ...repository, pull_number: number });
      const request = response.data;
      if (request.state !== 'open' || request.base.ref !== branch) {
        core.info(`Skipping PR #${number}: it is closed or targets a different branch.`);
        return;
      }
      requests = [request];
    } else {
      requests = await github.paginate(github.rest.pulls.list, {
        ...repository, state: 'open', base: branch, per_page: 100,
      });
    }
    if (group) {
      const included = [];
      for (const request of requests) {
        const comparison = await github.rest.repos.compareCommitsWithBasehead({
          ...repository, basehead: `${request.head.sha}...${group.head_sha}`,
        });
        if (['ahead', 'identical'].includes(comparison.data.status)) included.push(request);
      }
      requests = included;
      if (!requests.length) throw new Error('No open PR could be verified in the merge group');
    }
    for (const request of requests) targets.add(request.head.sha);
    for (const sha of targets) await publish(sha, 'pending', 'Evaluating peer approvals');
    if (!requests.length) {
      core.info('No open source PRs to evaluate.');
      return;
    }

    const members = async slug => (await membership.paginate(membership.rest.teams.listMembersInOrg, {
      org: repository.owner, team_slug: slug, per_page: 100,
    })).map(user => user.login);
    const contributors = await members(process.env.CONTRIBUTORS_TEAM);
    const results = [];
    for (const request of requests) {
      core.info(`Evaluating PR #${request.number}`);
      await postInstructionsOnce({ github, repository, request, contributors });
      const reviews = await github.paginate(github.rest.pulls.listReviews, {
        ...repository, pull_number: request.number, per_page: 100,
      });
      const result = evaluateReviews({
        author: request.user.login, headSha: request.head.sha,
        reviews, contributors,
      });
      const current = await github.rest.pulls.get({ ...repository, pull_number: request.number });
      if (current.data.head.sha !== request.head.sha || current.data.state !== 'open') {
        throw new Error(`PR #${request.number} changed during evaluation; retry required`);
      }
      if (current.data.draft) {
        result.approved = false;
        result.reason = 'Draft PRs are not eligible for merge';
      }
      results.push(result);
      core.info(`PR #${request.number}: ${result.reason}`);
      await publish(request.head.sha, result.approved ? 'success' : 'failure', result.reason);
    }
    if (group) {
      const approved = results.every(result => result.approved);
      await publish(group.head_sha, approved ? 'success' : 'failure',
        approved ? 'All grouped PRs have two current-commit peer approvals' : 'A grouped PR lacks required peer reviews');
    }
  } catch (error) {
    core.error(`Policy evaluation failed: ${JSON.stringify({
      name: error.name,
      message: error.message,
      status: error.status,
      request: error.request && { method: error.request.method, url: error.request.url },
      response: error.response && {
        status: error.response.status,
        data: error.response.data,
        requestId: error.response.headers?.['x-github-request-id'],
      },
      cause: error.cause && { name: error.cause.name, message: error.cause.message, code: error.cause.code },
    })}`);
    for (const sha of targets) {
      try {
        await publish(sha, 'error', 'Review policy evaluation failed; see workflow logs');
      } catch (statusError) {
        core.error(`Could not publish policy error for ${sha}: ${JSON.stringify({
          name: statusError.name,
          message: statusError.message,
          status: statusError.status,
          response: statusError.response?.data,
          cause: statusError.cause && { name: statusError.cause.name, message: statusError.cause.message, code: statusError.cause.code },
        })}`);
      }
    }
    core.setFailed(error.message);
  }
};