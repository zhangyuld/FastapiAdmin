# 库存管理接口与页面

当前库存、库存流水、期初库存、库存盘点前后端已开发，状态为已开发待验收。库存余额和流水复用已有库存记账底座，不直接修改商品表库存。真实 MySQL 并发与目标部署环境验收另行执行。

## 目录与路由

四个业务前缀为 `/inventory/stock/balance`、`log`、`opening`、`check`，与后端目录一致；实际请求沿用框架统一 API 前缀。

页面位于 `views/module_inventory/stock/{kind}/index.vue`，组件名分别为 InventoryStockBalance、InventoryStockLog、InventoryStockOpening、InventoryStockCheck。后端动态菜单提供路由，未新增重复静态路由。

接口和业务类型就近放在模块 API 文件；列表、单据弹窗、商品选择、明细、来源详情和定点数工具留在库存模块。来源详情复用采购、销售的只读弹窗，并独立检查该来源的详情权限和后端数据范围。

## 接口契约

| 模块       | 方法及相对路径              | 输入与行为                                              |
| ---------- | --------------------------- | ------------------------------------------------------- |
| 四个模块   | GET /list、GET /detail/{id} | 分页/详情；单据详情包含 items                           |
| 四个模块   | POST /export                | query、fields、format、sheet_name、filename；返回文件流 |
| 期初、盘点 | POST /create                | warehouse_id、business_date、remark、items；生成草稿    |
| 期初、盘点 | POST /update/{id}           | 完整业务输入和 version                                  |
| 期初、盘点 | POST /delete                | ids、versions；只允许草稿                               |
| 期初、盘点 | POST /confirm/{id}          | version；事务入账                                       |
| 期初、盘点 | POST /void/{id}             | version、void_reason；按原流水冲销                      |
| 盘点       | GET /snapshot               | warehouse_id、goods_ids；新行账面数量、金额、库存版本   |
| 盘点       | POST /refresh/{id}          | version；显式刷新已保存草稿，保留已保存实盘数并递增版本 |

当前库存、流水没有新增、更新或删除接口。余额支持商品、仓库、分类、数量状态、预警及审计筛选；流水另支持业务类型、操作类型、来源单号、业务日期和入账时间。数量三位、成本四位、金额两位，JSON 输出为固定精度字符串。

期初明细输入 goods_id、quantity、unit_cost；盘点明细输入 goods_id、actual_quantity，可选 unit_cost。零库存盘盈必须明确输入成本，零成本允许；非零库存按账面金额/数量比例计算成本。客户端不提交账面快照、差异或成本金额。

## 入账与冲销

- 库存查询为企业共享数据，不按余额或流水创建人做数据范围限制；单据仍沿用框架数据范围，来源详情另行授权。
- 同仓库商品已有有效期初或其他历史库存业务，不允许重新期初初始化。期初全部作废且没有其他库存业务时可重新录入；存在后续流水禁止期初作废。
- 盘点草稿固化账面数量、金额与库存版本；同仓库编辑原行保留快照，仅新增行、更换仓库或显式刷新取得新快照。确认若任一快照变化返回 409，不覆盖他人业务。
- 显式刷新读取已保存草稿，未保存修改会丢弃；前端先提示，再刷新供用户重新核对实盘数。
- 盘盈盘亏按未舍入的库存金额比例计价，全部盘亏结清金额尾差；零差异不生成流水。
- 确认/作废按商品固定顺序锁定所有余额。库存、流水、单据状态、版本、业务日志使用同一请求事务，失败整体回滚，不生成应收应付。
- 盘点作废按原确认数量和金额反向记账，不按当前平均成本重算；数量或金额不足、数量归零残留金额被拦截。

## 导出与权限

当前页、选中数据由前端生成文件，全部数据由后端按当前筛选和字段白名单顺序生成 xlsx/csv。显示标签保持一致，空文件名默认 `页面名称列表_时间戳.格式`。

权限前缀为 `module_inventory:stock_balance:`、`stock_log:`、`stock_opening:`、`stock_check:`。只读模块配置 query/detail/export；单据配置 query/create/update/detail/delete/confirm/void/export。盘点快照读取允许 create 或 update，刷新要求 update。

## 数据迁移与菜单初始化

新增迁移 `2026_10_12_1848_fa28c1122c75.py`，为盘点明细增加可空的 system_stock_amount、balance_version。旧草稿缺少快照时须显式刷新后确认；历史确认单不补造快照。

在 backend 执行：

```powershell
uv run main.py upgrade --env=dev
uv run main.py inventory-menu-init --env=dev
```

开发库已应用迁移并启用四页，补齐 18 个按钮节点；再次初始化新增 0 个节点。默认 SUPER_ADMIN、ADMIN 获得授权，普通角色需独立授权；已有登录会话需要重新登录加载菜单。
