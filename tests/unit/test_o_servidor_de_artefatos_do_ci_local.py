"""O servidor de artefatos do ci-local fala o que o `upload-artifact@v7` e o `@v8` de descida falam.

O `act` recusa o `mime_type` do v7 (O-CI-LOCAL-GUARDA-O-ARTEFATO-DO-UPLOAD-V7-01). Estas réguas
repetem as chamadas do cliente da ação, na ordem e na forma dele, contra o servidor de verdade.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SERVIDOR = RAIZ / "scripts" / "ci-local" / "servidor-de-artefatos.py"
TWIRP = "/twirp/github.actions.results.api.v1.ArtifactService/"
IDS = {"workflow_run_backend_id": "1", "workflow_job_run_backend_id": "1"}


class Cliente:
    def __init__(self, raiz: Path, dono: int) -> None:
        self.raiz = raiz
        arquivo = raiz.parent / f"porta-{time.monotonic_ns()}"
        self.processo = subprocess.Popen(
            [sys.executable, str(SERVIDOR), "--raiz", str(raiz), "--porta-em", str(arquivo),
             "--dono", str(dono)],
            stderr=subprocess.DEVNULL,
        )
        prazo = time.monotonic() + 15
        while not arquivo.exists():
            assert time.monotonic() < prazo, "o servidor não escreveu a porta"
            time.sleep(0.02)
        self.porta = int(arquivo.read_text(encoding="utf-8"))

    def pedir(
        self, metodo: str, caminho: str, corpo: bytes = b""
    ) -> tuple[int, dict[str, str], bytes]:
        conexao = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        conexao.request(metodo, caminho, body=corpo, headers={"Content-Length": str(len(corpo))})
        resposta = conexao.getresponse()
        dados = resposta.read()
        conexao.close()
        return resposta.status, {k.lower(): v for k, v in resposta.getheaders()}, dados

    def twirp(self, chamada: str, **corpo: Any) -> tuple[int, dict[str, Any]]:
        status, _, dados = self.pedir("POST", TWIRP + chamada, json.dumps(corpo).encode())
        return status, json.loads(dados or b"{}")

    def subir(self, nome: str, conteudo: bytes, mime: str = "application/zip") -> tuple[int, str]:
        status, criado = self.twirp(
            "CreateArtifact", **IDS, name=nome, version=7, mime_type=mime,
            expires_at="2026-11-10T00:00:00Z",
        )
        assert status == 200 and criado["ok"], criado
        destino = urlsplit(criado["signedUploadUrl"])
        assert destino.path.startswith("/blob/")
        metade = len(conteudo) // 2
        ids: list[str] = []
        for pedaco in (conteudo[:metade], conteudo[metade:]):
            bloco = base64.b64encode(f"bloco-{len(ids):04d}".encode()).decode()
            ids.append(bloco)
            status, _, _ = self.pedir("PUT", f"{destino.path}?comp=block&blockid={bloco}", pedaco)
            assert status == 201
        lista = "".join(f"<Latest>{b}</Latest>" for b in ids)
        xml = f'<?xml version="1.0"?><BlockList>{lista}</BlockList>'.encode()
        status, _, _ = self.pedir("PUT", f"{destino.path}?comp=blocklist", xml)
        assert status == 201
        digesto = hashlib.sha256(conteudo).hexdigest()
        return status, f"sha256:{digesto}"

    def fechar(self) -> None:
        self.processo.terminate()
        self.processo.wait(timeout=10)


@pytest.fixture()
def cliente(tmp_path: Path) -> Iterator[Cliente]:
    servidor = Cliente(tmp_path / "artefatos", os.getpid())
    yield servidor
    servidor.fechar()


def test_o_que_o_v7_sobe_o_v8_desce_igual_e_com_o_resumo(cliente: Cliente) -> None:
    conteudo = b"PK\x03\x04" + bytes(range(256)) * 50
    _, resumo = cliente.subir("cobertura-00-05", conteudo)
    status, fechado = cliente.twirp(
        "FinalizeArtifact", **IDS, name="cobertura-00-05", size=str(len(conteudo)), hash=resumo
    )
    assert status == 200 and fechado["ok"] and int(fechado["artifactId"]) > 0
    status, lista = cliente.twirp("ListArtifacts", **IDS, name_filter="cobertura-00-05")
    assert status == 200
    artefato = lista["artifacts"][0]
    assert artefato["size"] == str(len(conteudo)) and artefato["digest"] == resumo
    status, assinada = cliente.twirp("GetSignedArtifactURL", **IDS, name="cobertura-00-05")
    assert status == 200
    status, cabecalhos, descido = cliente.pedir("GET", urlsplit(assinada["signedUrl"]).path)
    assert status == 200 and descido == conteudo
    assert cabecalhos["content-type"] == "application/zip"
    _, por_id = cliente.twirp("ListArtifacts", **IDS, id_filter=fechado["artifactId"])
    assert [a["name"] for a in por_id["artifacts"]] == ["cobertura-00-05"]


def test_o_arquivo_sem_zip_desce_com_o_tipo_e_o_nome_que_subiu(cliente: Cliente) -> None:
    """O `archive: false` do v7: o v8 decide o nome e se extrai pelos cabeçalhos do blob."""
    _, resumo = cliente.subir("relatório.txt", b"texto cru", mime="text/plain")
    cliente.twirp("FinalizeArtifact", **IDS, name="relatório.txt", size="9", hash=resumo)
    _, assinada = cliente.twirp("GetSignedArtifactURL", **IDS, name="relatório.txt")
    _, cabecalhos, descido = cliente.pedir("GET", urlsplit(assinada["signedUrl"]).path)
    assert descido == b"texto cru" and cabecalhos["content-type"] == "text/plain"
    assert "filename*=UTF-8''relat%C3%B3rio.txt" in cabecalhos["content-disposition"]


def test_artefato_com_resumo_errado_nao_fecha_e_nao_se_lista(cliente: Cliente) -> None:
    cliente.subir("dados", b"o que subiu")
    status, recusa = cliente.twirp(
        "FinalizeArtifact", **IDS, name="dados", size="11", hash="sha256:" + "0" * 64
    )
    assert status == 400 and "dados" in recusa["msg"]
    assert cliente.twirp("ListArtifacts", **IDS)[1]["artifacts"] == []
    assert cliente.twirp("GetSignedArtifactURL", **IDS, name="dados")[0] == 404


def test_artefato_com_tamanho_errado_nao_fecha(cliente: Cliente) -> None:
    cliente.subir("dados", b"o que subiu")
    assert cliente.twirp("FinalizeArtifact", **IDS, name="dados", size="10")[0] == 400


def test_o_nome_nao_sai_da_pasta(cliente: Cliente, tmp_path: Path) -> None:
    assert cliente.twirp("CreateArtifact", **IDS, name="..", version=7)[0] == 400
    assert cliente.pedir("PUT", "/blob/1/%2e%2e?comp=block&blockid=x", b"x")[0] == 400
    assert cliente.pedir("GET", "/blob/%2e%2e/segredo")[0] == 400
    cliente.twirp("CreateArtifact", **IDS, name="../fora", version=7)
    assert not (tmp_path / "fora").exists()
    assert (cliente.raiz / "1" / "..%2Ffora" / "meta.json").is_file()


def test_o_artefato_fica_para_o_job_seguinte_e_o_novo_substitui(
    cliente: Cliente, tmp_path: Path
) -> None:
    """Cada `act` chama o seu job, e o `deb` lê o que o `build` subiu em outra chamada."""
    _, resumo = cliente.subir("dist", b"velho")
    cliente.twirp("FinalizeArtifact", **IDS, name="dist", size="5", hash=resumo)
    outro = Cliente(tmp_path / "artefatos", os.getpid())
    try:
        assert [a["name"] for a in outro.twirp("ListArtifacts", **IDS)[1]["artifacts"]] == ["dist"]
        _, resumo = outro.subir("dist", b"novo!!")
        outro.twirp("FinalizeArtifact", **IDS, name="dist", size="6", hash=resumo)
        _, assinada = outro.twirp("GetSignedArtifactURL", **IDS, name="dist")
        assert outro.pedir("GET", urlsplit(assinada["signedUrl"]).path)[2] == b"novo!!"
    finally:
        outro.fechar()


def test_apagar_tira_o_artefato(cliente: Cliente) -> None:
    _, resumo = cliente.subir("dados", b"abc")
    cliente.twirp("FinalizeArtifact", **IDS, name="dados", size="3", hash=resumo)
    assert cliente.twirp("DeleteArtifact", **IDS, name="dados")[1]["ok"]
    assert cliente.twirp("ListArtifacts", **IDS)[1]["artifacts"] == []


def test_o_servidor_morre_com_o_dono(tmp_path: Path) -> None:
    """Um ci-local morto por SIGKILL não pode deixar um servidor ocupando a porta para sempre."""
    dono = subprocess.Popen(["sleep", "60"])
    servidor = Cliente(tmp_path / "artefatos", dono.pid)
    dono.kill()
    dono.wait(timeout=5)
    try:
        assert servidor.processo.wait(timeout=8) == 0
    finally:
        servidor.processo.kill()
