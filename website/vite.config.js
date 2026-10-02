//--vite.config.js----------------------------------------------------------//
// Part of the Startup-Demos Project, under the MIT License                 //
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt      //
// for license information.                                                 //
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.       //
// SPDX-License-Identifier: MIT License                                     //
//--------------------------------------------------------------------------//
import { defineConfig } from 'vite';

// https://vitejs.dev/config/
export default defineConfig({
  // Use relative paths so the build works from any GitHub Pages subpath
  // (public GitHub, GHES /pages/owner/repo/, forks, and preview paths).
  base: './',
});
