"""O download do Proton cortado no meio retoma de onde parou, no install e no vigia.

O-DOWNLOAD-DO-PROTON-CORTADO-RETOMA-DE-ONDE-PAROU-01 (22/11/2026). TUDO É DE MENTIRA: o servidor é
um ``http.server`` em 127.0.0.1, em thread, que anuncia o tamanho inteiro e fecha a conexão aos N
bytes no primeiro pedido, e honra o ``Range`` nos seguintes. Nenhum caso toca a Steam, o cache de
verdade nem a rede.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o baixador sem a conferência
do tamanho devolve em silêncio o arquivo curto, o sha reprova e o parcial some (reprova os casos do
baixador, do install e do vigia); o install que apaga o parcial no erro de rede reprova o caso do
install; o ``IncompleteRead`` do corpo em pedaços sem a tradução reprova o caso do corpo em pedaços.
"""
from __future__ import annotations

import hashlib
import http.server
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import proton_pin as pp

CORPO = bytes(range(256)) * 4096
CORTE = 300_000
NOME = "GE-Proton10-99"
DO_VIGIA = f"{NOME}-x86_64"


class _Servidor:
    def __init__(self, cortes: list[int | None], em_pedacos: bool = False,
                 honra_range: bool = True) -> None:
        self.pedidos: list[str | None] = []
        self.cortes = list(cortes)
        dono = self

        class _H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                faixa = self.headers.get("Range")
                dono.pedidos.append(faixa)
                ini = 0
                if faixa and honra_range:
                    ini = int(faixa.split("=")[1].rstrip("-"))
                    if ini >= len(CORPO):
                        self.send_response(416)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {ini}-{len(CORPO) - 1}/{len(CORPO)}")
                else:
                    self.send_response(200)
                dados = CORPO[ini:]
                corte = dono.cortes.pop(0) if dono.cortes else None
                if em_pedacos:
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    if corte is not None:
                        parte = dados[:corte]
                        self.wfile.write(f"{len(parte):x}\r\n".encode() + parte + b"\r\n")
                        self.wfile.flush()
                        self.close_connection = True
                        return
                    self.wfile.write(f"{len(dados):x}\r\n".encode() + dados + b"\r\n0\r\n\r\n")
                    return
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados if corte is None else dados[:corte])
                if corte is not None:
                    self.wfile.flush()
                    self.close_connection = True

            def log_message(self, *_a: object) -> None:
                return

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}/{NOME}.tar.gz"

    def fecha(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture()
def cortando() -> Iterator[_Servidor]:
    srv = _Servidor([CORTE])
    yield srv
    srv.fecha()


def _conf(url: str, sha: str | None = None) -> dict[str, str]:
    return {"name": NOME, "url": url, "sha256": sha or hashlib.sha256(CORPO).hexdigest()}


def test_o_baixador_cortado_levanta_e_guarda_o_parcial_para_o_range(
        tmp_path: Path, cortando: _Servidor) -> None:
    parcial = tmp_path / f"{NOME}.tar.gz.hefesto-download"

    with pytest.raises(OSError, match="incompleto"):
        pp.baixar_a_release(cortando.url, parcial)
    assert parcial.stat().st_size == CORTE

    pp.baixar_a_release(cortando.url, parcial)

    assert parcial.read_bytes() == CORPO
    assert cortando.pedidos == [None, f"bytes={CORTE}-"]


def test_o_corpo_em_pedacos_cortado_tambem_e_incompleto_e_retoma(tmp_path: Path) -> None:
    srv = _Servidor([CORTE], em_pedacos=True)
    parcial = tmp_path / "x.hefesto-download"
    try:
        with pytest.raises(OSError, match="incompleto"):
            pp.baixar_a_release(srv.url, parcial)
        assert parcial.stat().st_size == CORTE
        pp.baixar_a_release(srv.url, parcial)
        assert parcial.read_bytes() == CORPO
    finally:
        srv.fecha()


def test_o_servidor_que_ignora_o_range_recomeca_do_zero_e_confere_o_tamanho(
        tmp_path: Path) -> None:
    srv = _Servidor([CORTE], honra_range=False)
    parcial = tmp_path / "x.hefesto-download"
    try:
        with pytest.raises(OSError, match="incompleto"):
            pp.baixar_a_release(srv.url, parcial)
        pp.baixar_a_release(srv.url, parcial)
        assert parcial.read_bytes() == CORPO
    finally:
        srv.fecha()


def test_o_install_cortado_guarda_o_parcial_e_a_segunda_vez_continua(
        tmp_path: Path, cortando: _Servidor) -> None:
    cache = tmp_path / "cache"
    parcial = cache / f"{NOME}.tar.gz.hefesto-download"

    primeira = pp.adiantar_para_o_cache(_conf(cortando.url), cache_dir=cache,
                                        downloader=pp.baixar_a_release)

    assert primeira.state == "unavailable"
    assert "incompleto" in primeira.detail
    assert "checksum" not in primeira.detail
    assert parcial.stat().st_size == CORTE

    segunda = pp.adiantar_para_o_cache(_conf(cortando.url), cache_dir=cache,
                                       downloader=pp.baixar_a_release)

    assert segunda.state == "em_cache"
    assert (cache / f"{NOME}.tar.gz").read_bytes() == CORPO
    assert not parcial.exists()
    assert cortando.pedidos == [None, f"bytes={CORTE}-"]


def test_o_install_com_o_tamanho_certo_e_o_sha_errado_apaga_o_parcial(
        tmp_path: Path) -> None:
    srv = _Servidor([])
    cache = tmp_path / "cache"
    try:
        res = pp.adiantar_para_o_cache(_conf(srv.url, "0" * 64), cache_dir=cache,
                                       downloader=pp.baixar_a_release)
    finally:
        srv.fecha()

    assert res.state == "checksum_mismatch"
    assert not (cache / f"{NOME}.tar.gz.hefesto-download").exists()


def _release(url: str) -> dict[str, object]:
    return {"tag_name": NOME, "published_at": "2026-01-01T00:00:00Z", "assets": [
        {"name": f"{NOME}-x86_64.tar.gz", "browser_download_url": url},
        {"name": f"{NOME}-x86_64.sha512sum", "browser_download_url": "http://x/soma"}]}


def _ler_de_mentira(url: str, sha512: str) -> object:
    def ler(endereco: str) -> bytes:
        if endereco == pp.GE_ULTIMA_API:
            return json.dumps(_release(url)).encode()
        return f"{sha512}  {NOME}-x86_64.tar.gz\n".encode()
    return ler


def test_o_vigia_cortado_guarda_o_parcial_e_a_segunda_vez_continua(
        tmp_path: Path, cortando: _Servidor) -> None:
    cache = tmp_path / "cache"
    parcial = cache / f"{DO_VIGIA}.tar.gz.hefesto-download"
    ler = _ler_de_mentira(cortando.url, hashlib.sha512(CORPO).hexdigest())

    primeira = pp.baixar_a_ultima_do_ge(cache, ler=ler, forcar=True)  # type: ignore[arg-type]

    assert primeira.estado == "falhou"
    assert "incompleto" in primeira.detalhe
    assert parcial.stat().st_size == CORTE

    segunda = pp.baixar_a_ultima_do_ge(cache, ler=ler, forcar=True)  # type: ignore[arg-type]

    assert segunda.estado == "baixada"
    assert (cache / f"{DO_VIGIA}.tar.gz").read_bytes() == CORPO
    assert cortando.pedidos == [None, f"bytes={CORTE}-"]


def test_o_vigia_com_o_tamanho_certo_e_o_sha_errado_apaga_o_parcial(tmp_path: Path) -> None:
    srv = _Servidor([])
    cache = tmp_path / "cache"
    ler = _ler_de_mentira(srv.url, "0" * 128)
    try:
        res = pp.baixar_a_ultima_do_ge(cache, ler=ler, forcar=True)  # type: ignore[arg-type]
    finally:
        srv.fecha()

    assert res.estado == "checksum"
    assert not (cache / f"{DO_VIGIA}.tar.gz.hefesto-download").exists()
