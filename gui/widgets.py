"""
gui/widgets.py
Small reusable widget helpers shared by mureport.py and sections.py.
"""

import tkinter as tk


def make_shadow_button(parent, text, command, bg, fg, active_bg, width=None,
                        offset=3, shadow_color="#b9bcc2"):
    """A tk.Button with a simple offset-frame drop shadow.

    Tkinter has no native box-shadow, so this fakes one: a plain darker Frame
    sits a few pixels behind the button (via place()), peeking out on the
    bottom-right edge.

    Returns (container, button): grid/pack the container, not the button.
    """
    container = tk.Frame(parent, bg=parent.cget("bg"))

    btn = tk.Button(
        container, text=text, command=command,
        bg=bg, fg=fg, activebackground=active_bg, activeforeground=fg,
        relief="flat", width=width,
    )
    btn.update_idletasks()
    w = btn.winfo_reqwidth()
    h = btn.winfo_reqheight()
    container.config(width=w + offset, height=h + offset)

    shadow = tk.Frame(container, bg=shadow_color, width=w, height=h)
    shadow.place(x=offset, y=offset)
    btn.place(x=0, y=0, width=w, height=h)
    btn.lift()  # btn was created before shadow, so it stacks *below* it by default; force it back on top

    return container, btn
