import { request } from "@utils";

const API_PATH = "/inventory/basic/category";

/** 商品分类树查询参数。 */
export interface GoodsCategoryQuery extends UserByQueryParams {
  name?: string;
  status?: 0 | 1;
}

/** 商品分类树节点及详情数据。 */
export interface GoodsCategoryItem extends BaseType {
  name: string;
  parent_id?: number | null;
  parent_name?: string | null;
  sort: number;
  status: 0 | 1;
  children?: GoodsCategoryItem[] | null;
}

/** 商品分类新增和修改表单。 */
export interface GoodsCategoryForm extends BaseFormType {
  name: string;
  parent_id?: number | null;
  sort: number;
  status: 0 | 1;
}

/** 规范分类表单，清空上级分类时固定提交 null。 */
function normalizeCategoryBody(body: GoodsCategoryForm): GoodsCategoryForm {
  return {
    ...body,
    parent_id: body.parent_id ?? null,
  };
}

const GoodsCategoryAPI = {
  /** 查询商品分类树。 */
  listCategoryTree(query?: GoodsCategoryQuery) {
    return request<ApiResponse<GoodsCategoryItem[]>>({
      url: `${API_PATH}/tree`,
      method: "get",
      params: query,
    });
  },

  /** 查询商品分类详情。 */
  getCategoryDetail(id: number) {
    return request<ApiResponse<GoodsCategoryItem>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  /** 创建商品分类。 */
  createCategory(body: GoodsCategoryForm) {
    return request<ApiResponse<GoodsCategoryItem>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: normalizeCategoryBody(body),
    });
  },

  /** 修改商品分类。 */
  updateCategory(id: number, body: GoodsCategoryForm) {
    return request<ApiResponse<GoodsCategoryItem>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: normalizeCategoryBody(body),
    });
  },

  /** 批量删除商品分类。 */
  deleteCategory(ids: number[]) {
    return request<ApiResponse>({
      url: `${API_PATH}/delete`,
      method: "delete",
      data: ids,
    });
  },

  /** 批量修改商品分类状态。 */
  batchCategoryStatus(body: BatchType) {
    return request<ApiResponse>({
      url: `${API_PATH}/status/batch`,
      method: "patch",
      data: body,
    });
  },
};

export default GoodsCategoryAPI;
