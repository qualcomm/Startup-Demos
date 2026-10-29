#===--workflow-gates.test.rb-----------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

require 'yaml'
require 'open3'
require 'tempfile'

Dir.chdir(File.expand_path('../../..', __dir__)) do
  source_url = 'https://github.com/example/source'
  defaults = {
    'SOURCE_URL' => source_url + '.git', 'SOURCE_BRANCH' => 'main',
    'MERGED_BRANCH' => 'main', 'EVENT_NAME' => 'workflow_dispatch',
    'REF_NAME' => 'main', 'PR_BASE_REF' => 'main',
    'MERGE_GROUP_BASE_REF' => 'refs/heads/main',
    'GITHUB_SERVER_URL' => 'https://github.com',
    'GITHUB_REPOSITORY' => 'example/source', 'REPOSITORY' => 'example/source',
    'RUNNER_STATUS_TOKEN' => '', 'GITHUB_TOKEN' => 'test', 'PAGES_RUNNER' => '',
    'MOCK_ONLINE' => '', 'MOCK_GIT' => '0'
  }
  checks = 0
  check = lambda do |script, overrides, expected, success = true|
    Tempfile.create('workflow-output') do |output|
      environment = defaults.merge(overrides).merge('GITHUB_OUTPUT' => output.path)
      mocks = <<~BASH
        gh() { [[ -n "$MOCK_ONLINE" ]] || return 1; printf '%s' "$MOCK_ONLINE"; }
        timeout() { return "$MOCK_GIT"; }
      BASH
      stdout, stderr, status = Open3.capture3(
        environment, 'bash', '-e', '-o', 'pipefail', '-c', mocks + script
      )
      result = File.read(output.path).lines.map(&:strip).last
      unless status.success? == success && (!success || result == expected)
        raise "Unexpected result #{overrides}: #{result}\n#{stdout}\n#{stderr}"
      end
      checks += 1
    end
  end

  %w[forward-sync reverse-sync].each do |name|
    workflow = YAML.load_file(".github/workflows/#{name}.yml")
    gate = workflow.fetch('jobs').fetch('source')
    raise 'Source gate must not need self-hosted runner' unless gate['runs-on'] == 'ubuntu-latest'
    script = gate.fetch('steps').first.fetch('run')
    check.call(script, {}, 'sync=true')
    check.call(script, {'SOURCE_URL' => source_url.upcase + '/'}, 'sync=true')
    check.call(script, {'GITHUB_REPOSITORY' => 'example/destination'}, 'sync=false')
    check.call(script, {'SOURCE_URL' => ''}, 'sync=false')
    check.call(script, {'MERGED_BRANCH' => 'other', 'REF_NAME' => 'other'}, 'sync=false')
    if name == 'reverse-sync'
      check.call(script, {'EVENT_NAME' => 'pull_request_target', 'REF_NAME' => '123/merge'}, 'sync=true')
      check.call(script, {'EVENT_NAME' => 'merge_group', 'REF_NAME' => 'gh-readonly-queue/main/test'}, 'sync=true')
    end
  end

  reverse = YAML.load_file('.github/workflows/reverse-sync.yml')
  sync_step = reverse.fetch('jobs').fetch('reverse-sync').fetch('steps').find { |step| step['id'] == 'sync' }
  raise 'Dry-run input must be passed through env' unless sync_step.fetch('env').fetch('DRY_RUN') == '${{ inputs.dry_run || false }}'
  raise 'Run script must not interpolate expressions' if sync_step.fetch('run').include?('${{')
  sync_script = <<~BASH
    python3() { printf '%s\n' "${!#}" >> "$GITHUB_OUTPUT"; }
  BASH
  sync_script += sync_step.fetch('run')
  check.call(sync_script, {'DRY_RUN' => 'true'}, '--dry-run')
  ['', 'false', 'TRUE', '$(exit 99)', '"; exit 99; #'].each do |value|
    check.call(sync_script, {'DRY_RUN' => value}, '--no-dry-run')
  end

  forward = YAML.load_file('.github/workflows/forward-sync.yml')
  forwarded = forward.fetch('jobs').fetch('update-readme').fetch('secrets')
  raise 'README job must receive only its required token' unless forwarded == {'SYNC_SOURCE_TOKEN' => '${{ secrets.SYNC_SOURCE_TOKEN }}'}
  readme = YAML.load_file('.github/workflows/update-readme.yml')
  events = readme.fetch('on', readme[true])
  declared = events.fetch('workflow_call').fetch('secrets')
  raise 'README token must be declared as required' unless declared == {'SYNC_SOURCE_TOKEN' => {'required' => true}}
  checks += 4

  script = YAML.load_file('.github/workflows/deploy.yml').fetch('jobs').fetch('select-runner').fetch('steps').first.fetch('run')
  check.call(script, {}, 'runner=ubuntu-latest')
  check.call(script, {'SOURCE_URL' => '', 'RUNNER_STATUS_TOKEN' => '', 'GITHUB_TOKEN' => '', 'MOCK_GIT' => '1'}, 'runner=ubuntu-latest')
  check.call(script, {'MOCK_GIT' => '1'}, 'runner=self-hosted')
  check.call(script, {'REPOSITORY' => 'example/destination'}, 'runner=ubuntu-latest')
  check.call(script, {'REPOSITORY' => 'example/destination', 'MOCK_GIT' => '1'}, nil, false)
  check.call(script, {'RUNNER_STATUS_TOKEN' => 'test', 'MOCK_ONLINE' => '1', 'MOCK_GIT' => '1'}, 'runner=self-hosted')
  check.call(script, {'RUNNER_STATUS_TOKEN' => 'test', 'MOCK_ONLINE' => '0'}, 'runner=ubuntu-latest')
  check.call(script, {'RUNNER_STATUS_TOKEN' => 'test', 'MOCK_ONLINE' => '0', 'MOCK_GIT' => '1'}, nil, false)
  check.call(script, {'RUNNER_STATUS_TOKEN' => 'test', 'MOCK_ONLINE' => 'error', 'MOCK_GIT' => '1'}, 'runner=self-hosted')
  check.call(script, {'PAGES_RUNNER' => 'self-hosted'}, 'runner=self-hosted')
  check.call(script, {'PAGES_RUNNER' => 'ubuntu-latest', 'MOCK_GIT' => '1'}, 'runner=ubuntu-latest')
  check.call(script, {'PAGES_RUNNER' => 'invalid'}, nil, false)
  puts "PASS: #{checks} source/destination workflow cases"
end