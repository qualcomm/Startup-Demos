# [Startup_Demo](../../)/[Hardware](../)/[IoT-Robotics](./)/[RB3-Gen2](./RB3-Gen2.md)

# RB3 Gen2 Device Setup Guide

## Table of Contents
- [Overview](#1-overview)
- [Requirements](#2-Requirements)
  - [Hardware Requirements](#21-Hardware-Requirements)
  - [System Requirements](#22-System-Requirements)
- [Tools Installation](#3-Tools-Installation)
- [Powering On Device](#4-Powering-On-Device)
- [Software Updates](#5-Software-Updates)
  - [Enabling EDL Mode](#51-Enabling-EDL-Mode)
  - [Download QIMP SDK](#52-Download-QIMP-SDK)
  - [Flash Device using PCAT Method](#53-Flash-Device-using-PCAT-Method)
- [Access DeviceShell](#6-Access-DeviceShell)
  - [Setup Read and Write Permission](#61-Setup-Read-and-Write-Permission)
- [Network-Connectivity](#7-Network-Connectivity)
  - [WiFi Setup](#71-WiFi-Setup)
  - [Ethernet Setup](#72-Ethernet-Setup)
- [Ubuntu Setup](#8-Ubuntu-Setup)
- [ESDK Installation Guide](#9-ESDK-Installation-Guide)
  - [Download eSDK](#91-Download-eSDK)
  - [ESDK Environment Setup](#92-ESDK-Environment-Setup)

## 1. Overview

The RB3 Gen2 development kit is designed for building advanced IoT and robotics applications. It is powered by the Qualcomm® QCS6490 chipset, which delivers robust performance, AI capabilities, and connectivity options.

- [RB3 Gen2 Development Kit](https://www.qualcomm.com/developer/hardware/rb3-gen-2-development-kit)
- [Qualcomm QCS6490](https://www.qualcomm.com/products/internet-of-things/qcs6490)

To set up the RB3 Gen2, you need to follow a specific procedure that involves carefully unpacking and connecting the development kit, as well as installing the necessary software and drivers. By following this procedure, you can ensure a successful setup and start developing your IoT and robotics applications with the RB3 Gen2 development kit.

## 2. Requirements
To set up the RB3 Gen2, you need to fulfill both the hardware and software requirements. This includes having the necessary hardware components, such as the development kit itself, a compatible computer or host device, and any additional peripherals or accessories required for your specific application.

### 2.1. Hardware Requirements
To get started, you'll need the following hardware components:
* Development board based on the Qualcomm QCS6490 processor
* 12V power supply
* Type-C cable
* HDMI cable
* Monitor

### 2.2. System Requirements
You'll need to run the setup on a computer with a compatible operating system, such as Windows, to ensure proper functionality and compatibility with the RB3 Gen2 development kit.

* Windows 10/11: You will need to use a Windows environment to install the necessary tools, connect the device, and update the software.

## 3. Tools Installation
To install the necessary tools, follow these steps on your Windows PC: The tools setup is intended for flashing and detecting devices. The process involves installing specific software and drivers to enable communication between the development kit and the host machine.

1. Download the [QSC installer](https://softwarecenter.qualcomm.com/) from the official website .
2. Run the installer and follow the prompts to install the QSC.
3. Once the installation is complete, launch the QSC and login in with your credentials.
4. After logging in, you will be able to access the various tools and software available for the RB3 Gen2 development kit.
5. Install PCAT and QUD from the software center.
6. Set up the ADB from the platform tools and add it to your environment variable: [ADB](https://dl.google.com/android/repository/platform-tools-latest-windows.zip)

For more detailed information and step-by-step instructions, Refer to the provided reference [Install QSC](https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-253/set_up_the_device.html?vproduct=1601111740013072&version=1.3#flash-using-pcat)

## 4. Powering On Device
The RB3 Gen 2 Development Kit comes preloaded with software.Follow the respective setup instructions to detect the device.

1. Carefully unpack the RB3 Gen2 development kit and its components, including the development board, power supply, Type-C cable, HDMI cable, and monitor.
2. Connect the 12V power supply to the development board, making sure it is securely plugged in.
3. Connect the HDMI cable to the development board and the monitor, ensuring a secure connection.
4. Connect the Type-C cable to the development board and your Windows PC, allowing for communication between the two devices.
5. Open the device manager on your Windows PC and verify that the device is recognized. 
- If it is connected, it will show the Qualcomm device in normal mode. 
- If it's in EDL mode, it will show the QDLloader.
6. Open a command prompt and type the command `adb devices` to verify the device connection. If the device is connected, it will be listed in the output.

For more detailed information and step-by-step instructions, Refer to the provided reference [Connect to HDMI display](https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-253/set_up_the_device.html?vproduct=1601111740013072&version=1.3#panel-0-v2luzg93cw==tab$connect-to-hdmi-display)

## 5. Software Updates

The RB3 Gen 2 Development Kit comes preloaded with software that helps you to quickly set up the device or if needed Update the software.follow the setup instructions for your operating system to prepare the development kit for running applications.

### 5.1. Enabling EDL Mode
Need to force the device into EDL mode to enable software flashing. in EDL mode, follow these steps

1. Press and hold the F_DL button.
2. Connect the device to a 12-V wall power supply.
3. Connect the device to the host system through the USB Type-C connector.
4. Release the F_DL button. The device should now be in EDL mode.

For more detailed information and step-by-step instructions, Refer to the provided reference [EDL mode](https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-253/set_up_the_device.html?vproduct=1601111740013072&version=1.3#edl-link-win)

### 5.2. Download QIMP SDK

1. Download [QIMP SDK](https://artifacts.codelinaro.org/artifactory/qli-ci/flashable-binaries/qimpsdk/qcs6490-rb3gen2-vision-kit/x86/qcom-6.6.52-QLI.1.3-Ver.1.1_qim-product-sdk-1.1.2.zip) for the vision kit on an x86 host
2. Unzip the file.

For more detailed information and step-by-step instructions, Refer to the provided reference [QIMP SDK software](https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-253/set_up_the_device.html?vproduct=1601111740013072&version=1.3#win-machine)

### 5.3. Flash Device using PCAT Method

1. Open a command prompt and navigate to the directory where the PCAT tool is installed.
2. Run the command `pcat -devices` to check if the device is recognized by the PCAT tool.
3. If the device is recognized, run the command `pcat -PLUGIN SD -DEVICE <SERIAL NUMBER> -BUILD "<extracted zip directory path>\target\qcs6490-rb3gen2-vision-kit\qcom-multimedia-image" -MEMORYTYPE UFS -FLAVOR asic` to flash the device.

Note: Replace `<SERIAL NUMBER>` with the actual serial number of your device, and `<extracted zip directory path>` with the actual path where the QIMP SDK is extracted.

For more detailed information and step-by-step instructions, Refer to the provided reference [Flash using PCAT](https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-253/set_up_the_device.html?vproduct=1601111740013072&version=1.3#flash-using-pcat)

## 6. Access DeviceShell:
To interact with the RB3 Gen2 device, you need to access its shell. This can be done using either SSH or ADB, depending on your setup and preferences. Below are the methods to log into the RB3 Gen2 shell

__Method 1__: Login using ADB
Enable adb to log into the target device. Install and connect to ADB.

	adb devices
	adb shell

__Method 2__: Login using SSH
Enable SSH to log into the target device.

To obtain the IP address, first set up the Wi-Fi , retrieve the IP address, and then log in to the device.

Log in to the SSH shell:

	ssh root@[ip-addr]
Note If prompted for a username and password , enter username root and password oelinux123.

### 6.1. Setup Read and Write Permission
On the target device, reconfigure the file system partition to support read and write permissions:

	setenforce 0
	mount -o remount,rw /
	mount -o remount, rw /usr

## 7. Network-Connectivity

To connect to a wireless network, you can use one of two methods: WiFi Setup or Ethernet Setup.

### 7.1. WiFi Setup

Establish a wireless connection using the nmcli command-line tool.

1. Open the command prompt.
2. Type the command `adb shell`.
3. Use the nmcli command-line tool to connect to the wireless access point (Wi-Fi router). The command is: `nmcli dev wifi connect <WiFi-SSID> password <WiFi-password>`.
   Example: `nmcli dev wifi connect QualcommWiFi password 1234567890`.
4. Verify the WiFi connection using the command `nmcli -p device`.

### 7.2. Ethernet Setup

1. Insert one end of the Ethernet cable into the Ethernet port (RJ45) of the RB3 Gen 2 device and connect the other end to your network router.
2. After the connection is established, run the following command on the UART serial console to obtain the IP address:
	ifconfig eth2

For more detailed information and step-by-step instructions, Refer to the provided reference [Get device IP address](https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-253/set_up_the_device.html?vproduct=1601111740013072&version=1.3#device-ip-win)

## 8. Ubuntu Setup

To set up Ubuntu for syncing, building, and flashing the associated firmware on supported devices, you will need to follow these steps. If you do not have an Ubuntu machine, you can set up a virtual machine (VM) running Ubuntu in a virtualized environment on a Windows or Linux host machine.

An Ubuntu 22.04 host machine with at least 100 GB of free space. To set up the virtual machine running Ubuntu 22.04 OS on a linux, see [Virtual Machine Setup Guide](https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-41/getting-started.html) 

## 9. ESDK Installation Guide

This guide provides detailed instructions for installing and setting up the <a href="https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-51/install-sdk.html#download-and-install-esdk" target="_blank"> Download and install eSDK </a> on your development kit.It is recommended to install eSDK from the Qualcomm public archive or compile it independently on your host machine.

### 9.1. Download eSDK

Download eSDK on Ubuntu x86 Architecture-Based Host Machines
Follow these steps to download and set up the eSDK on Ubuntu x86 architecture-based host machines:

Create a workspace directory and navigate to it:

	mkdir ~/ESDK_Installation && cd ~/ESDK_Installation

Install necessary packages:

	sudo apt update && sudo apt-get install diffstat bzip2 gcc g++ unzip gcc-aarch64-linux-gnu && sudo locale-gen en_US.UTF-8 && sudo dpkg-reconfigure locales

![N|Solid](../Images/RB3-Gen2/rb3_gen2_package_installation.png)

Download the eSDK:

	wget https://artifacts.codelinaro.org/artifactory/qli-ci/flashable-binaries/qimpsdk/qcs6490-rb3gen2-vision-kit/x86/qcom-6.6.52-QLI.1.3-Ver.1.1_qim-product-sdk-1.1.2.zip

![N|Solid](../Images/RB3-Gen2/rb3_gen2_esdk_download.png)

unzip the Downloaded file

	unzip qcom-6.6.52-QLI.1.3-Ver.1.1_qim-product-sdk-1.1.2.zip

![N|Solid](../Images/RB3-Gen2/rb3_gen2_esdk_unzip.png)

Run the setup script:

	cd ~/ESDK_Installation/target/qcs6490-rb3gen2-vision-kit/sdk/
	umask a+rx
	sh ./qcom-wayland-x86_64-qcom-multimedia-image-armv8-2a-qcs6490-rb3gen2-vision-kit-toolchain-ext-1.3-ver.1.1.sh

![N|Solid](../Images/RB3-Gen2/rb3_gen2_esdk_script.png)

### 9.2. ESDK Environment Setup

Set the ESDK root environment variable:

	export ESDK_ROOT=~/ESDK_Installation/
	cd $ESDK_ROOT
	source environment-setup-armv8-2a-qcom-linux

![N|Solid](../Images/RB3-Gen2/rb3_gen2_esdk_envsetup.png)