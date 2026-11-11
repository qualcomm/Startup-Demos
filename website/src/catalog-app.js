//--catalog-app.js---------------------------------------------------------//
// Part of the Startup-Demos Project, under the MIT License                 //
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt      //
// for license information.                                                 //
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.       //
// SPDX-License-Identifier: MIT License                                     //
//--------------------------------------------------------------------------//

import { createIcons, Search, ArrowUpRight, ArrowRight, LayoutGrid, List, SlidersHorizontal, X, ChevronDown, ChevronLeft, ChevronRight, ScanEye, Monitor, Tags, CodeXml, Cpu, GitBranch, Box, Clock, RotateCcw, ExternalLink, BookOpen, Play, Check, LoaderCircle, Menu, Wrench } from 'lucide';
import { facetDefinitions, prepareCatalog, emptyState, selectProjects, facetOptions, readState, writeState } from './catalog.js';
import './catalog.css';
import './qualcomm-theme.css';
import './project-images.css';

const icons = { Search, ArrowUpRight, ArrowRight, LayoutGrid, List, SlidersHorizontal, X, ChevronDown, ChevronLeft, ChevronRight, ScanEye, Monitor, Tags, CodeXml, Cpu, GitBranch, Box, Clock, RotateCcw, ExternalLink, BookOpen, Play, Check, LoaderCircle, Menu, Wrench };
const icon = name => `<i data-lucide="${name}" aria-hidden="true"></i>`;
const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
const safeUrl = value => {
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : ''; } catch { return ''; }
};
const pageSize = 12;
const repository = __PUBLISHING_REPOSITORY__;
let state = readState(location.search);
let projects = [];
let draft = null;
let lastDetailTrigger = null;
const openGroups = new Set(['technology', 'platform']);
const optionQueries = {};
let loadController;

document.body.innerHTML = `
  <header class="topbar"><div class="topbar-inner"><a class="brand" href="https://www.qualcomm.com/" aria-label="Qualcomm homepage"><img src="${import.meta.env.BASE_URL}qualcomm-wordmark.png" alt="Qualcomm" width="128" height="24"></a><a class="catalog-brand" href="${escape(location.pathname)}">Startup Demos</a><nav class="repository-links" aria-label="Repository documents"><a class="button" href="${escape(repository.documentBase)}CONTRIBUTING.md" target="_blank" rel="noopener noreferrer">Contributing</a><a class="button" href="${escape(repository.documentBase)}CODE-OF-CONDUCT.md" target="_blank" rel="noopener noreferrer">Code of Conduct</a><a class="button" href="${escape(repository.documentBase)}LICENSE.txt" target="_blank" rel="noopener noreferrer">License</a></nav><a class="developer-resources" href="https://www.qualcomm.com/developer" target="_blank" rel="noopener noreferrer">Developer Resources ${icon('arrow-up-right')}</a></div></header>
  <main class="workspace">
    <section class="catalog-heading" id="catalog"><div><h1>Applications Built for Qualcomm Platforms</h1><p class="intro">Discover demos and reference applications across AI, computer vision, and connected devices. Find a project for your platform and explore the source code to start building.</p></div><div class="catalog-total"><span id="total-value">--</span><span>applications<br>to explore</span></div></section>
    <div class="searchbar"><label class="global-search">${icon('search')}<span class="sr-only">Search applications</span><input id="search" type="search" placeholder="Search applications, platforms, or tools" autocomplete="off"></label><span class="catalog-label">STARTUP DEMOS / CATALOG</span></div>
    <div class="catalog-layout"><aside id="desktop-filters" class="filter-sidebar" aria-label="Application filters"></aside>
      <section class="results" aria-label="Applications"><div class="results-toolbar"><div class="result-heading"><button id="open-filters" class="button mobile-filter">${icon('sliders-horizontal')} Filters <span id="mobile-count"></span></button><h2 id="result-count" role="status" aria-live="polite">Loading applications</h2></div><div class="view-tools"><label class="sort-label"><span class="sr-only">Sort applications</span><select id="sort"><option value="name">Name: A to Z</option><option value="name-desc">Name: Z to A</option><option value="updated">Recently updated</option></select></label><div class="view-switch" role="group" aria-label="Result view"><button data-view="grid" class="icon-button" title="Grid view" aria-label="Grid view">${icon('layout-grid')}</button><button data-view="list" class="icon-button" title="List view" aria-label="List view">${icon('list')}</button></div></div></div>
      <div id="active-filters" class="active-filters"></div><div id="catalog-container" class="project-grid" aria-busy="true">${Array.from({ length: 6 }, () => '<div class="skeleton" aria-hidden="true"></div>').join('')}</div><nav id="pagination" aria-label="Results pages"></nav></section>
    </div>
  </main>
  <footer class="site-footer"><span>Qualcomm Startup Demos</span><span>Built for exploration. Ready for development.</span><a href="${escape(repository.url)}" target="_blank" rel="noopener noreferrer">GitHub Repository ${icon('arrow-up-right')}</a></footer>
  <dialog id="filter-dialog" class="filter-dialog" aria-labelledby="filter-title"><div class="drawer-heading"><h2 id="filter-title">Filters</h2><button class="icon-button" data-close="filter-dialog" aria-label="Close filters" title="Close filters">${icon('x')}</button></div><div id="mobile-filters"></div><div class="drawer-actions"><button class="button" id="draft-clear">Clear all</button><button class="button primary" id="apply-filters">Show applications ${icon('arrow-right')}</button></div></dialog>
  <dialog id="details-dialog" class="details-dialog" aria-labelledby="detail-title"></dialog>`;

const byId = id => document.getElementById(id);
const refreshIcons = () => createIcons({ icons, attrs: { 'stroke-width': 1.7 } });
const selectedCount = current => Object.values(current.filters).flat().length;

function updateUrl(replace = false) {
  const query = writeState(state);
  const next = `${location.pathname}${query ? `?${query}` : ''}`;
  if (`${location.pathname}${location.search}` !== next) history[replace ? 'replaceState' : 'pushState']({}, '', next);
}

function commit(replace = false) {
  state.page = 1;
  updateUrl(replace);
  render();
}

function renderFilters() {
  for (const [id, current] of [['desktop-filters', state], ['mobile-filters', draft || state]]) {
    byId(id).innerHTML = `${id === 'desktop-filters' ? `<div class="filter-heading"><h2>${icon('sliders-horizontal')} Filters</h2><button class="text-button" data-clear>Reset</button></div>` : ''}${facetDefinitions.map(({ key, label, icon: facetIcon }) => {
      const options = facetOptions(projects, current, key);
      if (!options.length) return '';
      return `<details data-group="${key}" ${openGroups.has(key) || current.filters[key].length ? 'open' : ''}><summary>${icon(facetIcon)}<span>${label}</span>${current.filters[key].length ? `<span class="selection-count">${current.filters[key].length}</span>` : ''}${icon('chevron-down')}</summary><div class="facet-body">${options.length > 6 ? `<label class="facet-search">${icon('search')}<span class="sr-only">Search ${label}</span><input type="search" data-option-search="${key}" value="${escape(optionQueries[key] || '')}" placeholder="Find ${label.toLowerCase()}"></label>` : ''}<div class="facet-options">${options.map(({ label: option, count }) => `<label class="facet-option" ${option.toLowerCase().includes((optionQueries[key] || '').toLowerCase()) ? '' : 'hidden'}><input type="checkbox" data-facet="${key}" value="${escape(option)}" ${current.filters[key].includes(option) ? 'checked' : ''} ${!count && !current.filters[key].includes(option) ? 'disabled' : ''}><span>${escape(option)}</span><span class="option-count">${count}</span></label>`).join('')}</div></div></details>`;
    }).join('')}<div class="sidebar-note">${icon('git-branch')}<span>Open source. Open possibilities.<a href="${escape(repository.url)}" target="_blank" rel="noopener noreferrer">Explore the repository ${icon('arrow-up-right')}</a></span></div>`;
  }
}

function sourceUrl(project) {
  return `${repository.sourceBase}${project.repo_path.split('/').map(encodeURIComponent).join('/')}`;
}

function dateLabel(date) {
  const parsed = Date.parse(date);
  return parsed ? new Intl.DateTimeFormat('en', { month: 'short', year: 'numeric' }).format(parsed) : 'Date not available';
}

function projectPictureUrl(project) {
  return project.picture_url ? safeUrl(new URL(project.picture_url, new URL(import.meta.env.BASE_URL, location.href)).href) : '';
}

function card(project) {
  const type = project.facets.technology[0] || 'Application';
  const symbol = type.includes('Vision') ? 'scan-eye' : type.includes('Generative') ? 'cpu' : 'box';
  const color = type.includes('Vision') ? 'mint' : type.includes('Generative') ? 'rose' : 'blue';
  const pictureUrl = projectPictureUrl(project);
  const picture = pictureUrl ? `<img class="project-picture" src="${escape(pictureUrl)}" alt="${escape(project.name)} preview" loading="lazy">` : '';
  const thirdParty = project.is_third_party || (Array.isArray(project.category) && project.category.includes('3rdParty'));
  return `<article class="project-card" data-id="${escape(project.id)}">${picture}<div class="card-top"><span class="project-symbol ${color}">${icon(symbol)}</span><span class="category-label">${escape(type)}</span>${thirdParty ? '<span class="third-party">Third-party</span>' : ''}</div><h3><button data-detail="${escape(project.id)}">${escape(project.name)}</button></h3><p class="project-description">${escape(project.description)}</p><div class="platform-badges">${project.facets.platform.length ? project.facets.platform.slice(0, 3).map(platform => `<span>${icon('monitor')}${escape(platform)}</span>`).join('') : '<span>Platform not specified</span>'}${project.facets.platform.length > 3 ? `<span>+${project.facets.platform.length - 3}</span>` : ''}</div><div class="card-bottom"><span class="card-language">${icon('code-xml')}${escape(project.facets.language.slice(0, 2).join(', ') || 'Language not specified')}</span><button class="detail-button" data-detail="${escape(project.id)}" aria-label="View ${escape(project.name)} details">View application ${icon('arrow-up-right')}</button></div></article>`;
}

function render() {
  const focused = document.activeElement;
  const focusFacet = focused?.dataset?.facet;
  const focusValue = focused?.value;
  byId('search').value = state.query;
  byId('sort').value = state.sort;
  const filtered = selectProjects(projects, state);
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  state.page = Math.min(state.page, pages);
  updateUrl(true);
  byId('total-value').textContent = projects.length;
  byId('result-count').innerHTML = `<strong>${filtered.length}</strong> ${filtered.length === 1 ? 'application' : 'applications'} <span>of ${projects.length}</span>`;
  byId('mobile-count').textContent = selectedCount(state) || '';
  document.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === state.view)));
  const active = facetDefinitions.flatMap(({ key }) => state.filters[key].map(value => `<button class="active-chip" data-remove-facet="${key}" data-value="${escape(value)}">${escape(value)} ${icon('x')}<span class="sr-only">Remove filter</span></button>`));
  if (state.query) active.unshift(`<button class="active-chip" data-remove-query>Search: ${escape(state.query)} ${icon('x')}<span class="sr-only">Remove search</span></button>`);
  byId('active-filters').innerHTML = active.join('') + (active.length ? '<button class="text-button" data-clear>Clear all</button>' : '');
  const container = byId('catalog-container');
  container.className = state.view === 'list' ? 'project-grid list-view' : 'project-grid';
  container.setAttribute('aria-busy', 'false');
  container.innerHTML = filtered.length ? filtered.slice((state.page - 1) * pageSize, state.page * pageSize).map(card).join('') : `<div class="empty-state">${icon('search')}<h3>${projects.length ? 'No matching applications' : 'No applications yet'}</h3><p>${projects.length ? 'Try another search or clear your filters.' : 'The catalog does not contain any applications.'}</p>${projects.length ? `<button class="button" data-clear>${icon('rotate-ccw')} Clear all</button>` : ''}</div>`;
  byId('pagination').innerHTML = filtered.length ? `<span>Showing ${(state.page - 1) * pageSize + 1}-${Math.min(state.page * pageSize, filtered.length)} of ${filtered.length}</span><div><button class="icon-button" data-page="${state.page - 1}" aria-label="Previous page" title="Previous page" ${state.page === 1 ? 'disabled' : ''}>${icon('chevron-left')}</button>${Array.from({ length: pages }, (_, index) => `<button class="page-button" data-page="${index + 1}" ${state.page === index + 1 ? 'aria-current="page"' : ''}>${index + 1}</button>`).join('')}<button class="icon-button" data-page="${state.page + 1}" aria-label="Next page" title="Next page" ${state.page === pages ? 'disabled' : ''}>${icon('chevron-right')}</button></div>` : '';
  renderFilters();
  refreshIcons();
  if (focusFacet) {
    byId('desktop-filters').querySelectorAll('[data-facet]').forEach(input => {
      if (input.dataset.facet === focusFacet && input.value === focusValue) input.focus({ preventScroll: true });
    });
  }
}

function showDetails(id, trigger) {
  const project = projects.find(item => item.id === id);
  if (!project) return;
  lastDetailTrigger = trigger;
  const dialog = byId('details-dialog');
  const fields = [
    ['Technology', project.facets.technology.join(', ')], ['Platforms', project.facets.platform.join(', ')],
    ['Languages', project.facets.language.join(', ')], ['Hardware', project.facets.hardware.join(', ')],
    ['Software/Tools', project.facets.software_tools.join(', ')], ['AI Models', project.facets.models.join(', ')],
    ['Peripherals/Sensors', project.facets.peripherals.join(', ')],
    ['Topics/Tools', project.facets.tags.join(', ')],
    ['Setup time', project.estimated_setup_time], ['Difficulty', project.difficulty_level],
    ['Contributors', Array.isArray(project.developers) ? project.developers.join(', ') : ''],
    ['Related applications', Array.isArray(project.related_projects) ? project.related_projects.join(', ') : ''],
    ['Source', project.facets.ownership.join(', ')], ['Last updated', dateLabel(project.last_updated)], ['Repository path', project.repo_path],
  ];
  const links = [[project.demo_video, 'Watch demo', 'play'], [project.homepage, 'Homepage', 'external-link']].filter(([url]) => safeUrl(url));
  dialog.innerHTML = `<div class="detail-header"><span class="eyebrow">APPLICATION DETAILS</span><button class="icon-button" data-close="details-dialog" aria-label="Close details" title="Close details" autofocus>${icon('x')}</button></div><span class="project-symbol mint">${icon('box')}</span><h2 id="detail-title">${escape(project.name)}</h2><p class="detail-description">${escape(project.description)}</p><div class="detail-links"><a class="button primary" href="${escape(sourceUrl(project))}" target="_blank" rel="noopener noreferrer">${icon('code-xml')} View source ${icon('arrow-up-right')}</a>${links.map(([url, label, symbol]) => `<a class="button" href="${escape(safeUrl(url))}" target="_blank" rel="noopener noreferrer">${icon(symbol)}${label}</a>`).join('')}</div><dl class="detail-metadata">${fields.filter(([, value]) => value).map(([label, value]) => `<div><dt>${label}</dt><dd>${escape(value)}</dd></div>`).join('')}</dl>`;
  dialog.showModal();
  const pictureUrl = projectPictureUrl(project);
  if (pictureUrl) {
    const picture = document.createElement('img');
    picture.className = 'detail-picture';
    picture.src = pictureUrl;
    picture.alt = `${project.name} preview`;
    byId('detail-title').after(picture);
  }
  refreshIcons();
}

function clearAll() {
  state = { ...emptyState(), sort: state.sort, view: state.view };
  commit();
}

document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.hasAttribute('data-detail')) showDetails(button.dataset.detail, button);
  else if (button.dataset.close) byId(button.dataset.close).close();
  else if (button.hasAttribute('data-clear')) clearAll();
  else if (button.hasAttribute('data-remove-query')) { state.query = ''; commit(); }
  else if (button.dataset.removeFacet) {
    state.filters[button.dataset.removeFacet] = state.filters[button.dataset.removeFacet].filter(value => value !== button.dataset.value);
    commit();
  } else if (button.dataset.view) { state.view = button.dataset.view; updateUrl(); render(); }
  else if (button.dataset.page) {
    state.page = Number(button.dataset.page); updateUrl(); render();
    byId('result-count').scrollIntoView({ block: 'start' });
  }
});

document.addEventListener('change', event => {
  const input = event.target;
  if (input.dataset.facet) {
    const current = input.closest('#mobile-filters') ? draft : state;
    const key = input.dataset.facet;
    current.filters[key] = input.checked ? [...current.filters[key], input.value] : current.filters[key].filter(value => value !== input.value);
    if (current === state) commit();
    else { renderFilters(); refreshIcons(); byId('mobile-filters').querySelectorAll('[data-facet]').forEach(candidate => { if (candidate.dataset.facet === key && candidate.value === input.value) candidate.focus(); }); }
  }
});

document.addEventListener('input', event => {
  const input = event.target;
  if (!input.dataset.optionSearch) return;
  optionQueries[input.dataset.optionSearch] = input.value;
  input.closest('.facet-body').querySelectorAll('.facet-option').forEach(label => {
    label.hidden = !label.querySelector('input').value.toLowerCase().includes(input.value.toLowerCase());
  });
});

document.addEventListener('toggle', event => {
  const group = event.target.dataset?.group;
  if (group) event.target.open ? openGroups.add(group) : openGroups.delete(group);
}, true);

let searchTimer;
byId('search').addEventListener('input', event => {
  const query = event.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { state.query = query; commit(); }, 180);
});
byId('sort').addEventListener('change', event => { state.sort = event.target.value; commit(); });
byId('open-filters').addEventListener('click', () => {
  draft = structuredClone(state); renderFilters(); refreshIcons(); byId('filter-dialog').showModal();
});
byId('draft-clear').addEventListener('click', () => {
  draft = { ...emptyState(), sort: state.sort, view: state.view }; renderFilters(); refreshIcons();
});
byId('apply-filters').addEventListener('click', () => { state = draft; draft = null; byId('filter-dialog').close(); commit(); });
byId('filter-dialog').addEventListener('close', () => { draft = null; byId('open-filters').focus(); });
byId('details-dialog').addEventListener('close', () => lastDetailTrigger?.focus());
for (const dialog of document.querySelectorAll('dialog')) dialog.addEventListener('click', event => { if (event.target === dialog) { const rectangle = dialog.getBoundingClientRect(); if (event.clientX < rectangle.left || event.clientX > rectangle.right || event.clientY < rectangle.top || event.clientY > rectangle.bottom) dialog.close(); } });
window.addEventListener('popstate', () => { clearTimeout(searchTimer); state = readState(location.search); render(); });

async function load() {
  loadController?.abort();
  loadController = new AbortController();
  try {
    const response = await fetch(new URL(`${import.meta.env.BASE_URL}catalog.json`, location.href), { signal: loadController.signal });
    if (!response.ok) throw new Error(`Catalog request failed (${response.status})`);
    projects = prepareCatalog(await response.json());
    render();
  } catch (error) {
    if (error.name === 'AbortError') return;
    byId('result-count').textContent = 'Catalog unavailable';
    byId('catalog-container').setAttribute('aria-busy', 'false');
    byId('catalog-container').innerHTML = `<div class="empty-state">${icon('rotate-ccw')}<h3>Unable to load applications</h3><p>The catalog could not be loaded. Please try again.</p><button class="button" id="retry">${icon('rotate-ccw')} Try again</button></div>`;
    byId('retry').addEventListener('click', load);
    refreshIcons();
    console.error(error);
  }
}

refreshIcons();
load();