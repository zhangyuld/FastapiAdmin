# 报表接口与接入进度

采购报表后端已完成并接入，client.ts 的 reportApiReady.purchase 为 true；销售、库存、毛利仍为 false，仅完成前端预览。未接入领域不请求不存在的接口，不展示模拟经营数据，指标使用缺失占位，导出禁用。后续按领域联调后分别启用，不修改全局请求拦截器来隐藏 404。

## 接口

前缀 /inventory/report/{purchase,sale,stock,profit}，真实请求由框架添加 /api/v1。

| 方法 | 路径     | 输入                                        | 响应                                    |
| ---- | -------- | ------------------------------------------- | --------------------------------------- |
| GET  | /list    | ReportQuery：view、筛选、page_no、page_size | ApiResponse<PageResult<领域 ReportRow>> |
| GET  | /summary | view 和筛选，不携带分页                     | ApiResponse<领域 ReportSummary>         |
| POST | /export  | query、fields、format、sheet_name、filename | Excel/CSV Blob                          |

采购后端已校验自身 query/export 权限、视图、日期及排序和导出字段白名单；其他领域需按同样边界实现。前端白名单清洗不是安全边界，不提供报表 create/update/delete。

## 视图与筛选

- purchase、sale、profit：documents 单据明细，goods 商品汇总。
- stock：balance 当前库存，movement 期间变动。
- 基础筛选：goods_code、goods_name、warehouse_id、category_id。没有对应档案查询权限时，筛选使用 warehouse_name、category_name；后端需支持名称查询，不能要求用户必须获得档案权限才能查询报表。
- purchase 仅 supplier_name；sale/profit 仅 customer_name；documents 支持 business_no。
- 业务日期 business_date 为两个 YYYY-MM-DD 值；stock/balance 不接受日期，stock/movement 不接受余额 warning。
- stock/balance 的 warning 为 normal、low、high。
- URL 保存已提交筛选和视图；页面缓存仅恢复当前领域参数。输入框未提交的值不参与汇总或全量导出。

## 统计契约

- 确认业务及有效退货的统计口径由后端实现。草稿、作废、冲销以及期间日期口径需在后端实现时确认，不在前端拼接分页业务单据推算指标。
- 采购返回 purchase_amount、return_amount、net_purchase_amount；销售返回优惠后的 sale_amount、return_amount、net_sale_amount。业务应计金额不是现金收付款金额。
- 商品数量按商品与单位分组；商品、仓库等维度需返回稳定唯一 id，不将不同单位数量相加为总指标。
- 当前库存返回 quantity、avg_cost、stock_amount、warning；期间变动返回 in_quantity、out_quantity、net_quantity、in_amount、out_amount、net_amount，不将净变动当期末余额。
- 毛利返回 net_sale_amount、net_cost_amount、gross_profit、gross_margin，成本必须来自固化销售成本及原成本退回，不使用当前参考进价。gross_margin 为百分数定点字符串，不能计算时为 null；前端不除法计算毛利率。
- 金额、数量、成本、毛利率均为定点字符串；summary 针对全部筛选数据，与当前页无关。响应字段以 client.ts 的领域类型为准。
- 明细来源 source 包含 business_type、business_id；商品汇总行不伪造来源。采购/销售来源仅以原模块详情权限打开只读弹窗，后端仍执行原业务数据范围校验。

## 导出

当前页/选中行使用前端既有导出弹窗；全部数据调用 POST /export，发送字段顺序、同一筛选、格式、文件名及工作表名。采购后端已复用列表筛选，提供合法 Content-Disposition；空文件名默认采购报表加 Asia/Shanghai 时间戳，格式扩展名一致。超过10万行明确报错，不由框架静默截断。档案文本按字面值导出，避免 CSV/Excel 公式执行；负金额及数量不改变方向或精度。

## 权限与接入

权限前缀为 module_inventory:{purchase_report,sale_report,stock_report,profit_report}:，页面使用 query，导出使用 export。已启用菜单不代表后端统计已交付。

接入顺序：实现与校验后端接口、确认统计口径、联调领域 DTO 与文件流、再将该领域 reportApiReady 设为 true，核对空数据/失败/普通角色及来源权限。当前不添加排行、趋势、资金核销或历史库存结存报表。

## 采购已实现口径

- 后端目录为 backend/app/modules/inventory/report/purchase/，包含 schema、crud、service、controller，路由在 app/api/v1/routers.py 注册。不新增报表表或迁移。
- 当前有效业务：主单 status=1、主单与明细均未删除；草稿和作废不统计，不从应付或库存冲销账单再次扣减。
- 入库与退货按各自 business_date 入选。作废后原期间会按当前有效状态重算，不是历史时点冻结报表。
- 有效明细先筛选再分组。商品筛选只汇总命中商品的明细金额；分类 ID 精确匹配当前商品档案归属，分类名称支持模糊查询，不自动扩展子分类。
- documents：入库、退货各一行。入库行 return_amount=0，退货行 purchase_amount=0、return_amount 为正数、net_purchase_amount 为负数。
- goods：按商品 ID、仓库 ID 及编码、名称、规格、单位快照分组；使用二进制快照键避免 MySQL 不区分大小写/重音的排序规则合并不同快照。稳定行 ID 为分组键摘要，不随分页变化。
- 商品筛选和展示使用明细快照；供应商、仓库名称以及分类归属使用当前档案，停用和软删除档案不会过滤其有效历史单据。
- summary：完整筛选明细采购金额之和、退货金额之和及差额；document_count 按业务类型和单据 ID 去重，包含入库与退货。金额两位、数量三位字符串；不跨单位求数量总计。
- 企业共享报表仅按 purchase_report:query/export 授权，不按创建人截断采购与退货；原采购详情仍执行自身权限与数据范围。
- 采购菜单 frontend_only 已设为 false，菜单种子和初始化脚本描述同步为已交付；其余三页保持前端预览。开发库已执行菜单初始化，新增0节点，不增加新的权限码。
