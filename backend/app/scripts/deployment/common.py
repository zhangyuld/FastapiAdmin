"""初始化错误、只读配置检查与跨进程互斥。"""

import hashlib
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.config.setting import settings
from app.core.database import async_engine

MANIFEST_PREFIX = "zhicang_init_"


class DeploymentError(RuntimeError):
    """向命令行返回可诊断错误，不附带数据库口令或导入密码。"""

    def __init__(self, code: str, message: str, exit_code: int = 3) -> None:
        """记录稳定错误码、脱敏说明和命令退出状态。"""
        self.code, self.message, self.exit_code = code, message, exit_code
        super().__init__(f"{code}: {message}")


def validate_environment() -> None:
    """生产拒绝默认密钥及调试启动，开发环境不改变既有配置。"""
    if settings.ENVIRONMENT == "prod" and (settings.DEBUG or len(settings.SECRET_KEY) < 32 or settings.SECRET_KEY.startswith("fastapiadmin-dev-")):
        raise DeploymentError("INIT_CONFIG_INVALID", "生产环境须关闭 DEBUG 并配置至少32位独立 SECRET_KEY", 2)


def password_from_env(name: str | None, username: str) -> str:
    """显式环境口令优先，未提供时按账号使用统一初始口令。"""
    from app.utils.password_util import PwdUtil

    password = os.environ.get(name, PwdUtil.default_initial_password(username)) if name else PwdUtil.default_initial_password(username)
    if not 8 <= len(password) <= 64 or PwdUtil.check_password_strength(password):
        raise DeploymentError("INIT_PASSWORD_REQUIRED", f"{name or '初始口令'} 必须为8至64位、至少包含两类字符的密码", 2)
    return password


def sqlite_path() -> Path | None:
    """读取 SQLite 实际文件，预检不存在的库时不创建空文件。"""
    if async_engine.dialect.name != "sqlite":
        return None
    database = async_engine.url.database
    return Path(database).resolve() if database and database != ":memory:" else None


@asynccontextmanager
async def initialization_lock() -> AsyncIterator[None]:
    """MySQL/PG使用连接级咨询锁，单机SQLite使用非阻塞文件锁。"""
    dialect = async_engine.dialect.name
    # 同一数据库即使用不同迁移账号连接，也必须争用同一把锁。
    url = async_engine.url
    identity = hashlib.sha256(f"{dialect}:{url.host}:{url.port}:{url.database}".encode()).hexdigest()[:32]
    if dialect in {"mysql", "postgresql"}:
        async with async_engine.connect() as connection:
            key: Any = f"zhicang_init_{identity}" if dialect == "mysql" else int(identity[:15], 16)
            acquire = "SELECT GET_LOCK(:key, 0)" if dialect == "mysql" else "SELECT pg_try_advisory_lock(:key)"
            release = "SELECT RELEASE_LOCK(:key)" if dialect == "mysql" else "SELECT pg_advisory_unlock(:key)"
            if not await connection.scalar(text(acquire), {"key": key}):
                raise DeploymentError("INIT_LOCKED", "另一个初始化任务正在执行")
            try:
                yield
            finally:
                await connection.execute(text(release), {"key": key})
        return
    path = sqlite_path()
    if path is None:
        raise DeploymentError("INIT_CONFIG_INVALID", "显式初始化须使用持久化数据库文件", 2)
    if not path.parent.is_dir():
        raise DeploymentError("INIT_CONFIG_INVALID", "SQLite父目录不存在", 2)
    with Path(f"{path}.init.lock").open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                if not handle.read(1):
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise DeploymentError("INIT_LOCKED", "另一个初始化任务正在执行") from error
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
