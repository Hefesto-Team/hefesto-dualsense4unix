"""PERFIL-POR-CONTROLE (02/09/2026) — campo por peça só entra COM caminho.

O QUE ELA DECIDIU, e é o que abre esta régua
---------------------------------------------
*"acelerômetro, giroscópio, e todas as demais features. **é tudo mesmo**"* — o
perfil por controle passa a ser TUDO, e a lista de exclusões que morava na
docstring de ``ControllerOverrides`` caiu com ela.

O QUE A DECISÃO **NÃO** DERRUBA, e é o defeito que este arquivo existe para
impedir: **um campo que grava e ninguém lê é pior que campo nenhum.** Ele faz a
tela prometer — a coluna da aba Perfis acende dizendo *"este controle tem
ajuste próprio"* sobre um valor que nada aplica, e a próxima pessoa gasta uma
tarde procurando o defeito no lugar errado. A ordem, então, não se inverte:
primeiro o caminho por unidade EXISTIR, depois o campo entrar no esquema.

POR QUE ESTA RÉGUA E NÃO A QUE JÁ EXISTIA
------------------------------------------
``test_toda_secao_de_perfil_tem_quem_a_aplique`` classifica
``Profile.model_fields`` — o perfil INTEIRO. Ela é exaustiva e morde, e
**ControllerOverrides não passa por ela**: o mapa ``controllers`` é UM campo do
``Profile``, e o que está DENTRO de cada entrada nunca foi contado. Um campo
novo aqui entra sem uma linha vermelha em lugar nenhum — que é exatamente o
buraco por onde a leva de hoje passaria, com a decisão dela na mão e nove
seções para trazer.

O QUE CADA TESTE VIGIA
-----------------------
1. a classificação bate com ``ControllerOverrides.model_fields`` nos DOIS
   sentidos: campo sem consumidor reprova, consumidor órfão reprova;
2. o consumidor declarado EXISTE e LÊ o campo — derivado da fonte do gerente,
   não digitado aqui;
3. o consumidor ENDEREÇA a peça: um perfil que escreve o campo para UM ``uniq``
   produz saída carregando aquele ``uniq``. É o que separa *"guardei"* de
   *"chega ao aparelho"*;
4. a régua sabe RECUSAR — as duas contas são funções puras, exercitadas com um
   conjunto sintético. Régua que só sabe passar não é régua;
5. **os fios de gatilho da fila**: o que hoje IMPEDE cada campo de entrar está
   afirmado como medição, não como opinião. Quando um deles ficar vermelho, a
   notícia é boa — o caminho nasceu, e a mensagem diz qual campo trazer.

**O PRIMEIRO FIO QUEIMOU EM 03/09/2026, e é assim que se lê esta régua
funcionando.** O ``mic`` era o item 1 da fila; a decisão dela
(MIC-QUINTO-AJUSTE-01) mandou o microfone virar o quinto ajuste por controle, a
costura do gerente foi feita (``apply_controller_mics``) e o ``muted`` entrou.
Os outros dois campos do microfone continuam FORA, cada um com o seu fio de
gatilho abaixo — e a recusa deles agora mora na BORDA de
``ControllerMicOverride``, com a razão na mensagem em vez do ``extra_forbidden``
cru. **A granularidade da fila desceu de SEÇÃO para CAMPO**, e isso é o
esperado: o caminho por unidade não nasce inteiro de uma vez.

MORDIDA (o que arrancar para ver reprovar): acrescente ``sensors: bool | None =
None`` a ``ControllerOverrides`` sem tocar em mais nada. O teste 1 aponta o
campo pelo nome e diz que ele não tem quem o leia por peça.

Endereços de rádio: faixa SINTÉTICA da casa, reusada do banco de provas do
backend (``aabbcc…``) — nunca o OUI de um aparelho real.
"""
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
    LedsConfig,
    MatchAny,
    Profile,
    ProfileSpeakerConfig,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)
from tests.unit.test_por_unidade_01_todas_as_abas import BRANCO, _StoreSemTrava

# ---------------------------------------------------------------------------
# A CLASSIFICAÇÃO — exaustiva, e é ela que ninguém contorna em silêncio
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsumidorPorUnidade:
    """Quem lê este campo POR PEÇA, e o que ele faz chegar ao aparelho."""

    #: a função do `profiles/manager.py` que percorre `profile.controllers`.
    funcao: str
    #: em uma frase, o que sai dela com o endereço junto — o vocabulário de
    #: quem lê o defeito, não o nome do parâmetro.
    chega_em: str


#: Um campo de `ControllerOverrides` por entrada. Campo novo que não esteja
#: aqui reprova por estar SEM CONSUMIDOR — nunca por estar numa denylist.
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
        chega_em="apply_mic(uniq=...) → set_microphone_mute(uniq=...)",
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
    """Campo sem consumidor reprova; consumidor órfão reprova.

    MORDIDA: acrescente um campo qualquer a ``ControllerOverrides`` sem lhe dar
    consumidor — este teste o aponta pelo nome.
    """
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
    """As duas contas, exercitadas com um conjunto sintético.

    Sem isto, um erro nas duas funções puras faria o teste acima passar em
    silêncio para sempre — o formato *régua que se confere contra ela mesma*.
    """
    sintetico = {"leds", "sensors"}
    assert _campos_sem_consumidor(sintetico, _CONSUMIDOR) == ["sensors"]
    assert _consumidores_orfaos(sintetico, _CONSUMIDOR) == [
        "mic",
        "rumble",
        "speaker",
        "triggers",
    ]


# ---------------------------------------------------------------------------
# O CONSUMIDOR EXISTE E LÊ O CAMPO — derivado da fonte, não digitado
# ---------------------------------------------------------------------------


def _fonte_da_funcao(nome: str) -> str:
    alvo = getattr(manager_module, nome, None) or getattr(ProfileManager, nome, None)
    assert alvo is not None, f"{nome} não existe em profiles/manager.py"
    return inspect.getsource(alvo)


@pytest.mark.parametrize("campo", sorted(_CONSUMIDOR))
def test_o_consumidor_declarado_le_o_campo(campo: str) -> None:
    """A função nomeada existe e cita o campo — e percorre `controllers`.

    MORDIDA: troque o nome da função na classificação por um vizinho que não
    lê aquele campo (``_controllers_to_led_scales`` para ``speaker``, por
    exemplo) e veja reprovar.
    """
    fonte = _fonte_da_funcao(_CONSUMIDOR[campo].funcao)
    assert re.search(rf"\bcfg\.{campo}\b|getattr\(cfg, \"{campo}\"", fonte), (
        f"{_CONSUMIDOR[campo].funcao} não lê o campo {campo!r} de cada entrada"
    )
    assert "controllers" in fonte, (
        f"{_CONSUMIDOR[campo].funcao} não percorre o mapa por peça"
    )


# ---------------------------------------------------------------------------
# O CONSUMIDOR ENDEREÇA A PEÇA — é o que separa "guardei" de "chegou"
# ---------------------------------------------------------------------------


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
        controllers={uniq: ControllerOverrides(mic=ControllerMicOverride(muted=True))},
    )
    gerente.apply_controller_mics(perfil)
    return alvos == [uniq] or None


_PROVAS = {
    "leds": _prova_leds,
    "triggers": _prova_triggers,
    "rumble": _prova_rumble,
    "speaker": _prova_speaker,
    "mic": _prova_mic,
}


def test_toda_entrada_da_classificacao_tem_prova() -> None:
    """A tabela de provas acompanha a classificação — senão ela envelhece calada."""
    assert sorted(_PROVAS) == sorted(_CONSUMIDOR)


@pytest.mark.parametrize("campo", sorted(_CONSUMIDOR))
def test_o_valor_da_peca_sai_com_o_endereco_dela(campo: str) -> None:
    """Escrito para UM ``uniq``, o valor sai endereçado àquele ``uniq``.

    MORDIDA: em ``_controllers_to_specs``, troque a chave ``out[uniq]`` por uma
    chave fixa qualquer; em ``apply_controller_speakers``, tire o
    ``uniq=str(uniq)`` da chamada. Nos dois casos o dado continua sendo
    calculado e deixa de ter dono — que é o defeito, e não a ausência do valor.
    """
    resultado = _PROVAS[campo](BRANCO)
    assert resultado, (
        f"o override de {campo!r} de uma peça não saiu endereçado a ela "
        f"({_CONSUMIDOR[campo].chega_em})"
    )


# ---------------------------------------------------------------------------
# OS FIOS DE GATILHO DA FILA — o que hoje impede cada campo de entrar
#
# Estes cinco afirmam MEDIÇÕES, não opiniões. Vermelho aqui é boa notícia: o
# caminho por unidade nasceu, e a mensagem diz qual campo trazer para o
# esquema. A fila por extenso, ordenada por custo, está na docstring de
# `ControllerOverrides`.
# ---------------------------------------------------------------------------


def test_o_microfone_ja_tem_endereco_por_peca() -> None:
    """As três primitivas do mic por unidade existem — e o ``muted`` já entrou.

    Isto DERRUBA a frase que morava na docstring do esquema: *"o
    ``EventTopic.BUTTON_DOWN`` não carrega uniq, então o laço do mic não sabe
    de qual peça veio o toque"*. Desde MIC-DA-MESA-ELEICAO-01 (01/09/2026) o
    gesto do microfone não passa mais pelo ``BUTTON_DOWN``: ele tem tópico
    próprio, e o tópico carrega o endereço.

    A costura do gerente foi feita em 03/09/2026 (MIC-QUINTO-AJUSTE-01,
    ``apply_controller_mics``) e o ``muted`` é campo de
    ``ControllerMicOverride``. As duas que sobram estão nomeadas na fila da
    docstring do esquema e cada uma tem o seu fio de gatilho abaixo. Este teste
    fixa o que JÁ existe para que não se reaprenda de novo que "não dá".
    """
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
    # 1. A PORTA ABRIU.
    assert "volume" in ControllerMicOverride.model_fields, (
        "o `volume` saiu do override por peça — ela mandou abri-lo em "
        "03/09/2026, e sem ele o ganho de captura volta a ser um só para a "
        "mesa inteira")
    assert ControllerMicOverride.model_validate({"volume": 50}).volume == 50

    # 2. E A FAIXA É A MESMA DO GLOBAL, lida do dono e não digitada aqui.
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.schema import ProfileMicConfig

    # A RECUSA TEM DE SER POR FAIXA, e não por o campo não existir — a
    # diferença foi medida numa mordida de 03/09/2026 que NÃO mordeu. Eu
    # arranquei `volume: int | None = Field(...)` do arquivo com um `replace`
    # de UMA ocorrência, e a linha existe DUAS vezes (aqui e em
    # `ProfileMicConfig`): saiu a do GLOBAL. Os testes continuaram verdes —
    # `extra="forbid"` recusava `{"volume": -1}` por o campo ter sumido, e a
    # asserção `pytest.raises(ValidationError)` não sabe distinguir os dois
    # casos. Verde sobre a cura arrancada é exatamente o que uma mordida existe
    # para impedir.
    #
    # Então o tipo do erro é conferido: `greater_than_equal`/`less_than_equal`
    # é faixa; `extra_forbidden` é campo inexistente, e reprova aqui.
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

    # 3. A FIAÇÃO. LÊ-SE A ÁRVORE, NÃO O TEXTO — e esta linha custou uma mordida
    # para nascer. A primeira versão fazia `"fonte_de_captura_do_uniq" in
    # inspect.getsource(...)`, e passou VERDE com a costura inteiramente
    # arrancada: o nome aparece no comentário de doze linhas que explica a
    # escolha, então a régua lia a PROSA e dizia que era fiação. É a forma exata
    # que esta casa mais pegou — *a régua confunde a PALAVRA com o ATO*.
    arvore = ast.parse(textwrap.dedent(inspect.getsource(Daemon.apply_profile_mic)))
    chamadas = [n for n in ast.walk(arvore)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert any(c.func.id == "fonte_de_captura_do_uniq" for c in chamadas), (
        "o applier deixou de CHAMAR `fonte_de_captura_do_uniq` — sem isso o "
        "volume por peça cai no microfone do vizinho, e o campo que acabou de "
        "abrir passa a gravar sobre a placa de som errada"
    )
    # 4. A QUEDA PARA A ROTA GLOBAL É O QUE NÃO PODE VOLTAR. O `or` a
    # reintroduziria em silêncio; o `if uniq else` é o que separa os dois — e a
    # diferença só existe na árvore, porque as duas formas dizem os mesmos nomes.
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
    """E o campo CHEGA à peça — abrir a borda sem isso seria o pior dos dois.

    *"Campo que grava e ninguém lê é pior que campo nenhum"* — é o contrato do
    topo de `ControllerOverrides`, e a régua que o sustenta é esta.

    `apply_controller_mics` monta uma VISTA do perfil com o override no lugar da
    seção global (`model_copy(update={"mic": secao})`) e chama `apply_mic`, que
    lê a seção por `getattr(secao, "volume"/"muted", None)`. O `volume` novo
    passa por esse caminho sem uma linha a mais — e é justamente isso que este
    teste prova, em vez de supor.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    vistos: list[tuple[str | None, int | None]] = []

    class _Mgr(ProfileManager):
        def apply_mic(self, profile, *, origin="manual", uniq=None):  # type: ignore[override]
            secao = getattr(profile, "mic", None)
            vistos.append((uniq, getattr(secao, "volume", None)))
            return "aplicado"

    uniq = "aa:bb:cc:00:00:07"  # forjado, faixa de fixture
    perfil = Profile(
        name="p", match=MatchAny(), priority=1,
        controllers={uniq: ControllerOverrides(
            mic=ControllerMicOverride(volume=33))},
    )
    mgr = _Mgr.__new__(_Mgr)
    saida = ProfileManager.apply_controller_mics(mgr, perfil)

    # A CHAVE É A NORMALIZADA, e ela é PERGUNTADA ao perfil — não digitada. O
    # esquema canoniza o `uniq` (doze hexadecimais, sem separador) no load, e um
    # teste que escrevesse `aa:bb:cc:...` do lado direito estaria afirmando um
    # formato que o produto não usa. Descobri isto aqui: a primeira versão
    # comparava com o endereço COM dois-pontos e reprovou.
    (chave,) = perfil.controllers
    assert vistos == [(chave, 33)], (
        f"o volume por peça não chegou ao applier: {vistos}")
    assert saida == {f"mic:{chave}": "aplicado"}


def test_o_interruptor_do_botao_de_mic_continua_um_por_maquina() -> None:
    """``mic_button_toggles_system`` não consulta ``uniq`` nenhum.

    Quem o lê é ``hotkey.mic_button_loop``, em ``daemon.config``, que é um por
    máquina. Guardá-lo por peça faria quatro controles gravarem quatro opiniões
    sobre um interruptor só — por isso ``ControllerMicOverride`` o recusa na
    borda, e a mensagem diz onde ele continua valendo.

    VERMELHO AQUI É BOA NOTÍCIA: o laço passou a consultar o override daquele
    ``uniq``. Traga ``button_toggles_system`` para ``ControllerMicOverride`` e
    apague este teste.
    """
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


def test_os_sensores_nao_tem_por_onde_ser_desligados() -> None:
    """O hub publica por ``uniq`` e só LÊ; o IPC não tem método de sensor.

    O giroscópio e o acelerômetro têm caminho de LEITURA por peça — e leitura
    não é aplicação. Um campo ``sensors`` no perfil hoje seria a tela
    prometendo um botão que não desliga nada, em transporte nenhum.

    VERMELHO AQUI É BOA NOTÍCIA: o interruptor nasceu (``sensors.set`` no IPC
    ou um método de escrita no hub). Traga ``ProfileSensorsConfig`` para o
    ``Profile`` e para ``ControllerOverrides`` — é a ONDA-CONTROLES-07.
    """
    publicos = {
        nome
        for nome, _ in inspect.getmembers(sensor_hub_module.SensorHub, inspect.isfunction)
        if not nome.startswith("_")
    }
    assert publicos == {"leitura", "reconciliar", "stop_all"}, (
        f"o SensorHub ganhou método público novo: {sorted(publicos)}"
    )

    from hefesto_dualsense4unix.daemon import ipc_server

    fonte_ipc = Path(inspect.getsourcefile(ipc_server) or "").read_text(encoding="utf-8")
    metodos = set(re.findall(r'"([a-z_]+\.[a-z_]+)":\s*self\._handle', fonte_ipc))
    de_sensor = sorted(
        m for m in metodos if re.search(r"sensor|gyro|giro|motion|accel", m)
    )
    assert not de_sensor, f"o IPC ganhou método de sensor: {de_sensor}"


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
    fonte = inspect.getsource(PyDualSenseController.read_state)
    assert "PRIMÁRIO" in fonte, (
        "o comentário que documenta o pipeline único saiu de read_state — "
        "confira se a entrada passou a ser por unidade antes de acreditar"
    )
