"""O `DraftConfig` sabe escrever as SEIS seções por controle do esquema.

MEDIDO EM 05/09/2026, atrás do pedido dela — *"pra cada perfil e dentro dele
cada config pra cada controle"*. O ``ControllerOverrides`` do esquema tem seis
seções (``leds``, ``triggers``, ``rumble``, ``speaker``, ``mic``, ``sensores``)
e o rascunho sabia escrever **quatro**: ``with_controller_mic`` e
``with_controller_sensores`` tinham ZERO ocorrências em ``src/`` e em
``tests/``. As duas seções só atravessavam pelo passthrough byte-idêntico de
``source_controllers`` — o que basta para não PERDER o que já estava no disco,
e não basta para GRAVAR o que ela acabou de escolher no card daquela peça.

ESTA RÉGUA MORDE NOS DOIS SENTIDOS:

* pela LISTA — o esquema é a fonte, e uma sétima seção que nasça lá reprova
  aqui até ganhar escritor. É o oposto de uma lista à mão, que envelhece calada
  (foi assim que estas duas ficaram quatro dias sem ninguém ver);
* pelo COMPORTAMENTO — cada escritor grava o que ela mexeu, não grava o que
  repete o global, e limpa quando ela desiste.

A MORDIDA: apague ``with_controller_mic`` do ``draft_config.py`` e
:func:`test_as_seis_secoes_do_esquema_tem_escritor` reprova nomeando a seção
órfã; troque o ``!=`` do global por um ``==`` e
:func:`test_valor_igual_ao_global_nao_vira_override` reprova.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.draft_config import DraftConfig, MicDraft
from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

#: O ENDEREÇO DE RÁDIO DA BANCADA, com a máscara da casa (octetos 4 e 5
#: zerados) e sem os dois-pontos — a forma em que o daemon publica o `uniq`.
UNIQ = "aabbcc0000ff"

#: AS SEÇÕES QUE NÃO TÊM ESCRITOR POR DESENHO, com a razão. Vazio hoje, e o
#: dict existe para que uma exceção futura seja DECLARADA em vez de a régua
#: ser afrouxada — que é o defeito que esta casa mediu mais vezes.
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
    """``muted`` e ``volume`` viram override DELA, e não do vizinho."""
    d = DraftConfig.default().with_controller_mic(
        UNIQ, MicDraft(muted=True, volume=40))
    secao = d.controller_override(UNIQ).mic
    assert secao is not None and secao.muted is True and secao.volume == 40


def test_o_mic_nao_grava_o_botao_do_sistema() -> None:
    """``button_toggles_system`` fica FORA — não tem caminho por unidade.

    O ``hotkey.mic_button_loop`` consulta o ``DaemonConfig``, que é um por
    máquina. Gravá-lo por peça faria a coluna "Ajuste próprio" acender sobre
    um valor que nada aplica.
    """
    d = DraftConfig.default().with_controller_mic(
        UNIQ, MicDraft(muted=True, button_toggles_system=True))
    secao = d.controller_override(UNIQ).mic
    assert "button_toggles_system" not in secao.model_fields_set


def test_valor_igual_ao_global_nao_vira_override() -> None:
    """Repetir o global não cria override — seria dívida que reaparece sozinha.

    O GLOBAL PRECISA TER NÚMERO, e a régua já deu verde sobre a cura arrancada
    por não ter: no `DraftConfig.default()` o mic é todo `None`, então o
    caminho "igual ao global" nem era alcançado — o guarda de *sem opinião*
    saía antes. Uma régua desta família só mede alguma coisa com os dois lados
    preenchidos.
    """
    base = DraftConfig.default().model_copy(
        update={"mic": MicDraft(volume=55, muted=True)})
    d = base.with_controller_mic(UNIQ, MicDraft(
        muted=base.mic.muted, volume=base.mic.volume))
    override = d.controller_override(UNIQ)
    assert override is None or override.mic is None, (
        "um override que repete o global some da tela e volta a divergir "
        "assim que o global mudar")


def test_o_mic_efetivo_herda_o_global_campo_a_campo() -> None:
    """Override só de ``muted`` não pode zerar o volume que o global carrega."""
    base = DraftConfig.default().model_copy(
        update={"mic": MicDraft(volume=77, muted=False)})
    d = base.with_controller_mic(UNIQ, MicDraft(muted=True, volume=77))
    efetivo = d.effective_mic_for(UNIQ)
    assert efetivo.muted is True
    assert efetivo.volume == 77, "o volume do global sumiu num override parcial"


@pytest.mark.parametrize("campo", ["giroscopio", "acelerometro"])
def test_os_sensores_gravam_um_sem_tocar_no_outro(campo: str) -> None:
    """Ela disse *"ambos"* e cada um por si — meia faixa desliga um sozinho."""
    d = DraftConfig.default().with_controller_sensores(UNIQ, **{campo: False})
    secao = d.controller_override(UNIQ).sensores
    assert getattr(secao, campo) is False
    outro = "acelerometro" if campo == "giroscopio" else "giroscopio"
    assert getattr(secao, outro) is None, (
        f"gravar {campo} deu opinião sobre {outro}, que ela não pediu")


def test_sem_opiniao_limpa_a_secao_de_sensores() -> None:
    """Os dois ``None`` são o caminho de volta ao default LIGADO.

    ``D-AUDIO-E-GIRO-NASCEM-LIGADOS`` (25/08/2026): um perfil que não pediu
    nada não pode desligar o sensor dela por omissão.
    """
    d = DraftConfig.default().with_controller_sensores(UNIQ, giroscopio=False)
    assert d.controller_override(UNIQ).sensores is not None
    limpo = d.with_controller_sensores(UNIQ)
    override = limpo.controller_override(UNIQ)
    assert override is None or override.sensores is None


def test_escrever_uma_secao_nao_apaga_a_vizinha() -> None:
    """As seis convivem na mesma peça — é o ponto inteiro do override."""
    d = (DraftConfig.default()
         .with_controller_mic(UNIQ, MicDraft(muted=True))
         .with_controller_sensores(UNIQ, giroscopio=False))
    override = d.controller_override(UNIQ)
    assert override.mic is not None and override.mic.muted is True
    assert override.sensores is not None and override.sensores.giroscopio is False
