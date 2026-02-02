//--build-catalog.js--------------------------------------------------------//
// Part of the Startup-Demos Project, under the MIT License                 //
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt      //
// for license information.                                                 //
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.       //
// SPDX-License-Identifier: MIT License                                     //
//--------------------------------------------------------------------------//
import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import glob from 'fast-glob';
import { execSync } from 'child_process';

// Detect repository root
const getRepoRoot = () => {
  try {
    // Try from current working directory first
    const root = execSync('git rev-parse --show-toplevel', { encoding: 'utf8' }).trim();
    return root;
  } catch (error) {
    // Fallback: assume we're in website/ directory
    return path.resolve(process.cwd(), '..');
  }
};

const REPO_ROOT = getRepoRoot();
console.log(`Repository root: ${REPO_ROOT}`);

/**
 * Detect programming languages in a directory by scanning file extensions
 */
function detectLanguages(projectDir) {
  const extToLang = {
    // Web - JavaScript/TypeScript
    'js': 'JavaScript', 'mjs': 'JavaScript', 'cjs': 'JavaScript',
    'ts': 'TypeScript', 'tsx': 'TypeScript',
    'jsx': 'JSX',

    // Web Frameworks
    'vue': 'Vue',
    'svelte': 'Svelte',

    // Python
    'py': 'Python', 'pyw': 'Python', 'pyx': 'Python', 'pyd': 'Python',

    // Java/JVM
    'java': 'Java',
    'kt': 'Kotlin', 'kts': 'Kotlin',
    'scala': 'Scala', 'sc': 'Scala',
    'groovy': 'Groovy', 'gvy': 'Groovy',
    'clj': 'Clojure', 'cljs': 'Clojure',

    // C/C++
    'c': 'C',
    'cpp': 'C++', 'cc': 'C++', 'cxx': 'C++', 'c++': 'C++',
    'h': 'C/C++', 'hpp': 'C++', 'hh': 'C++', 'hxx': 'C++',

    // C#/.NET
    'cs': 'C#',
    'fs': 'F#', 'fsi': 'F#', 'fsx': 'F#',
    'vb': 'Visual Basic',

    // Mobile
    'swift': 'Swift',
    'm': 'Objective-C',
    'mm': 'Objective-C++',
    'dart': 'Dart',

    // Systems Programming
    'rs': 'Rust',
    'go': 'Go',
    'zig': 'Zig',
    'v': 'V',
    'nim': 'Nim',

    // Functional Languages
    'hs': 'Haskell', 'lhs': 'Haskell',
    'erl': 'Erlang', 'hrl': 'Erlang',
    'ex': 'Elixir', 'exs': 'Elixir',
    'ml': 'OCaml', 'mli': 'OCaml',

    // Scripting
    'rb': 'Ruby',
    'php': 'PHP',
    'pl': 'Perl', 'pm': 'Perl',
    'lua': 'Lua',
    'r': 'R',
    'jl': 'Julia',

    // Data Science/Notebooks
    'ipynb': 'Jupyter',
    'rmd': 'R Markdown',

    // Database
    'sql': 'SQL',

    // Markup/Config (only if they contain logic)
    'graphql': 'GraphQL', 'gql': 'GraphQL',
    
    // Emerging/Blockchain
    'sol': 'Solidity',
    'wasm': 'WebAssembly',

    // Other Modern Languages
    'cr': 'Crystal',
    'elm': 'Elm',
    'purs': 'PureScript',
    'res': 'ReScript',
    'roc': 'Roc'
  };

  const unimportantLanguages = new Set([
    'CMake', 'Makefile', 'Dockerfile', 'Batchfile',
    'PowerShell', 'YAML', 'JSON', 'XML', 'HTML', 'CSS', 'SCSS', 'LESS', 'Sass',
    'Markdown', 'Text', 'Gradle', 'Properties', 'INI', 'TOML',
    'SVG', 'Protobuf'
  ]);

  try {
    // Find all source files recursively
    const pattern = `${projectDir}/**/*.{${Object.keys(extToLang).join(',')}}`;
    const files = glob.sync(pattern, {
      ignore: ['**/node_modules/**', '**/venv/**', '**/__pycache__/**', '**/dist/**', '**/build/**',
        '**/.git/**', '**/.gradle/**', '**/out/**', '**/bin/**', '**/obj/**', '**/target/**',
        '**/images/**', '**/assets/**', '**/models/**', '**/.next/**', '**/.nuxt/**',
        '**/vendor/**', '**/bower_components/**', '**/coverage/**']
    });

    const languages = new Set();
    files.forEach(file => {
      const ext = path.extname(file).slice(1).toLowerCase();
      const lang = extToLang[ext];
      if (lang && !unimportantLanguages.has(lang)) {
        languages.add(lang);
      }
    });

    const languageArray = Array.from(languages);
    return languageArray.length > 4 ? languageArray.slice(0, 4) : languageArray;
  } catch (error) {
    console.warn(`Error detecting languages for ${projectDir}:`, error.message);
    return [];
  }
}

/**
 * Get developers from git commit history (excluding merge commits and project.yaml changes)
 */
function getDevelopers(projectDir) {
  try {
    // Get all commit authors for this directory, excluding merges and project.yaml-only commits
    const cmd = `git log --no-merges --format="%ae|%s" -- "${projectDir}"`;
    const output = execSync(cmd, {
      cwd: REPO_ROOT,
      encoding: 'utf8',
      maxBuffer: 10 * 1024 * 1024
    });

    if (!output.trim()) {
      return [];
    }

    // Extract unique usernames from emails, excluding project.yaml addition commits
    const lines = output.trim().split('\n');
    const developers = new Set();

    lines.forEach(line => {
      if (line && line.includes('|')) {
        const [email, subject] = line.split('|');
        // Skip commits that only add project.yaml or are catalog-related
        if (subject &&
            !subject.toLowerCase().includes('add project.yaml') &&
            !subject.toLowerCase().includes('project catalog') &&
            !subject.toLowerCase().includes('update catalog') &&
            !subject.toLowerCase().includes('project.yaml')) {
          if (email && email.includes('@')) {
            const username = email.split('@')[0].trim();
            if (username) {
              developers.add(username);
            }
          }
        }
      }
    });

    const devArray = Array.from(developers);
    // Cap at 12 developers
    return devArray.length > 12 ? devArray.slice(0, 12) : devArray;
  } catch (error) {
    console.warn(`Error getting developers for ${projectDir}:`, error.message);
    return [];
  }
}

/**
 * Get the last commit date for a specific project directory
 */
function getLastCommitDate(projectDir) {
  try {
    const cmd = `git log -1 --format="%ad" --date=short -- "${projectDir}"`;
    const output = execSync(cmd, {
      cwd: REPO_ROOT,
      encoding: 'utf8',
      maxBuffer: 10 * 1024 * 1024
    });

    const date = output.trim();
    return date || null;
  } catch (error) {
    console.warn(`Error getting last commit date for ${projectDir}:`, error.message);
    return null;
  }
}

const main = async () => {
  // Search for all project.yaml files in the repository, ignoring node_modules
  const files = await glob(`${REPO_ROOT}/**/project.yaml`, {
    ignore: ['**/node_modules/**'],
    absolute: true,
  });

  const projects = [];

  for (const file of files) {
    try {
      const content = fs.readFileSync(file, 'utf8');
      const doc = yaml.load(content);

      // Basic validation
      if (!doc.name || !doc.description || !doc.category || !Array.isArray(doc.category)) {
        console.warn(`Skipping invalid project file: ${file}. Missing or invalid required fields (name, description, category as array).`);
        continue;
      }

      // Add a relative path to the project's directory for linking
      const relativePath = path.relative(REPO_ROOT, path.dirname(file));
      doc.repo_path = relativePath.replace(/\\/g, '/');

      // Detect languages from source files
      const projectAbsPath = path.dirname(file);
      console.log(`Scanning ${doc.name} at ${projectAbsPath}...`);
      doc.languages = detectLanguages(projectAbsPath);
      console.log(`  Languages: ${doc.languages.length > 0 ? doc.languages.join(', ') : 'none'}`);

      // Get developers from git history
      const projectRelPath = path.relative(REPO_ROOT, projectAbsPath);
      doc.developers = getDevelopers(projectRelPath);
      console.log(`  Developers: ${doc.developers.length > 0 ? doc.developers.join(', ') : 'none'}`);

      // Get last commit date
      doc.last_updated = getLastCommitDate(projectRelPath);
      console.log(`  Last Updated: ${doc.last_updated || 'unknown'}`);

      projects.push(doc);
    } catch (e) {
      console.error(`Error processing file ${file}:`, e);
    }
  }

  // Ensure public directory exists
  const publicDir = path.join(process.cwd(), 'public');
  if (!fs.existsSync(publicDir)) {
    fs.mkdirSync(publicDir, { recursive: true });
  }

  // Write the aggregated data to a JSON file in the public directory
  const outputPath = path.join(publicDir, 'catalog.json');
  fs.writeFileSync(outputPath, JSON.stringify(projects, null, 2));

  console.log(`Successfully generated catalog with ${projects.length} projects.`);
};

main();
