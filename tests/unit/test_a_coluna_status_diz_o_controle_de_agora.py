"""A coluna «Status» da aba Perfis diz o controle de agora, e o ponto diz o disco.

A-ABA-PERFIS-DIZ-O-STATUS-DE-AGORA-01 (02/10/2026). A queixa dela de 29/09,
com os quatro DualSense na mesa: *«alguns estão acesos e outros não. E pora
piorar não refletem o stauts real daquele momento do controle. parece
aleatório.»* <!-- noqa-acento: citação literal dela -->

O DEFEITO, MEDIDO: o glifo acendia com o que o PERFIL ABERTO NO EDITOR guarda
só para aquele controle (`perfis_web._secoes_do_controle`), e nada na coluna
lia o controle. Clicar noutro perfil da lista trocava os glifos das quatro
linhas com os controles parados.

A CURA (decidida por ela em 29/09, «Ponto embaixo» e «Aceso no DualSense"): o
glifo (`guarda.secao`) sai da entrada viva de cada controle, pelos donos que a
aba Controles já lê; o «só deste controle» vira o ponto embaixo
(`guarda.proprio`); o que o dono não responde fica no «não sei»
(`guarda.incerto`, com a dica em `guarda.dica`).

AS RÉGUAS (a numeração é a da sprint):

1. o agora vem do controle, não do perfil (quatro controles, cada um com uma
   combinação, e um perfil que guarda tudo dos quatro);
2. trocar o perfil do editor não mexe no agora, e mexe no ponto;
3. o «não sei» não acende nem apaga;
4. o ponto é o disco inteiro (`ControllerOverrides.model_fields`);
5. na tela (WebKit), o ponto e o glifo aceso são geometrias diferentes;
6. na tela, os oito grupos cabem na célula.

AS MORDIDAS estão no relato da entrega: `guarda.secao` de volta ao disco (1 e
2 reprovam nomeando a seção), o `None` do alto-falante virando apagado (3), o
ponto escondido no CSS (5) e o vão de 11 px de volta (6).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.interface.cartao_do_controle import (
    rotulo_lightbar,
    speaker_do_entry,
)
from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.interface import mesa_viva, onde
from hefesto_dualsense4unix.interface.pacotes import (
    TRAVESSAO,
    Contexto,
    a02_controles,
    a04_iluminacao,
    a05_vibracao,
    a10_perfis,
)
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]

UNIQS = ["aabbcc000011", "aabbcc000012", "aabbcc000013", "aabbcc000014"]

MENOR_CORPO: dict[str, Any] = {
    "leds": {}, "triggers": {}, "rumble": {}, "speaker": {"volume": 40},
    "mic": {}, "sensores": {}, "mascara": "xbox", "movimento": {},
}


def _entrada(uniq: str, jogador: int, **troca: Any) -> dict[str, Any]:
    """Uma entrada do `state_full` com tudo ligado; `troca` desliga o que pede."""
    base: dict[str, Any] = {
        "uniq": uniq, "connected": True, "player": jogador, "player_slot": jogador,
        "transport": "bt" if jogador > 1 else "usb",
        "lightbar_rgb": [0, 0, 255], "lightbar_on": True, "lightbar_source": "desired",
        "speaker": {"volume": 102, "muted": False},
        "audio": {"mic_mudo": False, "mic_mudo_desejado": None,
                  "canal_ativo": True, "canal_mudo": False},
        "sensores": {"giroscopio_ligado": True, "acelerometro_ligado": True},
        "mira": {"ligada": False, "toque": rot.DESTINO_NENHUM,
                 "inclinacao": rot.DESTINO_NENHUM},
    }
    for chave, valor in troca.items():
        if valor is None:
            base.pop(chave, None)
        elif isinstance(valor, dict) and isinstance(base.get(chave), dict):
            base[chave] = {**base[chave], **valor}
        else:
            base[chave] = valor
    return base


def _estado(*entradas: dict[str, Any]) -> dict[str, Any]:
    """O `state_full` dos quatro: P3 joga como Xbox, e os motores de cada um."""
    return {
        "active_profile": "Régua A",
        "controllers": list(entradas),
        "gamepad_emulation": {"flavor": "dualsense",
                              "por_aparelho": {UNIQS[2]: "xbox"}},
        "rumble_motor_pct_padrao": 100,
        "rumble_motores": {UNIQS[0]: {"forte_pct": 0, "fraco_pct": 0}},
    }


def _o_cenario() -> dict[str, Any]:
    """P1 com o microfone mudo, P2 com a barra apagada, P3 com a máscara Xbox,"""
    return _estado(
        _entrada(UNIQS[0], 1, audio={"mic_mudo": True}),
        _entrada(UNIQS[1], 2, lightbar_on=False, lightbar_rgb=[0, 0, 0]),
        _entrada(UNIQS[2], 3),
        _entrada(UNIQS[3], 4, mira={"ligada": True,
                                    "toque": rot.DESTINO_NENHUM,
                                    "inclinacao": rot.DESTINO_NENHUM}),
    )


def _perfil(nome: str, secoes: list[str]) -> Profile:
    """Um perfil que guarda `secoes` só de cada um dos quatro controles."""
    return Profile(name=nome, match=MatchAny(), controllers={
        uniq: ControllerOverrides(**{s: MENOR_CORPO[s] for s in secoes})
        for uniq in UNIQS})


TUDO = list(perfis_web.SECOES_POR_CONTROLE)


def _emitidos(monkeypatch: pytest.MonkeyPatch, state: dict[str, Any],
              perfis: list[Profile], editado: str = "") -> dict[str, Any]:
    """O que `a10_perfis.pacote()` manda pintar, com a mesa do `mesa_viva`."""
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: list(perfis))
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", editado, raising=False)
    mesa = mesa_viva.mesa_do_estado(state, {})
    conectados = [c for c in state.get("controllers") or [] if c.get("connected")]
    return a10_perfis.pacote(Contexto(state=state, mesa=mesa, conectados=conectados,
                                      estados={}))


def _por_linha(lista: list[Any]) -> list[dict[str, Any]]:
    """A lista achatada de volta em linhas, `{seção: valor}`."""
    largura = len(a10_perfis.SECOES_DA_COLUNA)
    return [dict(zip(a10_perfis.SECOES_DA_COLUNA, lista[i:i + largura], strict=True))
            for i in range(0, len(lista), largura)]


def _o_dono_diz(secao: str, entrada: dict[str, Any], state: dict[str, Any],
                mascara: str) -> bool | None:
    """O que o DONO responde para aquela seção, chamado sobre a mesma entrada."""
    if secao == "leds":
        tira = a04_iluminacao.estado_da_tira(rotulo_lightbar(entrada, state)[0])
        return {a04_iluminacao.ACESA: True, a04_iluminacao.APAGADA: False}.get(tira)
    if secao == "triggers":
        return None
    if secao == "rumble":
        barras = a05_vibracao._barras_dos_motores(state, str(entrada["uniq"]))
        return max(barras.values()) > 0
    if secao == "speaker":
        lido = speaker_do_entry(entrada)
        if lido is None:
            return None
        if lido[1] is True or lido[0] == 0:
            return False
        return None if lido[1] is None else True
    if secao == "mic":
        calado, nao_sei = a02_controles._faces_do_microfone(entrada["audio"])
        return False if calado else (None if nao_sei else True)
    if secao == "sensores":
        lidos = {a02_controles._sensor_ligado(entrada, q)
                 for q in ("giroscopio", "acelerometro")}
        return True if True in lidos else (False if lidos == {False} else None)
    if secao == "mascara":
        return mascara == mesa_viva.NOME_DA_MASCARA["dualsense"]
    if secao == "movimento":
        destinos = {a02_controles._destino_da_mira(entrada, c) for c in ("toque", "inclinacao")}
        return bool(a02_controles._mira_ligada(entrada)) or bool(
            destinos - {None, rot.DESTINO_NENHUM})
    raise AssertionError(f"a seção `{secao}` não tem dono nesta régua")


def _como_a_celula(aceso: bool | None) -> str:
    return TRAVESSAO if aceso is None else ("sim" if aceso else "")


def test_o_glifo_diz_o_que_o_dono_diz_de_cada_controle(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Quatro controles, quatro combinações, e um perfil que guarda TUDO dos"""
    state = _o_cenario()
    fora = _emitidos(monkeypatch, state, [_perfil("Régua A", TUDO)])
    mesa = mesa_viva.mesa_do_estado(state, {})
    linhas = _por_linha(fora["guarda.secao"])
    errados = []
    for n, (entrada, casa) in enumerate(zip(state["controllers"], mesa, strict=True)):
        for secao in a10_perfis.SECOES_DA_COLUNA:
            quer = _como_a_celula(_o_dono_diz(secao, entrada, state, casa["mascara"]))
            if linhas[n][secao] != quer:
                errados.append(f"P{n + 1}/{secao}: tela={linhas[n][secao]!r} dono={quer!r}")
    assert not errados, (
        "a coluna «Status» não diz o que o controle diz:\n  " + "\n  ".join(errados))
    assert linhas[0]["mic"] == "" and linhas[0]["rumble"] == ""
    assert linhas[1]["leds"] == ""
    assert linhas[2]["mascara"] == ""
    assert linhas[3]["movimento"] == "sim"
    assert [linha["triggers"] for linha in linhas] == [TRAVESSAO] * 4


def test_a_dica_diz_qual_mascara_e_o_nao_sei(monkeypatch: pytest.MonkeyPatch) -> None:
    """«Aceso no DualSense», e a dica diz qual (pergunta [40], 29/09)."""
    fora = _emitidos(monkeypatch, _o_cenario(), [_perfil("Régua A", TUDO)])
    dicas = _por_linha(fora["guarda.dica"])
    assert dicas[2]["mascara"] == a10_perfis.DICA_DA_MASCARA.format(
        mascara=mesa_viva.NOME_DA_MASCARA["xbox"])
    assert [dicas[i]["mascara"] for i in (0, 1, 3)] == ["", "", ""]
    assert [d["triggers"] for d in dicas] == [a10_perfis.DICA_DO_NAO_DIZ] * 4
    incertos = _por_linha(fora["guarda.incerto"])
    assert [i["triggers"] for i in incertos] == ["sim"] * 4
    assert all(v == "" for i in incertos for s, v in i.items() if s != "triggers")


def test_trocar_o_perfil_do_editor_muda_o_ponto_e_nao_o_glifo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O clique na lista que ela via trocar a coluna inteira com os controles"""
    state = _o_cenario()
    perfis = [_perfil("Régua A", TUDO), _perfil("Régua B", ["rumble"])]
    com_a = _emitidos(monkeypatch, state, perfis, editado="Régua A")
    com_b = _emitidos(monkeypatch, state, perfis, editado="Régua B")
    for chave in ("guarda.secao", "guarda.incerto", "guarda.dica"):
        assert com_a[chave] == com_b[chave], (
            f"`{chave}` mudou com o perfil do editor — o glifo voltou a ler o disco")
    assert com_a["guarda.proprio"] != com_b["guarda.proprio"]
    pontos_b = _por_linha(com_b["guarda.proprio"])
    assert [{s for s, v in p.items() if v} for p in pontos_b] == [{"rumble"}] * 4


def test_sem_perfil_nenhum_a_coluna_continua_dizendo_o_agora(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O agora não depende de perfil: sem um só para escolher, os quatro"""
    fora = _emitidos(monkeypatch, _o_cenario(), [])
    assert "Desconectado" not in " ".join(fora["guarda.nome"])
    assert _por_linha(fora["guarda.secao"])[3]["movimento"] == "sim"
    assert not any(fora["guarda.proprio"])


@pytest.mark.parametrize(("bloco", "secao"), [
    ("speaker", "speaker"), ("sensores", "sensores"), ("audio", "mic"),
    ("mira", "movimento")])
def test_o_bloco_ausente_fica_no_nao_sei(
        monkeypatch: pytest.MonkeyPatch, bloco: str, secao: str) -> None:
    """Sem o bloco do dono, a célula sai neutra: nem `"sim"` nem `""`."""
    state = _estado(_entrada(UNIQS[0], 1, **{bloco: None}))
    fora = _emitidos(monkeypatch, state, [_perfil("Régua A", TUDO)])
    linha = _por_linha(fora["guarda.secao"])[0]
    assert linha[secao] == TRAVESSAO, (
        f"sem `{bloco}` na entrada, a célula de `{secao}` disse {linha[secao]!r}")
    assert _por_linha(fora["guarda.incerto"])[0][secao] == "sim"


def test_o_controle_que_o_daemon_nao_publica_nao_afirma_nada(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Na mesa e fora da resposta do daemon: as oito células no «não sei»."""
    state = _o_cenario()
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [])
    mesa = mesa_viva.mesa_do_estado(state, {})
    fora = a10_perfis.pacote(Contexto(state=state, mesa=mesa, conectados=[], estados={}))
    assert set(_por_linha(fora["guarda.secao"])[0].values()) == {TRAVESSAO}


def test_o_motor_sem_mapa_nao_vira_o_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    """Daemon sem `rumble_motores`: a força seria o padrão do esquema, e não leitura."""
    state = _o_cenario()
    del state["rumble_motores"]
    fora = _emitidos(monkeypatch, state, [_perfil("Régua A", TUDO)])
    assert {linha["rumble"] for linha in _por_linha(fora["guarda.secao"])} == {TRAVESSAO}


@pytest.mark.parametrize("secao", list(ControllerOverrides.model_fields))
def test_o_ponto_acende_a_secao_guardada_e_so_ela(
        monkeypatch: pytest.MonkeyPatch, secao: str) -> None:
    """Toda seção de `ControllerOverrides` tem célula e acende só a sua."""
    assert secao in MENOR_CORPO, f"o esquema ganhou `{secao}`: monte o corpo mínimo"
    assert secao in a10_perfis.SECOES_DA_COLUNA, (
        f"o perfil guarda `{secao}` por controle e a coluna não tem o ponto dele")
    perfil = Profile(name="Régua A", match=MatchAny(),
                     controllers={UNIQS[1]: ControllerOverrides(**{secao: MENOR_CORPO[secao]})})
    fora = _emitidos(monkeypatch, _o_cenario(), [perfil])
    pontos = [{s for s, v in p.items() if v} for p in _por_linha(fora["guarda.proprio"])]
    assert pontos == [set(), {secao}, set(), set()], pontos


def _gerador() -> Any:
    pasta = pathlib.Path(onde.__file__).parent
    if str(pasta) not in sys.path:
        sys.path.insert(0, str(pasta))
    import aba10  # type: ignore[import-not-found]

    return aba10


def test_o_desenho_e_o_pacote_dizem_as_mesmas_dicas() -> None:
    """O gerador não importa o pacote (ele traz o GTK); a régua confere."""
    aba10 = _gerador()
    assert aba10.DICA_DO_NAO_DIZ == a10_perfis.DICA_DO_NAO_DIZ
    assert aba10.DICA_DA_MASCARA == a10_perfis.DICA_DA_MASCARA
    assert mesa_viva.NOME_DA_MASCARA["dualsense"] == aba10.MASCARA_QUE_ACENDE
    assert aba10.NAO_DIZ == a10_perfis.AGORA_NAO_DIZ
    assert set(a10_perfis.QUEM_DIZ_O_AGORA) == set(a10_perfis.SECOES_DA_COLUNA)


def _bootstrap() -> str:
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto"
    return m.group(1)


@pytest.fixture(scope="module")
def tela() -> Any:
    """A página do gerador num WebView oculto, com a folha e o BOOTSTRAP do produto."""
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    sys.path.insert(0, str(RAIZ / "scripts"))
    import regua_de_tela

    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA

    t = regua_de_tela.Tela(onde.BANCADA / "10-perfis.html", titulo_esperado="Hefesto",
                           largura=1280, altura=900)
    t.executar(
        "(function(){var s=document.createElement('style');"
        f"s.textContent={json.dumps(FOLHA_DA_CASA)};"
        "document.head.appendChild(s);return 'ok';})()")
    t.executar(_bootstrap() + ";'ok'")
    yield t
    t.fechar()


LER_A_COLUNA = r"""
(function(){
  var px = function(r){ return {l: r.left, r: r.right, t: r.top, b: r.bottom,
                                w: r.width, h: r.height}; };
  var linhas = [];
  document.querySelectorAll('tbody[data-hef="guarda.linhas"] tr').forEach(function(tr){
    var td = tr.querySelector('td.gd-pecas');
    var celulas = [];
    tr.querySelectorAll('.gc').forEach(function(gc){
      var gr = gc.querySelector('[data-hef="guarda.secao"]');
      var gq = gc.querySelector('[data-hef="guarda.incerto"]');
      var gp = gc.querySelector('[data-hef="guarda.proprio"]');
      var vgp = getComputedStyle(gp).visibility;
      celulas.push({secao: gr.dataset.hefSecao, aceso: gr.classList.contains('on'),
                    cor: getComputedStyle(gr).color, glifo: px(gq.getBoundingClientRect()),
                    grupo: px(gr.getBoundingClientRect()),
                    ponto: px(gp.getBoundingClientRect()), ponto_visivel: vgp,
                    fundo_do_ponto: getComputedStyle(gp).backgroundColor});
    });
    linhas.push({fora: tr.classList.contains('fora'), td: px(td.getBoundingClientRect()),
                 celulas: celulas});
  });
  return JSON.stringify(linhas);
})()
"""


def _pintar(tela: Any, fora: dict[str, Any]) -> list[dict[str, Any]]:
    carga = {"mesa": {k: fora[k] for k in (
        "guarda.secao", "guarda.incerto", "guarda.dica", "guarda.proprio",
        "guarda.nome", "guarda.vazio")}}
    tela.executar(f"(function(){{window.__hef.pintar({json.dumps(carga)});return 'ok';}})()")
    tela.avancar(0.2)
    return list(json.loads(tela.executar(LER_A_COLUNA)))


def test_o_ponto_e_o_glifo_aceso_sao_coisas_diferentes_na_tela(
        tela: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O ponto só onde o disco diz, embaixo do glifo e dentro da célula; a cor"""
    state = _o_cenario()
    perfil = _perfil("Régua A", ["leds", "mic", "movimento"])
    fora = _emitidos(monkeypatch, state, [perfil])
    linhas = _pintar(tela, fora)
    pontos = _por_linha(fora["guarda.proprio"])
    acesos = _por_linha(fora["guarda.secao"])
    cores_do_aceso: dict[bool, set[str]] = {True: set(), False: set()}
    errados = []
    for n, linha in enumerate(linhas[:len(UNIQS)]):
        for c in linha["celulas"]:
            secao = c["secao"]
            quer_ponto = bool(pontos[n][secao])
            visivel = c["ponto_visivel"] == "visible" and c["ponto"]["w"] > 0
            if visivel != quer_ponto:
                errados.append(f"P{n + 1}/{secao}: ponto {'visível' if visivel else 'ausente'}"
                               f", o disco diz {'guarda' if quer_ponto else 'não guarda'}")
            if c["aceso"] != (acesos[n][secao] == "sim"):
                errados.append(f"P{n + 1}/{secao}: aceso={c['aceso']} pacote="
                               f"{acesos[n][secao]!r}")
            if quer_ponto:
                if c["ponto"]["t"] < c["glifo"]["b"] - 0.5:
                    errados.append(f"P{n + 1}/{secao}: o ponto invade o glifo")
                td = linha["td"]
                if not (td["t"] <= c["ponto"]["t"] and c["ponto"]["b"] <= td["b"]):
                    errados.append(f"P{n + 1}/{secao}: o ponto sai da célula")
            if c["aceso"]:
                cores_do_aceso[quer_ponto].add(c["cor"])
    assert not errados, "\n".join(errados)
    assert cores_do_aceso[True] and cores_do_aceso[False], (
        "o cenário não tem aceso com ponto E aceso sem ponto — a régua não compara nada")
    assert cores_do_aceso[True] == cores_do_aceso[False], (
        f"a cor do aceso muda com o ponto: {cores_do_aceso}")


def test_as_oito_secoes_cabem_na_celula(tela: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A foto dela tinha o oitavo grupo inteiro fora da célula, nas quatro linhas."""
    aba10 = _gerador()
    fora = _emitidos(monkeypatch, _o_cenario(), [_perfil("Régua A", TUDO)])
    linhas = _pintar(tela, fora)
    assert len(linhas) == a10_perfis.LUGARES_DA_TABELA
    fora_da_celula = []
    for n, linha in enumerate(linhas, start=1):
        assert len(linha["celulas"]) == len(aba10.SECOES), (
            f"a linha {n} tem {len(linha['celulas'])} grupos e o gerador desenha "
            f"{len(aba10.SECOES)}")
        td = linha["td"]
        for c in linha["celulas"]:
            g = c["grupo"]
            if g["l"] < td["l"] - 0.5 or g["r"] > td["r"] + 0.5:
                fora_da_celula.append(f"linha {n}: `{c['secao']}` de {g['l']:.0f} a "
                                      f"{g['r']:.0f}, a célula vai de {td['l']:.0f} a "
                                      f"{td['r']:.0f}")
    assert not fora_da_celula, "\n".join(fora_da_celula)
