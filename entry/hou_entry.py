import sys
import hou

def start_clippy_thread():
    clippy_dir = '/path/to/clippy'
    if clippy_dir not in sys.path:
        sys.path.append(clippy_dir)
    try:
        import clippy_hou
        clippy_hou.ClippyForHoudini.start_clippy_timer()
    except Exception:
        pass

if hou.isUIAvailable():
    start_clippy_thread()
