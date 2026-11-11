//--classification.js------------------------------------------------------//
// Part of the Startup-Demos Project, under the MIT License                 //
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt      //
// for license information.                                                 //
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.       //
// SPDX-License-Identifier: MIT License                                     //
//--------------------------------------------------------------------------//

export function classifySource(emails) {
  const sources = new Set();
  for (const email of emails) {
    const normalized = email.trim().toLowerCase();
    if (/\[bot\]|\bbot@/.test(normalized)) continue;
    const match = normalized.match(/^[^\s@]+@([^\s@]+\.[^\s@]+)$/);
    if (!match) continue;
    const domain = match[1];
    if (domain === 'users.noreply.github.com' || domain === 'noreply.github.com') continue;
    if (domain === 'qualcomm.com' || domain.endsWith('.qualcomm.com')) sources.add('Qualcomm');
    else sources.add('Third Party');
  }
  return sources.size ? [...sources].sort() : ['Not Specified'];
}

const topicRules = [
  ['Object Detection', /\bobject detection\b|\byolo(?:v\d+)?\b/i],
  ['Image Classification', /\bimage classification\b/i],
  ['Optical Character Recognition', /\bocr\b|\boptical character recognition\b|\beasyocr\b/i],
  ['Speech Recognition', /\bspeech recognition\b|\basr\b|\bwhisper\b/i],
  ['Text to Speech', /\btext[ -]to[ -]speech\b|\btts\b/i],
  ['ONNX', /\bonnx\b/i],
  ['MediaPipe', /\bmediapipe\b/i],
  ['PyTorch', /\bpytorch\b/i],
  ['TensorFlow', /\btensorflow\b/i],
  ['GStreamer', /\bgstreamer\b/i],
  ['Large Language Models', /\bllm\b|\blarge language models?\b/i],
  ['Vision Language Models', /\bvlm\b|\bvision[ -]language models?\b/i],
];

export function generatedTopics(record) {
  const topics = record.topics_tools ?? record.tags;
  const text = [record.long_name || record.name, record.description, ...(Array.isArray(topics) ? topics : [])].join(' ');
  return topicRules.filter(([, pattern]) => pattern.test(text)).map(([label]) => label);
}

export function projectModels(record) {
  if (Array.isArray(record.ai_models)) {
    const models = [...new Set(record.ai_models.filter(value => typeof value === 'string' && value.trim()).map(value => value.trim()))];
    return models.length ? models : ['Not Specified'];
  }
  const declared = [record.ai_models, record.models, record.model]
    .flatMap(value => Array.isArray(value) ? value : typeof value === 'string' ? [value] : [])
    .filter(value => typeof value === 'string' && value.trim()).map(value => value.trim());
  const topics = record.topics_tools ?? record.tags;
  const text = [record.long_name || record.name, record.description, ...(Array.isArray(topics) ? topics : [])].join(' ');
  const detected = Array.from(text.matchAll(/\b(?:yolov\d+(?:[nslmx])?|yolo[ -]nas|whisper(?:[ -](?:tiny|base|small|medium|large)(?:-v\d+)?)?|llama[ -]?\d*(?:\.\d+)?|qwen\d*(?:\.\d+)?|phi[ -]?\d+(?:\.\d+)?|gemma[ -]?\d*|mobilenet(?:v\d+)?|resnet[ -]?\d+|efficientnet(?:[ -]b\d+)?|stable diffusion|piper(?:-tts)?|easyocr)\b/gi), match => match[0]);
  const models = new Map();
  for (const model of [...declared, ...detected]) {
    const label = model.trim().replace(/^(llama|gemma|qwen|phi)[ -]*(\d)/i, (_, family, version) => `${family[0].toUpperCase()}${family.slice(1).toLowerCase()} ${version}`);
    const key = label.toLowerCase().replace(/[\s-]/g, '');
    if (!models.has(key)) models.set(key, label);
  }
  return models.size ? [...models.values()] : ['Not Specified'];
}

export function projectPeripherals(record) {
  const declared = [record.peripherals_sensors, record.peripherals, record.sensors]
    .flatMap(value => Array.isArray(value) ? value : typeof value === 'string' ? [value] : [])
    .filter(value => typeof value === 'string' && value.trim()).map(value => value.trim());
  if (Array.isArray(record.peripherals_sensors)) return declared.length ? declared : ['Not Specified'];
  const topics = record.topics_tools ?? record.tags ?? [];
  const hardware = record.hardware ?? record.hardware_requirements ?? [];
  const text = [record.long_name || record.name, record.description, ...topics, ...hardware, ...declared].join(' ');
  const rules = [
    ['Camera', /\bcamera\b|\bwebcam\b/i],
    ['Microphone', /\bmicrophone\b|\bmic\b/i],
    ['Speaker', /\bspeakers?\b/i],
    ['Ultrasonic Sensor', /\bultrasonic\b/i],
    ['Movement Sensor', /\bmovement sensor\b|\bmotion sensor\b/i],
    ['Accelerometer', /\baccelerometer\b/i],
    ['Gyroscope', /\bgyroscope\b/i],
    ['Temperature Sensor', /\btemperature sensor\b/i],
    ['LED Matrix', /\bled matrix\b/i],
  ];
  const detected = rules.filter(([, pattern]) => pattern.test(text)).map(([label]) => label);
  const extras = declared.filter(value => !rules.some(([, pattern]) => pattern.test(value)));
  const peripherals = [...new Set([...detected, ...extras])];
  return peripherals.length ? peripherals : ['Not Specified'];
}