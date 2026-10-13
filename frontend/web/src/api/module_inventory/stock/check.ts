import { request } from "@utils";
import { createStockDocumentClient } from "./client";
import type { StockDocument, StockLine } from "./client";
/** 单据刷新账面快照的并发版本。 */
interface RefreshBody {
  version: number;
}
/** 保留实盘数并刷新服务端账面快照，调用后须重新核对差异。 */
function refresh(id: number, body: RefreshBody) {
  return request<ApiResponse<StockDocument>>({
    url: "/inventory/stock/check/refresh/" + id,
    method: "post",
    data: body,
  });
}
/** 新增商品前读取账面快照的参数。 */
interface SnapshotQuery {
  warehouse_id: number;
  goods_ids: number[];
}
/** 读取当前账面数量、金额和版本，不用前端输入替代服务端快照。 */
function snapshot(query: SnapshotQuery) {
  return request<ApiResponse<StockLine[]>>({
    url: "/inventory/stock/check/snapshot",
    method: "get",
    params: query,
  });
}
/** 库存盘点与快照专有接口。 */
export default {
  ...createStockDocumentClient({ path: "/inventory/stock/check" }),
  refresh,
  snapshot,
};
