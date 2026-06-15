# user-salse



## 项目结构

- `backend/` — Python FastAPI 后端
- `mini-program/` — Taro 4.x 微信小程序
- `admin-web/` — Ant Design Pro v6 管理后台

## 快速开始

### 后端

```bash
cd backend
pip install -e .
alembic upgrade head
python scripts/create_admin.py --username admin --password yourpassword
uvicorn app.main:app --reload
```

### 小程序

```bash
cd mini-program
npm install
npm run dev:weapp
```

### 管理后台

```bash
cd admin-web
npm install
npm run dev
```
