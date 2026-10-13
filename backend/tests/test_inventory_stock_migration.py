from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_stock_snapshot_migration_preserves_legacy_rows() -> None:
    """迁移保留旧实盘数据，新快照为空且可回退，不伪造历史快照。"""
    path = Path(__file__).parents[1] / "app/alembic/versions/2026_10_12_1848_fa28c1122c75.py"
    spec = spec_from_file_location("stock_snapshot_migration", path)
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE ims_stock_check_item (id INTEGER PRIMARY KEY, actual_quantity NUMERIC(18,3) NOT NULL)"))
        connection.execute(text("INSERT INTO ims_stock_check_item VALUES (1, 2.5)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert {"system_stock_amount", "balance_version"} <= {col["name"] for col in inspect(connection).get_columns("ims_stock_check_item")}
        row = connection.execute(text("SELECT actual_quantity, system_stock_amount, balance_version FROM ims_stock_check_item")).one()
        assert tuple(row) == (2.5, None, None)
        migration.downgrade()
        assert connection.scalar(text("SELECT actual_quantity FROM ims_stock_check_item")) == 2.5
        assert "balance_version" not in {col["name"] for col in inspect(connection).get_columns("ims_stock_check_item")}
    engine.dispose()
