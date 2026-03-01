"""
Blender Remote Console Server.

Run this ONCE in Blender's Python console to start a TCP listener:
    exec(open(r"F:\home\exploded-hexagon-home\src\blender_remote.py").read())

Then from PowerShell, send commands via:
    $tcp = New-Object Net.Sockets.TcpClient("127.0.0.1", 9876)
    $s = $tcp.GetStream(); $w = New-Object IO.StreamWriter($s); $r = New-Object IO.StreamReader($s)
    $w.WriteLine("bpy.context.scene.render.engine"); $w.Flush(); $r.ReadLine()

The server runs on a bpy.app.timers callback so it never blocks
Blender's UI. Each connection sends one Python expression/statement,
gets back the result or error, then disconnects.
"""

import bpy
import socket
import traceback
import io
import sys

_PORT = 9876
_server = None


def _start_server():
    global _server
    if _server is not None:
        try:
            _server.close()
        except Exception:
            pass
    _server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _server.bind(("127.0.0.1", _PORT))
    _server.listen(1)
    _server.setblocking(False)
    print(f"[Remote] Listening on 127.0.0.1:{_PORT}")


def _poll():
    """Called by bpy.app.timers every 0.5s to check for connections."""
    global _server
    if _server is None:
        return None  # stop timer
    try:
        conn, addr = _server.accept()
    except BlockingIOError:
        return 0.5  # no connection yet, check again in 0.5s
    except Exception:
        return 0.5

    try:
        conn.settimeout(5.0)
        data = b""
        while True:
            try:
                chunk = conn.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            data += chunk
        code = data.decode("utf-8", errors="replace").strip()
        if not code:
            conn.sendall(b"(empty)\n")
            conn.close()
            return 0.5

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = capture = io.StringIO()
        result = None
        error = None
        try:
            # Try eval first (expression), fall back to exec (statement)
            try:
                result = eval(code)
            except SyntaxError:
                exec(compile(code, '<remote>', 'exec'))
                result = None
        except Exception:
            error = traceback.format_exc()
        finally:
            sys.stdout = old_stdout

        output = capture.getvalue()
        if error:
            response = f"ERROR:\n{error}"
        elif output:
            response = output.rstrip("\n")
            if result is not None:
                response += f"\n>>> {result}"
        elif result is not None:
            response = str(result)
        else:
            response = "OK"

        conn.sendall((response + "\n").encode("utf-8"))
    except Exception as e:
        try:
            conn.sendall(f"SERVER ERROR: {e}\n".encode("utf-8"))
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return 0.5  # keep polling


# Start it up
_start_server()
if bpy.app.timers.is_registered(_poll):
    bpy.app.timers.unregister(_poll)
bpy.app.timers.register(_poll, first_interval=0.5)
print("[Remote] Server ready. Send Python commands to 127.0.0.1:9876")
