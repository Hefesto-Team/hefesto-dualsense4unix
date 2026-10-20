#!/usr/bin/env python3
"""A intensidade da vibração e do gatilho sai do firmware, como no PS5.

Sprint: A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01.

O PRODUTO (20/10/2026): de 0 a 100% o trilho vira o byte de atenuação do firmware (`common[36]`,
vibração no nibble baixo, gatilho no alto, flag1 `0x40`) em cada report, cabo (`0x02`) e rádio
(`0x31`), dos quatro controles; acima de 100% o software reforça (o motor até 255, o gatilho até a
força 8 do efeito). Os reports são montados em memória, sem aparelho.

O DESENHO (18/10/2026): a 05 tem o trilho de 0 a 200% e a 03 ganha o mesmo trilho para o gatilho.

MORDIDAS DO PRODUTO: tire o `flag1 |= 0x40` da redução no `_build_common` (o keepalive volta a
limpar o bit), troque os nibbles em `byte_de_reducao`, tire a divisão do motor pela fração do
firmware, tire o `escalar_o_bloco_do_gatilho` do bloco cru do jogo, ou tire a chamada a
`_empurrar_as_intensidades` de `set_trigger_scales` — cada uma reprova uma asserção.

MORDIDAS DO DESENHO: volte o `TETO_DA_FORCA` da 05 a 100, ponha botões de degrau na «Força», tire
a linha da 03 do desenho, troque o `data-papel` do trilho da 03 por `data-hef` (o trilho volta a só
pintar), ponha uma palavra de firmware na dica, ou aumente o respiro da grade da 03.
"""
from __future__ import annotations

import pathlib
import re
import sys

import threading
import zlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

CHROME = pathlib.Path("/usr/bin/google-chrome")
VISTAS = [(940, 809), (1272, 860), (1512, 860), (1900, 1000)]
JARGAO = ("firmware", "byte", "nibble", "multiplicador", "software", "atenuação", "bit", "pwm")


def _html(nome: str) -> str:
    arq = RAIZ / "mockup" / nome
    assert arq.exists(), f"o desenho não tem {nome} — rode o gerador da aba"
    return arq.read_text(encoding="utf-8")


def _trilhos(doc: str, campo_ou_papel: str) -> list[str]:
    todos = re.findall(r'<input class="trilho arrasta"[^>]*>', doc)
    return [t for t in todos if campo_ou_papel in t]


@pytest.fixture(scope="module")
def d03() -> str:
    return _html("03-gatilhos.html")


@pytest.fixture(scope="module")
def d05() -> str:
    return _html("05-vibracao.html")


def test_a_forca_da_vibracao_vai_de_0_a_200_sem_degraus(d05: str) -> None:
    from hefesto_dualsense4unix.interface import aba05
    from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX

    assert aba05.TETO_DA_FORCA == round(RUMBLE_CUSTOM_MULT_MAX * 100) == 200
    assert "data-forca=" not in d05 and 'class="seg"' not in d05
    trilhos = _trilhos(d05, 'data-papel="intensidade"')
    assert len(trilhos) == len(aba05.MESA)
    assert all('min="0"' in t and 'max="200"' in t and 'step="5"' in t for t in trilhos), trilhos


def test_o_gatilho_ganha_o_trilho_de_0_a_200_por_controle(d03: str) -> None:
    # D-1810-O-GATILHO-E-A-VIBRACAO-TEM-O-TRILHO-DE-0-A-200
    from hefesto_dualsense4unix.interface import aba03, aba05

    trilhos = _trilhos(d03, f'data-campo="{aba03.CAMPO_DA_INTENSIDADE}"')
    assert len(trilhos) == len(aba03.MESA), f"um trilho por lugar, e há {len(trilhos)}"
    for t in trilhos:
        assert 'min="0"' in t and 'max="200"' in t and 'step="5"' in t, t
        assert 'data-hef-alvo="valor"' in t, "o piloto não pinta o trilho"
    assert (aba03.TETO_DA_INTENSIDADE, aba03.PASSO_DA_INTENSIDADE) == (
        aba05.TETO_DA_FORCA, aba05.PASSO_DA_FORCA), "os dois trilhos têm de ter o mesmo alcance"
    assert "Intensidade do gatilho" in d03
    # o mesmo formato da 05: ícone do controle, trilho, número e `%`
    assert d03.count('class="teto">%</span>') >= len(aba03.MESA)
    assert aba03.GLIFO_DA_INTENSIDADE == aba05.GLIFO_DO_CONTROLE


def test_o_lugar_sem_controle_mostra_o_travessao_e_nao_um_numero(d03: str) -> None:
    from hefesto_dualsense4unix.interface import aba03

    vazios = [c for c in aba03.MESA if not c.get("conectado", True)]
    assert vazios, "a cena deve ter vagas sem controle"
    celulas = re.findall(r'<div class="g2-int[^"]*"[^>]*>', d03)
    assert len(celulas) == len(aba03.MESA)
    for c in vazios:
        cel = next(x for x in celulas if f'data-controle="{c["pref"]}"' in x)
        assert 'data-conectado="nao"' in cel and " off" in cel, cel
        molde = rf'<div class="g2-int[^"]*" data-controle="{c["pref"]}".*?</div>'
        achada = re.search(molde, d03, re.S)
        assert achada and f">{aba03.TRAVESSAO}</span>" in achada.group(0), "a vaga afirma um número"


def test_a_linha_da_03_fica_antes_do_l2_e_o_estilo_continua_escolhendo_o_efeito(d03: str) -> None:
    from hefesto_dualsense4unix.interface import aba03

    assert aba03.ONDE_ENTRA_A_INTENSIDADE == "acima"
    primeiro_trilho = d03.index(f'data-campo="{aba03.CAMPO_DA_INTENSIDADE}"')
    primeiro_modo = d03.index('data-gesto="modo"')
    assert primeiro_trilho < primeiro_modo, "a intensidade entra sob o chip, antes do L2"
    # o L2/R2 do estilo (r3b-03-15) fica como está: dois campos de cada por controle
    n = len(aba03.MESA)
    assert d03.count('data-gesto="modo"') == 2 * n and d03.count('data-gesto="imersao"') == 2 * n


def test_o_trilho_novo_nao_cria_gesto_sem_dono(d03: str) -> None:
    """Gesto sem dono reprova `test_os_sem_dono_so_diminuem`: o trilho só pinta (`data-hef`)."""
    from hefesto_dualsense4unix.interface import aba03

    g = aba03.GESTO_DA_INTENSIDADE_QUE_ESPERA_O_PRODUTO
    assert f'data-hef="{g}"' in d03
    assert f'data-papel="{g}"' not in d03 and f'data-gesto="{g}"' not in d03, (
        "o gesto novo ganhou endereço antes de ter atendente e camada")


def test_a_dica_de_cada_trilho_e_uma_frase_curta_sem_jargao() -> None:
    from hefesto_dualsense4unix.interface import aba03, aba05

    for dica in (aba03.DICA_DA_INTENSIDADE, aba05.DICA_DA_FORCA):
        baixa = dica.lower()
        assert not any(p in baixa for p in JARGAO), f"jargão na dica: {dica!r}"
        assert len(dica) <= 120 and dica.count(".") == 0, f"a dica é uma frase curta: {dica!r}"
        assert "100%" in dica and ("mais fraco" in dica or "mais fraca" in dica)


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema: a régua não tem motor")
def test_a_03_e_a_05_nao_rolam_na_vertical_nas_quatro_vistas() -> None:
    """Nem o documento, nem o `.miolo` (a rolagem interna que `passa_da_dobra` não vê)."""
    from playwright.sync_api import sync_playwright

    medir = """() => {
      const rola = [];
      for (const e of document.querySelectorAll('*')) {
        const s = getComputedStyle(e);
        if ((s.overflowY === 'auto' || s.overflowY === 'scroll')
            && e.scrollHeight > e.clientHeight + 1) {
          rola.push((e.className || e.tagName) + ':' + (e.scrollHeight - e.clientHeight));
        }
      }
      const d = document.documentElement;
      const sobra = d.scrollHeight - window.innerHeight;
      if (sobra > 1) rola.push('doc:' + sobra);
      return {rola, lateral: d.scrollWidth > d.clientWidth + 1};
    }"""
    achados = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        for pagina in ("03-gatilhos.html", "05-vibracao.html"):
            for larg, alt in VISTAS:
                pg = nav.new_page(viewport={"width": larg, "height": alt})
                pg.goto((RAIZ / "mockup" / pagina).as_uri())
                pg.wait_for_load_state("networkidle")
                pg.wait_for_timeout(300)
                m = pg.evaluate(medir)
                if m["rola"] or m["lateral"]:
                    achados.append((pagina, larg, alt, m))
                pg.close()
        nav.close()
    assert not achados, f"há rolagem: {achados}"


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema: a régua não tem motor")
def test_a_linha_da_03_tem_a_altura_e_as_colunas_da_linha_da_forca_da_05() -> None:
    """O pedido é «no mesmo formato, altura e colunas» do trilho da 05: mede-se a geometria.

    MORDIDA: troque, no `aba03.CSS`, o `grid-template-columns` da `.g2-int` (o 44px do número
    por 60px) ou a altura de 36 por 30, regere o desenho, e esta régua reprova.
    """
    from playwright.sync_api import sync_playwright

    medir = """s => {
      const t = document.querySelector(s), l = t.parentElement, cs = getComputedStyle(l);
      const cols = cs.gridTemplateColumns.split(' ');
      return {altura: Math.round(l.getBoundingClientRect().height),
              fixas: [cols[0], cols[2], cols[3]], vao: cs.columnGap,
              trilho: Math.round(t.getBoundingClientRect().height)};
    }"""
    medidas = {}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        for pagina, seletor in (("03-gatilhos.html", '.g2-int:not(.off) input.trilho'),
                                ("05-vibracao.html", 'input.trilho[data-papel="intensidade"]')):
            pg = nav.new_page(viewport={"width": 1272, "height": 860})
            pg.goto((RAIZ / "mockup" / pagina).as_uri())
            pg.wait_for_load_state("networkidle")
            medidas[pagina] = pg.evaluate(medir, seletor)
            pg.close()
        nav.close()
    m03, m05 = medidas["03-gatilhos.html"], medidas["05-vibracao.html"]
    assert m03 == m05, f"a linha da 03 não tem o formato da Força da 05: {m03} ≠ {m05}"
    assert m03["altura"] == 36 and m03["fixas"] == ["36px", "44px", "8px"], m03


# --- O PRODUTO: o report montado em memória ------------------------------------------------------

_MAC = ("aabbcc000001", "aabbcc000002", "aabbcc000003", "aabbcc000004")


class _Fio:
    def __init__(self) -> None:
        self.escrito: list[bytes] = []

    def write(self, dados: bytes) -> int:
        self.escrito.append(bytes(dados))
        return len(dados)


def _handle(*, radio: bool = False, vib: float = 1.0, gat: float = 1.0):
    """Um handle sem `init()` (sem aparelho), com só o estado que o report usa."""
    from pydualsense.enums import ConnectionType
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    from hefesto_dualsense4unix.core import backend_pydualsense as bp

    h = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    h.leftMotor = 0
    h.rightMotor = 0
    h.light = DSLight()
    h.audio = DSAudio()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h.conType = ConnectionType.BT if radio else ConnectionType.USB
    h._suppress_leds = False
    h._rumble_active = False
    h._rumble_stop_pending = False
    h._bt_seq = 0
    h.device = _Fio()
    h._escala_da_vibracao = vib
    h._escala_do_gatilho = gat
    return h


def _common(report: list[int]) -> list[int]:
    """O corpo de 47 bytes dentro do envelope: `[1..47]` no cabo, `[3..49]` no rádio."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    inicio = 3 if report[0] == rep.BT_REPORT_ID else 1
    return report[inicio : inicio + rep.COMMON_LEN]


@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
def test_com_a_forca_cheia_o_report_e_o_de_antes(radio: bool) -> None:
    """100% nos dois trilhos: o keepalive sai sem o `0x40` e o byte 36 fica zero, como sempre."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    c = _common(_handle(radio=radio).prepareReport())
    assert c[1] & rep.VALID_FLAG1_MOTOR_POWER == 0
    assert c[rep.COMMON_REDUCE_MOTOR_POWER] == 0


@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
@pytest.mark.parametrize("vibrando", [False, True], ids=["parado", "vibrando"])
def test_abaixo_de_100_cada_report_leva_o_bit_e_os_nibbles(radio: bool, vibrando: bool) -> None:
    """50% na vibração (4 passos, nibble baixo) e 25% no gatilho (6 passos, nibble alto)."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    h = _handle(radio=radio, vib=0.5, gat=0.25)
    if vibrando:
        h.setLeftMotor(100)
    report = h.prepareReport()
    c = _common(report)
    assert c[1] & rep.VALID_FLAG1_MOTOR_POWER, "o report saiu sem o BIT(6) do flag1"
    assert c[rep.COMMON_REDUCE_MOTOR_POWER] == 0x64, hex(c[rep.COMMON_REDUCE_MOTOR_POWER])
    if radio:
        assert len(report) == rep.BT_REPORT_LEN and report[2] == rep.BT_TAG
        crc = zlib.crc32(b"\xa2" + bytes(report[:74])) & 0xFFFFFFFF
        assert int.from_bytes(bytes(report[74:78]), "little") == crc, "o CRC não cobre o byte 36"
    else:
        assert len(report) == rep.USB_REPORT_LEN and report[0] == rep.USB_REPORT_ID


def test_os_nibbles_tem_dono_e_o_firmware_atenua_sem_calar() -> None:
    from hefesto_dualsense4unix.core import ds_output_report as rep

    assert rep.byte_de_reducao(0.5, 1.0) == 0x04, "a vibração saiu do nibble baixo"
    assert rep.byte_de_reducao(1.0, 0.5) == 0x40, "o gatilho saiu do nibble alto"
    assert rep.byte_de_reducao(0.0, 0.0) == 0x77, "zero é o passo 7 (12,5%): atenua, não cala"
    assert rep.byte_de_reducao(2.0, 1.5) == 0x00, "acima de 100% o firmware fica cheio"
    for pct in range(0, 101, 5):
        t = pct / 100
        assert rep.fracao_do_firmware(rep.passos_de_reducao(t)) >= t - 1e-9, pct
        assert rep.resto_do_software(t) <= 1.0 + 1e-9, f"{pct}% satura o resto do software"


def test_a_volta_a_100_chega_ao_firmware_uma_vez_e_o_keepalive_volta_ao_neutro() -> None:
    from hefesto_dualsense4unix.core import ds_output_report as rep

    h = _handle(vib=0.5)
    assert _common(h.prepareReport())[rep.COMMON_REDUCE_MOTOR_POWER] == 0x04
    h._escala_da_vibracao = 1.0
    volta = _common(h.prepareReport())
    assert volta[1] & rep.VALID_FLAG1_MOTOR_POWER and volta[rep.COMMON_REDUCE_MOTOR_POWER] == 0, (
        "a volta a 100% não foi escrita: o firmware seguiria com a redução velha")
    assert _common(h.prepareReport())[1] & rep.VALID_FLAG1_MOTOR_POWER == 0


def test_o_motor_leva_so_o_que_o_firmware_nao_tira() -> None:
    """O byte do motor já chega escalado pelo funil; a soma (o byte vezes o firmware) é o pedido."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    for escala, chegou, sai in ((0.5, 60, 120), (0.3, 60, 160), (0.125, 30, 240), (1.0, 77, 77)):
        h = _handle(vib=escala)
        h.setRightMotor(chegou)
        c = _common(h.prepareReport())
        fracao = rep.fracao_do_firmware(c[rep.COMMON_REDUCE_MOTOR_POWER] & 0x07)
        assert c[2] == sai, (escala, c[2])
        assert abs(c[2] * fracao - chegou) <= 1, "a soma do byte com o firmware não é o pedido"
    h = _handle(vib=0.5)
    h.setRightMotor(200)
    assert _common(h.prepareReport())[2] == 255, "o motor passou do teto"


def _bloco_rigido(forca: int = 128) -> bytes:
    from hefesto_dualsense4unix.core import trigger_effects as te

    return te.bloco_do_efeito(te.rigid(2, forca))


def _forcas(bloco: list[int] | bytes) -> list[int]:
    mascara = bloco[1] | (bloco[2] << 8)
    empacotado = int.from_bytes(bytes(bloco[3:7]), "little")
    return [((empacotado >> (3 * z)) & 7) + 1 for z in range(10) if mascara & (1 << z)]


@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
def test_acima_de_100_o_gatilho_reforca_ate_a_forca_maxima(radio: bool) -> None:
    """O efeito do Hefesto e o bloco cru do jogo, os dois: 200% dobra, e nada passa de 8."""
    h = _handle(radio=radio, gat=2.0)
    h._raw_trigger_left = list(_bloco_rigido(128))
    h._raw_trigger_right = list(_bloco_rigido(220))
    c = _common(h.prepareReport())
    antes_l, antes_r = _forcas(_bloco_rigido(128)), _forcas(_bloco_rigido(220))
    assert _forcas(c[21:32]) == [min(8, 2 * f) for f in antes_l], "o L2 do jogo não reforçou"
    assert _forcas(c[10:21]) == [min(8, 2 * f) for f in antes_r], "o R2 passou do teto ou não subiu"
    assert c[36] == 0


def test_a_zero_o_gatilho_do_hefesto_solta_e_o_firmware_fica_no_passo_mais_fraco() -> None:
    h = _handle(gat=0.0)
    h._raw_trigger_right = list(_bloco_rigido(128))
    c = _common(h.prepareReport())
    assert c[10] == 0x05 and not any(c[11:21]), "o software deixou força no zero"
    assert c[36] >> 4 == 7


def test_o_bloco_que_nao_se_le_com_certeza_sai_como_veio() -> None:
    """O arco de 01/08 reaproveita o `0x26` com outro arranjo; o galope não tem força."""
    from hefesto_dualsense4unix.core import ds_output_report as rep
    from hefesto_dualsense4unix.core import trigger_effects as te

    for efeito in (te.bow(2, 8, 4, 4), te.galloping(1, 8, 2, 5, 30), te.off()):
        bloco = te.bloco_do_efeito(efeito)
        assert rep.escalar_o_bloco_do_gatilho(bloco, 2.0) == bloco, efeito


def test_os_modos_oficiais_reforcam_cada_um_no_seu_byte() -> None:
    from hefesto_dualsense4unix.core import ds_output_report as rep
    from hefesto_dualsense4unix.core import trigger_effects as te

    arma = te.bloco_do_efeito(te.weapon(2, 6, 128))
    assert rep.escalar_o_bloco_do_gatilho(arma, 2.0)[3] == 7, "a arma não reforçou"
    metralhadora = te.bloco_do_efeito(te.machine(1, 8, 4, 30))
    dobrada = rep.escalar_o_bloco_do_gatilho(metralhadora, 1.5)
    assert set(_forcas(dobrada)) == {6} and dobrada[9] == metralhadora[9], "a frequência mudou"


def _controlador(chaves: tuple[str, ...]):
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    ctl = PyDualSenseController.__new__(PyDualSenseController)
    ctl._io_lock = threading.RLock()
    ctl._rumble_scale_by_uniq = {}
    ctl._trigger_scale_by_uniq = {}
    ctl._handles = {k: _handle(radio=i % 2 == 1) for i, k in enumerate(chaves)}
    return ctl


def test_o_controlador_poe_a_escala_de_cada_um_nos_quatro_handles() -> None:
    """Starlight Blue e Cosmic Red no cabo, White e Galactic Purple no rádio: cada um a sua."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    ctl = _controlador(_MAC)
    ctl.set_trigger_scales({"aa:bb:cc:00:00:02": 0.5, _MAC[3]: 1.5})
    ctl.set_rumble_scales({_MAC[0]: 0.25})
    assert [ctl._handles[k]._escala_do_gatilho for k in _MAC] == [1.0, 0.5, 1.0, 1.5]
    assert [ctl._handles[k]._escala_da_vibracao for k in _MAC] == [0.25, 1.0, 1.0, 1.0]
    assert ctl.escala_do_gatilho_de(_MAC[1]) == 0.5 and ctl.escala_do_gatilho_de(_MAC[2]) is None
    reports = [_common(ctl._handles[k].prepareReport()) for k in _MAC]
    bytes36 = [c[rep.COMMON_REDUCE_MOTOR_POWER] for c in reports]
    assert bytes36 == [0x06, 0x40, 0x00, 0x00], [hex(b) for b in bytes36]
    ctl.set_trigger_scales(None)
    assert all(ctl._handles[k]._escala_do_gatilho == 1.0 for k in _MAC), "o mapa vazio não limpou"
