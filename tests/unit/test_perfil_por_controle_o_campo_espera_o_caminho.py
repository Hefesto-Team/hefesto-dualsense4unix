"""PERFIL-POR-CONTROLE (02/09/2026) — campo por peça só entra COM caminho."""
from __future__ import annotations

import ast
import inspect
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.daemon import sensor_hub as sensor_hub_module
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.integrations import audio_control
from hefesto_dualsense4unix.profiles import manager as manager_module
from hefesto_dualsense4unix.profiles.manager import (
    ProfileManager,
    _controllers_to_rumble_scales,
    _controllers_to_specs,
)
from hefesto_dualsense4unix.profiles.schema import (
    ControllerMicOverride,
    ControllerOverrides,
    ControllerRumbleOverride,
    ControllerSensoresOverride,
    LedsConfig,
    MatchAny,
    Profile,
    ProfileSpeakerConfig,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)
from tests.unit.test_por_unidade_01_todas_as_abas import BRANCO, _StoreSemTrava


@dataclass(frozen=True)
class ConsumidorPorUnidade:
    """Quem lê este campo POR PEÇA, e o que ele faz chegar ao aparelho."""

    funcao: str
    chega_em: str


_CONSUMIDOR: dict[str, ConsumidorPorUnidade] = {
    "leds": ConsumidorPorUnidade(
        funcao="_controllers_to_specs",
        chega_em="OutputSpec por MAC, com a cor já escalada pelo brilho",
    ),
    "triggers": ConsumidorPorUnidade(
        funcao="_controllers_to_specs",
        chega_em="OutputSpec por MAC, com o efeito de L2/R2 daquela peça",
    ),
    "rumble": ConsumidorPorUnidade(
        funcao="_controllers_to_rumble_scales",
        chega_em="{uniq: fator}, aplicado na saída de cada handle",
    ),
    "speaker": ConsumidorPorUnidade(
        funcao="apply_controller_speakers",
        chega_em="apply_speaker(uniq=...) → set_speaker_volume(uniq=...)",
    ),
    "mic": ConsumidorPorUnidade(
        funcao="apply_controller_mics",
        chega_em="apply_mic(uniq=...) → apply_profile_mic(volume, uniq=...)",
    ),
    "sensores": ConsumidorPorUnidade(
        funcao="apply_controller_sensores",
        chega_em=(
            "REGISTRO.definir(uniq) → a janela de motion daquela peça sai do "
            "vpad com os 6 bytes do sensor zerados, e o nó evdev dela fica "
            "grabado"
        ),
    ),
    "mascara": ConsumidorPorUnidade(
        funcao="apply_controller_mascaras",
        chega_em=(
            "set_mask(uniq) → mascara_efetiva(uniq) devolve a do perfil, e o "
            "vpad daquela peça nasce (ou é recriado) com o VID/PID dela"
        ),
    ),
    "movimento": ConsumidorPorUnidade(
        funcao="_controllers_to_miras",
        chega_em=(
            "{uniq: arranjo}, depositado no store por definir_por_peca e "
            "perguntado pelo tique com o uniq de cada jogador (da_peca)"
        ),
    ),
}


def _campos_sem_consumidor(
    campos: set[str], classificacao: dict[str, ConsumidorPorUnidade]
) -> list[str]:
    """Campos do esquema que ninguém lê por peça. Função pura, testada abaixo."""
    return sorted(campos - set(classificacao))


def _consumidores_orfaos(
    campos: set[str], classificacao: dict[str, ConsumidorPorUnidade]
) -> list[str]:
    """Entradas que sobraram de um campo removido. Função pura, testada abaixo."""
    return sorted(set(classificacao) - campos)


def test_a_classificacao_cobre_o_esquema_nos_dois_sentidos() -> None:
    """Campo sem consumidor reprova; consumidor órfão reprova."""
    campos = set(ControllerOverrides.model_fields)
    sem_dono = _campos_sem_consumidor(campos, _CONSUMIDOR)
    assert not sem_dono, (
        "campo(s) de ControllerOverrides sem caminho por unidade: "
        f"{sem_dono}. A ordem não se inverte — primeiro o caminho existir, "
        "depois o campo entrar. A fila do que falta, com a medição de cada um, "
        "está na docstring de ControllerOverrides (profiles/schema.py)."
    )
    orfaos = _consumidores_orfaos(campos, _CONSUMIDOR)
    assert not orfaos, (
        f"consumidor declarado para campo que não existe mais: {orfaos}"
    )


def test_a_regua_sabe_recusar() -> None:
    """As duas contas, exercitadas com um conjunto sintético."""
    sintetico = {"leds", "touchpad"}
    assert _campos_sem_consumidor(sintetico, _CONSUMIDOR) == ["touchpad"]
    assert _consumidores_orfaos(sintetico, _CONSUMIDOR) == [
        "mascara",
        "mic",
        "movimento",
        "rumble",
        "sensores",
        "speaker",
        "triggers",
    ]


def _fonte_da_funcao(nome: str) -> str:
    alvo = getattr(manager_module, nome, None) or getattr(ProfileManager, nome, None)
    assert alvo is not None, f"{nome} não existe em profiles/manager.py"
    return inspect.getsource(alvo)


@pytest.mark.parametrize("campo", sorted(_CONSUMIDOR))
def test_o_consumidor_declarado_le_o_campo(campo: str) -> None:
    """A função nomeada existe e cita o campo — e percorre `controllers`."""
    fonte = _fonte_da_funcao(_CONSUMIDOR[campo].funcao)
    assert re.search(rf"\bcfg\.{campo}\b|getattr\(cfg, \"{campo}\"", fonte), (
        f"{_CONSUMIDOR[campo].funcao} não lê o campo {campo!r} de cada entrada"
    )
    assert "controllers" in fonte, (
        f"{_CONSUMIDOR[campo].funcao} não percorre o mapa por peça"
    )


def _prova_leds(uniq: str) -> object:
    specs = _controllers_to_specs(
        {uniq: ControllerOverrides(leds=LedsConfig(lightbar=(9, 9, 9)))},
        LedsConfig(),
    )
    return None if uniq not in specs else specs[uniq].led


def _prova_triggers(uniq: str) -> object:
    specs = _controllers_to_specs(
        {
            uniq: ControllerOverrides(
                triggers=TriggersConfig(left=TriggerConfig(mode="Off"))
            )
        }
    )
    return None if uniq not in specs else specs[uniq].trigger_left


def _prova_rumble(uniq: str) -> object:
    escalas = _controllers_to_rumble_scales(
        {uniq: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max"))},
        RumbleConfig(),
    )
    return escalas.get(uniq)


def _prova_speaker(uniq: str) -> object:
    alvos: list[str | None] = []

    def applier(volume: int, muted: bool = False, **kw: Any) -> str:
        alvos.append(kw.get("uniq"))
        return "aplicado"

    gerente = ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=_StoreSemTrava(),  # type: ignore[arg-type]
        speaker_applier=applier,
    )
    perfil = Profile(
        name="uma_peca_so",
        match=MatchAny(),
        controllers={uniq: ControllerOverrides(speaker=ProfileSpeakerConfig(volume=40))},
    )
    gerente.apply_controller_speakers(perfil)
    return alvos == [uniq] or None


def _prova_mic(uniq: str) -> object:
    alvos: list[str | None] = []

    def applier(
        volume: int | None = None, muted: bool | None = None, **kw: Any
    ) -> str:
        alvos.append(kw.get("uniq"))
        return "aplicado"

    gerente = ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=_StoreSemTrava(),  # type: ignore[arg-type]
        mic_applier=applier,
    )
    perfil = Profile(
        name="uma_peca_so",
        match=MatchAny(),
        controllers={uniq: ControllerOverrides(mic=ControllerMicOverride(volume=40))},
    )
    gerente.apply_controller_mics(perfil)
    return alvos == [uniq] or None


def _prova_sensores(uniq: str) -> object:
    from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

    REGISTRO.limpar()
    try:
        gerente = ProfileManager(
            controller=object(),  # type: ignore[arg-type]
            store=_StoreSemTrava(),  # type: ignore[arg-type]
        )
        perfil = Profile(
            name="uma_peca_so",
            match=MatchAny(),
            controllers={
                uniq: ControllerOverrides(
                    sensores=ControllerSensoresOverride(giroscopio=False)
                )
            },
        )
        gerente.apply_controller_sensores(perfil)
        return (
            REGISTRO.estado(uniq).giroscopio is False
            and REGISTRO.estado("aa:bb:cc:00:00:ff").giroscopio is True
        ) or None
    finally:
        REGISTRO.limpar()


def _prova_mascara(uniq: str) -> object:
    """A máscara escrita para UMA peça vale só nela (MASCARA-NO-PERFIL-01)."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
        _zerar_registro_de_mascaras,
        mascara_efetiva,
        registro_de_mascaras,
    )

    _zerar_registro_de_mascaras()
    try:
        gerente = ProfileManager(
            controller=object(),  # type: ignore[arg-type]
            store=_StoreSemTrava(),  # type: ignore[arg-type]
        )
        perfil = Profile(
            name="uma_peca_so",
            match=MatchAny(),
            controllers={uniq: ControllerOverrides(mascara="xbox")},
        )
        gerente.apply_controller_mascaras(perfil)
        return (
            mascara_efetiva(uniq, "dualsense") == "xbox"
            and mascara_efetiva("aa:bb:cc:00:00:ff", "dualsense") == "dualsense"
        ) or None
    finally:
        registro_de_mascaras().clear_mask(uniq)
        _zerar_registro_de_mascaras()


def _prova_movimento(uniq: str) -> object:
    """A mira escrita para UMA peça vale só nela (A-MIRA-POR-MOVIMENTO-NA-TELA-01)."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
    from hefesto_dualsense4unix.profiles.schema import ProfileMovimentoConfig

    store = _StoreSemTrava()
    gerente = ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
    )
    perfil = Profile(
        name="uma_peca_so",
        match=MatchAny(),
        controllers={
            uniq: ControllerOverrides(
                movimento=ProfileMovimentoConfig(destino="analogico_direito")
            )
        },
    )
    try:
        gerente.apply_movimento(perfil)
        mesa = rot.ativo(store)
        return (
            rot.da_peca(store, uniq, mesa) is not None
            and rot.da_peca(store, "aa:bb:cc:00:00:ff", mesa) is None
        ) or None
    finally:
        REGISTRO.limpar()


_PROVAS = {
    "leds": _prova_leds,
    "triggers": _prova_triggers,
    "rumble": _prova_rumble,
    "speaker": _prova_speaker,
    "mic": _prova_mic,
    "sensores": _prova_sensores,
    "mascara": _prova_mascara,
    "movimento": _prova_movimento,
}


def test_toda_entrada_da_classificacao_tem_prova() -> None:
    """A tabela de provas acompanha a classificação — senão ela envelhece calada."""
    assert sorted(_PROVAS) == sorted(_CONSUMIDOR)


@pytest.mark.parametrize("campo", sorted(_CONSUMIDOR))
def test_o_valor_da_peca_sai_com_o_endereco_dela(campo: str) -> None:
    """Escrito para UM ``uniq``, o valor sai endereçado àquele ``uniq``."""
    resultado = _PROVAS[campo](BRANCO)
    assert resultado, (
        f"o override de {campo!r} de uma peça não saiu endereçado a ela "
        f"({_CONSUMIDOR[campo].chega_em})"
    )


def test_o_microfone_ja_tem_endereco_por_peca() -> None:
    """As três primitivas do mic por unidade existem — e o ``muted`` já entrou."""
    assert hasattr(EventTopic, "MIC_DA_MESA"), (
        "a borda do botão de mic COM endereço sumiu — sem ela o mic volta a "
        "não saber de qual peça veio o toque"
    )
    assert "uniq" in inspect.signature(audio_control.fonte_de_captura_do_uniq).parameters
    assert "uniq" in inspect.signature(
        PyDualSenseController.set_microphone_mute
    ).parameters


def test_o_volume_do_mic_vale_por_peca_e_a_fiacao_continua_inteira() -> None:
    """ELA DISSE A PALAVRA — 03/09/2026 — e este fio trocou de lado.

    Ele nasceu vigiando uma PORTA FECHADA: *"o campo não entra por decurso de
    prazo: entra quando ela disser"*, e a instrução no corpo era literal —
    *"se foi a palavra dela, apague este teste"*. Ela disse: *"manda a ver em
    tudo que falta por favor"*, depois de ter posto o alvo do produto em uma
    frase no mesmo dia: *"4 controles funcionarem no mesmo modo com configs
    diferentes"*. Com dois DualSense no cabo há DUAS placas de som
    (MIC-DA-MESA-CHEIA-01), e o ganho de captura é exatamente uma config que
    difere por peça.

    **APAGAR SERIA PERDER A METADE QUE AINDA IMPORTA.** A porta abriu; a FIAÇÃO
    que a abertura pressupõe continua tendo de estar de pé, e ela é frágil de um
    jeito específico: `apply_profile_mic` não pode CAIR para a rota global
    quando o `uniq` não resolve. A rota global devolve a PRIMEIRA fonte de
    captura da lista — escrever nela seria mexer no microfone do vizinho, com o
    agravante de parecer curado. É o erro fácil de cometer escrevendo um `or`.

    Então o teste guarda hoje as TRÊS coisas de uma vez: o campo existe, o
    applier chama a rota por unidade, e não há queda para a global.
    """
    assert "volume" in ControllerMicOverride.model_fields, (
        "o `volume` saiu do override por peça — ela mandou abri-lo em "
        "03/09/2026, e sem ele o ganho de captura volta a ser um só para a "
        "mesa inteira")
    assert ControllerMicOverride.model_validate({"volume": 50}).volume == 50

    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.schema import ProfileMicConfig

    for modelo in (ControllerMicOverride, ProfileMicConfig):
        assert "volume" in modelo.model_fields, (
            f"{modelo.__name__} perdeu o campo `volume` — sem ele a recusa "
            "abaixo passaria a ser 'campo desconhecido', que é outro defeito")
        for fora_da_faixa, esperado in ((-1, "greater_than_equal"),
                                        (101, "less_than_equal")):
            with pytest.raises(ValidationError) as e:
                modelo.model_validate({"volume": fora_da_faixa})
            tipos = {d["type"] for d in e.value.errors()}
            assert esperado in tipos, (
                f"{modelo.__name__} recusou {fora_da_faixa} por {tipos}, e o "
                f"esperado era `{esperado}` — a faixa 0..100 caiu")

    arvore = ast.parse(textwrap.dedent(inspect.getsource(Daemon.apply_profile_mic)))
    chamadas = [n for n in ast.walk(arvore)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert any(c.func.id == "fonte_de_captura_do_uniq" for c in chamadas), (
        "o applier deixou de CHAMAR `fonte_de_captura_do_uniq` — sem isso o "
        "volume por peça cai no microfone do vizinho, e o campo que acabou de "
        "abrir passa a gravar sobre a placa de som errada"
    )
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.BoolOp) and isinstance(no.op, ast.Or)):
            continue
        nomes = {c.func.id for c in ast.walk(no)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        assert "fonte_de_captura_do_uniq" not in nomes, (
            "o applier caiu para a rota global com um `or` — sem fonte daquele "
            "controle ninguém escreve, que é o contrário de escrever na "
            "primeira da lista"
        )


def test_o_applier_do_mic_por_peca_repassa_o_volume() -> None:
    """E o campo CHEGA à peça — abrir a borda sem isso seria o pior dos dois."""
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    vistos: list[tuple[str | None, int | None]] = []

    class _Mgr(ProfileManager):
        def apply_mic(self, profile, *, origin="manual", uniq=None):  # type: ignore[override]
            secao = getattr(profile, "mic", None)
            vistos.append((uniq, getattr(secao, "volume", None)))
            return "aplicado"

    uniq = "aa:bb:cc:00:00:07"
    perfil = Profile(
        name="p", match=MatchAny(), priority=1,
        controllers={uniq: ControllerOverrides(
            mic=ControllerMicOverride(volume=33))},
    )
    mgr = _Mgr.__new__(_Mgr)
    saida = ProfileManager.apply_controller_mics(mgr, perfil)

    (chave,) = perfil.controllers
    assert vistos == [(chave, 33)], (
        f"o volume por peça não chegou ao applier: {vistos}")
    assert saida == {f"mic:{chave}": "aplicado"}


def test_o_interruptor_do_botao_de_mic_continua_um_por_maquina() -> None:
    """``mic_button_toggles_system`` não consulta ``uniq`` nenhum."""
    from hefesto_dualsense4unix.daemon.subsystems import hotkey as hotkey_module

    fonte = inspect.getsource(hotkey_module.mic_button_loop)
    assert "mic_button_toggles_system" in fonte, (
        "o laço do botão de mic deixou de ler o interruptor — confira se ele "
        "virou por peça antes de acreditar que este fio ainda mede algo"
    )
    assert not re.search(
        r"mic_button_toggles_system[^\n]*uniq|uniq[^\n]*mic_button_toggles_system",
        fonte,
    ), "o interruptor passou a ser consultado por peça"
    with pytest.raises(ValueError, match="MÁQUINA"):
        ControllerMicOverride.model_validate({"button_toggles_system": True})


def test_o_interruptor_de_sensor_existe_e_e_por_peca() -> None:
    """O sensor SAIU da fila em 04/09/2026 — e esta régua virou de lado."""
    publicos = {
        nome
        for nome, _ in inspect.getmembers(sensor_hub_module.SensorHub, inspect.isfunction)
        if not nome.startswith("_")
    }
    assert publicos == {
        "aceleracao_do_movimento",
        "angulo_do_movimento",
        "entradas",
        "grab_do_movimento",
        "hz_do_movimento",
        "leitura",
        "reconciliar",
        "stop_all",
        "toque_da_peca",
        "velocidade_do_movimento",
    }, f"o SensorHub mudou de superfície pública: {sorted(publicos)}"

    from hefesto_dualsense4unix.daemon import ipc_handlers, ipc_server

    fonte_ipc = Path(inspect.getsourcefile(ipc_server) or "").read_text(encoding="utf-8")
    metodos = set(re.findall(r'"([a-z_]+\.[a-z_]+)":\s*self\._handle', fonte_ipc))
    assert "sensor.set" in metodos, (
        "o interruptor de sensor sumiu do IPC — sem ele o campo `sensores` do "
        "perfil vira a tela prometendo um botão que não desliga nada"
    )

    corpo = inspect.getsource(ipc_handlers.IpcHandlersMixin._handle_sensor_set)
    for chave in ("alcance", "ressalva", "giroscopio", "acelerometro"):
        assert f'"{chave}"' in corpo, (
            f"a resposta do sensor.set deixou de trazer {chave!r} — e é por "
            "ela que a tela sabe QUAL metade do interruptor pegou"
        )


def test_a_entrada_continua_de_um_controle_so() -> None:
    """Mouse, teclado e ações de botão esbarram no mesmo pipeline único.

    ``read_state`` lê o PRIMÁRIO e o ``Daemon`` tem UM device de cada. Guardar
    por controle é fácil; fazer valer exige ler cada peça e despachar para o
    device dela — é o item mais caro da fila, e destrava cinco campos de uma
    vez (``mouse``, ``key_bindings``, ``button_actions``, ``teclado_emulado``,
    ``suppress_desktop_emulation``).

    VERMELHO AQUI É BOA NOTÍCIA: a entrada virou por unidade.
    """
    anotacoes = getattr(Daemon, "__annotations__", {})
    assert "_mouse_device" in anotacoes and "_keyboard_device" in anotacoes
    for slot in ("_mouse_device", "_keyboard_device"):
        assert "dict" not in str(anotacoes[slot]).lower(), (
            f"{slot} virou um mapa — a emulação passou a ter um device por "
            "peça, e os cinco campos de entrada podem entrar no esquema"
        )
