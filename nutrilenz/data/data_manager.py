import logging
import threading

from ..domain.analysis import Analysis
from ..domain.flag import Flag
from ..domain.product import Product
from ..domain.user import User
from ..errors.auth_error import AuthError
from ..errors.data_error import DataError
from .passwords import PasswordHasher
from .data_store import DataStore

logger = logging.getLogger("nutrilenz.data")


class DataManager:
    """The one entry point for saving and loading. Works with any DataStore
    (MySQL or in-memory) and handles accounts and passwords."""

    def __init__(self, store: DataStore):
        self._store = store                     # given from outside, lives on its own
        self._hasher = PasswordHasher()         # created and owned by the manager
        self._ready = False
        self._ready_lock = threading.Lock()

    # --- start-up ---
    def ensure_ready(self) -> None:
        """Connect and create tables the first time. Raises DB_UNAVAILABLE if it still can't."""
        if self._ready:
            return
        with self._ready_lock:
            if not self._ready:
                self._store.initialise()
                self._ready = True

    @property
    def is_ready(self) -> bool:
        return self._ready

    def is_empty(self) -> bool:
        return self._store.count_users() == 0

    # --- accounts ---
    def register(self, username: str, password: str, goal_specs: list[dict],
                 avoid_ingredients: list[str], dietary_checks: list[str] | None = None) -> User:
        user = User(username, self._hasher.hash(password), goal_specs, avoid_ingredients,
                    dietary_checks=dietary_checks)
        return self._store.add_user(user)

    def authenticate(self, username: str, password: str) -> User:
        user = self._store.find_user(username)
        if user is None or not user.password_matches(password, self._hasher):
            raise AuthError("BAD_LOGIN")
        return user

    def get_user(self, user_id: int) -> User:
        user = self._store.get_user(user_id)
        if user is None:
            raise DataError("USER_NOT_FOUND")
        return user

    def update_profile(self, user: User, goal_specs: list[dict], avoid_ingredients: list[str],
                       dietary_checks: list[str] | None = None) -> User:
        if dietary_checks is not None:
            user.profile.replace_dietary_checks(dietary_checks)
        user.profile.replace_goals(goal_specs)
        user.profile.replace_avoid_list(avoid_ingredients)
        self._store.update_profile(user)
        return user

    def delete_account(self, user_id: int) -> None:
        if not self._store.delete_user(user_id):
            raise DataError("USER_NOT_FOUND")

    # --- products ---
    def save_product(self, product: Product) -> Product:
        """Reuse an identical saved product instead of storing a duplicate."""
        if product.product_id is not None:
            return product
        wanted = self._product_key(product)
        for saved in self._store.list_products():
            if self._product_key(saved) == wanted:
                product.assign_id(saved.product_id)
                return product
        return self._store.add_product(product)

    @staticmethod
    def _product_key(product: Product) -> tuple:
        data = product.to_dict()
        data.pop("product_id")
        return tuple(sorted((k, str(v).casefold()) for k, v in data.items()))

    def catalogue(self) -> list[Product]:
        return self._store.list_products()

    def categories(self) -> list[str]:
        names = {p.category.strip().title() for p in self._store.list_products() if p.category}
        return sorted(names)

    # --- analyses ---
    def save_analysis(self, analysis: Analysis) -> Analysis:
        self.save_product(analysis.product)
        return self._store.add_analysis(analysis)

    def history(self, user_id: int, flag: Flag | None = None, search: str | None = None) -> list[Analysis]:
        return self._store.list_analyses(user_id, flag, search)

    def get_analysis(self, user_id: int, analysis_id: int) -> Analysis:
        analysis = self._store.get_analysis(user_id, analysis_id)
        if analysis is None:
            raise DataError("RECORD_NOT_FOUND")
        return analysis

    def delete_analysis(self, user_id: int, analysis_id: int) -> None:
        if not self._store.delete_analysis(user_id, analysis_id):
            raise DataError("RECORD_NOT_FOUND")

    def previous_analyses(self, user_id: int, product_name: str) -> int:
        """How many times this user already analysed a product with this name."""
        wanted = product_name.strip().casefold()
        return sum(1 for record in self._store.list_analyses(user_id, search=product_name)
                   if record.product.name.casefold() == wanted)
