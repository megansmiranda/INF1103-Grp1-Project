import copy
import threading

from ..domain.analysis import Analysis
from ..domain.flag import Flag
from ..domain.product import Product
from ..domain.user import User
from ..errors.data_error import DataError
from .mapper import RecordMapper
from .data_store import DataStore


class InMemoryDataStore(DataStore):
    """Keeps everything in memory. Used by the tests and when no database is set up.
    It follows the same contract as MySQLDataStore, including returning fresh copies."""

    def __init__(self):
        self._mapper = RecordMapper()
        self._lock = threading.Lock()          # jobs run on several threads
        self._users: dict[int, dict] = {}
        self._products: dict[int, dict] = {}
        self._analyses: dict[int, dict] = {}
        self._next_id = {"user": 1, "product": 1, "analysis": 1}

    def initialise(self) -> None:
        return None

    def _new_id(self, kind: str) -> int:
        new_id = self._next_id[kind]
        self._next_id[kind] += 1
        return new_id

    # --- users ---
    def add_user(self, user: User) -> User:
        with self._lock:
            if self._find_row(user.username) is not None:
                raise DataError("DUPLICATE_USER")
            user.assign_id(self._new_id("user"))
            self._users[user.user_id] = self._mapper.user_to_row(user)
            return user

    def _find_row(self, username: str) -> dict | None:
        wanted = username.strip().casefold()
        for row in self._users.values():
            if row["username"].casefold() == wanted:
                return row
        return None

    def find_user(self, username: str) -> User | None:
        with self._lock:
            row = self._find_row(username)
            return self._mapper.user_from_row(copy.deepcopy(row)) if row else None

    def get_user(self, user_id: int) -> User | None:
        with self._lock:
            row = self._users.get(user_id)
            return self._mapper.user_from_row(copy.deepcopy(row)) if row else None

    def update_profile(self, user: User) -> None:
        with self._lock:
            if user.user_id not in self._users:
                raise DataError("USER_NOT_FOUND")
            self._users[user.user_id] = self._mapper.user_to_row(user)

    def delete_user(self, user_id: int) -> bool:
        with self._lock:
            if self._users.pop(user_id, None) is None:
                return False
            self._analyses = {k: v for k, v in self._analyses.items() if v["user_id"] != user_id}
            return True

    def count_users(self) -> int:
        with self._lock:
            return len(self._users)

    # --- products ---
    def add_product(self, product: Product) -> Product:
        with self._lock:
            product.assign_id(self._new_id("product"))
            self._products[product.product_id] = self._mapper.product_to_row(product)
            return product

    def get_product(self, product_id: int) -> Product | None:
        with self._lock:
            row = self._products.get(product_id)
            return self._mapper.product_from_row(copy.deepcopy(row)) if row else None

    def list_products(self) -> list[Product]:
        with self._lock:
            return [self._mapper.product_from_row(copy.deepcopy(row))
                    for row in self._products.values()]

    # --- analyses ---
    def add_analysis(self, analysis: Analysis) -> Analysis:
        with self._lock:
            if analysis.user_id not in self._users:
                raise DataError("USER_NOT_FOUND")
            if analysis.product.product_id not in self._products:
                raise DataError("RECORD_NOT_FOUND", "product is not saved")
            analysis.assign_id(self._new_id("analysis"))
            self._analyses[analysis.analysis_id] = self._mapper.analysis_to_row(analysis)
            return analysis

    def _load(self, row: dict) -> Analysis:
        product = self._mapper.product_from_row(copy.deepcopy(self._products[row["product_id"]]))
        return self._mapper.analysis_from_row(copy.deepcopy(row), product)

    def list_analyses(self, user_id: int, flag: Flag | None = None,
                      search: str | None = None) -> list[Analysis]:
        with self._lock:
            rows = [row for row in self._analyses.values() if row["user_id"] == user_id]
            if search:
                wanted = search.strip().casefold()
                rows = [row for row in rows
                        if wanted in self._products[row["product_id"]]["product_name"].casefold()]
            rows.sort(key=lambda row: (row["analysed_at"], row["analysis_id"]), reverse=True)
            records = [self._load(row) for row in rows]
            return [record for record in records if flag is None or record.has_flag(flag)]

    def get_analysis(self, user_id: int, analysis_id: int) -> Analysis | None:
        with self._lock:
            row = self._analyses.get(analysis_id)
            if row is None or row["user_id"] != user_id:
                return None
            return self._load(row)

    def delete_analysis(self, user_id: int, analysis_id: int) -> bool:
        with self._lock:
            row = self._analyses.get(analysis_id)
            if row is None or row["user_id"] != user_id:
                return False
            del self._analyses[analysis_id]
            return True
