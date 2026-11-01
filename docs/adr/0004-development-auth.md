# ADR-0004: 开发身份与生产 OIDC 边界

- 状态：已接受
- 日期：2026-08-27

## 决策

开发环境由服务端配置注入固定用户，不接受客户端身份请求头。`DEV_AUTH_ENABLED=true` 仅允许
在 `APP_ENV=development`；其他环境必须拒绝启动。授权始终按 Project 的
`owner/editor/viewer` 成员关系执行。

## 结果

首轮不实现密码或正式登录页。生产 OIDC 后续替换身份解析适配器，不改变 User subject、
ProjectMember 或 use case 权限检查。

