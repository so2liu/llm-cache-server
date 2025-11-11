# GitHub Actions 自动构建 Docker 镜像配置指南

## 概述

本项目已配置 GitHub Actions 自动构建和发布 Docker 镜像到 GitHub Container Registry (ghcr.io)。镜像是公开的，所有人都可以拉取使用。

## 配置步骤

### 1. 无需额外配置！

使用 GitHub Container Registry 的优势：
- **自动认证**：使用内置的 `GITHUB_TOKEN`，无需配置额外的 secrets
- **免费使用**：公开镜像完全免费，无限存储和带宽
- **与仓库集成**：镜像自动关联到 GitHub 仓库
- **权限管理**：可以使用 GitHub 的权限系统管理访问

### 2. 触发构建

GitHub Actions 会在以下情况自动触发构建：

#### a. 推送到 main 分支
```bash
git push origin main
```
生成的镜像标签：
- `ghcr.io/so2liu/llm-cache-server:latest`
- `ghcr.io/so2liu/llm-cache-server:main`
- `ghcr.io/so2liu/llm-cache-server:build-123`（自增的构建编号）
- `ghcr.io/so2liu/llm-cache-server:sha-abc1234`（Git commit SHA）

#### b. 创建版本标签
```bash
git tag v1.2.3
git push origin v1.2.3
```
生成的镜像标签：
- `ghcr.io/so2liu/llm-cache-server:1.2.3`
- `ghcr.io/so2liu/llm-cache-server:1.2`
- `ghcr.io/so2liu/llm-cache-server:1`
- `ghcr.io/so2liu/llm-cache-server:build-123`（自增的构建编号）
- `ghcr.io/so2liu/llm-cache-server:sha-abc1234`

#### c. Pull Request
PR 会构建但不推送镜像，用于测试构建是否成功。

### 3. 镜像使用

#### 使用最新版本
```bash
docker pull ghcr.io/so2liu/llm-cache-server:latest
docker run -p 9999:9999 -v $(pwd)/data:/app/data ghcr.io/so2liu/llm-cache-server:latest
```

#### 使用特定版本
```bash
docker pull ghcr.io/so2liu/llm-cache-server:1.2.3
docker run -p 9999:9999 -v $(pwd)/data:/app/data ghcr.io/so2liu/llm-cache-server:1.2.3
```

#### 使用构建编号（推荐用于回滚）
```bash
# 使用特定构建编号
docker pull ghcr.io/so2liu/llm-cache-server:build-123
docker run -p 9999:9999 -v $(pwd)/data:/app/data ghcr.io/so2liu/llm-cache-server:build-123
```

**构建编号的优势**：
- 自增编号，容易追踪和回滚
- 不依赖 Git tag，每次 push 都会生成
- 可以在 GitHub Actions 日志中查看构建编号
- 适合在测试环境中使用特定构建版本

### 4. 查看已发布的镜像

#### 在 GitHub 上查看
1. 进入仓库主页
2. 点击右侧的 "Packages"
3. 可以看到所有已发布的镜像版本和标签
4. 点击具体版本查看详细信息和使用说明

#### 使用命令行查看
```bash
# 列出所有可用的标签（需要安装 crane 工具）
crane ls ghcr.io/so2liu/llm-cache-server

# 或者访问 GitHub Packages 页面
# https://github.com/so2liu/llm-cache-server/pkgs/container/llm-cache-server
```

## Workflow 特性

### 多架构支持
自动构建支持以下平台：
- `linux/amd64`（x86_64）
- `linux/arm64`（ARM64，包括 Apple Silicon）

### 构建缓存
使用 GitHub Actions 缓存加速构建：
- 缓存 Docker 构建层
- 显著减少构建时间

### 智能标签策略
使用 `docker/metadata-action` 自动生成标签：
- 基于分支名（如 `main`）
- 基于语义化版本（如 `v1.2.3` -> `1.2.3`, `1.2`, `1`）
- **自增构建编号**（如 `build-123`）- 每次 push 都会自增
- Git commit SHA（如 `sha-abc1234`）
- `latest` 标签（仅 main 分支）

## 版本发布流程

### 发布新版本：

1. 确保代码在 main 分支且已测试通过
2. 创建并推送版本标签：
   ```bash
   git tag -a v1.2.3 -m "Release version 1.2.3"
   git push origin v1.2.3
   ```
3. GitHub Actions 自动构建并推送镜像
4. 在 GitHub Releases 页面查看构建状态

### 版本号规范

遵循 [语义化版本](https://semver.org/lang/zh-CN/)：
- `v1.0.0`: 主版本号.次版本号.修订号
- 主版本号：不兼容的 API 修改
- 次版本号：向后兼容的功能性新增
- 修订号：向后兼容的问题修正

## 监控和调试

### 查看构建日志
1. 进入 GitHub 仓库
2. 点击 Actions 标签
3. 选择对应的 workflow run
4. 查看详细日志

### 常见问题

#### 构建失败
- 检查 Dockerfile 语法
- 确保依赖文件（pyproject.toml, uv.lock）正确
- 查看 Actions 日志中的错误信息

#### 无法推送镜像
- 确认 workflow 中的 `permissions` 包含 `packages: write`
- 检查 GITHUB_TOKEN 是否有效（通常不会有问题）
- 确认仓库设置中启用了 Actions 权限

#### 镜像标签不符合预期
- 检查 Git tag 格式（应为 `v1.2.3` 格式）
- 确认推送的是正确的分支或 tag

#### 镜像不是公开的
首次推送后，需要在 GitHub 上将镜像设置为公开：
1. 进入仓库页面
2. 点击右侧的 "Packages"
3. 选择你的镜像
4. 点击 "Package settings"
5. 滚动到底部，在 "Danger Zone" 中选择 "Change visibility"
6. 设置为 "Public"

## 文件位置

- Workflow 配置：`.github/workflows/release.yaml`
- Dockerfile：`Dockerfile`
- Docker 忽略文件：`.dockerignore`

## 与 Docker Hub 的对比

| 特性 | GitHub Container Registry | Docker Hub |
|------|---------------------------|------------|
| 价格 | 完全免费（公开镜像） | 免费层有限制 |
| 认证 | 使用 GITHUB_TOKEN，无需配置 | 需要配置 secrets |
| 与 GitHub 集成 | 原生集成 | 需要额外配置 |
| 镜像地址 | `ghcr.io/owner/repo` | `docker.io/username/image` |
| 权限管理 | 使用 GitHub 权限 | 独立权限系统 |
