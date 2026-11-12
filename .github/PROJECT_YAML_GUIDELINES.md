# Project YAML Guidelines

Errors were found in your Project.yaml file. Please correct the project file using the sample and mandatory fields below.

## Example Project YAML

```yaml
long_name: Example Vision Demo
shortname: example-vision-demo
description: Detects objects using a local camera.
technology: [Computer Vision & VR]
platforms: [IoT-Robotics, IQ-9075 Evaluation Kit]
hardware: [IQ-9075]
software_tools: [Linux, Ubuntu, Qualcomm AI Hub]
ai_models: [YOLO]
topics_tools: [Object Detection]
peripherals_sensors: [Camera]
picture: Images/inference_result.png
```

## Mandatory Fields

| Field | Accepted Values |
| --- | --- |
| `long_name` | Display-name string; no length limit. |
| `shortname` | String, 10-20 characters. |
| `description` | String, at most 200 characters. |
| `technology` | Array: `Computer Vision & VR`, `Generative AI`, `Other applications`, `Connectivity`. |
| `platforms` | Array: `AI PC`, `IoT-Robotics`, `Android Phones`, `CloudAI-Playground`, `Connectivity`, `AIC100 Ultra`, `Arduino UNO Q`, `IQ-9075 Evaluation Kit`, `RB3 Gen2`, `Radxa Dragon Q6A`, `Snapdragon X Elite`, `VENTUNO Q`. |
| `hardware` | Array: `AIC100 Ultra`, `IQ-8275`, `IQ-9075`, `QCS6490`, `QRB2210`, `Snapdragon X Elite`. |
| `software_tools` | Array: `Android`, `Edge Impulse`, `Linux`, `Qualcomm AI Hub`, `Ubuntu`, `Windows`. |
| `ai_models` | Array of model-name strings, or `[]`. |
| `topics_tools` | Array of topic/tool strings, or `[]`. |
| `peripherals_sensors` | Array of peripheral/sensor strings, or `[]`. |
| `picture` | Relative path to an existing image inside the project. |

If you need to add new accepted values to a mandatory field's list, contact the maintainers.
