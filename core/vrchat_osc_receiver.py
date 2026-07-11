"""
Servidor OSC local que ESCUTA parametros que o VRChat transmite (diferente de
core/osc.py, que so ENVIA pro chatbox). Usado hoje so pra "mute sync":
/avatar/parameters/MuteSelf e um parametro nativo do avatar, sincronizado
automaticamente pelo VRChat quando o OSC esta ativado.

Porta fixa 9001 (padrao do VRChat para dados enviados por ele) — sem OSCQuery,
que exigiria a dependencia "tinyoscquery" (nao disponivel no PyPI, so via
instalacao direta de um repositorio Git, o que tornaria a instalacao do app
fragil). A porta 9001 cobre o caso padrao, que e a grande maioria dos usuarios.
"""
import threading
from typing import Callable, Optional

from pythonosc import dispatcher as osc_dispatcher
from pythonosc import osc_server

MUTE_SELF_ADDRESS = "/avatar/parameters/MuteSelf"
DEFAULT_RECEIVE_PORT = 9001


class VRChatOSCReceiver:
    def __init__(self, port: int = DEFAULT_RECEIVE_PORT):
        self.port = port
        self.mute_state = False
        self.on_mute_changed: Optional[Callable[[bool], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        self._server: Optional[osc_server.ThreadingOSCUDPServer] = None
        self._thread: Optional[threading.Thread] = None

    def is_running(self) -> bool:
        return self._server is not None

    def start(self):
        if self._server is not None:
            return
        try:
            disp = osc_dispatcher.Dispatcher()
            disp.map(MUTE_SELF_ADDRESS, self._handle_mute_self)
            self._server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", self.port), disp)
        except OSError as e:
            self._server = None
            if self.on_error:
                try:
                    self.on_error(f"Não foi possível abrir a porta OSC {self.port} (já em uso?): {e}")
                except Exception:
                    pass
            return

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
        self._thread = None

    def _handle_mute_self(self, address, *args):
        if not args:
            return
        self.mute_state = bool(args[0])
        if self.on_mute_changed:
            try:
                self.on_mute_changed(self.mute_state)
            except Exception:
                pass
