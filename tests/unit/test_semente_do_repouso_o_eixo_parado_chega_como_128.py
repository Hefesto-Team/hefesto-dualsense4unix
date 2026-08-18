"""O eixo que nunca se mexeu chega ao jogo como 128 — SEMENTE-DO-REPOUSO-01.

O QUE ESTE ARQUIVO GUARDA
-------------------------
O `EvdevSnapshot` nasce com os sticks em **128** (`core/evdev_reader.py`, o
default do dataclass) e só é atualizado por EVENTO. O evdev não emite `EV_ABS`
para valor que não muda: um eixo parado desde antes de o leitor abrir o nó
nunca gera evento nenhum, e o produto publica 128 — seja qual for a posição
real do stick.

MEDIDO em 15/08/2026, 22h12, com quatro controles na mesa
(`docs/data/ensaios-brutos/2026-08-15-A1-entrada-em-repouso.txt`, seções 1 e 2;
célula `entrada.stick@dualsense` do mapa de canais): numa janela de 20 s, o
`ABS_Y` do DualSense do **vpad P2, no cabo** ficou parado em **124** pelos 5001
quadros — o único dos 16 eixos com ZERO transições e longe do centro — e o vpad
publicou **128**. Os outros 15 eixos da mesma janela chegaram com erro ZERO,
porque se mexeram e o evento veio. O `EVIOCGABS` do mesmo nó, no mesmo instante,
devolvia 124: o kernel sabia. Quem publicava 128 era o produto.

(A unidade é nomeada pelo VPAD, e não pelo MAC, de propósito. Em `tests/` o MAC
não entra nem mascarado — `test_anonimato_de_fixtures.py` só admite as faixas
forjadas `02:fe`/`aa:bb:cc`/`e8:47:3a`, e a alternativa de escrever aqui um MAC
forjado seria pior que omitir: diria que a medição saiu de um aparelho que não
existe. Quem precisar da unidade exata abre o ensaio bruto citado acima, onde a
máscara da casa — octetos 4 e 5 zerados — é a forma permitida.)

A CURA que estes testes trancam: `EvdevReader._on_device_opened` semeia o
snapshot com o `absinfo.value` que o `capabilities()` já traz — o mesmo
`absinfo` de onde a FAIXA já era lida, e que o produto descartava.

Custou 4 LSB naquela unidade e ninguém sente. Num stick gasto, ou num controle
sendo segurado fora do centro no instante em que o daemon sobe, custa o que o
desvio for — e some sozinho, sem log, assim que a pessoa toca o stick.

MORDE? Duas metades, e cada uma foi arrancada sozinha em 15/08/2026 — com o
`src/` COPIADO para fora da árvore e o `PYTHONPATH` apontado para a cópia, sem
mutar a árvore de trabalho:

1. **A semeadura.** Arrancada a chamada de `_semear_posicao_de_repouso`:
   **6 reprovam, 8 seguem verdes**. A primeira reprova com
   ``o eixo que não emitiu EV_ABS nenhum desde o open chegou como 128, e o
   kernel dizia 124 no MESMO instante``. Os 8 verdes são de propósito: guardam
   o lado "não invente", e reprovar ali seria exigir a semeadura, não a
   prudência dela.
2. **A recusa do `valor == mínimo`** (a armadilha do nó recém-criado).
   Arrancada só ela: **1 reprova, 13 seguem verdes** —
   ``os sticks foram semeados com (0, 0, 0, 0) a partir de um `absinfo.value`
   igual ao MÍNIMO da faixa``. Cada arrancamento reprova SÓ o teste da própria
   cura, e a rodada de controle volta 14/14 verde.

MACs mascarados na convenção da casa: as faixas forjadas de `tests/`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evdev import AbsInfo, ecodes

from hefesto_dualsense4unix.core.evdev_reader import (
    EvdevReader,
    EvdevSnapshot,
    normalizar_eixo,
    posicoes_de_eixo,
)

#: A faixa que o `hid_playstation` declara para os eixos do DualSense: 0..255,
#: sem `flat` e sem `fuzz` (é a faixa canônica da casa, `EIXO_MAX_HEFESTO`).
#: `value` é o que muda de teste para teste — é a POSIÇÃO no instante do open.
def _abs_dualsense(valor: int) -> AbsInfo:
    return AbsInfo(value=valor, min=0, max=255, fuzz=0, flat=0, resolution=0)


#: A faixa dos analógicos do Nintendo Pro, com sinal (medida em 06/08/2026).
#: Aqui o CENTRO é 0 e o mínimo é o talo de verdade — o oposto do DualSense.
def _abs_pro(valor: int) -> AbsInfo:
    return AbsInfo(value=valor, min=-32767, max=32767, fuzz=250, flat=500, resolution=0)


#: O hat do D-pad. Entra nas caps porque um DualSense de verdade o publica, e
#: porque ele NÃO pode ser semeado como eixo (ele vira botão em `_handle_abs`).
_ABS_HAT = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)


class _DevFalso:
    """Só o que `_on_device_opened` toca: o `capabilities()` do nó aberto.

    O `capabilities()` do python-evdev devolve o `_rawcapabilities` colhido no
    `InputDevice.__init__` — o `absinfo` do INSTANTE DO OPEN. É por isso que o
    dublê pode ser um dicionário fixo: no produto ele também é.
    """

    def __init__(self, caps: Any) -> None:
        self._caps = caps

    def capabilities(self) -> Any:
        return self._caps


class _DevIlegivel:
    """Nó cujo `capabilities()` levanta — o modo de falha que degrada."""

    def capabilities(self) -> Any:
        raise OSError(19, "No such device")


def _caps_dualsense(
    *,
    lx: int = 127,
    ly: int = 124,
    rx: int = 130,
    ry: int = 129,
    l2: int = 0,
    r2: int = 0,
) -> dict[int, Any]:
    """As caps daquela unidade no cabo, como a bancada as mediu.

    Os defaults SÃO os números do ensaio de 15/08: centro (127, 124, 130, 129),
    gatilhos em repouso. O `ly=124` é o eixo do achado.
    """
    return {
        ecodes.EV_KEY: [ecodes.BTN_SOUTH, ecodes.BTN_TL2, ecodes.BTN_TR2],
        ecodes.EV_ABS: [
            (ecodes.ABS_X, _abs_dualsense(lx)),
            (ecodes.ABS_Y, _abs_dualsense(ly)),
            (ecodes.ABS_Z, _abs_dualsense(l2)),
            (ecodes.ABS_RX, _abs_dualsense(rx)),
            (ecodes.ABS_RY, _abs_dualsense(ry)),
            (ecodes.ABS_RZ, _abs_dualsense(r2)),
            (ecodes.ABS_HAT0X, _ABS_HAT),
            (ecodes.ABS_HAT0Y, _ABS_HAT),
        ],
    }


def _reader_aberto_em(caps: Any) -> EvdevReader:
    """Um reader que acabou de abrir um nó com estas caps — nenhum evento ainda."""
    reader = EvdevReader(device_path=Path("/dev/input/event999"))
    reader._on_device_opened(_DevFalso(caps))
    return reader


# --- O achado, tal como foi medido ---------------------------------------


def test_o_eixo_parado_chega_com_a_posicao_real_e_nao_com_128() -> None:
    """O caso literal da bancada: `ABS_Y` em 124 no open, sem um único evento.

    MORDIDA: sem a semeadura, `ly` fica no default do `EvdevSnapshot` e este
    teste reprova dizendo `124 real -> 128 publicado`.
    """
    reader = _reader_aberto_em(_caps_dualsense())
    snap = reader.snapshot()
    assert snap.ly == 124, (
        "o eixo que não emitiu EV_ABS nenhum desde o open chegou como "
        f"{snap.ly}, e o kernel dizia 124 no MESMO instante (EVIOCGABS do nó, "
        "15/08/2026 22h12). Sem semear o snapshot com o `absinfo.value`, todo "
        "eixo parado vira centro perfeito e o desvio real some sem log — foi "
        f"assim que o vpad publicou 128 para um stick em 124. Default do "
        f"dataclass: {EvdevSnapshot().ly}"
    )


def test_os_quatro_eixos_do_stick_chegam_com_a_medida_da_bancada() -> None:
    """Os quatro daquela unidade, não só o que estava longe do centro.

    Os outros três também nasciam 128 e só acertavam por acidente — porque se
    mexeram e o evento veio. Sem mão na mesa, nenhum deles acerta.
    """
    reader = _reader_aberto_em(_caps_dualsense())
    snap = reader.snapshot()
    assert (snap.lx, snap.ly, snap.rx, snap.ry) == (127, 124, 130, 129), (
        "o centro de repouso medido daquela unidade é (127, 124, 130, 129) e o "
        f"produto publicou ({snap.lx}, {snap.ly}, {snap.rx}, {snap.ry}). "
        "Nenhuma das quatro unidades da mesa de 15/08 tem os quatro sticks em "
        "128: semear com um 'centro' fixo seria trocar um erro por outro"
    )


def test_a_semente_e_o_mesmo_numero_que_o_primeiro_evento_produziria() -> None:
    """Invariante que impede a semeadura de inventar valor novo.

    A semente passa pelo MESMO `normalizar_eixo` que `_handle_abs` usa. Se um
    dia divergirem, o snapshot daria um salto no primeiro evento de um eixo que
    não se moveu — e ninguém saberia de onde veio.
    """
    reader = _reader_aberto_em(_caps_dualsense(ly=124))
    semeado = reader.snapshot().ly
    reader._handle_abs(ecodes.ABS_Y, 124, ecodes)
    assert reader.snapshot().ly == semeado, (
        "o valor semeado no open divergiu do que o mesmo valor CRU produz pelo "
        "caminho de evento: o eixo daria um salto assim que o kernel repetisse "
        "a posição"
    )


# --- Armadilha (a): o gatilho repousa em 0, não em 128 -------------------


def test_gatilho_solto_no_open_continua_solto() -> None:
    """L2/R2 repousam em 0. Semear um 'centro' ali seria disparo fantasma."""
    reader = _reader_aberto_em(_caps_dualsense(l2=0, r2=0))
    snap = reader.snapshot()
    assert (snap.l2_raw, snap.r2_raw) == (0, 0), (
        f"gatilho em repouso chegou como ({snap.l2_raw}, {snap.r2_raw}). O "
        "repouso do gatilho é 0, não o centro do stick: qualquer semeadura por "
        "'centro' em vez de pelo `absinfo.value` do PRÓPRIO eixo trocaria o "
        "defeito do stick por um gatilho meio-apertado sozinho"
    )


def test_gatilho_ja_apertado_no_open_chega_apertado() -> None:
    """O caso que hoje erra do outro lado: dedo no gatilho quando o daemon sobe.

    MORDIDA: sem a semeadura, `l2_raw` fica em 0 e o teste reprova — o dedo só
    passaria a existir para o jogo quando ela mexesse no gatilho.
    """
    reader = _reader_aberto_em(_caps_dualsense(l2=200, r2=37))
    snap = reader.snapshot()
    assert (snap.l2_raw, snap.r2_raw) == (200, 37), (
        f"gatilho apertado no instante do open chegou como ({snap.l2_raw}, "
        f"{snap.r2_raw}) em vez de (200, 37): o kernel já tinha o valor no "
        "`absinfo` e o produto o descartou"
    )


def test_gatilho_sintetizado_do_pro_nao_e_afetado() -> None:
    """No Pro não há `ABS_Z`/`ABS_RZ`: o gatilho vem do botão e continua vindo.

    Sem eixo não há `absinfo.value`, então não há o que semear — e a síntese
    digital (`_sintetizar_gatilho`) tem de seguir ligada e mandando.
    """
    caps = {
        ecodes.EV_KEY: [ecodes.BTN_TL2, ecodes.BTN_TR2],
        ecodes.EV_ABS: [
            (ecodes.ABS_X, _abs_pro(0)),
            (ecodes.ABS_Y, _abs_pro(0)),
            (ecodes.ABS_RX, _abs_pro(0)),
            (ecodes.ABS_RY, _abs_pro(0)),
            (ecodes.ABS_HAT0X, _ABS_HAT),
            (ecodes.ABS_HAT0Y, _ABS_HAT),
        ],
    }
    reader = _reader_aberto_em(caps)
    assert reader._sintetizar_l2 is True
    assert reader.snapshot().l2_raw == 0
    reader._handle_key(ecodes.BTN_TL2, 1, ecodes)
    assert reader.snapshot().l2_raw == 255, (
        "a semeadura pisou na síntese digital do gatilho do Pro: o ZL dele é "
        "botão, não eixo, e sem a síntese o gatilho fica 0 para sempre"
    )


# --- Armadilha (b): o `absinfo.value` do nó recém-criado -----------------


def test_stick_no_minimo_declarado_nao_e_semeado() -> None:
    """`value == min` num stick de faixa 0..255 é a memória zerada do `input_dev`.

    Um `input_dev` recém-criado tem `absinfo.value = 0` antes do primeiro
    report. Num DualSense (0..255) esse 0 é indistinguível de TALO À ESQUERDA.
    Publicá-lo seria o defeito que `normalizar_eixo` já descreve: o personagem
    anda sozinho para o canto e não para, até alguém tocar o stick. Recusar
    deixa o 128 de hoje, que é regressão ZERO — e o primeiro evento corrige.

    Este teste passa TAMBÉM com a cura arrancada, e é de propósito: ele guarda
    o "não invente", não a semeadura.
    """
    reader = _reader_aberto_em(_caps_dualsense(lx=0, ly=0, rx=0, ry=0))
    snap = reader.snapshot()
    assert (snap.lx, snap.ly, snap.rx, snap.ry) == (128, 128, 128, 128), (
        f"os sticks foram semeados com ({snap.lx}, {snap.ly}, {snap.rx}, "
        f"{snap.ry}) a partir de um `absinfo.value` igual ao MÍNIMO da faixa — "
        "que é o valor de um nó que ainda não recebeu report nenhum. Publicar "
        "isso é um talo FANTASMA que só some quando ela tocar o stick"
    )


def test_gatilho_no_minimo_e_semeado_porque_ali_o_minimo_e_o_repouso() -> None:
    """A recusa do mínimo é SÓ dos sticks, e o resultado tem de ser 0 mesmo."""
    reader = _reader_aberto_em(_caps_dualsense(l2=0))
    assert reader.snapshot().l2_raw == 0


def test_stick_do_pro_no_zero_continua_no_centro() -> None:
    """Faixa com sinal: a memória zerada (`0`) JÁ É o centro, e vira 128.

    No Pro o mínimo é `-32767` — o talo de verdade —, então a recusa do mínimo
    nunca tem o que fazer ali, e o valor de nó recém-criado é inofensivo.
    """
    caps = {
        ecodes.EV_KEY: [ecodes.BTN_SOUTH],
        ecodes.EV_ABS: [
            (ecodes.ABS_X, _abs_pro(0)),
            (ecodes.ABS_Y, _abs_pro(0)),
            (ecodes.ABS_RX, _abs_pro(0)),
            (ecodes.ABS_RY, _abs_pro(0)),
        ],
    }
    reader = _reader_aberto_em(caps)
    snap = reader.snapshot()
    assert (snap.lx, snap.ly, snap.rx, snap.ry) == (128, 128, 128, 128)


def test_stick_do_pro_fora_do_centro_chega_convertido() -> None:
    """E quando o Pro está de verdade fora do centro, a semente é a convertida."""
    caps = {
        ecodes.EV_KEY: [ecodes.BTN_SOUTH],
        ecodes.EV_ABS: [(ecodes.ABS_Y, _abs_pro(-16384))],
    }
    reader = _reader_aberto_em(caps)
    esperado = normalizar_eixo(-16384, reader._eixos[ecodes.ABS_Y])
    assert reader.snapshot().ly == esperado
    assert esperado != 128, "o caso perdeu a força: -16384 tem de sair do centro"


# --- Degradar para o que já rodava ---------------------------------------


def test_node_ilegivel_nao_semeia_nada() -> None:
    """`capabilities()` que levanta: o snapshot fica no default, sem exceção.

    Passa com a cura arrancada de propósito — guarda o modo de falha, que é
    "degradar para o que já rodava", nunca derrubar a thread de leitura.
    """
    reader = EvdevReader(device_path=Path("/dev/input/event999"))
    reader._on_device_opened(_DevIlegivel())
    snap = reader.snapshot()
    assert (snap.lx, snap.ly, snap.rx, snap.ry) == (128, 128, 128, 128)
    assert (snap.l2_raw, snap.r2_raw) == (0, 0)


def test_eixo_listado_sem_absinfo_nao_semeia() -> None:
    """Nó que lista só o código do eixo (sem `absinfo`): não há posição a ler."""
    caps = {ecodes.EV_KEY: [ecodes.BTN_SOUTH], ecodes.EV_ABS: [ecodes.ABS_Y]}
    reader = _reader_aberto_em(caps)
    assert reader.snapshot().ly == 128
    assert posicoes_de_eixo(caps, ecodes.EV_ABS) == {}


def test_o_hat_do_dpad_nao_vira_stick_na_semeadura() -> None:
    """`ABS_HAT0X/Y` são D-pad, não eixo de stick: a semeadura não os toca.

    Semeá-los como se fossem eixo escreveria o hat por cima de um campo do
    snapshot que não é dele.
    """
    reader = _reader_aberto_em(_caps_dualsense())
    assert reader.snapshot().buttons_pressed == frozenset()


def test_a_semeadura_e_refeita_a_cada_reabertura() -> None:
    """Queda + reabertura: o nó novo traz posição nova, e ela manda.

    `_reset_on_disconnect` esquece a forma dos eixos de propósito (o nó morreu);
    a posição tem de ser relida no open seguinte, senão o valor velho ficaria
    congelado até o primeiro evento do controle novo.
    """
    reader = _reader_aberto_em(_caps_dualsense(ly=124))
    assert reader.snapshot().ly == 124
    reader._reset_on_disconnect()
    reader._on_device_opened(_DevFalso(_caps_dualsense(ly=201)))
    assert reader.snapshot().ly == 201, (
        "a reabertura não releu a posição: o eixo ficaria no valor da conexão "
        "anterior até o controle novo emitir um EV_ABS que pode nunca vir"
    )
