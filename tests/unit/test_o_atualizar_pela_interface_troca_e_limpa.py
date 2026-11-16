"""O Atualizar da interface baixa, instala, troca as referências e apaga a versão velha.

O-ATUALIZAR-PELA-INTERFACE-BAIXA-INSTALA-TROCA-E-LIMPA-01, 16/11/2026. TUDO É DE MENTIRA: o lar é
``tmp_path`` com ``HOME`` e ``XDG_*`` desviados, a Steam e o cache são pastas, a rede é um
dicionário de URL para bytes e a fila roda no processo do teste. Teste que vai à rede reprova.

Cada peça termina atualizada (baixou, instalou, trocou a referência e apagou a velha depois de a
nova subir, com UMA anterior guardada para voltar), esperando com o motivo, ou falhou com o porquê.
"""
from __future__ import annotations

import contextlib
import functools
import hashlib
import io
import json
import socket
import tarfile
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import proton_pin as pp
from hefesto_dualsense4unix.interface import atualizacoes as tela
from tests.unit.test_o_fixar_proton_desinstala_as_que_sobram import _vdf
from tests.unit.test_o_proton_novo_so_entra_se_passar import _proton_de_mentira

VELHA = "GE-Proton11-7-x86_64"
NOVA = "GE-Proton11-12-x86_64"
MAIS_VELHA = "GE-Proton11-5-x86_64"
URL_DO_TAR = f"https://exemplo.invalid/{NOVA}.tar.gz"
URL_DA_SOMA = f"https://exemplo.invalid/{NOVA}.sha512sum"


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    return casa


@pytest.fixture(autouse=True)
def trava_da_rede(monkeypatch: pytest.MonkeyPatch) -> Any:
    pedidos: list[object] = []

    def _conectar(sock: socket.socket, endereco: object) -> None:
        pedidos.append(endereco)
        raise OSError(f"o teste foi à rede: {endereco}")

    def _resolver(host: object, *_a: object, **_k: object) -> list[object]:
        pedidos.append(host)
        raise OSError(f"o teste foi à rede: {host}")

    monkeypatch.setattr(socket.socket, "connect", _conectar)
    monkeypatch.setattr(socket, "getaddrinfo", _resolver)
    yield pedidos
    assert not pedidos, f"o teste foi à rede: {pedidos}"


def _tarball(tmp: Path, nome: str) -> bytes:
    origem = _proton_de_mentira(tmp / "origem" / nome)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(origem, arcname=nome)
    return buf.getvalue()


class _Rede:
    def __init__(self, mapa: dict[str, bytes]) -> None:
        self.mapa = mapa

    def ler(self, url: str) -> bytes:
        if url not in self.mapa:
            raise OSError("sem rede")
        return self.mapa[url]

    def baixar(self, url: str, destino: Path, passo: at.Passo, _sha: str = "") -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(self.ler(url))
        passo.fracao(1.0)


@pytest.fixture
def steam(lar: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A Steam com a GE velha em todo jogo, o cache com a velha e uma mais velha, e a nova no ar."""
    raiz = lar / ".steam" / "steam"
    (raiz / "config").mkdir(parents=True)
    (raiz / "steamapps").mkdir()
    _proton_de_mentira(raiz / "compatibilitytools.d" / VELHA)
    (raiz / "config" / "config.vdf").write_text(_vdf({"10": VELHA, "20": VELHA}),
                                                encoding="utf-8")
    cache = pp.default_cache_dir()
    cache.mkdir(parents=True)
    (cache / f"{VELHA}.tar.gz").write_bytes(_tarball(tmp_path / "v", VELHA))
    (cache / f"{MAIS_VELHA}.tar.gz").write_bytes(b"sobra de uma subida antiga")
    nova = _tarball(tmp_path / "n", NOVA)
    release = {"tag_name": "GE-Proton11-12", "assets": [
        {"name": f"{NOVA}.tar.gz", "browser_download_url": URL_DO_TAR},
        {"name": f"{NOVA}.sha512sum", "browser_download_url": URL_DA_SOMA}]}
    rede = _Rede({pp.GE_ULTIMA_API: json.dumps(release).encode(), URL_DO_TAR: nova,
                  URL_DA_SOMA: f"{hashlib.sha512(nova).hexdigest()}  x\n".encode()})
    monkeypatch.setattr(pp, "_steam_gate", lambda: None)
    monkeypatch.setattr(pp, "_ler_da_rede", rede.ler)
    monkeypatch.setattr(pp, "baixar_a_ultima_do_ge",
                        functools.partial(pp.baixar_a_ultima_do_ge, ler=rede.ler))
    monkeypatch.setattr(pa, "_baixar", rede.baixar)
    monkeypatch.setattr(censo, "proton_em_uso",
                        lambda *a, **k: censo.ProtonEmUso(frozenset(), ()))
    monkeypatch.setattr(censo, "casas_do_heroic", lambda *a, **k: ((), ()))
    return {"raiz": raiz, "compat": raiz / "compatibilitytools.d", "cache": cache,
            "vdf": raiz / "config" / "config.vdf", "rede": rede}


def _so_o_proton() -> list[at.Peca]:
    return [p for p in pa.registro() if p.id == "proton"]


def _rodar(lista: list[at.Peca], ids: list[str], **k: Any) -> int:
    at.conferir(rede=True, lista=lista)
    return at.rodar(ids, lista=lista, jogo_aberto=lambda: False, reiniciar=lambda: True,
                    reabrir=lambda: True, dormir=k.pop("dormir", lambda _s: None), **k)


def _tarballs(cache: Path) -> list[str]:
    return sorted(p.name.removesuffix(".tar.gz") for p in cache.glob("*.tar.gz"))


def test_o_proton_sobe_troca_os_jogos_apaga_as_velhas_e_guarda_uma_para_voltar(
        steam: dict[str, Any]) -> None:
    """D-1611-O-ATUALIZAR-TROCA-E-LIMPA: a nova sobe e a velha sai."""
    lista = _so_o_proton()
    assert _rodar(lista, ["proton"]) == 0, at.ler_o_andamento()
    linha = at.ler_o_andamento()["pecas"][0]
    assert linha["selo"] == at.PRONTA and linha["etapas"] == dict.fromkeys(at.ETAPAS, "feito")
    mapa = pp.extract_compat_tool_mapping(steam["vdf"].read_text(encoding="utf-8"))
    assert set(mapa.values()) == {NOVA}, "a referência de todo jogo vai para a nova"
    assert sorted(p.name for p in steam["compat"].iterdir()) == [NOVA], "a velha sai da Steam"
    assert _tarballs(steam["cache"]) == [NOVA, VELHA], \
        "no cache fica a nova e UMA anterior, a que volta; a mais velha sai"
    assert at.ler_as_anteriores()["proton"]["anterior"] == "11-7"
    assert at.voltar("proton", lista=lista) == ""
    assert sorted(p.name for p in steam["compat"].iterdir()) == [VELHA]
    mapa = pp.extract_compat_tool_mapping(steam["vdf"].read_text(encoding="utf-8"))
    assert set(mapa.values()) == {VELHA}, "a volta troca a referência de volta"


def test_o_proton_que_nao_sobe_nao_apaga_nada(steam: dict[str, Any],
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    def _nao_extrai(*_a: object, **_k: object) -> None:
        raise OSError("o tar não abriu")

    monkeypatch.setattr(pp, "ensure_pinned_proton", _nao_extrai)
    lista = _so_o_proton()
    assert _rodar(lista, ["proton"]) == 1
    assert at.ler_o_andamento()["pecas"][0]["selo"] == at.FALHOU
    assert sorted(p.name for p in steam["compat"].iterdir()) == [VELHA]
    mapa = pp.extract_compat_tool_mapping(steam["vdf"].read_text(encoding="utf-8"))
    assert set(mapa.values()) == {VELHA}
    assert VELHA in _tarballs(steam["cache"]), "a velha só sai depois que a nova subiu"


def test_o_cache_do_proton_guarda_uma_anterior_mesmo_pelo_vigia(steam: dict[str, Any]) -> None:
    """O ``--manter`` do vigia sobe por fora do atualizador: a limpeza do cache é a mesma."""
    cache, compat = steam["cache"], steam["compat"]
    rede = steam["rede"]

    def baixar(url: str, destino: Path) -> None:
        destino.write_bytes(rede.ler(url))

    baixada = pp.baixar_a_ultima_do_ge(cache, forcar=True, baixar=baixar)
    assert baixada.estado == "baixada"
    conf = pp._load_conf(None)
    assert pp.instalar_a_ultima_do_cache(conf, compat_dir=compat, cache_dir=cache).estado \
        == "instalada"
    pp.lock_proton_for_all_games(conf=conf, todos=True)
    pp.apagar_as_sobras()
    assert _tarballs(cache) == [NOVA, VELHA]
    assert pp._ler_registro(cache).get("anterior") == VELHA


def _tar_do_umu(caminho: Path) -> Path:
    with tarfile.open(caminho, "w") as tar:
        info = tarfile.TarInfo("umu/umu-run")
        info.size, info.mode = 10, 0o755
        tar.addfile(info, io.BytesIO(b"#!/bin/sh\n"))
    return caminho


def test_o_umu_troca_o_link_apaga_as_velhas_e_o_pacote_baixado(lar: Path) -> None:
    pasta_do_cache = pa._cache() / "umu"
    pasta_do_cache.mkdir(parents=True)
    dados: dict[str, Any] = {}
    for versao in ("1.4.2", "1.4.3", "1.4.4"):
        tar = _tar_do_umu(pasta_do_cache / f"umu-launcher-{versao}-zipapp.tar")
        dados = {"tar": str(tar), "tag": versao}
        dados.update(pa._instalar_o_umu(at.Passo(), dados))
        pa._aplicar_o_umu(at.Passo(), dados)
    casa = lar / ".local" / "bin" / "umu-run"
    assert "1.4.4" in str(casa.resolve()), "a referência vai para a nova"
    assert sorted(p.name for p in pa._pasta_do_umu().iterdir()) == ["1.4.3", "1.4.4", "atual"]
    assert sorted(p.name for p in pasta_do_cache.iterdir()) == [
        "umu-launcher-1.4.4-zipapp.tar"], "o pacote baixado das versões que saíram sai junto"


def _peca_do_python(feito: list[str]) -> at.Peca:
    def baixar(_p: at.Passo, _d: dict[str, Any]) -> dict[str, Any]:
        return {"pacotes": {"evdev": ["1.9.3", "2.0.0"]}}

    return at.Peca("python", "Python", "As bibliotecas", "O serviço",
                   lambda rede: at.Versoes("", "1" if rede else None, rotulo="1 pacote",
                                           nova=True),
                   baixar, None, None, lambda anterior: feito.append(str(anterior.get("dados"))))


def test_a_peca_sem_numero_de_versao_tambem_volta_pela_tela() -> None:
    """O Python não tem versão própria: a anterior dele são as bibliotecas de antes."""
    feito: list[str] = []
    lista = [_peca_do_python(feito)]
    assert _rodar(lista, ["python"]) == 0
    html = tela.html_das_anteriores(at.ler_as_anteriores(), ["python"])
    assert 'data-gesto="voltar-a-anterior" data-v="python"' in html, html
    assert ">Voltar a <" not in html and ">Voltar a  <" not in html
    assert at.voltar("python", lista=lista) == ""
    assert feito and "evdev" in feito[0]


def test_o_comando_que_trava_calado_respeita_o_teto() -> None:
    inicio = time.monotonic()
    rc, ultima = pa._comando(["sleep", "8"], teto_s=0.5)
    assert time.monotonic() - inicio < 5, "o teto vale também para o comando que não escreve"
    assert rc == 124, (rc, ultima)


def test_o_teto_solta_a_fila_mesmo_com_o_grupo_fora_do_alcance(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Atrás do ``sudo -n`` o comando é root: quem chama não o mata, e ele segura a saída. O
    sinal recusado (EPERM, como o kernel responde) não pode prender a fila no teto."""
    import os
    import signal

    pids: list[int] = []

    def _recusado(_pgid: int, _sinal: int) -> None:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(os, "killpg", _recusado)
    inicio = time.monotonic()
    try:
        rc, ultima = pa._comando(["sh", "-c", "echo $$; exec sleep 30"], teto_s=0.5,
                                 linha=lambda t: pids.extend([int(t)] if t.isdigit() else []))
    finally:
        for pid in pids:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
    assert time.monotonic() - inicio < 20, "o teto vale também para o comando que não se mata"
    assert rc == 124, (rc, ultima)
    assert pids, "a linha do comando chegou antes do teto"


def _peca(ident: str, feito: list[str], *, espera: list[bool] | None = None,
          falha: str = "") -> at.Peca:
    def instalar(_p: at.Passo, _d: dict[str, Any]) -> None:
        if espera is not None and not espera[0]:
            raise at.EsperaError("há trabalho em voo", lambda: espera[0])
        if falha:
            raise at.EtapaFalhouError(falha)
        feito.append(ident)

    return at.Peca(ident, ident.upper(), "dica", "todos",
                   lambda rede: at.Versoes("1.0", "1.1" if rede else None),
                   None, instalar, None, lambda _a: None)


def test_o_clique_no_atualizar_termina_cada_peca_num_dos_tres_estados(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Do clique ao fim: a que sobe fica «Atualizado», a que espera mostra o motivo enquanto
    espera e sobe sozinha quando a condição some, e a que falha diz o porquê."""
    from hefesto_dualsense4unix.interface.pacotes import atualizacoes as gestos

    feito: list[str] = []
    livre = [False]
    vistas: list[str] = []
    lista = [_peca("a", feito), _peca("b", feito, espera=livre),
             _peca("c", feito, falha="sem rede")]
    monkeypatch.setattr(at, "pecas", lambda: lista)
    at.conferir(rede=True, lista=lista)

    def dormir(_s: float) -> None:
        vistas.append(tela.html_do_andamento(at.ler_o_andamento(), rodando=True))
        livre[0] = True

    def soltar(ids: list[str]) -> bool:
        at.rodar(ids, lista=lista, jogo_aberto=lambda: False, reiniciar=lambda: True,
                 reabrir=lambda: True, dormir=dormir)
        return True

    monkeypatch.setattr(at, "soltar", soltar)
    gestos.TELA.update({"vista": "pergunta", "reinstalar": set()})
    gestos.atualizar(None, {}, None)  # type: ignore[arg-type]
    assert vistas and "Esperando: há trabalho em voo" in vistas[0], "a espera aparece na tela"
    fim = tela.html_do_andamento(at.ler_o_andamento(), rodando=False)
    assert feito == ["a", "b"], "a que esperava subiu sozinha quando a condição sumiu"
    assert fim.count('class="mp-l ok"') == 3, "a, b e o serviço: «Atualizado»"
    assert "Falhou: sem rede" in fim
    assert 'data-gesto="atualizacoes-tentar"' in fim
