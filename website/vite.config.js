//--vite.config.js----------------------------------------------------------//
// Part of the Startup-Demos Project, under the MIT License                 //
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt      //
// for license information.                                                 //
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.       //
// SPDX-License-Identifier: MIT License                                     //
//--------------------------------------------------------------------------//
import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import { repositoryInfo } from './scripts/repository.js';

// https://vitejs.dev/config/
export default defineConfig({
  define: {
    __PUBLISHING_REPOSITORY__: JSON.stringify(repositoryInfo(process.env, fileURLToPath(new URL('..', import.meta.url)))),
  },
  // Use relative paths so the build works from any GitHub Pages subpath
  // (public GitHub, GHES /pages/owner/repo/, forks, and preview paths).
  base: './',
});
