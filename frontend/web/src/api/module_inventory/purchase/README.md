# 采购管理接口约定

前端页面和菜单权限已完成。后端采购入库、原单采购退货已实现列表、详情、草稿创建、更新、删除、导出、确认和作废；采购入库另提供可退数量查询。当前不开放独立采购退货。接口方法仅使用 GET/POST，统一复用框架的认证、异常响应和 ApiResponse 包装。接口路径由请求层统一添加现有 API 前缀。

## 页面及权限

| 页面     | 路由组件                               | 权限前缀                         |
| -------- | -------------------------------------- | -------------------------------- |
| 采购入库 | module_inventory/purchase/in/index     | module_inventory:purchase_in     |
| 采购退货 | module_inventory/purchase/return/index | module_inventory:purchase_return |

页面权限后缀 query；按钮后缀 create、update、detail、delete、confirm、void、export。
菜单由后端动态路由提供，无需增加前端静态路由。更新数据库菜单：
在 backend 目录执行 `uv run main.py inventory-menu-init --env=dev`，再退出重新登录。普通角色还需确认对应页面和按钮已授权。

## 公共接口

以下路径前缀 P 为 /inventory/purchase/inbound 或 /inventory/purchase/return_order。

| 方法 | 路径           | 入参及响应                                                    |
| ---- | -------------- | ------------------------------------------------------------- |
| GET  | P/list         | PurchaseQuery；返回 ApiResponse<PageResult<PurchaseDocument>> |
| GET  | P/detail/{id}  | 返回 ApiResponse<PurchaseDocument>，必须含完整 items          |
| POST | P/create       | PurchaseSaveBody；返回新建 PurchaseDocument                   |
| POST | P/update/{id}  | PurchaseSaveBody，必须带 version                              |
| POST | P/delete       | { ids: number[], versions: Record<number, number> }           |
| POST | P/confirm/{id} | { version: number }                                           |
| POST | P/void/{id}    | { version: number, void_reason: string }                      |
| POST | P/export       | { query, fields, format, sheet_name, filename? }；返回文件流  |

JSON 的 versions 对象键实际为 ID 字符串，后端应按 ID 解析。

查询字段：page_no、page_size、order_no、supplier_id、warehouse_id、business_date 日期区间、status，以及框架已有 created_by、updated_by、created_time、updated_time 审计筛选。退货增加 source_order_no。
查询日期区间的序列化方式沿用请求层，后端与基础档案查询保持一致。
公共单据、明细和保存输入定义位于 client.ts；关联退货响应位于 in.ts，具体请求入参紧邻接口函数，不再使用独立 types.ts。

## 保存草稿

示例采购入库请求：

```json
{
  "supplier_id": 1,
  "warehouse_id": 1,
  "business_date": "2026-10-10",
  "remark": "",
  "items": [{ "goods_id": 1, "quantity": "2.000", "unit_price": "12.3456" }]
}
```

退货必须填写 return_reason、source_purchase_in_id，每行必须传 source_purchase_in_item_id。来源必须为有数据权限的已确认采购入库单。无来源、无来源行的请求返回 422，不能保存独立退货。
更新必须带 version；允许切换来源，但必须完整提交新来源及全部明细。前端从新来源重新读取快照，不提供清除来源改为独立退货入口。
前端不提交 order_no、status、total_amount、商品快照、成本及审计字段。单号由后端生成，编辑也不可修改。
服务端从档案及来源单读取快照，校验明细非空、重复商品或来源行、供应商及仓库状态、数据权限、数量与金额范围。

金额建议以字符串返回：数量三位、单价四位、金额两位。前端使用整数缩放做预览，按行四舍五入后求和；最终以服务端 Decimal 计算和返回为准。

## 原单退货入账

退货供应商、仓库、商品和单价必须与来源一致，后端逐行验证，拒绝伪造的来源关系和价格。商品名称等快照取自原入库明细，成本取自原库存确认流水，不能用当前商品参考成本替代。
草稿保存时校验可退数量，但不占用；确认时重新加锁校验并计算实际金额、成本。多个草稿不预占同一额度，先确认生效，后确认超过剩余额度时返回 409。

多次部分退货按原入账金额累计分摊到分：

```text
累计目标金额 = 四舍五入(原行金额 × (已退数量 + 本次数量) / 原数量, 2)
本次金额 = max(0, 累计目标金额 - 已退金额)
成本采用相同分摊算法，原金额读取库存确认流水的 cost_amount。
```

只统计已确认且未删除的退货。作废释放数量和金额额度；乱序作废后本次分摊不产生负额，全部退完补齐原金额。草稿金额为当前预估，确认时可能因其他退货生效而变化；详情的行金额及合计以服务端固化结果展示，不再按数量乘单价重算。

确认生成负数量、负成本的库存流水和负金额应付，更新确认状态、版本和业务日志；作废生成原流水全量反向记录和正向应付，关联 reversal_log_id、reversal_id，原记录永久保留。退货应付有核销时禁止直接作废。
库存出库不允许负数量、负金额，也不能在数量归零后留下非零金额。退货本身作废可以恢复库存，但仍校验金额范围及原入账记录完整性。

## 退货来源及可退数量

GET /inventory/purchase/inbound/returnable/{id}?exclude_return_id={当前退货单ID}

返回 ApiResponse<PurchaseDocument>，必须含 supplier_name、warehouse_name、order_no 和 items；每条明细必须含入库明细 id、商品快照、原单价、returnable_quantity。
查询沿用 module_inventory:purchase_in:detail 权限及入库单数据范围。
编辑草稿时 exclude_return_id 用于校验编辑上下文，后端校验其确属当前用户有数据权限且关联该入库单的草稿；不能传入其他来源、已确认或不存在的退货单。
可退数量 = 入库数量减去已确认且未删除的关联退货数量；草稿不预占，作废退货释放数量。exclude_return_id 不增加可退数量。
前端仅展示已确认入库单，关联后锁定供应商、仓库、商品与单价，可修改退货数量和移除行；不同来源行即使商品相同也可分别退货。
保存和确认时必须重新校验实时可退数量，不能信任前端读取结果；确认时加锁和事务保证并发退货不会超量。

## 入库详情关联退货

入库详情 items 增加 returned_quantity、returnable_quantity，并返回 return_summary：
return_status 为 none、partial、full；confirmed_count 为有效退货单数；returned_amount 为有效退货金额。
汇总计入全部已确认且未删除、未作废的关联退货，不受下游退货的数据范围过滤影响；不改变原采购数量、金额和单据状态。
未确认或已作废入库单的可退数量为零，草稿退货不预占数量，作废退货释放数量。

GET /inventory/purchase/inbound/returns/{id}?page_no=1&page_size=10

分页返回当前用户数据范围内的关联退货，包含草稿、已确认、已作废记录，按退货 ID 降序排列。
同时要求 module_inventory:purchase_in:detail 和 module_inventory:purchase_return:query 权限，并校验原入库单的数据范围。
记录包含 id、order_no、business_date、status、total_amount、return_reason、confirmed_time；数量和金额使用固定精度字符串。
点击单号仍调用退货详情接口，独立要求 purchase_return:detail 权限及退货单的数据范围；不可见记录不会为了凑齐汇总而暴露。
刷新关联区域会重新读取原单详情和关联列表，避免汇总、商品可退数量与列表更新不同步。

## 状态和事务

status=0 草稿：允许编辑、删除、确认。
status=1 已确认：只读，允许填写原因作废。
status=2 已作废：只读，不允许恢复或删除。

所有修改校验 version、权限和状态。创建/更新只保存草稿；确认才影响库存、流水和应付；作废做冲销，不能直接删除库存流水。
存在未删除且未作废的关联退货（含草稿），或应付有核销金额、未撤销核销记录时，禁止入库作废。
冲销使用原流水的数量和金额，库存数量、金额不足，或冲销后数量为零但金额非零时，禁止强行冲销。
入库后平均成本 =（原库存金额 + 入库明细金额）/（原库存数量 + 入库数量），四舍五入保留四位。库存金额保留两位，不由平均成本反算。
零金额入库正常增加数量，生成已结清的零应付账单。反向应付保留原业务日期，通过 reversal_id 关联原账单；应付汇总需按带方向 amount 计算，不能把原账单和冲销账单的 unallocated_amount 直接相加。
后端事务必须保证主单、明细、库存、成本和往来数据一致，且重复确认/作废不会重复记账。前端保护不替代后端约束。

## 导出与失败状态

当前页及已选草稿由现有前端导出组件生成；全量数据请求后端文件流。
后端需校验 fields 白名单、保留字段顺序、使用当前筛选但忽略分页，并将状态及关联名称转换为展示值。
filename 为空时默认“采购入库列表*时间戳.格式”或“采购退货列表*时间戳.格式”；返回正确 Content-Type 和 Content-Disposition，异常返回框架规范 JSON。
采购入库、原单采购退货上述接口均可进行联调。确认及作废返回最新单据详情，重复提交或版本、状态不符返回 409，不重复记账。详情提供重试且禁止加载失败后保存。后端运行未开启自动重载时，修改控制器后需重启。
普通角色使用退货来源选择器时还需要采购入库 query、detail 权限及对应来源的数据范围。退货写接口仍独立校验来源数据权限，不能只依赖页面按钮。

## 后端实现位置

- purchase/in/crud.py：权限读取、行锁、版本状态更新及关联退货查询。
- purchase/in/service.py：草稿、确认、冲销与可退数量业务编排。
- purchase/return/schema.py、crud.py、service.py、controller.py：原单采购退货输入输出、数据访问、业务编排和 GET/POST 接口。
- stock/posting.py：库存余额并发初始化、版本更新及不可变流水。
- finance/payable.py：应付生成、核销限制和反向应付。
- common/business_log.py：与业务事务一起提交或回滚的状态日志。

以上文件均位于 backend/app/modules/inventory/ 内，in、return 为 Python 关键字，通过 import_module 注册及引用对应模块。已有表结构无需迁移。退货创建、修改、删除、确认和作废先锁来源入库单，再锁退货单及库存；切换来源按来源 ID 排序锁新旧来源。核销必须先锁应付账单，再写核销明细，保持相同锁顺序。
