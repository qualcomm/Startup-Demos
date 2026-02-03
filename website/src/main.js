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
    const heading = document.createElement('h2');
    heading.textContent = displayCategory;
    categorySection.appendChild(heading);
    const articleGrid = document.createElement('div');
    articleGrid.className = 'grid';

    groupedByCategory[category].forEach(project => {
      const article = document.createElement('article');
      
      const tagsArray = [];
      // Add platforms first as platform tags
      if (project.platforms) {
        project.platforms.forEach(p => {
          const tagSpan = document.createElement('span');
          tagSpan.className = 'tag platform-tag';
          tagSpan.textContent = p;
          tagsArray.push(tagSpan);
        });
      }
      // Then add regular tags
      if (project.tags) {
        project.tags.forEach(tag => {
          const tagSpan = document.createElement('span');
          tagSpan.className = 'tag';
          tagSpan.textContent = tag;
          tagsArray.push(tagSpan);
        });
      }



      let thirdPartyBadge = null;
      if (project.is_third_party) {
        thirdPartyBadge = document.createElement('span');
        thirdPartyBadge.className = 'third-party-stamp';
      }

      let statusBadge = null;
      if (project.status) {
        const statusClass = project.status.toLowerCase().replace(/\s+/g, '-');
        statusBadge = document.createElement('span');
        statusBadge.className = `badge status-${statusClass}`;
        statusBadge.textContent = project.status;
      }

      let difficultyBadge = null;
      if (project.difficulty_level) {
        const diffClass = project.difficulty_level.toLowerCase();
        difficultyBadge = document.createElement('span');
        difficultyBadge.className = `badge difficulty-${diffClass}`;
        difficultyBadge.textContent = project.difficulty_level;
      }

      // Determine base URL and org based on hostname
      const isPublic = window.location.hostname.endsWith('github.io');
      const repoBaseUrl = isPublic 
        ? 'https://github.com/qualcomm/Startup-Demos/tree/main/' 
        : 'https://github.qualcomm.com/Innovationlab/qilab_platform_apps2/tree/main/';

      let repoUrl = '';
      if (project.repo_path) {
        repoUrl = repoBaseUrl + encodeURI(project.repo_path);
      }

      let stickyNote = '';
      if (project.last_updated) {
        stickyNote = `<div class="last-updated-sticky">Last updated: ${escapeHtml(project.last_updated)}</div>`;
      }

      const linksArray = [];
      if (project.homepage) {
        const homeLink = document.createElement('a');
        homeLink.href = project.homepage;
        homeLink.target = '_blank';
        homeLink.textContent = '🌐 Homepage';
        linksArray.push(homeLink);
      }
      if (project.docs) {
        const docsLink = document.createElement('a');
        docsLink.href = project.docs;
        docsLink.target = '_blank';
        docsLink.textContent = '📖 Docs';
        linksArray.push(docsLink);
      }
      if (project.demo_video) {
        const demoLink = document.createElement('a');
        demoLink.href = project.demo_video;
        demoLink.target = '_blank';
        demoLink.textContent = '▶️ Demo Video';
        linksArray.push(demoLink);
      }

      // Build article using safe DOM methods
      const header = document.createElement('header');
      
      // Add title (link or plain text)
      if (project.repo_path && repoUrl) {
        const titleLink = document.createElement('a');
        titleLink.href = repoUrl;
        titleLink.target = '_blank';
        titleLink.style.textDecoration = 'none';
        titleLink.style.color = 'inherit';
        const strong = document.createElement('strong');
        strong.textContent = `${project.name} ↗`;
        titleLink.appendChild(strong);
        header.appendChild(titleLink);
      } else {
        const strong = document.createElement('strong');
        strong.textContent = project.name;
        header.appendChild(strong);
      }
      
      // Add badges
      if (thirdPartyBadge) {
        header.appendChild(document.createTextNode(' '));
        header.appendChild(thirdPartyBadge);
      }
      if (statusBadge) {
        header.appendChild(document.createTextNode(' '));
        header.appendChild(statusBadge);
      }
      if (difficultyBadge) {
        header.appendChild(document.createTextNode(' '));
        header.appendChild(difficultyBadge);
      }
      
      article.appendChild(header);

      if (stickyNote) {
        const stickyDiv = document.createElement('div');
        stickyDiv.className = 'last-updated-sticky';
        stickyDiv.textContent = `Last updated: ${project.last_updated}`;
        article.appendChild(stickyDiv);
      }

      const cardBody = document.createElement('div');
      cardBody.className = 'card-body';
      const descPara = document.createElement('p');
      descPara.textContent = project.description;
      cardBody.appendChild(descPara);
      
      if (project.team) {
        const teamPara = document.createElement('p');
        const teamStrong = document.createElement('strong');
        teamStrong.textContent = 'Team:';
        teamPara.appendChild(teamStrong);
        teamPara.appendChild(document.createTextNode(' ' + project.team));
        cardBody.appendChild(teamPara);
      }
      
      if (project.hardware_requirements && project.hardware_requirements.length > 0) {
        const hwPara = document.createElement('p');
        const hwStrong = document.createElement('strong');
        hwStrong.textContent = 'Hardware:';
        hwPara.appendChild(hwStrong);
        hwPara.appendChild(document.createTextNode(' ' + project.hardware_requirements.join(', ')));
        cardBody.appendChild(hwPara);
      }
      
      if (project.estimated_setup_time) {
        const setupPara = document.createElement('p');
        const setupStrong = document.createElement('strong');
        setupStrong.textContent = 'Setup Time:';
        setupPara.appendChild(setupStrong);
        setupPara.appendChild(document.createTextNode(' ' + project.estimated_setup_time));
        cardBody.appendChild(setupPara);
      }
      
      if (project.related_projects && project.related_projects.length > 0) {
        const relPara = document.createElement('p');
        const relStrong = document.createElement('strong');
        relStrong.textContent = 'Related:';
        relPara.appendChild(relStrong);
        relPara.appendChild(document.createTextNode(' ' + project.related_projects.join(', ')));
        cardBody.appendChild(relPara);
      }
      
      article.appendChild(cardBody);

      const cardMeta = document.createElement('div');
      cardMeta.className = 'card-meta';
      const metaLangs = document.createElement('div');
      metaLangs.className = 'card-meta-langs';
      if (project.languages && project.languages.length > 0) {
        metaLangs.textContent = `</> ${project.languages.join(', ')}`;
      }
      const metaAuthors = document.createElement('div');
      metaAuthors.className = 'card-meta-authors';
      if (project.developers && project.developers.length > 0) {
        metaAuthors.textContent = `By: ${project.developers.join(', ')}`;
      }
      cardMeta.appendChild(metaLangs);
      cardMeta.appendChild(metaAuthors);
      article.appendChild(cardMeta);

      const footer = document.createElement('footer');
      const tagsDiv = document.createElement('div');
      tagsDiv.className = 'tags';
      tagsArray.forEach((tagSpan, index) => {
        if (index > 0) tagsDiv.appendChild(document.createTextNode(' '));
        tagsDiv.appendChild(tagSpan);
      });
      const linksDiv = document.createElement('div');
      linksDiv.className = 'links';
      linksArray.forEach((link, index) => {
        if (index > 0) linksDiv.appendChild(document.createTextNode(' '));
        linksDiv.appendChild(link);
      });
      footer.appendChild(tagsDiv);
      footer.appendChild(linksDiv);
      article.appendChild(footer);

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
