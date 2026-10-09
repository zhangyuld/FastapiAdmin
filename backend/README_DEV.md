# 开发步骤

## module新增

  - 在`app.module`下新增对应的模块文件夹
  - 在文件夹内新增`model.py`,`schema.py`,`crud.py`,`service.py`,`controller.py`, `param.py`
    - `model.py`        ORM 模型 - 数据库表定义,可能在上层等地方定义
    - `schema.py`       Pydantic 模型 - 数据验证,做入参,出参等格式处理
    - `crud.py`         数据层 - 数据库操作
    - `service.py`      服务层 - 业务逻辑处理
    - `controller.py`   控制器 - HTTP 请求处理
    - `param.py`        参数模型 - 请求参数,非必需
  - 开发完成后需要在在`app/api/v1/router.py`中导入对应的模块,才能被外部访问到

## 新增菜单处理
  - `backend\sql\sys_menu.json`中新增菜单信息和权限
  - `backend\app\scripts\inventory_menu.py`中调整菜单的状态
  - `backend\tests\test_inventory_menu.py`中`test_only_delivered_inventory_pages_are_enabled().delivered_names`添加菜单

  - 处理完后运行 `uv run main.py inventory-menu-init --env=dev`刷入对应的菜单数据
