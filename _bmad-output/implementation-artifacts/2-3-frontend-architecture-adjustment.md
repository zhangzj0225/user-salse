---
story_id: "2.3"
story_key: "2-3-frontend-architecture-adjustment"
epic: "2"
title: "前端架构调整"
status: "done"
created: "2026-06-19"
---

# Story 2.3: 前端架构调整

## User Story

As a 开发者,
I want 移除 mini-program 并创建 user-web,
So that 匹配 PRD v2 的双 Web 端架构。

## Acceptance Criteria

### AC1: 删除 mini-program 目录

**Given** Epic 1 的 mini-program 目录（Taro 微信小程序）
**When** 执行前端架构调整
**Then** `mini-program/` 目录及其所有内容被删除
**And** git 记录删除操作

### AC2: 创建 user-web 项目

**Given** 需要替代 mini-program 的 Web 端
**When** 创建 user-web 项目
**Then** `user-web/` 目录包含基础项目结构
**And** 技术栈：React 19 + Vite 5 + TypeScript 5.x + Ant Design v6
**And** 路由：react-router-dom v6
**And** 状态管理：@tanstack/react-query + Zustand
**And** 代码质量：Biome

### AC3: user-web 目录结构

**Given** user-web 项目已创建
**When** 检查目录结构
**Then** 包含 `src/pages/`, `src/components/`, `src/services/`, `src/stores/`, `src/utils/`
**And** 包含 `vite.config.ts`, `package.json`, `tsconfig.json`, `index.html`
**And** 包含基础页面骨架（login, home）

### AC4: admin-web 和 backend 保持不变

**Given** 前端架构调整完成
**When** 检查 admin-web 和 backend
**Then** `admin-web/` 目录内容不变
**And** `backend/` 目录内容不变

### AC5: README 更新

**Given** 前端架构调整完成
**When** 检查 README.md
**Then** 项目结构说明更新为 user-web + admin-web + backend
**And** 移除 mini-program 相关描述
