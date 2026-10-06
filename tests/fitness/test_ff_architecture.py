"""Static, atomic fitness function: bounded contexts may only import their own
package, the shared Published Language (ecogrid.contracts) or third-party code.
Complements import-linter (.importlinter) and also catches `from pkg import sub`."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "ecogrid"
CONTEXTS = {"marketplace", "meter_data", "settlement", "identity", "notifications"}


def imported_modules(tree: ast.AST, current: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import stays inside the current context
                continue
            base = node.module or ""
            found.add(base)
            found.update(f"{base}.{a.name}" for a in node.names)  # from x import sub
    return found


def violations_in(source: str, context: str) -> list[str]:
    bad = []
    for mod in imported_modules(ast.parse(source), context):
        parts = mod.split(".")
        target = parts[1] if parts[0] == "ecogrid" and len(parts) > 1 else parts[0]
        if target in CONTEXTS and target != context:
            bad.append(mod)
    return bad


def test_ff10_no_cross_context_imports():
    problems = []
    for ctx in CONTEXTS:
        for f in (ROOT / ctx).rglob("*.py"):
            problems += [f"{f.relative_to(ROOT)}: {m}" for m in violations_in(f.read_text(), ctx)]
    assert not problems, "Bounded-context violations:\n" + "\n".join(problems)


def test_ff10b_checker_catches_the_form_the_ai_version_missed():
    src = "from ecogrid.meter_data import acl\nfrom meter_data import infrastructure\n"
    assert len(violations_in(src, "marketplace")) >= 2
