#!/usr/bin/env python3
#===--update_readme_tables.py---------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
Auto-generate README tables from project.yaml files.
Discovers all project.yaml at 3-level depth and regenerates:
1. Main "Applications & Releases" table (platform × category grid)
2. Arduino-specific table (filtered by platforms containing "arduino")
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
import yaml
import subprocess
from collections import defaultdict


def find_project_yaml_files(repo_root: Path) -> List[Path]:
    """Find all project.yaml files at exactly 3-level depth."""
    project_files = []
    
    # Pattern: repo_root/level1/level2/project.yaml
    for level1 in repo_root.iterdir():
        if not level1.is_dir() or level1.name.startswith('.'):
            continue
        for level2 in level1.iterdir():
            if not level2.is_dir() or level2.name.startswith('.'):
                continue
            for level3 in level2.iterdir():
                if not level3.is_dir() or level3.name.startswith('.'):
                    continue
                project_yaml = level3 / 'project.yaml'
                if project_yaml.exists():
                    project_files.append(project_yaml)
    
    print(f"Γ£ô Found {len(project_files)} project.yaml files")
    return project_files


def get_last_commit_date(project_path: Path) -> str:
    """Get the last commit date for a project folder using git log."""
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%cs', '--', str(project_path)],
            capture_output=True,
            text=True,
            cwd=project_path.parent.parent.parent  # repo root
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()  # Returns YYYY-MM-DD
        else:
            # Fallback to file modification time
            from datetime import datetime
            mtime = project_path.stat().st_mtime
            return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
    except Exception:
        # Fallback to current date if git fails
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d')


def parse_project_metadata(yaml_path: Path, repo_root: Path) -> Optional[Dict]:
    """Parse a project.yaml file and extract metadata."""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data:
            print(f"ΓÜá Empty YAML: {yaml_path}")
            return None
        
        # Required fields
        if 'name' not in data:
            print(f"ΓÜá Missing 'name' field: {yaml_path}")
            return None
        
        if 'category' not in data or not isinstance(data['category'], list) or len(data['category']) < 2:
            print(f"ΓÜá Invalid 'category' field: {yaml_path}")
            return None
        
        # Extract path components (Category/Platform/ProjectName)
        # Get relative path from repo root
        try:
            rel_to_repo = yaml_path.relative_to(repo_root)
            # Path should be: Category/Platform/ProjectName/project.yaml
            parts = rel_to_repo.parts
            if len(parts) < 4:
                print(f"ΓÜá Invalid path structure: {yaml_path}")
                return None
            
            category_folder = parts[0]
            platform_folder = parts[1]
            project_folder = parts[2]
            
            # Build relative path for links
            rel_path = f"./{category_folder}/{platform_folder}/{project_folder}/"
        except ValueError:
            print(f"ΓÜá Could not compute relative path: {yaml_path}")
            return None
        
        # Get project folder path for git log
        project_dir_path = yaml_path.parent
        last_updated = get_last_commit_date(project_dir_path)
        
        metadata = {
            'name': data['name'],
            'description': data.get('description', ''),
            'category': data['category'][0],  # Main category (GenAI, CV_VR, etc.)
            'platform': data['category'][1],  # Platform (AI_PC, IoT-Robotics, etc.)
            'platforms': data.get('platforms', []),  # List of target platforms
            'tags': data.get('tags', []),
            'is_third_party': data.get('is_third_party', False),
            'path': rel_path,
            'yaml_path': str(yaml_path),
            'last_updated': last_updated
        }
        
        return metadata
        
    except yaml.YAMLError as e:
        print(f"Γ£ù YAML parse error in {yaml_path}: {e}")
        return None
    except Exception as e:
        print(f"Γ£ù Error processing {yaml_path}: {e}")
        return None


def normalize_category_name(category: str) -> str:
    """Map YAML category to README table column name."""
    mapping = {
        'GenAI': 'Generative AI',
        'CV_VR': 'CV & VR',
        '5G+AI': '5G + AI',
        'Others': 'Others',
    }
    return mapping.get(category, category)


def normalize_platform_name(platform: str) -> str:
    """Map YAML platform to README table row name."""
    mapping = {
        'AI_PC': 'AI PC',
        'IoT-Robotics': 'IoT-Robotics',
        'Android': 'Android Phones',
        'Connectivity': 'Connectivity',
        'CloudAI-Playground': 'CloudAI-Playground',
    }
    return mapping.get(platform, platform)


def generate_main_table(projects: List[Dict]) -> str:
    """Generate the main Applications & Releases table with uniform grey Shields.io badges."""
    
    # Filter out third-party projects
    filtered = [p for p in projects if not p['is_third_party']]
    
    # Define table structure with colors
    categories = [
        ('Generative AI', 'Generative AI', 'brightgreen'),
        ('CV & VR', 'CV & VR', 'blueviolet'),
        ('5G+AI', '5G + AI', 'red'),
        ('Others', 'Others', 'orange')
    ]
    
    platforms = [
        ('≡ƒÆ╗ AI PC', 'AI PC'),
        ('≡ƒöº IoT-Robotics', 'IoT-Robotics'),
        ('≡ƒô▒ Android Phones', 'Android Phones'),
        ('≡ƒîÉ Connectivity', 'Connectivity'),
        ('Γÿü∩╕Å CloudAI-Playground', 'CloudAI-Playground')
    ]
    
    # Build 2D grid: platform ├ù category
    grid = defaultdict(lambda: defaultdict(list))
    
    for proj in filtered:
        cat_name = normalize_category_name(proj['category'])
        plat_name = normalize_platform_name(proj['platform'])
        
        category_keys = [c[1] for c in categories]
        platform_keys = [p[1] for p in platforms]
        
        if cat_name in category_keys and plat_name in platform_keys:
            # Find the color for this category
            cat_color = next((c[2] for c in categories if c[1] == cat_name), 'blue')
            proj['category_color'] = cat_color
            grid[plat_name][cat_name].append(proj)
    
    # Sort projects within each cell alphabetically
    for plat in grid:
        for cat in grid[plat]:
            grid[plat][cat].sort(key=lambda p: p['name'].lower())
    
    # Generate HTML table with category-colored Shields.io badges
    lines = ['<table>']
    lines.append('  <tr>')
    lines.append('    <th align="center"><strong>Platforms</strong></th>')
    
    # Define color schemes for badges
    color_schemes = {
        'brightgreen': ('#28a745', '#d4edda'),
        'blueviolet': ('#6f42c1', '#e2d9f3'),
        'red': ('#dc3545', '#f8d7da'),
        'orange': ('#fd7e14', '#ffe5cc')
    }
    
    for cat_display, _, cat_color in categories:
        lines.append(f'    <th align="center"><strong>{cat_display}</strong></th>')
    lines.append('  </tr>')
    
    # Generate rows
    for idx, (plat_display, plat_key) in enumerate(platforms):
        lines.append('  <tr>')
        # Remove emoji from platform display and left-align
        plat_text = plat_display.split(' ', 1)[-1] if ' ' in plat_display else plat_display
        lines.append(f'    <td align="left"><strong>{plat_text}</strong></td>')
        
        for _, cat_key, cat_color in categories:
            projects_in_cell = grid[plat_key][cat_key]
            
            # Get light color for column
            color_schemes = {
                'brightgreen': ('#28a745', '#d4edda'),
                'blueviolet': ('#6f42c1', '#e2d9f3'),
                'red': ('#dc3545', '#f8d7da'),
                'orange': ('#fd7e14', '#ffe5cc')
            }
            _, light_color = color_schemes.get(cat_color, ('#6c757d', '#e9ecef'))
            
            # Apply banding by darkening odd rows
            hex_color = light_color.lstrip('#')
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            if idx % 2 == 1:
                r, g, b = int(r * 0.92), int(g * 0.92), int(b * 0.92)
            cell_bg = f'#{r:02x}{g:02x}{b:02x}'
            
            if projects_in_cell:
                links = []
                for proj in projects_in_cell:
                    # Create category-colored Shields.io badge (category color for name, grey for date)
                    badge_name = proj['name'].replace(' ', '_').replace('-', '--')
                    badge_date = proj['last_updated'].replace('-', '.')
                    cat_color_badge = proj.get('category_color', 'blue')
                    badge_url = f'https://img.shields.io/badge/{badge_name}-{badge_date}-grey?style=flat-square&labelColor={cat_color_badge}'
                    link = f'<a href="{proj["path"]}" title="{proj["description"]}">\n        <img src="{badge_url}" alt="{proj["name"]}"/>\n      </a>'
                    links.append(link)
                cell_content = '<br>\n      '.join(links)
                lines.append(f'    <td>\n      {cell_content}\n    </td>')
            else:
                lines.append(f'    <td align="center">—</td>')
        
        lines.append('  </tr>')
    
    lines.append('</table>')
    
    return '\n'.join(lines)


def is_arduino_project(platforms: List) -> bool:
    """Check if project targets Arduino platform."""
    if not platforms:
        return False
    
    # Normalize to list if single string
    if isinstance(platforms, str):
        platforms = [platforms]
    
    # Case-insensitive substring match for "arduino"
    for plat in platforms:
        if isinstance(plat, str) and 'arduino' in plat.lower():
            return True
    
    return False


def categorize_arduino_project(tags: List) -> str:
    """Categorize Arduino project into AI/IOT/Robotics based on tags.
    Priority order when tied: AI > IOT > Robotics"""
    tags_lower = [str(t).lower() for t in tags]
    
    # Simple heuristic based on keywords
    ai_keywords = ['ai', 'vision', 'detection', 'recognition', 'neural', 'model', 'inference']
    iot_keywords = ['iot', 'sensor', 'connectivity', 'mqtt', 'bluetooth', 'wifi']
    robotics_keywords = ['robot', 'motor', 'servo', 'actuator', 'control']
    
    ai_score = sum(1 for kw in ai_keywords if any(kw in tag for tag in tags_lower))
    iot_score = sum(1 for kw in iot_keywords if any(kw in tag for tag in tags_lower))
    robotics_score = sum(1 for kw in robotics_keywords if any(kw in tag for tag in tags_lower))
    
    # Find the maximum score
    max_score = max(ai_score, iot_score, robotics_score)
    
    # If no matches at all, default to AI
    if max_score == 0:
        return 'AI'
    
    # Return category with highest score, prioritizing AI > IOT > Robotics on ties
    if ai_score == max_score:
        return 'AI'
    elif iot_score == max_score:
        return 'IOT'
    else:
        return 'Robotics'


def generate_arduino_table(projects: List[Dict]) -> str:
    """Generate the Arduino Applications & Releases table with uniform grey Shields.io badges."""
    
    # Filter Arduino projects
    arduino_projects = [p for p in projects if is_arduino_project(p['platforms']) and not p['is_third_party']]
    
    if not arduino_projects:
        print("ΓÜá No Arduino projects found")
    
    # Categorize into AI/IOT/Robotics with specific colors
    categories = [
        ('AI', '🤖 AI', 'blue'),
        ('IOT', '🌐 IOT', 'cyan'),
        ('Robotics', '🤖 Robotics', 'purple')
    ]
    
    # Build grid by Arduino platform type
    platform_grid = defaultdict(lambda: defaultdict(list))
    arduino_platforms = set()
    
    for proj in arduino_projects:
        category = categorize_arduino_project(proj['tags'])
        # Find Arduino platform in the platforms list
        for platform in proj['platforms']:
            if 'arduino' in platform.lower():
                arduino_platforms.add(platform)
                platform_grid[platform][category].append(proj)
    
    # Sort platforms alphabetically
    sorted_platforms = sorted(arduino_platforms)
    
    # Sort within each category
    for plat in platform_grid:
        for cat in platform_grid[plat]:
            platform_grid[plat][cat].sort(key=lambda p: p['name'].lower())
    
    # Generate HTML table with category-colored Shields.io badges
    lines = [
        '<table>',
        '  <tr>',
        '    <th align="center"><strong>Platforms</strong></th>',
    ]
    
    # Define color schemes for badges
    color_schemes = {
        'blue': ('#007bff', '#cfe2ff'),
        'cyan': ('#17a2b8', '#cff4fc'),
        'purple': ('#6f42c1', '#e2d9f3')
    }
    
    for _, cat_display, cat_color in categories:
        lines.append(f'    <th align="center"><strong>{cat_display}</strong></th>')
    
    lines.append('  </tr>')
    
    # Generate row for each Arduino platform
    for arduino_platform in sorted_platforms:
        lines.append('  <tr>')
        # Format platform name (Arduino UNO-Q -> Arduino UNO Q)
        display_name = arduino_platform.replace('-', ' ')
        # Add product link if it's Arduino UNO Q
        if 'uno q' in display_name.lower() or 'uno-q' in arduino_platform.lower():
            lines.append(f'    <td align="left"><strong><a href="https://www.arduino.cc/product-uno-q">{display_name}</a></strong></td>')
        else:
            lines.append(f'    <td align="left"><strong>{display_name}</strong></td>')
        
        for cat_key, _, cat_color in categories:
            projects_in_cat = platform_grid[arduino_platform][cat_key]
            
            if projects_in_cat:
                links = []
                for proj in projects_in_cat:
                    # Create category-colored Shields.io badge (category color for name, grey for date)
                    badge_name = proj['name'].replace(' ', '_').replace('-', '--')
                    badge_date = proj['last_updated'].replace('-', '.')
                    badge_url = f'https://img.shields.io/badge/{badge_name}-{badge_date}-grey?style=flat-square&labelColor={cat_color}'
                    link = f'<a href="{proj["path"]}" title="{proj["description"]}">\n        <img src="{badge_url}" alt="{proj["name"]}"/>\n      </a>'
                    links.append(link)
                cell_content = '<br>\n      '.join(links)
                lines.append(f'    <td>\n      {cell_content}\n    </td>')
            else:
                lines.append(f'    <td align="center">—</td>')
        
        lines.append('  </tr>')
    
    lines.append('</table>')
    
    return '\n'.join(lines)


def update_readme(readme_path: Path, main_table: str, arduino_table: str) -> bool:
    """Update README.md with new tables. Returns True if changes were made."""
    
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Replace main table (find table after "## Applications & Releases")
    # Pattern: heading followed by optional blank lines, then <table>...</table>
    main_pattern = r'(## Applications & Releases\s*\n)(<table>.*?</table>)'
    main_replacement = r'\1' + main_table
    content = re.sub(main_pattern, main_replacement, content, flags=re.DOTALL)
    
    # Replace Arduino table (handle markdown link in heading)
    arduino_pattern = r'(## \[Arduino\]\(https://www\.arduino\.cc\) Applications & Releases\s*\n)(<table>.*?</table>)'
    arduino_replacement = r'\1' + arduino_table
    content = re.sub(arduino_pattern, arduino_replacement, content, flags=re.DOTALL)
    
    if content == original_content:
        print("Γ£ô No changes needed in README.md")
        return False
    
    # Write back
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Γ£ô README.md updated successfully")
    return True


def main():
    """Main execution function."""
    print("=" * 60)
    print("README Table Generator")
    print("=" * 60)
    
    # Find repo root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    print(f"Repository root: {repo_root}")
    
    # Find all project.yaml files
    yaml_files = find_project_yaml_files(repo_root)
    
    if not yaml_files:
        print("Γ£ù No project.yaml files found")
        sys.exit(1)
    
    # Parse all projects
    projects = []
    for yaml_path in yaml_files:
        metadata = parse_project_metadata(yaml_path, repo_root)
        if metadata:
            projects.append(metadata)
    
    print(f"Γ£ô Successfully parsed {len(projects)} projects")
    
    if not projects:
        print("Γ£ù No valid projects found")
        sys.exit(1)
    
    # Generate tables
    print("\nGenerating main table...")
    main_table = generate_main_table(projects)
    
    print("Generating Arduino table...")
    arduino_table = generate_arduino_table(projects)
    
    # Update README
    readme_path = repo_root / 'README.md'
    if not readme_path.exists():
        print(f"Γ£ù README.md not found at {readme_path}")
        sys.exit(1)
    
    print("\nUpdating README.md...")
    changed = update_readme(readme_path, main_table, arduino_table)
    
    print("\n" + "=" * 60)
    if changed:
        print("Γ£ô Tables updated successfully!")
    else:
        print("Γ£ô Tables are already up to date")
    print("=" * 60)


if __name__ == '__main__':
    main()
