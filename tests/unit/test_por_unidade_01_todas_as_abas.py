"""POR-UNIDADE-01 (10/08/2026) — o override por peça alcança mais que luz e gatilho.

Pedido dela, textual: *"se eu quiser fazer uma guia específica do perfil X pro
controle branco e outra pro mesmo perfil mas pra um controle preto ele vai
funcionar pra cada um deles dessa forma."* Perguntada sobre quais seções:
**todas as abas**.

O que este arquivo vigia, e por quê cada um:

1. **A VIBRAÇÃO da peça chega ao hardware.** A intensidade por unidade vira um
   FATOR no backend (``set_rumble_scales``), irmão exato da escala de brilho do
   R-20 — e é aplicado na SAÍDA de cada handle. Sem isso, o número ficaria
   guardado no perfil dela sem ninguém ler, que é o defeito mais caro desta
   casa (*a cura escrita e nunca ligada*).

2. **O SOM da peça chega ao controle na ativação.** A fiação por-``uniq`` já
   existia inteira desde a SOM-02/E4 (``apply_speaker(uniq=...)`` →
   ``set_speaker_volume(uniq=...)``) e nunca fora ligada: faltava o perfil ter
   ONDE guardar quem é quem.

3. **O DOWNGRADE continua possível.** O risco central medido desta entrega não
   é o perfil ANTIGO (que valida sem a chave nova), é o perfil NOVO lido por um
   hefesto VELHO: ``extra="forbid"`` faz um campo desconhecido rejeitar o
   ``Profile`` INTEIRO, não só a seção. O antidoto é a OMISSÃO
   (``exclude_unset=True`` por entrada em ``profiles/loader.save_profile``), e
   a regra é nunca semear campo novo por default no rascunho. Os dois testes
   do fim provam a omissão pelos dois lados: o que o disco recebe e o que o
   rascunho intocado produz.

4. **O que NÃO cabe por unidade continua recusado na BORDA.** ``mode``,
   ``mouse``, ``key_bindings`` e ``mic`` não entram no mapa, e o ``auto`` do
   rumble também não — cada um por um motivo escrito no esquema. Recusa no
   load, com mensagem, é a disciplina desta casa; campo aceito-e-ignorado vira
   comportamento errado silencioso meses depois.

MORDIDA (o que arrancar para ver reprovar) — cada teste diz a sua no corpo.
MAC mascarado pela regra da casa: octetos 4 e 5 zerados.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.draft_config import (
    DraftConfig,
    registrar_alto_falante_no_rascunho,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import (
    ProfileManager,
    _controllers_to_rumble_scales,
)
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    ControllerRumbleOverride,
    LedsConfig,
    MatchAny,
    Profile,
    ProfileSpeakerConfig,
    RumbleConfig,
)
from tests.unit.test_backend_multi_controller import (
    KEY_1,
    KEY_2,
    UNIQ_1,
    UNIQ_2,
    _FakeHandle,
    _null_evdev,
)

#: Os dois controles dela, com a máscara da casa (octetos 4 e 5 zerados).
BRANCO = UNIQ_1
PRETO = UNIQ_2


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _backend() -> tuple[Any, _FakeHandle, _FakeHandle]:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    inst = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    inst._handles = {KEY_1: h1, KEY_2: h2}
    inst._primary_key = KEY_1
    return inst, h1, h2


# ---------------------------------------------------------------------------
# 1. A VIBRAÇÃO da peça chega ao hardware
# ---------------------------------------------------------------------------


def test_a_peca_com_intensidade_propria_vibra_diferente_da_outra() -> None:
    """Um ``set_rumble`` broadcast, dois motores com força DIFERENTE.

    É a metade que faltava: sem escala por peça, o mesmo par (weak, strong)
    chegava idêntico nos dois controles e "o branco vibra mais fraco que o
    preto" não tinha como existir.

    MORDIDA: no ``set_rumble`` do backend, trocar
    ``self._escalar_rumble(key, weak, strong)`` por ``(weak, strong)`` (ou
    voltar o ``_for_each_com_key`` para o ``_for_each`` sem key) — o branco
    passa a receber 200 e a igualdade abaixo reprova.
    """
    backend, branco, preto = _backend()

    backend.set_rumble_scales({BRANCO: 0.5})
    backend.set_rumble(weak=100, strong=200)

    # setLeftMotor recebe o STRONG; setRightMotor recebe o WEAK (API pydualsense).
    assert branco.left_motor == [100], "a peça com fator próprio não foi escalada"
    assert branco.right_motor == [50]
    assert preto.left_motor == [200], "a peça SEM opinião não pode ser tocada"
    assert preto.right_motor == [100]


def test_peca_sem_opiniao_recebe_o_par_intacto() -> None:
    """Sem escala registrada, o caminho é byte-idêntico ao de antes de 10/08.

    Não é redundância com o teste acima: ali a segunda peça não tem entrada num
    mapa que EXISTE; aqui o mapa está vazio, que é o estado de todo perfil já
    salvo no disco dela. Um arredondamento novo no caminho de quem não pediu
    nada seria regressão silenciosa em 14 perfis.

    MORDIDA: fazer ``_escalar_rumble`` devolver ``int(weak * 1.0)`` sempre em
    vez de sair cedo quando não há fator — 255 continua 255, mas troque para
    ``0.999`` e a asserção pega.
    """
    backend, branco, preto = _backend()

    backend.set_rumble(weak=255, strong=1)

    assert branco.right_motor == [255]
    assert branco.left_motor == [1]
    assert preto.right_motor == [255]
    assert preto.left_motor == [1]


def test_o_coop_tambem_respeita_a_intensidade_da_peca() -> None:
    """``set_rumble_for`` (a rota do co-op) escala pela MESMA regra.

    Sem isto, a mesma peça vibraria diferente conforme a ROTA — forte no
    co-op, fraca no jogo —, e a incoerência apareceria como "às vezes funciona".

    MORDIDA: no ``set_rumble_for``, voltar a ``handle.setLeftMotor(strong)`` /
    ``handle.setRightMotor(weak)`` sem passar por ``_escalar_rumble``.
    """
    backend, branco, _preto = _backend()

    backend.set_rumble_scales({BRANCO: 0.25})
    assert backend.set_rumble_for(BRANCO, weak=200, strong=100) is True

    assert branco.right_motor == [50]
    assert branco.left_motor == [25]


def test_a_escala_e_relativa_a_politica_global_do_perfil() -> None:
    """O fator é ``mult_da_peça / mult_global`` — nunca o absoluto.

    O valor que chega ao ``set_rumble`` JÁ vem escalado pela política global
    (``apply_rumble_policy`` faz isso em todo caminho de rumble). Registrar o
    absoluto escalaria duas vezes: a peça em "max" dentro de um perfil
    "economia" ficaria mais FRACA que a que não opinou — o oposto do pedido.

    MORDIDA: em ``_controllers_to_rumble_scales``, trocar ``mult / base`` por
    ``mult`` — o fator vira 1.0 (== "sem opinião") e a peça some do mapa.
    """
    escalas = _controllers_to_rumble_scales(
        {PRETO: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max"))},
        RumbleConfig(policy="economia"),
    )
    # max = 1.0, economia = 0.3 -> a peça precisa de 3.33x o que o global já deu.
    assert PRETO in escalas
    assert escalas[PRETO] == pytest.approx(1.0 / 0.3)


def test_a_peca_que_concorda_com_o_global_nao_entra_no_mapa() -> None:
    """Fator 1.0 é "sem opinião" — mesma regra da escala de brilho (R-20).

    MORDIDA: tirar o ``if fator == 1.0: continue`` de
    ``_controllers_to_rumble_scales``.
    """
    escalas = _controllers_to_rumble_scales(
        {PRETO: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max"))},
        RumbleConfig(policy="max"),
    )
    assert escalas == {}


def test_global_em_auto_pula_a_peca_em_vez_de_prometer() -> None:
    """Denominador MÓVEL não vira fator — e a peça fica com o global.

    O ``auto`` resolve pela bateria a cada tick. Um fator contra ele faria a
    peça vibrar de forma imprevisível; prometer isso seria pior do que não
    entregar. É o mesmo eixo da recusa do ``auto`` POR UNIDADE, um andar acima.

    MORDIDA: em ``_controllers_to_rumble_scales``, tratar ``base is None`` como
    ``base = 0.7`` em vez de pular.
    """
    escalas = _controllers_to_rumble_scales(
        {PRETO: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max"))},
        RumbleConfig(policy="auto"),
    )
    assert escalas == {}


# ---------------------------------------------------------------------------
# 2. O SOM da peça chega ao controle na ativação
# ---------------------------------------------------------------------------


class _StoreSemTrava:
    """StateStore mínimo: nenhuma categoria manual armada."""

    manual_override_categories: tuple[str, ...] = ()
    active_profile: str | None = None


def test_cada_peca_recebe_o_proprio_volume_na_ativacao() -> None:
    """Duas unidades, dois volumes, um perfil só — o pedido dela, literal.

    O global escreve em todo mundo (``uniq=None`` = broadcast) e cada override
    reescreve apenas a SUA peça POR CIMA. A ordem é a entrega: invertê-la faria
    o global apagar a peça.

    MORDIDA: apagar a linha ``self.apply_controller_speakers(...)`` de
    ``_apply_appliers`` (``profiles/manager.py``) — sobra só a chamada global e
    a lista abaixo perde as duas entradas com ``uniq``.
    """
    chamadas: list[tuple[int, bool, str | None]] = []

    def applier(
        volume: int,
        muted: bool = False,
        *,
        uniq: str | None = None,
        origin: str = "autoswitch",
        rota: int | None = None,
    ) -> str:
        chamadas.append((volume, muted, uniq))
        return "aplicado"

    manager = ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=_StoreSemTrava(),  # type: ignore[arg-type]
        speaker_applier=applier,
    )
    profile = Profile(
        name="som_por_peca",
        match=MatchAny(),
        speaker=ProfileSpeakerConfig(volume=120),
        controllers={
            BRANCO: ControllerOverrides(speaker=ProfileSpeakerConfig(volume=40)),
            PRETO: ControllerOverrides(speaker=ProfileSpeakerConfig(volume=220)),
        },
    )

    relatorio: dict[str, str] = {}
    manager.apply_speaker(profile, relatorio=relatorio)
    manager.apply_controller_speakers(profile, relatorio=relatorio)

    assert chamadas == [
        (120, False, None),  # o global, em todo mundo
        (40, False, BRANCO),
        (220, False, PRETO),
    ]
    # O relatório diz QUAL peça, para a GUI não fundir tudo num rótulo só.
    assert relatorio[f"speaker:{BRANCO}"] == "aplicado"
    assert relatorio[f"speaker:{PRETO}"] == "aplicado"


def test_a_peca_sem_secao_de_som_nao_escreve_nada() -> None:
    """Ausência de opinião é SILÊNCIO — nunca um volume inventado.

    Tomar a posse dos bytes de áudio de uma peça que não pediu é a armadilha 1
    da SOM-02: a primeira escrita nossa faz o hefesto mandar volume em todo
    report, e o DualSense não devolve o que o firmware tinha.

    MORDIDA: em ``apply_controller_speakers``, trocar o ``if secao is None:
    continue`` por ``secao = secao or profile.speaker``.
    """
    chamadas: list[str | None] = []

    def applier(volume: int, muted: bool = False, **kw: Any) -> str:
        chamadas.append(kw.get("uniq"))
        return "aplicado"

    manager = ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=_StoreSemTrava(),  # type: ignore[arg-type]
        speaker_applier=applier,
    )
    profile = Profile(
        name="so_a_luz",
        match=MatchAny(),
        speaker=ProfileSpeakerConfig(volume=120),
        controllers={BRANCO: ControllerOverrides(leds=LedsConfig(lightbar=(9, 9, 9)))},
    )

    manager.apply_controller_speakers(profile)

    assert chamadas == []


# ---------------------------------------------------------------------------
# 3. O DOWNGRADE — a omissão é o antidoto, e ela tem de sobreviver
# ---------------------------------------------------------------------------


def _entradas_do_disco(caminho: Path) -> dict[str, Any]:
    return json.loads(caminho.read_text(encoding="utf-8"))["controllers"]


def test_a_peca_que_so_opina_sobre_luz_nao_ganha_as_chaves_novas(
    isolated_profiles_dir: Path,
) -> None:
    """O perfil salvo NÃO carrega ``rumble``/``speaker`` em quem não opinou.

    ESTE é o risco central desta entrega, e ele não é o perfil antigo — é o
    DOWNGRADE. Um hefesto velho tem ``extra="forbid"`` no ``ControllerOverrides``
    e, ao ver uma chave que não conhece, rejeita o ``Profile`` INTEIRO: não a
    seção, o perfil. Se toda gravação densificasse as entradas, voltar uma
    versão significaria "todos os perfis dela quebrados", inclusive os 4 que já
    têm bloco ``controllers`` hoje.

    MORDIDA: em ``profiles/loader.save_profile``, tirar o ``exclude_unset=True``
    do dump por entrada — as chaves ``rumble``/``speaker`` aparecem com
    ``null`` e as duas asserções abaixo reprovam.
    """
    profile = Profile(
        name="downgrade",
        match=MatchAny(),
        controllers={
            BRANCO: ControllerOverrides(leds=LedsConfig(lightbar=(1, 2, 3))),
            PRETO: ControllerOverrides(
                rumble=ControllerRumbleOverride(policy="economia")
            ),
        },
    )

    caminho = save_profile(profile)
    entradas = _entradas_do_disco(caminho)

    assert "rumble" not in entradas[BRANCO], (
        "quem só opinou sobre a luz ganhou a chave nova — um hefesto anterior "
        "a 10/08 recusaria o perfil INTEIRO no downgrade"
    )
    assert "speaker" not in entradas[BRANCO]
    assert "speaker" not in entradas[PRETO]
    assert "leds" not in entradas[PRETO]
    # E o que ELA escreveu continua lá, com o valor dela.
    assert entradas[PRETO]["rumble"] == {"policy": "economia"}


def test_o_rascunho_intocado_nao_semeia_campo_novo(
    isolated_profiles_dir: Path,
) -> None:
    """"Salvar Perfil" sem gesto por unidade não inventa mapa nem seção.

    A outra metade da regra: a omissão no disco só protege se o RASCUNHO
    também não semear. Um default novo no ``DraftConfig`` — uma seção
    ``rumble``/``speaker`` nascendo preenchida no override — furaria a proteção
    pela borda de cima, com o ``save_profile`` gravando um campo "explícito"
    que ninguém pediu.

    MORDIDA: dar a ``ControllerOverrides.rumble`` um
    ``default_factory=ControllerRumbleOverride`` no esquema — o mapa passa a
    nascer com a seção e a primeira asserção reprova.
    """
    draft = DraftConfig.default()

    # Sem NENHUM gesto por unidade: o mapa nem existe.
    assert draft.to_profile("virgem").controllers is None

    # Com um gesto de LUZ numa peça: existe o mapa, e SÓ a luz nele.
    tocado = draft.with_controller_leds(
        BRANCO, draft.leds.model_copy(update={"lightbar_rgb": (200, 0, 0)})
    )
    caminho = save_profile(tocado.to_profile("so_luz"))
    entrada = _entradas_do_disco(caminho)[BRANCO]

    assert set(entrada) == {"leds"}, (
        f"o rascunho semeou seção que ela não pediu: {sorted(entrada)}"
    )


# ---------------------------------------------------------------------------
# 4. O que NÃO cabe por unidade é recusado na BORDA, com mensagem
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "secao",
    ["mode", "mouse", "key_bindings", "mic", "suppress_desktop_emulation"],
    ids=["modo", "mouse", "teclado", "microfone", "modo_jogo"],
)
def test_o_que_e_da_sessao_nao_entra_no_mapa_por_peca(secao: str) -> None:
    """Modo, mouse, teclado, mic e modo-jogo não são da peça de plástico.

    Três motivos distintos, todos escritos no esquema: o modo (e a máscara) são
    da SESSÃO por decisão dela em 10/08/2026; mouse e teclado esbarram numa
    MEDIÇÃO — ``read_state`` diz, em comentário de código, que "INPUT vem
    SEMPRE do controle PRIMÁRIO" e a emulação é single-controller por
    construção; o mic esbarra no barramento, que publica ``BUTTON_DOWN`` sem
    ``uniq``, e num alvo (o microfone padrão do sistema) que é um só.

    Recusa na BORDA e não no applier, pela razão de sempre: arquivo inválido é
    rejeitado no load, com mensagem, em vez de virar comportamento errado
    silencioso meses depois.

    MORDIDA: trocar ``extra="forbid"`` por ``extra="allow"`` no
    ``ControllerOverrides``.
    """
    with pytest.raises(ValueError, match=r"extra_forbidden|Extra inputs"):
        ControllerOverrides.model_validate({secao: {}})


def test_o_auto_do_rumble_e_recusado_por_peca_com_a_razao_escrita() -> None:
    """``auto`` escala pela BATERIA — e quem a lê é o controle PRIMÁRIO.

    Aceitá-lo por unidade guardaria no perfil dela uma promessa que o caminho
    do rumble não sabe cumprir: as duas peças escalariam pela bateria da mesma.
    A mensagem tem de DIZER isso — "Input should be 'economia'..." mandaria
    quem lê o arquivo procurar no lugar errado.

    MORDIDA: apagar o validador ``_auto_nao_e_por_unidade`` do esquema.
    """
    with pytest.raises(ValueError, match="BATERIA"):
        ControllerRumbleOverride.model_validate({"policy": "auto"})


def test_o_passthrough_e_da_sessao_e_a_borda_recusa() -> None:
    """``passthrough`` não descreve a peça: descreve quem manda na vibração.

    Ele solta o rumble que a GUI TRAVOU — e a trava
    (``DaemonConfig.rumble_active``) é UMA para o daemon inteiro. Duas unidades
    pedindo passthrough diferente no mesmo perfil não têm resposta honesta.

    MORDIDA: reusar ``RumbleConfig`` (que TEM o campo) no lugar de
    ``ControllerRumbleOverride``.
    """
    with pytest.raises(ValueError, match=r"extra_forbidden|Extra inputs"):
        ControllerRumbleOverride.model_validate({"passthrough": False})


# ---------------------------------------------------------------------------
# 5. A JANELA: o seletor de alvo é quem decide onde a anotação cai
# ---------------------------------------------------------------------------


class _JanelaFalsa:
    """Dona do rascunho, com o seletor de alvo da aba Status."""

    def __init__(self, alvo: str | None = None) -> None:
        self.draft = DraftConfig.default()
        self._edit_target_uniq = alvo


def test_com_o_seletor_em_todos_o_som_continua_indo_para_o_global() -> None:
    """Quem tem UM controle não pode passar a colecionar override por MAC.

    O padrão do seletor é "Todos", e é o estado de quem nunca ouviu falar em
    alvo de edição. Deduzir a peça do CARD em que ela encostou faria todo gesto
    de volume virar override e a seção global nunca mais ser escrita.

    MORDIDA: em ``registrar_alto_falante_no_rascunho``, trocar a condição
    ``alvo and str(alvo) == str(uniq)`` por ``uniq`` sozinho.
    """
    janela = _JanelaFalsa(alvo=None)

    registrar_alto_falante_no_rascunho(janela, volume=180, uniq=BRANCO)

    assert janela.draft.speaker.volume == 180
    assert janela.draft.source_controllers in (None, {})


def test_com_a_peca_escolhida_no_seletor_o_som_vira_override_dela() -> None:
    """O gesto que ela fez ESCOLHENDO a peça fica preso ao plástico.

    E o global não se mexe: é o que faz "o preto mais alto, o resto como está"
    ser dizível.

    MORDIDA: a mesma de cima, ao contrário — apagar o ramo por peça inteiro.
    """
    janela = _JanelaFalsa(alvo=PRETO)
    janela.draft = janela.draft.with_speaker(100)

    registrar_alto_falante_no_rascunho(janela, volume=240, uniq=PRETO)

    assert janela.draft.speaker.volume == 100, "o global não era o alvo do gesto"
    override = janela.draft.controller_override(PRETO)
    assert override is not None
    assert override.speaker is not None
    assert override.speaker.volume == 240
    # E a peça que ela NÃO escolheu segue herdando o global.
    assert janela.draft.effective_speaker_for(BRANCO).volume == 100


def test_a_peca_que_volta_a_concordar_com_o_global_perde_o_override() -> None:
    """Concordância não vira registro — a regra COR-04, aplicada ao som.

    Sem isso, o mapa juntaria entradas idênticas ao global que a ativação
    teria de reaplicar uma a uma, e "voltei tudo ao normal" deixaria rastro
    que só um editor de JSON apaga.

    MORDIDA: em ``with_controller_speaker``, tirar o ramo ``igual_ao_global``.
    """
    janela = _JanelaFalsa(alvo=PRETO)
    janela.draft = janela.draft.with_speaker(100)

    registrar_alto_falante_no_rascunho(janela, volume=240, uniq=PRETO)
    assert janela.draft.controller_override(PRETO) is not None

    registrar_alto_falante_no_rascunho(janela, volume=100, uniq=PRETO)

    assert janela.draft.controller_override(PRETO) is None
    assert janela.draft.source_controllers in (None, {})


def test_a_aba_rumble_exibe_a_intensidade_da_peca_escolhida() -> None:
    """O que ela vê no seletor é o que o "Salvar Perfil" grava.

    ``effective_rumble_for`` é o irmão de ``effective_leds_for``: override da
    peça quando existe, global quando não. Sem ele, trocar de peça no seletor
    deixaria a tela mostrando a intensidade da ANTERIOR.

    MORDIDA: fazer ``effective_rumble_for`` devolver ``self.rumble`` sempre.
    """
    draft = DraftConfig.default().model_copy(
        update={"rumble": DraftConfig.default().rumble.model_copy(
            update={"policy": "economia"}
        )}
    )
    draft = draft.with_controller_rumble(
        PRETO, draft.rumble.model_copy(update={"policy": "max"})
    )

    assert draft.effective_rumble_for(PRETO).policy == "max"
    assert draft.effective_rumble_for(BRANCO).policy == "economia"
    assert draft.effective_rumble_for(None).policy == "economia"
    # weak/strong são o TESTE DE MOTORES e nunca foram do perfil: seguem o global.
    assert draft.effective_rumble_for(PRETO).weak == draft.rumble.weak


def test_o_aplicar_leva_a_intensidade_e_o_som_da_peca() -> None:
    """O payload do botão verde carrega as duas seções novas por peça.

    Sem isto, a escolha por unidade só valeria na PRÓXIMA ativação de perfil —
    ela clicaria no verde e nada mudaria, que é exatamente a queixa
    O-VERDE-NAO-LEVAVA-O-SOM-01 reaberta um nível abaixo.

    MORDIDA: apagar os blocos ``if override.rumble is not None`` e
    ``if override.speaker is not None`` de ``_controllers_to_ipc``.
    """
    draft = DraftConfig.default().with_speaker(100)
    draft = draft.with_controller_rumble(
        PRETO, draft.rumble.model_copy(update={"policy": "max"})
    )
    draft = draft.with_controller_speaker(
        PRETO, draft.speaker.model_copy(update={"volume": 240})
    )

    entrada = draft.to_ipc_dict()["controllers"][PRETO]

    assert entrada["rumble"] == {"policy": "max"}
    assert entrada["speaker"]["volume"] == 240
