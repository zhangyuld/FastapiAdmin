<div align="center">
     <img src="./frontend/web/src/assets/images/login/logo.png" width="150" height="150" alt="智仓云 Logo" />
     <h1>智仓云进销存系统</h1>
     <p>采购、销售、库存、往来与经营报表一体化管理</p>
     <p>基于 FastAPI + Vue 3 + TypeScript，提供前后端分离的 Web 管理端</p>
</div>

## 系统介绍

智仓云围绕商品流转和库存管理，连接基础档案、采购入库、销售出库、退货、期初库存、库存盘点与应收应付查询，帮助业务人员追踪单据、查看库存变化，并通过首页和报表了解经营情况。

当前主要交付后端服务和 Web 管理端，在 FastApiAdmin 框架基础上进行业务开发。仓库保留的移动端工程、框架演示页面及开发工具，不代表进销存移动端或全部扩展能力已经交付。

## 业务功能

以下为当前已实现的主要业务模块，实际可见页面和操作由账号权限决定。

| 模块 | 主要功能 |
| --- | --- |
| 首页 | 今日/本月采购与销售指标、库存金额、应收应付概览、经营趋势、仓库库存金额、库存预警及最近单据 |
| 基础档案 | 商品分类、商品、客户、供应商、仓库管理，为业务单据与报表提供基础资料 |
| 采购管理 | 采购入库、采购退货，单据新增、编辑、查看、确认、作废与导出，关联查看退货信息 |
| 销售管理 | 销售出库、销售退货，单据管理及相关库存、往来记账 |
| 库存管理 | 当前库存、库存流水、期初库存、库存盘点，查询库存数量、金额及变化来源 |
| 往来管理 | 应收账款、应付账款，账单详情、往来对象余额、余额汇总及导出 |
| 报表中心 | 采购报表、销售报表、库存报表、毛利报表，按业务条件查询和导出 |
| 系统支撑 | 用户、部门、岗位、角色、菜单、字典、参数、操作日志与产品配置等管理能力 |

往来模块当前以业务形成的账单和余额查询为主，不等同于完整的财务总账、收付款或资金核销系统；首页采购、销售金额也不代表实际资金收付。

## 业务流程

```text
维护商品分类、商品、客户、供应商、仓库
  → 按需确认期初库存
  → 采购入库 / 销售出库
  → 按业务需要办理关联退货、库存盘点
  → 查看库存余额、库存流水、应收应付和经营报表
```

- 单据区分草稿、已确认、已作废等业务状态，可执行操作受状态和权限共同约束。
- 单据确认通过业务服务形成库存流水及相关往来记录，不以直接修改余额替代业务处理。
- 采购和销售退货关联原业务单据，查询时可追踪来源与退货情况。
- 列表、详情、导出和报表按各自权限与业务口径处理，查看页面不等于拥有编辑或确认权限。

## 用户与权限

| 用户类型 | 使用边界 |
| --- | --- |
| 普通业务用户 | 按岗位授予进销存页面、按钮和数据范围，不要求授予系统管理权限才能使用业务筛选 |
| 业务管理角色 | 按实际授权维护业务与管理资料；角色名称或拥有较多菜单不等于超管身份 |
| 超级管理员 | 管理受限的产品配置及超管专属能力，维护用户授权与系统运行相关设置 |

AI 管理、监控管理、接口管理、任务管理和代码生成保留为超管专属能力，不作为普通业务用户入口。监控、接口、任务相关菜单归入系统管理，AI 管理保留独立入口。框架演示代码保留，但不开放业务菜单入口。

产品配置由后端统一控制；超管统一调整允许下发的设置，用户使用发布后的配置。快速入口仅超管可见，即使开启也不下发给普通用户。当前登录使用账号密码，不提供手机号、扫码和第三方登录入口。

## 技术架构

| 层次 | 技术与职责 |
| --- | --- |
| Web 管理端 | Vue 3、TypeScript、Vite、Element Plus、Pinia，承载进销存页面、动态菜单和交互 |
| 后端接口 | FastAPI、Pydantic，处理请求校验、认证授权和统一响应 |
| 业务与持久化 | 按 schema / crud / service / controller 分层，使用 SQLAlchemy 管理模型与事务 |
| 数据库迁移 | Alembic 管理已审查的结构变更，显式区分空库初始化与已有库升级 |
| 缓存与会话 | Redis 提供登录会话及运行缓存等能力 |
| 部署 | 支持宿主机部署与 Docker Compose，前后端通过代理或独立服务发布 |

数据库适配包含 MySQL、PostgreSQL 和 SQLite，具体驱动和配置见后端文档。生产数据库、Docker、代理与备份恢复需在目标环境验收，不将本地测试视为生产可用性证明。

## 本地运行

首次运行先准备 Python、uv、Node.js、pnpm，以及可连接的数据库和 Redis。`uv sync` 只安装 Python 依赖，不会安装数据库服务；使用 MySQL/PostgreSQL 时请先创建目标空库。

**1. 获取代码与配置环境**

获取本项目当前版本代码，并进入仓库根目录。原框架仓库用于了解框架来源，不保证包含智仓云定制模块和显式初始化命令；部署时请使用本项目实际仓库及对应版本。

以下复制仅在配置文件不存在时执行，不覆盖已有配置（Bash 示例；PowerShell 使用 `Copy-Item`）：

```bash
cp backend/env/.env.example backend/env/.env.dev
cp frontend/web/.env.development.example frontend/web/.env.development
```

编辑后端 `backend/env/.env.dev` 的数据库、Redis 和安全配置，并核对前端代理目标。新空库、已有业务库的处理不同；已有库应先按部署指南备份与升级，不按新空库试错。

**2. 显式初始化后启动后端**

在仓库的 `backend/` 目录逐条执行，每步成功后再继续：

```bash
uv sync --frozen
uv run main.py init-db --env=dev --dry-run
uv run main.py init-db --env=dev --apply
uv run main.py init-check --env=dev
uv run main.py run --env=dev
```

`run` 只检查并启动，不自动建表、迁移或导入业务数据。新库默认只创建必要超管 `super`，初始密码为 `super123456@#`，可通过部署环境变量覆盖；已有账号不会被重置。首次登录应及时改密，生产建议注入独立密码。账号与安全配置的完整规则见部署指南。

**3. 启动 Web 前端**

另开终端，在仓库的 `frontend/web/` 目录执行：

```bash
pnpm install --frozen-lockfile
pnpm run dev
```

当前默认访问 `http://127.0.0.1:5180/web/`，以 `frontend/web/.env` 的端口和基础路径为准。后端默认端口8001，以实际环境配置为准。同版本已初始化后的日常启动只需后端 `run` 与前端 `dev`，不重复初始化。

业务数据初始为空是正常状态；组织导入和业务样例导入均为可选显式操作，不随启动执行。详细步骤见 [后端 README](backend/README.md) 和 [部署与初始化指南](backend/DEPLOYMENT_INIT.md)。

| 环境要求 | 说明 |
| --- | --- |
| Python 3.12+、uv | 安装与运行后端，依赖版本按 `backend/uv.lock` 锁定 |
| Node.js 20+、pnpm | 安装与运行 Web 前端，依赖版本按前端锁文件安装 |
| 数据库、Redis | 先准备可连接的服务及数据库，参数与后端环境配置一致 |

## 部署与升级

宿主机首次部署按 [部署与初始化指南](backend/DEPLOYMENT_INIT.md) 的“首次上云或新空库部署”步骤执行。

使用 Docker 时，首次部署按 [Docker 初始化顺序](backend/DEPLOYMENT_INIT.md#7-docker-compose-执行顺序) 操作：准备配置与持久化目录 → 启动 MySQL/Redis → 一次性容器预检、初始化与验收 → 发布前端产物 → 启动后端/Nginx。

> 根目录 `deploy.sh` 可构建并启动服务，但当前未串联显式数据库初始化，不能代替首次部署流程。端口、SSL 证书和目录映射另见 [Docker 部署文档](docker/README.md)；初始化命令以部署与初始化指南为准。不要覆盖已有 `.env` 或删除数据库目录来重试部署。

首次空库初始化、已有库升级和同版本重启使用不同流程。生产部署前应确认备份、密钥、持久化目录、账号权限及恢复方案；业务样例导入不是上线必需步骤。

- **单实例部署**：当前定时调度等运行能力按单实例方式验收，不把增加 worker 或容器副本视为已经支持分布式部署。
- **密钥安全**：真实凭据通过受控环境配置注入，不提交到仓库；初始化账号应及时改密。
- **结构变更**：生产只应用已审查并随版本提交的迁移，不在生产现场生成迁移，不通过清库或删除版本记录修复失败。
- **业务验收**：除安装检查外，还应验证普通角色权限、单据状态、库存与往来记录，以及报表口径。

## 工程结构

```
项目根目录/
├─ backend/              # 后端服务与测试
│   ├── app/modules/inventory/  # 进销存业务：档案、采购、销售、库存、往来、报表、首页
│   ├── app/modules/system/    # 用户、角色、菜单和产品配置等系统能力
│   ├── app/alembic/           # 数据库迁移
│   ├── app/scripts/           # 初始化、菜单及数据导入实现
│   ├── scripts/               # 独立业务数据导入和历史维护入口
│   ├── tests/                 # 自动化测试
│   ├── README_DEV.md          # 开发指南
│   └── DEPLOYMENT_INIT.md     # 部署与初始化指南
├─ frontend/
│   ├── web/             # 智仓云 Web 管理端
│   ├── app/             # 原框架移动端工程，非当前进销存交付范围
│   └── docs/            # 原框架文档站源码，具体业务以本项目文档为准
├─ docker/               # Compose、Nginx、数据库及缓存部署配置
├─ deploy.sh             # 构建与启动脚本，不代替首次初始化
└─ LICENSE               # MIT 开源协议
```

## 文档导航

| 文档 | 用途 |
| --- | --- |
| [后端 README](backend/README.md) | 后端目录、技术栈、本地初始化与启动 |
| [后端开发指南](backend/README_DEV.md) | 模型迁移、接口开发、路由注册、菜单权限与测试 |
| [部署与初始化指南](backend/DEPLOYMENT_INIT.md) | 首次部署、升级、账号规则、组织和业务数据导入、异常处理 |
| [Web 工程说明](frontend/web/README.md) | 前端工程与开发参考；产品范围和初始化规则以本项目根文档及部署指南为准 |
| [Docker 配置参考](docker/README.md) | 端口、证书、目录映射等配置；初始化顺序以部署与初始化指南为准 |

## 开发与贡献

修改功能前先明确业务范围、接口契约和权限边界，沿用现有模块分层；涉及表结构时同步迁移，涉及菜单时同时核对数据库节点与角色授权。提交前执行与改动范围相匹配的类型检查、测试和构建验证，具体命令见各工程文档。

反馈问题时提供版本、复现步骤、预期结果及脱敏后的错误信息；不上传真实密码、完整连接串或企业业务数据。

## 框架来源与致谢

智仓云基于 **FastApiAdmin** 进行业务定制，感谢原框架作者、[框架贡献者](https://github.com/fastapiadmin/FastapiAdmin/graphs/contributors)及相关开源项目提供的基础能力。

- 原框架仓库：[GitHub](https://github.com/fastapiadmin/FastapiAdmin) · [Gitee](https://gitee.com/fastapiadmin/FastapiAdmin)
- 原框架文档：[FastApiAdmin 文档](https://service.fastapiadmin.com)，用于框架技术参考，不代表智仓云业务功能或部署步骤。
- 后端技术：[FastAPI](https://fastapi.tiangolo.com/) · [Pydantic](https://docs.pydantic.dev/) · [SQLAlchemy](https://www.sqlalchemy.org/) · [APScheduler](https://github.com/agronholm/apscheduler)
- 前端技术：[Vue 3](https://cn.vuejs.org/) · [TypeScript](https://www.typescriptlang.org/) · [Vite](https://vitejs.dev/) · [Element Plus](https://element-plus.org/)
- 保留扩展所用技术：[Agno](https://github.com/agno-agi/agno) · [UniApp](https://uniapp.dcloud.net.cn/) · [Wot Design Uni](https://wot-ui.cn/)

项目保留原框架的 MIT 许可证和版权声明，详见 [LICENSE](LICENSE)。本文介绍的是智仓云业务系统，不将原框架网站、社群或在线演示作为本产品的官方服务入口。
