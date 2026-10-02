"""POR-UNIDADE-01 (10/08/2026) — o override por peça alcança mais que luz e gatilho."""
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


def test_a_peca_com_intensidade_propria_vibra_diferente_da_outra() -> None:
    """Um ``set_rumble`` broadcast, dois motores com força DIFERENTE."""
    backend, branco, preto = _backend()

    backend.set_rumble_scales({BRANCO: 0.5})
    backend.set_rumble(weak=100, strong=200)

    assert branco.left_motor == [100], "a peça com fator próprio não foi escalada"
    assert branco.right_motor == [50]
    assert preto.left_motor == [200], "a peça SEM opinião não pode ser tocada"
    assert preto.right_motor == [100]


def test_peca_sem_opiniao_recebe_o_par_intacto() -> None:
    """Sem escala registrada, o caminho é byte-idêntico ao de antes de 10/08."""
    backend, branco, preto = _backend()

    backend.set_rumble(weak=255, strong=1)

    assert branco.right_motor == [255]
    assert branco.left_motor == [1]
    assert preto.right_motor == [255]
    assert preto.left_motor == [1]


def test_o_coop_tambem_respeita_a_intensidade_da_peca() -> None:
    """``set_rumble_for`` (a rota do co-op) escala pela MESMA regra."""
    backend, branco, _preto = _backend()

    backend.set_rumble_scales({BRANCO: 0.25})
    assert backend.set_rumble_for(BRANCO, weak=200, strong=100) is True

    assert branco.right_motor == [50]
    assert branco.left_motor == [25]


def test_a_escala_e_relativa_a_politica_global_do_perfil() -> None:
    """O fator é ``mult_da_peça / mult_global`` — nunca o absoluto."""
    escalas = _controllers_to_rumble_scales(
        {PRETO: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max"))},
        RumbleConfig(policy="economia"),
    )
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    assert PRETO in escalas
    assert escalas[PRETO] == pytest.approx(
        RUMBLE_POLICY_MULT["max"] / RUMBLE_POLICY_MULT["economia"]
    )


def test_a_peca_que_concorda_com_o_global_nao_entra_no_mapa() -> None:
    """Fator 1.0 é "sem opinião" — mesma regra da escala de brilho (R-20)."""
    escalas = _controllers_to_rumble_scales(
        {PRETO: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max"))},
        RumbleConfig(policy="max"),
    )
    assert escalas == {}


def test_global_em_auto_pula_a_peca_em_vez_de_prometer() -> None:
    """Denominador MÓVEL não vira fator — e a peça fica com o global."""
    escalas = _controllers_to_rumble_scales(
        {PRETO: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max"))},
        RumbleConfig(policy="auto"),
    )
    assert escalas == {}


class _StoreSemTrava:
    """StateStore mínimo: nenhuma categoria manual armada."""

    manual_override_categories: tuple[str, ...] = ()
    active_profile: str | None = None


def test_cada_peca_recebe_o_proprio_volume_na_ativacao() -> None:
    """Duas unidades, dois volumes, um perfil só — o pedido dela, literal."""
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
        (120, False, None),
        (40, False, BRANCO),
        (220, False, PRETO),
    ]
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


def _entradas_do_disco(caminho: Path) -> dict[str, Any]:
    return json.loads(caminho.read_text(encoding="utf-8"))["controllers"]


def test_a_peca_que_so_opina_sobre_luz_nao_ganha_as_chaves_novas(
    isolated_profiles_dir: Path,
) -> None:
    """O perfil salvo NÃO carrega ``rumble``/``speaker`` em quem não opinou."""
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
    assert entradas[PRETO]["rumble"] == {"policy": "economia"}


def test_o_rascunho_intocado_nao_semeia_campo_novo(
    isolated_profiles_dir: Path,
) -> None:
    """"Salvar Perfil" sem gesto por unidade não inventa mapa nem seção."""
    draft = DraftConfig.default()

    assert draft.to_profile("virgem").controllers is None

    tocado = draft.with_controller_leds(
        BRANCO, draft.leds.model_copy(update={"lightbar_rgb": (200, 0, 0)})
    )
    caminho = save_profile(tocado.to_profile("so_luz"))
    entrada = _entradas_do_disco(caminho)[BRANCO]

    assert set(entrada) == {"leds"}, (
        f"o rascunho semeou seção que ela não pediu: {sorted(entrada)}"
    )


@pytest.mark.parametrize(
    "secao",
    ["mode", "mouse", "key_bindings", "suppress_desktop_emulation"],
    ids=["modo", "mouse", "teclado", "modo_jogo"],
)
def test_o_que_ainda_nao_tem_caminho_nao_entra_no_mapa_por_peca(secao: str) -> None:
    """Os quatro esperam um caminho de aplicação por unidade — e até lá, recusa."""
    with pytest.raises(ValueError, match=r"extra_forbidden|Extra inputs"):
        ControllerOverrides.model_validate({secao: {}})


def test_o_auto_do_rumble_e_recusado_por_peca_com_a_razao_escrita() -> None:
    """``auto`` escala pela BATERIA — e quem a lê é o controle PRIMÁRIO."""
    with pytest.raises(ValueError, match="BATERIA"):
        ControllerRumbleOverride.model_validate({"policy": "auto"})


def test_o_passthrough_e_da_sessao_e_a_borda_recusa() -> None:
    """``passthrough`` não descreve a peça: descreve quem manda na vibração."""
    with pytest.raises(ValueError, match=r"extra_forbidden|Extra inputs"):
        ControllerRumbleOverride.model_validate({"passthrough": False})


class _JanelaFalsa:
    """Dona do rascunho, com o seletor de alvo da aba Status."""

    def __init__(self, alvo: str | None = None) -> None:
        self.draft = DraftConfig.default()
        self._edit_target_uniq = alvo


def test_com_o_seletor_em_todos_o_som_continua_indo_para_o_global() -> None:
    """Quem tem UM controle não pode passar a colecionar override por MAC."""
    janela = _JanelaFalsa(alvo=None)

    registrar_alto_falante_no_rascunho(janela, volume=180, uniq=BRANCO)

    assert janela.draft.speaker.volume == 180
    assert janela.draft.source_controllers in (None, {})


def test_com_a_peca_escolhida_no_seletor_o_som_vira_override_dela() -> None:
    """O gesto que ela fez ESCOLHENDO a peça fica preso ao plástico."""
    janela = _JanelaFalsa(alvo=PRETO)
    janela.draft = janela.draft.with_speaker(100)

    registrar_alto_falante_no_rascunho(janela, volume=240, uniq=PRETO)

    assert janela.draft.speaker.volume == 100, "o global não era o alvo do gesto"
    override = janela.draft.controller_override(PRETO)
    assert override is not None
    assert override.speaker is not None
    assert override.speaker.volume == 240
    assert janela.draft.effective_speaker_for(BRANCO).volume == 100


def test_a_peca_que_volta_a_concordar_com_o_global_perde_o_override() -> None:
    """Concordância não vira registro — a regra COR-04, aplicada ao som."""
    janela = _JanelaFalsa(alvo=PRETO)
    janela.draft = janela.draft.with_speaker(100)

    registrar_alto_falante_no_rascunho(janela, volume=240, uniq=PRETO)
    assert janela.draft.controller_override(PRETO) is not None

    registrar_alto_falante_no_rascunho(janela, volume=100, uniq=PRETO)

    assert janela.draft.controller_override(PRETO) is None
    assert janela.draft.source_controllers in (None, {})


def test_a_aba_rumble_exibe_a_intensidade_da_peca_escolhida() -> None:
    """O que ela vê no seletor é o que o "Salvar Perfil" grava."""
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
    assert draft.effective_rumble_for(PRETO).weak == draft.rumble.weak


def test_o_aplicar_leva_a_intensidade_e_o_som_da_peca() -> None:
    """O payload do botão verde carrega as duas seções novas por peça."""
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
