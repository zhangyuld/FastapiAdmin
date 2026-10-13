# 销售管理前端接口契约

销售出库及原单销售退货均已补齐后端 schema、crud、service、controller、库存和应收记账，并注册路由。销售菜单已配置为 status=0 并补齐按钮权限，后端自动化测试通过不代表真实 MySQL 并发及正式业务验收已完成。无原单销售退货、收款及退款核销接口不在本阶段范围内。

## 页面与目录

- 销售出库：views/module_inventory/sale/out/index.vue，组件名 InventorySaleOut。
- 销售退货：views/module_inventory/sale/return/index.vue，组件名 InventorySaleReturn。
- 列表、录单弹窗、明细、商品选择、原单选择、关联退货均位于 sale/components。
- 局部状态保留在组件或 sale/composables，金额校验保留在 sale/utils，不依赖采购模块组件。

后端销售出库目录为 backend/app/modules/inventory/sale/out/，销售退货目录为 backend/app/modules/inventory/sale/return_order/。采购对应目录为 purchase/inbound/ 和 purchase/return_order/。后端模块使用普通 Python 导入，不使用 in、return 关键字作为目录名；接口 URL 与后端目录一致：采购入库 /inventory/purchase/inbound、采购退货 /inventory/purchase/return_order、销售退货 /inventory/sale/return_order，销售出库仍为 /inventory/sale/out；旧接口地址不再注册。前端页面目录、菜单路由及权限标识保持不变，无需数据库迁移或重新初始化菜单。

已有菜单 component_path 与上述页面一致，无需新增静态路由。在 backend 目录执行 uv run main.py inventory-menu-init --env=dev，可复用已有销售菜单、启用页面并补齐按钮权限；默认 SUPER_ADMIN、ADMIN 角色自动获得授权，其他角色需手动授权。销售报表等未开发页面仍保持禁用。

## 基础接口

业务前缀：/inventory/sale/out 和 /inventory/sale/return_order。所有查询 GET，所有写入与导出 POST。

公共单据、明细和保存输入类型位于 client.ts；出库输入与关联退货响应位于 out.ts，退货输入位于 return.ts。请求入参类型紧邻接口函数，不再使用独立 types.ts。

| 方法 | 相对路径      | 请求/响应                                               |
| ---- | ------------- | ------------------------------------------------------- |
| GET  | /list         | SaleQuery -> ApiResponse<PageResult<SaleDocument>>      |
| GET  | /detail/{id}  | ApiResponse<SaleDocument>，必须包含 items               |
| POST | /create       | SaleOutSaveBody 或 SaleReturnSaveBody -> 单据详情       |
| POST | /update/{id}  | 完整草稿输入加 version -> 单据详情                      |
| POST | /delete       | { ids: number[], versions: Record<number, number> }     |
| POST | /confirm/{id} | { version }，库存/应收/状态同事务更新                   |
| POST | /void/{id}    | { version, void_reason }，保留原记录并反向记账          |
| POST | /export       | { query, fields, format, sheet_name, filename } -> Blob |

查询支持单号、客户、仓库、业务日期范围、状态及审计字段；退货另支持 source_order_no。列表返回 customer_name、warehouse_name、created_by 及确认审计信息。

出库返回 original_amount、discount_amount、receivable_amount；退货返回 return_amount，不将金额字段统称为 total_amount。数量三位、价格/成本四位、金额两位，建议 JSON 使用固定精度字符串。

销售出库确认按商品顺序锁定库存余额，成本金额按未舍入的余额金额比例计算、单位成本快照保留四位；全部出库结清剩余库存金额。确认将库存、固化成本、应收及业务日志同事务写入，失败全部回滚。作废按原确认流水恢复数量和成本并生成反向应收，存在未作废关联退货（含草稿）或核销记录时拒绝。重复确认、重复作废和旧版本请求返回冲突，不重复记账。

出库输入含 customer_id、warehouse_id、business_date、discount_amount、remark、items；退货输入含 customer_id、warehouse_id、source_sale_out_id、business_date、return_reason、remark、items。
明细仅输入 goods_id、quantity、unit_price，原单退货再输入 source_sale_out_item_id。合计、商品快照和成本不得信任前端输入。

## 优惠与原单退货

GET /inventory/sale/out/returnable/{id}?exclude_return_id={已保存的当前退货草稿ID}

沿用销售出库 detail 权限，返回已确认原单及明细。每行必须返回原明细 id、原商品快照、原单价、returnable_quantity 和 returnable_amount。

- returnable_quantity：原数量减去全部已确认且未删除、未作废的退货数量，草稿不占用。
- returnable_amount：后端分摊原单优惠并扣减有效历史退货后的剩余可退金额；免费商品可为零。
- 原单供应商概念不适用销售，接口使用 customer_id 和 customer_name。
- exclude_return_id 只能是用户有数据权限、属于该原单的已保存草稿，不增加可退额度；切换来源不传旧来源草稿 ID。
- 前端按剩余金额乘本次数量占剩余数量比例做预估，不把原单价乘数量冒充退款；后端仍须按原优惠分摊、累计退货及尾差重新计算最终金额。
- 后端全量退回时累计退款应等于原应收，累计恢复成本等于原出库成本；重复退货及作废再退不能重复分摊尾差。
- 出库来源查询及退货写入共用按行金额累计分摊整单优惠的规则。退货确认按原行净额、原出库成本及有效累计数量重新分摊，累计全部退回补齐尾差，草稿金额只是保存时的预估。作废后再退使用剩余有效数量、退款及成本，不仅使用前端预估金额。
- 当前页面只支持原单退货；客户、仓库、商品和单价由原单锁定。成本不可编辑，详情读取固化成本，草稿成本允许为空。

## 关联退货预留

出库详情可返回 return_summary（return_status: none/partial/full，confirmed_count，returned_amount），items 可返回 returned_quantity、returnable_quantity。

GET /inventory/sale/out/returns/{id}?page_no=1&page_size=10

返回 ApiResponse<PageResult<RelatedSaleReturn>>，包含 id、order_no、business_date、status、return_amount、return_reason、confirmed_time。
同时要求 sale_out:detail 和 sale_return:query 权限，校验原单数据范围，关联记录按退货数据范围过滤。统计按全部有效关联退货计算，但不泄露无权查看的具体退货单。
该区域仅在详情返回 return_summary 后展示；点击单号独立调用退货 detail 接口并校验权限。

## 权限、导出与失败处理

权限前缀为 module_inventory:sale_out 和 module_inventory:sale_return，动作 query/create/update/detail/delete/confirm/void/export。
来源选择需要 sale_out:query、sale_out:detail；商品选择需要 goods:query；客户和仓库选项需要对应基础档案 query 权限。

只有草稿可以修改或删除；确认和作废携带 version。已确认/已作废详情只读，后端仍须校验状态、版本、库存、应收和数据范围。

当前页、选择数据由前端导出；全量导出走后端文件流，传递当前筛选、选择字段顺序、格式、sheet*name、filename。空文件名后端默认“销售出库列表*时间戳.格式”或“销售退货列表\_时间戳.格式”，返回正确 Content-Type 和 UTF-8 Content-Disposition。

退货确认按原成本恢复库存并生成负向应收；作废按原退货流水扣回库存、恢复应收并释放额度，库存不足或原账单存在核销时拒绝。来源、退货及库存按固定顺序加锁，版本冲突或重复操作不重复记账。加载失败或来源可退额度缺失时禁止保存；接口错误不会显示保存成功。数量超限、优惠超原价及精度错误在前端拦截，但不替代后端校验。
