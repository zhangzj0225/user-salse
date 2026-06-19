# Story 3.6: 团队树与上级链

## Status: ready-for-dev

## Story Description

用户可以查看自己的团队树（下级树）和上级链条。

- **我的团队**：以当前用户为根，展示直接下级列表（昵称、角色、注册时间、直接下级数），支持逐层展开，无深度限制，展示团队总人数。
- **我的上级**：从当前用户到根节点的完整上级链，每级显示昵称和角色，根节点显示"无上级"。

## Acceptance Criteria

1. **GET /api/v1/users/me/team** — 返回直接下级列表，每个节点包含 user_id、nickname、role、created_at、children_count
2. **GET /api/v1/users/me/team?parent_id=X** — 展开指定下级的直接下级（逐层展开）
3. **GET /api/v1/users/me/team** 响应包含 total_count（团队总人数，含间接下级）
4. **GET /api/v1/users/me/upstream** — 返回从当前用户到根的完整上级链
5. 上级链每级包含 user_id、nickname、role、level（从 1 开始）
6. 根节点（无上级）在上级链末尾显示，role 不变，level 为最大值
7. 无上级用户访问 upstream 返回空列表
8. 无下级用户访问 team 返回空列表 + total_count=0
9. 需要 user token 认证
10. 团队树仅展示自己分支下的用户（不能查看他人的团队）

## Technical Notes

- 使用 adjacency list（parent_id）递归查询，无深度限制
- total_count 使用递归 CTE 或递归 Python 查询统计所有后代
- 逐层展开：前端传 parent_id，后端返回该节点的直接下级（需验证该节点是当前用户的后代）
- 无需修改现有模型

## Files to Create/Modify

| File | Action |
|------|--------|
| `backend/app/schemas/team.py` | NEW |
| `backend/app/services/team_service.py` | NEW |
| `backend/app/api/v1/team.py` | NEW |
| `backend/app/main.py` | UPDATE (注册路由) |
| `backend/tests/test_team_service.py` | NEW |
| `backend/tests/test_team_api.py` | NEW |
