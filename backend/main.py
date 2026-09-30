import asyncio
import os
from typing import Annotated

import typer
import uvicorn
from alembic import command
from alembic.config import Config
from typer.main import Typer

from app.common.enums import EnvironmentEnum

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
    command.upgrade(config=alembic_cfg, revision="head")
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


if __name__ == "__main__":
    fastapiadmin_cli()
