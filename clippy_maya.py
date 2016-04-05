#!/usr/bin/python
import random

from maya import OpenMaya, cmds
from PyQt4 import QtCore, QtGui

# import clippy_api as api
import clippy_window as window


def get_maya_window():
    """
    Gets the Maya main window as a PyQt object.
    """
    import sip
    import maya.OpenMayaUI as apiUI
    ptr = apiUI.MQtUtil.mainWindow()
    if ptr is None:
        return None
    return sip.wrapinstance(long(ptr), QtCore.QObject)

def maya_to_qt(maya_name):
    """
    Converts a Maya UI element by name to a PyQt object.
    """
    import sip
    import maya.OpenMayaUI as apiUI
    ptr = apiUI.MQtUtil.findControl(maya_name)
    if ptr is None:
        ptr = apiUI.MQtUtil.findLayout(maya_name)
    if ptr is None:
        ptr = apiUI.MQtUtil.findMenuItem(maya_name)
    if ptr is None:
        return None
    return sip.wrapinstance(long(ptr), QtCore.QObject)

def get_maya_viewports():
    import pymel.core.windows as win
    model_panels = win.getPanel(type='modelPanel')
    viewports = list()
    for panel in model_panels:
        try:
            panel_qt = maya_to_qt(panel.getControl())
            # hack to get the actual viewport widget item
            viewport = panel_qt.layout().itemAt(0).widget().layout().itemAt(1).widget()
            geo = viewport.geometry()
            tl = viewport.parent().mapToGlobal(geo.topLeft())
            br = viewport.parent().mapToGlobal(geo.bottomRight())
            global_geo = QtCore.QRect(tl, br)
            viewports.append((global_geo, panel_qt.isVisible()))
        except (AttributeError, TypeError, ValueError, RuntimeError):
            pass
    return viewports

class ClippyForMaya(window.ClippyWindow):
    """
    The main clippy window locked to the Maya window.
    """
    APPLICATION = 'Maya'

    def __init__(self, *args, **kwargs):
        self.viewport_boxes = list()
        kwargs['parent_window'] = get_maya_window()
        window.ClippyWindow.__init__(self, *args, **kwargs)

    def update_geometry(self, *args, **kwargs):
        """
        Updates the geometry of the clippy window to be
        the correct size and position.
        """
        window.ClippyWindow.update_geometry(self, *args, **kwargs)
        viewports = get_maya_viewports()
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(161, 161, 161))
        while len(self.viewport_boxes) < len(viewports):
            box = QtGui.QWidget(self.viewport_fix)
            box.setAutoFillBackground(True)
            box.setBackgroundRole(QtGui.QPalette.Window)
            box.setPalette(palette)
            self.viewport_boxes.append(box)
        while len(self.viewport_boxes) > len(viewports):
            self.viewport_boxes.pop(0).deleteLater()
        for box, viewport in zip(self.viewport_boxes, viewports):
            global_geo, visible = viewport
            tl = self.mapFromGlobal(global_geo.topLeft())
            br = self.mapFromGlobal(global_geo.bottomRight())
            local_geo = QtCore.QRect(tl, br)
            box.setVisible(visible)
            box.setGeometry(local_geo)
        self.viewport_fix.lower()
        self.background.lower()

    def _init_app_event_triggers(self):
        """
        Initialize Maya specific event triggers.
        """
        save_id = OpenMaya.MSceneMessage\
            .addCallback(OpenMaya.MSceneMessage.kAfterSave,
                         self.scene_save_event,
                         'scene_save')
        self.app_callbacks.append((OpenMaya.MSceneMessage, save_id))
        open_id = OpenMaya.MSceneMessage\
            .addCallback(OpenMaya.MSceneMessage.kAfterOpen,
                         self.scene_fire_event,
                         'scene_open')
        self.app_callbacks.append((OpenMaya.MSceneMessage, open_id))
        rename_id = OpenMaya.MNodeMessage\
           .addNameChangedCallback(OpenMaya.MObject(),
                                   self.node_fire_event,
                                   'node_name_changed')
        self.app_callbacks.append((OpenMaya.MNodeMessage, rename_id))
        delete_id = OpenMaya.MDGMessage\
            .addNodeRemovedCallback(self.node_delete_event)
        self.app_callbacks.append((OpenMaya.MNodeMessage, delete_id))
        # Adds the attribute changed callback to all newly created nodes
        add_child_id = OpenMaya.MDagMessage\
            .addChildAddedCallback(self.node_child_added_fire_event, None)
        self.app_callbacks.append((OpenMaya.MDagMessage, add_child_id))
        # Add the attribute changed callback to all existing nodes
        selection_list = OpenMaya.MSelectionList()
        selection_list.add('*', True)
        node = OpenMaya.MObject()
        for i in xrange(selection_list.length()):
            selection_list.getDependNode(i, node)
            if not node.hasFn(OpenMaya.MFn.kTransform):
                continue
            attr_changed_id = OpenMaya.MNodeMessage\
                .addAttributeChangedCallback(node,
                                             self.node_attr_fire_event,
                                             None)
            self.app_callbacks.append((OpenMaya.MNodeMessage, attr_changed_id))

    def node_child_added_fire_event(self, parent_mdagpath, child_mdagpath,
                                    client_data):
        if not child_mdagpath.hasFn(OpenMaya.MFn.kTransform):
            return
        child_node = child_mdagpath.node()
        attr_changed_id = OpenMaya.MNodeMessage\
            .addAttributeChangedCallback(child_node,
                                         self.node_attr_fire_event,
                                         None)
        self.app_callbacks.append((OpenMaya.MNodeMessage, attr_changed_id))

    def dag_fire_event(self, op_type, dag_path_parent, dag_path_child,
                       event_name):
        parent_name = dag_path_parent.partialPathName()
        child_name = dag_path_parent.partialPathName()
        self.fire_event(event_name, force=True, parent_name=parent_name,
                        child_name=child_name)

    def _remove_app_event_triggers(self):
        """
        Remove Maya specific event triggers.
        """
        for message_class, callback_id in self.app_callbacks:
            message_class.removeCallback(callback_id)
        self.app_callbacks = list()

    def node_delete_event(self, mobject, client_data):
        node_name = OpenMaya.MFnDependencyNode(mobject).name()
        self.fire_event('node_deleted', node_name=node_name)

    def node_attr_fire_event(self, attr_msg, changed_mplug,
                             connected_mplug, client_data):
        if attr_msg & OpenMaya.MNodeMessage.kAttributeSet:
            node_name, _, attr_name = changed_mplug.name().partition('.')
            attr_value = cmds.getAttr(changed_mplug.name())
            event_name = None
            try:
                while isinstance(attr_value, (tuple, list)):
                    attr_value = max(attr_value)
                attr_int = int(attr_value)
            except (TypeError, ValueError):
                attr_int = 0
            if attr_int > 9000 and random.randint(0, 2) == 0:
                event_name = 'over_9000'
            elif 'translate' in attr_name:
                event_name = 'node_moved'
            elif 'rotate' in attr_name:
                event_name = 'node_rotated'
            elif 'scale' in attr_name:
                event_name = 'node_scaled'
            if event_name:
                self.fire_event(event_name, node_name=node_name,
                                attr_name=attr_name)

    def node_fire_event(self, mobject, prev_name, event_name):
        node_name = OpenMaya.MFnDependencyNode(mobject).name()
        if not prev_name or node_name == prev_name:
            return
        ignore = ('manipulator',)
        if any(node_name.lower().startswith(i) for i in ignore):
            return
        self.fire_event(event_name, node_name=node_name, prev_name=prev_name)

    def scene_save_event(self, *args):
        QtCore.QTimer.singleShot(50, self.print_fake_save)
        self.fire_event('scene_save', force=True)

    def print_fake_save(self, *args):
        try:
            from path_lib import PathContext
        except ImportError:
            return
        ctx = PathContext(proj_name='12345_CLIPPERS', seq_name='CLP',
                          shot_name='clippy', disc='clipping',
                          wip_name='clipped')
        fake_path = ctx.get_path('sh_wip_dir') + '/clippy_rules.ma'
        cmds.warning('// Result: ' + fake_path + ' //')
