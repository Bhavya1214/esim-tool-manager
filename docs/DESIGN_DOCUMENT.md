# Design Document: Automated Tool Manager for eSim

## 1. Overview
The **eSim Automated Tool Manager (eTM)** is a cross-platform CLI utility written in Python designed to manage the lifecycle of external EDA tools (Ngspice, KiCad, Magic, XSchem, etc.) required by the eSim ecosystem. It abstracts away OS-specific package managers (apt, winget, choco, brew), handles version pinning, automates PATH/env configuration, and validates dependencies.

## 2. Architecture

### 2.1 High-Level Components
```mermaid
graph TD
    CLI[Typer CLI Interface] --> Core[Core Services]
    Core --> Repo[Tool Repository (YAML)]
    Core --> Platform[Platform Abstraction]
    Core --> Installer[Installation Manager]
    Core --> Updater[Update Manager]
    Core --> Config[Configuration Manager]
    Core --> DepCheck[Dependency Checker]
    Platform --> OS[Linux/Windows/macOS]
    Installer --> PKG[Apt/Choco/Winget/Brew]
    Installer --> Manual[Manual Download/Compile]
