import functools
import os

from qtpy import API_NAME
from qtpy.QtCore import QEvent, Qt, QTimer
from qtpy.QtGui import QOpenGLWindow, QSurfaceFormat, QWindow, QKeySequence
from qtpy.QtWidgets import QFileDialog

from .base import BaseViewer
from .base import Buttons, Modifiers

from ..constants import OPEN_GL_MAJOR, OPEN_GL_MINOR
from ..utils import convert_to

MAP_BUTTONS = {
    Qt.NoButton: Buttons.NoButton,
    Qt.LeftButton: Buttons.LeftButton,
    Qt.RightButton: Buttons.RightButton,
    Qt.MiddleButton: Buttons.MiddleButton,
}
MAP_Modifiers = {
    Qt.NoModifier: Modifiers.NoModifier,
    Qt.ShiftModifier: Modifiers.ShiftModifier,
    Qt.ControlModifier: Modifiers.ControlModifier,
    Qt.AltModifier: Modifiers.AltModifier,
}


# https://github.com/matplotlib/matplotlib/blob/master/lib/matplotlib/backends/backend_qt5.py#L138
def _allow_super_init(__init__):
    """
    Decorator for ``__init__`` to allow ``super().__init__`` on PyQt4/PySide2.
    """

    if API_NAME == "PyQt5":

        return __init__

    else:
        # To work around lack of cooperative inheritance in PyQt4, PySide,
        # and PySide2, when calling FigureCanvasQT.__init__, we temporarily
        # patch QWidget.__init__ by a cooperative version, that first calls
        # QWidget.__init__ with no additional arguments, and then finds the
        # next class in the MRO with an __init__ that does support cooperative
        # inheritance (i.e., not defined by the PyQt4, PySide, PySide2, sip
        # or Shiboken packages), and manually call its `__init__`, once again
        # passing the additional arguments.

        qwidget_init = QOpenGLWindow.__init__

        def cooperative_qwidget_init(self, *args, **kwargs):
            qwidget_init(self)
            mro = type(self).__mro__
            next_coop_init = next(
                cls for cls in mro[mro.index(QOpenGLWindow) + 1:]
                if cls.__module__.split(".")[0] not in
                ["PyQt4", "sip", "PySide", "PySide2", "Shiboken"])
            next_coop_init.__init__(self, *args, **kwargs)

        @functools.wraps(__init__)
        def wrapper(self, *args, **kwargs):
            setattr(QOpenGLWindow, "__init__", cooperative_qwidget_init)
            __init__(self, *args, **kwargs)

        return wrapper


class Viewer(QOpenGLWindow, BaseViewer):
    @_allow_super_init
    def __init__(
        self,
        scene=None,
        viewport_size=None,
        render_flags=None,
        viewer_flags=None,
        registered_keys=None,
        parent=None,
        **kwargs,
    ):

        super(Viewer, self).__init__(
            scene=scene,
            viewport_size=viewport_size,
            render_flags=render_flags,
            viewer_flags=viewer_flags,
            registered_keys=registered_keys,
            parent=parent,
            **kwargs,
        )
        fmt = QSurfaceFormat()
        fmt.setMajorVersion(OPEN_GL_MAJOR)
        fmt.setMinorVersion(OPEN_GL_MINOR)
        fmt.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
        fmt.setDepthBufferSize(24)
        fmt.setSamples(4)
        fmt.setRenderableType(QSurfaceFormat.OpenGL)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        self.setFormat(fmt)

        self.setSurfaceType(QWindow.OpenGLSurface)
        self.setTitle(self.viewer_flags["window_title"])
        self.resize(*self.viewport_size)

        timer = QTimer(
            self,
            interval=1000 / self.viewer_flags["refresh_rate"],
            timeout=self.on_timeout,
        )
        timer.start()

    def paintGL(self):
        self.makeCurrent()
        self.draw()

    def resizeGL(self, width, height):
        self.handle_resize(width, height)

    def on_timeout(self):
        self.handle_timeout()
        self.update()

    def mousePressEvent(self, event):
        buttons = convert_to(event.buttons(), MAP_BUTTONS, Buttons.NoButton)
        modifiers = convert_to(event.modifiers(), MAP_Modifiers,
                               Modifiers.NoModifier)
        self.handle_mouse_press(buttons, modifiers, event.x(), event.y())
        self.update()

    def mouseMoveEvent(self, event):
        buttons = convert_to(event.buttons(), MAP_BUTTONS, Buttons.NoButton)
        modifiers = convert_to(event.modifiers(), MAP_Modifiers,
                               Modifiers.NoModifier)
        self.handle_mouse_drag(buttons, modifiers, event.x(), event.y())
        self.update()

    def mouseReleaseEvent(self, event):
        buttons = convert_to(event.buttons(), MAP_BUTTONS, Buttons.NoButton)
        modifiers = convert_to(event.modifiers(), MAP_Modifiers,
                               Modifiers.NoModifier)
        self.handle_mouse_release(buttons, modifiers, event.x(), event.y())
        self.update()

    def wheelEvent(self, event):
        dp = event.angleDelta() / 120
        self.handle_mouse_scroll(event.position().x(),
                                 event.position().y(), dp.x(), dp.y())

    def keyPressEvent(self, event):
        self.handle_key_press(
            QKeySequence(event.key()).toString(), event.key())

    def get_save_filename(self, file_exts):
        file_types = {
            "png": ("png files", "*.png"),
            "jpg": ("jpeg files", "*.jpg"),
            "gif": ("gif files", "*.gif"),
            "all": ("all files", "*"),
        }
        filters = []
        for ext in file_exts:
            name, extension = file_types[ext]
            filters.append("{} ({})".format(name, extension))

        save_dir = self.viewer_flags["save_directory"]
        if save_dir is None:
            save_dir = os.getcwd()
        filename, _ = QFileDialog.getSaveFileName(None,
                                                  "Select file save location",
                                                  save_dir, ";;".join(filters))
        if filename:
            return filename

    def set_full_screen(self, fullscreen):
        if self.viewer_flags["fullscreen"]:
            self.showFullScreen()
        else:
            self.showNormal()
        self.requestActivate()

    def handle_close(self):
        self.close()

    def set_title(self, title):
        self.setTitle(title)

    def event(self, e):
        if e.type() == QEvent.Close:
            try:
                self.free_resource()
            except Exception:
                pass
        return super().event(e)


__all__ = ["Viewer"]
