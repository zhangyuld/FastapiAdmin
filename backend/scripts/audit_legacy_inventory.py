"""核查旧D前缀批次及交叉引用，仅SELECT，不支持写入或删除。"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from typer import Exit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    """选择环境后只读核查，不通过初始化或业务导入入口执行。"""
    parser = argparse.ArgumentParser(description="只读核查旧D前缀数据，不删除数据库记录")
    parser.add_argument("--env", choices=("dev", "prod"), required=True)
    parser.add_argument("--report", type=Path, help="保存新JSON核查文件，拒绝覆盖已有文件")
    args = parser.parse_args()
    from main import EnvironmentEnum, _execute_deployment

    async def action() -> dict[str, Any]:
        """仅加载审计实现并返回不含密码的候选清单。"""
        from app.scripts.data_import.legacy_audit import audit_legacy_data

        result = await audit_legacy_data()
        if args.report:
            with args.report.open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2, default=str)
            return {"mode": "read-only", "report": str(args.report.resolve()), "database": result["database"], "batches": [{"dataset": row["dataset"], "prefix": row["prefix"], "counts": row["counts"], "external_references": row["external_references"], "warnings": row["warnings"]} for row in result["batches"]], "deleted": False}
        return result

    try:
        _execute_deployment(EnvironmentEnum(args.env), action)
    except Exit as error:
        raise SystemExit(error.exit_code) from None


if __name__ == "__main__":
    main()
