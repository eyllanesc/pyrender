import os
from threading import Thread, RLock
import time

try:
    from Tkinter import Tk, tkFileDialog as filedialog
except Exception:
    try:
        from tkinter import Tk, filedialog as filedialog
    except Exception:
        pass

from .base import BaseViewer
from .base import Buttons, Modifiers
from ..constants import OPEN_GL_MAJOR, OPEN_GL_MINOR
from ..utils import convert_to

import pyglet
from pyglet import clock

pyglet.options["shadow_window"] = False

MAP_BUTTONS = {
    0: Buttons.NoButton,
    pyglet.window.mouse.LEFT: Buttons.LeftButton,
    pyglet.window.mouse.RIGHT: Buttons.RightButton,
    pyglet.window.mouse.MIDDLE: Buttons.MiddleButton,
}
MAP_Modifiers = {
    0: Modifiers.NoModifier,
    pyglet.window.key.MOD_SHIFT: Modifiers.ShiftModifier,
    pyglet.window.key.MOD_CTRL: Modifiers.ControlModifier,
    pyglet.window.key.MOD_ALT: Modifiers.AltModifier,
}


class Viewer(pyglet.window.Window, BaseViewer):
    def __init__(self,
                 scene,
                 viewport_size=None,
                 render_flags=None,
                 viewer_flags=None,
                 registered_keys=None,
                 run_in_thread=False,
                 **kwargs):
        self._render_lock = RLock()
        self.run_in_thread = run_in_thread

        if self.run_in_thread:
            self._thread = Thread(
                target=self._init_and_start_app,
                args=(
                    scene,
                    viewport_size,
                    render_flags,
                    viewer_flags,
                    registered_keys,
                    kwargs,
                ),
            )
            self._thread.start()
        else:
            self._init_and_start_app(
                scene,
                viewport_size,
                render_flags,
                viewer_flags,
                registered_keys,
                kwargs,
            )

    def _init_and_start_app(self, scene, viewport_size, render_flags,
                            viewer_flags, registered_keys, kwargs):
        from pyglet.gl import Config

        conf = Config(
            sample_buffers=1,
            samples=4,
            depth_size=24,
            double_buffer=True,
            major_version=OPEN_GL_MAJOR,
            minor_version=OPEN_GL_MINOR,
        )
        if viewport_size is None:
            viewport_size = (640, 480)
        BaseViewer.__init__(self,
                            scene,
                            viewport_size=viewport_size,
                            render_flags=render_flags,
                            viewer_flags=viewer_flags,
                            registered_keys=registered_keys,
                            **kwargs)
        pyglet.window.Window.__init__(
            self,
            config=conf,
            resizable=True,
            width=viewport_size[0],
            height=viewport_size[1],
        )
        if self.context.config.major_version < 3:
            raise ValueError("Unable to initialize an OpenGL 3+ context")
        clock.schedule_interval(Viewer._time_event,
                                1.0 / self.viewer_flags["refresh_rate"], self)
        self.switch_to()
        self.set_caption(self.viewer_flags["window_title"])
        pyglet.app.run()

    @property
    def render_lock(self):
        """:class:`threading.RLock` : If acquired, prevents the viewer from
        rendering until released.

        Run :meth:`.Viewer.render_lock.acquire` before making updates to
        the scene in a different thread, and run
        :meth:`.Viewer.render_lock.release` once you're done to let the viewer
        continue.
        """
        return self._render_lock

    @staticmethod
    def _time_event(dt, self):
        self.handle_timeout()
        self.draw()

    def on_draw(self):
        if self.run_in_thread:
            self.render_lock.acquire()
        self.draw()
        if self.run_in_thread:
            self.render_lock.release()

    def on_resize(self, width, height):
        self.handle_resize(width, height)

    def on_mouse_press(self, x, y, buttons, modifiers):
        buttons = convert_to(buttons, MAP_BUTTONS, Buttons.NoButton)
        modifiers = convert_to(modifiers, MAP_Modifiers, Modifiers.NoModifier)
        self.handle_mouse_press(buttons, modifiers, x, y)
        self.on_draw()

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        buttons = convert_to(buttons, MAP_BUTTONS, Buttons.NoButton)
        modifiers = convert_to(modifiers, MAP_Modifiers, Modifiers.NoModifier)
        self.handle_mouse_drag(buttons, modifiers, x, y)
        self.on_draw()

    def on_mouse_release(self, x, y, buttons, modifiers):
        buttons = convert_to(buttons, MAP_BUTTONS, Buttons.NoButton)
        modifiers = convert_to(modifiers, MAP_Modifiers, Modifiers.NoModifier)
        self.handle_mouse_release(buttons, modifiers, x, y)
        self.on_draw()

    def on_mouse_scroll(self, x, y, dx, dy):
        self.handle_mouse_scroll(x, y, dx, dy)

    def on_key_press(self, symbol, modifiers):
        self.handle_key_press(pyglet.window.key.symbol_string(symbol), symbol)

    def on_close(self):
        try:
            self.free_resource()
        except Exception:
            pass
        finally:
            super(Viewer, self).on_close()
            pyglet.app.exit()

    def set_full_screen(self, fullscreen):
        self.set_fullscreen(fullscreen)

    def set_title(self, title):
        self.set_caption(title)

    def get_save_filename(self, file_exts):
        file_types = {
            "png": ("png files", "*.png"),
            "jpg": ("jpeg files", "*.jpg"),
            "gif": ("gif files", "*.gif"),
            "all": ("all files", "*"),
        }
        filetypes = [file_types[x] for x in file_exts]
        try:
            root = Tk()
            save_dir = self.viewer_flags["save_directory"]
            if save_dir is None:
                save_dir = os.getcwd()
            filename = filedialog.asksaveasfilename(
                initialdir=save_dir,
                title="Select file save location",
                filetypes=filetypes,
            )
        except Exception:
            return None

        root.destroy()
        if filename == ():
            return None
        return filename

    def handle_close(self):
        self.on_close()

    def close_external(self):
        """Close the viewer from another thread.

        This function will wait for the actual close, so you immediately
        manipulate the scene afterwards.
        """
        self._should_close = True
        while self.is_active:
            time.sleep(1.0 / self.viewer_flags["refresh_rate"])


__all__ = ["Viewer"]
