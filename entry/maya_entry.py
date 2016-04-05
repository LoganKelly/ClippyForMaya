import sys
from maya import cmds, utils

def start_clippy_thread():
    clippy_dir = '/path/to/clippy'
    if clippy_dir not in sys.path:
        sys.path.append(clippy_dir)
    try:
        import clippy_maya
        clippy_maya.ClippyForMaya.start_clippy_timer()
    except Exception:
        pass
    
if not cmds.about(batch=True):
    utils.executeDeferred(start_clippy_thread)