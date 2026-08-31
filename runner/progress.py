"""Progress narration for the pipeline.

Tells the user a task is running, so a slow run does not look frozen.
Written to stderr: visible on the terminal, leaves stdout for the result.
Any method can import `announce` and call it for its own sub-steps.
"""
import click


def announce(text):
    """Print one progress line to stderr."""
    click.echo(text, err=True)
