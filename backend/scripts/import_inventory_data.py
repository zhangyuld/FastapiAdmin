"""独立业务数据导入入口：先选环境，再加载应用，不执行系统初始化。"""

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

from typer import Exit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    """默认只读预检，生产写入还须明确确认库存和财务影响。"""
    parser = argparse.ArgumentParser(description="导入正常编码的进销存业务样例，不参与启动和系统初始化")
    parser.add_argument("--env", choices=("dev", "prod"), required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dataset", default="standard-v1")
    parser.add_argument("--base-date", type=date.fromisoformat)
    parser.add_argument("--confirm-production", action="store_true", help="确认写入生产库存、成本、往来及经营报表")
    args = parser.parse_args()
    if args.env == "prod" and args.apply and not args.confirm_production:
        parser.error("生产写入会影响真实库存、应收应付和报表，请审核预检并添加 --confirm-production")
    from main import EnvironmentEnum, _execute_deployment

    async def action() -> dict[str, Any]:
        """共用连接清理和脱敏报错，不调用任何初始化写入。"""
        from app.scripts.data_import.inventory import import_inventory_data

        result = await import_inventory_data(args.apply, args.dataset, args.base_date)
        return {"environment": args.env, "warning": "写入会影响库存、成本、往来和经营报表", **result}

    try:
        _execute_deployment(EnvironmentEnum(args.env), action)
    except Exit as error:
        raise SystemExit(error.exit_code) from None


if __name__ == "__main__":
    main()
