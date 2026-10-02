"""O Salvar de uma aba não mexe no perfil, e o gesto de uma seção só mexe nela.

MEDIDO NO DISCO DELA em 26/09/2026. Às 18:38:37 ela clicou em «Salvar Perfil»
na aba Vibração com o PRAGMATA aberto, e o backup de antes e o de depois
diferem em duas linhas que não são da vibração::

    controllers.<…:03>.mic.muted:      True  -> False   (o microfone ligou)
    controllers.<…:03>.speaker.fonte:  'sfx' -> ausente (a fonte sumiu)

A causa era o Salvar pôr o estado do aparelho por cima do disco. Desde
27/09 (`D-2709-O-SALVAR-LE-O-PERFIL`) o Salvar e o Aplicar leem o perfil do
disco, e só ele, em toda aba — quem mede isso nas dez abas, com o aparelho
divergindo em tudo, é `test_o_salvar_e_o_aplicar_leem_so_o_perfil.py`.

ESTE ARQUIVO GUARDA O CASO DELA E OS ESCRITORES POR SEÇÃO: o clique das
18:38:37 com o estado daquela hora, e os gestos que gravam no clique (o
editor da aba Perfis, a força da 05, o som da 02) mudando só o campo deles.

A RÉGUA COMPARA CONTRA O DISCO LIDO ANTES DO GESTO, nunca contra a própria
saída. Na parte GLOBAL do perfil a comparação é pelo esquema (o padrão que o
``save_profile`` escreve denso não é mudança); nos OVERRIDES é pelo JSON cru,
porque lá o campo ausente herda do global, e escrever o padrão seria mudança.

AS MORDIDAS:

- devolva ao ``rodape.salvar`` o microfone do aparelho (o ``mic_mudo`` do
  vivo no rascunho) e :func:`test_o_caso_das_18h38_da_vibracao` reprova com o
  microfone do …:03;
- monte o alto-falante do ``a02_controles._lembrar_do_som`` sobre um
  ``SpeakerDraft`` nu, em vez do efetivo da peça, e
  :func:`test_o_volume_da_02_guarda_a_fonte_e_a_rota` reprova com a fonte.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import (
    Contexto,
    a02_controles,
    a05_vibracao,
    a10_perfis,
    rodape,
)
from hefesto_dualsense4unix.profiles import loader

NOME = "PRAGMATA"

#: OS QUATRO CONTROLES DO PERFIL DELA, com endereço FORJADO (faixa `aa:bb:cc` e
#: `02:fe:`), na grafia do mapa `controllers` (sem os dois-pontos).
P3 = "aabbcc000003"
P2 = "aabbcc0000d8"
P4 = "aabbcc0000ab"
P1 = "02fe000000f0"

#: O PERFIL COMO ESTAVA NO DISCO DELA ANTES DO SALVAR, com as chaves trocadas.
#: Ele tem opinião em toda seção que o vivo alcança — é o que torna a régua
#: capaz de ver um atravessamento em qualquer uma delas.
PERFIL: dict[str, Any] = {
    "name": NOME, "version": 1,
    "match": {"type": "criteria", "window_class": ["steam_app_3357650"],
              "window_title_regex": None, "process_name": []},
    "priority": 80,
    "triggers": {"left": {"mode": "Off", "params": []},
                 "right": {"mode": "Off", "params": []}},
    "leds": {"lightbar": [0, 0, 0], "player_leds": [False] * 5,
             "lightbar_brightness": 1.0, "auto_player_colors": True,
             "lightbar_para_o_numero": None},
    "rumble": {"passthrough": True, "policy": "balanceado", "custom_mult": None},
    "mouse": {"enabled": False, "speed": 6, "scroll_speed": 1},
    "mode": {"kind": "gamepad", "gamepad_flavor": None, "caminho": "dualsense"},
    "suppress_desktop_emulation": False,
    "controllers": {
        P3: {"leds": {"lightbar": [255, 0, 0]},
             "triggers": {"left": {"mode": "SimpleRigid", "params": [6]},
                          "right": {"mode": "Machine",
                                    "params": [0, 9, 3, 3, 50, 8]}},
             "rumble": {"policy": "max"},
             "speaker": {"volume": 102, "muted": True, "rota": 2, "fonte": "sfx"},
             "mic": {"muted": True, "volume": 68},
             "mascara": "dualsense"},
        P2: {"leds": {"lightbar": [128, 255, 0]},
             "rumble": {"policy": "custom", "custom_mult": 2.0},
             "speaker": {"volume": 102, "muted": False},
             "mic": {"muted": False, "volume": 54},
             "mascara": "dualsense"},
        P4: {"leds": {"lightbar": [255, 0, 128]},
             "speaker": {"volume": 102, "muted": False},
             "mic": {"muted": False, "volume": 98},
             "mascara": "dualsense"},
        P1: {"leds": {"lightbar": [0, 255, 0]},
             "speaker": {"volume": 102, "muted": False},
             "mic": {"muted": True, "volume": 98},
             "mascara": "dualsense"},
    },
    "ponte": {"kind": "gamepad", "gamepad_flavor": "dualsense",
              "steam_input": False,
              "confirmada_em": "2026-09-17T01:42:11-03:00",
              "confirmada_por": "silencio"},
}

#: O …:03 COMO O DAEMON O PUBLICAVA ÀS 18:38:37: o microfone LIGADO no aparelho
#: contra o `mic.muted=true` do disco; o resto igual ao disco.
VIVO_DAS_18H38: dict[str, Any] = {
    "uniq": P3, "connected": True, "transport": "bt", "is_primary": True,
    "lightbar_rgb": [255, 0, 0], "lightbar_on": True, "lightbar_source": "sysfs",
    "brilho_da_barra": 1.0, "brilho_das_luzes": "fraco",
    "speaker": {"volume": 102, "muted": True, "rota": 2, "fonte": "sfx"},
    "audio": {"mic_mudo": False, "mic_mudo_desejado": None, "volume_captura": 68},
    "sensores": {"giroscopio_ligado": True, "acelerometro_ligado": True},
}

#: O MESMO CONTROLE COM O VIVO DIVERGINDO EM TODA SEÇÃO que o daemon publica
#: por peça — a luz, o alto-falante, o microfone e os sensores.
VIVO_QUE_DIVERGE: dict[str, Any] = {
    **VIVO_DAS_18H38,
    "lightbar_rgb": [0, 0, 255],
    "speaker": {"volume": 60, "muted": False, "rota": 2, "fonte": "sfx"},
    "audio": {"mic_mudo": False, "mic_mudo_desejado": None, "volume_captura": 30},
    "sensores": {"giroscopio_ligado": False, "acelerometro_ligado": True},
}

#: OS GLOBAIS QUE O DAEMON PUBLICA, divergindo do disco na vibração e no
#: mouse.
MESA_QUE_DIVERGE: dict[str, Any] = {
    "rumble_policy": "max",
    "rumble_passthrough": False,
    "rumble_policy_custom_mult": None,
    "mouse_emulation": {"enabled": True, "speed": 11, "scroll_speed": 4},
}

MESA_DAS_18H38: dict[str, Any] = {
    "rumble_policy": "balanceado",
    "rumble_passthrough": True,
    "rumble_policy_custom_mult": None,
}

class PonteDeMentira:
    """O mínimo que os gestos que gravam e reaplicam chamam."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch:{nome}")
        return True

    # 01/10/2026: o gravar-e-reaplicar pede o `profile.reaplicar`, que não é escolha.
    def profile_reaplicar(self, nome: str) -> bool:
        self.chamadas.append(f"profile_reaplicar:{nome}")
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"chamar:{metodo}")
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}


@pytest.fixture(autouse=True)
def _perfil_no_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """O perfil no disco hermético da suíte (o `XDG_CONFIG_HOME` do conftest).

    Gravado pelo PRÓPRIO produto, para que a representação do arquivo seja a
    de sempre e a régua compare o gesto, não a forma do fixture.
    """
    from hefesto_dualsense4unix.profiles.schema import Profile

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", NOME, raising=False)
    loader.save_profile(Profile.model_validate(PERFIL), origem="teste")


def _clique_do_salvar(aba: str) -> dict[str, str]:
    """O clique do «Salvar» como o piloto o manda: com a aba de onde veio."""
    return {"gesto": "salvar", "pagina": aba}  # (noqa-acento: chave do clique)


def _ctx(vivo: dict[str, Any], mesa: dict[str, Any]) -> Contexto:
    return Contexto(state={"active_profile": NOME, "controllers": [vivo], **mesa},
                    mesa=[vivo], conectados=[vivo])


def _achatar(obj: Any, pre: str = "") -> dict[str, Any]:
    fora: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            fora.update(_achatar(v, f"{pre}.{k}" if pre else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            fora.update(_achatar(v, f"{pre}[{i}]"))
    else:
        fora[pre] = obj
    return fora


def _o_disco(nome: str = NOME) -> dict[str, Any]:
    """O perfil no disco, achatado: o global pelo esquema, os overrides crus."""
    from hefesto_dualsense4unix.profiles.schema import Profile

    arquivo = loader.arquivo_do_perfil(nome)
    assert arquivo is not None, f"o perfil {nome!r} não está no disco"
    cru = json.loads(arquivo.read_text(encoding="utf-8"))
    global_ = Profile.model_validate(cru).model_dump(mode="json", exclude={"controllers"})
    return _achatar({**global_, "controllers": cru.get("controllers") or {}})


def _secao(caminho: str) -> str:
    """`controllers.<uniq>.mic.muted` → `mic`; `rumble.policy` → `rumble`."""
    partes = caminho.split(".")
    if partes[0] == "controllers" and len(partes) > 2:
        return partes[2].split("[")[0]
    return partes[0].split("[")[0]


def _o_que_mudou(antes: dict[str, Any], depois: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    return {k: (antes.get(k, "<ausente>"), depois.get(k, "<ausente>"))
            for k in sorted(set(antes) | set(depois))
            if antes.get(k, "<ausente>") != depois.get(k, "<ausente>")}


def _fora_da_secao(mudou: dict[str, Any], secoes: frozenset[str]) -> dict[str, Any]:
    return {k: v for k, v in mudou.items() if _secao(k) not in secoes}


# --------------------------------------------------------------------------
# 1. o Salvar do rodapé, com o estado dela das 18:38:37
# --------------------------------------------------------------------------
def test_o_caso_das_18h38_da_vibracao() -> None:
    """O clique dela, com o estado dela: o microfone e a fonte do …:03 ficam."""
    antes = _o_disco()
    rodape.salvar(_ctx(VIVO_DAS_18H38, MESA_DAS_18H38),
                  _clique_do_salvar("05-vibracao.html"), PonteDeMentira())
    mudou = _o_que_mudou(antes, _o_disco())
    assert f"controllers.{P3}.mic.muted" not in mudou, (
        f"o Salvar da Vibração ligou o microfone do …:03: {mudou}")
    assert f"controllers.{P3}.speaker.fonte" not in mudou, (
        f"o Salvar da Vibração apagou a fonte do alto-falante do …:03: {mudou}")
    assert not mudou, f"nada mudou no aparelho, e o disco mudou: {mudou}"


def test_o_volume_da_02_guarda_a_fonte_e_a_rota() -> None:
    """O gesto do volume grava o volume, e a rota e a fonte da peça ficam.

    Até 27/09 era o Salvar da 02 que levava o volume do aparelho ao disco; hoje
    é o gesto, no clique (`a02_controles._lembrar_do_som`), e ele parte do
    efetivo da peça: o `with_controller_speaker` troca a seção inteira.
    """
    a02_controles._lembrar_do_som(_ctx(VIVO_QUE_DIVERGE, MESA_QUE_DIVERGE),
                                  P3, speaker={"volume": 60})
    depois = _o_disco()
    assert depois[f"controllers.{P3}.speaker.volume"] == 60
    assert depois.get(f"controllers.{P3}.speaker.fonte") == "sfx", (
        "o volume da 02 apagou a fonte do alto-falante — o `SpeakerDraft` foi "
        "remontado sem ela")
    assert depois.get(f"controllers.{P3}.speaker.rota") == 2


def test_o_salvar_da_02_guarda_o_ganho_e_o_volume_do_microfone() -> None:
    """O Salvar da 02 regrava o microfone da peça inteiro: o mudo, o volume e o ganho.

    É a assinatura da escrita das 18:40:14 de 26/09 no Freestyle dela
    (`mic.volume` 64 → ausente): o Salvar remontava o microfone com o que o
    daemon publica, e o daemon não publica o ganho, nem o volume enquanto o
    canal não responde. Desde 27/09 ele lê o disco, e o aparelho aberto aqui
    (o `mic_mudo` falso) também não entra.
    """
    from hefesto_dualsense4unix.profiles.schema import Profile

    cru = json.loads(json.dumps(PERFIL))
    cru["controllers"][P3]["mic"] = {"muted": True, "volume": 68, "gain": 40}
    loader.save_profile(Profile.model_validate(cru), origem="teste")
    vivo = {**VIVO_DAS_18H38,
            "audio": {"mic_mudo": False, "mic_mudo_desejado": None}}
    rodape.salvar(_ctx(vivo, MESA_DAS_18H38),
                  _clique_do_salvar("02-controles.html"), PonteDeMentira())
    depois = _o_disco()
    assert depois.get(f"controllers.{P3}.mic.muted") is True, (
        "o Salvar da 02 gravou o microfone aberto do aparelho como escolha dela")
    assert depois.get(f"controllers.{P3}.mic.gain") == 40, (
        "o Salvar da 02 apagou o ganho do microfone do …:03 — o `MicDraft` "
        "foi remontado sem ele")
    assert depois.get(f"controllers.{P3}.mic.volume") == 68, (
        "o Salvar da 02 apagou o volume do microfone do …:03 com o canal "
        "ainda sem resposta")


# --------------------------------------------------------------------------
# 2. os escritores por seção: a 10, a 05 e a 02
# --------------------------------------------------------------------------
def test_o_editor_da_10_so_muda_o_campo_dele() -> None:
    """Mudar a prioridade grava a prioridade, e o microfone fica."""
    antes = _o_disco()
    a10_perfis.editor_prioridade(_ctx(VIVO_QUE_DIVERGE, MESA_QUE_DIVERGE),
                                 {"valor": "81", "evento": "change"},
                                 PonteDeMentira())
    mudou = _o_que_mudou(antes, _o_disco())
    assert mudou == {"priority": (80, 81)}, (
        f"o editor da aba Perfis mexeu fora da prioridade: {mudou}")


def test_a_forca_da_05_so_muda_a_vibracao() -> None:
    """O gesto por seção da própria Vibração: a força do …:03 e mais nada."""
    antes = _o_disco()
    a05_vibracao._gravar_a_forca(_ctx(VIVO_QUE_DIVERGE, MESA_QUE_DIVERGE),
                                 PonteDeMentira(), P3, "economia")
    mudou = _o_que_mudou(antes, _o_disco())
    assert mudou, "a régua não mediu nada: a força não foi gravada"
    assert not _fora_da_secao(mudou, frozenset({"rumble"})), mudou


@pytest.mark.parametrize(("campos", "secao"), [
    ({"speaker": {"volume": 50}}, "speaker"),
    # O mudo não passa por aqui desde 29/09 (O-MUDO-E-DO-CONTROLE-01): é do
    # controle. O caso do microfone mede o volume da peça.
    ({"mic": {"volume": 55}}, "mic"),
])
def test_o_som_da_02_so_muda_a_secao_do_gesto(campos: dict[str, Any], secao: str) -> None:
    """O escritor do som da 02 grava o campo do gesto, e a outra seção fica."""
    antes = _o_disco()
    a02_controles._lembrar_do_som(_ctx(VIVO_QUE_DIVERGE, MESA_QUE_DIVERGE),
                                  P3, **campos)
    mudou = _o_que_mudou(antes, _o_disco())
    assert mudou, "a régua não mediu nada: o som não foi gravado"
    assert not _fora_da_secao(mudou, frozenset({secao})), mudou
