//--vite.config.js----------------------------------------------------------//
// Part of the Startup-Demos Project, under the MIT License                 //
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt      //
// for license information.                                                 //
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.       //
// SPDX-License-Identifier: MIT License                                     //
//--------------------------------------------------------------------------//
import { defineConfig } from 'vite';

// Automatically determine base path from repository name
// For GHES Pages: /pages/owner/repo/
// For GitHub.com Pages: /repo/
const getBasePath = () => {
  if (process.env.GITHUB_REPOSITORY) {
    const [owner, repo] = process.env.GITHUB_REPOSITORY.split('/');
    // Check if this is GHES (github.qualcomm.com) or public GitHub
    // For GHES, the path is /pages/owner/repo/
    if (process.env.GITHUB_SERVER_URL && process.env.GITHUB_SERVER_URL.includes('github.qualcomm.com')) {
      return `/pages/${owner}/${repo}/`;
    }
    // For public GitHub, just /repo/
    return `/${repo}/`;
  }
  return '/Startup-Demos/'; // Default for local dev
};

// https://vitejs.dev/config/
export default defineConfig({
  base: getBasePath(),
});
