"""按业务编码导入组织权限，不使用固定ID、不覆盖既有账号。"""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_db_session
from app.modules.system.dept.model import DeptModel
from app.modules.system.menu.model import MenuModel
from app.modules.system.params.model import ParamsModel
from app.modules.system.position.model import PositionModel
from app.modules.system.role.model import RoleMenusModel, RoleModel
from app.modules.system.user.model import UserModel, UserPositionsModel, UserRolesModel
from app.utils.password_util import PwdUtil

from .common import MANIFEST_PREFIX, DeploymentError, initialization_lock, password_from_env, validate_environment


class NamedRecord(BaseModel):
    """导入自然键与显示名，不开放数据库主键和审计字段。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=64)
    order: int = Field(default=1, ge=0, le=9999)


class DepartmentInput(NamedRecord):
    """部门父项用编码引用，导入前检测循环。"""

    parent_code: str | None = Field(default=None, max_length=64)


class RoleInput(NamedRecord):
    """数据范围只采用当前框架实际支持的三种取值。"""

    data_scope: Literal[1, 2, 3] = 1
    permissions: list[str] = Field(default_factory=list, max_length=500)


class UserInput(BaseModel):
    """可用环境变量覆盖默认口令，不允许明文密码或超管标志。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    username: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=32)
    dept_code: str = Field(min_length=2, max_length=64)
    role_codes: list[str] = Field(min_length=1, max_length=20)
    position_codes: list[str] = Field(default_factory=list, max_length=20)
    password_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{2,63}$")


class OrganizationInput(BaseModel):
    """数据集标识固定导入契约，同标识不能悄悄更换权限内容。"""

    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    departments: list[DepartmentInput] = Field(default_factory=list, max_length=200)
    positions: list[NamedRecord] = Field(default_factory=list, max_length=200)
    roles: list[RoleInput] = Field(default_factory=list, max_length=100)
    users: list[UserInput] = Field(default_factory=list, max_length=1000)


def organization_file(path: Path) -> OrganizationInput:
    """读取受控组织JSON，错误不回显可能含凭据的原始输入。"""
    try:
        if path.stat().st_size > 2_000_000:
            raise ValueError("file limit")
        return OrganizationInput.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError) as error:
        raise DeploymentError("INIT_DATA_INVALID", "组织文件格式、字段或文件大小不合法，请核对部署示例", 2) from error


async def manifest(db: AsyncSession, key: str) -> dict[str, Any] | None:
    """受管数据集记录不允许重复、停用或损坏后继续写入。"""
    rows = (await db.scalars(select(ParamsModel).where(ParamsModel.config_key == key))).all()
    if not rows:
        return None
    if len(rows) != 1 or rows[0].is_deleted or rows[0].status != 0:
        raise DeploymentError("INIT_DATA_CONFLICT", "初始化数据集标记重复或不可用")
    try:
        value = json.loads(rows[0].config_value)
        if not isinstance(value, dict):
            raise ValueError("manifest")
        return value
    except (ValueError, TypeError) as error:
        raise DeploymentError("INIT_DATA_CONFLICT", "初始化数据集标记损坏") from error


def add_manifest(db: AsyncSession, key: str, value: dict[str, Any]) -> None:
    """与本批业务在同一事务记录结果，不保留密码。"""
    db.add(
        ParamsModel(config_name="部署初始化数据集", config_key=key, config_value=json.dumps(value, ensure_ascii=False), config_type=True, status=0, description="仅初始化命令维护，不进入匿名配置缓存")
    )


async def import_organization(db: AsyncSession, spec: OrganizationInput, apply: bool = False) -> dict[str, Any]:
    """先完整预检引用和冲突，再在调用方事务中写入，重跑不覆盖授权。"""
    key = f"{MANIFEST_PREFIX}org_{spec.dataset}"
    fingerprint = hashlib.sha256(spec.model_dump_json().encode()).hexdigest()
    previous = await manifest(db, key)
    if previous and previous.get("fingerprint") != fingerprint:
        raise DeploymentError("INIT_DATA_CONFLICT", "相同组织数据集标识的内容已改变，请人工审核")

    async def mapping(model: Any, field: str) -> dict[str, Any]:
        """所有自然键包含软删除行，避免复用已删除编码。"""
        rows = (await db.scalars(select(model))).all()
        keys = [getattr(row, field) for row in rows]
        if len(keys) != len(set(keys)):
            raise DeploymentError("INIT_DATA_CONFLICT", f"{model.__tablename__}.{field} 存在重复自然键")
        return {getattr(row, field): row for row in rows}

    departments = await mapping(DeptModel, "code")
    positions = await mapping(PositionModel, "code")
    roles = await mapping(RoleModel, "code")
    users = await mapping(UserModel, "username")
    menus = {row.id: row for row in (await db.scalars(select(MenuModel).where(MenuModel.is_deleted.is_(False), MenuModel.status == 0))).all()}
    permission_ids: dict[str, set[int]] = {}
    for row in menus.values():
        if row.permission:
            permission_ids.setdefault(row.permission, set()).add(row.id)
    role_menus: dict[int, set[int]] = {}
    user_roles: dict[int, set[int]] = {}
    user_positions: dict[int, set[int]] = {}
    for role_id, menu_id in (await db.execute(select(RoleMenusModel.role_id, RoleMenusModel.menu_id))).all():
        role_menus.setdefault(role_id, set()).add(menu_id)
    for user_id, role_id in (await db.execute(select(UserRolesModel.user_id, UserRolesModel.role_id))).all():
        user_roles.setdefault(user_id, set()).add(role_id)
    for user_id, position_id in (await db.execute(select(UserPositionsModel.user_id, UserPositionsModel.position_id))).all():
        user_positions.setdefault(user_id, set()).add(position_id)

    collections = {"departments": spec.departments, "positions": spec.positions, "roles": spec.roles, "users": spec.users}
    for label, items in collections.items():
        names = [item.username if isinstance(item, UserInput) else item.code for item in items]
        if len(names) != len(set(names)):
            raise DeploymentError("INIT_DATA_INVALID", f"{label} 含重复业务编码", 2)
    dept_specs = {row.code: row for row in spec.departments}
    ordered_departments: list[DepartmentInput] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(code: str) -> None:
        """按父项先后排序，缺父项及循环均拒绝。"""
        if code in visiting:
            raise DeploymentError("INIT_DATA_INVALID", "部门存在循环引用", 2)
        if code in visited:
            return
        if code not in dept_specs:
            row = departments.get(code)
            if row is None or row.is_deleted or row.status != 0:
                raise DeploymentError("INIT_DATA_INVALID", "引用了不存在或停用的部门", 2)
            return
        visiting.add(code)
        item = dept_specs[code]
        if item.parent_code:
            visit(item.parent_code)
        visiting.remove(code)
        visited.add(code)
        ordered_departments.append(item)

    for code in dept_specs:
        visit(code)

    desired_menus: dict[str, set[int]] = {}
    for item in spec.roles:
        desired: set[int] = set()
        for permission in item.permissions:
            if permission not in permission_ids or "*" in permission:
                raise DeploymentError("INIT_DATA_INVALID", f"未知或通配权限标识：{permission}", 2)
            desired.update(permission_ids[permission])
        pending = list(desired)
        while pending:
            parent = menus[pending.pop()].parent_id
            if parent is not None:
                if parent not in menus:
                    raise DeploymentError("INIT_DATA_CONFLICT", "菜单祖先不存在或停用")
                if parent not in desired:
                    desired.add(parent)
                    pending.append(parent)
        desired_menus[item.code] = desired

    def unchanged(row: Any, values: dict[str, Any]) -> None:
        """已有行只能精确匹配，不覆盖软删除、状态及用户自定义字段。"""
        if row.is_deleted or row.status != 0 or any(getattr(row, field) != value for field, value in values.items()):
            raise DeploymentError("INIT_DATA_CONFLICT", "既有组织/账号与导入内容冲突，不会覆盖")

    reverse_dept = {row.id: code for code, row in departments.items()}
    for item in spec.departments:
        if item.code in departments:
            row = departments[item.code]
            unchanged(row, {"name": item.name, "order": item.order})
            if reverse_dept.get(row.parent_id) != item.parent_code:
                raise DeploymentError("INIT_DATA_CONFLICT", "既有部门父项与导入不一致")
    for item in spec.positions:
        if item.code in positions:
            unchanged(positions[item.code], {"name": item.name, "order": item.order})
    for item in spec.roles:
        if item.code in roles:
            row = roles[item.code]
            unchanged(row, {"name": item.name, "order": item.order, "data_scope": item.data_scope})
            if role_menus.get(row.id, set()) != desired_menus[item.code]:
                raise DeploymentError("INIT_DATA_CONFLICT", "既有角色授权与导入不一致，不会覆盖")
    role_codes = set(roles) | {row.code for row in spec.roles}
    position_codes = set(positions) | {row.code for row in spec.positions}
    for item in spec.users:
        visit(item.dept_code)
        if not set(item.role_codes).issubset(role_codes) or not set(item.position_codes).issubset(position_codes):
            raise DeploymentError("INIT_DATA_INVALID", "用户引用了不存在的岗位或角色", 2)
        for code in item.role_codes:
            if code in roles:
                unchanged(roles[code], {})
        for code in item.position_codes:
            if code in positions:
                unchanged(positions[code], {})
        if item.username in users:
            row = users[item.username]
            unchanged(row, {"name": item.name, "is_superuser": False})
            expected_roles = {roles[code].id for code in item.role_codes if code in roles}
            expected_positions = {positions[code].id for code in item.position_codes if code in positions}
            if (
                reverse_dept.get(row.dept_id) != item.dept_code
                or len(expected_roles) != len(set(item.role_codes))
                or len(expected_positions) != len(set(item.position_codes))
                or user_roles.get(row.id, set()) != expected_roles
                or user_positions.get(row.id, set()) != expected_positions
            ):
                raise DeploymentError("INIT_DATA_CONFLICT", "既有用户组织关联与导入不一致")

    counts = {
        "departments": sum(row.code not in departments for row in spec.departments),
        "positions": sum(row.code not in positions for row in spec.positions),
        "roles": sum(row.code not in roles for row in spec.roles),
        "users": sum(row.username not in users for row in spec.users),
    }
    if not apply:
        return {"dataset": spec.dataset, "mode": "dry-run", "create": counts, "password_env": sorted({row.password_env for row in spec.users if row.username not in users and row.password_env}), "password_policy": "environment-or-account-default"}
    passwords = {row.username: password_from_env(row.password_env, row.username) for row in spec.users if row.username not in users}
    for item in ordered_departments:
        if item.code not in departments:
            row = DeptModel(code=item.code, name=item.name, order=item.order, parent_id=departments[item.parent_code].id if item.parent_code else None, status=0)
            db.add(row)
            await db.flush()
            departments[item.code] = row
    for item in spec.positions:
        if item.code not in positions:
            row = PositionModel(**item.model_dump(), status=0)
            db.add(row)
            await db.flush()
            positions[item.code] = row
    for item in spec.roles:
        if item.code not in roles:
            row = RoleModel(**item.model_dump(exclude={"permissions"}), status=0)
            db.add(row)
            await db.flush()
            roles[item.code] = row
            db.add_all(RoleMenusModel(role_id=row.id, menu_id=menu_id) for menu_id in desired_menus[item.code])
    for item in spec.users:
        if item.username not in users:
            row = UserModel(
                username=item.username, name=item.name, dept_id=departments[item.dept_code].id, is_superuser=False, status=0, password=await PwdUtil.ahash_password(passwords[item.username])
            )
            db.add(row)
            await db.flush()
            db.add_all(UserRolesModel(user_id=row.id, role_id=roles[code].id) for code in set(item.role_codes))
            db.add_all(UserPositionsModel(user_id=row.id, position_id=positions[code].id) for code in set(item.position_codes))
    if previous is None:
        add_manifest(db, key, {"fingerprint": fingerprint, "dataset": spec.dataset})
    await db.flush()
    return {"dataset": spec.dataset, "mode": "apply", "created": counts}


async def initialize_organization(path: Path, apply: bool = False) -> dict[str, Any]:
    """显式导入真实组织，不从应用启动中调用。"""
    from .check import check_installation

    validate_environment()
    spec = organization_file(path)
    await check_installation()
    if not apply:
        async with async_db_session() as db:
            return await import_organization(db, spec)
    async with initialization_lock(), async_db_session() as db, db.begin():
        return await import_organization(db, spec, True)
