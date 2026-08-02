"""SOM-ROTA-01 — a rota, o pré-amplificador e o canal do controle.

A pergunta de desenho que ela fez, ao saber que o kernel escreve três campos e
esta árvore escrevia um:

    "então aqui a solução de design é setar pra impedir que o user quebre a
     feature?"

**Não, é o contrário — e a diferença governa a sprint inteira.** A curva que
ela mediu em 01/08 (mudo até 38, satura em 102, 60% do curso inerte) não é o
usuário quebrando nada: é o registrador de volume lutando contra um ganho de
entrada no valor padrão. A entrega é dar mais alcance, não menos.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import _byte_da_rota


class _Handle:
    """O mínimo de um handle: o que `set_audio_volumes` mexe."""

    def __init__(self) -> None:
        self._volumes_audio: list[int | None] = [None, None, None, None]
        self._preamp_audio: int | None = None


def _handle_com_rota(valor: int) -> _Handle:
    h = _Handle()
    h._volumes_audio[3] = valor
    return h


# ---------------------------------------------------------------------------
# E1 — os campos que faltavam, com a disciplina de posse intacta
# ---------------------------------------------------------------------------


def test_o_preamp_tem_bit_proprio_e_offset_proprio() -> None:
    """O `audio_control2` mora longe dos outros quatro, e no OUTRO flag.

    Os bytes de áudio de `common[4..7]` são autorizados pelo `valid_flag0`; o
    pré-amplificador é `common[37]` e é autorizado pelo **bit7 do flag1**. Um
    campo autorizado pelo flag errado é um campo que o firmware ignora.

    Mordida: apontar `VALID_FLAG1_AUDIO_CONTROL2_ENABLE` para um bit do flag0.
    """
    from hefesto_dualsense4unix.core import backend_pydualsense as bp

    assert rep.COMMON_AUDIO_CONTROL2 == 37
    assert rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE == 0x80

    # O valor `0x80` COINCIDE com o do `VALID_FLAG0_AUDIO_PATH`, e a
    # coincidência é do protocolo — são bit7 de bytes diferentes. Por isso a
    # asserção não pode ser numérica: o que separa os dois é em QUAL flag o
    # bit é ligado, e é isso que se afere.
    fonte = __import__("inspect").getsource(bp._PinnedPyDualSense._build_common)
    assert "flag1 |= rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE" in fonte
    assert "flag0 |= rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE" not in fonte, (
        "o pré-amp é autorizado pelo flag1; no flag0 o firmware o ignora"
    )


def test_os_tetos_de_volume_nao_sao_todos_255() -> None:
    """O fone vai até `0x7F` e o microfone até `0x40`.

    A árvore tratava os quatro bytes como 0-255. Mandar 200 no volume do
    microfone é mandar lixo num campo que o firmware interpreta — o valor não
    é "alto demais", é fora do domínio.

    Fonte: kernel 6.18 (patches do jack de áudio) e `dualsensectl`, que
    concordam. Mordida: subir qualquer um dos dois para 255.
    """
    assert rep.TETO_HEADPHONE_VOLUME == 0x7F
    assert rep.TETO_MIC_VOLUME == 0x40
    assert rep.TETO_SPEAKER_VOLUME == 0xFF, "o alto-falante é o único que vai a 255"


def test_o_clamp_do_volume_respeita_o_teto_de_cada_campo() -> None:
    """E o clamp acontece na PORTA, não no fio.

    Mordida: voltar a `_clamp_u8(valor, 0)` para todos os quatro.
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import _AUDIO_TETOS

    assert _AUDIO_TETOS == (0x7F, 0xFF, 0x40, 0xFF)


# ---------------------------------------------------------------------------
# E3 — a rota, e o meio-byte que ela NÃO pode apagar
# ---------------------------------------------------------------------------


def test_a_rota_omitida_nao_toma_a_posse_do_byte_do_microfone() -> None:
    """`common[7]` carrega DUAS coisas, e é por isso que o default é não tocar.

    Bits 4-5 são a rota de saída; o resto é o caminho do microfone (forçar
    interno, forçar headset, cancelamento de eco, de ruído, e o `INPUT_PATH`).
    Escrever o byte inteiro com o número da rota apagaria tudo isso em
    silêncio — é o que a sprint proíbe com todas as letras.

    Mordida: fazer `_byte_da_rota` devolver `0` em vez de `None`.
    """
    assert _byte_da_rota(_Handle(), None) is None


@pytest.mark.parametrize(
    "rota",
    [
        rep.SAIDA_ESTEREO_NO_FONE,
        rep.SAIDA_MONO_NO_FONE,
        rep.SAIDA_L_FONE_R_ALTO_FALANTE,
        rep.SAIDA_SO_NO_ALTO_FALANTE,
    ],
)
def test_a_rota_entra_nos_bits_4_e_5(rota: int) -> None:
    """Os quatro valores do `OUTPUT_PATH_SEL`, no lugar certo do byte.

    O caso do Zelda é o `2`: canal esquerdo para o fone/TV, canal direito para
    o alto-falante do controle. *"O speaker do controle faz os barulhos da
    espada do Link enquanto na tela tem o som normal do jogo"* — um byte.

    **A asserção deixou de casar o byte INTEIRO**, e a razão é a regressão de
    02/08: os literais que estavam aqui (`0b0000_0000` para a rota 0, etc.)
    travavam justamente a base ZERO que matou o microfone dela. Um teste que
    exige o resto do byte zerado é um teste que exige o `FORCE_INTERNAL_MIC`
    apagado.

    Agora ele afere o que é dele — os bits 4-5 — e o microfone tem teste
    próprio (`test_a_rota_preserva_o_microfone_quando_assume_o_byte_do_zero`).

    Mordida: trocar o `OUTPUT_PATH_SEL_SHIFT` de 4 para 0.
    """
    novo = _byte_da_rota(_Handle(), rota)

    assert novo is not None
    assert (novo & rep.OUTPUT_PATH_SEL_MASK) >> rep.OUTPUT_PATH_SEL_SHIFT == rota


def test_trocar_a_rota_preserva_o_caminho_do_microfone() -> None:
    """A parte mais fácil de errar da sprint, e a mais silenciosa.

    Com o byte já em posse e o microfone configurado (aqui: forçar o interno
    no bit0 e cancelamento de ruído no bit3), pedir uma rota nova pode mexer
    SÓ nos bits 4-5. Um `common[7] = rota` apagaria os dois bits do mic sem
    erro nenhum, e o sintoma apareceria noutro lugar — no microfone.

    Mordida: trocar o corpo por `return int(rota) << 4`.
    """
    mic_configurado = 0b0000_1001  # bit0 (mic interno) + bit3 (anti-ruído)
    handle = _handle_com_rota(mic_configurado)

    novo = _byte_da_rota(handle, rep.SAIDA_L_FONE_R_ALTO_FALANTE)

    assert novo is not None
    assert novo & ~rep.OUTPUT_PATH_SEL_MASK == mic_configurado, (
        "os bits do microfone têm de sobreviver à troca de rota"
    )
    assert (novo & rep.OUTPUT_PATH_SEL_MASK) >> rep.OUTPUT_PATH_SEL_SHIFT == 2


def test_a_rota_substitui_a_anterior_em_vez_de_somar() -> None:
    """E trocar de rota não acumula bits — 3 depois de 1 é 3, não 3|1.

    Mordida: trocar o `& ~OUTPUT_PATH_SEL_MASK` por nada (só `|`).
    """
    handle = _handle_com_rota(
        rep.SAIDA_SO_NO_ALTO_FALANTE << rep.OUTPUT_PATH_SEL_SHIFT
    )
    novo = _byte_da_rota(handle, rep.SAIDA_MONO_NO_FONE)
    assert novo is not None
    assert (novo & rep.OUTPUT_PATH_SEL_MASK) >> rep.OUTPUT_PATH_SEL_SHIFT == 1


# ---------------------------------------------------------------------------
# A disciplina de posse — a regra que a AUDIO-OWNER-01 pagou para manter
# ---------------------------------------------------------------------------


def test_o_preamp_sem_dono_sai_zerado_e_sem_autorizacao(monkeypatch: Any) -> None:
    """Autorizar um byte sem escrevê-lo é mandar ZERO — a 60 Hz.

    Foi o defeito que a AUDIO-OWNER-01 curou para os quatro bytes de volume, e
    ele vale igual para o pré-amplificador: um bit de autorização ligado com o
    byte em `0x00` não é neutro, é "ganho zero" com cara de keepalive. Mesma
    classe do keepalive de vibração do GUERRA-01, que zerava o rumble de
    terceiros.

    Mordida: ligar `VALID_FLAG1_AUDIO_CONTROL2_ENABLE` incondicionalmente no
    `_build_common`.
    """
    from hefesto_dualsense4unix.core import backend_pydualsense as bp

    fonte = __import__("inspect").getsource(bp._PinnedPyDualSense._build_common)

    assert "if preamp is None:" in fonte
    assert "flag1 &= ~rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE" in fonte, (
        "sem dono, o bit de autorização do pré-amp tem de sair APAGADO"
    )


def test_a_devolucao_da_posse_leva_o_preamp_junto() -> None:
    """"Devolver" não pode devolver metade.

    O pré-amp é justamente o campo que muda o ALCANCE do controle deslizante;
    deixá-lo em posse depois do release faria o botão físico do controle
    continuar sem valer para parte do caminho do áudio.

    Mordida: apagar o `self._preamp_audio = None` do `release_audio_volumes`.
    """
    from hefesto_dualsense4unix.core import backend_pydualsense as bp

    fonte = __import__("inspect").getsource(
        bp._PinnedPyDualSense.release_audio_volumes
    )
    assert "self._preamp_audio = None" in fonte


def test_a_rota_preserva_o_microfone_quando_assume_o_byte_do_zero() -> None:
    """A REGRESSÃO de 02/08/2026, medida na máquina dela e curada no mesmo dia.

    Ao pedir uma rota, o `common[7]` era escrito com base ZERO — porque
    ninguém tinha posse dele antes. **O microfone do controle parou de
    captar**: o `parec` passou de 131072 bytes para ZERO, e voltou assim que a
    posse foi devolvida.

    É exatamente a armadilha 2 que ela nomeou na sprint — *"o common[7] carrega
    a rota E o caminho do microfone; escrever meio byte muda o outro meio"* — e
    o `_byte_da_rota` só preservava o outro meio quando JÁ havia posse. Na
    PRIMEIRA escrita, que é o caso real de quem nunca mexeu na rota, ele
    zerava tudo.

    Não há como ler o `common[7]` do firmware (não existe report de entrada nem
    feature que o devolva), então a base é a mais conservadora que se pode
    afirmar: o microfone INTERNO ligado.

    Mordida: voltar `vigente = 0`.
    """
    novo = _byte_da_rota(_Handle(), rep.SAIDA_SO_NO_ALTO_FALANTE)

    assert novo is not None
    assert novo & rep.AUDIO_CONTROL_FORCE_INTERNAL_MIC, (
        "sem o FORCE_INTERNAL_MIC na base, a primeira escrita da rota mata o "
        "microfone do controle — medido"
    )
    assert (novo & rep.OUTPUT_PATH_SEL_MASK) >> rep.OUTPUT_PATH_SEL_SHIFT == 3
