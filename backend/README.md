# FastApiAdmin - Backend

基于 FastAPI 框架构建的企业级后端架构，为前端 Vue3 管理系统提供完整的 API 服务支持。

当前项目在框架基础上实现智仓云进销存业务。本文是后端阅读与本地运行入口，不替代完整部署手册。

## 文档导航

| 文档 | 阅读场景 |
| --- | --- |
| [仓库 README](../README.md) | 了解原框架、全栈工程结构与前后端启动入口 |
| 本文 | 了解后端技术栈、目录、分层及首次本地运行步骤 |
| [开发指南](README_DEV.md) | 新增接口、模型迁移、路由注册、菜单权限及测试 |
| [部署与初始化指南](DEPLOYMENT_INIT.md) | 首次部署、已有库升级、配置与账号规则、独立数据导入、Docker 和故障排查 |

> **先初始化，再启动**：`run` 只检查并启动，不自动建表、迁移或导入数据。初始化与部署命令的详细边界以部署指南为准，业务样例数据始终按需通过独立脚本导入。

## 技术栈

| 技术 | 版本 | 说明 |
|------|------|------|
| FastAPI | 0.138.2 | 现代 Web 框架 |
| SQLAlchemy | 2.0.51 | ORM 框架 |
| Alembic | 1.18.4 | 数据库迁移工具 |
| Pydantic | 2.12.5+ | 数据验证与序列化 |
| APScheduler | 3.11.0 | 定时任务调度 |
| redis-py | 7.1.0 | 缓存与会话存储 |
| Uvicorn | 0.49.0 | ASGI 服务器 |
| Python | 3.12+ | 运行环境 |

依赖声明以 `pyproject.toml` 为准，实际解析版本以 `uv.lock` 为准；复现仓库环境使用 `uv sync --frozen`，不要只根据上表手动升级依赖。

## 项目结构

```txt
backend/
├── app/                     # 项目核心代码
│   ├── alembic/             # 数据库迁移管理
│   ├── api/                 # 路由装配层（routers.py 按域分组聚合各模块路由）
│   ├── modules/             # 业务模块层（按业务域竖切）
│   │   ├── inventory/       #   首页、基础档案、采购、销售、库存、往来、报表
│   │   ├── system/          #   系统管理
│   │   ├── monitor/         #   系统监控
│   │   ├── task/            #   定时任务（cronjob）+ 存储传输（storage）
│   │   ├── generator/       #   代码生成
│   │   ├── ai/              #   AI 功能
│   │   └── common/          #   文件上传 / 公共能力
│   ├── common/              # 公共组件（常量、枚举、响应封装）
│   ├── config/              # 项目配置文件
│   ├── core/                # 核心模块（数据库、中间件、安全）
│   ├── plugin/              # 插件模块（二开目录）
│   ├── scripts/             # 显式初始化、菜单同步和业务数据导入实现
│   └── utils/               # 工具类（验证码、文件上传等）
├── env/                     # 环境配置文件
├── examples/                # 组织导入等受控文件示例
├── logs/                    # 日志输出目录
├── scripts/                 # 独立业务数据导入、历史数据审计/清理入口
├── sql/                     # 系统基础数据 JSON 种子，不是业务演示数据
├── static/                  # 静态资源文件
├── tests/                   # pytest 自动化测试，开发与回归时保留
├── main.py                  # CLI：启动、迁移、显式初始化、验收及菜单同步
├── alembic.ini              # Alembic 迁移配置
├── requirements.txt         # Python 依赖包
├── pyproject.toml           # 项目配置（uv / ruff）
├── uv.lock                  # uv 依赖锁文件
├── README_DEV.md            # 开发操作指南
└── DEPLOYMENT_INIT.md       # 部署与初始化操作指南
```

### 模块分层

每个业务模块采用统一的分层结构：

```txt
modules/<模块>/<子域>/
├── controller.py    # 控制器 - HTTP 请求处理
├── service.py       # 服务层 - 业务逻辑处理
├── crud.py          # 数据层 - 数据库操作
├── model.py         # ORM 模型 - 数据库表定义
├── schema.py        # Pydantic 模型 - 数据验证
└── param.py         # 可选 - 复杂请求参数依赖
```

模型可以按业务聚合放在上层目录，新增功能前先查找已有定义，避免重复建表。内置模块在 `app/api/v1/routers.py` 显式注册；只有 `app/plugin/module_*/` 符合约定的控制器使用插件自动发现，详见开发指南。

分包理念（按业务竖切 vs 按技术层次分包）详见 [项目概述](https://service.fastapiadmin.com/guide/overview)。

## 快速开始

### 环境要求

- **Python**: 3.12+
- **数据库**: MySQL 8.0+ / PostgreSQL / SQLite（按 `env/.env.dev` 和驱动配置选择；生产目标版本需单独验收）
- **Redis**: 与 `.env.dev` 中配置一致

MySQL/PostgreSQL 服务和目标数据库需预先准备；`uv sync` 只安装 Python 依赖，不安装或启动数据库、Redis。SQLite 也不能替代项目运行所需的 Redis。

### 第一次在本机跑起来

以下命令均在 **`backend/` 目录**执行；每步成功后再继续。已有业务库先阅读部署指南的“已有库升级”，不能按新空库处理。

1. 首次且配置文件不存在时，将 `env/.env.example` 复制为 `env/.env.dev`（PowerShell：`Copy-Item env/.env.example env/.env.dev`；Bash：`cp env/.env.example env/.env.dev`）。不要覆盖已有配置。
2. 编辑 `.env.dev`，确认 `ENVIRONMENT=dev`、数据库类型/地址/库名/账号、Redis 连接及安全密钥。启动数据库和 Redis，确认目标为空库。
3. 安装依赖、预检并显式初始化，再验收与启动：

```bash
uv sync --frozen
uv run main.py init-db --env=dev --dry-run
uv run main.py init-db --env=dev --apply
uv run main.py init-check --env=dev
uv run main.py run --env=dev
```

4. 默认后端地址为 `http://127.0.0.1:8001`，以 `SERVER_PORT` 为准。`/api/v1/healthz` 是最小存活探针，不代替业务验收；`/docs` 受鉴权保护，匿名访问返回401是预期行为。
5. 新库默认仅创建必要超管 `super`，初始密码为 `super123456@#`，不会自动创建 `admin` 或普通业务账号。部署前可通过进程环境变量覆盖用户名/密码，已有有效超管不会被重置；完整规则见部署指南。公开默认密码只用于初始登录，应及时修改。

前端启动见仓库 README；当前默认访问 `http://127.0.0.1:5180/web/`。普通用户和角色通过后台维护或受控组织导入建立。

初始化成功但商品、单据、报表为空是正常状态。需要业务样例时，按部署指南“独立业务数据导入”操作，不使用已移除的 `inventory-demo-init` 命令。

### 后续日常启动

同版本且数据库已验收时，只运行：

```bash
uv run main.py run --env=dev
```

缺表、缺版本或必要数据时先排查，不通过重复启动自动修复。`init-check` 只读，`init-db --dry-run` 不写库，`init-db --apply` 才执行初始化。

### 模型变更与迁移

在已初始化的开发库上生成迁移，人工审查后再应用：

```bash
uv run main.py revision --env=dev -m "业务结构变更说明"
uv run main.py upgrade --env=dev
uv run main.py init-check --env=dev
```

迁移文件必须随模型代码提交；生产只应用已审查迁移，不现场生成。生成命令不会把表直接写入数据库，空库也不能只执行 `upgrade`，详见开发指南与部署指南。

### 不使用 uv 时

在 Python 3.12+ 虚拟环境内安装运行依赖：

```bash
python -m venv .venv
# Bash: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

激活后将上述 `uv run main.py ...` 替换为 `python main.py ...`，仍须按同样顺序初始化、验收与启动。`requirements.txt` 不包含完整开发测试依赖，开发优先使用 uv。

### 代码格式化（ruff）

```bash
uv run ruff check
uv run ruff format --check .
```

当前 Ruff 配置启用了自动修复，执行 `ruff check` 可能修改文件；仅检查可用 `uv run ruff check --no-fix`。修复/格式化应限定本次修改文件，并复查 diff，避免无关格式变化。

## 后端约定（日期与序列化）

使用 **Pydantic v2** 与 **PostgreSQL（asyncpg）** 时：ORM 写入需要 Python 原生日期时间，JSON 输出需要可序列化字符串。

- 自定义 `DateStr` / `TimeStr` / `DateTimeStr`（`app/core/validator.py`）使用 **`PlainSerializer(..., when_used='json')`**
- `model_dump(mode='python')` 供 ORM 使用原生类型；JSON / Redis 使用 `model_dump(mode='json')`
- 统一 HTTP 响应见 `app/common/response.py` 中的 **`jsonable_encoder`**
- 写入 Redis 时请使用 **`model_dump(mode='json')`** 再序列化

## 相关链接

- **FastAPI 官方文档**: [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
- **SQLAlchemy 文档**: [https://docs.sqlalchemy.org/](https://docs.sqlalchemy.org/)
- **Pydantic 文档**: [https://pydantic-docs.helpmanual.io/](https://pydantic-docs.helpmanual.io/)
