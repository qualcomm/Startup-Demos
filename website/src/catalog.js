import { generatedTopics, projectPeripherals, projectModels } from './classification.js';

export const facetDefinitions = [
  { key: 'technology', label: 'Technology', icon: 'scan-eye' },
  { key: 'platform', label: 'Platforms', icon: 'monitor' },
  { key: 'hardware', label: 'Hardware', icon: 'cpu' },
  { key: 'software_tools', label: 'Software/Tools', icon: 'wrench' },
  { key: 'models', label: 'AI Models', icon: 'box' },
  { key: 'tags', label: 'Topics/Tools', icon: 'tags' },
  { key: 'peripherals', label: 'Peripherals/Sensors', icon: 'cpu' },
  { key: 'language', label: 'Language', icon: 'code-xml' },
  { key: 'ownership', label: 'Source', icon: 'git-branch' },
];

const aliases = new Map([
  ['aic100ultra', 'AIC100 Ultra'],
  ['object detection', 'Object Detection'],
  ['mediapipe', 'MediaPipe'],
  ['ai_pc', 'AI PC'],
  ['ai pc', 'AI PC'],
]);

export function canonical(value) {
  const trimmed = String(value).trim().replace(/\s+/g, ' ');
  return aliases.get(trimmed.toLowerCase().replace(/^aic100 ultra$/, 'aic100ultra')) || trimmed;
}

const platformCategories = new Set(['AI_PC', 'Android', 'IoT-Robotics', 'CloudAI-Playground', 'Connectivity']);
const technologyLabels = { CV_VR: 'Computer Vision & VR', GenAI: 'Generative AI', 'Edge-AI': 'Edge AI', '5G+AI': '5G & AI', Others: 'Other applications' };
const values = value => Array.isArray(value) ? [...new Set(value.filter(item => typeof item === 'string').map(canonical))] : [];

export function prepareCatalog(records) {
  const identities = new Set();
  return records.map(record => {
    const name = record.long_name || record.name;
    if (!record.repo_path || identities.has(record.repo_path)) {
      throw new Error(`Missing or duplicate application path: ${record.repo_path || name}`);
    }
    identities.add(record.repo_path);
    const categories = values(record.technology ?? record.category);
    const rawCategories = Array.isArray(record.category) ? record.category : [];
    const technology = Array.isArray(record.technology)
      ? values(record.technology)
      : rawCategories.filter(category => !platformCategories.has(category) && category !== '3rdParty')
        .map(category => technologyLabels[category] || canonical(category));
    const topicValues = values(record.topics_tools ?? record.tags);
    const facets = {
      technology: [...new Set(technology)],
      platform: values(record.platforms),
      software_tools: values(record.software_tools),
      tags: Array.isArray(record.topics_tools) ? topicValues : values([...topicValues, ...generatedTopics({ ...record, name })]),
      language: values(record.languages),
      hardware: values(record.hardware ?? record.hardware_requirements),
      models: projectModels(record),
      peripherals: projectPeripherals(record),
      ownership: values(record.source_affiliations).filter(source => ['Qualcomm', 'Third Party', 'Not Specified'].includes(source)),
    };
    if (!facets.ownership.length) facets.ownership = ['Not Specified'];
    return { ...record, name, id: record.repo_path, facets, searchText: [name, record.description, ...categories, ...Object.values(facets).flat()].join(' ').toLowerCase() };
  });
}

export function emptyState() {
  return { query: '', sort: 'name', view: 'grid', page: 1, filters: Object.fromEntries(facetDefinitions.map(({ key }) => [key, []])) };
}

export function matches(project, state, ignoredFacet) {
  const terms = state.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return terms.every(term => project.searchText.includes(term)) && facetDefinitions.every(({ key }) =>
    key === ignoredFacet || !state.filters[key].length || state.filters[key].some(value => project.facets[key].includes(value)));
}

export function selectProjects(projects, state) {
  const compareName = (first, second) => first.name.localeCompare(second.name) || first.id.localeCompare(second.id);
  return projects.filter(project => matches(project, state)).sort((first, second) => {
    if (state.sort === 'updated') {
      const difference = (Date.parse(second.last_updated) || 0) - (Date.parse(first.last_updated) || 0);
      return difference || compareName(first, second);
    }
    return state.sort === 'name-desc' ? -compareName(first, second) : compareName(first, second);
  });
}

export function facetOptions(projects, state, key) {
  const labels = new Set([...projects.flatMap(project => project.facets[key]), ...state.filters[key]]);
  const contextual = projects.filter(project => matches(project, state, key));
  return [...labels].sort((first, second) => first.localeCompare(second)).map(label => ({
    label, count: contextual.filter(project => project.facets[key].includes(label)).length,
  }));
}

export function readState(search) {
  const parameters = new URLSearchParams(search);
  const state = emptyState();
  state.query = parameters.get('q') || '';
  if (['name', 'name-desc', 'updated'].includes(parameters.get('sort'))) state.sort = parameters.get('sort');
  if (parameters.get('view') === 'list') state.view = 'list';
  const page = Number(parameters.get('page'));
  if (Number.isSafeInteger(page) && page > 0) state.page = page;
  for (const { key } of facetDefinitions) state.filters[key] = [...new Set(parameters.getAll(key).map(canonical))];
  return state;
}

export function writeState(state) {
  const parameters = new URLSearchParams();
  if (state.query) parameters.set('q', state.query);
  if (state.sort !== 'name') parameters.set('sort', state.sort);
  if (state.view !== 'grid') parameters.set('view', state.view);
  if (state.page !== 1) parameters.set('page', state.page);
  for (const { key } of facetDefinitions) for (const value of state.filters[key]) parameters.append(key, value);
  return parameters.toString();
}