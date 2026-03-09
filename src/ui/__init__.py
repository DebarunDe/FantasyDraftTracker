"""Fantasy Draft Tracker CLI interface."""

__all__ = ["DraftApp", "main"]


def __getattr__(name):
    if name in ("DraftApp", "main"):
        from src.ui.cli import DraftApp, main

        return DraftApp if name == "DraftApp" else main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
