"""
Servidor WebSocket local que a ponte IPC usa (ver seção "Arquitetura —
decisão central: ponte IPC" no plano de migração). Um processo Python só,
spawnado pelo Rust; o frontend conecta direto via WebSocket do browser.
Envelope de mensagem: request/response correlacionados por id + eventos
broadcast pra todas as conexões — mesma forma descrita no plano.
"""
import asyncio
import dataclasses
import json
import os
import threading

import websockets

from core.languages import LANGS
from core.voices import voice_options_for, normalize_lang_code

from service import device_catalog, com_thread, log_stream
from service.app_state import AppState

IPC_PORT = 47823


class RpcError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class IpcServer:
    def __init__(self):
        self.clients: set = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.state: AppState | None = None
        self.shutdown_event: asyncio.Event | None = None

    def initiate_shutdown(self) -> None:
        """Chamado tanto pelo RPC app.shutdown quanto pelo watcher de stdin
        em run_service.py (Rust fecha o stdin do processo filho ao receber
        CloseRequested na janela principal — ver run_service.py)."""
        if self.state is not None:
            self.state.shutdown()
        if self.shutdown_event is not None:
            self.shutdown_event.set()

    def broadcast(self, event: str, payload) -> None:
        if self.loop is None:
            return
        message = json.dumps({"type": "event", "event": event, "payload": payload}, ensure_ascii=False)
        self.loop.call_soon_threadsafe(self._dispatch_broadcast, message)

    def _dispatch_broadcast(self, message: str) -> None:
        for ws in list(self.clients):
            asyncio.ensure_future(self._safe_send(ws, message))

    @staticmethod
    async def _safe_send(ws, message: str) -> None:
        try:
            await ws.send(message)
        except Exception:
            pass

    async def handle_connection(self, websocket) -> None:
        self.clients.add(websocket)
        try:
            async for raw in websocket:
                await self._handle_message(websocket, raw)
        finally:
            self.clients.discard(websocket)

    async def _handle_message(self, websocket, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except Exception:
            return
        if msg.get("type") != "request":
            return
        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        handler = DISPATCH.get(method)
        try:
            if handler is None:
                raise RpcError("unknown_method", f"Método desconhecido: {method}")
            result = await handler(self.state, params)
            response = {"id": req_id, "type": "response", "ok": True, "result": result}
        except RpcError as e:
            response = {"id": req_id, "type": "response", "ok": False, "error": {"code": e.code, "message": e.message}}
        except Exception as e:  # noqa: BLE001 — nunca deixa uma exceção derrubar a conexão
            response = {"id": req_id, "type": "response", "ok": False, "error": {"code": "internal_error", "message": str(e)}}
        await websocket.send(json.dumps(response, ensure_ascii=False))


server = IpcServer()


# ── handlers ─────────────────────────────────────────────────────────────

async def h_hello(state: AppState, params):
    return {}


async def h_shutdown(state: AppState, params):
    server.initiate_shutdown()
    return {}


async def h_settings_get(state: AppState, params):
    return state.settings


async def h_settings_set(state: AppState, params):
    return state.apply_settings_patch(params or {})


async def h_devices_list_audio_io(state: AppState, params):
    inputs, outputs = device_catalog.list_audio_io_devices()
    return {"inputs": inputs, "outputs": outputs}


async def h_devices_list_loopback(state: AppState, params):
    return device_catalog.list_loopback_devices_public()


async def h_devices_list_session_apps(state: AppState, params):
    apps = await com_thread.list_session_apps_async(asyncio.get_running_loop())
    return [
        {"pid": a.pid, "executable": a.executable, "display_name": a.display_name, "is_active": a.is_active}
        for a in apps
    ]


def _find_device_index(devices, name):
    if not name:
        return None
    for d in devices:
        if d["name"] == name:
            return d["index"]
    for d in devices:
        if device_catalog.same_device_name(d["name"], name):
            return d["index"]
    return None


async def h_mic_start(state: AppState, params):
    inputs, outputs = device_catalog.list_audio_io_devices()
    mic_index = _find_device_index(inputs, state.settings.get("mic"))
    out_index = _find_device_index(outputs, state.settings.get("out"))
    if mic_index is None or out_index is None:
        raise RpcError("invalid_device", "Erro: selecione microfone e saída!")
    state.mic_service.start(mic_index, out_index)
    return {}


async def h_mic_stop(state: AppState, params):
    state.mic_service.stop()
    return {}


async def h_mic_set_pitch(state: AppState, params):
    state.set_pitch(int(params.get("pitch", 0)))
    return {}


async def h_received_start(state: AppState, params):
    ok = state.received_controller.start(
        params.get("sourceMode"), params.get("deviceName"), params.get("targetExecutable"),
        params.get("candidateLangs") or [], params.get("targetLanguage"),
    )
    if not ok:
        raise RpcError("start_failed", "Não foi possível iniciar a escuta.")
    return {}


async def h_received_stop(state: AppState, params):
    state.received_controller.stop()
    return {}


async def h_received_test(state: AppState, params):
    duration = float(params.get("duration", 4.0))
    try:
        state.received_controller.run_test(
            state.settings.get("received_device"), state.settings.get("received_langs") or [], duration,
        )
    except (ValueError, RuntimeError) as e:
        raise RpcError("test_failed", str(e))
    return {}


async def h_osc_clear_chatbox(state: AppState, params):
    try:
        state.clear_chatbox()
    except Exception as e:
        raise RpcError("osc_error", str(e))
    return {}


async def h_history_list(state: AppState, params):
    return [dataclasses.asdict(e) for e in state.history_store.list_entries()]


async def h_history_clear(state: AppState, params):
    state.history_store.clear()
    return {}


async def h_history_search(state: AppState, params):
    entries = state.history_store.search(params.get("query", ""), params.get("filterKey", "all"))
    return [dataclasses.asdict(e) for e in entries]


# Tkinter nao e thread-safe pra varias instancias tk.Tk() vivas ao mesmo
# tempo em threads diferentes do processo (mesma classe de risco que
# motivou o PYAUDIO_LOCK global deste projeto). Cada handler abaixo roda
# num worker do executor padrao (varias threads); sem essa trava, abrir 2
# dialogos nativos em sequencia rapida (ex.: "Exportar conversa" e depois
# "Exportar tema" antes do primeiro fechar) pode travar/derrubar o processo
# nativamente. So serializa o USO do dialogo, nao bloqueia o event loop
# (quem espera e o worker thread do executor, nao a thread principal).
_TK_DIALOG_LOCK = threading.Lock()


def _ask_save_path(default_name: str, filetypes) -> str:
    import tkinter as tk
    from tkinter import filedialog

    with _TK_DIALOG_LOCK:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        ext = os.path.splitext(default_name)[1] or ".txt"
        path = filedialog.asksaveasfilename(
            defaultextension=ext, filetypes=filetypes, initialfile=default_name,
        )
        root.destroy()
        return path


def _ask_open_path(filetypes) -> str:
    import tkinter as tk
    from tkinter import filedialog

    with _TK_DIALOG_LOCK:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(filetypes=filetypes)
        root.destroy()
        return path


async def h_history_export_txt(state: AppState, params):
    # diálogo nativo roda numa thread do executor — nunca bloqueia o loop
    # (senão travaria até o level meter a 10Hz enquanto o diálogo tá aberto).
    path = await asyncio.get_running_loop().run_in_executor(
        None, _ask_save_path, "conversa.txt", [("Texto", "*.txt")],
    )
    if not path:
        return {"saved": False}
    state.history_store.export_txt(path)
    return {"saved": True, "path": path}


# Genéricos (pedido do usuário: importar/exportar temas de shader como
# arquivo transferível entre instalações) — não são específicos de shader de
# propósito, o front manda o conteúdo já serializado (JSON) e só usa o
# diálogo nativo de arquivo daqui; reaproveitável por qualquer outra feature
# de import/export de arquivo texto que aparecer depois.
async def h_system_save_text_file(state: AppState, params):
    content = params.get("content", "")
    default_name = params.get("defaultName", "arquivo.json")
    path = await asyncio.get_running_loop().run_in_executor(
        None, _ask_save_path, default_name, [("JSON", "*.json"), ("Todos os arquivos", "*.*")],
    )
    if not path:
        return {"saved": False}
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"saved": True, "path": path}


async def h_system_open_text_file(state: AppState, params):
    path = await asyncio.get_running_loop().run_in_executor(
        None, _ask_open_path, [("JSON", "*.json"), ("Todos os arquivos", "*.*")],
    )
    if not path:
        return {"opened": False, "content": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        raise RpcError("read_failed", str(e))
    return {"opened": True, "content": content, "path": path}


async def h_history_replay(state: AppState, params):
    try:
        state.replay_entry(int(params.get("index", -1)))
    except (IndexError, ValueError) as e:
        raise RpcError("invalid_index", str(e))
    return {}


async def h_log_get_buffer(state: AppState, params):
    return log_stream.get_buffer()


async def h_catalog_languages(state: AppState, params):
    return dict(LANGS)




async def h_catalog_voices_for_language(state: AppState, params):
    lang = params.get("lang", "en")
    normalized = normalize_lang_code(lang)
    voices = voice_options_for(lang)
    return {
        "normalizedLang": normalized,
        "voices": [{"id": v.id, "engine": v.engine, "gender": v.gender, "style": v.style} for v in voices],
    }


DISPATCH = {
    "app.hello": h_hello,
    "app.shutdown": h_shutdown,
    "settings.get": h_settings_get,
    "settings.set": h_settings_set,
    "devices.listAudioIO": h_devices_list_audio_io,
    "devices.listLoopback": h_devices_list_loopback,
    "devices.listSessionApps": h_devices_list_session_apps,
    "mic.start": h_mic_start,
    "mic.stop": h_mic_stop,
    "mic.setPitch": h_mic_set_pitch,
    "received.start": h_received_start,
    "received.stop": h_received_stop,
    "received.test": h_received_test,
    "osc.clearChatbox": h_osc_clear_chatbox,
    "history.list": h_history_list,
    "history.clear": h_history_clear,
    "history.search": h_history_search,
    "history.exportTxt": h_history_export_txt,
    "history.replay": h_history_replay,
    "log.getBuffer": h_log_get_buffer,
    "system.saveTextFile": h_system_save_text_file,
    "system.openTextFile": h_system_open_text_file,
    "catalog.languages": h_catalog_languages,
    "catalog.voicesForLanguage": h_catalog_voices_for_language,
}


async def run(port: int = IPC_PORT):
    server.loop = asyncio.get_running_loop()
    log_stream.set_broadcast(server.broadcast)
    server.state = AppState(server.broadcast, server.loop)
    server.shutdown_event = asyncio.Event()
    async with websockets.serve(server.handle_connection, "127.0.0.1", port):
        print(f"[ipc_server] escutando em ws://127.0.0.1:{port}", flush=True)
        # devolve o controle assim que app.shutdown ou o watcher de stdin
        # (run_service.py) chamarem server.initiate_shutdown() — o `async with`
        # acima fecha o servidor de forma limpa ao sair deste bloco.
        await server.shutdown_event.wait()
