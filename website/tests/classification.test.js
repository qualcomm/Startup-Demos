//--classification.test.js-------------------------------------------------//
// Part of the Startup-Demos Project, under the MIT License                 //
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt      //
// for license information.                                                 //
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.       //
// SPDX-License-Identifier: MIT License                                     //
//--------------------------------------------------------------------------//

import test from 'node:test';
import assert from 'node:assert/strict';
import { classifySource, generatedTopics, projectModels } from '../src/classification.js';
import { facetDefinitions, prepareCatalog } from '../src/catalog.js';

test('filter order matches the requested data contract', () => {
  assert.deepEqual(facetDefinitions.map(facet => facet.label), ['Technology', 'Platforms', 'Hardware', 'Software/Tools', 'AI Models', 'Topics/Tools', 'Peripherals/Sensors', 'Language', 'Source']);
});

test('AI Models combines declared models with explicit names, not frameworks', () => {
  assert.deepEqual(projectModels({ ai_models: ['YOLOv8'], description: 'yolov8 with ONNX and Whisper tiny' }), ['YOLOv8']);
  assert.deepEqual(projectModels({ description: 'ONNX runtime application' }), ['Not Specified']);
  assert.deepEqual(projectModels({ model: 'Custom model' }), ['Custom model']);
  assert.deepEqual(projectModels({ description: 'Gemma-4 and Gemma 4 with Llama3.3 and Llama 3.3' }), ['Gemma 4', 'Llama 3.3']);
});

test('migrated fields are authoritative, including explicit empty arrays', () => {
  const record = { repo_path: 'demo/new', long_name: 'Whisper camera demo', technology: ['Audio'], platforms: ['Android'], hardware: ['Device'], software_tools: ['ONNX'], ai_models: [], topics_tools: ['Reviewed topic'], peripherals_sensors: [], languages: ['Python'] };
  const project = prepareCatalog([record])[0];
  assert.equal(project.name, record.long_name);
  assert.deepEqual(project.facets.technology, ['Audio']);
  assert.deepEqual(project.facets.software_tools, ['ONNX']);
  assert.deepEqual(project.facets.models, ['Not Specified']);
  assert.deepEqual(project.facets.tags, ['Reviewed topic']);
  assert.deepEqual(project.facets.peripherals, ['Not Specified']);
  assert.deepEqual(prepareCatalog([{ ...record, topics_tools: [] }])[0].facets.tags, []);
});

test('source uses exact corporate domains and retains mixed affiliations', () => {
  assert.deepEqual(classifySource(['person@QUALCOMM.COM', 'person@lab.qualcomm.com']), ['Qualcomm']);
  assert.deepEqual(classifySource(['person@external.org', 'person@notqualcomm.com']), ['Third Party']);
  assert.deepEqual(classifySource(['person@qualcomm.com', 'person@external.org']), ['Qualcomm', 'Third Party']);
  assert.deepEqual(classifySource(['123+person@users.noreply.github.com', 'robot[bot]@users.noreply.github.com', '', 'invalid']), ['Not Specified']);
});

test('topics combine project tags with text-grounded generated classifications', () => {
  const record = { repo_path: 'vision/demo', name: 'YOLOv8 Demo', description: 'An ONNX object detection demo', category: ['CV_VR'], platforms: ['AI PC'], hardware_requirements: ['Device A'], tags: ['Custom topic'], languages: ['Python'], source_affiliations: ['Qualcomm'] };
  const project = prepareCatalog([record])[0];
  assert.deepEqual(project.facets.technology, ['Computer Vision & VR']);
  assert.deepEqual(project.facets.platform, ['AI PC']);
  assert.deepEqual(project.facets.hardware, ['Device A']);
  assert.deepEqual(project.facets.language, ['Python']);
  assert.deepEqual(project.facets.ownership, ['Qualcomm']);
  assert.deepEqual(project.facets.tags, ['Custom topic', 'Object Detection', 'ONNX']);
  assert.deepEqual(generatedTopics({ name: 'Unspecified demo' }), []);
  assert.deepEqual(prepareCatalog([{ ...record, source_affiliations: undefined, is_third_party: false }])[0].facets.ownership, ['Not Specified']);
});