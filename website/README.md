# Project Catalog Website

This website automatically discovers and displays all projects in the repository that contain a `project.yaml` file.

## How to Add Your Project

1. Create a file named `project.yaml` in your project's root directory
2. Add the required fields (see schema below)
3. Commit and push to the `main` branch
4. The website will automatically include your project

## `project.yaml` Schema

### Required Fields

- `name` (string): Project display name
- `description` (string): Brief project description
- `category` (array of strings): Categories the project belongs to (e.g., ["CV_VR"], ["GenAI", "5G+AI"])

### Optional Fields

- `platforms` (array of strings): Supported platforms (e.g., ["AI PC"], ["Android", "Cloud"])
- `tags` (array of strings): Tags for filtering (e.g., ["Computer Vision", "Deep Learning"])
- `team` (string): Development team name
- `is_third_party` (boolean): Set to `true` for third-party applications
- `license` (string): Software license (e.g., "MIT", "Apache 2.0")
- `status` (string): Project status (e.g., "stable", "experimental", "beta")
- `hardware_requirements` (array of strings): Required hardware
- `difficulty_level` (string): Complexity level ("beginner", "intermediate", "advanced")
- `estimated_setup_time` (string): Setup time estimate (e.g., "15 minutes")
- `demo_video` (string): Demo video URL
- `related_projects` (array of strings): Related project names
- `homepage` (string): Project homepage URL
- `docs` (string): Documentation URL
- `repo_path` (string): Relative path from repository root (for monorepo projects)

### Example

```yaml
name: "Image Classification"
description: "Real-time image classification using ONNX models"
category: ["CV_VR"]
platforms: ["AI PC"]
tags: ["Computer Vision", "Deep Learning", "ONNX"]
license: "MIT"
status: "stable"
difficulty_level: "beginner"
estimated_setup_time: "15 minutes"
```

That's it! The catalog will automatically display:
- Your project name and description
- Platform badges
- Programming languages (auto-detected)
- Contributors (from git history)
- Last updated date (from git log)



