"""
Armazenamento do historico de conversa, independente de framework de UI.
A UI (ui/history_panel.py) so le e renderiza o que esta aqui.

Duas origens possiveis, sempre marcadas explicitamente pra nunca serem
confundidas:
  - "local"    -> minha propria fala (microfone)
  - "received" -> fala de outra pessoa, capturada por loopback do audio
                  que o VRChat esta reproduzindo
"""
import threading
from dataclasses import dataclass
from typing import Iterable, List, Optional

CATEGORY_TRANSLATED = "translated"
CATEGORY_SAME_LANG = "same_lang"
CATEGORY_ERROR = "error"
CATEGORY_WARNING = "warning"
CATEGORY_RECEIVED = "received"

SOURCE_LOCAL = "local"
SOURCE_RECEIVED = "received"

MY_CATEGORIES = {CATEGORY_TRANSLATED, CATEGORY_SAME_LANG}

FILTER_ALL = "all"
FILTER_MINE = "mine"
FILTER_RECEIVED = "received"
FILTER_ERRORS = "errors"

FILTER_CATEGORIES = {
    FILTER_ALL: None,
    FILTER_MINE: MY_CATEGORIES,
    FILTER_RECEIVED: {CATEGORY_RECEIVED},
    FILTER_ERRORS: {CATEGORY_ERROR, CATEGORY_WARNING},
}


@dataclass
class HistoryEntry:
    timestamp: str
    category: str
    speaker: str
    original: str
    translated: Optional[str] = None
    target_lang: Optional[str] = None
    target_lang_code: Optional[str] = None
    source: str = SOURCE_LOCAL
    source_language: Optional[str] = None
    confidence: Optional[float] = None
    sent_to_chatbox: bool = False
    tts_played: bool = False


class HistoryStore:
    """Guarda as entradas em memoria com um limite maximo (evita crescimento indefinido)."""

    def __init__(self, max_entries: int = 500):
        self.max_entries = max_entries
        self.entries: List[HistoryEntry] = []
        # add() e chamado de VARIAS threads ao mesmo tempo (loop do
        # microfone + loop de fala recebida podem falar simultaneamente) -
        # sem essa trava, o corte de "max_entries" (append + del fatiado)
        # nao e atomico e pode ficar impreciso sob concorrencia real (race
        # condition encontrada em revisao de codigo). search()/export_txt()
        # tiram uma COPIA da lista sob a trava em vez de segurar ela durante
        # toda a iteracao/I-O de disco.
        self._lock = threading.Lock()

    def add(self, entry: HistoryEntry) -> int:
        """Adiciona uma entrada. Retorna quantas entradas antigas devem ser
        descartadas tambem na UI (0 se nenhuma)."""
        with self._lock:
            self.entries.append(entry)
            overflow = len(self.entries) - self.max_entries
            if overflow > 0:
                del self.entries[:overflow]
            return max(overflow, 0)

    def clear(self):
        with self._lock:
            self.entries.clear()

    def list_entries(self) -> List[HistoryEntry]:
        """Copia segura de .entries pra quem for iterar fora desta classe
        (ver service/ipc_server.py::h_history_list) — acessar self.entries
        direto de outra thread tem a mesma race de add(), ver comentario no
        __init__."""
        with self._lock:
            return list(self.entries)

    def search(self, query: str = "", filter_key: str = FILTER_ALL) -> Iterable[HistoryEntry]:
        allowed = FILTER_CATEGORIES.get(filter_key)
        q = (query or "").strip().lower()
        with self._lock:
            snapshot = list(self.entries)
        for e in snapshot:
            if allowed is not None and e.category not in allowed:
                continue
            if q and q not in e.original.lower() and q not in (e.translated or "").lower():
                continue
            yield e

    def export_txt(self, path: str):
        with self._lock:
            snapshot = list(self.entries)
        with open(path, "w", encoding="utf-8") as f:
            for e in snapshot:
                if e.category == CATEGORY_RECEIVED:
                    lang_label = f" ({e.source_language})" if e.source_language else ""
                    f.write(f"[{e.timestamp}] RECEBIDO{lang_label}: {e.original}\n")
                    if e.translated:
                        f.write(f"TRADUÇÃO: {e.translated}\n")
                else:
                    f.write(f"[{e.timestamp}] {e.speaker}: {e.original}\n")
                    if e.category == CATEGORY_TRANSLATED and e.translated:
                        label = f"TRADUÇÃO — {e.target_lang}" if e.target_lang else "TRADUÇÃO"
                        f.write(f"{label}: {e.translated}\n")
                    elif e.category == CATEGORY_SAME_LANG:
                        f.write("(mesmo idioma, sem tradução)\n")
                    elif e.category in (CATEGORY_ERROR, CATEGORY_WARNING):
                        f.write(f"[{e.category.upper()}]\n")
                f.write("\n")
