import bpy, socket, sys, io, traceback

_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
_srv.bind(('127.0.0.1', 9876))
_srv.listen(1)
_srv.setblocking(False)

def _handle(conn):
    conn.settimeout(5.0)
    data = b''
    while True:
        try:
            chunk = conn.recv(65536)
        except socket.timeout:
            break
        if not chunk:
            break
        data += chunk
    code = data.decode('utf-8', errors='replace').strip()
    if not code:
        conn.sendall(b'(empty)\n')
        return
    old_out = sys.stdout
    sys.stdout = buf = io.StringIO()
    res = err = None
    try:
        try:
            res = eval(code)
        except SyntaxError:
            exec(compile(code, '<r>', 'exec'))
    except Exception:
        err = traceback.format_exc()
    finally:
        sys.stdout = old_out
    out = buf.getvalue()
    if err:
        resp = 'ERROR:\n' + err
    elif out:
        resp = out.rstrip('\n')
    elif res is not None:
        resp = str(res)
    else:
        resp = 'OK'
    conn.sendall((resp + '\n').encode('utf-8'))

def _poll():
    try:
        conn, _ = _srv.accept()
    except BlockingIOError:
        return 0.5
    except Exception:
        return 0.5
    try:
        _handle(conn)
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return 0.5

bpy.app.timers.register(_poll, first_interval=1.0)
print('[Remote] Server ready on 9876')