"""Makes documentation drift fail the build.

`tests/test_documentation.py` checks that the docs do not *link* to things that
do not exist. This file checks that they do not *describe* things that do not
exist: it reads the Python examples out of the Markdown and validates every
call in them against the real signature in the source tree.

Five separate documentation drifts in one refactor motivated this, and each was
caught by a human reading rather than by a check:

1. Three guides shipped examples that raise `TypeError` on the first call
   (`search_character_moments` without its required `show_name`,
   `get_character_relationships` likewise, `find_similar_characters(...,
   show_name=None)` against a `str` parameter, `adapt_content_for_platform`
   without `quality_profile`), and one that called `_chunk_transcript()`, a
   method that has never existed.
2. `docs/evals.md` said the eval gate "is what CI runs" when CI had no eval
   step.
3. `docs/portfolio-refinement.md` went stale twice.
4. `docs/test-baseline.md` described the pre-refactor world in the present
   tense.
5. A README note described a component with zero callers.

## How symbols are resolved: the source tree, not `import`

Signatures come from parsing the first-party source with `ast`, not from
importing it. `inspect.Signature.bind` still does the validation - the
signatures are real `inspect.Signature` objects, just built statically. The
reasons for not importing:

* `import main` configures file logging as a side effect, and the docs import
  it (`from main import AnimeVideoGenerator`). A documentation check should not
  write to the working tree.
* Importing `agents.*` pulls torch, chromadb and sentence-transformers - about
  1.1 GB and several seconds. This check is meant to run in a CI job that
  installs nothing, so that a docs failure is legible in seconds rather than
  buried behind a dependency install.
* A static index gives the same answer in every environment. An import-based
  check silently weakens wherever an optional dependency is missing.

The cost is that decorator-rewritten or dynamically attached signatures are
invisible here. Nothing in this repo's documented surface is either.

## Opting out

Some blocks are illustrative, not runnable: a fragment of a dict, an excerpt of
a method body, a hand-written signature listing. Put a directive in an HTML
comment on the line before the fence:

    <!-- docs-check: skip - why this block is not runnable -->
    ```python
    ...
    ```

A reason is mandatory; `skip` on its own is rejected. Use it sparingly - a
skipped block is an unchecked claim.

Two directives do better than skipping where they apply:

    <!-- docs-check: signatures core.content_cache.ContentCache -->

        The block is a hand-written signature listing. Every `def` in it must
        match the real method: same parameter names, same order, same
        defaultedness. This is what would have caught the two methods
        `docs/CONTENT_CACHING_GUIDE.md` documented that do not exist.

    <!-- docs-check: bind self=agents.character_analysis_agent.CharacterAnalysisAgent -->

        Names a type for a receiver the block never assigns, so `self.foo(...)`
        or `agent.foo(...)` can be checked instead of skipped.

One further directive applies to prose rather than to a block:

    <!-- docs-check: absent BaseMetadata.create - removed in 7eabf6f -->

        Lets a doc name a symbol in order to say it does *not* exist, without
        the existence check flagging the very sentence that is telling the
        truth. It is an inverted assertion, not an exemption: if the symbol
        comes back, the build says so.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Packages whose contents the docs are allowed to reference as first-party
# symbols. Anything outside this set is treated as third-party and left alone.
FIRST_PARTY_ROOTS = ("agents", "config", "core", "evals", "media", "utils")
FIRST_PARTY_MODULES = ("main",)


def documentation_files() -> list[Path]:
    """Every Markdown file this contract applies to."""
    files = sorted((PROJECT_ROOT / "docs").rglob("*.md"))
    files.append(PROJECT_ROOT / "README.md")
    return [f for f in files if f.exists()]


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


# ---------------------------------------------------------------------------
# A static index of the first-party source
# ---------------------------------------------------------------------------


@dataclass
class ClassInfo:
    name: str
    module: str
    bases: list[str]
    methods: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = field(default_factory=dict)
    attributes: set[str] = field(default_factory=set)

    @property
    def qualname(self) -> str:
        return f"{self.module}.{self.name}"


@dataclass
class ModuleInfo:
    name: str
    classes: dict[str, ClassInfo] = field(default_factory=dict)
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = field(default_factory=dict)
    names: set[str] = field(default_factory=set)


@dataclass
class SourceIndex:
    modules: dict[str, ModuleInfo] = field(default_factory=dict)
    classes_by_name: dict[str, list[ClassInfo]] = field(default_factory=dict)
    methods_by_name: dict[str, list[ClassInfo]] = field(default_factory=dict)

    def module(self, dotted: str) -> ModuleInfo | None:
        return self.modules.get(dotted)

    def resolve_dotted(self, dotted: str) -> object | None:
        """Resolve `core.content_cache.ContentCache` against the source tree.

        Returns a ModuleInfo, a ClassInfo, an ast function node, or None when
        the path does not exist. Only first-party paths are resolvable; callers
        must check `is_first_party` first.
        """
        parts = dotted.split(".")
        for cut in range(len(parts), 0, -1):
            mod = self.modules.get(".".join(parts[:cut]))
            if mod is None:
                continue
            rest = parts[cut:]
            if not rest:
                return mod
            if len(rest) == 1:
                if rest[0] in mod.classes:
                    return mod.classes[rest[0]]
                if rest[0] in mod.functions:
                    return mod.functions[rest[0]]
                if rest[0] in mod.names:
                    return mod.names
                return None
            if len(rest) == 2 and rest[0] in mod.classes:
                return self.lookup_member(mod.classes[rest[0]], rest[1])
            return None
        return None

    def lookup_member(self, cls: ClassInfo, name: str) -> object | None:
        """Find `name` on `cls` or on any first-party base, breadth-first."""
        seen: set[str] = set()
        queue = [cls]
        while queue:
            current = queue.pop(0)
            if current.qualname in seen:
                continue
            seen.add(current.qualname)
            if name in current.methods:
                return current.methods[name]
            if name in current.attributes:
                return current
            for base in current.bases:
                queue.extend(self.classes_by_name.get(base.split(".")[-1], []))
        return None

    def has_unresolvable_base(self, cls: ClassInfo) -> bool:
        """True when a base class is not first-party, so members may be inherited."""
        seen: set[str] = set()
        queue = [cls]
        while queue:
            current = queue.pop(0)
            if current.qualname in seen:
                continue
            seen.add(current.qualname)
            for base in current.bases:
                resolved = self.classes_by_name.get(base.split(".")[-1], [])
                if not resolved:
                    return True
                queue.extend(resolved)
        return False


def _is_first_party(dotted: str) -> bool:
    head = dotted.split(".")[0]
    return head in FIRST_PARTY_ROOTS or head in FIRST_PARTY_MODULES


def _module_name_for(path: Path) -> str:
    rel = path.relative_to(PROJECT_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _source_files() -> list[Path]:
    files: list[Path] = []
    for root in FIRST_PARTY_ROOTS:
        base = PROJECT_ROOT / root
        if base.is_dir():
            files.extend(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
    for mod in FIRST_PARTY_MODULES:
        candidate = PROJECT_ROOT / f"{mod}.py"
        if candidate.exists():
            files.append(candidate)
    return sorted(files)


def _self_attributes(node: ast.ClassDef) -> set[str]:
    """Attribute names assigned as `self.x = ...` anywhere in the class body."""
    found: set[str] = set()
    for sub in ast.walk(node):
        targets: list[ast.expr] = []
        if isinstance(sub, ast.Assign):
            targets = list(sub.targets)
        elif isinstance(sub, ast.AnnAssign | ast.AugAssign):
            targets = [sub.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                found.add(target.attr)
    return found


@lru_cache(maxsize=1)
def source_index() -> SourceIndex:
    index = SourceIndex()
    for path in _source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # pragma: no cover - a broken source fails elsewhere
            continue
        info = ModuleInfo(name=_module_name_for(path))
        index.modules[info.name] = info
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls = ClassInfo(
                    name=node.name,
                    module=info.name,
                    bases=[ast.unparse(b) for b in node.bases],
                    attributes=_self_attributes(node),
                )
                for item in node.body:
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        cls.methods[item.name] = item
                    elif isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                cls.attributes.add(target.id)
                    elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        cls.attributes.add(item.target.id)
                info.classes[node.name] = cls
                info.names.add(node.name)
                index.classes_by_name.setdefault(node.name, []).append(cls)
                for method in cls.methods:
                    index.methods_by_name.setdefault(method, []).append(cls)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                info.functions[node.name] = node
                info.names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        info.names.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                info.names.add(node.target.id)
    return index


# ---------------------------------------------------------------------------
# ast function node -> inspect.Signature
# ---------------------------------------------------------------------------

_EMPTY = inspect.Parameter.empty


def _annotation(node: ast.expr | None) -> object:
    return _EMPTY if node is None else ast.unparse(node)


def signature_from_ast(
    func: ast.FunctionDef | ast.AsyncFunctionDef, *, drop_first: bool = False
) -> inspect.Signature:
    """Build a real `inspect.Signature` from a parsed `def`."""
    a = func.args
    params: list[inspect.Parameter] = []

    positional = list(a.posonlyargs) + list(a.args)
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(a.defaults))
    defaults += list(a.defaults)

    for i, (arg, default) in enumerate(zip(positional, defaults, strict=True)):
        kind = (
            inspect.Parameter.POSITIONAL_ONLY
            if i < len(a.posonlyargs)
            else inspect.Parameter.POSITIONAL_OR_KEYWORD
        )
        params.append(
            inspect.Parameter(
                arg.arg,
                kind,
                default=_EMPTY if default is None else ast.unparse(default),
                annotation=_annotation(arg.annotation),
            )
        )

    if drop_first and params:
        params.pop(0)

    if a.vararg is not None:
        params.append(
            inspect.Parameter(
                a.vararg.arg,
                inspect.Parameter.VAR_POSITIONAL,
                annotation=_annotation(a.vararg.annotation),
            )
        )
    for arg, default_node in zip(a.kwonlyargs, a.kw_defaults, strict=True):
        params.append(
            inspect.Parameter(
                arg.arg,
                inspect.Parameter.KEYWORD_ONLY,
                default=_EMPTY if default_node is None else ast.unparse(default_node),
                annotation=_annotation(arg.annotation),
            )
        )
    if a.kwarg is not None:
        params.append(
            inspect.Parameter(
                a.kwarg.arg,
                inspect.Parameter.VAR_KEYWORD,
                annotation=_annotation(a.kwarg.annotation),
            )
        )
    return inspect.Signature(params)


# ---------------------------------------------------------------------------
# Extracting Python blocks and their directives
# ---------------------------------------------------------------------------

FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^\s`]*)")
DIRECTIVE = re.compile(r"<!--\s*docs-check:\s*(.*?)\s*-->", re.S)


@dataclass
class Block:
    doc: Path
    line: int
    code: str
    skip_reason: str | None = None
    signatures_of: str | None = None
    receivers: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{_rel(self.doc)}:{self.line}"


def _parse_directives(raw: str, block: Block, problems: list[str]) -> None:
    for body in DIRECTIVE.findall(raw):
        text = " ".join(body.split())
        if text.startswith("skip"):
            reason = text[len("skip") :].lstrip(" -:").strip()
            if not reason:
                problems.append(
                    f"{block}: `docs-check: skip` needs a reason "
                    "(`skip - why this block is not runnable`)."
                )
            block.skip_reason = reason or "(no reason given)"
        elif text.startswith("signatures"):
            target = text[len("signatures") :].strip()
            if not target:
                problems.append(f"{block}: `docs-check: signatures` needs a dotted target.")
            block.signatures_of = target
        elif text.startswith("absent"):
            pass  # a file-scoped assertion, handled by TestDocumentedSymbolsExist
        elif text.startswith("bind"):
            for pair in text[len("bind") :].split():
                name, _, dotted = pair.partition("=")
                if not dotted:
                    problems.append(f"{block}: `docs-check: bind` wants `name=dotted.Path`.")
                    continue
                block.receivers[name] = dotted
        else:
            problems.append(f"{block}: unknown docs-check directive {text!r}.")


def extract_python_blocks(doc: Path, problems: list[str]) -> list[Block]:
    """Fenced ```python blocks, with any docs-check directives above them."""
    lines = doc.read_text(encoding="utf-8").splitlines()
    blocks: list[Block] = []
    i = 0
    pending: list[str] = []
    while i < len(lines):
        match = FENCE.match(lines[i])
        if not match:
            if lines[i].strip():
                pending.append(lines[i])
                pending[:] = pending[-4:]
            i += 1
            continue
        indent, ticks, info = match.groups()
        start = i
        i += 1
        body: list[str] = []
        closer = re.compile(rf"^\s*{re.escape(ticks[0])}{{{len(ticks)},}}\s*$")
        while i < len(lines) and not closer.match(lines[i]):
            body.append(lines[i][len(indent) :] if lines[i].startswith(indent) else lines[i])
            i += 1
        i += 1
        if info.lower() not in {"python", "py", "python3"}:
            pending = []
            continue
        block = Block(doc=doc, line=start + 1, code="\n".join(body))
        _parse_directives("\n".join(pending), block, problems)
        blocks.append(block)
        pending = []

    # `bind` is file-scoped: a guide declares its subject once at the top and
    # every `self.foo(...)` in it is then checkable, wherever the comment sits.
    file_scoped = Block(doc=doc, line=0, code="")
    _parse_directives(doc.read_text(encoding="utf-8"), file_scoped, [])
    if file_scoped.receivers:
        for block in blocks:
            block.receivers = {**file_scoped.receivers, **block.receivers}
    return blocks


def parse_block(code: str) -> ast.Module | None:
    """Parse a doc example, tolerating a bare top-level `await`."""
    try:
        return ast.parse(code)
    except SyntaxError:
        pass
    if "await " not in code:
        return None
    indented = "\n".join("    " + line if line.strip() else line for line in code.splitlines())
    try:
        wrapped = ast.parse("async def _docs_example():\n" + indented)
    except SyntaxError:
        return None
    body = wrapped.body[0]
    assert isinstance(body, ast.AsyncFunctionDef)
    return ast.Module(body=body.body, type_ignores=[])


# ---------------------------------------------------------------------------
# Check 1: every documented call binds against a real signature
# ---------------------------------------------------------------------------

_NON_OPTIONAL = re.compile(r"^(str|int|float|bool|bytes|list|dict|set|tuple)(\[.*\])?$")


@dataclass
class _Instance:
    cls: ClassInfo


class CallChecker(ast.NodeVisitor):
    """Resolves the calls in one document's examples and binds them.

    One checker runs over every block in a file, in order, because guides are
    written as a sequence: `agent = CharacterAnalysisAgent()` in the setup
    block is what makes `agent.search_character_moments(...)` three blocks
    later checkable at all. Treating each block as an island is how the
    original examples, which called three methods without their required
    `show_name`, sailed through review.
    """

    def __init__(self, index: SourceIndex) -> None:
        self.block: Block | None = None
        self.index = index
        self.problems: list[str] = []
        self.env: dict[str, object] = {}
        self.local_defs: set[str] = set()

    def enter(self, block: Block) -> None:
        self.block = block
        for name, dotted in block.receivers.items():
            resolved = self.index.resolve_dotted(dotted)
            if isinstance(resolved, ClassInfo):
                self.env.setdefault(name, _Instance(resolved))
            else:
                self.problems.append(
                    f"{block}: `docs-check: bind {name}={dotted}` does not resolve to a class."
                )

    # -- bookkeeping -------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            target = alias.asname or alias.name.split(".")[0]
            mod = self.index.module(alias.name)
            if mod is not None:
                self.env[target] = mod
            else:
                self.local_defs.add(target)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = self.index.module(node.module or "")
        for alias in node.names:
            target = alias.asname or alias.name
            member = None if mod is None else (mod.classes.get(alias.name))
            if member is not None:
                self.env[target] = member
            elif mod is not None and alias.name in mod.functions:
                self.env[target] = mod.functions[alias.name]
            elif mod is not None and alias.name not in mod.names:
                self.problems.append(
                    f"{self.block}: `from {node.module} import {alias.name}` - "
                    f"{node.module} defines no {alias.name}."
                )
                self.local_defs.add(target)
            else:
                self.local_defs.add(target)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.local_defs.add(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.local_defs.add(node.name)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        inferred = self._infer(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if inferred is not None:
                    self.env[target.id] = inferred
                else:
                    self.env.pop(target.id, None)
                    self.local_defs.add(target.id)
            elif isinstance(target, ast.Tuple):
                for element in target.elts:
                    if isinstance(element, ast.Name):
                        self.env.pop(element.id, None)
                        self.local_defs.add(element.id)

    def visit_For(self, node: ast.For) -> None:
        for name in ast.walk(node.target):
            if isinstance(name, ast.Name):
                self.local_defs.add(name.id)
                self.env.pop(name.id, None)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.local_defs.add(node.name)
        self.generic_visit(node)

    def visit_withitem(self, node: ast.withitem) -> None:
        if isinstance(node.optional_vars, ast.Name):
            self.local_defs.add(node.optional_vars.id)
        self.generic_visit(node)

    def _infer(self, value: ast.expr) -> object | None:
        """The type of an assignment's right-hand side, when it is knowable."""
        if isinstance(value, ast.Await):
            return self._infer(value.value)
        if not isinstance(value, ast.Call):
            return None
        target = self._resolve_callee(value.func)
        if isinstance(target, ClassInfo):
            return _Instance(target)
        return None

    # -- resolution --------------------------------------------------------

    def _resolve_callee(self, func: ast.expr) -> object | None:
        if isinstance(func, ast.Name):
            if func.id in self.env:
                return self.env[func.id]
            if func.id in self.local_defs or hasattr(builtins, func.id):
                return None
            unique = self.index.classes_by_name.get(func.id, [])
            if len(unique) == 1:
                return unique[0]
            return None
        if isinstance(func, ast.Attribute):
            owner = self._resolve_owner(func.value)
            if isinstance(owner, _Instance):
                member = self.index.lookup_member(owner.cls, func.attr)
                if member is None:
                    if self.index.has_unresolvable_base(owner.cls):
                        return None
                    self.problems.append(
                        f"{self.block}: `{ast.unparse(func)}(...)` - "
                        f"{owner.cls.qualname} has no attribute {func.attr!r}."
                    )
                    return None
                return member
            if isinstance(owner, ModuleInfo):
                if func.attr in owner.classes:
                    return owner.classes[func.attr]
                if func.attr in owner.functions:
                    return owner.functions[func.attr]
                if func.attr in owner.names:
                    return None
                self.problems.append(
                    f"{self.block}: `{ast.unparse(func)}(...)` - "
                    f"module {owner.name} defines no {func.attr!r}."
                )
                return None
            return self._resolve_unknown_receiver(func)
        return None

    def _resolve_owner(self, value: ast.expr) -> object | None:
        if isinstance(value, ast.Name):
            return self.env.get(value.id)
        return None

    def _resolve_unknown_receiver(self, func: ast.Attribute) -> object | None:
        """Last resort for `something.method(...)` where `something` is opaque.

        A method name owned by exactly one first-party class is assumed to be
        that one: `format_adapter.adapt_content_for_platform(...)` has only one
        possible meaning in this repo. A private name owned by none is a bug in
        the docs by construction - `self._chunk_transcript(...)` cannot be
        third-party. Everything else is left alone, because
        `self.model.with_structured_output(...)` is langchain's and not ours.
        """
        owners = self.index.methods_by_name.get(func.attr, [])
        if len(owners) == 1:
            return owners[0].methods[func.attr]
        if not owners and func.attr.startswith("_") and not func.attr.startswith("__"):
            self.problems.append(
                f"{self.block}: `{ast.unparse(func)}(...)` - no first-party class defines a "
                f"method named {func.attr!r}, and a private name cannot come from a "
                "third-party object."
            )
        return None

    # -- the actual check --------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)
        target = self._resolve_callee(node.func)
        if target is None:
            return
        rendered = ast.unparse(node.func)
        if isinstance(target, ClassInfo):
            init = self.index.lookup_member(target, "__init__")
            if not isinstance(init, ast.FunctionDef | ast.AsyncFunctionDef):
                return
            signature = signature_from_ast(init, drop_first=True)
            label = f"{target.qualname}(...)"
        elif isinstance(target, ast.FunctionDef | ast.AsyncFunctionDef):
            decorators = {ast.unparse(d) for d in target.decorator_list}
            bound = (
                isinstance(node.func, ast.Attribute)
                and not isinstance(self._resolve_owner(node.func.value), ModuleInfo)
                and "staticmethod" not in decorators
            )
            if "classmethod" in decorators:
                bound = True  # `cls` is supplied by the descriptor either way
            signature = signature_from_ast(target, drop_first=bound)
            label = f"{rendered}(...)"
        else:
            return
        self._bind(node, signature, label)

    def _bind(self, node: ast.Call, signature: inspect.Signature, label: str) -> None:
        args: list[object] = []
        kwargs: dict[str, object] = {}
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                return  # *args defeats static binding
            args.append(arg)
        for keyword in node.keywords:
            if keyword.arg is None:
                return  # **kwargs likewise
            kwargs[keyword.arg] = keyword.value
        try:
            bound = signature.bind(*args, **kwargs)
        except TypeError as exc:
            self.problems.append(
                f"{self.block}: `{label}` does not match the real signature "
                f"{label.split('(')[0]}{signature} - {exc}."
            )
            return
        for name, value in bound.arguments.items():
            parameter = signature.parameters[name]
            if (
                isinstance(value, ast.Constant)
                and value.value is None
                and isinstance(parameter.annotation, str)
                and _NON_OPTIONAL.match(parameter.annotation)
            ):
                self.problems.append(
                    f"{self.block}: `{label}` passes None for {name!r}, "
                    f"which is annotated `{parameter.annotation}`."
                )


def check_document(blocks: list[Block], index: SourceIndex) -> list[str]:
    """Check one document's examples, carrying names forward between blocks."""
    checker = CallChecker(index)
    problems: list[str] = []
    for block in blocks:
        if block.skip_reason is not None:
            continue
        if block.signatures_of is not None:
            problems.extend(check_signature_listing(block, index))
            continue
        tree = parse_block(block.code)
        if tree is None:
            problems.append(
                f"{block}: this ```python block is not valid Python. Either fix it or mark it "
                "`<!-- docs-check: skip - <reason> -->` if it is a fragment."
            )
            continue
        checker.enter(block)
        checker.visit(tree)
    problems.extend(checker.problems)
    # A call reached through an assignment is resolved twice (once to infer the
    # target's type, once to bind it); report each distinct problem once.
    return list(dict.fromkeys(problems))


# ---------------------------------------------------------------------------
# The signature-listing directive
# ---------------------------------------------------------------------------


def _listing_shape(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[str, str, bool]]:
    signature = signature_from_ast(func)
    return [
        (name, str(p.kind), p.default is not _EMPTY)
        for name, p in signature.parameters.items()
        if name not in {"self", "cls"}
    ]


def check_signature_listing(block: Block, index: SourceIndex) -> list[str]:
    target = block.signatures_of or ""
    problems: list[str] = []
    if not _is_first_party(target):
        return [f"{block}: `docs-check: signatures {target}` is not a first-party path."]
    resolved = index.resolve_dotted(target)
    if resolved is None:
        return [f"{block}: `docs-check: signatures {target}` does not resolve."]

    source = block.code
    if not source.lstrip().startswith("class "):
        # A listing of bare `def`s; give it a class wrapper so it parses.
        source = "class _Listing:\n" + "\n".join(
            "    " + line if line.strip() else line for line in source.splitlines()
        )
    # Hand-written listings have no bodies. Give each `def` a `...`.
    source = re.sub(r"(\)(?:\s*->[^\n:]+)?)\s*:?\s*(?=\n|$)", r"\1: ...", source)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{block}: signature listing does not parse ({exc.msg})."]

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if isinstance(resolved, ClassInfo):
            real = index.lookup_member(resolved, node.name)
            where = resolved.qualname
        else:
            assert isinstance(resolved, ModuleInfo)
            real = resolved.functions.get(node.name)
            where = resolved.name
        if not isinstance(real, ast.FunctionDef | ast.AsyncFunctionDef):
            problems.append(f"{block}: documents `{node.name}()`, which {where} does not define.")
            continue
        documented, actual = _listing_shape(node), _listing_shape(real)
        if documented != actual:
            problems.append(
                f"{block}: `{node.name}{signature_from_ast(node, drop_first=True)}` does not "
                f"match {where}.{node.name}{signature_from_ast(real, drop_first=True)}."
            )
    return problems


# ---------------------------------------------------------------------------
# Tests: executable examples
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _blocks_by_document() -> tuple[dict[Path, list[Block]], list[str]]:
    problems: list[str] = []
    grouped: dict[Path, list[Block]] = {}
    for doc in documentation_files():
        grouped[doc] = extract_python_blocks(doc, problems)
    return grouped, problems


def _all_blocks() -> list[Block]:
    grouped, _ = _blocks_by_document()
    return [block for blocks in grouped.values() for block in blocks]


class TestDocumentedExamples:
    """Every ``` ```python ``` block in the docs describes a call that exists."""

    def test_directives_are_well_formed(self):
        _, problems = _blocks_by_document()
        assert not problems, "\n" + "\n".join(problems)

    def test_calls_match_real_signatures(self):
        grouped, _ = _blocks_by_document()
        index = source_index()
        problems: list[str] = []
        for blocks in grouped.values():
            problems.extend(check_document(blocks, index))
        assert not problems, (
            "\nThe documentation describes calls the source does not support:\n\n"
            + "\n".join(f"  - {p}" for p in problems)
        )

    def test_opt_outs_stay_rare(self):
        """A skipped block is an unchecked claim; keep the habit expensive."""
        blocks = _all_blocks()
        skipped = [str(b) for b in blocks if b.skip_reason is not None]
        assert len(skipped) <= max(6, len(blocks) // 3), (
            f"{len(skipped)} of {len(blocks)} documented examples opt out of checking: "
            f"{skipped}. Prefer `docs-check: signatures` or a runnable example."
        )


# ---------------------------------------------------------------------------
# Check 2: documented symbols exist
# ---------------------------------------------------------------------------

# A dotted path rooted in a first-party package: core.content_cache.ContentCache.
MODULE_PATH = re.compile(r"^[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+$")
# A class-qualified member: WorkflowOrchestrator.process_episode_complete()
MEMBER_PATH = re.compile(r"^([A-Z][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)(\(\))?$")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCED = re.compile(r"^```.*?^```", re.S | re.M)


def _prose(markdown: str) -> str:
    """Markdown with fenced blocks and HTML comments removed."""
    return re.sub(r"<!--.*?-->", "", FENCED.sub("", markdown), flags=re.S)


ABSENT_DIRECTIVE = re.compile(r"<!--\s*docs-check:\s*absent\s+([A-Za-z_][\w.]*)\s*-[^>]*-->")


def _documented_symbols(doc: Path) -> list[str]:
    text = _prose(doc.read_text(encoding="utf-8"))
    return [token.strip() for token in CODE_SPAN.findall(text)]


def _declared_absent(doc: Path) -> set[str]:
    """Symbols a doc names in order to say they do *not* exist.

    A guide sometimes has to mention a removed API - "there is deliberately no
    `BaseMetadata.create()`" - and a bare existence check would flag exactly
    the sentence that is telling the truth. Rather than an ignore list, this is
    an inverted assertion: the named symbol must stay absent, so re-adding it
    fails the build and the prose gets revisited.

        <!-- docs-check: absent BaseMetadata.create - removed in 7eabf6f -->
    """
    return set(ABSENT_DIRECTIVE.findall(doc.read_text(encoding="utf-8")))


class TestDocumentedSymbolsExist:
    """`core.content_cache.ContentCache` in a doc must name something real.

    Deliberately narrow. A backticked dotted token is only checked when its
    first segment is a first-party package (`core`, `agents`, ...) or a class
    name defined exactly once in the source. That leaves `time.sleep`,
    `cv2.imread`, `result.data` and `AIMessage.usage_metadata` alone, which is
    the point: a check that trips over ordinary prose gets routed around.
    """

    def test_first_party_module_paths_resolve(self):
        index = source_index()
        problems: list[str] = []
        for doc in documentation_files():
            for token in _documented_symbols(doc):
                if token.endswith(("()", ",")):
                    token = token.rstrip("(),")
                if not MODULE_PATH.match(token) or not _is_first_party(token):
                    continue
                if token.rsplit(".", 1)[-1] in {"py", "md", "json", "toml", "txt", "yml", "cfg"}:
                    continue
                if index.resolve_dotted(token) is None:
                    problems.append(f"{_rel(doc)}: `{token}` does not exist in the source tree.")
        assert not problems, "\n" + "\n".join(problems)

    def test_class_members_resolve(self):
        index = source_index()
        problems: list[str] = []
        for doc in documentation_files():
            absent = _declared_absent(doc)
            for token in _documented_symbols(doc):
                match = MEMBER_PATH.match(token)
                if not match:
                    continue
                class_name, member, _ = match.groups()
                candidates = index.classes_by_name.get(class_name, [])
                if len(candidates) != 1:
                    continue  # not ours, or ambiguous
                cls = candidates[0]
                if member.startswith("__") and member.endswith("__"):
                    continue
                exists = index.lookup_member(cls, member) is not None
                if f"{class_name}.{member}" in absent:
                    if exists:
                        problems.append(
                            f"{_rel(doc)}: declares `{class_name}.{member}` absent, but "
                            f"{cls.qualname} defines it now. Update the prose."
                        )
                    continue
                if not exists and not index.has_unresolvable_base(cls):
                    problems.append(
                        f"{_rel(doc)}: `{token}` - {cls.qualname} has no member {member!r}."
                    )
        assert not problems, "\n" + "\n".join(problems)


# ---------------------------------------------------------------------------
# Check 3: claims that cannot be checked mechanically carry evidence
# ---------------------------------------------------------------------------

# The sha is optional and informational: it records the commit at which the
# number was measured, for a human reading the doc. `sources:` is the part the
# build acts on.
VERIFIED_TAG = re.compile(
    r"<!--\s*verified:\s*(?:([0-9a-f]{7,40})\s+)?sources:\s*([^>]+?)\s*-->",
)

# Files whose load-bearing numbers are not derivable from any committed
# artifact, so a tag is the only evidence available. Everything else is checked
# directly against the thing it describes - see TestEvalNumbersMatchTheBaseline.
FILES_REQUIRING_A_CLAIM_TAG = ("docs/telemetry.md",)


def _git(*args: str, cwd: Path = PROJECT_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


@lru_cache(maxsize=1)
def _git_available() -> bool:
    return _git("rev-parse", "--git-dir").returncode == 0


@lru_cache(maxsize=1)
def _repo_is_shallow() -> bool:
    return _git("rev-parse", "--is-shallow-repository").stdout.strip() == "true"


def _last_commit(path: str, cwd: Path = PROJECT_ROOT) -> str | None:
    """The full sha of the last commit touching ``path``, or ``None`` if never committed."""
    return _git("log", "-1", "--format=%H", "--", path, cwd=cwd).stdout.strip() or None


def _has_uncommitted_changes(path: str, cwd: Path = PROJECT_ROOT) -> bool:
    return bool(_git("status", "--porcelain", "--", path, cwd=cwd).stdout.strip())


def _sources_changed_after_doc(
    doc: str, sources: Sequence[str], cwd: Path = PROJECT_ROOT
) -> list[tuple[str, str]]:
    """``(source, short sha)`` for every source last touched after the doc was.

    ``git log <doc commit>..HEAD -- <source>`` excludes everything reachable
    from the doc's own last commit, so a source edited *in the same commit as
    the doc* does not appear. That is the whole point: committing the doc
    alongside the code it describes is what makes this pass.
    """
    doc_commit = _last_commit(doc, cwd=cwd)
    if doc_commit is None:
        return []  # never committed - nothing to be stale against
    changed: list[tuple[str, str]] = []
    for source in sources:
        log = _git("log", "--format=%h", f"{doc_commit}..HEAD", "--", source, cwd=cwd).stdout
        if log.strip():
            changed.append((source, log.split()[0]))
    return changed


class TestVerifiedClaims:
    """A doc with a claim tag must be at least as new as the code it cites.

    A measured number - the telemetry stage table, a timing, a cost - cannot be
    recomputed by a unit test without running the thing that produced it. The
    tag names the files that determine it, and the build fails when one of them
    is touched in a commit later than the doc's own last commit.

    **Why this is not compared against the tagged sha.** It used to be, and it
    cried wolf three times out of four. A tag can never cite the commit that
    lands it - the sha does not exist until after the commit is written - so
    every doc was permanently one commit behind by construction, and every code
    change demanded a follow-up commit whose entire content was bumping shas.
    Friction that pointless is routed around, and a check people route around
    is not a check. Comparing two facts git already knows removes the bump
    entirely: update the doc in the same commit as the code and there is
    nothing left to maintain.

    The sha survives as provenance - "this table was measured at 7e48b43" is
    worth telling a reader - but nothing is gated on it.

    What this still catches, which is the case that matters: `core/database.py`
    changes, `docs/data-model.md` does not, and the build says so.

    What it cannot catch: whether the human who touched the doc actually
    re-read the claim. File granularity means a source edit that cannot
    possibly affect the claim still asks for a look; the answer is to narrow
    `sources:` to the files that really determine it. And a doc with
    uncommitted changes is taken as current, because failing someone while they
    are in the middle of writing the fix is exactly the crying wolf this
    replaces.

    Applied to a handful of numbers on purpose. Tagging prose would make every
    sentence a merge conflict, and the fix people would reach for is deleting
    the tag.
    """

    def test_tags_are_well_formed(self):
        """`sources:` must be non-empty and name real files; a sha must be a commit."""
        problems: list[str] = []
        for doc in documentation_files():
            for sha, raw_sources in VERIFIED_TAG.findall(doc.read_text(encoding="utf-8")):
                sources = [s.strip() for s in raw_sources.split(",") if s.strip()]
                if not sources:
                    problems.append(
                        f"{_rel(doc)}: a `verified:` tag lists no sources. The point of the "
                        f"tag is to record which files determine the claim."
                    )
                for source in sources:
                    if not (PROJECT_ROOT / source).exists():
                        problems.append(
                            f"{_rel(doc)}: `sources:` cites {source}, which does not exist. "
                            f"It was renamed or deleted - point the tag at whatever replaced "
                            f"it, and re-read the claim while you are there."
                        )
                if sha and _git_available():
                    kind = _git("cat-file", "-t", sha).stdout.strip()
                    if kind and kind != "commit":
                        problems.append(
                            f"{_rel(doc)}: `verified: {sha}` names a {kind}, not a commit."
                        )
        assert not problems, "\n" + "\n".join(problems)

    def test_cited_sources_have_not_moved_since_the_doc_did(self):
        if not _git_available():
            pytest.skip("not a git checkout")
        if _repo_is_shallow():
            pytest.skip("shallow clone: git cannot say when a file last changed")

        problems: list[str] = []
        for doc in documentation_files():
            tags = VERIFIED_TAG.findall(doc.read_text(encoding="utf-8"))
            if not tags:
                continue
            rel = _rel(doc)
            if _has_uncommitted_changes(rel):
                continue  # being edited right now; judge it once it lands
            sources = sorted(
                {
                    source.strip()
                    for _sha, raw in tags
                    for source in raw.split(",")
                    if source.strip() and (PROJECT_ROOT / source.strip()).exists()
                }
            )
            doc_commit = _last_commit(rel)
            for source, changed_in in _sources_changed_after_doc(rel, sources):
                problems.append(
                    f"{rel} last changed in {doc_commit[:7]}, but {source} - which its "
                    f"`verified:` tag says the claim rests on - changed later, in "
                    f"{changed_in}. Re-read the claim against the code and commit the doc "
                    f"with the change that affects it; that is all this check wants, and "
                    f"there is no sha to bump. If {source} does not actually determine the "
                    f"claim, drop it from `sources:` - the tag should cite the narrowest "
                    f"set of files that does, or it will cry wolf."
                )
        assert not problems, "\n" + "\n".join(problems)

    def test_measured_numbers_are_tagged(self):
        for name in FILES_REQUIRING_A_CLAIM_TAG:
            text = (PROJECT_ROOT / name).read_text(encoding="utf-8")
            assert VERIFIED_TAG.search(text), (
                f"{name} states measured numbers that no test can recompute. They need a "
                "`<!-- verified: [<sha>] sources: a.py, b.py -->` tag so the build notices "
                "when the code behind them moves."
            )


class TestTheStalenessRuleItself:
    """The check above is only worth having if it fails on real drift.

    Asserted against a throwaway three-commit repository rather than this one,
    because the interesting states - doc and code in one commit, code alone
    afterwards - cannot be staged in the live history.
    """

    @staticmethod
    def _repo(tmp_path: Path) -> Path:
        root = tmp_path / "repo"
        (root / "docs").mkdir(parents=True)
        _git("init", "-q", "-b", "main", str(root), cwd=tmp_path)
        _git("config", "user.email", "t@example.com", cwd=root)
        _git("config", "user.name", "T", cwd=root)
        return root

    @staticmethod
    def _commit(root: Path, message: str, files: dict[str, str]) -> None:
        for name, body in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        _git("add", "-A", cwd=root)
        _git("commit", "-qm", message, cwd=root)

    def test_doc_committed_with_the_code_is_current(self, tmp_path):
        """The landing-commit case the old sha comparison could never express."""
        root = self._repo(tmp_path)
        self._commit(root, "initial", {"code.py": "v1", "docs/guide.md": "describes v1"})
        self._commit(root, "change both", {"code.py": "v2", "docs/guide.md": "describes v2"})
        assert _sources_changed_after_doc("docs/guide.md", ["code.py"], cwd=root) == []

    def test_code_changed_without_the_doc_is_stale(self, tmp_path):
        root = self._repo(tmp_path)
        self._commit(root, "initial", {"code.py": "v1", "docs/guide.md": "describes v1"})
        self._commit(root, "change the code only", {"code.py": "v2"})
        stale = _sources_changed_after_doc("docs/guide.md", ["code.py"], cwd=root)
        assert [source for source, _sha in stale] == ["code.py"]

    def test_doc_updated_after_the_code_is_current(self, tmp_path):
        root = self._repo(tmp_path)
        self._commit(root, "initial", {"code.py": "v1", "docs/guide.md": "describes v1"})
        self._commit(root, "change the code only", {"code.py": "v2"})
        self._commit(root, "catch the doc up", {"docs/guide.md": "describes v2"})
        assert _sources_changed_after_doc("docs/guide.md", ["code.py"], cwd=root) == []


# ---------------------------------------------------------------------------
# Direct checks: preferred over a tag wherever the evidence is committed
# ---------------------------------------------------------------------------

BASELINE = PROJECT_ROOT / "evals" / "baseline.json"
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


class TestEvalNumbersMatchTheBaseline:
    """`docs/evals.md` quotes a scorecard. `evals/baseline.json` holds it.

    This is the check a claim tag would otherwise approximate, and it is
    strictly better: it compares the number in the prose to the number in the
    artifact rather than asking whether a file has changed.
    """

    @staticmethod
    def _doc() -> str:
        return (PROJECT_ROOT / "docs" / "evals.md").read_text(encoding="utf-8")

    @staticmethod
    def _baseline() -> dict:
        return json.loads(BASELINE.read_text(encoding="utf-8"))

    def test_aggregate_and_gate(self):
        doc, baseline = self._doc(), self._baseline()
        assert f"AGGREGATE             {baseline['aggregate_score']:.3f}" in doc, (
            f"docs/evals.md does not quote the committed aggregate "
            f"{baseline['aggregate_score']:.3f}."
        )
        for key in ("min_aggregate_score", "max_case_regression"):
            value = baseline["gate"][key]
            assert f"{value:.3f}" in doc or f"{value}" in doc, (
                f"docs/evals.md does not state the committed `gate.{key}` ({value})."
            )

    def test_per_case_scores(self):
        doc, baseline = self._doc(), self._baseline()
        missing = [
            f"{case} {data['score']:.3f}"
            for case, data in sorted(baseline["cases"].items())
            if not re.search(rf"^\s*{re.escape(case)}\s+{data['score']:.3f}\b", doc, re.M)
        ]
        assert not missing, f"docs/evals.md quotes stale per-case scores; expected {missing}."

    def test_metric_averages(self):
        doc, baseline = self._doc(), self._baseline()
        missing = [
            f"{metric} {value:.3f}"
            for metric, value in sorted(baseline["metric_averages"].items())
            if not re.search(rf"^\s*{re.escape(metric)}\s+{value:.3f}\b", doc, re.M)
        ]
        assert not missing, f"docs/evals.md quotes stale metric averages; expected {missing}."


class TestDocsDoNotInventCiSteps:
    """`docs/evals.md` once said the eval gate "is what CI runs". It did not.

    Any doc that says CI runs something must be able to point at the step.
    """

    CI_CLAIM = re.compile(r"(what CI runs|CI runs|runs in CI|gates? CI|in CI\b)", re.I)
    SCRIPT = re.compile(r"\b((?:[\w.-]+/)*[\w.-]+\.py)\b")

    def test_a_script_a_doc_says_ci_runs_is_in_the_workflow(self):
        """Every "CI runs X" in the docs has to point at a step that exists.

        The check looks at the claim's own line and the two above it, which is
        where the command sits in practice - in `docs/evals.md` it was the
        trailing comment on the command itself. Prose that claims CI runs
        something without naming a script is left alone; a regex cannot tell
        that apart from an aspiration, and guessing would make the check noisy.
        """
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        problems: list[str] = []
        for doc in documentation_files():
            if _rel(doc) == "docs/documentation-plan.md":
                continue  # a plan describes CI that does not exist yet, on purpose
            lines = doc.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines):
                if not self.CI_CLAIM.search(line):
                    continue
                window = "\n".join(lines[max(0, number - 2) : number + 1])
                for script in set(self.SCRIPT.findall(window)):
                    if "/" not in script:
                        continue  # a bare filename is too weak a signal
                    if script not in workflow:
                        problems.append(
                            f"{_rel(doc)}:{number + 1} says CI runs `{script}`, but "
                            f"{_rel(CI_WORKFLOW)} never invokes it."
                        )
        assert not problems, "\n" + "\n".join(problems)

    def test_docs_job_runs_this_file(self):
        """The docs contract is only enforcement if CI actually runs it."""
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        assert "tests/test_docs_contract.py" in workflow, (
            "CI has no step running the documentation contract, so nothing here can fail a build."
        )


class TestDocumentedPytestFlagsMatchPyproject:
    """A doc quoting pytest's configured flags has to quote the real ones.

    This replaces a ``verified:`` tag. ``docs/troubleshooting.md`` cited
    ``pyproject.toml`` wholesale, so every unrelated edit to that file - a
    version bump, a URL correction, a new lint rule - marked the doc stale and
    demanded a no-op commit. That is the same crying wolf the staleness rule was
    rewritten to avoid, reappearing at file granularity instead of sha
    granularity.

    The claim is one sentence and mechanically checkable, so it is checked
    directly instead. Same principle as the eval scorecard and the CI steps:
    where the evidence is committed, compare against it and drop the tag.
    """

    FLAG = re.compile(r"`(-m 'not network'|--timeout=\d+)`")

    def test_quoted_flags_are_really_in_addopts(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r"addopts\s*=\s*(\"\"\".*?\"\"\"|\'[^\']*\'|\"[^\"]*\")", pyproject, re.S)
        assert match, "pyproject.toml has no addopts for the docs to describe."
        configured = match.group(1)

        problems: list[str] = []
        for doc in documentation_files():
            if _rel(doc) == "docs/documentation-plan.md":
                continue  # a plan may describe configuration that does not exist yet
            for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines()):
                if "addopts" not in line and "pyproject" not in line:
                    continue
                for flag in self.FLAG.findall(line):
                    bare = flag.split("=")[0] if flag.startswith("--") else flag
                    if bare not in configured:
                        problems.append(
                            f"{_rel(doc)}:{number + 1} says pytest is configured with "
                            f"`{flag}`, but addopts in pyproject.toml does not carry it."
                        )
        assert not problems, "\n" + "\n".join(problems)
