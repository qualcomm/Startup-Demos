# ExecuTorch on Qualcomm

Run LLMs and multimodal models on Qualcomm boards using ExecuTorch + QNN.

**Supported targets:** IQ-9075 EVK (QCS9075), Ventuno-Q (QCS8275)
**Operating system required:** [Official Ubuntu for Qualcomm](https://ubuntu.com/download/qualcomm-iot)

Neither SOC is in ExecuTorch's supported list. Both are architecturally compatible with QCS9100, which is used for all export and build steps.

## Models

| Model | Folder | Type |
|-------|--------|------|
| [InternVL3-1B](models/internvl3_1b/README.md) | `models/internvl3_1b/` | Multimodal (vision + language) |
| [Llama-3.2-3B-Instruct](models/Llama-3.2-3B-Instruct/README.md) | `models/Llama-3.2-3B-Instruct/` | Text generation |

Pick a model and follow its README for complete end-to-end instructions.

## Platform setup

- [Official Ubuntu images](https://ubuntu.com/download/qualcomm-iot)
- [Get Started with your device](https://dragonwingdocs.qualcomm.com/Ubuntu/ubuntu-overview)
