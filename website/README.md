# Project Catalog Website

The catalog discovers every application directory containing a `project.yaml` file. The YAML metadata drives application names, descriptions, filters, details, and the card image.

## Add or Update Project Metadata

Create or update `project.yaml` in the application directory. Keep values factual and based on the project README, source, and configuration. The website uses the `description` directly, so keep it at 200 characters or fewer. Use a project-local image for the mandatory `picture` field.

## Schema

### Required fields

| Field | Type | Meaning |
| --- | --- | --- |
| `long_name` | string | Human-readable display name, for example `Data Payload Monitor`. Do not put repository breadcrumb Markdown here. |
| `shortname` | string | GitHub/URL-friendly identifier, 10–20 characters, unique across projects. Use lowercase letters, digits, and hyphens. |
| `description` | string | Website card description, at most 200 characters. |
| `technology` | string array | Application technology areas, such as `Computer Vision & VR`, `Generative AI`, `Edge AI`, or `Other applications`. |
| `platforms` | string array | First item is one catalog group; later items, when applicable, are hardware platform/product names. |
| `hardware` | string array | Exact chipset or board silicon used. Use `[]` when unknown or not applicable. |
| `software_tools` | string array | Operating systems, SDKs, frameworks, and developer tools. Use `[]` when none are identified. |
| `ai_models` | string array | AI models used by the application. Use the most specific supported name; do not add labels such as “version unspecified.” |
| `topics_tools` | string array | Other searchable topics and technologies that are not listed in `software_tools`. |
| `peripherals_sensors` | string array | Exact physical peripherals and sensors used. Use `[]` when there are none or when the application only processes files. |
| `picture` | string | Path, relative to the project directory, to an existing image used on the website. |

### Platform groups and mappings

Use exactly one group as the first `platforms` entry:

- `AI PC`
- `IoT-Robotics`
- `Android Phones`
- `CloudAI-Playground`
- `Connectivity` (reserved; currently no project is assigned to it)

Add the applicable hardware platform name after the group. Keep platform names consistent with these mappings:

| Platform | Hardware value | Software/tools to include |
| --- | --- | --- |
| Snapdragon X Elite | `Snapdragon X Elite` | `Windows` |
| Arduino UNO Q | `QRB2210` | `Linux` |
| RB3 Gen2 | `QCS6490` | `Linux`, `Ubuntu` |
| Radxa Dragon Q6A | chipset only when confirmed | `Linux`, `Ubuntu` |
| IQ-9075 Evaluation Kit | `IQ-9075` | `Linux`, `Ubuntu` |
| VENTUNO Q | `IQ-8275` | `Linux`, `Ubuntu` |
| AIC100 Ultra | `AIC100 Ultra` | `Linux` |
| Android Phones | leave hardware empty | `Android` |

For `QCS9075` evidence, use hardware `IQ-9075` and platform `IQ-9075 Evaluation Kit`. For `QCS8275` evidence, use hardware `IQ-8275` and platform `VENTUNO Q`. Do not add a duplicate IQ platform when the project already has an IQ platform entry. Use the spelling `VENTUNO Q` consistently.

Put `Qualcomm AI Hub` and `Edge Impulse` under `software_tools`, not `topics_tools`. Operating systems belong in `software_tools` as well. Keep `ai_models` for model names, not software frameworks.

### Optional fields

| Field | Type | Meaning |
| --- | --- | --- |
| `estimated_setup_time` | string | Evidence-based setup estimate, for example `15 minutes`. |
| `difficulty_level` | string | Suggested learning/setup level, such as `beginner`, `intermediate`, or `advanced`. |
| `related_projects` | string array | Repository-relative project paths for clearly related applications. |
| `homepage` | string | Include only when the project has a running demo application. |
| `demo_video` | string | Optional link to a project demo video. |

Do not add `status`, `license`, `is_third_party`, or `docs` fields to this schema. The repository README is the documentation source. The website build generates repository paths, source links, detected languages, contributors, source affiliation, and last-updated date; do not author those generated values.

## Example

```yaml
long_name: Data Payload Monitor
shortname: data-payload-monitor
description: Simulates sensor data, processes it on RB3 Gen2, and visualizes IoT metrics.
technology:
  - Other applications
platforms:
  - IoT-Robotics
  - RB3 Gen2
hardware:
  - QCS6490
software_tools:
  - Linux
  - Ubuntu
  - Streamlit
ai_models: []
topics_tools:
  - IoT
  - Monitoring
  - Real-time
peripherals_sensors: []
picture: Images/rb3_gen2_hms_sensor_dashboard.gif
estimated_setup_time: 15 minutes
difficulty_level: beginner
related_projects: []
```

## Validation

Before submitting, confirm that the YAML parses, the `shortname` is unique and 10–20 characters long, the description is no longer than 200 characters, the picture exists in the project directory, and platform/hardware/model/peripheral values are supported by project evidence.