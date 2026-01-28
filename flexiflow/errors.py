"""FlexiFlow error types with structured, actionable messages.

Error Contract:
Every user-facing error includes:
- What happened (one sentence, plain English)
- Why (root cause, not stack trace)
- Fix (specific, actionable)
- Context (relevant keys/paths, trimmed)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ErrorContext:
    """Structured context for error messages."""

    items: Dict[str, Any] = field(default_factory=dict)

    def add(self, key: str, value: Any) -> "ErrorContext":
        """Add a context item, returning self for chaining."""
        self.items[key] = value
        return self

    def format(self) -> str:
        """Format context as indented key=value lines."""
        if not self.items:
            return ""
        lines = [f"  {k}={v!r}" for k, v in self.items.items()]
        return "\n".join(lines)


class FlexiFlowError(Exception):
    """Base exception for FlexiFlow with structured error messages.

    Attributes:
        what: One-sentence description of what happened
        why: Root cause explanation
        fix: Actionable fix suggestion
        context: Relevant debugging context
    """

    def __init__(
        self,
        what: str,
        *,
        why: Optional[str] = None,
        fix: Optional[str] = None,
        context: Optional[ErrorContext] = None,
    ):
        self.what = what
        self.why = why
        self.fix = fix
        self.context = context or ErrorContext()

        # Build the full message
        message = self._format_message()
        super().__init__(message)

    def _format_message(self) -> str:
        """Format the full error message."""
        lines = [self.what]

        if self.why:
            lines.append(f"\nWhy: {self.why}")

        if self.fix:
            lines.append(f"\nFix: {self.fix}")

        ctx = self.context.format()
        if ctx:
            lines.append(f"\nContext:\n{ctx}")

        return "".join(lines)


class ConfigError(FlexiFlowError):
    """Error loading or validating configuration."""

    pass


class StateError(FlexiFlowError):
    """Error related to states or state machine."""

    pass


class PersistenceError(FlexiFlowError):
    """Error loading or saving state."""

    pass


class ImportError_(FlexiFlowError):
    """Error importing a dotted path symbol."""

    pass


# --- Helper constructors for common errors ---


def config_missing_field(field: str, path: Optional[str] = None) -> ConfigError:
    """Config is missing a required field."""
    ctx = ErrorContext()
    if path:
        ctx.add("config_path", path)
    ctx.add("field", field)

    return ConfigError(
        f"Config missing required field: '{field}'",
        why=f"The '{field}' field is required but was not found in the config.",
        fix=f"Add '{field}' to your config file.",
        context=ctx,
    )


def config_wrong_type(
    field: str, expected: str, got: str, path: Optional[str] = None
) -> ConfigError:
    """Config field has wrong type."""
    ctx = ErrorContext()
    if path:
        ctx.add("config_path", path)
    ctx.add("field", field)
    ctx.add("expected", expected)
    ctx.add("got", got)

    return ConfigError(
        f"Config field '{field}' has wrong type",
        why=f"Expected {expected}, but got {got}.",
        fix=f"Change '{field}' to be a {expected}.",
        context=ctx,
    )


def state_not_found(name: str, valid_states: list) -> StateError:
    """State name not found in registry."""
    # Show up to 5 valid states to avoid overwhelming output
    shown = valid_states[:5]
    more = len(valid_states) - 5 if len(valid_states) > 5 else 0

    valid_str = ", ".join(shown)
    if more > 0:
        valid_str += f" (+{more} more)"

    ctx = ErrorContext()
    ctx.add("requested_state", name)
    ctx.add("valid_states", shown)

    return StateError(
        f"Unknown state: '{name}'",
        why="The requested state is not registered in the state registry.",
        fix=f"Use one of the valid states: {valid_str}\n"
        "Or register your custom state with DEFAULT_REGISTRY.register(name, StateClass)",
        context=ctx,
    )


def persistence_invalid_json(path: str, error: str) -> PersistenceError:
    """Persistence file contains invalid JSON."""
    ctx = ErrorContext()
    ctx.add("path", path)
    ctx.add("error", error)

    return PersistenceError(
        f"Invalid JSON in state file: {path}",
        why="The file exists but contains malformed JSON.",
        fix="Check the file for syntax errors, or delete it to start fresh.",
        context=ctx,
    )


def persistence_missing_field(path: str, field: str) -> PersistenceError:
    """Persistence file is missing a required field."""
    ctx = ErrorContext()
    ctx.add("path", path)
    ctx.add("field", field)

    return PersistenceError(
        f"State file missing required field: '{field}'",
        why=f"The state file exists but is missing the '{field}' field.",
        fix="This may indicate a corrupted file. Delete it to start fresh, "
        "or manually add the missing field.",
        context=ctx,
    )


def import_invalid_format(dotted_path: str) -> ImportError_:
    """Dotted path has invalid format."""
    ctx = ErrorContext()
    ctx.add("dotted_path", dotted_path)

    return ImportError_(
        f"Invalid dotted path format: '{dotted_path}'",
        why="Dotted paths must be in 'module:ClassName' format.",
        fix="Use the format 'mypackage.module:MyClass' (colon separates module from class).",
        context=ctx,
    )


def import_module_not_found(module: str, dotted_path: str) -> ImportError_:
    """Module in dotted path not found."""
    ctx = ErrorContext()
    ctx.add("module", module)
    ctx.add("dotted_path", dotted_path)

    return ImportError_(
        f"Module not found: '{module}'",
        why="The module specified in the dotted path could not be imported.",
        fix="Check that the module exists and is on your Python path.\n"
        "You may need to install the package or add its directory to sys.path.",
        context=ctx,
    )


def import_symbol_not_found(module: str, symbol: str, dotted_path: str) -> ImportError_:
    """Symbol not found in module."""
    ctx = ErrorContext()
    ctx.add("module", module)
    ctx.add("symbol", symbol)
    ctx.add("dotted_path", dotted_path)

    return ImportError_(
        f"Symbol '{symbol}' not found in module '{module}'",
        why="The module was imported successfully, but doesn't contain that symbol.",
        fix="Check the spelling of the class/function name.\n"
        "Make sure it's defined at the top level of the module.",
        context=ctx,
    )


def import_not_state_subclass(dotted_path: str, got_type: str) -> ImportError_:
    """Imported symbol is not a State subclass."""
    ctx = ErrorContext()
    ctx.add("dotted_path", dotted_path)
    ctx.add("got_type", got_type)

    return ImportError_(
        f"Not a State subclass: '{dotted_path}'",
        why=f"Expected a State subclass, but got {got_type}.",
        fix="Make sure your class inherits from flexiflow.State:\n"
        "  from flexiflow import State\n"
        "  class MyState(State): ...",
        context=ctx,
    )
