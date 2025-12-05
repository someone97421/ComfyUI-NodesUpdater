
**ComfyUI-Updater**

这是一个用于自动更新 **ComfyUI** 的轻量级实用工具。通过简单的配置和脚本运行，它可以帮助用户快速保持 ComfyUI 及其组件处于最新状态，省去了繁琐的手动 Git 操作。

## **✨ 功能特点**

* **一键更新**：通过运行批处理脚本即可启动更新流程。  
* **配置灵活**：使用 config.ini 配置文件，支持自定义 ComfyUI 的安装路径或其他更新选项。  
* **轻量化**：基于 Python 编写，依赖少，易于修改和二次开发。  
* **自动化**：自动处理 Git 拉取（Pull）请求，确保本地文件与远程仓库同步。

## **📂 文件结构说明**

* main.py: 核心 Python 脚本，包含执行更新操作的主要逻辑。  
* config.ini: 配置文件，用户需在此文件中指定 ComfyUI 的安装路径等信息。  
* Run.bat: Windows 批处理启动脚本，用于一键运行更新程序。

## **🛠️ 环境要求**

在使用本工具之前，请确保您的系统已安装以下软件：

* **Python 3.x**: 用于运行更新脚本。  
* **Git**: 必须安装并配置好 Git 环境变量，以便程序执行版本控制操作。

## **🚀 使用指南**

### **1\. 下载或克隆仓库**

首先，将本项目下载到您的本地计算机：

Bash

git clone https://github.com/someone97421/ComfyUI-Updater.git  
\# 或者直接下载 ZIP 压缩包并解压

### **2\. 修改配置文件 (关键步骤)**

在运行程序之前，**必须**先配置您的 ComfyUI 路径。

1. 在解压后的文件夹中找到 config.ini 文件。  
2. 使用记事本或任意文本编辑器打开它。  
3. 根据文件内的注释提示，填写您的 ComfyUI 安装目录路径。  
   * *示例（假设）：* path \= D:\\ComfyUI 或 comfyui\_dir \= C:\\Users\\Name\\ComfyUI  
   * *请参考文件内部具体的变量名进行修改。*

### **3\. 运行更新**

配置完成后，双击文件夹中的 **Run.bat** 文件。

* 程序将自动启动命令行窗口。  
* 脚本会根据配置文件中的路径，尝试连接并更新 ComfyUI。  
* 更新完成后，请留意控制台输出的提示信息。

## **⚠️ 注意事项**

* **备份数据**：虽然更新通常是安全的，但建议在进行任何更新操作前备份您的 ComfyUI 关键数据（如 output 文件夹或自定义的工作流）。  
* **网络连接**：由于需要从 GitHub 拉取更新，请确保您的网络环境可以正常访问 GitHub。  
* **路径格式**：在编辑 config.ini 时，请注意路径分隔符的格式（Windows 下通常使用 \\ 或 \\\\）。

## **🤝 贡献**

欢迎提交 Issue 或 Pull Request 来改进这个工具！

<img width="488" height="331" alt="image" src="https://github.com/user-attachments/assets/705ca95d-b582-4eb4-be4b-cedf832fa79d" />
<img width="830" height="740" alt="image" src="https://github.com/user-attachments/assets/726aa1da-8457-4556-adc8-abd9211d316a" />  
<img width="831" height="742" alt="image" src="https://github.com/user-attachments/assets/cf5c74bd-8945-487d-a3e3-93cf5b590067" />

