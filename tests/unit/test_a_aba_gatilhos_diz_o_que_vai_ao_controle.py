#!/usr/bin/env python3
"""A RÉGUA DA A-ABA-GATILHOS-DIZ-O-QUE-VAI-AO-CONTROLE-01: a coluna diz o que o controle recebe.

O DEFEITO, achado na conferência da O-MODO-FREESTYLE-03 e medido pelo clique no
piloto (24/09/2026): com um perfil de jogo sem a seção `triggers`, a aba 03
dizia «Desligado» nos dois lados dos quatro controles, e o daemon mandava a
eles o nascimento do esquema — «Rígido». O `or {}` da pintura virava `Off`; o
esquema lê a mesma ausência como `TriggersConfig()` (NASCE-LIGADO-01). E a
mentira passava da tela para o disco: o «Guardar» lê a coluna, e gravou `Off`
nos dois lados do override do P2.

A MEDIÇÃO ACHOU UMA SEGUNDA, da mesma família: o override de um controle era
procurado pelo `uniq` cru. O esquema aceita a chave em qualquer grafia e a
canoniza ao carregar, então o daemon aplicava um override que a aba não via.

O ORÁCULO É O DAEMON, e não um número digitado. O perfil vai para o disco de
mentira que o `conftest` já isola, é carregado pelo `loader` real e aplicado
pelo `ProfileManager.apply` real sobre um backend que só grava as duas camadas
que recebe. O efeito de cada controle é o merge por campo do backend. A coluna
CASA quando `build_from_name(modo da coluna, ajustes da coluna)` é o MESMO
`TriggerEffect` que vai ao controle.

A MATRIZ: P1 a P4, dois no USB e dois no BT; o `uniq` na grafia do daemon real
(doze hexa) e na da régua da casa (`aa:bb:…`); a fita em «Todos» e num controle
só; perfil de jogo, «Todos» e manual; o L2 e o R2; o perfil que traz só um
lado; o override de um controle só, com a chave canônica e com a editada à mão;
e o `Off` ESCRITO, que tem de continuar `Off`.

A MORDIDA, arrancada antes deste arquivo entrar: com
`_o_lado_que_o_perfil_cala` devolvendo `{}`, os casos sem seção reprovam com
«Desligado»; com `_chave_no_perfil` devolvendo o `uniq` cru, o override de
chave editada à mão reprova; com o perfil nenhum devolvendo o nascimento, a
régua do perfil nenhum reprova.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "03-gatilhos.html"
LADOS = {"e": "left", "d": "right"}

#: A MESA DA MATRIZ: P1 e P2 no USB, P3 e P4 no BT. MACs da faixa sintética da
#: casa — há dois portões de anonimato nesta árvore e eles não perdoam.
MACS = {1: "aa:bb:cc:00:00:01", 2: "aa:bb:cc:00:00:02",
        3: "aa:bb:cc:00:00:03", 4: "aa:bb:cc:00:00:04"}
TRANSPORTE = {1: "usb", 2: "usb", 3: "bt", 4: "bt"}

#: O JOGO, O «TODOS» E O MANUAL — as três regras de casamento que a aba Perfis
#: oferece. Nenhuma das três traz a seção `triggers`.
JOGO = {"type": "criteria", "window_class": ["steam_app_1599660"]}
TODOS = {"type": "any"}
MANUAL = {"type": "manual"}


def _perfil(nome: str, match: dict[str, Any], **resto: Any) -> dict[str, Any]:
    return {"name": nome, "version": 1, "priority": 50, "match": match, **resto}


#: OS PERFIS DA MATRIZ, na forma do disco. Os modos que não são o nascimento
#: estão escritos por extenso DE PROPÓSITO: eles são o que o perfil DIZ, e o
#: oráculo não é esta tabela — é o daemon lendo o arquivo.
PERFIS = {
    "jogo-sem-secao": _perfil("Sackboy", JOGO),
    "todos-sem-secao": _perfil("Qualquer Janela", TODOS),
    "manual-sem-secao": _perfil("Na Mão", MANUAL),
    "so-o-l2": _perfil("L2 Escrito", MANUAL, triggers={
        "left": {"mode": "PulseA", "params": [2, 7, 180]}}),
    "so-o-r2": _perfil("R2 Escrito", JOGO, triggers={
        "right": {"mode": "Vibration", "params": [3, 8, 20]}}),
    # O P3 é dono do R2 (chave canônica) e o P4 de um L2 `Off` ESCRITO, com a
    # chave na grafia de quem edita o JSON à mão — o esquema a canoniza ao
    # carregar, e o daemon aplica o override.
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
def _rascunho_limpo():
    """O rascunho da aba é estado de MÓDULO: nenhum teste herda o de outro."""
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield
    a03_gatilhos.esquecer_o_rascunho()


@pytest.fixture
def disco():
    """A pasta de perfis do lar de mentira que o `conftest` já isola.

    É a MESMA para os dois leitores: `pacotes.perfil.pasta()` e o `loader`
    perguntam a `xdg_paths.profiles_dir()` na chamada.
    """
    from hefesto_dualsense4unix.profiles.slug import slugify
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    pasta = profiles_dir(ensure=True)

    def gravar(chave: str) -> str:
        cru = PERFIS[chave]
        (pasta / f"{slugify(str(cru['name']))}.json").write_text(
            json.dumps(cru), encoding="utf-8")
        return str(cru["name"])

    return gravar


def _ctx(nome: str | None, grafia: str = "doze-hexa", alvo: int | None = None):
    """O `Contexto` do tique, montado como o piloto o monta (`_contexto`)."""
    import mesa_viva
    from pacotes import Contexto

    state = {"controllers": [_controle(n, grafia) for n in (1, 2, 3, 4)],
             "output_target_index": alvo, "active_profile": nome}
    conectados = [c for c in state["controllers"] if c.get("connected", True)]
    return Contexto(state=state, mesa=mesa_viva.mesa_do_estado(state, {}),
                    conectados=conectados, estados={})


class _Camadas:
    """O backend de mentira: grava as duas camadas que a ativação publica.

    `efetivo` é o `_merge_desired` do backend real, reduzido ao gatilho: o campo
    do override quando não-None, senão o do padrão — nunca resolução por objeto.
    """

    def __init__(self) -> None:
        from hefesto_dualsense4unix.core.controller import OutputSpec
        from hefesto_dualsense4unix.testing.fake_controller import FakeController

        class Gravador(FakeController):
            def __init__(self) -> None:
                super().__init__()
                self.padrao = OutputSpec()
                self.do_perfil: dict[str, Any] = {}

            def apply_output_defaults(self, spec):  # type: ignore[override]
                self.padrao = spec
                return "escreveu"

            def reset_profile_overrides(self, overrides, procedencias=None):
                self.do_perfil = dict(overrides or {})

        self.controlador = Gravador()

    def efetivo(self, mac: str, disco: str):
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


def _o_que_a_coluna_diz(r: dict[str, Any], uniq: str, pref: str,
                        sig: str) -> tuple[str, str, list[int]]:
    """`(rótulo, modo, ajustes)` de um lado, lidos do que a página recebe.

    O modo é o `modo-chave-<lado>` que pousa no `<select>`; os ajustes são os
    `aj-val-<lado>-<i>` da caixa que o bloco troca — a mesma leitura que o
    piloto faz para o «Guardar».
    """
    col = r["colunas"][uniq]
    caixa = r["blocos"][f'[data-controle="{pref}"] .ajustes.{sig}']
    ajustes = [int(v) for v in re.findall(
        rf'data-campo="aj-val-{sig}-\d+">(-?\d+)<', caixa)]
    return str(col[f"modo-{sig}"]), str(col[f"modo-chave-{sig}"]), ajustes


def _conferir(nome: str, ctx) -> list[str]:
    """As linhas em que a coluna MENTE — lista vazia quando as oito casam."""
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name
    from pacotes import pacote_da_pagina

    r = pacote_da_pagina(PAGINA, ctx)
    assert r is not None
    manda = _o_que_o_daemon_manda(nome)
    pref_de = {str(m["uniq"]): str(m["pref"]) for m in ctx.mesa}
    mentiras = []
    for c in ctx.conectados:
        uniq = str(c["uniq"])
        for sig, disco in LADOS.items():
            rotulo, modo, ajustes = _o_que_a_coluna_diz(r, uniq, pref_de[uniq], sig)
            vai = manda.efetivo(uniq, disco)
            diz = build_from_name(modo, ajustes)
            if diz != vai:
                mentiras.append(
                    f"P{c['player']} ({c['transport'].upper()}) "
                    f"{'L2' if sig == 'e' else 'R2'}: a coluna diz «{rotulo}» "
                    f"{ajustes} e o controle recebe {vai}")
    return mentiras


@pytest.mark.parametrize("alvo", [None, 1], ids=["fita-em-todos", "fita-no-p2"])
@pytest.mark.parametrize("grafia", ["doze-hexa", "dois-pontos"])
@pytest.mark.parametrize("caso", list(PERFIS))
def test_a_coluna_diz_o_que_o_controle_recebe(disco, caso, grafia, alvo) -> None:
    """Os oito lados da mesa, em cada perfil da matriz, casam com o daemon."""
    nome = disco(caso)
    mentiras = _conferir(nome, _ctx(nome, grafia, alvo))
    assert not mentiras, (
        f"com o perfil {nome!r} ({caso}) a aba mente sobre o gatilho em "
        f"{len(mentiras)} de 8 lados:\n  " + "\n  ".join(mentiras))


def test_o_nascimento_e_perguntado_ao_esquema(disco, monkeypatch) -> None:
    """Se o nascimento mudar no esquema, a aba muda junto — ela não o digita.

    O nascimento é trocado para `Feedback [5, 4]` no dono
    (`schema.MODO_DE_NASCIMENTO_DO_GATILHO`), e o oráculo o lê de lá também.
    Uma aba com `Rigid` ou `[5, 200]` escrito à mão reprova aqui mesmo com a
    régua de cima verde.
    """
    from hefesto_dualsense4unix.profiles import schema

    monkeypatch.setattr(schema, "MODO_DE_NASCIMENTO_DO_GATILHO", "Feedback")
    monkeypatch.setattr(schema, "PARAMS_DE_NASCIMENTO_DO_GATILHO", [5, 4])
    nome = disco("jogo-sem-secao")
    mentiras = _conferir(nome, _ctx(nome))
    assert not mentiras, (
        "o nascimento do gatilho mudou no esquema e a aba não acompanhou — ela "
        "está digitando o modo em vez de perguntar ao dono:\n  "
        + "\n  ".join(mentiras))


def test_o_efeito_pronto_le_o_mesmo_modo_da_coluna(disco) -> None:
    """`_modo_de_agora` é quem escolhe a lista do «Efeito pronto» nos gestos.

    Ele tinha a ordem escrita por conta própria, e com ela os dois defeitos da
    pintura. Agora ele e a coluna perguntam à mesma função — e têm de dizer o
    mesmo modo, lado a lado, nos quatro controles.
    """
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


class _Ponte:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(metodo)
        return True


def test_o_guardar_nao_troca_o_gatilho_do_controle_por_off(disco) -> None:
    """O «Guardar» lê a COLUNA — e a coluna que mentia gravava a mentira.

    Medido no piloto antes da cura: com o Sackboy ativo, o «Guardar» do P2
    gravou `Off` nos dois lados do override dele, e na ativação seguinte o P2
    perdia o gatilho que o perfil dava. Aqui a coluna é recolhida como o piloto
    a recolhe (o `modo-chave-*` e os `aj-val-*`), o gesto grava no disco de
    verdade, e o daemon relê o arquivo: o P2 tem de continuar recebendo o que
    recebia.
    """
    from pacotes import gesto_da_pagina, pacote_da_pagina

    nome = disco("jogo-sem-secao")
    ctx = _ctx(nome)
    r = pacote_da_pagina(PAGINA, ctx)
    assert r is not None
    p2 = next(c for c in ctx.conectados if c["player"] == 2)
    uniq = str(p2["uniq"])
    forma: dict[str, str] = {"nome-do-efeito": ""}
    for sig in LADOS:
        _rotulo, modo, ajustes = _o_que_a_coluna_diz(r, uniq, "p2", sig)
        forma[f"modo-chave-{sig}"] = modo
        forma.update({f"aj-val-{sig}-{i}": str(v) for i, v in enumerate(ajustes)})
    antes = _o_que_o_daemon_manda(nome)

    guardar = gesto_da_pagina(PAGINA, "guardar")
    assert guardar is not None
    guardar(ctx, {"uniq": uniq, "controle": "p2", "forma": forma}, _Ponte())

    depois = _o_que_o_daemon_manda(nome)
    for disco_ in LADOS.values():
        assert depois.efetivo(uniq, disco_) == antes.efetivo(uniq, disco_), (
            f"o «Guardar» do P2 trocou o {disco_} que o controle recebia "
            f"({antes.efetivo(uniq, disco_)}) por {depois.efetivo(uniq, disco_)} — "
            f"a coluna gravou o que dizia, e o que ela dizia era {forma}")


class _PonteDoBroadcast(_Ponte):
    """A ponte do «Em todos»: aceita o envio e anota o efeito de cada lado."""

    def __init__(self) -> None:
        super().__init__()
        self.saiu: dict[str, Any] = {}

    def trigger_set_detalhado(self, lado: str, modo: str, params: list[int],
                              uniq: str | None = None) -> bool:
        from hefesto_dualsense4unix.core.trigger_effects import build_from_name

        self.saiu[lado] = build_from_name(modo, params)
        return True

    def trigger_reset_detalhado(self, lado: str, uniq: str | None = None) -> bool:
        from hefesto_dualsense4unix.core.trigger_effects import build_from_name

        self.saiu[lado] = build_from_name("Off", [])
        return True


def test_o_em_todos_nao_espalha_o_lado_que_ela_nao_tocou(disco) -> None:
    """O «Em todos» também lê a COLUNA, e o alcance dele é a mesa inteira.

    Ele recolhe os dois lados da coluna, manda os dois em broadcast e grava os
    dois na seção global. Com a coluna dizendo «Desligado» no lado que o perfil
    cala, trocar só o L2 do P1 tirava o «Rígido» de nascimento do R2 dos QUATRO
    controles, no aparelho e no perfil. Aqui ela troca só o L2, a coluna é
    recolhida como o piloto a recolhe, e o R2 que sai no fio e o que o daemon
    relê do disco têm de ser o que eram.
    """
    from pacotes import gesto_da_pagina, pacote_da_pagina
    from pacotes.a03_gatilhos import GESTO_DE_TODOS

    from hefesto_dualsense4unix.profiles.schema import TriggersConfig

    nome = disco("jogo-sem-secao")
    ctx = _ctx(nome)
    r = pacote_da_pagina(PAGINA, ctx)
    assert r is not None
    uniq = str(next(c for c in ctx.conectados if c["player"] == 1)["uniq"])
    # O MODO NOVO NÃO É O NASCIMENTO: com ele o gesto não teria o que gravar, e
    # a régua mediria um clique que o produto, com razão, ignora.
    novo = "Pulse"
    assert TriggersConfig().left.mode != novo
    forma: dict[str, str] = {"nome-do-efeito": ""}
    for sig in LADOS:
        _rotulo, modo, ajustes = _o_que_a_coluna_diz(r, uniq, "p1", sig)
        forma[f"modo-chave-{sig}"] = modo
        forma.update({f"aj-val-{sig}-{i}": str(v) for i, v in enumerate(ajustes)})
    # ELA TROCA SÓ O L2: a caixa dele passa a ser a do modo novo, nos padrões.
    forma = {k: v for k, v in forma.items() if not k.startswith("aj-val-e-")}
    forma["modo-chave-e"] = novo
    antes = _o_que_o_daemon_manda(nome)

    em_todos = gesto_da_pagina(PAGINA, GESTO_DE_TODOS)
    assert em_todos is not None
    ponte = _PonteDoBroadcast()
    em_todos(ctx, {"uniq": uniq, "controle": "p1", "forma": forma}, ponte)

    depois = _o_que_o_daemon_manda(nome)
    for c in ctx.conectados:
        u = str(c["uniq"])
        era = antes.efetivo(u, "right")
        assert ponte.saiu.get("right", era) == era, (
            f"o «Em todos» do P1 mandou ao R2 do P{c['player']} "
            f"{ponte.saiu.get('right')} no lugar de {era} — a coluna dizia {forma}")
        assert depois.efetivo(u, "right") == era, (
            f"o «Em todos» do P1 gravou no perfil um R2 que tira do "
            f"P{c['player']} o {era} que ele recebia: {depois.efetivo(u, 'right')}")
        assert depois.efetivo(u, "left") != antes.efetivo(u, "left"), (
            "o L2 não mudou: o gesto não gravou nada e esta régua não mediu o "
            "lado que ela não tocou")


def test_sem_perfil_nenhum_a_coluna_nao_inventa_o_nascimento() -> None:
    """Sem perfil valendo, nenhum perfil mandou gatilho, e a coluna não inventa um.

    O nascimento é o que o esquema põe no perfil que CALA a seção; sem perfil
    não há seção calada, e o daemon não escreveu gatilho nenhum. Com o daemon
    respondendo `active_profile: null` e o disco sem marcador, os oito lados
    dizem o estado sem efeito, e não o «Rígido» que só um perfil manda.
    """
    from pacotes import pacote_da_pagina

    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    ctx = _ctx(None)
    r = pacote_da_pagina(PAGINA, ctx)
    assert r is not None
    pref_de = {str(m["uniq"]): str(m["pref"]) for m in ctx.mesa}
    sem_efeito = build_from_name("Off", [])
    for c in ctx.conectados:
        uniq = str(c["uniq"])
        for sig in LADOS:
            rotulo, modo, ajustes = _o_que_a_coluna_diz(r, uniq, pref_de[uniq], sig)
            assert build_from_name(modo, ajustes) == sem_efeito, (
                f"sem perfil nenhum, a coluna do P{c['player']} diz «{rotulo}» "
                f"{ajustes} num gatilho que perfil nenhum escreveu")
