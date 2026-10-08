import { request } from "@utils";

const API_PATH = "/inventory/basic/goods";

/** 商品启停状态。 */
export type GoodsStatus = 0 | 1;

/** 商品分页查询参数。 */
export interface GoodsPageQuery extends PageQuery, UserByQueryParams {
  goods_code?: string;
  goods_name?: string;
  category_id?: number;
  status?: GoodsStatus;
}

/** 商品列表及详情数据。 */
export interface GoodsItem extends BaseType {
  category_id: number;
  category_name?: string | null;
  goods_code: string;
  goods_name: string;
  spec?: string | null;
  unit: string;
  reference_cost_price: number | string;
  sale_price: number | string;
  stock_min: number | string;
  stock_max: number | string;
  remark?: string | null;
  status: GoodsStatus;
}

/** 商品新增和修改表单。 */
export interface GoodsForm extends BaseFormType {
  category_id: number | undefined;
  goods_code: string;
  goods_name: string;
  spec?: string;
  unit: string;
  reference_cost_price: number;
  sale_price: number;
  stock_min: number;
  stock_max: number;
  remark?: string;
  status: GoodsStatus;
}

/** 商品批量删除参数。 */
export interface GoodsDeleteBody {
  ids: number[];
}

/** 商品批量状态参数。 */
export interface GoodsStatusBody extends GoodsDeleteBody {
  status: GoodsStatus;
}

/** 商品允许导出的字段。 */
export const GOODS_EXPORT_FIELDS = [
  "goods_code",
  "goods_name",
  "category_name",
  "spec",
  "unit",
  "reference_cost_price",
  "sale_price",
  "stock_min",
  "stock_max",
  "status",
  "remark",
  "created_time",
  "updated_time",
] as const;

/** 商品导出字段。 */
export type GoodsExportField = (typeof GOODS_EXPORT_FIELDS)[number];

/** 商品全量导出参数。 */
export interface GoodsExportBody {
  query: GoodsPageQuery;
  fields: GoodsExportField[];
  format: "xlsx" | "csv";
  sheet_name: string;
}

const GoodsAPI = {
  /** 分页查询商品。 */
  listGoods(query: GoodsPageQuery) {
    return request<ApiResponse<PageResult<GoodsItem>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  /** 查询商品详情。 */
  getGoodsDetail(id: number) {
    return request<ApiResponse<GoodsItem>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  /** 创建商品。 */
  createGoods(body: GoodsForm) {
    return request<ApiResponse<GoodsItem>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: body,
    });
  },

  /** 修改商品。 */
  updateGoods(id: number, body: GoodsForm) {
    return request<ApiResponse<GoodsItem>>({
      url: `${API_PATH}/update/${id}`,
      method: "post",
      data: body,
    });
  },

  /** 批量删除商品。 */
  deleteGoods(body: GoodsDeleteBody) {
    return request<ApiResponse>({
      url: `${API_PATH}/delete`,
      method: "post",
      data: body,
    });
  },

  /** 批量修改商品状态。 */
  batchGoodsStatus(body: GoodsStatusBody) {
    return request<ApiResponse>({
      url: `${API_PATH}/status/batch`,
      method: "post",
      data: body,
    });
  },

  /** 导出商品。 */
  exportGoods(body: GoodsExportBody) {
    return request<Blob>({
      url: `${API_PATH}/export`,
      method: "post",
      data: body,
      responseType: "blob",
    });
  },
};

export default GoodsAPI;
