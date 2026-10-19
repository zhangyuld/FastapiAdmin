"""仅清理已审核报告中的旧批次，默认预检，写入须明确声明维护窗口。"""

import argparse
import sys
from pathlib import Path
from typing import Any

from typer import Exit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    """以批准清单限定数据库和批次，不提供模糊前缀清空能力。"""
    parser = argparse.ArgumentParser(description="备份并清理已审核的旧批次，不导入新数据")
    parser.add_argument("--env", choices=("dev", "prod"), required=True)
    parser.add_argument("--approved-report", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--maintenance-confirmed", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.maintenance_confirmed:
        parser.error("实际清理前须停止相关写入，并显式添加 --maintenance-confirmed")
    from main import EnvironmentEnum, _execute_deployment

    async def action() -> dict[str, Any]:
        """所有删除依赖精确清单、已校验备份和SQL事务。"""
        from app.scripts.data_import.legacy_cleanup import cleanup_legacy

        return await cleanup_legacy(args.approved_report, args.backup_dir, args.dataset, args.apply)

    try:
        _execute_deployment(EnvironmentEnum(args.env), action)
    except Exit as error:
        raise SystemExit(error.exit_code) from None


if __name__ == "__main__":
    main()
