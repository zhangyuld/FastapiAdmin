"""独立CLI进程使用临时SQLite，不触碰开发数据库或运行服务。"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def deployment_env(tmp_path: Path) -> dict[str, str]:
    """测试口令仅传给子进程，不导入部署代码以免缓存环境混用。"""
    return {
        **os.environ,
        "DATABASE_TYPE": "sqlite",
        "DATABASE_NAME": str(tmp_path / "installation.db"),
        "DEBUG": "False",
        "SECRET_KEY": "deployment-test-key-not-for-real-production-2026",
        "INIT_ADMIN_PASSWORD": "TmpInit#2026",
        "PYTHONIOENCODING": "utf-8",
        "LOGGER_LEVEL": "ERROR",
    }


def command(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    """真实运行Typer命令，同时捕获返回码与脱敏输出。"""
    return subprocess.run([sys.executable, "main.py", *args], cwd=BACKEND, env=env, input="", capture_output=True, text=True, encoding="utf-8", timeout=90)


def import_command(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    """独立脚本与main.py隔离，子进程仅使用测试库。"""
    return subprocess.run([sys.executable, "scripts/import_inventory_data.py", *args], cwd=BACKEND, env=env, input="", capture_output=True, text=True, encoding="utf-8", timeout=90)


def payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """读取最后一条机器可读结果，不把日志当成功。"""
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(next(line for line in reversed(result.stdout.splitlines()) if line.startswith("{")))


def test_deployment_preview_does_not_create_database(deployment_env: dict[str, str]) -> None:
    """预检缺失SQLite文件时不能通过连接偷偷创建文件。"""
    value = payload(command(deployment_env, "init-db", "--env=dev", "--dry-run"))
    assert value["mode"] == "dry-run" and value["structure"]["empty"]
    assert not Path(deployment_env["DATABASE_NAME"]).exists()


def test_deployment_bootstrap_and_repeat(deployment_env: dict[str, str]) -> None:
    """首次完整建库，重跑不改密码、不创建旧演示管理员。"""
    first = payload(command(deployment_env, "init-db", "--env=dev", "--apply"))
    assert first["created"]["initial_admin"] == 1
    with sqlite3.connect(deployment_env["DATABASE_NAME"]) as db:
        before = db.execute("SELECT username, password, is_superuser FROM sys_user").fetchall()
        from app.utils.password_util import PwdUtil

        assert PwdUtil.verify_password("TmpInit#2026", before[0][1])
        assert len(before) == 1 and before[0][0] == "super" and before[0][2] == 1
        assert db.execute("SELECT COUNT(*) FROM ims_goods").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM agno_sessions").fetchone()[0] == 0
    env = {key: value for key, value in deployment_env.items() if key != "INIT_ADMIN_PASSWORD"}
    payload(command(env, "init-db", "--env=dev", "--apply"))
    checked = payload(command(env, "init-check", "--env=dev", "--database-only"))
    assert checked["status"] == "ready" and not checked["redis_checked"]
    with sqlite3.connect(env["DATABASE_NAME"]) as db:
        assert db.execute("SELECT username, password, is_superuser FROM sys_user").fetchall() == before


def test_deployment_rejects_invalid_password_before_ddl(deployment_env: dict[str, str]) -> None:
    """显式无效密码不能被默认值掩盖，也不得开始建表。"""
    deployment_env["INIT_ADMIN_PASSWORD"] = ""
    result = command(deployment_env, "init-db", "--env=dev", "--apply")
    assert result.returncode != 0 and "INIT_PASSWORD_REQUIRED" in result.stderr
    path = Path(deployment_env["DATABASE_NAME"])
    if path.exists():
        with sqlite3.connect(path) as db:
            assert not db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()


def test_deployment_rejects_partial_database(deployment_env: dict[str, str]) -> None:
    """无版本非空库不能被当成新空库或被自动stamp。"""
    with sqlite3.connect(deployment_env["DATABASE_NAME"]) as db:
        db.execute("CREATE TABLE existing_data (id INTEGER PRIMARY KEY)")
    result = command(deployment_env, "init-db", "--env=dev", "--apply")
    assert result.returncode != 0 and "INIT_SCHEMA_CONFLICT" in result.stderr
    with sqlite3.connect(deployment_env["DATABASE_NAME"]) as db:
        assert [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")] == ["existing_data"]


def test_deployment_invalid_modes_and_production_revision(deployment_env: dict[str, str]) -> None:
    """错误模式在连接数据库之前失败，生产禁止生成迁移。"""
    assert command(deployment_env, "init-db", "--apply", "--dry-run").returncode != 0
    assert command(deployment_env, "revision", "--env=prod").returncode != 0
    assert not Path(deployment_env["DATABASE_NAME"]).exists()


@pytest.fixture
def installed_env(deployment_env: dict[str, str]) -> dict[str, str]:
    """独立进程安装后供组织及演示场景使用。"""
    payload(command(deployment_env, "init-db", "--env=dev", "--apply"))
    return deployment_env


def org_file(path: Path, **updates: Any) -> Path:
    """组织样例只引用密码环境名，不保存明文口令。"""
    data = {
        "dataset": "example-org-v1",
        "departments": [{"code": "ACME", "name": "示例公司"}, {"code": "BUY", "name": "采购部", "parent_code": "ACME"}],
        "positions": [{"code": "BUYER", "name": "采购员"}],
        "roles": [{"code": "BUYER", "name": "采购员", "data_scope": 1, "permissions": ["module_inventory:goods:query"]}],
        "users": [{"username": "example_buyer", "name": "采购员", "dept_code": "BUY", "position_codes": ["BUYER"], "role_codes": ["BUYER"], "password_env": "ORG_BUYER_PASSWORD"}],
        **updates,
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_org_preview_apply_and_repeat(installed_env: dict[str, str], tmp_path: Path) -> None:
    """关联由编码解析，预检不写库，重跑保留哈希与权限。"""
    path = org_file(tmp_path / "organization.json")
    args = ("init-org", "--env=dev", "--file", str(path))
    preview = payload(command(installed_env, *args, "--dry-run"))
    assert preview["create"]["users"] == 1
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        assert db.execute("SELECT COUNT(*) FROM sys_user").fetchone()[0] == 1
    installed_env["ORG_BUYER_PASSWORD"] = ""
    result = command(installed_env, *args, "--apply")
    assert result.returncode != 0 and "INIT_PASSWORD_REQUIRED" in result.stderr
    installed_env["ORG_BUYER_PASSWORD"] = "TmpBuyer#2026"
    assert payload(command(installed_env, *args, "--apply"))["created"]["users"] == 1
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        user = db.execute("SELECT id, password, is_superuser, dept_id FROM sys_user WHERE username='example_buyer'").fetchone()
        from app.utils.password_util import PwdUtil

        assert PwdUtil.verify_password("TmpBuyer#2026", user[1])
        assert user[2] == 0 and db.execute("SELECT code FROM sys_dept WHERE id=?", (user[3],)).fetchone()[0] == "BUY"
        roles = db.execute("SELECT role_id, menu_id FROM sys_role_menus").fetchall()
    installed_env.pop("ORG_BUYER_PASSWORD")
    assert not any(payload(command(installed_env, *args, "--apply"))["created"].values())
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        assert db.execute("SELECT id, password, is_superuser, dept_id FROM sys_user WHERE username='example_buyer'").fetchone() == user
        assert db.execute("SELECT role_id, menu_id FROM sys_role_menus").fetchall() == roles


def test_org_cycle_and_unknown_permission_are_atomic(installed_env: dict[str, str], tmp_path: Path) -> None:
    """坏文件不会留下半套部门，通配权限不允许作为自动导入捷径。"""
    path = org_file(tmp_path / "cycle.json", departments=[{"code": "ACME", "name": "公司", "parent_code": "BUY"}, {"code": "BUY", "name": "采购", "parent_code": "ACME"}])
    result = command(installed_env, "init-org", "--file", str(path), "--apply")
    assert result.returncode != 0 and "INIT_DATA_INVALID" in result.stderr
    path = org_file(path, roles=[{"code": "BUYER", "name": "采购", "permissions": ["*:*:*"]}])
    result = command(installed_env, "init-org", "--file", str(path), "--apply")
    assert result.returncode != 0 and "INIT_DATA_INVALID" in result.stderr
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        assert db.execute("SELECT COUNT(*) FROM sys_dept WHERE code='ACME'").fetchone()[0] == 0


def test_deployment_preserves_unknown_revision(installed_env: dict[str, str]) -> None:
    """版本不存在时拒绝执行，绝不自动清理版本号。"""
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        db.execute("UPDATE alembic_version SET version_num='unpublished_revision'")
    result = command(installed_env, "init-db", "--apply")
    assert result.returncode != 0 and "INIT_SCHEMA_CONFLICT" in result.stderr
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "unpublished_revision"


def test_run_does_not_initialize(deployment_env: dict[str, str]) -> None:
    """真正启动入口对未安装库失败退出，不能补表或创建管理员。"""
    result = command(deployment_env, "run", "--env=dev")
    assert result.returncode != 0
    assert "APP_NOT_INITIALIZED" in result.stdout + result.stderr
    assert not Path(deployment_env["DATABASE_NAME"]).exists()


def test_production_environment_and_import_confirmation(deployment_env: dict[str, str]) -> None:
    """先选择环境，生产写入须确认；旧初始化子命令不再存在。"""
    deployment_env["DEBUG"] = "True"
    result = command(deployment_env, "init-db", "--env=prod", "--dry-run")
    assert result.returncode != 0 and "INIT_CONFIG_INVALID" in result.stderr
    result = import_command(deployment_env, "--env=prod", "--apply")
    assert result.returncode == 2 and "--confirm-production" in result.stderr
    assert command(deployment_env, "inventory-demo-init", "--env=dev").returncode != 0
    assert not Path(deployment_env["DATABASE_NAME"]).exists()


@pytest.mark.parametrize("environment", ["dev", "prod"])
def test_import_uses_posting_and_is_idempotent(installed_env: dict[str, str], environment: str) -> None:
    """真实业务服务形成库存及往来，重复命令不重复记账。"""
    args = (f"--env={environment}", "--confirm-production")
    preview = payload(import_command(installed_env, *args, "--dry-run", "--base-date", "2026-10-15"))
    assert preview["planned"]["business_documents"] == 84
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        assert db.execute("SELECT COUNT(*) FROM ims_goods").fetchone()[0] == 0
    installed_env.pop("INVENTORY_DATA_PASSWORD", None)
    applied = payload(import_command(installed_env, *args, "--apply", "--base-date", "2026-10-15"))
    assert applied["created"]["goods"] == 30 and applied["organization"]["created"]["users"] == 10
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        counts = {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in ("ims_stock_log", "ims_receivable", "ims_payable", "ims_purchase_in", "ims_sale_out")}
        assert all(counts.values())
        assert db.execute("SELECT COUNT(*) FROM sys_user WHERE is_superuser=1").fetchone()[0] == 1
        from app.utils.password_util import PwdUtil

        demo_hash = db.execute("SELECT password FROM sys_user WHERE is_superuser=0 LIMIT 1").fetchone()[0]
        assert PwdUtil.verify_password("zcy123456@#", demo_hash)
        assert db.execute("SELECT goods_code FROM ims_goods ORDER BY id LIMIT 1").fetchone()[0] == "G001"
        assert db.execute("SELECT name FROM ims_goods_category ORDER BY id LIMIT 1").fetchone()[0] == "办公耗材"
        assert db.execute("SELECT username FROM sys_user WHERE is_superuser=0 ORDER BY id LIMIT 1").fetchone()[0] == "zhangming"
        for table in ("ims_purchase_in", "ims_sale_out", "ims_goods", "ims_customer", "ims_supplier", "ims_warehouse"):
            assert db.execute(f"SELECT COUNT(*) FROM {table} WHERE remark LIKE '%演示%'").fetchone()[0] == 0
        record = json.loads(db.execute("SELECT config_value FROM sys_param WHERE config_key='zhicang_init_import_inventory_standard-v1'").fetchone()[0])
        assert len(record["records"]["ims_goods"]) == 30 and len(record["records"]["sys_user"]) == 10
        assert db.execute("SELECT COUNT(*) FROM ims_purchase_in WHERE status=0").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM ims_purchase_in WHERE status=2").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM ims_stock_balance WHERE quantity<0").fetchone()[0] == 0
        assert not db.execute(
            "SELECT b.warehouse_id, b.goods_id FROM ims_stock_balance b LEFT JOIN (SELECT warehouse_id,goods_id,SUM(change_quantity) q FROM ims_stock_log GROUP BY warehouse_id,goods_id) l ON b.warehouse_id=l.warehouse_id AND b.goods_id=l.goods_id WHERE l.q IS NULL OR ABS(b.quantity-l.q)>0.00001"
        ).fetchall()
    assert payload(import_command(installed_env, *args, "--apply"))["skipped"]
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        assert {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in counts} == counts
    result = import_command(installed_env, *args, "--apply", "--base-date", "2026-10-14")
    assert result.returncode != 0 and "INIT_DATA_CONFLICT" in result.stderr
    result = import_command(installed_env, *args, "--dry-run", "--dataset", "second-batch")
    assert result.returncode != 0 and "IMPORT_DATA_CONFLICT" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("table", ["apscheduler_jobs", "agno_sessions"])
def test_check_is_read_only_and_detects_auxiliary_loss(installed_env: dict[str, str], table: str) -> None:
    """验收不改数据库，辅助表丢失时启动也不得补建。"""
    path = Path(installed_env["DATABASE_NAME"])
    before = path.read_bytes()
    payload(command(installed_env, "init-check", "--database-only"))
    assert path.read_bytes() == before
    with sqlite3.connect(path) as db:
        db.execute(f'DROP TABLE "{table}"')
    result = command(installed_env, "run")
    assert result.returncode != 0 and "INIT_AUX_SCHEMA_INVALID" in result.stdout + result.stderr
    with sqlite3.connect(path) as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE name=?", (table,)).fetchall()
    payload(command(installed_env, "init-db", "--apply"))
    payload(command(installed_env, "init-check", "--database-only"))


def test_check_detects_dangling_organization(installed_env: dict[str, str]) -> None:
    """只读验收报告组织关联损坏，不自动修改用户部门。"""
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        db.execute("UPDATE sys_user SET dept_id=999999")
    result = command(installed_env, "init-check", "--database-only")
    assert result.returncode != 0 and "INIT_DATA_CONFLICT" in result.stderr


def test_org_example_is_executable_and_conflicts_are_preserved(installed_env: dict[str, str]) -> None:
    """部署示例使用真实权限，重跑不会覆盖人工更改后的授权。"""
    installed_env["ORG_WAREHOUSE_PASSWORD"] = "TmpWarehouse#2026"
    args = ("init-org", "--file", str(BACKEND / "examples" / "organization.json"))
    assert payload(command(installed_env, *args, "--apply"))["created"]["users"] == 1
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        db.execute("UPDATE sys_role SET data_scope=3 WHERE code='WAREHOUSE_READER'")
    result = command(installed_env, *args, "--apply")
    assert result.returncode != 0 and "INIT_DATA_CONFLICT" in result.stderr
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        assert db.execute("SELECT data_scope FROM sys_role WHERE code='WAREHOUSE_READER'").fetchone()[0] == 3


def test_invalid_configuration_is_sanitized(deployment_env: dict[str, str]) -> None:
    """配置解析失败仅报告类型，不输出含凭据的原始输入或堆栈。"""
    deployment_env["DATABASE_PORT"] = "not-a-port-sensitive-value"
    result = command(deployment_env, "init-db", "--dry-run")
    assert result.returncode == 2 and "INIT_CONFIG_INVALID" in result.stderr
    assert "not-a-port-sensitive-value" not in result.stderr and "Traceback" not in result.stderr


def test_concurrent_initialization_is_rejected(deployment_env: dict[str, str]) -> None:
    """写入命令争用同一SQLite文件锁，冲突时不能开始建表。"""
    path = Path(f"{deployment_env['DATABASE_NAME']}.init.lock")
    with path.open("w+b") as handle:
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = command(deployment_env, "init-db", "--apply")
        assert result.returncode == 3 and "INIT_LOCKED" in result.stderr
        assert not Path(deployment_env["DATABASE_NAME"]).exists()


def test_scheduler_jobstore_never_creates_its_table() -> None:
    """绕过生命周期检查时，作业存储本身仍须拒绝自动建表。"""
    from unittest.mock import Mock

    from sqlalchemy import create_engine, inspect

    from app.core.ap_scheduler import ExistingSQLAlchemyJobStore

    engine = create_engine("sqlite:///:memory:")
    store = ExistingSQLAlchemyJobStore(engine=engine)
    try:
        with pytest.raises(RuntimeError, match="APP_NOT_INITIALIZED"):
            store.start(Mock(), "sqlalchemy")
        assert not inspect(engine).has_table("apscheduler_jobs")
        store.jobs_t.create(engine)
        store.start(Mock(), "sqlalchemy")
    finally:
        engine.dispose()


@pytest.mark.parametrize("environment,username", [("dev", "super"), ("prod", "super"), ("dev", "admin"), ("prod", "admin")])
def test_bootstrap_account_defaults(deployment_env: dict[str, str], environment: str, username: str) -> None:
    """两种环境均按账号使用默认值，不额外创建其他账号。"""
    from app.utils.password_util import PwdUtil

    deployment_env.pop("INIT_ADMIN_PASSWORD", None)
    deployment_env["INIT_ADMIN_USERNAME"] = username
    payload(command(deployment_env, "init-db", f"--env={environment}", "--apply"))
    with sqlite3.connect(deployment_env["DATABASE_NAME"]) as db:
        rows = db.execute("SELECT username,password FROM sys_user").fetchall()
        assert len(rows) == 1 and rows[0][0] == username
        assert PwdUtil.verify_password(PwdUtil.default_initial_password(username), rows[0][1])


def test_org_missing_password_reference_uses_account_default(installed_env: dict[str, str], tmp_path: Path) -> None:
    """组织文件可省略口令变量，普通用户使用统一默认值。"""
    from app.utils.password_util import PwdUtil

    path = org_file(tmp_path / "defaults.json", users=[{"username": "default_reader", "name": "查询员", "dept_code": "BUY", "role_codes": ["BUYER"]}])
    payload(command(installed_env, "init-org", "--file", str(path), "--apply"))
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        password = db.execute("SELECT password FROM sys_user WHERE username='default_reader'").fetchone()[0]
        assert PwdUtil.verify_password("zcy123456@#", password)


def test_inventory_import_conflict_leaves_no_partial_organization(installed_env: dict[str, str]) -> None:
    """同用户名冲突在组织写入前拒绝，预检和apply都不得覆盖。"""
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        db.execute("UPDATE sys_user SET username='zhangming' WHERE username='super'")
        original = db.execute("SELECT id,password,is_superuser FROM sys_user").fetchall()
    for mode in ("--dry-run", "--apply"):
        result = import_command(installed_env, "--env=dev", mode)
        assert result.returncode == 3 and "IMPORT_DATA_CONFLICT" in result.stderr
        with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
            assert db.execute("SELECT id,password,is_superuser FROM sys_user").fetchall() == original
            assert db.execute("SELECT COUNT(*) FROM sys_dept").fetchone()[0] == 1
            assert db.execute("SELECT COUNT(*) FROM ims_goods").fetchone()[0] == 0


def test_legacy_audit_is_readonly_and_detects_external_references(installed_env: dict[str, str], tmp_path: Path) -> None:
    """在临时库还原旧批次，精确识别候选且不忽略跨批组织引用。"""
    import hashlib

    payload(import_command(installed_env, "--env=dev", "--apply"))
    prefix = "D" + hashlib.sha256(b"standard-v1").hexdigest()[:10]
    jobs = ("manager", "buyer", "seller", "keeper", "finance", "viewer", "buyer2", "seller2", "keeper2", "finance2")
    accounts = [f"{prefix.lower()}_{key}" for key in jobs]
    with sqlite3.connect(installed_env["DATABASE_NAME"]) as db:
        row = db.execute("SELECT id,config_value FROM sys_param WHERE config_key='zhicang_init_import_inventory_standard-v1'").fetchone()
        record = json.loads(row[1])
        for identifier, username in zip(record["records"]["sys_user"], accounts, strict=True):
            db.execute("UPDATE sys_user SET username=? WHERE id=?", (username, identifier))
        for table in ("sys_role", "sys_position"):
            for identifier, code in db.execute(f"SELECT id,code FROM {table}").fetchall():
                if identifier in record["records"][table]:
                    db.execute(f"UPDATE {table} SET code=? WHERE id=?", (f"{prefix}_{code.lower()}", identifier))
        for identifier in record["records"]["sys_dept"]:
            code = db.execute("SELECT code FROM sys_dept WHERE id=?", (identifier,)).fetchone()[0]
            db.execute("UPDATE sys_dept SET code=? WHERE id=?", (f"{prefix}_{code}", identifier))
        for identifier in record["records"]["ims_goods_category"]:
            name = db.execute("SELECT name FROM ims_goods_category WHERE id=?", (identifier,)).fetchone()[0]
            db.execute("UPDATE ims_goods_category SET name=? WHERE id=?", (f"{prefix}_{name}", identifier))
        for table, field in (("ims_goods", "goods_code"), ("ims_customer", "customer_code"), ("ims_supplier", "supplier_code"), ("ims_warehouse", "warehouse_code")):
            for identifier, code in db.execute(f"SELECT id,{field} FROM {table}").fetchall():
                db.execute(f"UPDATE {table} SET {field}=? WHERE id=?", (f"{prefix}_{code}", identifier))
        for table in ("ims_purchase_in", "ims_sale_out", "ims_purchase_return", "ims_sale_return", "ims_stock_opening", "ims_stock_check"):
            db.execute(f"UPDATE {table} SET remark='演示数据集 standard-v1'")
        record["counts"]["accounts"] = accounts
        db.execute("UPDATE sys_param SET config_key='zhicang_init_demo_standard-v1', config_value=? WHERE id=?", (json.dumps(record), row[0]))
        db.execute("UPDATE sys_param SET config_key='zhicang_init_org_demo-standard-v1' WHERE config_key='zhicang_init_org_import-standard-v1'")
    path = Path(installed_env["DATABASE_NAME"])
    before = path.read_bytes()
    report = tmp_path / "audit.json"
    result = subprocess.run([sys.executable, "scripts/audit_legacy_inventory.py", "--env=dev", "--report", str(report)], cwd=BACKEND, env=installed_env, input="", capture_output=True, text=True, encoding="utf-8", timeout=90)
    payload(result)
    assert path.read_bytes() == before
    value = json.loads(report.read_text(encoding="utf-8"))
    batch = value["batches"][0]
    assert batch["counts"]["ims_goods"] == 30 and batch["counts"]["ims_business_log"] > 0
    assert batch["external_references"] == [] and batch["warnings"] == [] and not value["deleted"]
    with sqlite3.connect(path) as db:
        sequence_before = db.execute("SELECT * FROM ims_document_sequence").fetchall()
        db.execute("UPDATE sys_user SET dept_id=? WHERE username='super'", (record["records"]["sys_dept"][0],))
    result = subprocess.run([sys.executable, "scripts/audit_legacy_inventory.py", "--env=dev"], cwd=BACKEND, env=installed_env, input="", capture_output=True, text=True, encoding="utf-8", timeout=90)
    batch = payload(result)["batches"][0]
    assert any(row["table"] == "sys_user" and row["field"] == "dept_id" for row in batch["external_references"])
    backup = tmp_path / "backup"
    backup.mkdir()
    cleanup_args = [sys.executable, "scripts/cleanup_legacy_inventory.py", "--env=dev", "--approved-report", str(report), "--backup-dir", str(backup), "--dataset", "standard-v1", "--apply", "--maintenance-confirmed"]
    result = subprocess.run(cleanup_args, cwd=BACKEND, env=installed_env, input="", capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert result.returncode != 0 and "CLEANUP_SCOPE_CHANGED" in result.stderr
    assert not list(backup.iterdir())
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM ims_goods").fetchone()[0] == 30
        db.execute("UPDATE sys_user SET dept_id=1 WHERE username='super'")
        before_name = db.execute("SELECT config_value FROM sys_param WHERE config_key='sys_name'").fetchone()[0]
        db.execute("CREATE TRIGGER cleanup_guard_test BEFORE DELETE ON ims_goods BEGIN UPDATE sys_param SET config_value='unexpected' WHERE config_key='sys_name'; END")
    result = subprocess.run(cleanup_args, cwd=BACKEND, env=installed_env, input="", capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert result.returncode != 0 and "CLEANUP_VERIFICATION_FAILED" in result.stderr
    assert (backup / "target-rows.json").exists() and not (backup / "completed.json").exists()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM ims_goods").fetchone()[0] == 30
        assert db.execute("SELECT config_value FROM sys_param WHERE config_key='sys_name'").fetchone()[0] == before_name
        db.execute("DROP TRIGGER cleanup_guard_test")
    backup = tmp_path / "backup-success"
    backup.mkdir()
    cleanup_args[cleanup_args.index("--backup-dir") + 1] = str(backup)
    result = subprocess.run(cleanup_args, cwd=BACKEND, env=installed_env, input="", capture_output=True, text=True, encoding="utf-8", timeout=90)
    completed = payload(result)
    assert completed["committed"] and completed["retained_verified"]
    assert (backup / "target-rows.json").stat().st_size > 0
    saved = json.loads((backup / "target-rows.json").read_text(encoding="utf-8"))
    assert len(saved["rows"]["ims_goods"]) == 30 and len(saved["rows"]["sys_user"]) == 10
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM ims_goods").fetchone()[0] == 0
        assert db.execute("SELECT username FROM sys_user").fetchall() == [("super",)]
        assert db.execute("SELECT COUNT(*) FROM ims_stock_log").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM sys_param WHERE config_key LIKE 'zhicang_init_%'").fetchone()[0] == 0
        assert db.execute("SELECT * FROM ims_document_sequence").fetchall() == sequence_before
