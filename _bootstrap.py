import bpy

_ns = {}

def _deferred_load():
    try:
        exec(open(r'F:\home\exploded-hexagon-home\_startup_safe.py').read(), _ns)
    except Exception as e:
        print(f'[Bootstrap] Error: {e}')
    return None

bpy.app.timers.register(_deferred_load, first_interval=3.0)