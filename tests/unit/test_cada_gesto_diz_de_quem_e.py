"""Cada gesto diz de quem é (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01, réguas 9 a 11)."""
from __future__ import annotations

import html.parser
import sys
from pathlib import Path
from typing import Any

import pytest

import hefesto_dualsense4unix
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.utils import maquina as m

UM = "aa:bb:cc:00:00:01"
DOIS = "aa:bb:cc:00:00:02"


def _pacotes() -> Any:
    """Os pacotes como o piloto os importa (o `interface/` no caminho)."""
    interface = str(Path(hefesto_dualsense4unix.__file__).parent / "interface")
    if interface not in sys.path:
        sys.path.insert(0, interface)
    import pacotes

    pacotes._carregar_tudo()
    return pacotes


class _Gestos(html.parser.HTMLParser):
    """Os gestos de uma página, fora dos ``<script>``, com o nome que o piloto despacha."""

    def __init__(self) -> None:
        super().__init__()
        self.gestos: set[str] = set()
        self._no_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self._no_script = True
            return
        if self._no_script:
            return
        dados = {chave: valor for chave, valor in attrs if valor}
        for chave in ("data-gesto", "data-hef-gesto", "data-papel"):
            if chave in dados:
                self.gestos.add(str(dados[chave]))
                break

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._no_script = False


def _as_dez() -> list[str]:
    pasta = onde.pagina("01-jogar.html").parent
    nomes = sorted(p.name for p in pasta.glob("[01][0-9]-*.html"))
    assert len(nomes) == 10, nomes
    return nomes


def _gestos(nome: str, *, publicado: bool) -> set[str]:
    leitor = _Gestos()
    leitor.feed(onde.pagina(nome, publicado=publicado).read_text(encoding="utf-8"))
    return leitor.gestos


def _vistos() -> set[tuple[str, str]]:
    """Todo ``(página, gesto)`` da página publicada e do desenho."""
    return {(nome, g) for nome in _as_dez() for publicado in (True, False)
            for g in _gestos(nome, publicado=publicado)}


def test_todo_gesto_das_dez_tem_camada() -> None:
    """Cada gesto das dez (publicada e desenho) tem linha em ``CAMADA``.

    MORDIDA: apagar a linha do ``vel-cursor`` da tabela reprova.
    """
    camada = _pacotes().camada
    faltam = sorted(
        f"{p}·{g}" for p, g in _vistos()
        if (p, g) not in camada.CAMADA)
    assert not faltam, f"gesto sem camada: {faltam}"


#: O gesto nasceu com a base comum (A-BASE-COMUM-DAS-ABAS-01) e o botão «Modo automático» que o
#: aciona entra na página com a sprint da própria aba (A-ABA-CONTROLES-DO-TODO-01). Sai desta
#: lista no dia em que a página o trouxer.
#: O «Desligar» saiu do desenho da 04 (a lista Efeito tem «Sem efeito»), mas a página publicada o
#: traz até o `--publicar 04`; no dia em que ela perder o botão, sai o gesto `apagar` do pacote, a
#: linha dele da `CAMADA` e esta entrada (o `apagar` vira o miolo do `efeito-da-luz`).
A_ABA_AINDA_TRAZ = {
    ("02-controles.html", "modo-dos-controles"),
    ("04-iluminacao.html", "apagar"),
}


#: Os quatro que a Perfis do todo tirou de propósito (A-ABA-PERFIS-DO-TODO-01, `5faca7e8a`; o
#: `aba10.py` exige que não voltem): «Nome do jogo» e «Aplicar em» substituem o Nome, o Funciona em
#: e o Detectar, e a ordem se arrasta em «Qual vale primeiro». Saem com
#: OS-GESTOS-QUE-A-PERFIS-DO-TODO-DEIXOU-SEM-BOTAO-SAEM-01.
SEM_BOTAO_NA_PAGINA = {
    ("10-perfis.html", "detectar"),
    ("10-perfis.html", "editor.ambiente"),
    ("10-perfis.html", "perfis.renomear"),
    ("10-perfis.html", "editor.prioridade"),
    # O «Parar tudo» só existe na janela da extensão que o declara no manifesto; a do desenho não
    # declara (a dos acessórios, que o trazia, saiu em 19/10/2026).
    ("07-lancadores.html", "parar-tudo-da-modificacao"),
}


def test_toda_linha_da_camada_tem_gesto() -> None:
    """E toda linha tem gesto na página."""
    pac = _pacotes()
    camada = pac.camada
    vistos = _vistos()
    sobra = sorted(f"{p}·{g}" for p, g in camada.CAMADA
                   if (p, g) not in vistos and (p, g) not in A_ABA_AINDA_TRAZ
                   and (p, g) not in SEM_BOTAO_NA_PAGINA)
    assert not sobra, f"linha sem gesto na página: {sobra}"
    assert set(camada.CAMADA.values()) <= camada.CAMADAS


def test_quem_grava_pelo_dono_e_do_computador() -> None:
    """A camada concorda com o que o gesto declara que grava."""
    pac = _pacotes()
    camada = pac.camada
    erradas = []
    for chave, escritor in pac.GESTOS_QUE_MEXEM.items():
        esperada = {"gravar_pelo_gesto": camada.COMPUTADOR,
                    "voltar_o_computador_ao_de_fabrica": camada.COMPUTADOR}.get(escritor)
        if esperada is not None and camada.CAMADA.get(chave) != esperada:
            erradas.append(f"{chave} grava {escritor} e a camada diz {camada.CAMADA.get(chave)}")
    assert not erradas, erradas


class _Ponte:
    """Um daemon de papel que confirma tudo: o que se mede aqui é o disco."""

    def __getattr__(self, nome: str) -> Any:
        def registrar(*_a: Any, **_k: Any) -> Any:
            if nome == "resultado":
                return {"status": "ok"}
            if nome.endswith("_detalhado"):
                return {"status": "ok", "por_uniq": True}
            return True
        return registrar


def _contexto(pac: Any, ativo: str, *uniqs: str) -> Any:
    conectados = [{"uniq": u, "connected": True, "transport": "usb", "is_primary": i == 0,
                   "inputs": {}, "audio": {"mic_mudo": False},
                   "speaker": {"volume": 100, "muted": False}}
                  for i, u in enumerate(uniqs or (UM,))]
    mesa = [{"pref": f"p{i + 1}", "jogador": i + 1, "uniq": c["uniq"], "nome": "Régua",
             "via": "USB", "cor": "white", "transporte": "usb"}
            for i, c in enumerate(conectados)]
    return pac.Contexto(
        state={"active_profile": ativo, "rumble_policy": "balanceado", "rumble_ff": {},
               "mouse_emulation": {"enabled": True, "speed": 6, "scroll_speed": 1},
               "keyboard_emulation": {"enabled": True}},
        mesa=mesa, conectados=conectados, estados={})


def _perfil(nome: str, **campos: Any) -> Profile:
    return Profile.model_validate(
        {"name": nome, "match": {"type": "criteria", "window_class": [nome.lower()]},
         **campos})


CLIQUES: list[tuple[str, str, dict[str, Any]]] = [
    ("02-controles.html", "volume", {"uniq": UM, "volume": "microfone", "valor": "42"}),
    ("04-iluminacao.html", "brilho-luzes", {"uniq": UM, "controle": "p1", "luzes": "forte"}),
    ("05-vibracao.html", "forca", {"uniq": UM, "forca": "max"}),
    ("06-navegacao.html", "vel-cursor", {"valor": "11"}),
    ("06-navegacao.html", "vel-rolagem", {"valor": "4"}),
    ("06-navegacao.html", "teclado", {"valor": "Sempre"}),
]


@pytest.mark.parametrize(("aba", "gesto", "carga"), CLIQUES,
                         ids=[f"{a[:2]}-{g}" for a, g, _c in CLIQUES])
def test_o_gesto_vale_para_o_perfil_ativo_e_para_nenhum_outro(
    aba: str, gesto: str, carga: dict[str, Any]
) -> None:
    """Com um jogo ativo o gesto grava no perfil DELE; o computador e os outros ficam.

    Os outros dois perfis do disco (o Freestyle e um outro jogo) ficam byte a
    byte, e o ``maquina.json`` não muda (D-0610-O-ESCOPO-SAI-DAS-ABAS).

    MORDIDA: devolver ao ``onde_grava`` o «só se o jogo já sobrepõe» reprova.
    """
    pac = _pacotes()
    assert pac.camada.CAMADA[(aba, gesto)] == pac.camada.COMPUTADOR
    ativo = save_profile(_perfil("Jogo X"))
    outros = [save_profile(_perfil(n)) for n in ("Freestyle", "Jogo Y")]
    antes_ativo = ativo.read_bytes()
    antes = [c.read_bytes() for c in outros]
    maquina_antes = m.carregar_maquina().computador
    fn = pac.gesto_da_pagina(aba, gesto)
    assert fn is not None, f"{aba}·{gesto} sem dono"
    fn(_contexto(pac, "Jogo X"), dict(carga), _Ponte())
    assert [c.read_bytes() for c in outros] == antes, f"{aba}·{gesto} mudou outro perfil"
    assert ativo.read_bytes() != antes_ativo, (
        f"{aba}·{gesto} não chegou ao perfil do jogo ativo")
    assert m.carregar_maquina().computador == maquina_antes, (
        f"{aba}·{gesto} mexeu no computador com um jogo ativo")


@pytest.mark.parametrize(("aba", "gesto", "carga"), CLIQUES,
                         ids=[f"{a[:2]}-{g}" for a, g, _c in CLIQUES])
def test_sem_jogo_o_gesto_vale_para_o_computador(
    aba: str, gesto: str, carga: dict[str, Any]
) -> None:
    """Com o Freestyle ativo o gesto grava no ``maquina.json`` e em perfil nenhum."""
    pac = _pacotes()
    caminhos = [save_profile(_perfil(n)) for n in ("Jogo X", "Freestyle", "Jogo Y")]
    antes = [c.read_bytes() for c in caminhos]
    maquina_antes = m.carregar_maquina().computador
    fn = pac.gesto_da_pagina(aba, gesto)
    assert fn is not None, f"{aba}·{gesto} sem dono"
    fn(_contexto(pac, "Freestyle"), dict(carga), _Ponte())
    assert [c.read_bytes() for c in caminhos] == antes, f"{aba}·{gesto} mudou um perfil"
    assert m.carregar_maquina().computador != maquina_antes, (
        f"{aba}·{gesto} não chegou ao maquina.json")


def test_os_sem_dono_so_diminuem() -> None:
    """Todo gesto das dez tem atendente: a lista dos sem dono está VAZIA (08/10/2026).

    O da fita (``monta.GESTO_DA_FITA``) é atendido pelo piloto, que o registra
    ao subir. MORDIDA: um ``data-gesto`` novo sem atendente reprova (*«tudo na
    interface deveria funcionar»*), e uma entrada nova no ``SEM_GESTO`` também:
    não há mais lista permitida, o botão ganha dono ou sai do desenho.
    """
    pac = _pacotes()
    import monta

    declarados = set(pac.a06_navegacao.SEM_GESTO) | set(pac.a08_conexoes.SEM_GESTO)
    assert not declarados, f"gesto declarado sem dono: {sorted(declarados)}"
    sem_atendente = sorted(
        f"{p}·{g}" for p, g in _vistos()
        if pac.gesto_da_pagina(p, g) is None
        and g not in declarados and g != monta.GESTO_DA_FITA)
    assert not sem_atendente, f"gesto sem atendente e sem declaração: {sem_atendente}"
