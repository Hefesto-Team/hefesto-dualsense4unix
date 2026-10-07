"""O download do Proton pinado vai pelo HTTP da stdlib, e retoma de onde parou.

A-STEAM-E-OS-LANCADORES-SEM-ARQUIVO-INTERNO-01, 07/10/2026. O `curl` da máquina era uma porta que o
produto não prometeu a ninguém: o PATH de um computador sem ele derrubava o `--ensure`. Aqui o
servidor é um `http.server` em 127.0.0.1, em thread, que entende (ou ignora) o `Range`.
"""
from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import proton_pin as pp

CORPO = bytes(range(256)) * 4096  # 1 MiB


def _servidor(honra_range: bool, pedidos: list[str | None]) -> http.server.ThreadingHTTPServer:
    class _H(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            faixa = self.headers.get("Range")
            pedidos.append(faixa)
            if faixa and honra_range:
                ini = int(faixa.split("=")[1].rstrip("-"))
                if ini >= len(CORPO):
                    self.send_response(416)
                    self.end_headers()
                    return
                self.send_response(206)
                dados = CORPO[ini:]
            elif self.path == "/some":
                self.send_response(404)
                self.end_headers()
                return
            else:
                self.send_response(200)
                dados = CORPO
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def log_message(self, *_a: object) -> None:
            return

    return http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)


@pytest.fixture()
def servidor() -> Iterator[tuple[str, list[str | None]]]:
    pedidos: list[str | None] = []
    srv = _servidor(True, pedidos)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", pedidos
    srv.shutdown()
    srv.server_close()


@pytest.fixture()
def servidor_sem_range() -> Iterator[tuple[str, list[str | None]]]:
    pedidos: list[str | None] = []
    srv = _servidor(False, pedidos)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", pedidos
    srv.shutdown()
    srv.server_close()


def test_baixa_o_arquivo_inteiro(tmp_path: Path, servidor: tuple[str, list[str | None]]) -> None:
    url, pedidos = servidor
    destino = tmp_path / "x.tar.gz.hefesto-download"

    pp.baixar_a_release(f"{url}/ok", destino)

    assert destino.read_bytes() == CORPO
    assert pedidos == [None]


def test_retoma_do_byte_em_que_parou(
    tmp_path: Path, servidor: tuple[str, list[str | None]]
) -> None:
    url, pedidos = servidor
    destino = tmp_path / "x.part"
    destino.write_bytes(CORPO[:1000])

    pp.baixar_a_release(f"{url}/ok", destino)

    assert destino.read_bytes() == CORPO
    assert pedidos == ["bytes=1000-"]


def test_servidor_que_ignora_o_range_recomeca_do_zero(
    tmp_path: Path, servidor_sem_range: tuple[str, list[str | None]]
) -> None:
    url, _ = servidor_sem_range
    destino = tmp_path / "x.part"
    destino.write_bytes(b"lixo-parcial")

    pp.baixar_a_release(f"{url}/ok", destino)

    assert destino.read_bytes() == CORPO


def test_http_de_erro_vira_oserror_com_o_codigo(
    tmp_path: Path, servidor: tuple[str, list[str | None]]
) -> None:
    url, _ = servidor

    with pytest.raises(OSError, match="HTTP 404"):
        pp.baixar_a_release(f"{url}/some", tmp_path / "x.part")


def test_servidor_fora_do_ar_vira_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError, match="download falhou"):
        pp.baixar_a_release("http://127.0.0.1:1/x", tmp_path / "x.part")


def test_o_modulo_nao_chama_mais_o_curl() -> None:
    """O processo `curl` não é mais uma porta do produto. MORDIDA: volte o `["curl", ...]`."""
    fonte = Path(pp.__file__).read_text(encoding="utf-8")

    assert '"curl"' not in fonte
