//--main.js-----------------------------------------------------------------//
// Part of the Startup-Demos Project, under the MIT License                 //
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt      //
// for license information.                                                 //
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.       //
// SPDX-License-Identifier: MIT License                                     //
//--------------------------------------------------------------------------//

import '@picocss/pico';
import './style.css';

// HTML escape helper to prevent XSS
function escapeHtml(unsafe) {
  if (typeof unsafe !== 'string') return '';
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

const searchInput = document.getElementById('search-input');
const tagFiltersContainer = document.getElementById('tag-filters');
const platformFiltersContainer = document.getElementById('platform-filters');
const catalogContainer = document.getElementById('catalog-container');
const loadingIndicator = document.getElementById('loading');

let projects = [];
let allTags = new Set();
let allPlatforms = new Set();
let activeTagFilters = new Set();
let activePlatformFilters = new Set();

// Initialize sticky note style on page load
function initializeStickyNotes() {
  document.querySelectorAll('.last-updated-sticky').forEach(el => {
    // Apply gray minimal style with transparency
    el.style.background = "#9e9e9e";
    el.style.opacity = "0.6";
    el.style.fontSize = "0.45rem";
    el.style.padding = "0.25rem 0.4rem 0.25rem 0.4rem";
    el.style.clipPath = "polygon(0 0, 95% 0, 97% 50%, 95% 100%, 0 100%)";
  });
}

// Fetch and process data
async function loadProjects() {
  try {
    // Use Vite's built-in BASE_URL which matches the base in vite.config.js
    const response = await fetch(`${import.meta.env.BASE_URL}catalog.json`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    
    // Process projects to handle multiple categories
    const processedProjects = [];
    data.forEach(project => {
      project.category.forEach(category => {
        processedProjects.push({ ...project, primaryCategory: category });
      });
      if (project.tags) {
        project.tags.forEach(tag => allTags.add(tag));
      }
      if (project.platforms) {
        project.platforms.forEach(platform => allPlatforms.add(platform));
      }
    });

    projects = processedProjects;
    
    render();
    setupFilters();
  } catch (error) {
    console.error("Failed to load projects:", error);
    catalogContainer.innerHTML = '<p>Error loading projects. See console for details.</p>';
  } finally {
    loadingIndicator.style.display = 'none';
    document.getElementById('app-content').style.display = 'block';
    
    // Initialize sticky notes with final style
    initializeStickyNotes();
  }
}

// Render projects grouped by category
function render() {
  const query = searchInput.value.toLowerCase();
  
  const filteredProjects = projects.filter(p => {
    const matchesSearch = p.name.toLowerCase().includes(query) || p.description.toLowerCase().includes(query);
    const matchesTagFilters = activeTagFilters.size === 0 || (p.tags && p.tags.some(tag => activeTagFilters.has(tag)));
    const matchesPlatformFilters = activePlatformFilters.size === 0 || (p.platforms && p.platforms.some(platform => activePlatformFilters.has(platform)));
    return matchesSearch && matchesTagFilters && matchesPlatformFilters;
  });

  const groupedByCategory = filteredProjects.reduce((acc, project) => {
    const category = project.primaryCategory;
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(project);
    return acc;
  }, {});

  catalogContainer.innerHTML = ''; // Clear previous results

  const sortedCategories = Object.keys(groupedByCategory).sort((a, b) => {
    // Always put "3rdParty" at the end
    if (a === '3rdParty') return 1;
    if (b === '3rdParty') return -1;
    return a.localeCompare(b);
  });

  if (sortedCategories.length === 0) {
    catalogContainer.innerHTML = '<p>No projects found matching your criteria.</p>';
    return;
  }

  for (const category of sortedCategories) {
    const categorySection = document.createElement('section');
    // Format category name: replace underscores with spaces, special case for CV_VR
    let displayCategory = category;
    if (category === 'CV_VR') {
      displayCategory = 'CV and VR';
    } else {
      displayCategory = category.replace(/_/g, ' ');
    }
    categorySection.innerHTML = `<h2>${escapeHtml(displayCategory)}</h2>`;
    const articleGrid = document.createElement('div');
    articleGrid.className = 'grid';

    groupedByCategory[category].forEach(project => {
      const article = document.createElement('article');
      
      let tagsHtml = '';
      // Add platforms first as platform tags
      if (project.platforms) {
        tagsHtml += project.platforms.map(p => `<span class="tag platform-tag">${escapeHtml(p)}</span>`).join(' ');
      }
      // Then add regular tags
      if (project.tags) {
        tagsHtml += ' ' + project.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ');
      }

      let teamHtml = '';
      if (project.team) {
        teamHtml = `<p><strong>Team:</strong> ${escapeHtml(project.team)}</p>`;
      }

      let hardwareHtml = '';
      if (project.hardware_requirements && project.hardware_requirements.length > 0) {
        hardwareHtml = `<p><strong>Hardware:</strong> ${project.hardware_requirements.map(escapeHtml).join(', ')}</p>`;
      }

      let setupTimeHtml = '';
      if (project.estimated_setup_time) {
        setupTimeHtml = `<p><strong>Setup Time:</strong> ${escapeHtml(project.estimated_setup_time)}</p>`;
      }

      let relatedHtml = '';
      if (project.related_projects && project.related_projects.length > 0) {
        relatedHtml = `<p><strong>Related:</strong> ${project.related_projects.map(escapeHtml).join(', ')}</p>`;
      }

      let thirdPartyBadge = '';
      if (project.is_third_party) {
        thirdPartyBadge = '<span class="third-party-stamp"></span>';
      }

      let statusBadge = '';
      if (project.status) {
        const statusClass = escapeHtml(project.status.toLowerCase().replace(/\s+/g, '-'));
        statusBadge = `<span class="badge status-${statusClass}">${escapeHtml(project.status)}</span>`;
      }

      let difficultyBadge = '';
      if (project.difficulty_level) {
        const diffClass = escapeHtml(project.difficulty_level.toLowerCase());
        difficultyBadge = `<span class="badge difficulty-${diffClass}">${escapeHtml(project.difficulty_level)}</span>`;
      }

      // Determine base URL and org based on hostname
      const isPublic = window.location.hostname.endsWith('github.io');
      const repoBaseUrl = isPublic 
        ? 'https://github.com/qualcomm/Startup-Demos/tree/main/' 
        : 'https://github.qualcomm.com/Innovationlab/qilab_platform_apps2/tree/main/';

      let repoUrl = '';
      let headerContent = '';
      if (project.repo_path) {
        repoUrl = repoBaseUrl + encodeURI(project.repo_path);
        headerContent = `<a href="${escapeHtml(repoUrl)}" target="_blank" style="text-decoration: none; color: inherit;"><strong>${escapeHtml(project.name)} ↗</strong></a>`;
      } else {
        headerContent = `<strong>${escapeHtml(project.name)}</strong>`;
      }

      let stickyNote = '';
      if (project.last_updated) {
        stickyNote = `<div class="last-updated-sticky">Last updated: ${escapeHtml(project.last_updated)}</div>`;
      }

      let linksHtml = '';
      if (project.homepage) {
        linksHtml += `<a href="${escapeHtml(project.homepage)}" target="_blank">🌐 Homepage</a>`;
      }
      if (project.docs) {
        linksHtml += ` <a href="${escapeHtml(project.docs)}" target="_blank">📖 Docs</a>`;
      }
      if (project.demo_video) {
        linksHtml += ` <a href="${escapeHtml(project.demo_video)}" target="_blank">▶️ Demo Video</a>`;
      }

      article.innerHTML = `
        <header>${headerContent} ${thirdPartyBadge} ${statusBadge} ${difficultyBadge}</header>
        ${stickyNote}
        <div class="card-body">
          <p>${escapeHtml(project.description)}</p>${teamHtml}${hardwareHtml}${setupTimeHtml}${relatedHtml}
        </div>
        <div class="card-meta">
          <div class="card-meta-langs">${project.languages && project.languages.length > 0 ? `&lt;/&gt; ${project.languages.map(escapeHtml).join(', ')}` : ''}</div>
          <div class="card-meta-authors">${project.developers && project.developers.length > 0 ? `By: ${project.developers.map(escapeHtml).join(', ')}` : ''}</div>
        </div>
        <footer>
          <div class="tags">${tagsHtml}</div>
          <div class="links">${linksHtml}</div>
        </footer>
      `;
      articleGrid.appendChild(article);
    });
    categorySection.appendChild(articleGrid);
    catalogContainer.appendChild(categorySection);
  }
  
  // Reapply sticky note styles after DOM update
  initializeStickyNotes();
}

// Setup filter buttons
function setupFilters() {
  // Platform filters
  if (allPlatforms.size > 0) {
    platformFiltersContainer.innerHTML = '<div class="filter-section"><div class="filter-header"><span class="filter-label">🖥️ Platforms</span><span class="clear-filter">⟲</span></div><div class="filter-buttons"></div></div>';
    const platformContainer = platformFiltersContainer.querySelector('.filter-buttons');
    const sortedPlatforms = Array.from(allPlatforms).sort();
    
    // Add clear button functionality
    const clearBtn = platformFiltersContainer.querySelector('.clear-filter');
    clearBtn.onclick = () => {
      activePlatformFilters.clear();
      platformContainer.querySelectorAll('button').forEach(btn => btn.classList.remove('active'));
      render();
    };
    
    sortedPlatforms.forEach(platform => {
      const button = document.createElement('button');
      button.textContent = platform;
      button.dataset.platform = platform;
      button.onclick = () => {
        if (activePlatformFilters.has(platform)) {
          activePlatformFilters.delete(platform);
          button.classList.remove('active');
        } else {
          activePlatformFilters.add(platform);
          button.classList.add('active');
        }
        render();
      };
      platformContainer.appendChild(button);
    });
  }

  // Tag filters
  if (allTags.size > 0) {
    tagFiltersContainer.innerHTML = '<div class="filter-section"><div class="filter-header"><span class="filter-label">📂 Categories</span><span class="clear-filter">⟲</span></div><div class="filter-buttons"></div></div>';
    const tagContainer = tagFiltersContainer.querySelector('.filter-buttons');
    const sortedTags = Array.from(allTags).sort();
    
    // Add clear button functionality
    const clearBtn = tagFiltersContainer.querySelector('.clear-filter');
    clearBtn.onclick = () => {
      activeTagFilters.clear();
      tagContainer.querySelectorAll('button').forEach(btn => btn.classList.remove('active'));
      render();
    };
    
    sortedTags.forEach(tag => {
      const button = document.createElement('button');
      button.textContent = tag;
      button.dataset.tag = tag;
      button.onclick = () => {
        if (activeTagFilters.has(tag)) {
          activeTagFilters.delete(tag);
          button.classList.remove('active');
        } else {
          activeTagFilters.add(tag);
          button.classList.add('active');
        }
        render();
      };
      tagContainer.appendChild(button);
    });
  }
}


// Event Listeners
searchInput.addEventListener('input', render);

// Initial Load
loadProjects();
