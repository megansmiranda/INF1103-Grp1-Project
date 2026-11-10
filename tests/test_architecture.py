"""Checks the brief's structural rules: no procedural code left, the four managers
exist as classes, and only the IO Manager talks to the screen."""
import ast
import inspect
from pathlib import Path

from nutrilenz.ai.ai_manager import AIManager
from nutrilenz.ai.ai_provider import AIProvider
from nutrilenz.ai.ai_task import AITask
from nutrilenz.data.data_manager import DataManager
from nutrilenz.data.data_store import DataStore
from nutrilenz.domain.goal import Goal
from nutrilenz.domain.dietary_check import DietaryCheck
from nutrilenz.logic.logic_manager import LogicManager
from nutrilenz.logic.rule import Rule
from nutrilenz.web.io_manager import WebIOManager

PACKAGE = Path(__file__).resolve().parent.parent / "nutrilenz"


def python_files():
    return sorted(PACKAGE.rglob("*.py"))


def test_no_module_level_functions():
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = [node.name for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert functions == [], f"{path.name} has procedural functions: {functions}"


def test_only_io_manager_prints_or_reads_input():
    for path in python_files():
        if path.parent.name == "web":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = [node.func.id for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        assert "print" not in calls and "input" not in calls, path.name


def test_four_managers_are_classes():
    for manager in (WebIOManager, AIManager, LogicManager, DataManager):
        assert inspect.isclass(manager)


def test_abstract_bases_cannot_be_created_and_have_subclasses():
    for base in (AIProvider, AITask, Goal, DietaryCheck, Rule, DataStore):
        assert inspect.isabstract(base)
        assert base.__subclasses__(), base.__name__
