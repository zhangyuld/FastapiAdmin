import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.path_conf import SCRIPT_DIR, STATIC_DIR
from app.core.base_model import MappedBase
from app.core.database import async_db_session
from app.core.logger import logger
from app.modules.system.dept.model import DeptModel
from app.modules.system.dict.model import DictDataModel, DictTypeModel
from app.modules.system.menu.model import MenuModel
from app.modules.system.params.model import ParamsModel
from app.modules.system.role.model import RoleModel
from app.modules.system.user.model import UserModel, UserRolesModel
from app.modules.system.versions.model import VersionModel
from app.modules.task.cronjob.node.model import NodeModel
from app.modules.task.storage.node.model import StorageNodeModel
from app.utils.import_util import ImportUtil

# 导入全部模型：与 alembic env.py 保持一致，确保全局 MapperRegistry 的 FK 引用可完整解析
ImportUtil.find_models(MappedBase)


class InitializeData:
    """初始化数据库和基础数据"""

    # 按依赖关系排序：先基础表，再关联表
    prepare_init_models: list[type] = [
        MenuModel,
        DeptModel,
        ParamsModel,
        RoleModel,
        DictTypeModel,
        DictDataModel,
        UserModel,
        UserRolesModel,
        VersionModel,
        NodeModel,
        StorageNodeModel,
    ]

    # 树形模型：JSON 含嵌套 children，需递归创建对象
    _RECURSIVE_TABLES: set[str] = {"sys_menu", "sys_dept"}

    async def init_db(self) -> None:
        """应用数据库迁移并导入种子数据（迁移成功即证明连接正常，失败时异常上抛）"""
        await self.__apply_migrations()

        async with async_db_session() as session, session.begin():
            await self.__init_data(session)

        # 内置本地存储源的根目录（种子节点 host 指向 static/upload），保证开箱可浏览
        (STATIC_DIR / "upload").mkdir(parents=True, exist_ok=True)

    @staticmethod
    async def __apply_migrations() -> None:
        """测试/兼容入口显式调用，不自动生成迁移或删除未知版本。"""
        from app.scripts.deployment.structure import ensure_structure

        await ensure_structure()

    async def __init_data(self, db: AsyncSession) -> None:
        """按依赖顺序初始化各表种子数据（表已有数据则整体跳过，实现幂等）"""
        skipped: list[str] = []
        for model in self.prepare_init_models:
            table_name = model.__tablename__

            data = self.__load_json(table_name)
            if not data:
                logger.info(f"⏭️  跳过 {table_name} 表，无初始化数据")
                continue

            # 已有数据则跳过（汇总到循环结束后一次输出，避免每次启动刷 9 行）
            count = await db.execute(select(func.count()).select_from(model))
            if count.scalar():
                skipped.append(table_name)
                continue

            try:
                if table_name in self._RECURSIVE_TABLES:
                    objs = self.__create_objects_with_children(data, model)
                elif table_name == "sys_dict_data":
                    objs = await self.__create_dict_data_objs(db, data)
                else:
                    objs = [model(**item) for item in data]

                if objs:
                    db.add_all(objs)
                    await db.flush()
                    logger.info(f"✅️ 已向 {table_name} 写入初始化数据")
                else:
                    logger.info(f"⏭️  跳过 {table_name} 表数据初始化（无有效数据）")

            except Exception:
                logger.error(f"❌️ 初始化 {table_name} 表数据失败")
                raise

        if skipped:
            logger.info(f"⏭️  {len(skipped)} 张表已有数据，跳过初始化：{', '.join(skipped)}")

    @staticmethod
    async def __create_dict_data_objs(db: AsyncSession, data: list[dict]) -> list[DictDataModel]:
        """字典数据种子：dict_type_id 通过查询库内字典类型解析。"""
        type_names = {item.get("dict_type") for item in data if item.get("dict_type")}
        result = await db.execute(
            select(DictTypeModel.dict_type, DictTypeModel.id).where(
                DictTypeModel.dict_type.in_(type_names)
            )
        )
        # Row[Tuple[str, int]] 静态类型上不是双元素 (key, value) 元组，dict(rows) 会被类型检查器拒绝；
        # 用下标显式拆出 (dict_type, id) 再构造，运行行为不变且类型清晰
        id_map: dict[str, int] = {row[0]: row[1] for row in result.all()}

        objs: list[DictDataModel] = []
        for item in data:
            dict_type = item.get("dict_type")
            if not isinstance(dict_type, str):  # 与 type_names 的 truthy 过滤一致，同时收窄类型
                continue
            dict_type_id = id_map.get(dict_type)
            if dict_type_id is None:
                logger.warning(f"⚠️  未找到字典类型 {dict_type}，跳过")
                continue
            item["dict_type_id"] = dict_type_id
            objs.append(DictDataModel(**item))
        return objs

    @staticmethod
    def __create_objects_with_children(data: list[dict], model_class: type) -> list:
        """递归创建树形模型实例，处理嵌套 children 并注入 parent_id"""

        def _create(obj_data: dict) -> Any:
            children_data = obj_data.pop("children", [])
            obj = model_class(**obj_data)

            # 子节点通过 relationship 自动设置 parent_id
            if children_data:
                obj.children = [_create(child) for child in children_data]

            return obj

        return [_create(item) for item in data]

    @staticmethod
    def __load_json(filename: str) -> list[dict]:
        """读取并解析种子数据 JSON 文件（不存在则返回空列表）"""
        json_path = SCRIPT_DIR / f"{filename}.json"
        if not json_path.exists():
            return []

        try:
            with open(json_path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"❌️ 解析 {json_path} 失败: {e!s}")
            raise
        except Exception as e:
            logger.error(f"❌️ 读取 {json_path} 失败: {e!s}")
            raise
