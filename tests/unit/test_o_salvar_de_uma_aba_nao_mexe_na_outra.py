"""O Salvar de uma aba não mexe na seção de outra — O-SALVAR-DA-VIBRACAO-01.

MEDIDO NO DISCO DELA em 26/09/2026. Às 18:38:37 ela clicou em «Salvar Perfil»
na aba Vibração com o PRAGMATA aberto, e o backup de antes e o de depois
diferem em duas linhas que não são da vibração::

    controllers.<…:03>.mic.muted:      True  -> False   (o microfone ligou)
    controllers.<…:03>.speaker.fonte:  'sfx' -> ausente (a fonte sumiu)

AS DUAS CAUSAS, e as duas moram no dono da sobreposição
(``pacotes/rodape._draft_do_ativo``):

1. o Salvar é um gesto só para as dez abas, e punha o VIVO por cima do disco
   em TODAS as seções — o microfone ligado no aparelho virou a escolha dela;
2. o alto-falante do vivo era remontado sem a ``fonte``.

E o molde tinha um segundo chamador: os gestos do editor da aba Perfis
(``a10_perfis._com_o_que_esta_valendo``). Mudar a prioridade fazia o mesmo.

A RÉGUA COMPARA CONTRA O DISCO LIDO ANTES DO GESTO, nunca contra a própria
saída. Na parte GLOBAL do perfil a comparação é pelo esquema (o padrão que o
``save_profile`` escreve denso não é mudança); nos OVERRIDES é pelo JSON cru,
porque lá o campo ausente herda do global, e escrever o padrão seria mudança.

AS MORDIDAS, uma por cura (medidas na entrega):

- faça ``salvar`` passar ``TODAS_AS_SECOES_DO_VIVO`` em vez da seção da aba e
  :func:`test_o_salvar_da_aba_so_muda_a_secao_dela` reprova nas abas que não
  são donas, e :func:`test_o_caso_das_18h38_da_vibracao` reprova com o
  microfone e a fonte;
- devolva o ``SpeakerDraft(volume, muted, rota)`` nu a ``_o_som_daquela_peca``
  e :func:`test_o_salvar_da_02_guarda_a_fonte_e_a_rota` reprova com a fonte;
- faça ``a10_perfis._com_o_que_esta_valendo`` pedir todas as seções e
  :func:`test_o_editor_da_10_so_muda_o_campo_dele` reprova com o microfone.
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

#: O MESMO CONTROLE COM O VIVO DIVERGINDO EM TODA SEÇÃO que a sobreposição
#: alcança — a luz, o alto-falante, o microfone e os sensores. A cor viva é um
#: dos tons da casa (o azul do número 1), para a inversão do brilho achá-la.
VIVO_QUE_DIVERGE: dict[str, Any] = {
    **VIVO_DAS_18H38,
    "lightbar_rgb": [0, 0, 255],
    "speaker": {"volume": 60, "muted": False, "rota": 2, "fonte": "sfx"},
    "audio": {"mic_mudo": False, "mic_mudo_desejado": None, "volume_captura": 30},
    "sensores": {"giroscopio_ligado": False, "acelerometro_ligado": True},
}

#: OS GLOBAIS QUE O DAEMON PUBLICA, divergindo do disco nas duas seções que a
#: sobreposição lê da mesa inteira: a vibração e o mouse.
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

AS_DEZ = ("01-jogar.html", "02-controles.html", "03-gatilhos.html",
          "04-iluminacao.html", "05-vibracao.html", "06-navegacao.html",
          "07-lancadores.html", "08-conexoes.html", "09-sistema.html",
          "10-perfis.html")


class PonteDeMentira:
    """O mínimo que os gestos que gravam e reaplicam chamam."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch:{nome}")
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
    return {"gesto": "salvar", "pagina": aba}  # noqa-acento: chave do clique


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
# 1. o dono do mapa: cada seção viva tem UMA aba dona
# --------------------------------------------------------------------------
def test_cada_secao_viva_tem_uma_aba_dona_so() -> None:
    """Duas abas donas da mesma seção fariam o Salvar de uma mexer na outra.

    E uma seção sem dona seria sobreposição que nenhum Salvar faz — o que o
    `TODAS_AS_SECOES_DO_VIVO` promete e ninguém cumpre.
    """
    donas: dict[str, list[str]] = {}
    for aba in AS_DEZ:
        for secao in rodape.secoes_do_vivo(aba):
            donas.setdefault(secao, []).append(aba)
    assert set(donas) == set(rodape.TODAS_AS_SECOES_DO_VIVO), donas
    duplas = {s: p for s, p in donas.items() if len(p) > 1}
    assert not duplas, f"seção viva com duas abas donas: {duplas}"
    assert rodape.secoes_do_vivo("") == frozenset(), (
        "o clique que não diz de que aba veio não é dono de seção nenhuma")


# --------------------------------------------------------------------------
# 2. o Salvar do rodapé, nas dez abas
# --------------------------------------------------------------------------
@pytest.mark.parametrize("aba", AS_DEZ)
def test_o_salvar_da_aba_so_muda_a_secao_dela(aba: str) -> None:
    """Com o vivo divergindo em TODA seção, o disco só muda nas da aba."""
    antes = _o_disco()
    rodape.salvar(_ctx(VIVO_QUE_DIVERGE, MESA_QUE_DIVERGE),
                  _clique_do_salvar(aba), PonteDeMentira())
    mudou = _o_que_mudou(antes, _o_disco())
    donas = rodape.secoes_do_vivo(aba)
    assert not _fora_da_secao(mudou, donas), (
        f"o Salvar da {aba} mexeu fora das seções dela ({sorted(donas)}): "
        f"{_fora_da_secao(mudou, donas)}")
    # A SOBREPOSIÇÃO CONTINUA VALENDO NA ABA DONA — sem isto, uma «cura» que
    # só grava o disco passaria verde e apagaria o que o 01/09 mediu.
    faltou = sorted(s for s in donas if not any(_secao(k) == s for k in mudou))
    assert not faltou, (
        f"o vivo não chegou ao disco nas seções da própria {aba}: {faltou}")


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


def test_o_salvar_da_02_guarda_a_fonte_e_a_rota() -> None:
    """Na aba dona do alto-falante, o vivo traz o volume e não apaga o resto.

    O daemon publica o volume e o mudo; a rota e a fonte o Salvar herda do
    que o perfil já dizia daquela peça.
    """
    rodape.salvar(_ctx(VIVO_QUE_DIVERGE, MESA_QUE_DIVERGE),
                  _clique_do_salvar("02-controles.html"), PonteDeMentira())
    depois = _o_disco()
    assert depois[f"controllers.{P3}.speaker.volume"] == 60
    assert depois.get(f"controllers.{P3}.speaker.fonte") == "sfx", (
        "o Salvar da 02 apagou a fonte do alto-falante — o `SpeakerDraft` foi "
        "remontado sem ela")
    assert depois.get(f"controllers.{P3}.speaker.rota") == 2


# --------------------------------------------------------------------------
# 3. os outros escritores por seção: a 10, a 05 e a 02
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
    ({"mic": {"muted": False}}, "mic"),
])
def test_o_som_da_02_so_muda_a_secao_do_gesto(campos: dict[str, Any], secao: str) -> None:
    """O escritor do som da 02 grava o campo do gesto, e a outra seção fica."""
    antes = _o_disco()
    a02_controles._lembrar_do_som(_ctx(VIVO_QUE_DIVERGE, MESA_QUE_DIVERGE),
                                  P3, **campos)
    mudou = _o_que_mudou(antes, _o_disco())
    assert mudou, "a régua não mediu nada: o som não foi gravado"
    assert not _fora_da_secao(mudou, frozenset({secao})), mudou
