#!/usr/bin/env python3
"""A RÉGUA DA A-ABA-GATILHOS-DIZ-O-QUE-VAI-AO-CONTROLE-01: a coluna diz o que o controle recebe."""
from __future__ import annotations

import json
import pathlib
import sys
from collections.abc import Callable, Iterator
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "03-gatilhos.html"
LADOS = {"e": "left", "d": "right"}

MACS = {1: "aa:bb:cc:00:00:01", 2: "aa:bb:cc:00:00:02",
        3: "aa:bb:cc:00:00:03", 4: "aa:bb:cc:00:00:04"}
TRANSPORTE = {1: "usb", 2: "usb", 3: "bt", 4: "bt"}

JOGO = {"type": "criteria", "window_class": ["steam_app_1599660"]}
TODOS = {"type": "any"}
MANUAL = {"type": "manual"}


Disco = Callable[[str], str]


def _perfil(nome: str, match: dict[str, Any], **resto: Any) -> dict[str, Any]:
    return {"name": nome, "version": 1, "priority": 50, "match": match, **resto}


PERFIS = {
    "jogo-sem-secao": _perfil("Sackboy", JOGO),
    "todos-sem-secao": _perfil("Qualquer Janela", TODOS),
    "manual-sem-secao": _perfil("Na Mão", MANUAL),
    "so-o-l2": _perfil("L2 Escrito", MANUAL, triggers={
        "left": {"mode": "PulseA", "params": [2, 7, 180]}}),
    "so-o-r2": _perfil("R2 Escrito", JOGO, triggers={
        "right": {"mode": "Vibration", "params": [3, 8, 20]}}),
    "um-controle-so": _perfil("Meio", MANUAL, triggers={
        "left": {"mode": "PulseA", "params": [2, 7, 180]}},
        controllers={
            "aabbcc000003": {"triggers": {
                "right": {"mode": "Vibration", "params": [3, 8, 20]}}},
            "aa:bb:cc:00:00:04": {"triggers": {
                "left": {"mode": "Off", "params": []}}}}),
    "off-escrito": _perfil("Escrito", JOGO, triggers={
        "left": {"mode": "Off", "params": []},
        "right": {"mode": "Vibration", "params": [3, 8, 20]}}),
}


def _controle(n: int, grafia: str) -> dict[str, Any]:
    """Um controle com a forma do `state_full`. A grafia do `uniq` é a pergunta.

    `doze-hexa` é a do daemon real — `describe_controllers` publica o
    `norm_mac`; `dois-pontos` é a da régua da casa. A aba tem de acertar nas
    duas.
    """
    mac = MACS[n]
    return {
        "uniq": mac.replace(":", "") if grafia == "doze-hexa" else mac,
        "player": n, "player_slot": n, "index": n - 1, "connected": True,
        "is_primary": n == 1, "battery_pct": 80, "transport": TRANSPORTE[n],
        "vpad_backend": "uhid",
        "inputs": {"lx": 128, "ly": 128, "rx": 128, "ry": 128,
                   "l2_raw": 0, "r2_raw": 0, "buttons": []},
    }


@pytest.fixture(autouse=True)
def _rascunho_limpo() -> Iterator[None]:
    """O rascunho da aba é estado de MÓDULO: nenhum teste herda o de outro."""
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield
    a03_gatilhos.esquecer_o_rascunho()


@pytest.fixture
def disco() -> Disco:
    """A pasta de perfis do lar de mentira que o `conftest` já isola."""
    from hefesto_dualsense4unix.profiles.slug import slugify
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    pasta = profiles_dir(ensure=True)

    def gravar(chave: str) -> str:
        cru = PERFIS[chave]
        (pasta / f"{slugify(str(cru['name']))}.json").write_text(
            json.dumps(cru), encoding="utf-8")
        return str(cru["name"])

    return gravar


def _ctx(nome: str | None, grafia: str = "doze-hexa",
         alvo: int | None = None) -> Any:
    """O `Contexto` do tique, montado como o piloto o monta (`_contexto`)."""
    import mesa_viva
    from pacotes import Contexto

    controles = [_controle(n, grafia) for n in (1, 2, 3, 4)]
    state: dict[str, Any] = {"controllers": controles,
                             "output_target_index": alvo, "active_profile": nome}
    conectados = [c for c in controles if c.get("connected", True)]
    return Contexto(state=state, mesa=mesa_viva.mesa_do_estado(state, {}),
                    conectados=conectados, estados={})


class _Camadas:
    """O backend de mentira: grava as duas camadas que a ativação publica."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.core.controller import OutputSpec
        from hefesto_dualsense4unix.testing.fake_controller import FakeController

        class Gravador(FakeController):
            def __init__(self) -> None:
                super().__init__()
                self.padrao = OutputSpec()
                self.do_perfil: dict[str, Any] = {}

            def apply_output_defaults(self, spec: Any) -> Any:
                self.padrao = spec
                return "escreveu"

            def reset_profile_overrides(self, overrides: Any,
                                        procedencias: Any = None) -> None:
                self.do_perfil = dict(overrides or {})

        self.controlador = Gravador()

    def efetivo(self, mac: str, disco: str) -> Any:
        campo = f"trigger_{disco}"
        dele = self.controlador.do_perfil.get(mac.replace(":", "").lower())
        if dele is not None and getattr(dele, campo) is not None:
            return getattr(dele, campo)
        return getattr(self.controlador.padrao, campo)


def _o_que_o_daemon_manda(nome: str) -> _Camadas:
    """O perfil lido e aplicado pelo código do DAEMON — o oráculo desta régua."""
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    camadas = _Camadas()
    ProfileManager(controller=camadas.controlador).apply(
        loader.load_profile(nome), origin="auto", relatorio={})
    return camadas


def _o_que_a_coluna_diz(r: dict[str, Any], uniq: str,
                        sig: str) -> tuple[str, str, list[int] | None]:
    """`(rótulo, modo, ajustes)` de um lado, lidos do que a página recebe."""
    col = r["colunas"][uniq]
    ajustes = _o_que_a_imersao_diz(col, sig)
    return str(col[f"modo-{sig}"]), str(col[f"modo-chave-{sig}"]), ajustes


def _o_que_a_imersao_diz(col: dict[str, Any], sig: str) -> list[int] | None:
    """Na página do todo os números não aparecem: quem os diz é o modo e a imersão da coluna.

    Campo da imersão em branco é perfil com números próprios: a tela não afirma número nenhum, e
    a régua confere só o modo (`None`).
    """
    from pacotes import a03_gatilhos

    modo, imersao = str(col[f"modo-chave-{sig}"]), str(col[f"imersao-{sig}"])
    if imersao == a03_gatilhos.SEM_IMERSAO:
        return a03_gatilhos._padroes(modo)
    if imersao == "":
        return None
    achada = a03_gatilhos._imersoes().POR_CHAVE.get(imersao)
    assert achada is not None, f"a coluna diz a imersão {imersao!r}, que a lista não tem"
    return a03_gatilhos._params_da_imersao(achada, modo, "") or []


def _conferir(nome: str, ctx: Any) -> list[str]:
    """As linhas em que a coluna MENTE — lista vazia quando as oito casam."""
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name
    from pacotes import pacote_da_pagina
    from pacotes.a03_gatilhos import _padroes as a03_padroes

    r = pacote_da_pagina(PAGINA, ctx)
    assert r is not None
    manda = _o_que_o_daemon_manda(nome)
    mentiras = []
    for c in ctx.conectados:
        uniq = str(c["uniq"])
        for sig, disco in LADOS.items():
            rotulo, modo, ajustes = _o_que_a_coluna_diz(r, uniq, sig)
            vai = manda.efetivo(uniq, disco)
            if ajustes is None:
                diz = build_from_name(modo, a03_padroes(modo))
                casa = type(diz) is type(vai)
            else:
                diz = build_from_name(modo, ajustes)
                casa = diz == vai
            if not casa:
                mentiras.append(
                    f"P{c['player']} ({c['transport'].upper()}) "
                    f"{'L2' if sig == 'e' else 'R2'}: a coluna diz «{rotulo}» "
                    f"{ajustes} e o controle recebe {vai}")
    return mentiras


@pytest.mark.parametrize("alvo", [None, 1], ids=["fita-em-todos", "fita-no-p2"])
@pytest.mark.parametrize("grafia", ["doze-hexa", "dois-pontos"])
@pytest.mark.parametrize("caso", list(PERFIS))
def test_a_coluna_diz_o_que_o_controle_recebe(disco: Disco, caso: str, grafia: str,
                                              alvo: int | None) -> None:
    """Os oito lados da mesa, em cada perfil da matriz, casam com o daemon."""
    nome = disco(caso)
    mentiras = _conferir(nome, _ctx(nome, grafia, alvo))
    assert not mentiras, (
        f"com o perfil {nome!r} ({caso}) a aba mente sobre o gatilho em "
        f"{len(mentiras)} de 8 lados:\n  " + "\n  ".join(mentiras))


def test_o_nascimento_e_perguntado_ao_esquema(disco: Disco,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    """Se o nascimento mudar no esquema, a aba muda junto — ela não o digita."""
    from hefesto_dualsense4unix.profiles import schema

    monkeypatch.setattr(schema, "MODO_DE_NASCIMENTO_DO_GATILHO", "Feedback")
    monkeypatch.setattr(schema, "PARAMS_DE_NASCIMENTO_DO_GATILHO", [5, 4])
    nome = disco("jogo-sem-secao")
    mentiras = _conferir(nome, _ctx(nome))
    assert not mentiras, (
        "o nascimento do gatilho mudou no esquema e a aba não acompanhou — ela "
        "está digitando o modo em vez de perguntar ao dono:\n  "
        + "\n  ".join(mentiras))


def test_o_efeito_pronto_le_o_mesmo_modo_da_coluna(disco: Disco) -> None:
    """`_modo_de_agora` é quem escolhe a lista do «Efeito pronto» nos gestos."""
    from pacotes import a03_gatilhos, pacote_da_pagina

    for caso in ("jogo-sem-secao", "so-o-l2", "um-controle-so"):
        nome = disco(caso)
        ctx = _ctx(nome)
        r = pacote_da_pagina(PAGINA, ctx)
        assert r is not None
        for c in ctx.conectados:
            uniq = str(c["uniq"])
            for sig, disco_ in LADOS.items():
                coluna = r["colunas"][uniq][f"modo-chave-{sig}"]
                gesto = a03_gatilhos._modo_de_agora(ctx, uniq, disco_)
                assert gesto == coluna, (
                    f"{caso}, P{c['player']} {disco_}: a coluna diz {coluna!r} e "
                    f"o «Efeito pronto» monta a lista de {gesto!r}")


def test_sem_perfil_nenhum_a_coluna_nao_inventa_o_nascimento() -> None:
    """Sem perfil valendo, nenhum perfil mandou gatilho, e a coluna não inventa um."""
    from pacotes import pacote_da_pagina

    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    ctx = _ctx(None)
    r = pacote_da_pagina(PAGINA, ctx)
    assert r is not None
    sem_efeito = build_from_name("Off", [])
    for c in ctx.conectados:
        uniq = str(c["uniq"])
        for sig in LADOS:
            rotulo, modo, ajustes = _o_que_a_coluna_diz(r, uniq, sig)
            assert build_from_name(modo, ajustes) == sem_efeito, (
                f"sem perfil nenhum, a coluna do P{c['player']} diz «{rotulo}» "
                f"{ajustes} num gatilho que perfil nenhum escreveu")
