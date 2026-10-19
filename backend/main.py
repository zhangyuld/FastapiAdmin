import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import typer
import uvicorn
from alembic import command
from alembic.config import Config
from typer.main import Typer


class EnvironmentEnum(str, Enum):
    """CLI先选择环境，避免为了导入应用枚举而提前加载dev配置。"""

    DEV = "dev"
    PROD = "prod"


fastapiadmin_cli: Typer = typer.Typer()
alembic_cfg: Config = Config(file_="alembic.ini")


@fastapiadmin_cli.command(
    name="run",
    help="启动 FastapiAdmin 服务, 运行 python(或uv run) main.py run --env=dev 不加参数默认 dev 环境",
)
def run(
    env: Annotated[EnvironmentEnum, typer.Option("--env", help="运行环境 (dev, prod)")] = EnvironmentEnum.DEV,
) -> None:
    """按指定环境加载配置并启动 Uvicorn（dev 环境 DEBUG=True 自动开启 reload）。

    参数:
    - env (EnvironmentEnum): 运行环境，对应 `--env`。

    返回:
    - None
    """
    os.environ["ENVIRONMENT"] = env.value

    from app.utils.banner import worship

    typer.secho(message=f"{worship()}", fg=typer.colors.GREEN)
    from app.config.setting import settings

    uvicorn.run(
        app="app:create_app",
        factory=True,
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS,
        log_config=None,
        timeout_graceful_shutdown=5,
    )


@fastapiadmin_cli.command(
    name="revision",
    help="生成新的 Alembic 迁移脚本, 运行 python(或uv run) main.py revision --env=dev",
)
def revision(
    env: Annotated[EnvironmentEnum, typer.Option("--env", help="运行环境 (dev, prod)")] = EnvironmentEnum.DEV,
    message: Annotated[str, typer.Option("--message", "-m", help="迁移说明（进入迁移文件名 slug）")] = "迁移脚本",
) -> None:
    """使用 Alembic 自动生成迁移脚本（autogenerate）。

    参数:
    - env (EnvironmentEnum): 运行环境，用于加载对应数据库模型元数据。
    - message (str): 迁移说明，写入迁移文件 message 与文件名 slug。

    返回:
    - None
    """
    if env == EnvironmentEnum.PROD:
        raise typer.BadParameter("生产禁止生成迁移；请在开发环境生成、审查并提交")
    os.environ["ENVIRONMENT"] = env.value
    command.revision(config=alembic_cfg, autogenerate=True, message=message)
    typer.echo(message="迁移脚本已生成")


@fastapiadmin_cli.command(
    name="upgrade",
    help="应用最新的 Alembic 迁移, 运行 python(或uv run) main.py upgrade --env=dev",
)
def upgrade(
    env: Annotated[EnvironmentEnum, typer.Option("--env", help="运行环境 (dev, prod)")] = EnvironmentEnum.DEV,
) -> None:
    """将数据库升级到 Alembic 最新版本（head）。

    参数:
    - env (EnvironmentEnum): 运行环境。

    返回:
    - None
    """
    os.environ["ENVIRONMENT"] = env.value
    async def apply_committed() -> None:
        """升级同样互斥并保留未知版本，禁止将已有库伪装成空库。"""
        from app.scripts.deployment.common import DeploymentError, initialization_lock, validate_environment
        from app.scripts.deployment.structure import ensure_structure, structure_state

        validate_environment()
        async with initialization_lock():
            if (await structure_state())["empty"]:
                raise DeploymentError("APP_NOT_INITIALIZED", "空库请使用 init-db，不单独执行增量升级")
            await ensure_structure()

    _execute_deployment(env, apply_committed)
    typer.echo(message="所有迁移已应用。")


@fastapiadmin_cli.command(
    name="menu-upgrade",
    help="将已有数据库菜单升级为进销存菜单结构，运行 uv run main.py menu-upgrade --env=dev",
)
def menu_upgrade(
    env: Annotated[EnvironmentEnum, typer.Option("--env", help="运行环境 (dev, prod)")] = EnvironmentEnum.DEV,
) -> None:
    """幂等迁移已有菜单数据，保留页面节点 ID、组件和权限标识。"""
    os.environ["ENVIRONMENT"] = env.value

    from app.scripts.inventory_menu import run_inventory_menu_upgrade

    changed = asyncio.run(run_inventory_menu_upgrade())
    typer.echo(message="菜单迁移完成。" if changed else "菜单已是目标结构，无需重复迁移。")


@fastapiadmin_cli.command(
    name="inventory-menu-init",
    help="初始化进销存规划菜单，运行 uv run main.py inventory-menu-init --env=dev",
)
def inventory_menu_init(
    env: Annotated[EnvironmentEnum, typer.Option("--env", help="运行环境 (dev, prod)")] = EnvironmentEnum.DEV,
) -> None:
    """幂等创建进销存目录和停用页面，不覆盖已有菜单配置。"""
    os.environ["ENVIRONMENT"] = env.value

    from app.scripts.inventory_menu import run_inventory_business_menu_setup

    created_count = asyncio.run(run_inventory_business_menu_setup())
    typer.echo(message=f"进销存菜单初始化完成，新增 {created_count} 个节点。")


def _execute_deployment(env: EnvironmentEnum, action: Callable[[], Awaitable[Any]]) -> None:
    """环境必须先于数据库模块加载，统一脱敏报错并释放命令连接。"""
    os.environ["ENVIRONMENT"] = env.value
    try:
        from app.scripts.deployment.common import DeploymentError
    except Exception as error:
        typer.echo(f"INIT_CONFIG_INVALID: {type(error).__name__}，请核对环境配置字段及格式", err=True)
        raise typer.Exit(2) from None

    async def execute() -> Any:
        """所有阶段在同一事件循环中执行，避免异步连接跨循环复用。"""
        from app.core.database import async_engine, engine

        try:
            return await action()
        finally:
            from app.modules.ai.chat import crud

            if crud._db_instance is not None:
                await crud._db_instance.db_engine.dispose()
            await async_engine.dispose()
            engine.dispose()

    try:
        result = asyncio.run(execute())
        if result is not None:
            typer.echo(json.dumps(result, ensure_ascii=False, default=str))
    except DeploymentError as error:
        typer.echo(f"{error.code}: {error.message}", err=True)
        raise typer.Exit(error.exit_code) from error
    except Exception as error:
        # 驱动异常和Pydantic原始输入可能含凭据，终端只输出异常类型。
        typer.echo(f"INIT_STAGE_FAILED: {type(error).__name__}，请核对配置、数据库及部署文档", err=True)
        raise typer.Exit(4) from None


def _validate_mode(apply: bool, dry_run: bool) -> None:
    """默认预检，禁止同时声明写入与只读模式。"""
    if apply and dry_run:
        raise typer.BadParameter("--apply 与 --dry-run 不能同时使用")


@fastapiadmin_cli.command("init-db", help="显式初始化结构与必需数据；默认只读预检")
def init_db(
    env: Annotated[EnvironmentEnum, typer.Option("--env")] = EnvironmentEnum.DEV,
    apply: Annotated[bool, typer.Option("--apply")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """创建必要管理员，环境口令优先，否则采用账号默认初始口令。"""
    _validate_mode(apply, dry_run)
    os.environ["ENVIRONMENT"] = env.value

    async def action() -> dict[str, Any]:
        """已有管理员时不索取或重置其密码。"""
        from app.scripts.deployment.bootstrap import initialize_database
        return await initialize_database(apply)

    _execute_deployment(env, action)


@fastapiadmin_cli.command("init-check", help="只读检查安装结果，不补表或修改数据")
def init_check(
    env: Annotated[EnvironmentEnum, typer.Option("--env")] = EnvironmentEnum.DEV,
    database_only: Annotated[bool, typer.Option("--database-only", help="仅检查数据库，明确跳过Redis网络检查")] = False,
) -> None:
    """默认同时校验Redis连通性，未授权端点不作为失败依据。"""
    async def action() -> dict[str, Any]:
        """复用运行期只读检查。"""
        from app.scripts.deployment.check import check_installation

        return await check_installation(redis=not database_only)

    _execute_deployment(env, action)


@fastapiadmin_cli.command("init-org", help="按受控JSON初始化部门、岗位、角色、用户及关联")
def init_org(
    file: Annotated[Path, typer.Option("--file", exists=True, dir_okay=False)],
    env: Annotated[EnvironmentEnum, typer.Option("--env")] = EnvironmentEnum.DEV,
    apply: Annotated[bool, typer.Option("--apply")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """默认只预检，导入只补缺失记录不覆盖现有授权。"""
    _validate_mode(apply, dry_run)

    async def action() -> dict[str, Any]:
        """读取组织文件及口令环境变量。"""
        from app.scripts.deployment.organization import initialize_organization

        return await initialize_organization(file, apply)

    _execute_deployment(env, action)


if __name__ == "__main__":
    fastapiadmin_cli()
