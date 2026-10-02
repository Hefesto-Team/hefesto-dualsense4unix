"""O `DraftConfig` sabe escrever as SEIS seções por controle do esquema."""

from __future__ import annotations


from hefesto_dualsense4unix.app.draft_config import DraftConfig, MicDraft
from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

UNIQ = "aabbcc0000ff"

SEM_ESCRITOR: dict[str, str] = {}


def _escritor(secao: str) -> str:
    return f"with_controller_{secao}"


def test_as_seis_secoes_do_esquema_tem_escritor() -> None:
    """A lista vem do ESQUEMA, não daqui — seção nova reprova até ter escritor."""
    faltam = [
        s for s in ControllerOverrides.model_fields
        if s not in SEM_ESCRITOR and not hasattr(DraftConfig, _escritor(s))
    ]
    assert not faltam, (
        f"o esquema declara estas seções por controle e o rascunho não sabe "
        f"escrevê-las: {faltam}. Sem escritor, o que ela escolher no card "
        f"daquela peça não chega ao disco — some no Salvar, calado. Se a "
        f"ausência for deliberada, declare-a em SEM_ESCRITOR com a razão.")


def test_o_mic_grava_os_dois_campos_daquela_peca() -> None:
    """``volume`` e ``gain`` viram override DELA, e não do vizinho."""
    d = DraftConfig.default().with_controller_mic(
        UNIQ, MicDraft(muted=True, volume=40, gain=30))
    secao = d.controller_override(UNIQ).mic
    assert secao is not None and secao.volume == 40 and secao.gain == 30
    assert "muted" not in secao.model_fields_set, (
        "o rascunho escreveu o mudo do microfone no perfil — o mudo é do controle")


def test_o_mic_nao_grava_o_botao_do_sistema() -> None:
    """``button_toggles_system`` fica FORA — não tem caminho por unidade."""
    d = DraftConfig.default().with_controller_mic(
        UNIQ, MicDraft(volume=40, button_toggles_system=True))
    secao = d.controller_override(UNIQ).mic
    assert "button_toggles_system" not in secao.model_fields_set


def test_valor_igual_ao_global_nao_vira_override() -> None:
    """Repetir o global não cria override — seria dívida que reaparece sozinha."""
    base = DraftConfig.default().model_copy(
        update={"mic": MicDraft(volume=55, muted=True)})
    d = base.with_controller_mic(UNIQ, MicDraft(
        muted=base.mic.muted, volume=base.mic.volume))
    override = d.controller_override(UNIQ)
    assert override is None or override.mic is None, (
        "um override que repete o global some da tela e volta a divergir "
        "assim que o global mudar")


def test_o_mic_efetivo_herda_o_global_campo_a_campo() -> None:
    """Override só do ``gain`` não pode zerar o volume que o global carrega."""
    base = DraftConfig.default().model_copy(
        update={"mic": MicDraft(volume=77, gain=50)})
    d = base.with_controller_mic(UNIQ, MicDraft(gain=30, volume=77))
    efetivo = d.effective_mic_for(UNIQ)
    assert efetivo.gain == 30
    assert efetivo.volume == 77, "o volume do global sumiu num override parcial"


