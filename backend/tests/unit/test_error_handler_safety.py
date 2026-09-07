"""An error handler must not touch an ORM object after a rollback.

The incident, 2026-09-07, in the Spotify OAuth callback:

    except Exception as exc:
        await session.rollback()
        logger.exception("Spotify callback failed internal_id=%s", current_user.id)

`rollback()` expires every ORM instance in the session — independent of
`expire_on_commit`, which only governs commit. Reading `current_user.id`
afterwards therefore issues a refresh SELECT, which is synchronous IO in an
async context, and SQLAlchemy raises `MissingGreenlet`.

That exception is raised *while evaluating the arguments to
`logger.exception`*, so the logging call never runs. The original error — the
thing the handler existed to report — is destroyed, and the client gets an
unhandled 500 with a stack trace about greenlets instead of the fault.

Eight handlers had it. Every one was a 500 path, which is to say every one was
already the unhappy path nobody exercises, and the bug converted a
diagnosable failure into an undiagnosable one. It survived a full test suite
because no test forced a commit to fail.

The fix is one line per handler — capture the id into a local before the try —
and it is entirely un-reviewable: the broken and fixed versions look equally
correct, and nothing fails until a commit fails in production. So it is
checked here structurally instead.

**The rule:** inside an `except` handler, after `session.rollback()`, only
plain locals and module-level names may be dereferenced. Anything else has to
be captured into a local first.
"""

import ast
from pathlib import Path

import pytest

_API_DIR = Path(__file__).parent.parent.parent / "app" / "api" / "v1"
_SERVICES_DIR = Path(__file__).parent.parent.parent / "app" / "services"

_MODULES = sorted(_API_DIR.glob("*.py")) + sorted(_SERVICES_DIR.glob("*.py"))


def _module_level_names(tree: ast.Module) -> set[str]:
    """Imports and module-level bindings — `status`, `logger`, `settings`, …

    These are safe to dereference after a rollback: they are not ORM objects
    and hold no session state.
    """
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _is_rollback(node: ast.stmt) -> bool:
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and sub.func.attr == "rollback"
        ):
            return True
    return False


def _unsafe_reads(tree: ast.Module, safe: set[str]) -> list[tuple[int, str]]:
    """Every `name.attr` read after a rollback inside an except handler."""
    offenders: list[tuple[int, str]] = []

    for handler in (n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)):
        # The handler's own exception variable is a plain object, not ORM.
        allowed = safe | ({handler.name} if handler.name else set())

        rolled_back = False
        for statement in handler.body:
            if not rolled_back:
                rolled_back = _is_rollback(statement)
                continue
            for sub in ast.walk(statement):
                if (
                    isinstance(sub, ast.Attribute)
                    and isinstance(sub.value, ast.Name)
                    and sub.value.id not in allowed
                ):
                    offenders.append((sub.lineno, f"{sub.value.id}.{sub.attr}"))
    return offenders


def test_there_are_modules_to_check() -> None:
    """Guards the sweep below against silently checking nothing."""
    assert len(_MODULES) > 5


@pytest.mark.parametrize("module", _MODULES, ids=lambda p: p.name)
def test_no_orm_access_after_rollback(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    offenders = _unsafe_reads(tree, _module_level_names(tree))

    assert offenders == [], (
        f"{module.name}: {offenders} — dereferenced after session.rollback() "
        "inside an except handler. rollback() expires every ORM object in the "
        "session, so this issues a refresh SELECT: synchronous IO in an async "
        "context, raising MissingGreenlet from inside the error handler and "
        "destroying the original exception before it can be logged. Capture "
        "the value into a local before the try block."
    )
