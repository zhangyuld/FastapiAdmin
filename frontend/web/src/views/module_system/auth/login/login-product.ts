import overviewImage from "@/assets/images/login/showcase/overview.png";
import purchaseImage from "@/assets/images/login/showcase/purchase.png";
import stockImage from "@/assets/images/login/showcase/stock.png";
import reportImage from "@/assets/images/login/showcase/report.png";

/** 产品介绍分区标识，仅用于当前登录页定位。 */
export type LoginSectionId = "overview" | "trade" | "stock" | "reports";

/** 导航与分区使用同一组标识，避免位置和高亮错配。 */
export interface LoginSectionLink {
  id: LoginSectionId;
  label: string;
}

/** 单项已交付能力，不包含规划中的资金核销功能。 */
export interface LoginFeature {
  icon: string;
  title: string;
  description: string;
}

/** 登录页静态产品内容和脱敏截图。 */
export interface LoginProductSection extends LoginSectionLink {
  number: string;
  title: string;
  description: string;
  image: string;
  imageAlt: string;
  features: LoginFeature[];
}

export const loginSectionLinks: LoginSectionLink[] = [
  { id: "overview", label: "系统概览" },
  { id: "trade", label: "采购销售" },
  { id: "stock", label: "库存管理" },
  { id: "reports", label: "经营报表" },
];

export const loginOverviewImage = overviewImage;

export const loginProductSections: LoginProductSection[] = [
  {
    id: "trade",
    label: "采购销售",
    number: "01",
    title: "每一笔进出，都有据可循。",
    description: "从采购入库到销售出库，让商品流转与业务单据同步。退货关联原单，业务前后清晰可查。",
    image: purchaseImage,
    imageAlt: "智仓云采购入库列表，展示标准业务样例的单据日期、供应商、仓库和确认状态",
    features: [
      {
        icon: "ri:truck-line",
        title: "采购入库",
        description: "记录采购明细，确认入库形成库存与应付。",
      },
      {
        icon: "ri:shopping-bag-3-line",
        title: "销售出库",
        description: "关联客户与仓库，出库同步库存成本与应收。",
      },
      {
        icon: "ri:arrow-go-back-line",
        title: "原单退货",
        description: "采购、销售退货关联来源单据，追溯业务往来。",
      },
    ],
  },
  {
    id: "stock",
    label: "库存管理",
    number: "02",
    title: "看清库存，也看清每次变化。",
    description:
      "按商品、按仓库查看数量与金额。从期初建账到日常盘点，把账面库存与实际库存连接起来。",
    image: stockImage,
    imageAlt: "智仓云当前库存列表，展示标准业务样例的仓库、商品、库存数量、成本金额与预警",
    features: [
      {
        icon: "ri:stack-line",
        title: "多仓库存",
        description: "按仓库查询商品结存，数量与库存价值一目了然。",
      },
      {
        icon: "ri:file-list-3-line",
        title: "库存流水",
        description: "每次库存变化保留业务来源，方便逐笔追踪。",
      },
      {
        icon: "ri:checkbox-multiple-line",
        title: "建账与盘点",
        description: "期初库存建立基线，盘点记录差异，关注上下限预警。",
      },
    ],
  },
  {
    id: "reports",
    label: "经营报表",
    number: "03",
    title: "让日常业务，成为经营的依据。",
    description: "汇总采购、销售、库存与毛利，结合应收应付余额查询，从同一套业务记录了解经营情况。",
    image: reportImage,
    imageAlt: "智仓云销售报表，展示标准业务样例的销售汇总、退货金额和商品统计",
    features: [
      {
        icon: "ri:bar-chart-box-line",
        title: "业务报表",
        description: "采购、销售与库存报表，支持按业务条件筛选和导出。",
      },
      {
        icon: "ri:line-chart-line",
        title: "毛利分析",
        description: "结合销售收入与出库成本，查看商品毛利表现。",
      },
      {
        icon: "ri:wallet-3-line",
        title: "往来余额",
        description: "查询客户应收、供应商应付及对应业务明细。",
      },
    ],
  },
];
