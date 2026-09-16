"""Progress narration for the pipeline.

Tells the user a task is running, so a slow run does not look frozen.
Written to stderr: visible on the terminal, leaves stdout for the result.
Any method can import `announce` and call it for its own sub-steps.
"""
import click

_listener = None


def set_listener(callback):
    """Register callback(text, level) to be called on every announce(). Pass None to clear."""
    global _listener
    _listener = callback


def announce(text, level=0):
    """Print one progress line to stderr. `level` indents sub-steps (2 spaces each)."""
    click.echo("  " * level + text, err=True)
    if _listener:
        _listener(text, level)
