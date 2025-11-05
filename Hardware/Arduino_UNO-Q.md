# Arduino UNO-Q Hardware Documentation

Welcome to the Arduino UNO-Q Hardware Documentation page. This document provides comprehensive information about the Arduino UNO-Q platform, including details on Arduino Hardware specifications.

## Table of Contents
- [Introduction to Arduino UNO-Q](#introduction-to-arduino-uno-q)
- [Requirements](#requirements)
  - [Hardware](#hardware)
  - [Software](#software)
- [Arduino UNO-Q Product overview](#arduino-uno-q-product-overview)
- [Getting Started](#getting-started)
- [Arduino® UNO Q: Hello World Example](#arduino-uno-q-hello-world-example)
- [Arduino® UNO Q: Wireless Connectivity](#arduino-uno-q-wireless-connectivity)
- [UNO Q as a Single-Board Computer](#uno-q-as-a-single-board-computer)
- [Flashing a New Image to the UNO Q](#flashing-a-new-image-to-the-uno-q)
- [Arduino Flasher CLI](#arduino-flasher-cli)

## Introduction to Arduino UNO-Q
The Arduino® UNO Q is a next-generation single-board computer that merges the power of a high-performance microprocessor with the precision of a real-time microcontroller. This hybrid architecture enables advanced applications in AI, machine learning, robotics, and edge computing.

For detailed steps, refer to the documentation: 
[Arduino UNO-Q User Manual](https://docs.arduino.cc/tutorials/uno-q/user-manual/)

## Requirements

### Hardware 
To get started with the Arduino® UNO Q, you’ll need a few essential hardware components to ensure proper setup and operation. These components support both development and deployment workflows, especially when using the board as a single-board computer or with Arduino App Lab.

Required Hardware:
- Arduino® UNO Q board – The core development platform.
- USB-C® cable – For data transfer and power.
- USB-C multiport adapter (dongle) – Must support external power delivery.

For detailed steps, refer to the documentation: 
[Hardware](https://docs.arduino.cc/tutorials/uno-q/user-manual/#hardware-requirements)

### Software
To develop and run applications on the Arduino® UNO Q board, the following software tools are required or recommended:

Required Software:
- Arduino App Lab (version 0.1.23 or later)
  This is the primary development environment for creating and deploying hybrid apps that run on both the microcontroller (MCU) and microprocessor (MPU) of the UNO Q.

Optional Software:
- Arduino IDE 2+
  Can be used to program only the MCU side of the UNO Q, ideal for traditional Arduino sketch development.

  For detailed steps, refer to the documentation: 
[Software](https://docs.arduino.cc/tutorials/uno-q/user-manual/#software-requirements)

### Arduino UNO-Q Product overview

The Arduino® UNO Q is a powerful hybrid single-board computer that combines high-performance computing with real-time embedded control. It integrates two key processing units:

Microprocessor (MPU):
- Qualcomm® QRB2210 – Quad-core Arm® Cortex®-A53 @ 2.0 GHz
- Runs a full Debian Linux OS with upstream support
- Includes Adreno™ 702 GPU for 3D graphics and dual ISPs for embedded vision

Microcontroller (MCU):
- STMicroelectronics® STM32U585 – Arm® Cortex®-M33 @ 160 MHz
- Runs Arduino sketches over Zephyr OS
- Ideal for low-power, real-time applications

This section also inculde the infomartion.
1. Board Architecture Overview.
2. Pinout.
3. Datasheet.
4. Schematics.

For detailed steps, refer to the documentation: 
[Product overview](https://docs.arduino.cc/tutorials/uno-q/user-manual/#product-overview)

## Getting Started
Getting started with the Arduino® UNO Q is simple and designed to help you quickly begin development using its hybrid architecture. The board comes preloaded with a Debian Linux OS, allowing you to use it as a single-board computer right out of the box.

Steps for First Use:
1. Connect the Hardware.
2. Boot the Board.
3. Start Developing.

For detailed steps, refer to the documentation: 
[Getting Started](https://docs.arduino.cc/tutorials/uno-q/user-manual/#first-use)

## Arduino® UNO Q: Hello World Example
The classic Hello World example in the Arduino ecosystem is the Blink sketch, which toggles an LED on and off. On the Arduino® UNO Q, this example helps verify that the board is correctly connected and functioning with Arduino App Lab.

Please follow the instructions to run sample application:
[Hello World](https://docs.arduino.cc/tutorials/uno-q/user-manual/#hello-world-example)

## Arduino® UNO Q: Wireless Connectivity
The Arduino® UNO Q is equipped with robust wireless capabilities, making it ideal for modern IoT and edge computing applications. It features the WCBN3536A radio module, which supports:

- Dual-band Wi-Fi® 5 (2.4 GHz and 5 GHz)
- Bluetooth® 5.1

These wireless technologies are integrated with onboard antennas, ensuring reliable performance and simplified setup without the need for external modules.

For detailed steps, refer to the documentation: 
[Wireless Connectivity](https://docs.arduino.cc/tutorials/uno-q/user-manual/#wireless-connectivity)

## UNO Q as a Single-Board Computer
The Arduino® UNO Q can be used as a fully functional Single-Board Computer (SBC), thanks to its hybrid architecture combining a powerful microprocessor and microcontroller. This setup enables users to perform everyday computing tasks alongside embedded development.

For detailed steps, refer to the documentation: 
[Single-Board Computer](https://docs.arduino.cc/tutorials/uno-q/single-board-computer/)

## Flashing a New Image to the UNO Q
The Arduino® UNO Q runs a pre-installed Debian Linux OS, which typically receives automatic updates. However, in cases where a full reset or fresh installation is needed, users can flash a new image to the board using the Arduino Flasher CLI tool.

For detailed steps, refer to the documentation: 
[Flashing a New Image](https://docs.arduino.cc/tutorials/uno-q/update-image/)

## Arduino Flasher CLI
The Arduino® UNO Q runs a pre-installed Debian Linux OS, which typically receives automatic updates. However, in cases where a full reset or fresh installation is needed, users can flash a new image to the board using the Arduino Flasher CLI tool.

For detailed steps, refer to the documentation: 
[Arduino Flasher CLI](https://www.arduino.cc/en/software/#flasher-tool)
