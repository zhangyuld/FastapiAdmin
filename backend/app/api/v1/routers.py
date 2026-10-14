"""v1 路由总表"""

from fastapi import APIRouter

from app.modules.ai.chat.controller import ChatRouter
from app.modules.common.file.controller import FileRouter
from app.modules.generator.gencode.controller import GenRouter
from app.modules.inventory.basic.category.controller import GoodsCategoryRouter
from app.modules.inventory.basic.customer.controller import CustomerRouter
from app.modules.inventory.basic.goods.controller import GoodsRouter
from app.modules.inventory.basic.supplier.controller import SupplierRouter
from app.modules.inventory.basic.warehouse.controller import WarehouseRouter
from app.modules.inventory.dashboard.controller import DashboardRouter
from app.modules.inventory.finance.payable.controller import PayableRouter
from app.modules.inventory.finance.receivable.controller import ReceivableRouter
from app.modules.inventory.purchase.inbound.controller import PurchaseInRouter
from app.modules.inventory.purchase.return_order.controller import PurchaseReturnRouter
from app.modules.inventory.report.profit.controller import ProfitReportRouter
from app.modules.inventory.report.purchase.controller import PurchaseReportRouter
from app.modules.inventory.report.sale.controller import SaleReportRouter
from app.modules.inventory.report.stock.controller import StockReportRouter
from app.modules.inventory.sale.out.controller import SaleOutRouter
from app.modules.inventory.sale.return_order.controller import SaleReturnRouter
from app.modules.inventory.stock.balance.controller import StockBalanceRouter
from app.modules.inventory.stock.check.controller import StockCheckRouter
from app.modules.inventory.stock.log.controller import StockLogRouter
from app.modules.inventory.stock.opening.controller import StockOpeningRouter
from app.modules.monitor.cache.controller import CacheRouter
from app.modules.monitor.health.controller import HealthRouter
from app.modules.monitor.online.controller import OnlineRouter
from app.modules.monitor.server.controller import ServerRouter
from app.modules.system.auth.controller import AuthRouter
from app.modules.system.dept.controller import DeptRouter
from app.modules.system.dict.controller import DictRouter
from app.modules.system.log.controller import LogRouter
from app.modules.system.menu.controller import MenuRouter
from app.modules.system.notice.controller import NoticeRouter
from app.modules.system.params.controller import ParamsRouter
from app.modules.system.position.controller import PositionRouter
from app.modules.system.role.controller import RoleRouter
from app.modules.system.ticket.controller import TicketRouter
from app.modules.system.user.controller import UserRouter
from app.modules.system.versions.controller import VersionRouter
from app.modules.task.cronjob.job.controller import CronJobRouter
from app.modules.task.cronjob.node.controller import CronJobNodeRouter
from app.modules.task.storage.browse.controller import StorageBrowseRouter
from app.modules.task.storage.node.controller import StorageNodeRouter
from app.modules.task.storage.transfer.controller import StorageTransferRouter
from app.modules.task.storage.workflow.controller import StorageWorkflowRouter

# 域前缀 → 该域 controller 清单（唯一路由事实来源）
DOMAIN_CONTROLLERS: dict[str, list[APIRouter]] = {
    "/system": [
        AuthRouter,
        UserRouter,
        RoleRouter,
        MenuRouter,
        DeptRouter,
        PositionRouter,
        DictRouter,
        ParamsRouter,
        NoticeRouter,
        TicketRouter,
        VersionRouter,
        LogRouter,
    ],
    "/monitor": [
        CacheRouter,
        HealthRouter,
        OnlineRouter,
        ServerRouter,
    ],
    "/task": [
        CronJobRouter,
        CronJobNodeRouter,
        StorageBrowseRouter,
        StorageNodeRouter,
        StorageTransferRouter,
        StorageWorkflowRouter,
    ],
    "/ai": [ChatRouter],
    "/inventory/basic": [GoodsCategoryRouter, GoodsRouter, CustomerRouter, SupplierRouter, WarehouseRouter],
    "/inventory/dashboard": [DashboardRouter],
    "/inventory/purchase": [PurchaseInRouter, PurchaseReturnRouter],
    "/inventory/sale": [SaleOutRouter, SaleReturnRouter],
    "/inventory/stock": [StockBalanceRouter, StockLogRouter, StockOpeningRouter, StockCheckRouter],
    "/inventory/finance": [ReceivableRouter, PayableRouter],
    "/inventory/report": [PurchaseReportRouter, SaleReportRouter, StockReportRouter, ProfitReportRouter],
    "/generator": [GenRouter],
    "/common": [FileRouter],
}

api_v1 = APIRouter()
for prefix, controllers in DOMAIN_CONTROLLERS.items():
    router = APIRouter(prefix=prefix)
    for controller in controllers:
        router.include_router(controller)
    api_v1.include_router(router)
