# 智仓云部署与初始化指南

更新日期：2026-10-20（文档整合；不代表重新完成目标环境验收）。

> 状态：独立初始化命令和启动分离已实现；临时 SQLite 验证，MySQL/PostgreSQL、Docker 与云端仍需在目标环境验收。
> `run` 不再自动迁移、导入种子或补建辅助表。已有安装升级本版本前，也需要显式预检、补齐辅助结构后验收。
> 本文不代表已经部署到云端；执行写入命令前必须确认环境、备份与目标数据库。

## 阅读顺序与场景选择

[后端 README](README.md) 提供技术栈、目录与本地最短启动流程；[开发指南](README_DEV.md) 说明模型、接口、路由、菜单与测试。本文集中维护部署命令、写入边界、账号规则和异常处理，避免三处重复维护完整步骤。

| 当前场景 | 操作入口 | 不应做的事 |
| --- | --- | --- |
| 首次本地开发，使用新空库 | 后端 README 的首次运行步骤；具体配置/异常参考本文第4、8节 | 直接运行 `run` 并期待自动建表 |
| 首次上云或新空库部署 | 第4节步骤1至8 | 把 `upgrade` 当作完整空库初始化 |
| 已有业务库部署新版本 | 第5节“已有库升级” | 清库、删除版本记录或现场生成迁移 |
| 同版本正常重启 | 第5节“正常重启” | 重复导入组织或业务数据 |
| 导入真实部门、岗位、角色和用户 | 第4节步骤5，系统已初始化后也可单独执行 | 认为 `init-db` 已创建全套企业账号 |
| 需要进销存业务样例 | 第6节独立脚本，dev/prod均按需执行 | 在启动或初始化中自动注入演示业务 |
| 使用 Docker Compose | 第7节，再对照第4节配置与验收 | 未初始化就把 `deploy.sh` 当成完整首次部署入口 |
| 处理旧D前缀历史数据 | 第6节“历史专项维护”，仅适用于已审核旧批次 | 在新部署中例行执行清理脚本 |

宿主机命令除前端构建外均在 `backend/` 执行，Docker 命令在 `docker/` 执行。代码块中的 `/secure/...`、域名等为占位路径，需替换成已准备并受控的真实位置，Windows 可使用对应绝对路径。

**执行规则**：逐条运行并检查退出码；失败时停止后续步骤，先按第8节排查。以下 Bash 命令块不等于可无条件整段执行的发布脚本；PowerShell 的上一条本机命令退出码可用 `$LASTEXITCODE` 检查。没有异常输出不等于已经完成业务验收。

## 1. 启动、初始化和演示数据的边界

| 类别 | 目标职责 | 是否生产必需 |
| --- | --- | --- |
| 项目启动 | 检查配置和已初始化数据库，连接数据库/Redis，加载缓存，启动必要调度器，提供服务 | 是 |
| 数据库初始化 | 首次创建完整结构，处理已提交迁移，初始化必需系统数据、菜单、产品配置及保留模块的辅助表 | 首次部署必需 |
| 组织权限初始化 | 按审核后的部署资料导入部门、岗位、角色、真实用户及关联 | 按企业实际需要，可在后台维护 |
| 独立业务数据导入 | 按需导入组织账号、基础档案和进销存业务样例；不属于初始化 | 否，dev/prod均可显式执行，生产须额外确认 |

约束：

- `uv run main.py run --env=prod` 只启动项目，不生成迁移、不执行迁移、不导入组织/业务数据、不修复缺失表、不重置密码。
- 启动允许读取数据库并恢复 Redis 参数/字典缓存、建立连接及启动调度器。这些运行期工作与业务数据初始化不同。
- 产品配置、Agno 会话表以及 APScheduler SQL 作业存储表均须纳入显式初始化和校验；不能只移除业务模型建表后遗漏其他自动建表入口。
- 所有初始化均为单实例、人工或发布作业显式执行，不能让多个应用 worker 同时初始化。
- 不提供自动删库、清表、覆盖账号、重置密码或清理无法解析迁移版本的部署操作。

## 2. 实现入口与执行链路

1. `main.py` 先解析 `--env` 再导入应用配置，避免生产命令提前加载开发配置。
2. `app/scripts/deployment/structure.py` 判断空库、核对历史与模型；真空库完整建表、校验后标记版本，已有库仅执行已提交迁移。
3. `bootstrap.py` 按自然键补系统参数、菜单、字典、默认系统部门和超管角色；没有有效超管时才创建初始超管，不导入旧演示账号。
4. `check.py` 显式准备 Agno 和 APScheduler 辅助表，并提供启动与验收共用的只读检查。
5. `organization.py` 导入企业组织；业务样例已抽离至 `app/scripts/data_import/inventory.py`，仅由独立 `scripts/import_inventory_data.py` 调用，不进入 `main.py` 初始化或启动链路。
6. `app/__init__.py` 启动先只读检查数据库，之后连接 Redis、恢复运行缓存并启动调度器；SQL 作业存储启动也禁止自动建表。

重要边界：

- 当前迁移链主要为进销存增量，不是完整系统基线；首次空库使用 `init-db`，不能单独 `upgrade`。
- 非空无版本、未知版本、多 head 或当前版本结构漂移一律拒绝；不会删版本或盲目 stamp。
- 系统基础数据只补缺失项；已有配置、密码和授权保留，受管自然键重复/已删除等冲突报错。
- 真实企业岗位、组织和普通用户由 `init-org` 或后台维护，不能认为 `init-db` 已提供全套企业组织。
- 本地上传存储源按名称补缺，不覆盖已有源或争夺默认标志；日志清理等定时业务任务不自动启用，由超管审核后配置。
- `app/scripts/initialize.py` 保留旧测试兼容入口，不是生产部署入口；不会由 `run` 调用。
- 旧库可能仍有 `super`、`admin` 等默认弱密码账号，升级不会自动删除或改密。必须人工审核；新库仅创建一个必要超管。

## 3. 命令清单及实施状态

所有宿主机 Python 命令均在仓库 `backend/` 目录执行。环境参数必须显式指定，生产使用 `--env=prod`。

| 命令 | 状态 | 职责 |
| --- | --- | --- |
| `uv run main.py run --env=prod` | 已实现 | 仅检查和启动，缺结构或必要数据则失败 |
| `uv run main.py upgrade --env=prod` | 已存在 | 应用仓库已提交迁移，不生成迁移、不导入种子 |
| `uv run main.py revision --env=dev -m "迁移说明"` | 已存在 | 仅开发阶段生成迁移，审查并提交后部署；禁止在生产部署时生成 |
| `uv run main.py inventory-menu-init --env=prod` | 已存在 | 补进销存菜单/按钮，为已有默认管理员角色补交付权限；普通角色仍需授权 |
| `uv run main.py menu-upgrade --env=prod` | 已存在 | 旧版菜单升级为进销存菜单结构，按升级需要执行 |
| `uv run main.py init-db --env=prod --dry-run` | 已实现 | 只读检查结构、版本和种子文件，列出初始化阶段 |
| `uv run main.py init-db --env=prod --apply` | 已实现 | 显式初始化结构与必需系统数据；不生成演示业务 |
| `uv run main.py init-org --env=prod --file /secure/org-init.json --dry-run` | 已实现 | 预检企业组织及用户导入资料 |
| `uv run main.py init-org --env=prod --file /secure/org-init.json --apply` | 已实现 | 按业务编码导入组织、角色、用户及关联 |
| `uv run main.py init-check --env=prod` | 已实现 | 只读验收数据库、基础数据、权限引用、辅助表及 Redis 连通性 |
| `uv run python scripts/import_inventory_data.py --env=dev --dry-run` | 独立脚本 | 预览业务数据导入，不写库 |
| `uv run python scripts/import_inventory_data.py --env=dev --apply` | 独立脚本 | 按需导入正常业务数据，不参与初始化 |
| `uv run python scripts/import_inventory_data.py --env=prod --apply --confirm-production` | 独立脚本 | 经审核后手动写入生产业务数据 |
| `uv run python scripts/audit_legacy_inventory.py --env=dev` | 只读脚本 | 核查旧D前缀批次、主键清单和交叉引用，不执行删除 |

`python main.py ...` 与 `uv run main.py ...` 的命令入口相同，但前者须已激活正确虚拟环境。现有 Typer 无参数入口不是新的初始化命令，部署启动使用明确的 `run` 子命令。

命令约定：

- `init-db`、`init-org` 和独立业务导入脚本默认只读预检，只有 `--apply` 才写库；`--dry-run` 与 `--apply` 互斥，不用“写入后回滚”模拟只读预检。此规则不适用于 `upgrade`、`inventory-menu-init`、`menu-upgrade`，后三者不加 `--apply` 也会修改数据库，不能当作预检命令。
- `init-db`、`init-org`、`init-check` 和独立业务导入成功时输出 JSON 结果；`upgrade`、菜单命令和常驻启动的输出形式不同，不假设所有命令最后一行都是 JSON。共用部署执行器的错误使用稳定错误码和脱敏说明，不输出密码、连接凭据或完整配置密钥；未分类驱动/业务异常只显示异常类型。
- 部署执行器成功返回0；配置/参数/导入格式错误返回2，前置条件、数据冲突和验收失败通常返回3，未分类执行失败返回4。菜单命令和服务启动不经过同一错误包装，不保证相同的错误码格式；任何非0退出均先停止后续步骤。
- 遇到冲突或缺失前置条件必须失败退出，不能打印“成功”后继续部署。

## 4. 首次上云或新空库部署

> 以下命令已接入；目标服务器仍需逐步执行、记录结果，不能把本地测试当作云端验收。

| 步骤 | 完成标志 | 是否可跳过 |
| --- | --- | --- |
| 1. 环境与目标库 | 版本、数据库归属、依赖服务及备份策略明确 | 不可跳过；已有业务库改走第5节 |
| 2. 配置与依赖 | 依赖安装成功，配置和安全密钥已准备 | 不可跳过；已有配置不重复复制 |
| 3. 只读预检 | 退出0，结构与版本符合目标场景 | 不建议跳过；不代替备份或实际写入校验 |
| 4. 必需初始化 | 退出0，必要结构、系统数据和超管已准备 | 新空库不可跳过；不是业务样例导入 |
| 5. 企业组织导入 | 已导入审核后的组织和权限，或记录后台维护安排 | 可跳过；初始超管可在后台维护 |
| 6. 只读验收 | 退出0，数据库及 Redis 检查通过 | 不可跳过；`--database-only` 不等于完整验收 |
| 7. 前端与代理 | 同版本完整产物、域名、证书及代理配置就绪 | 可用已发布产物代替现场构建，不能缺少可用 Web 服务 |
| 8. 启动与验证 | 服务启动，登录、权限和实际业务访问通过 | 不可跳过；存活探针不代替业务验收 |

### 步骤1：确认环境、目标数据库与备份

- 获取同一发布版本的后端代码、迁移文件、`uv.lock` 和前端产物，保留版本号或提交号。
- 核对连接的是新空库还是已有库。已有库一律转第5节，先备份并确认备份可恢复。
- 准备 Python 3.12、uv、MySQL、Redis。前端构建另需匹配项目要求的 Node 与 pnpm；使用预构建产物则服务器不必安装前端构建工具。
- MySQL 实例、数据库名与部署账号由 DBA/云平台预先创建，字符集使用 utf8mb4。业务运行账号与迁移账号宜分离；初始化账号具有所需 DDL/DML 权限，运行阶段不依赖建表权限。
- MySQL/Redis 不应直接开放公网。确认域名、证书、上传文件持久化目录及访问权限。

跳过风险：连错库可能污染真实数据；无备份不能继续已有库升级。连接拒绝、超时或 `Unknown database` 分别检查服务/网络、连接参数及数据库是否预建，不通过反复运行初始化碰运气。

### 步骤2：准备配置和依赖

在 `backend/` 中：

```bash
uv sync --frozen
```

首次且目标配置文件不存在时，将 `env/.env.example` 复制为 `env/.env.prod` 并编辑，不覆盖已有生产配置。PowerShell 使用 `Copy-Item env/.env.example env/.env.prod`，Bash 使用 `cp env/.env.example env/.env.prod`，复制前先确认文件不存在。至少确认：

| 配置 | 说明 |
| --- | --- |
| `ENVIRONMENT=prod`、`DEBUG=False` | 明确生产环境，不使用热重载 |
| `DATABASE_TYPE/HOST/PORT/NAME/USER/PASSWORD` | 与实际部署数据库一致 |
| `REDIS_HOST/PORT/PASSWORD/DB_NAME` | 与实际 Redis 一致，实例内应用之间避免键空间混用 |
| `SECRET_KEY` | 强随机独立密钥，不使用仓库开发默认值；各实例保持一致 |
| `DATA_ENCRYPTION_KEY` | 建议单独管理并备份，变更需考虑已有密文解密 |
| `SERVER_HOST=0.0.0.0`、`SERVER_PORT` | 容器/服务器监听地址与代理端口匹配 |
| `PROD_CORS_ORIGINS` | 如跨域访问，配置实际 HTTPS 域名，不照抄示例域名 |
| 反向代理可信来源设置 | 按实际代理层数和网络隔离配置，不能允许公网请求任意伪造转发头 |

初始超管用户名通过 `INIT_ADMIN_USERNAME` 指定，默认 `super`。dev/prod 统一采用以下初始密码：`super` 为 `super123456@#`，`admin` 为 `admin123456@#`，其他初始化或自动生成账号为 `zcy123456@#`。仅新建时生效，不额外创建原本不需要的账号；`init-db` 仍只创建一个必要超管，已有有效超管时不修改密码。

可通过进程环境变量 `INIT_ADMIN_PASSWORD`、组织文件中引用的密码变量或独立业务脚本的 `INVENTORY_DATA_PASSWORD` 覆盖默认值；未设置变量时采用账号默认值，显式设置为空或强度不足则失败，不静默回退。这些变量不是写进 `env/.env.prod` 就能被脚本读取，命令不再强制交互询问密码。显式密码仍须8至64位、至少两类字符。旧 `DEMO_INIT_PASSWORD` 不再作为新导入脚本的输入。生产强制 `DEBUG=False`，`SECRET_KEY` 至少32位且不能使用框架开发默认值。

**安全提示：上述是已公开约定的初始密码，不适合长期用于生产。生产部署建议始终注入独立密码，并在登录后立即改密；当前没有强制首次改密能力。真实凭据不得提交仓库或输出到日志。**

跳过风险：`ModuleNotFoundError`/依赖安装失败、连接或认证失败、错误环境连接、HTTPS 重定向循环。修复安装源/版本/网络及对应配置，保持锁文件一致，不在服务器临时升级全部依赖。

本步骤完成后应已有可用依赖、明确的目标库及可连接的数据库/Redis。生产部署所需密钥必须在运行下一步前注入；安装依赖成功不代表配置或连接已经验收。

### 步骤3：预检初始化计划

```bash
uv run main.py init-db --env=prod --dry-run
```

输出 `mode`、`structure.empty/revision/target/missing/drift` 和 `stages`。为避免泄露凭据，不输出连接串。预检只做结构、迁移历史和种子文件格式检查，不模拟写入，也不能保证没有数据阶段的自然键冲突。

- 真空库：列出完整结构和必需数据创建计划。
- 已完成初始化：结构检查无缺表/漂移；实际写入时仍按自然键补缺，不生成重复记录。
- 非空但无可信迁移版本、当前版本缺表/漂移或缺少迁移脚本：失败，人工核对，不自动清理版本记录。旧版本可通过已提交迁移升级；保留键冲突在数据阶段拒绝。

跳过风险：直到实际写入才发现目标库或依赖错误。预检不能替代备份，也不能证明后续 DDL 可完整回滚。

### 步骤4：执行必需初始化

```bash
uv run main.py init-db --env=prod --apply
```

执行顺序：

1. 获取初始化互斥锁并复核目标环境，避免并发初始化。
2. 真空库创建完整模型结构，校验后设置与当前结构一致的迁移版本；已有可信版本按已提交迁移处理，不自动生成迁移。
3. 准备保留功能所需的 Agno 会话、SQL 作业存储等辅助表，并验证结构；不能吞掉任意建表失败。
4. 依赖顺序初始化必需系统参数、字典、菜单、角色及初始超管，并补进销存菜单和产品配置。
5. 创建所需存储目录，输出阶段结果；重复执行只补缺失的受管基础记录，不覆盖已发布产品配置或既有账号密码、角色授权。

新库仅创建必要初始超管，不导入旧种子中所有默认演示账号。既有库不自动删除账号或改变超管标志，按部署审核清单处理。

跳过风险：缺表、无可登录管理员、缺少菜单或产品配置时拒绝启动，不回退到自动初始化。

失败处理：MySQL 的 DDL 可能隐式提交，不能承诺初始化整体事务回滚。保留阶段结果，重新检查实际表与版本；数据阶段尽量事务化，恢复或幂等补齐前必须再次预检，不能通过清库重试。

### 步骤5：导入企业组织与权限（可按实际跳过）

```bash
uv run main.py init-org --env=prod --file /secure/org-init.json --dry-run
uv run main.py init-org --env=prod --file /secure/org-init.json --apply
```

- 导入部门树、岗位、角色、用户、用户部门/岗位/角色关联及角色菜单权限。
- 使用部门/岗位/角色编码、用户名、权限标识解析关联，不写死数据库ID。
- 导入文件参考 `backend/examples/organization.json`，字段定义见 `app/scripts/deployment/organization.py`。正式组织资料与演示数据分开保存，凭据不入代码仓库。
- 普通业务角色只授权对应进销存能力；业务管理员不等于超管。数据范围明确区分全部、本部门及以下、本人等已支持范围。
- 缺父部门、循环部门关系、未知岗位/权限、重复编码、与已有非受管账号冲突均失败，不静默创建半套关系。

跳过：若仅由初始超管登录后在后台配置组织，可跳过；普通员工尚不能正常按职责使用。不要为解决业务下拉查询而给员工授予整个系统管理权限。

JSON 顶层包含 `dataset/departments/positions/roles/users`；父部门通过 `parent_code` 引用。用户指定 `dept_code/role_codes/position_codes`，`password_env` 可选，不能传明文 `password` 或 `is_superuser`。示例口令变量为 `ORG_WAREHOUSE_PASSWORD`，设置后优先使用，未设置或省略字段时按账号采用默认值。`data_scope`：1本人、2本部门及以下、3全部。权限使用现有菜单中的精确标识，不支持通配符，自动包含菜单祖先。

相同数据集和相同内容可重复导入；内容、现有名称/层级/角色权限或用户关联有冲突则拒绝，不覆盖人工调整。同数据集不能随意换内容，新增批次使用经审核的新数据集标识；新标识也不会绕过既有记录冲突检查。初始化标记保存在 `sys_param` 的 `zhicang_init_` 受管键中，不进入匿名配置或普通参数编辑。

### 步骤6：执行只读验收

```bash
uv run main.py init-check --env=prod
```

检查：数据库版本/必需模型表结构、必要参数和产品配置有效性、进销存入口与字典、启用超管、组织/角色/岗位/菜单引用完整性、Agno/调度辅助表及 Redis 连通性。不会代替企业权限审核或检查每个业务菜单是否已授权。

仅排查数据库时可加 `--database-only` 明确跳过 Redis，结果 `redis_checked=false`；这不是完整上线验收。启动时数据库检查同样只读，Redis 连接由后续运行链路检查。

无商品、无业务单据是生产新库的正常状态，不能因没有演示数据判定部署失败。验收只读，不补数、不修改版本、不重置缓存会话或密码；失败必须先解决再启动。

### 步骤7：构建前端与准备代理

在 `frontend/web/` 中：

```bash
pnpm install --frozen-lockfile
pnpm ts:check
pnpm build:prod
```

将 `dist` 作为完整版本部署到实际 Nginx 静态目录，或发布系统已提供的同版本产物。不要只替换 `index.html` 而遗漏哈希 JS/CSS/图片，也不要在流量访问时不受控地先删旧资源再复制。

- 项目当前 Web 基础路径为 `/web/`，Nginx 路径、ICO 和前端基础路径保持一致。
- 修改 Nginx 示例中的 `service.fastapiadmin.com` 为实际域名，准备 `server.pem`/`server.key` 或按配置使用对应证书文件。
- `/api/v1` 正确转发后端并传递可信的 Host/协议/客户端地址；部署完成先校验代理配置，再启用公网流量。

跳过风险：白屏、404、旧版本缓存、证书加载失败、HTTPS 循环重定向或502。按 Network/代理错误日志区分前端资源、上游连接和协议问题，不靠清空业务库解决。

### 步骤8：启动与验收

在 `backend/` 中：

```bash
uv run main.py run --env=prod
```

由进程管理器或容器管理实际常驻进程。启动只检查和运行，不进行第4/5步的数据初始化。

- 访问 `https://实际域名/web/`，检查登录、图标、首页及请求。
- 访问 `https://实际域名/api/v1/healthz`，期望200及 `{"status":"ok"}`；此接口只是最小进程存活探针，不代表账实核对、所有依赖或业务验收完成。
- 使用部署管理员登录，核对初始密码和权限；使用普通业务账号验证仅能访问获授权功能。
- 未认证的接口文档返回401、普通用户访问超管专属接口返回403，是预期保护行为，不应为“修复部署”而关闭鉴权。

## 5. 已有库升级与正常重启

### 已有库升级

1. 确定维护窗口并停止写入，备份数据库、上传文件和所需密钥，确认恢复方案。
2. 发布同版本代码及完整迁移文件，核对环境；缺少历史迁移时停止，不能删除 `alembic_version` 或直接 `stamp head` 掩盖问题。
3. 显式运行已存在的命令 `uv run main.py upgrade --env=prod`，只应用已提交迁移。
4. `init-db --env=prod --dry-run` 后按需要执行 `--apply`，用于检查/补必要基础数据和辅助表；已有企业配置和业务记录不重写。
5. 仅旧版菜单结构升级需要 `menu-upgrade`；仅补进销存节点需要 `inventory-menu-init`。若新版 `init-db` 已覆盖补菜单，则不要求重复执行，两者应保持幂等。
6. `init-check --env=prod` 通过后启动新版本，再切换流量并核对普通角色菜单和业务。

迁移失败保留原始错误及当前版本，不盲目重试可能已部分提交的 DDL；回滚使用已验证的数据库/文件恢复方案，不能承诺仅回退代码就能恢复旧结构。

菜单同步完成后仍需核对角色授权并退出重新登录。当前进销存同步会为已有 `SUPER_ADMIN`、`ADMIN` 角色补齐已交付权限，不会给所有普通角色自动授权；修改 JSON 也不会无条件覆盖数据库里的既有路径、组件等配置。开发时的菜单维护和测试步骤见开发指南。

### 正常重启

同一版本且数据库已经验收时，只运行 `uv run main.py run --env=prod` 或容器/服务重启，不重复导入组织或业务数据。

## 6. 独立业务数据导入，不属于初始化

独立脚本在dev/prod都可运行，不随系统初始化或启动执行。新增普通账号默认密码为 `zcy123456@#`，可用 `INVENTORY_DATA_PASSWORD` 覆盖。先备份并审核预检；生产写入将真实影响库存、成本、应收应付和报表：

```bash
uv run python scripts/import_inventory_data.py --env=dev --dry-run
uv run python scripts/import_inventory_data.py --env=dev --apply
uv run main.py init-check --env=dev

# 生产只读预检不需要确认开关；实际写入须显式确认
uv run python scripts/import_inventory_data.py --env=prod --dry-run
uv run python scripts/import_inventory_data.py --env=prod --apply --confirm-production
```

- 前提是目标库的必要初始化已完成；脚本只检查，不调用建表、迁移或补种子。
- 内容涵盖正常组织、岗位、角色、用户，商品分类/商品、客户/供应商/仓库，以及近期采购、销售、退货、期初库存和盘点。
- 先生成组织与档案，再按依赖顺序和合法业务日期创建/确认单据，形成库存、成本、应收应付和业务审计记录；不直接伪造余额或手工拼账。
- 编码、名称、用户名、备注均无D哈希、演示前缀或后缀。使用G001、C01、S01、W01等正常编码、公司总部/采购部等组织名称和zhangming/liwei等普通用户名；单号仍由标准业务编号服务生成。
- 相同批次重复执行跳过、不重复记账；不同批次遇到既有编码、用户名等冲突直接失败，不复用、不覆盖、不自动加后缀改名。日期基准可固定，不能每天重跑自动追加。
- 生产允许人工导入，`--apply` 时必须额外提供 `--confirm-production`；默认和 `--dry-run` 均只读。没有清库重置开关。
- 这些记录写入后与正常业务同等生效，不是隔离沙箱。用于展示素材时须脱敏，不对外将样例经营数字冒充企业真实经营成果。

默认数据集 `standard-v1`，可用 `--dataset` 指定独立标识，用 `--base-date YYYY-MM-DD` 固定业务日期（不能晚于当天）；省略时首次采用上海时区当天。相同数据集重跑沿用首次日期、直接跳过，不重复记账；显式更换日期报冲突。不要通过换标识反复填充同一个业务库。

当前一组生成6部门、6岗位、6业务角色、10普通用户、6分类、30商品、10客户、8供应商、3仓库，以及84张业务单据：采购入库36、销售出库36、采购退货3、销售退货3、期初3、盘点3。采购/销售中各含3草稿、3已作废，其余按服务确认；同时形成真实库存流水、应收应付。包含库存不足/超上限预警样本。组织与业务在同一事务提交，不提供清库重置命令。

需要覆盖默认值时，Windows PowerShell 可用隐藏输入传入口令，避免在命令历史中写明文（可选，在 `backend/` 执行）：

```powershell
$secret = Read-Host "导入账号初始口令" -AsSecureString
$env:INVENTORY_DATA_PASSWORD = [System.Net.NetworkCredential]::new("", $secret).Password
try {
    uv run python scripts/import_inventory_data.py --env=dev --dry-run
    if ($LASTEXITCODE -ne 0) { throw "业务数据预检失败" }
    uv run python scripts/import_inventory_data.py --env=dev --apply
    if ($LASTEXITCODE -ne 0) { throw "业务数据导入失败" }
} finally {
    Remove-Item Env:INVENTORY_DATA_PASSWORD -ErrorAction SilentlyContinue
    $secret.Dispose()
}
```

企业组织导入时可将变量名换成文件中对应的 `password_env` 来覆盖默认口令。命令结果 `created.accounts` 返回普通用户名，不输出口令。后台新增用户未指定密码时同样按账号使用默认值；Excel导入普通用户默认值为 `zcy123456@#`，可由 `PASSWORD_IMPORT_DEFAULT` 配置覆盖，更新已有用户资料不重置密码。

批次标识只用于独立导入记录，不嵌入业务字段。记录保存在受管参数键 `zhicang_init_import_inventory_<dataset>`，包含首次日期、数量与本批组织/业务行ID；组织关联记录为 `zhicang_init_org_import-<dataset>`，不进入匿名参数缓存。相同标识已完成时直接跳过，不会自动恢复被人工删除的数据；`--dataset` 不是批量造重复业务的开关。

### 历史专项维护：旧D前缀数据清理（非部署步骤）

本节只用于已存在旧批次且经过审核确认的环境。新空库、正常重启和新的业务样例导入均不需要执行；下述本地历史执行记录不代表其他环境已清理。

旧 `main.py inventory-demo-init` 已移除，原有数据不会随升级、初始化或新导入自动删除。先运行只读核查：

```bash
uv run python scripts/audit_legacy_inventory.py --env=dev --report /secure/legacy-inventory.json
```

报告文件必须不存在、父目录须已准备；脚本拒绝覆盖文件。核查以旧完成标记、精确批次编码、创建人、单据来源及关联主键限定范围，不使用 `LIKE 'D%'` 删除。报告列出组织/档案/单据/明细/库存/往来/日志、外键及已知多态交叉引用，只含必要主键，不读取账号密码。

清理必须先人工审核清单、停止相关写入并备份受影响数据，获确认后再按依赖处理。存在跨批业务、资金核销或外部引用时不得直接删除；全局单据序列不回退，缓存会话、辅助表及文件仍需额外核对。当前审计脚本不提供删除能力，也不冒充已完成备份或清理。

审核确认后，可使用独立清理脚本。备份目录须事先创建、为空且仅维护账号可访问，禁止放入代码仓库；先默认预检，确认维护窗口后才加写入开关：

```bash
uv run python scripts/cleanup_legacy_inventory.py --env=dev --approved-report /secure/legacy-inventory.json --backup-dir /secure/legacy-backup --dataset standard-v1
uv run python scripts/cleanup_legacy_inventory.py --env=dev --approved-report /secure/legacy-inventory.json --backup-dir /secure/legacy-backup --dataset standard-v1 --apply --maintenance-confirmed
```

- 仅支持MySQL实际清理与SQLite测试，PostgreSQL不自动执行。MySQL须安装匹配的 `mysqldump`，所有数据表须为InnoDB；备份或Redis不可用即停止，不跳过备份。
- 获取维护互斥锁、锁定表行/索引范围，重新核对目标数据库、精确主键清单、引用、超管标志、资金核销和AI数据。清单变化、外部引用或额外AI记录均拒绝执行。
- 删除前生成完整逻辑备份 `database-before.sql`、带类型的目标行快照 `target-rows.json`、目标账号会话备份和 `prepared.json`，回读校验SHA-256。备份包含敏感数据，访问权限须与生产凭据同级；命令不回显密码。
- 只按批准主键依赖顺序物理清理，保持外键检查开启；在同一事务核对全部目标无残留、所有非目标行指纹未变化，失败回滚。仅撤销目标账号会话，不清空Redis，未修改全局单据编号。
- 成功提交后生成 `completed.json`；若SQL提交后报告写入失败，先只读核对数据库和已有文件，不能盲目重跑。SQL回滚时已撤销的目标会话不会自动恢复，账号可重新登录。
- 2026-10-16已在本地 `localhost/fastapiadmin` 按确认清单清理 `standard-v1 / D8acb53ec8f`：旧批次目标行及2条标记均无残留，原有账号与业务行指纹保留，剩余库存数量/金额与流水一致，数据库及Redis验收通过，后端已恢复。本次没有导入新业务数据。

完整SQL备份是本次清理前快照，不是当前库；恢复将影响备份之后的正常业务。恢复前须另行审核停机窗口与恢复方案，不直接对正在运行的库执行整库覆盖。已验证备份文件哈希和目标快照，不冒充已完成云端灾备恢复演练。

## 7. Docker Compose 执行顺序

当前 `docker/backend/Dockerfile` 使用 pip 安装依赖，容器内不保证有 uv，因此容器命令使用 `python main.py ...`。在仓库 `docker/` 目录操作。

1. 检查 `docker/.env`、后端生产配置/密钥注入、真实域名证书及持久化目录。Compose 已显式转发必填 `SECRET_KEY`，关闭 `DEBUG` 并指定 MySQL；未设置密钥时解析即失败。`.env` 仍不会自动把其他任意变量传入容器，组织/演示口令需显式 `run -e 变量名` 转发。
2. 按 Compose bind mount 配置预先准备 MySQL/Redis 数据目录、上传目录和证书目录，不覆盖已有目录数据。
3. 构建后端镜像，仅启动基础依赖：

```bash
docker compose --env-file .env build backend
docker compose --env-file .env up -d mysql redis
docker compose --env-file .env ps
```

4. 确认 MySQL/Redis 健康后，在同一镜像、同一网络及环境中运行一次性初始化。生产建议先在宿主进程环境注入独立口令，再通过 `run -e INIT_ADMIN_PASSWORD` 转发变量，不在命令里写密码明文；未提供时采用上述账号默认初始密码，不交互询问。

```bash
docker compose --env-file .env run --rm --no-deps backend python main.py init-db --env=prod --dry-run
docker compose --env-file .env run --rm --no-deps backend python main.py init-db --env=prod --apply
docker compose --env-file .env run --rm --no-deps backend python main.py init-check --env=prod
```

需要真实组织导入时，在验收前额外挂载受控组织资料，并以第4节命令导入；不把包含密码的资料打入公开镜像。

5. 发布已构建的 Web 产物至当前 Nginx 映射目录 `docker/nginx/web/dist`，校验证书、配置和目录权限后启动应用：

```bash
docker compose --env-file .env up -d backend nginx
docker compose --env-file .env logs --tail=100 backend
docker compose --env-file .env ps
```

注意：

- 当前 `deploy.sh` 仍直接构建并启动全部服务，未插入上述显式初始化。新部署请使用本节手动流程；尚未初始化时直接使用它启动应用会失败，不宣称已提供新流程一键入口。
- 当前 MySQL 映射 `docker/mysql/init` 仅在 MySQL 数据目录首次为空时由数据库镜像执行，不能代替应用迁移、系统种子或演示数据命令；已有卷时不会重新执行。
- 当前 Nginx `depends_on` 只要求后端容器已启动，不等于业务验收通过，发布流程仍需检查后端实际就绪。
- 不用 `docker compose down -v`、删除 MySQL 数据目录或清空 Redis 全实例作为初始化失败的默认解决办法。

## 8. 跳过、异常与解决办法

独立初始化命令使用 `DeploymentError` 和以下错误码。数据库驱动等未分类异常统一为 `INIT_STAGE_FAILED: 异常类型`，避免泄露连接凭据；启动日志中的驱动消息可能随数据库版本变化。

| 场景 | 当前可能表现 / 目标错误 | 是否允许跳过及解决办法 |
| --- | --- | --- |
| 发布代码不完整/版本过旧 | `No such command 'init-db'` 或 `No such option '--apply'` | 不能继续；确认发布版本、执行目录和依赖环境，不能改库绕过 |
| 依赖缺失 | `ModuleNotFoundError`、uv/pip 安装错误 | 不跳过；在正确目录按锁文件安装，核对 Python/安装源/网络 |
| 生产配置无效或显式密码不合法 | `INIT_CONFIG_INVALID`、`INIT_PASSWORD_REQUIRED`，退出2 | 修复配置/注入方式；未设置密码变量时采用账号默认值，显式空值或弱密码拒绝执行 |
| 数据库不可达或库不存在 | `OperationalError`、连接拒绝、超时、`Unknown database` | 不跳过；查数据库/云安全组/内网地址/库名/账号权限 |
| 数据库账号权限不足 | `Access denied`、DDL/DML 权限错误 | 不用运行账号临时升为全局root；由受控迁移账号完成初始化 |
| Redis 连接或认证失败 | 验收报 `INIT_REDIS_UNAVAILABLE`，退出3；启动可能记录驱动异常 | 不跳过；检查密码、端口和容器服务名。登录会话及调度依赖Redis，不能带病启动 |
| 应用未初始化 | `APP_NOT_INITIALIZED`，命令退出3 | 启动拒绝；先运行显式初始化和验收，不允许 run 自动建表 |
| 迁移缺失或分支不一致 | `Can't locate revision identified by ...`、多head、版本不匹配 | 停止；恢复同版本完整迁移链并核对实际结构，禁止自动删除版本或盲目stamp |
| 非空无版本/部分结构库 | `INIT_SCHEMA_CONFLICT`，退出3 | 不当成空库；备份、查历史来源并制定受控基线/修复方案 |
| JSON种子/组织文件错误 | `INIT_DATA_INVALID`，退出2 | 修复格式、父节点、编码与引用；不回显原始敏感输入，不静默跳过坏数据 |
| 重复基础键或账号冲突 | `INIT_DATA_CONFLICT`，退出3；驱动约束异常归类执行失败 | 组织导入精确一致才跳过；基础种子保留已有配置，重复/删除键报错，不覆盖密码和授权 |
| 产品配置重复/损坏 | 当前 `产品配置键重复，请超管修复` / `产品配置无效，请超管修复` | 备份并核对保留键记录和JSON版本，不手工全量重置已发布配置 |
| AI或调度辅助表缺失 | `INIT_AUX_SCHEMA_INVALID`，退出3 | 显式运行 `init-db --apply` 补缺；已有辅助表结构不兼容须受控迁移，不通过重试强改 |
| 并发初始化 | `INIT_LOCKED`，退出3 | 等待作业完成，核对锁持有者；MySQL/PG采用数据库咨询锁，SQLite本地文件锁，不能随意删除有效锁文件 |
| 初始化中途失败 | `INIT_STAGE_FAILED`，退出4 | 核对已提交DDL及数据，预检后修复/恢复，不能承诺整体回滚；脱敏错误不足定位时由维护人员安全排查，不把密钥贴到日志 |
| 部门岗位用户未导入 | 超管可登录，但普通人员没有账号、岗位或菜单 | 允许企业暂缓；后续显式导入或后台配置，不算全部权限验收完成 |
| 演示数据未导入 | 商品/报表为空，首页已授权领域显示零业务 | 生产正常、允许跳过；不要为填满首页在生产伪造单据 |
| 生产导入未确认 | 参数错误，退出2 | 先审核只读预检，确认影响后在独立脚本显式加 `--confirm-production` |
| 业务数据导入冲突 | `IMPORT_DATA_CONFLICT`，退出3 | 核对编码/用户名，不能通过更换批次标识覆盖或自动改名 |
| 单据记账校验失败 | 库存不足、原单不可退、期初已存在、盘点快照冲突等业务异常 | 修复演示数据顺序/数量/日期，继续使用业务服务，不绕过校验直接改余额 |
| 上传目录不可写 | `PermissionError`、存储节点根目录错误 | 修复正确挂载目录与运行账号权限，不给整个服务器目录开放写权限 |
| 登录/业务权限不足 | 401、403；超管专属接口拒绝普通用户 | 核对账号、角色、数据范围及重新登录；不把所有员工设为超管 |
| Web空白、资源404或代理502 | 浏览器Network/控制台、Nginx错误日志 | 核对完整产物、`/web/`路径、上游服务/端口、缓存与证书；不改业务库 |
| HTTPS循环重定向 | 反复301/307 | 核对代理协议头、可信代理及TLS终止层，不直接关闭生产安全策略 |

## 9. 最终验收清单

- [ ] 首次空库初始化成功，表结构/版本及系统必需数据一致。
- [ ] 重复初始化不新增重复记录、不改密码、不覆盖授权和产品配置。
- [ ] 缺表/缺迁移/配置冲突时失败且退出码非0，run 不自动修复。
- [ ] 正常重启未执行初始化或迁移，辅助组件也不在运行时补建缺失表。
- [ ] 企业部门、岗位、角色、用户关联正确，普通账号不能访问超管专属功能。
- [ ] 生产样例数据导入已明确审核且影响已确认；账号已安全改密，真实凭据和密钥未提交仓库。
- [ ] Web资源、HTTPS、上传持久化、登录及实际业务权限验证完成。
- [ ] 备份、版本记录和恢复操作已验证，初始化异常和跳过项均有明确记录。

实现验证：`backend/tests/test_deployment_init.py` 使用独立临时 SQLite 和真实 CLI 子进程验证建库、幂等、组织导入、演示记账、只读验收、缺表拒绝启动与错误脱敏，不写开发数据库。上述清单仍需在实际部署环境逐项验收，尤其是 MySQL/PostgreSQL 权限、并发锁、Redis、Docker、代理及备份恢复，不能表述为已完成生产验收。
