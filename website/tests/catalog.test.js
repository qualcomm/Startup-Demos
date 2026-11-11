//--catalog.test.js--------------------------------------------------------//
// Part of the Startup-Demos Project, under the MIT License                 //
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt      //
// for license information.                                                 //
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.       //
// SPDX-License-Identifier: MIT License                                     //
//--------------------------------------------------------------------------//

import test from 'node:test';
import assert from 'node:assert/strict';
import { prepareCatalog, emptyState, selectProjects, facetOptions, readState, writeState, canonical, facetDefinitions } from '../src/catalog.js';

const records = [
  { name: 'EasyOCR', description: 'Read text', repo_path: 'vision/ocr', category: ['CV_VR', 'AI_PC'], platforms: ['AI PC'], tags: ['ONNX'], languages: ['Python'], last_updated: '2026-01-01' },
  { name: 'EasyOCR', description: 'Android text', repo_path: 'android/ocr', category: ['CV_VR', 'Android'], platforms: ['Android'], tags: ['MediaPipe'], languages: ['Java'] },
  { name: 'Assistant', description: 'Local chat', repo_path: 'ai/chat', category: ['GenAI'], platforms: ['AI PC'], tags: ['ONNX'], languages: ['Python'], last_updated: '2026-02-01' },
];
const projects = prepareCatalog(records);

test('peripheral section preserves requested order and uses explicit metadata evidence', () => {
  assert.deepEqual(facetDefinitions.map(facet => facet.label), ['Technology', 'Platforms', 'Hardware', 'Software/Tools', 'AI Models', 'Topics/Tools', 'Peripherals/Sensors', 'Language', 'Source']);
  const catalog = prepareCatalog([
    { ...records[0], description: 'Read text from a webcam', sensors: ['Ultrasonic Sensor'], peripherals: ['USB relay'] },
    records[1],
  ]);
  assert.deepEqual(catalog[0].facets.peripherals, ['Camera', 'Ultrasonic Sensor', 'USB relay']);
  assert.deepEqual(catalog[1].facets.peripherals, ['Not Specified']);
  const state = emptyState();
  state.filters.peripherals = ['Camera'];
  assert.equal(selectProjects(catalog, state).length, 1);
  assert.deepEqual(readState(writeState(state)), state);
  state.query = 'ultrasonic';
  assert.equal(selectProjects(catalog, state).length, 1);
});

test('new project metadata fields populate catalog facets and preserve explicit empty peripherals', () => {
  const [project] = prepareCatalog([{
    long_name: 'Data Payload Monitor', shortname: 'data-payload-monitor', description: 'Processes sensor data.',
    repo_path: 'Others/IoT-Robotics/Data_Payload_Monitor', technology: ['Other applications'],
    platforms: ['IoT-Robotics', 'RB3 Gen2'], hardware: ['QCS6490'], software_tools: ['Linux', 'Ubuntu', 'Streamlit'],
    ai_models: [], topics_tools: ['IoT', 'Monitoring'], peripherals_sensors: [], picture: 'Images/preview.png',
    languages: ['Python'], source_affiliations: ['Qualcomm'],
  }]);
  assert.equal(project.name, 'Data Payload Monitor');
  assert.deepEqual(project.facets.hardware, ['QCS6490']);
  assert.deepEqual(project.facets.software_tools, ['Linux', 'Ubuntu', 'Streamlit']);
  assert.deepEqual(project.facets.tags, ['IoT', 'Monitoring']);
  assert.deepEqual(project.facets.peripherals, ['Not Specified']);
  assert.equal(project.searchText.includes('data payload monitor'), true);
});

test('one entry per path, not category or name', () => {
  assert.equal(projects.length, 3);
  assert.equal(projects.filter(project => project.name === 'EasyOCR').length, 2);
  assert.deepEqual(projects[0].facets.technology, ['Computer Vision & VR']);
  assert.throws(() => prepareCatalog([records[0], records[0]]), /duplicate/);
});

test('OR within groups, AND between groups and search terms', () => {
  const state = emptyState();
  state.filters.platform = ['AI PC', 'Android'];
  state.filters.language = ['Python'];
  assert.equal(selectProjects(projects, state).length, 2);
  state.query = 'onnx text';
  assert.deepEqual(selectProjects(projects, state).map(project => project.id), ['vision/ocr']);
});

test('facet counts ignore own group and retain selected zero matches', () => {
  const state = emptyState();
  state.filters.platform = ['AI PC'];
  assert.equal(facetOptions(projects, state, 'platform').find(option => option.label === 'Android').count, 1);
  state.filters.language = ['Java'];
  assert.equal(facetOptions(projects, state, 'platform').find(option => option.label === 'AI PC').count, 0);
});

test('aliases normalize and state round trips with repeated selections', () => {
  assert.equal(canonical(' AIC100Ultra '), 'AIC100 Ultra');
  assert.equal(canonical('Object detection'), 'Object Detection');
  const state = emptyState();
  state.query = 'text & vision';
  state.filters.platform = ['AI PC', 'Android'];
  state.view = 'list';
  state.page = 2;
  assert.deepEqual(readState(writeState(state)), state);
  assert.equal(readState('?page=Infinity&sort=bad&view=bad').page, 1);
});

test('sort uses parsed dates, missing dates last, stable name/path ties', () => {
  const state = emptyState();
  state.sort = 'updated';
  assert.deepEqual(selectProjects(projects, state).map(project => project.id), ['ai/chat', 'vision/ocr', 'android/ocr']);
  state.sort = 'name-desc';
  assert.equal(selectProjects(projects, state).at(-1).name, 'Assistant');
});