"""O modo automático e o modo personalizado das abas Gatilhos e Iluminação — 08/10/2026.

A-O-MODO-AUTOMATICO-E-O-PERSONALIZADO-01 (pedido de 06/10). Um par de botões no alto
de cada aba (``modo-dos-gatilhos`` e ``modo-da-luz``), um campo escrito no perfil
(``triggers.modo`` e ``leds.modo``) e UMA regra de leitura para o perfil de antes, sem o campo.

O QUE ESTE ARQUIVO MEDE, e a mordida de cada um está no docstring do caso:

1. a regra (``decidir_o_modo_*``) é uma só: o modelo e o JSON da interface respondem igual;
2. a tela e o aparelho não discordam: só o modo ESCRITO como Automático age no
   ``ProfileManager`` (``perfil_no_modo``), e o disco nunca perde a escolha guardada;
3. os gestos gravam o campo certo, reaplicam o perfil e não regravam o modo em que o perfil já
   está; sem a tela, as portas de cor, brilho, número e efeito recusam no Automático;
4. a luz do jogo saiu da Iluminação (o LED do microfone, que é outra feature, ficou);
5. o rótulo da chave ``Off`` é «Sem efeito».

O LAR É DE MENTIRA: o ``conftest`` desvia ``HOME`` e os ``XDG_*``, e os casos que gravam
escrevem perfil de verdade com ``save_profile``.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _p in (str(RAIZ / "src"), str(INTERFACE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hefesto_dualsense4unix.core.trigger_effects import rigid
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import schema as sch
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchAny,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

AUTOMATICO = "automatico"  # (noqa-acento)
UM = "aa:bb:cc:00:00:01"
CHAVE_UM = "aabbcc000001"
NOME = "regua-dos-modos"

MESA = [{"pref": "p1", "uniq": UM, "jogador": 1, "cor": "white", "nome": "White",
         "via": "USB", "mascara": "DualSense"}]
P1 = {"uniq": UM, "index": 0, "transport": "usb", "connected": True, "player": 1,
      "player_slot": 1, "is_primary": True, "inputs": {"l2_raw": 0, "r2_raw": 0},
      "lightbar_rgb": [0, 0, 255], "lightbar_on": True, "lightbar_source": "sysfs"}


@pytest.fixture
def a03():
    import pacotes  # noqa: F401
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


@pytest.fixture
def a04():
    import pacotes  # noqa: F401
    from pacotes import a04_iluminacao

    return a04_iluminacao


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def pasta_de_perfis() -> pathlib.Path:
    """A pasta de perfis do lar de mentira (o ``conftest`` desvia ``HOME`` e os ``XDG_*``).

    Não se troca ``profiles_dir`` só no loader: a tela lê pelo ``xdg_paths``, e as duas pontas
    têm de olhar a mesma pasta.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    alvo = pathlib.Path(profiles_dir(ensure=True))
    for velho in alvo.glob("*.json"):
        velho.unlink()
    return alvo


class Ponte:
    """Um dublê da ponte: guarda o que foi chamado e devolve o caminho feliz."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args: Any, **kwargs: Any) -> Any:
            self.chamadas.append((nome, args, kwargs))
            return True if nome in ("chamar", "profile_switch") else {
                "aplicado_em": [UM], "guardado_em": []}

        return registrar

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]


def _ctx(pac: Any, perfil: str = NOME) -> Any:
    return pac.Contexto(state={"active_profile": perfil}, mesa=[dict(m) for m in MESA],
                        conectados=[dict(P1)], estados={})


def _salvar(**campos: Any) -> pathlib.Path:
    return save_profile(Profile(name=NOME, match=MatchAny(), **campos), origem="regua")


def _disco(caminho: pathlib.Path) -> dict:
    return json.loads(pathlib.Path(caminho).read_text(encoding="utf-8"))


def _trigger(modo: str, *params: int) -> TriggerConfig:
    return TriggerConfig(mode=modo, params=list(params))


def _com_overrides(**controles: ControllerOverrides) -> dict[str, ControllerOverrides]:
    return dict(controles)


def test_as_constantes_do_desenho_sao_as_do_esquema() -> None:
    """O quadro e os botões falam a língua do esquema: uma palavra, um dono."""
    from hefesto_dualsense4unix.interface import monta

    assert monta.MODO_AUTOMATICO == sch.MODO_AUTOMATICO == AUTOMATICO
    assert monta.MODO_PERSONALIZADO == sch.MODO_PERSONALIZADO == "personalizado"


@pytest.mark.parametrize(("perfil", "esperado"), [
    (Profile(name="a", match=MatchAny()), AUTOMATICO),
    (Profile(name="a", match=MatchAny(),
             leds=LedsConfig(lightbar=(40, 80, 180), auto_player_colors=True)), AUTOMATICO),
    (Profile(name="a", match=MatchAny(), leds=LedsConfig(auto_player_colors=False)),
     "personalizado"),
    (Profile(name="a", match=MatchAny(),
             controllers=_com_overrides(
                 aabbcc000001=ControllerOverrides(leds=LedsConfig(lightbar=(7, 8, 9))))),
     "personalizado"),
    (Profile(name="a", match=MatchAny(),
             controllers=_com_overrides(
                 aabbcc000001=ControllerOverrides(leds=LedsConfig(lightbar=(0, 0, 0))))),
     AUTOMATICO),
    (Profile(name="a", match=MatchAny(), leds=LedsConfig(modo="personalizado")),
     "personalizado"),
    (Profile(name="a", match=MatchAny(),
             leds=LedsConfig(modo=AUTOMATICO, auto_player_colors=False)), AUTOMATICO),
], ids=["vazio", "global-nao-conta", "auto-desligado", "cor-no-controle",
        "preto-no-controle-nao-conta", "escrito-personalizado", "escrito-vence"])
def test_a_regra_da_luz_sem_o_campo_escrito(perfil: Profile, esperado: str, a04: Any) -> None:
    """``None`` vale o que o perfil já dizia; o escrito manda; o modelo e o JSON concordam.

    A cor GLOBAL não conta como «cor própria»: no merge do backend a paleta automática vence
    o global e só perde para a cor do controle, então a tela não pode dizer Personalizado
    sobre um aparelho que acende o plástico.

    MORDIDA: faça ``_tem_cor_propria`` contar o global e ``global-nao-conta`` reprova.

    Prova da D-0810-O-MODO-AUTOMATICO-E-O-PERSONALIZADO.
    """
    cru = perfil.model_dump(mode="json", exclude_unset=True)
    assert a04.modo_da_luz_do_perfil(cru) == esperado


@pytest.mark.parametrize(("perfil", "esperado"), [
    (Profile(name="a", match=MatchAny()), "personalizado"),
    (Profile(name="a", match=MatchAny(),
             triggers=TriggersConfig(left=_trigger("Off"), right=_trigger("Off"))), AUTOMATICO),
    (Profile(name="a", match=MatchAny(),
             triggers=TriggersConfig(right=_trigger("Rigid", 5, 200))), "personalizado"),
    (Profile(name="a", match=MatchAny(),
             triggers=TriggersConfig(left=_trigger("Off"), right=_trigger("Off")),
             controllers=_com_overrides(aabbcc000001=ControllerOverrides(
                 triggers=TriggersConfig(left=_trigger("Rigid", 5, 200))))), "personalizado"),
    (Profile(name="a", match=MatchAny(),
             triggers=TriggersConfig(left=_trigger("Off"), right=_trigger("Off")),
             controllers=_com_overrides(aabbcc000001=ControllerOverrides(
                 triggers=TriggersConfig(left=_trigger("Off"))))), AUTOMATICO),
    (Profile(name="a", match=MatchAny(),
             triggers=TriggersConfig(right=_trigger("Rigid", 5, 200), modo=AUTOMATICO)),
     AUTOMATICO),
    (Profile(name="a", match=MatchAny(), triggers=TriggersConfig(modo="personalizado")),
     "personalizado"),
], ids=["vazio-nasce-com-efeito", "todos-off", "global-rigido", "override-rigido",
        "override-off", "escrito-vence",
        "escrito-personalizado"])
def test_a_regra_dos_gatilhos_sem_o_campo_escrito(
    perfil: Profile, esperado: str, a03: Any
) -> None:
    """Automático sem opinião = todos os gatilhos (globais e de cada controle) em «Sem efeito».

    MORDIDA: ignore os overrides em ``_todos_os_gatilhos_sem_efeito`` (a 03) e
    ``override-rigido`` reprova.
    """
    cru = perfil.model_dump(mode="json", exclude_unset=True)
    assert a03.modo_dos_gatilhos_do_perfil(cru) == esperado


def test_sem_perfil_o_modo_e_o_personalizado(a03: Any, a04: Any) -> None:
    """«Não há perfil» não é um modo: a tela não finge um Automático."""
    for vazio in (None, {}):
        assert a03.modo_dos_gatilhos_do_perfil(vazio) == "personalizado"
        assert a04.modo_da_luz_do_perfil(vazio) == "personalizado"


def test_o_perfil_sem_modo_escrito_vai_inteiro_ao_aparelho() -> None:
    """A vista só age sobre o modo ESCRITO: o perfil de antes segue como estava."""
    p = Profile(name="a", match=MatchAny(),
                triggers=TriggersConfig(right=_trigger("Rigid", 5, 200)))
    assert sch.perfil_no_modo(p) is p
    q = Profile(name="a", match=MatchAny(), triggers=TriggersConfig(modo="personalizado"),
                leds=LedsConfig(modo="personalizado", lightbar=(1, 2, 3)))
    assert sch.perfil_no_modo(q) is q


def test_o_automatico_dos_gatilhos_manda_sem_efeito_e_o_disco_fica() -> None:
    """Global e overrides saem ``Off``; o original (o que vai ao disco) não se mexe.

    MORDIDA: tire o ramo dos gatilhos de ``perfil_no_modo`` e o ``right`` volta ``Rigid``.

    Prova da D-0810-O-MODO-AUTOMATICO-E-O-PERSONALIZADO.
    """
    p = Profile(
        name="a", match=MatchAny(),
        triggers=TriggersConfig(left=_trigger("Off"), right=_trigger("Rigid", 5, 200),
                                modo=AUTOMATICO),
        controllers=_com_overrides(aabbcc000001=ControllerOverrides(
            triggers=TriggersConfig(left=_trigger("Rigid", 2, 90)))),
    )
    vista = sch.perfil_no_modo(p)
    assert vista.triggers.left.mode == vista.triggers.right.mode == "Off"
    dele = vista.controllers["aabbcc000001"].triggers
    assert dele is not None and dele.left.mode == "Off"
    assert "right" not in dele.model_fields_set, "inventou opinião num lado sem dono"
    assert p.triggers.right.mode == "Rigid"
    assert p.controllers["aabbcc000001"].triggers.left.mode == "Rigid"


def test_o_automatico_da_luz_tira_a_cor_e_deixa_o_resto() -> None:
    """A cor própria sai da vista; brilho e luzes do número seguem como o controle os tem.

    MORDIDA: tire a limpeza dos overrides de ``perfil_no_modo`` e o controle volta a acender a
    cor escolhida em pleno Automático.
    """
    p = Profile(
        name="a", match=MatchAny(),
        leds=LedsConfig(lightbar=(40, 80, 180), auto_player_colors=False, modo=AUTOMATICO),
        controllers=_com_overrides(aabbcc000001=ControllerOverrides(
            leds=LedsConfig(lightbar=(7, 8, 9), lightbar_para_o_numero=1,
                            lightbar_brightness=0.5))),
    )
    vista = sch.perfil_no_modo(p)
    assert vista.leds.lightbar == (0, 0, 0)
    assert vista.leds.auto_player_colors is True
    dele = vista.controllers["aabbcc000001"].leds
    assert dele is not None
    assert "lightbar" not in dele.model_fields_set
    assert "lightbar_para_o_numero" not in dele.model_fields_set
    assert dele.lightbar_brightness == 0.5
    assert p.controllers["aabbcc000001"].leds.lightbar == (7, 8, 9)
    assert p.leds.lightbar == (40, 80, 180)


def test_o_manager_aplica_a_vista_dos_gatilhos(pasta_de_perfis: pathlib.Path) -> None:
    """O Automático escrito chega ao aparelho como ``Off`` nos dois lados; o Personalizado, não.

    MORDIDA: troque ``perfil_no_modo(profile)`` por ``profile`` em ``apply_profile``.
    """
    gatilhos = TriggersConfig(left=_trigger("Off"), right=_trigger("Rigid", 5, 200))
    for modo, direito in ((AUTOMATICO, "Off"), ("personalizado", "Rigid")):
        save_profile(Profile(name=f"m-{modo}", match=MatchAny(),
                             triggers=gatilhos.model_copy(update={"modo": modo})))
        fc = FakeController()
        fc.connect()
        ProfileManager(controller=fc, store=StateStore()).activate(f"m-{modo}")
        lados = {c.payload[0]: c.payload[1] for c in fc.commands if c.kind == "set_trigger"}
        if direito == "Rigid":
            assert lados["right"].forces == rigid(5, 200).forces
        else:
            assert lados["right"].forces != rigid(5, 200).forces
        assert load_profile(f"m-{modo}").triggers.right.mode == "Rigid", (
            "a escolha guardada tem de continuar no disco")


def test_o_manager_aplica_a_vista_da_luz(pasta_de_perfis: pathlib.Path) -> None:
    """No Automático a cor global do perfil não sai ao aparelho; no Personalizado, sim.

    MORDIDA: a mesma do caso acima, na luz.
    """
    for modo, acende in ((AUTOMATICO, False), ("personalizado", True)):
        save_profile(Profile(name=f"l-{modo}", match=MatchAny(),
                             leds=LedsConfig(lightbar=(10, 20, 30), auto_player_colors=False,
                                             modo=modo)))
        fc = FakeController()
        fc.connect()
        ProfileManager(controller=fc, store=StateStore()).activate(f"l-{modo}")
        cores = [c.payload for c in fc.commands if c.kind == "set_led"]
        assert (cores == [(10, 20, 30)]) is acende, (modo, cores)


def test_o_gesto_dos_gatilhos_grava_o_modo_e_guarda_a_escolha(
    pasta_de_perfis: pathlib.Path, a03: Any, pac: Any
) -> None:
    """Automático e volta: o campo certo no disco, o efeito guardado intacto, o perfil reaplicado.

    MORDIDA: grave ``update={"modo": "personalizado"}`` fixo no gesto e o primeiro passo reprova.
    """
    caminho = _salvar(triggers=TriggersConfig(right=_trigger("Rigid", 5, 200)))
    ponte = Ponte()
    funcao = pac.gesto_da_pagina("03-gatilhos.html", "modo-dos-gatilhos")
    assert funcao is not None

    saiu = funcao(_ctx(pac), {"modo": AUTOMATICO, "uniq": UM}, ponte)
    assert isinstance(saiu, dict) and "recado" in saiu
    disco = _disco(caminho)
    assert disco["triggers"]["modo"] == AUTOMATICO
    assert disco["triggers"]["right"]["mode"] == "Rigid"
    assert "profile_reaplicar" in ponte.nomes()

    funcao(_ctx(pac), {"modo": "personalizado", "uniq": UM}, Ponte())
    disco = _disco(caminho)
    assert disco["triggers"]["modo"] == "personalizado"
    assert disco["triggers"]["right"]["mode"] == "Rigid"


def test_pedir_o_modo_em_que_o_perfil_ja_esta_nao_grava_nada(
    pasta_de_perfis: pathlib.Path, pac: Any
) -> None:
    """O botão já aceso não regrava o perfil nem mexe no aparelho."""
    caminho = _salvar(triggers=TriggersConfig(right=_trigger("Rigid", 5, 200)))
    antes = pathlib.Path(caminho).read_bytes()
    ponte = Ponte()
    funcao = pac.gesto_da_pagina("03-gatilhos.html", "modo-dos-gatilhos")
    assert funcao(_ctx(pac), {"modo": "personalizado", "uniq": UM}, ponte) is None
    assert pathlib.Path(caminho).read_bytes() == antes
    assert ponte.chamadas == []


def test_o_gesto_dos_gatilhos_recusa_pedido_sem_modo_e_sem_perfil(
    pasta_de_perfis: pathlib.Path, pac: Any
) -> None:
    funcao = pac.gesto_da_pagina("03-gatilhos.html", "modo-dos-gatilhos")
    _salvar()
    for ruim in ("", "qualquer"):
        with pytest.raises(ValueError):
            funcao(_ctx(pac), {"modo": ruim, "uniq": UM}, Ponte())
    with pytest.raises(RuntimeError):
        funcao(_pac_sem_perfil(pac), {"modo": AUTOMATICO, "uniq": UM}, Ponte())


def _pac_sem_perfil(pac: Any) -> Any:
    return pac.Contexto(state={}, mesa=[dict(m) for m in MESA], conectados=[dict(P1)],
                        estados={})


@pytest.mark.parametrize("gesto", ["modo", "imersao"])
def test_no_automatico_escrito_os_gestos_de_efeito_recusam(
    pasta_de_perfis: pathlib.Path, pac: Any, gesto: str
) -> None:
    """A porta de quem fala com o gesto sem a tela também fecha, e a recusa não grava.

    MORDIDA: tire ``_nao_no_automatico(ctx)`` de um dos dois e o caso dele reprova.
    """
    caminho = _salvar(triggers=TriggersConfig(modo=AUTOMATICO))
    antes = pathlib.Path(caminho).read_bytes()
    funcao = pac.gesto_da_pagina("03-gatilhos.html", gesto)
    assert funcao is not None
    with pytest.raises(RuntimeError, match="modo automático"):
        funcao(_ctx(pac), {"uniq": UM, "lado": "d", "modo": "Rigid", "valor": "5"}, Ponte())
    assert pathlib.Path(caminho).read_bytes() == antes


def test_o_perfil_de_antes_segue_aceitando_o_efeito(
    pasta_de_perfis: pathlib.Path, pac: Any
) -> None:
    """Sem ``triggers.modo`` escrito a guarda não fecha nada: só o escrito recusa."""
    _salvar(triggers=TriggersConfig(right=_trigger("Rigid", 5, 200)))
    from pacotes import a03_gatilhos

    a03_gatilhos._nao_no_automatico(_ctx(pac))


def test_no_automatico_a_tela_dos_gatilhos_diz_sem_efeito(a03: Any) -> None:
    """Com o modo escrito, a tela mostra ``Off`` antes de olhar o rascunho e o disco.

    MORDIDA: tire o ramo do Automático de ``_o_que_o_controle_recebe`` e o disco reaparece.
    """
    p = {"triggers": {"modo": AUTOMATICO, "right": {"mode": "Rigid", "params": [5, 200]}}}
    for disco in ("left", "right"):
        assert a03._o_que_o_controle_recebe(p, UM, disco) == {"mode": "Off", "params": []}
    p["triggers"]["modo"] = "personalizado"
    assert a03._o_que_o_controle_recebe(p, UM, "right")["mode"] == "Rigid"


def test_o_rotulo_da_chave_off_e_sem_efeito(a03: Any) -> None:
    """Resposta de 06/10: o ``Off`` aparece como «Sem efeito»; a chave não muda.

    Prova da D-0810-O-MODO-AUTOMATICO-E-O-PERSONALIZADO.
    """
    assert a03.ROTULO_DO_JOGO_DECIDE == "Sem efeito"
    assert a03._rotulo_do_modo("Off") == "Sem efeito"


def test_o_pacote_dos_gatilhos_diz_o_modo_da_aba(
    pasta_de_perfis: pathlib.Path, a03: Any, pac: Any
) -> None:
    """O quadro e os dois botões do par acendem pelo modo do PERFIL."""
    _salvar(triggers=TriggersConfig(right=_trigger("Rigid", 5, 200)))
    saiu = a03.pacote(_ctx(pac))
    assert saiu["modo-dos-gatilhos"] == "personalizado"
    assert saiu["modo-dos-gatilhos-personalizado"] == "sim"
    assert saiu["modo-dos-gatilhos-automatico"] == ""
    _salvar(triggers=TriggersConfig(right=_trigger("Rigid", 5, 200), modo=AUTOMATICO))
    saiu = a03.pacote(_ctx(pac))
    assert saiu["modo-dos-gatilhos"] == AUTOMATICO
    assert saiu["modo-dos-gatilhos-automatico"] == "sim"
    assert saiu["modo-dos-gatilhos-personalizado"] == ""


def test_no_automatico_o_hex_e_o_do_plastico_mesmo_com_cor_guardada(
    pasta_de_perfis: pathlib.Path, a04: Any, pac: Any
) -> None:
    """A cor guardada fica no disco e NÃO vale no Automático: o hex e o X dizem o plástico.

    MORDIDA: arranque o ramo ``MODO_AUTOMATICO`` de ``_a_cor_de_agora`` e o hex volta à guardada.
    """
    _salvar(controllers=_com_overrides(**{CHAVE_UM: ControllerOverrides(
        leds=LedsConfig(lightbar=(12, 34, 56), lightbar_para_o_numero=1))}),
        leds=LedsConfig(modo=AUTOMATICO))
    cego = dict(P1, lightbar_source="desconhecida", lightbar_rgb=None)
    ctx = pac.Contexto(state={"active_profile": NOME}, mesa=[dict(m) for m in MESA],
                       conectados=[cego], estados={})
    cru = pac.perfil.ativo(NOME)
    cor = a04._a_cor_de_agora(ctx, cru, cego)
    assert tuple(cor) != (12, 34, 56)
    cru["leds"]["modo"] = "personalizado"
    assert tuple(a04._a_cor_de_agora(ctx, cru, cego)) == (12, 34, 56)


def test_o_par_de_botoes_acende_pelo_modo_e_leva_o_pintor() -> None:
    from hefesto_dualsense4unix.interface import monta

    html = monta.par_de_modos("modo-da-luz", AUTOMATICO)
    assert html.count('data-gesto="modo-da-luz"') == 2
    assert 'data-modo="automatico"' in html and 'data-modo="personalizado"' in html
    assert html.count('data-hef-atributo="aria-pressed"') == 2
    assert html.count('aria-pressed="true"') == 1
    assert html.count('class="on"') == 1
    for modo in (AUTOMATICO, "personalizado"):
        assert f'data-campo="modo-da-luz-{modo}"' in html


@pytest.mark.parametrize(("arquivo", "gesto"), [
    ("03-gatilhos.html", "modo-dos-gatilhos"), ("04-iluminacao.html", "modo-da-luz")])
def test_o_quadro_leva_o_modo_sem_colidir_com_o_botao(arquivo: str, gesto: str) -> None:
    """O quadro usa ``data-modo-da-aba`` e o botão ``data-modo``: o piloto despacha por
    ``closest`` e leva o dataset inteiro, então os dois nomes não podem ser o mesmo.

    MORDIDA: renomeie o atributo do quadro para ``data-modo`` e o gesto recebe o modo errado.
    """
    from hefesto_dualsense4unix.interface import onde

    texto = onde.pagina(arquivo).read_text(encoding="utf-8")
    assert f'data-campo="{gesto}"' in texto
    assert 'data-modo-da-aba="personalizado"' in texto
    marca = texto.index('data-modo-da-aba="personalizado"')
    quadro = texto[texto.rindex("<", 0, marca):texto.index(">", marca)]
    assert "data-modo=" not in quadro


def test_a_folha_para_as_colunas_no_automatico() -> None:
    """O CSS que deixa a coluna parada existe nas duas abas — é a metade da tela do «parado».

    MORDIDA: tire o ``pointer-events:none`` da folha de uma aba e a mordida de piloto reprova;
    aqui a régua de texto reprova antes.
    """
    from hefesto_dualsense4unix.interface import onde

    for pagina in ("03-gatilhos.html", "04-iluminacao.html"):
        texto = onde.pagina(pagina).read_text(encoding="utf-8")
        if 'data-governa="' in texto:
            assert ".governado-pelo-jogo{" in texto
            assert "pointer-events:none" in texto.split(".governado-pelo-jogo{", 1)[1][:120]
            continue
        assert '.quadro[data-modo-da-aba="automatico"]' in texto
        assert "pointer-events:none" in texto.split(
            '.quadro[data-modo-da-aba="automatico"]', 1)[1][:300]


def test_a_luz_do_jogo_saiu_da_iluminacao_e_o_led_do_microfone_ficou(a04: Any) -> None:
    """Saiu a frase, o campo do ``state_full``, o método do IPC e a leitura do backend.

    O LED do microfone do jogo (``luz_do_mic_do_jogo``) é outra feature e não pode ter ido.
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
    from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic
    from hefesto_dualsense4unix.interface import onde

    for nome in ("frase_da_luz_do_jogo", "FRASE_DA_LUZ_DO_JOGO", "ENDERECO_DA_LUZ_DO_JOGO",
                 "ENDERECO_DO_AUTOMATICO", "auto_cores"):
        assert not hasattr(a04, nome), f"{nome} voltou à Iluminação"
    assert not hasattr(PyDualSenseController, "luz_do_jogo_para")
    assert not hasattr(IpcHandlersMixin, "_luz_do_jogo")
    assert hasattr(luz_do_mic, "luz_do_mic_do_jogo")
    desenho = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    assert "luz-do-jogo" not in desenho and 'data-gesto="auto-cores"' not in desenho


def test_o_gesto_da_luz_grava_o_modo_liga_as_cores_e_reaplica(
    pasta_de_perfis: pathlib.Path, pac: Any
) -> None:
    """Automático liga a paleta e escreve o modo; Personalizado desliga a paleta e a cor que o
    controle acende agora fica guardada nele. O perfil é reaplicado nos dois.

    MORDIDA: grave ``auto_player_colors`` fixo em ``True`` e o Personalizado reprova.
    """
    _salvar(leds=LedsConfig(modo="personalizado", auto_player_colors=False))
    funcao = pac.gesto_da_pagina("04-iluminacao.html", "modo-da-luz")
    assert funcao is not None

    ponte = Ponte()
    saiu = funcao(_ctx(pac), {"modo": AUTOMATICO}, ponte)
    assert isinstance(saiu, dict) and "recado" in saiu
    assert "profile_reaplicar" in ponte.nomes()
    perfil = load_profile(NOME)
    assert perfil.leds.modo == AUTOMATICO and perfil.leds.auto_player_colors is True

    ponte = Ponte()
    funcao(_ctx(pac), {"modo": "personalizado"}, ponte)
    perfil = load_profile(NOME)
    assert perfil.leds.modo == "personalizado" and perfil.leds.auto_player_colors is False
    assert "profile_reaplicar" in ponte.nomes()

    with pytest.raises(ValueError):
        funcao(_ctx(pac), {"modo": "outro"}, Ponte())
