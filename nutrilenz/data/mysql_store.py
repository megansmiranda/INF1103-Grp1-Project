import json
import logging
from contextlib import contextmanager
from pathlib import Path

import pymysql
import pymysql.cursors

from ..domain.analysis import Analysis
from ..domain.flag import Flag
from ..domain.product import Product
from ..domain.user import User
from ..errors.data_error import DataError
from .mapper import RecordMapper
from .data_store import DataStore

logger = logging.getLogger("nutrilenz.data")


class MySQLDataStore(DataStore):
    """Stores everything in MySQL. Opens a short connection per call, so it is safe
    to use from several job threads. Connection problems become DB_UNAVAILABLE."""

    SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"

    def __init__(self, host: str, port: int, user: str, password: str, database: str,
                 connect_timeout: int = 5):
        self._settings = {"host": host, "port": port, "user": user, "password": password,
                          "database": database, "connect_timeout": connect_timeout,
                          "charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor,
                          "autocommit": False}
        self._mapper = RecordMapper()

    @contextmanager
    def _cursor(self):
        """One connection + transaction. Commits on success, rolls back on any error."""
        try:
            connection = pymysql.connect(**self._settings)
        except pymysql.MySQLError as error:
            logger.error("Cannot connect to MySQL: %r", error)
            raise DataError("DB_UNAVAILABLE") from error
        try:
            with connection.cursor() as cursor:
                yield cursor
            connection.commit()
        except pymysql.err.IntegrityError as error:
            connection.rollback()
            if error.args and error.args[0] == 1062:          # duplicate key
                raise DataError("DUPLICATE_USER") from error
            raise DataError("RECORD_NOT_FOUND", str(error)) from error
        except pymysql.MySQLError as error:
            connection.rollback()
            logger.error("MySQL error: %r", error)
            raise DataError("DB_UNAVAILABLE") from error
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialise(self) -> None:
        with self._cursor() as cursor:
            for statement in self.schema_statements():
                cursor.execute(statement)
            # Additive upgrade: existing NULL rows load with no checks/results.
            for table, column in (("users", "dietary_checks"), ("analyses", "dietary_results")):
                cursor.execute("SHOW COLUMNS FROM " + table + " LIKE %s", (column,))
                if cursor.fetchone() is None:
                    cursor.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " JSON NULL")

    @classmethod
    def schema_statements(cls) -> list[str]:
        """CREATE TABLE statements from schema.sql. Comment lines are removed first,
        so a ';' inside a comment cannot split a statement."""
        lines = [line for line in cls.SCHEMA_FILE.read_text(encoding="utf-8").splitlines()
                 if not line.strip().startswith("--")]
        return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]

    @staticmethod
    def _json(text) -> object:
        """Decode a JSON column. A damaged value raises CORRUPT_DATA."""
        if isinstance(text, (dict, list)):
            return text
        try:
            return json.loads(text)
        except (TypeError, ValueError) as error:
            raise DataError("CORRUPT_DATA") from error

    # --- users ---
    def add_user(self, user: User) -> User:
        row = self._mapper.user_to_row(user)
        with self._cursor() as cursor:
            cursor.execute("INSERT INTO users (username, password_hash, avoid_ingredients, dietary_checks) "
                           "VALUES (%s, %s, %s, %s)",
                           (row["username"], row["password_hash"], json.dumps(row["avoid_ingredients"]),
                            json.dumps(row["dietary_checks"])))
            user.assign_id(cursor.lastrowid)
            self._write_goals(cursor, user.user_id, row["goals"])
        return user

    @staticmethod
    def _write_goals(cursor, user_id: int, goals: list[dict]) -> None:
        cursor.execute("DELETE FROM goals WHERE user_id = %s", (user_id,))
        for goal in goals:
            cursor.execute("INSERT INTO goals (user_id, nutrient, direction, target) "
                           "VALUES (%s, %s, %s, %s)",
                           (user_id, goal["nutrient"], goal["direction"], goal["target"]))

    def _load_user(self, cursor, where: str, value) -> User | None:
        cursor.execute("SELECT user_id, username, password_hash, avoid_ingredients, dietary_checks FROM users "
                       "WHERE " + where, (value,))
        row = cursor.fetchone()
        if row is None:
            return None
        cursor.execute("SELECT nutrient, direction, target FROM goals WHERE user_id = %s "
                       "ORDER BY goal_id", (row["user_id"],))
        row["goals"] = [{"nutrient": g["nutrient"], "direction": g["direction"],
                         "target": float(g["target"])} for g in cursor.fetchall()]
        row["avoid_ingredients"] = self._json(row["avoid_ingredients"])
        row["dietary_checks"] = self._json(row["dietary_checks"]) if row.get("dietary_checks") else []
        try:
            return self._mapper.user_from_row(row)
        except (KeyError, ValueError) as error:
            raise DataError("CORRUPT_DATA") from error

    def find_user(self, username: str) -> User | None:
        with self._cursor() as cursor:
            return self._load_user(cursor, "username = %s", username.strip())

    def get_user(self, user_id: int) -> User | None:
        with self._cursor() as cursor:
            return self._load_user(cursor, "user_id = %s", user_id)

    def update_profile(self, user: User) -> None:
        row = self._mapper.user_to_row(user)
        with self._cursor() as cursor:
            changed = cursor.execute("UPDATE users SET avoid_ingredients = %s, dietary_checks = %s "
                                     "WHERE user_id = %s", (json.dumps(row["avoid_ingredients"]),
                                     json.dumps(row["dietary_checks"]), user.user_id))
            cursor.execute("SELECT 1 FROM users WHERE user_id = %s", (user.user_id,))
            if not changed and cursor.fetchone() is None:
                raise DataError("USER_NOT_FOUND")
            self._write_goals(cursor, user.user_id, row["goals"])

    def delete_user(self, user_id: int) -> bool:
        with self._cursor() as cursor:
            return cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,)) > 0

    def count_users(self) -> int:
        with self._cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM users")
            return int(cursor.fetchone()["n"])

    # --- products ---
    def add_product(self, product: Product) -> Product:
        row = self._mapper.product_to_row(product)
        with self._cursor() as cursor:
            cursor.execute("INSERT INTO products (product_name, brand, category, nutrition, "
                           "ingredient_text, marketing_claim) VALUES (%s, %s, %s, %s, %s, %s)",
                           (row["product_name"], row["brand"], row["category"],
                            json.dumps(row["nutrition"]), row["ingredient_text"],
                            row["marketing_claim"]))
            product.assign_id(cursor.lastrowid)
        return product

    def _product_from(self, row: dict) -> Product:
        row = dict(row)
        row["nutrition"] = self._json(row["nutrition"])
        try:
            return self._mapper.product_from_row(row)
        except (KeyError, ValueError) as error:
            raise DataError("CORRUPT_DATA") from error

    PRODUCT_COLUMNS = ("product_id, product_name, brand, category, nutrition, "
                       "ingredient_text, marketing_claim")

    def get_product(self, product_id: int) -> Product | None:
        with self._cursor() as cursor:
            cursor.execute("SELECT " + self.PRODUCT_COLUMNS + " FROM products WHERE product_id = %s",
                           (product_id,))
            row = cursor.fetchone()
        return self._product_from(row) if row else None

    def list_products(self) -> list[Product]:
        with self._cursor() as cursor:
            cursor.execute("SELECT " + self.PRODUCT_COLUMNS + " FROM products ORDER BY product_id")
            rows = cursor.fetchall()
        products = []
        for row in rows:
            try:
                products.append(self._product_from(row))
            except DataError:
                logger.warning("Skipped damaged product row %s", row.get("product_id"))
        return products

    # --- analyses ---
    def add_analysis(self, analysis: Analysis) -> Analysis:
        row = self._mapper.analysis_to_row(analysis)
        with self._cursor() as cursor:
            cursor.execute(
                "INSERT INTO analyses (user_id, product_id, profile_snapshot, ai_analysis, "
                "goal_results, flags, score, provider, analysed_at, dietary_results) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (row["user_id"], row["product_id"], json.dumps(row["profile_snapshot"]),
                 json.dumps(row["ai_analysis"]), json.dumps(row["goal_results"]),
                 json.dumps(row["flags"]), row["score"], row["provider"], row["analysed_at"],
                 json.dumps(row["dietary_results"])))
            analysis.assign_id(cursor.lastrowid)
        return analysis

    ANALYSIS_QUERY = ("SELECT a.*, p.product_name, p.brand, p.category, p.nutrition, "
                      "p.ingredient_text, p.marketing_claim FROM analyses a "
                      "JOIN products p ON p.product_id = a.product_id ")

    def _analysis_from(self, row: dict) -> Analysis:
        product = self._product_from(row)
        record = dict(row)
        record["dietary_results"] = self._json(row["dietary_results"]) if row.get("dietary_results") else None
        for column in ("profile_snapshot", "ai_analysis", "goal_results", "flags"):
            record[column] = self._json(record[column])
        try:
            return self._mapper.analysis_from_row(record, product)
        except (KeyError, ValueError, TypeError) as error:
            raise DataError("CORRUPT_DATA") from error

    def list_analyses(self, user_id: int, flag: Flag | None = None,
                      search: str | None = None) -> list[Analysis]:
        sql = self.ANALYSIS_QUERY + "WHERE a.user_id = %s"
        params: list = [user_id]
        if search:
            sql += " AND p.product_name LIKE %s"
            params.append("%" + search.strip().replace("%", r"\%").replace("_", r"\_") + "%")
        sql += " ORDER BY a.analysed_at DESC, a.analysis_id DESC"
        with self._cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        records = []
        for row in rows:
            try:
                record = self._analysis_from(row)
                if flag is None or record.has_flag(flag):
                    records.append(record)
            except DataError:
                logger.warning("Skipped damaged analysis row %s", row.get("analysis_id"))
        return records

    def get_analysis(self, user_id: int, analysis_id: int) -> Analysis | None:
        with self._cursor() as cursor:
            cursor.execute(self.ANALYSIS_QUERY + "WHERE a.user_id = %s AND a.analysis_id = %s",
                           (user_id, analysis_id))
            row = cursor.fetchone()
        return self._analysis_from(row) if row else None

    def delete_analysis(self, user_id: int, analysis_id: int) -> bool:
        with self._cursor() as cursor:
            return cursor.execute("DELETE FROM analyses WHERE user_id = %s AND analysis_id = %s",
                                  (user_id, analysis_id)) > 0
