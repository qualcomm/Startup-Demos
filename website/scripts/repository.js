import { spawnSync } from 'node:child_process';

export function repositoryInfo(environment = process.env, cwd = process.cwd(), git = args => {
  const result = spawnSync('git', args, { cwd, encoding: 'utf8' });
  return result.status === 0 ? result.stdout.trim() : '';
}) {
  let url;
  if (environment.GITHUB_REPOSITORY) {
    url = `${environment.GITHUB_SERVER_URL || 'https://github.com'}/${environment.GITHUB_REPOSITORY}`;
  } else {
    const remote = git(['config', '--get', 'remote.origin.url']);
    url = remote.replace(/^git@([^:]+):/, 'https://$1/').replace(/^ssh:\/\/git@/, 'https://').replace(/\.git$/, '');
  }
  let parsed;
  try { parsed = new URL(url); } catch { throw new Error('Cannot determine publishing repository. Set GITHUB_REPOSITORY or configure remote.origin.url.'); }
  if (!['https:', 'http:'].includes(parsed.protocol)) throw new Error('Unsupported publishing repository URL');
  parsed.username = '';
  parsed.password = '';
  parsed.search = '';
  parsed.hash = '';
  const branch = environment.REPOSITORY_DEFAULT_BRANCH || git(['symbolic-ref', '--short', 'refs/remotes/origin/HEAD']).replace(/^origin\//, '') || 'main';
  const root = parsed.href.replace(/\/$/, '');
  return { url: root, sourceBase: `${root}/tree/${encodeURIComponent(branch)}/`, documentBase: `${root}/blob/${encodeURIComponent(branch)}/` };
}