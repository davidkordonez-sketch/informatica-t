"""Log de reenvíos en formato JSON Lines (FR-10, A-16, R10).

Único lugar del Router que toca el sistema de archivos.
Garantías:
1. Serializa el registro en memoria ANTES de tocar el archivo.
2. Una sola escritura por registro, bajo un lock (dos paquetes simultáneos -> dos líneas completas).
3. flush() + os.fsync(): solo después de esto el registro cuenta como persistido.
4. Si el archivo quedó con un fragmento sin salto de línea, la siguiente escritura lo aísla.
5. find_all() omite las líneas que no son JSON válido y cuenta cuántas omitió.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List

from router.dao.forwarding_log_dao import ForwardingLogDAO
from router.exceptions import PersistenceError
from router.models import ForwardingResult

logger = logging.getLogger("router")


class JsonLinesForwardingLogDAO(ForwardingLogDAO):
    def __init__(self, file_path: str, opener: Callable[..., Any] = open) -> None:
        self._file_path = Path(file_path)
        self._write_lock = threading.Lock()
        self._opener = opener  # inyectable para simular escrituras parciales (TC-26)
        self.last_skipped_lines = 0

    def save(self, result: ForwardingResult) -> None:
        try:
            line = (json.dumps(result.to_log_record(), ensure_ascii=False) + "\n").encode("utf-8")
        except (TypeError, ValueError) as error:  # nada se escribió
            raise PersistenceError("Forwarding result could not be serialized") from error

        with self._write_lock:
            try:
                self._file_path.parent.mkdir(parents=True, exist_ok=True)
                prefix = b"\n" if self._ends_without_newline() else b""
                with self._opener(self._file_path, "ab") as handle:
                    handle.write(prefix + line)  # una sola escritura
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception as error:  # incluye escrituras parciales y fallos de fsync
                raise PersistenceError(
                    "Forwarding log could not be persisted", {"reason": type(error).__name__}
                ) from error

    def find_all(self) -> List[Dict[str, Any]]:
        if not self._file_path.exists():
            self.last_skipped_lines = 0
            return []
        try:
            raw = self._file_path.read_bytes()
        except OSError as error:
            raise PersistenceError("Forwarding log could not be read") from error
        records: List[Dict[str, Any]] = []
        skipped = 0
        for raw_line in raw.split(b"\n"):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                skipped += 1
                continue
            if isinstance(record, dict):
                records.append(record)
            else:
                skipped += 1
        if skipped:
            logger.warning("Skipped %d corrupted line(s) in %s", skipped, self._file_path)
        self.last_skipped_lines = skipped
        return records

    def _ends_without_newline(self) -> bool:
        if not self._file_path.exists() or self._file_path.stat().st_size == 0:
            return False
        with open(self._file_path, "rb") as handle:
            handle.seek(-1, os.SEEK_END)
            return handle.read(1) != b"\n"
