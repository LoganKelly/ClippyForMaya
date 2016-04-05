#!/usr/bin/python

import hou
from PyQt4 import QtGui, QtCore
# import clippy_api as api
import clippy_window as window

class ClippyForHoudini(window.ClippyWindow):
    """
    The main clippy window locked to the Maya window.
    """
    CHECK_IDLE = False
    WINDOW_SCREEN_GRAB = False
    APPLICATION = 'Houdini'
    
    def __init__(self, *args, **kwargs):
        parent_window = None
        application = QtGui.QApplication.instance()
        for w in application.topLevelWidgets():
            if 'Houdini' in w.windowTitle():
                parent_window = w
                break
        if parent_window is None:
            raise Exception('No Houdini window found.')
        window.ClippyWindow.__init__(self, parent_window, *args, **kwargs)

    def _init_app_event_triggers(self):
        """
        Initialize Maya specific event triggers.
        """

    def _remove_app_event_triggers(self):
        """
        Remove Maya specific event triggers.
        """
