#!/usr/bin/env python3
"""O servidor de artefatos do ci-local: a API v4 do GitHub, com os campos que a do act recusa.

O `act` recusa o `mime_type` do `upload-artifact@v7` (0.2.89 a 0.2.97, nektos/act#6114). Este
atende o que o runner chama: as cinco chamadas Twirp e o blob do Azure. Só escuta em 127.0.0.1,
e `--dono` o encerra junto com o processo do ci-local.

    servidor-de-artefatos.py --raiz PASTA --porta-em ARQUIVO --dono PID
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import threading
import time
import zlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

TWIRP = "/twirp/github.actions.results.api.v1.ArtifactService/"
BLOB = "/blob/"
MIME_PADRAO = "application/zip"
PEDACO = 1024 * 1024
ESPERA_DO_DONO_S = 2.0


class Recusa(Exception):
    def __init__(self, status: int, codigo: str, texto: str) -> None:
        super().__init__(texto)
        self.status = status
        self.codigo = codigo


class Deposito:
    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.trava = threading.Lock()

    def _pasta(self, corrida: str, nome: str) -> Path:
        partes = (corrida, nome)
        if not all(partes) or any(p in {".", ".."} for p in partes):
            raise Recusa(400, "invalid_argument", f"artefato sem nome válido: {partes}")
        return self.raiz / quote(corrida, safe="") / quote(nome, safe="")

    def _meta(self, pasta: Path) -> dict[str, Any]:
        arquivo = pasta / "meta.json"
        if not arquivo.is_file():
            raise Recusa(404, "not_found", f"não há artefato em {pasta.name}")
        dados: dict[str, Any] = json.loads(arquivo.read_text(encoding="utf-8"))
        return dados

    def _gravar_meta(self, pasta: Path, meta: dict[str, Any]) -> None:
        temporario = pasta / "meta.json.novo"
        temporario.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        temporario.replace(pasta / "meta.json")

    def criar(self, corrida: str, job: str, nome: str, mime: str) -> None:
        pasta = self._pasta(corrida, nome)
        with self.trava:
            shutil.rmtree(pasta, ignore_errors=True)
            (pasta / "blocos").mkdir(parents=True)
            self._gravar_meta(
                pasta,
                {
                    "corrida": corrida,
                    "job": job,
                    "nome": nome,
                    "mime": mime or MIME_PADRAO,
                    "criado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "pronto": False,
                },
            )

    def caminho_do_bloco(self, corrida: str, nome: str, bloco: str) -> Path:
        pasta = self._pasta(corrida, nome)
        self._meta(pasta)
        return pasta / "blocos" / hashlib.sha256(bloco.encode()).hexdigest()

    def caminho_do_conteudo(self, corrida: str, nome: str) -> Path:
        pasta = self._pasta(corrida, nome)
        self._meta(pasta)
        return pasta / "blob"

    def juntar_blocos(self, corrida: str, nome: str, lista: bytes) -> None:
        pasta = self._pasta(corrida, nome)
        self._meta(pasta)
        ids = re.findall(rb"<(?:Latest|Committed|Uncommitted)>([^<]*)<", lista)
        with (pasta / "blob").open("wb") as saida:
            for bloco in ids:
                parte = self.caminho_do_bloco(corrida, nome, bloco.decode())
                if not parte.is_file():
                    raise Recusa(400, "invalid_argument", f"o bloco {bloco!r} não subiu")
                with parte.open("rb") as entrada:
                    shutil.copyfileobj(entrada, saida, PEDACO)
        shutil.rmtree(pasta / "blocos", ignore_errors=True)

    def finalizar(self, corrida: str, nome: str, tamanho: str, resumo: str) -> str:
        pasta = self._pasta(corrida, nome)
        meta = self._meta(pasta)
        conteudo = pasta / "blob"
        if not conteudo.is_file():
            raise Recusa(400, "invalid_argument", f"o artefato {nome} não subiu")
        medido = conteudo.stat().st_size
        if tamanho and int(tamanho) != medido:
            raise Recusa(400, "invalid_argument", f"{nome}: {tamanho} bytes ditos, {medido} recebidos")
        calculo = hashlib.sha256()
        with conteudo.open("rb") as entrada:
            while pedaco := entrada.read(PEDACO):
                calculo.update(pedaco)
        digesto = f"sha256:{calculo.hexdigest()}"
        if resumo and resumo != digesto:
            raise Recusa(400, "invalid_argument", f"{nome}: o resumo {resumo} não é o {digesto}")
        with self.trava:
            meta.update(pronto=True, tamanho=medido, digesto=digesto)
            self._gravar_meta(pasta, meta)
        return self._id(corrida, nome)

    def _id(self, corrida: str, nome: str) -> str:
        return str(zlib.crc32(f"{corrida}/{nome}".encode()))

    def listar(self, corrida: str, nome: str, identidade: str) -> list[dict[str, Any]]:
        achados = []
        pasta_da_corrida = self.raiz / quote(corrida, safe="")
        for pasta in sorted(pasta_da_corrida.glob("*")):
            arquivo = pasta / "meta.json"
            if not arquivo.is_file():
                continue
            meta = self._meta(pasta)
            numero = self._id(corrida, meta["nome"])
            if meta["pronto"] and nome in ("", meta["nome"]) and identidade in ("", "0", numero):
                achados.append(
                    {
                        "workflowRunBackendId": corrida,
                        "workflowJobRunBackendId": meta["job"],
                        "databaseId": numero,
                        "name": meta["nome"],
                        "size": str(meta["tamanho"]),
                        "digest": meta["digesto"],
                        "createdAt": meta["criado"],
                    }
                )
        return achados

    def pronto(self, corrida: str, nome: str) -> tuple[Path, dict[str, Any]]:
        pasta = self._pasta(corrida, nome)
        meta = self._meta(pasta)
        if not meta["pronto"]:
            raise Recusa(404, "not_found", f"o artefato {nome} não fechou")
        return pasta / "blob", meta

    def apagar(self, corrida: str, nome: str) -> str:
        pasta = self._pasta(corrida, nome)
        self._meta(pasta)
        with self.trava:
            shutil.rmtree(pasta)
        return self._id(corrida, nome)


class Atendente(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    deposito: Deposito

    def _responder(self, status: int, corpo: bytes = b"", tipo: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, dados: dict[str, Any]) -> None:
        self._responder(200, json.dumps(dados).encode())

    def _tamanho(self) -> int:
        tamanho = self.headers.get("Content-Length")
        if tamanho is None:
            raise Recusa(411, "malformed", "pedido sem Content-Length")
        return int(tamanho)

    def _url(self, corrida: str, nome: str) -> str:
        return f"http://{self.headers['Host']}{BLOB}{quote(corrida, safe='')}/{quote(nome, safe='')}"

    def _protegido(self, atender: Any) -> None:
        try:
            atender()
        except (Recusa, ValueError) as erro:
            status, codigo = (
                (erro.status, erro.codigo) if isinstance(erro, Recusa) else (400, "malformed")
            )
            self.log_error("%s", erro)
            self.close_connection = True
            self._responder(status, json.dumps({"code": codigo, "msg": str(erro)}).encode())

    def do_POST(self) -> None:
        self._protegido(self._twirp)

    def do_PUT(self) -> None:
        self._protegido(self._subir)

    def do_GET(self) -> None:
        self._protegido(self._descer)

    def _twirp(self) -> None:
        corpo = self.rfile.read(self._tamanho())
        endereco = urlsplit(self.path).path
        if not endereco.startswith(TWIRP):
            raise Recusa(404, "bad_route", endereco)
        pedido: dict[str, Any] = json.loads(corpo or b"{}")
        corrida = str(pedido.get("workflow_run_backend_id", ""))
        job = str(pedido.get("workflow_job_run_backend_id", ""))
        nome = str(pedido.get("name", ""))
        metodo = endereco.removeprefix(TWIRP)
        d = self.deposito
        if metodo == "CreateArtifact":
            d.criar(corrida, job, nome, str(pedido.get("mime_type") or ""))
            self._json({"ok": True, "signedUploadUrl": self._url(corrida, nome)})
        elif metodo == "FinalizeArtifact":
            resumo = str(pedido.get("hash") or "")
            numero = d.finalizar(corrida, nome, str(pedido.get("size", "")), resumo)
            self._json({"ok": True, "artifactId": numero})
        elif metodo == "ListArtifacts":
            filtro = str(pedido.get("name_filter") or "")
            identidade = str(pedido.get("id_filter") or "")
            self._json({"artifacts": d.listar(corrida, filtro, identidade)})
        elif metodo == "GetSignedArtifactURL":
            d.pronto(corrida, nome)
            self._json({"signedUrl": self._url(corrida, nome)})
        elif metodo == "DeleteArtifact":
            self._json({"ok": True, "artifactId": d.apagar(corrida, nome)})
        else:
            raise Recusa(404, "bad_route", metodo)

    def _alvo(self) -> tuple[str, str, dict[str, list[str]]]:
        partes = urlsplit(self.path)
        pedacos = partes.path.removeprefix(BLOB).split("/")
        if not partes.path.startswith(BLOB) or len(pedacos) != 2:
            raise Recusa(404, "bad_route", partes.path)
        return unquote(pedacos[0]), unquote(pedacos[1]), parse_qs(partes.query)

    def _subir(self) -> None:
        tamanho = self._tamanho()
        corrida, nome, consulta = self._alvo()
        comp = consulta.get("comp", [""])[0].lower()
        if comp == "blocklist":
            self.deposito.juntar_blocos(corrida, nome, self.rfile.read(tamanho))
        else:
            bloco = consulta.get("blockid", [""])[0]
            if comp == "block":
                destino = self.deposito.caminho_do_bloco(corrida, nome, bloco)
            else:
                destino = self.deposito.caminho_do_conteudo(corrida, nome)
            with destino.open("wb") as saida:
                restante = tamanho
                while restante > 0:
                    pedaco = self.rfile.read(min(restante, PEDACO))
                    if not pedaco:
                        raise Recusa(400, "malformed", "o corpo acabou antes do Content-Length")
                    saida.write(pedaco)
                    restante -= len(pedaco)
        self._responder(201)

    def _descer(self) -> None:
        corrida, nome, _ = self._alvo()
        conteudo, meta = self.deposito.pronto(corrida, nome)
        self.send_response(200)
        self.send_header("Content-Type", meta["mime"])
        self.send_header("Content-Length", str(conteudo.stat().st_size))
        self.send_header(
            "Content-Disposition", f"attachment; filename*=UTF-8''{quote(nome, safe='')}"
        )
        self.end_headers()
        with conteudo.open("rb") as entrada:
            shutil.copyfileobj(entrada, self.wfile, PEDACO)


def _acompanhar_o_dono(dono: int) -> None:
    while True:
        try:
            os.kill(dono, 0)
        except ProcessLookupError:
            os._exit(0)
        time.sleep(ESPERA_DO_DONO_S)


def main() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--raiz", type=Path, required=True)
    argumentos.add_argument("--porta-em", type=Path, required=True)
    argumentos.add_argument("--dono", type=int, required=True)
    opcoes = argumentos.parse_args()
    opcoes.raiz.mkdir(parents=True, exist_ok=True)
    Atendente.deposito = Deposito(opcoes.raiz)
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Atendente)
    servidor.daemon_threads = True
    threading.Thread(target=_acompanhar_o_dono, args=(opcoes.dono,), daemon=True).start()
    temporario = opcoes.porta_em.with_name(opcoes.porta_em.name + ".novo")
    temporario.write_text(str(servidor.server_address[1]), encoding="utf-8")
    temporario.replace(opcoes.porta_em)
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
