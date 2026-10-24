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

MORDIDAS DO DESENHO: volte o `TETO_DA_FORCA` da 05 a 100, ponha botões de degrau na «Força», tire a
linha da 03 do desenho, troque o `data-papel` do trilho da 03 por `data-hef` (o trilho volta a só
pintar), tire a linha da 03 da `camada.py`, tire o `_a_intensidade_que_fica` do `_com_os_gatilhos`,
ponha uma palavra de firmware na dica, ou aumente o respiro da grade da 03.

O PADRÃO DO COMPUTADOR (21/10/2026, A-INTENSIDADE-DO-GATILHO-VALE-NO-PADRAO-DO-COMPUTADOR-01): sem
jogo, o trilho da 03 grava no `maquina.json`, e o gerente aplica a escala lida dali em todo jogo
sem escolha própria. MORDIDAS: tire o `"triggers"` de `SECOES_DO_CONTROLE_NO_COMPUTADOR` (o
`maquina.json` recusa o gatilho), tire o `CAMPOS_DO_CONTROLE_NO_COMPUTADOR` do
`_CAMPOS_DO_CONTROLE` (o computador não chega ao perfil que vale), volte a camada da 03 a `_J`, ou
tire o `cem_por_cima` (o 100% do jogo deixa a do computador valer).
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
    # o ícone tem um dono comum de desenho, e as duas abas o conferem contra ele
    from hefesto_dualsense4unix.interface.monta import glifo_do_controle

    dono = glifo_do_controle()
    assert (dono, dono) == (aba03.GLIFO_DA_INTENSIDADE, aba05.GLIFO_DO_CONTROLE)


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
    primeiro_efeito = d03.index('data-gesto="imersao"')
    assert primeiro_trilho < primeiro_efeito, "a intensidade entra sob o chip, antes do L2"
    # o L2/R2 do estilo (r3b-03-15) fica como está: um campo de efeito por gatilho e por controle
    # (o acionamento saiu da página em 22/10/2026: o gatilho só tem o efeito)
    n = len(aba03.MESA)
    assert d03.count('data-gesto="modo"') == 0 and d03.count('data-gesto="imersao"') == 2 * n


def test_o_trilho_da_03_manda_o_gesto_e_tem_dono_e_camada(d03: str) -> None:
    """O trilho da 03 manda `data-papel` (o gesto), e o gesto tem atendente e camada.

    A prova da D-2110-A-INTENSIDADE-DO-GATILHO-VALE-NO-PADRAO-DO-COMPUTADOR, que substitui a
    D-2010-A-INTENSIDADE-DO-GATILHO-MORA-NO-PERFIL-DO-JOGO (caduca em 21/10/2026).

    Gesto sem dono reprova `test_os_sem_dono_so_diminuem`; gesto sem camada fica de fora do Nativo
    sem ninguém decidir. A camada é a do computador (`_C`), como a «Força da vibração» da 05.
    """
    from hefesto_dualsense4unix.interface import aba03
    from hefesto_dualsense4unix.interface.pacotes import camada

    g = aba03.GESTO_DA_INTENSIDADE
    trilhos = _trilhos(d03, aba03.CAMPO_DA_INTENSIDADE)
    assert trilhos and all(f'data-papel="{g}"' in t and "data-hef=" not in t for t in trilhos), (
        "o trilho da intensidade voltou a só pintar: o arrasto não chega ao produto")
    assert camada.CAMADA.get(("03-gatilhos.html", g)) == camada.COMPUTADOR == camada.CAMADA[
        ("05-vibracao.html", "intensidade")]


@pytest.fixture
def a03(monkeypatch):
    """O pacote da 03 (carrega o GTK real), com o disco do perfil em memória."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos, perfil

    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    disco: dict[str, object] = {"perfil": Profile(name="régua", match={"type": "any"})}
    gravados: list[object] = []
    reaplicados: list[str] = []

    def _gravar(prof, **_):
        gravados.append(prof)
        disco["perfil"] = prof

    monkeypatch.setattr(loader, "load_profile", lambda _nome: disco["perfil"], raising=False)
    monkeypatch.setattr(loader, "save_profile", _gravar, raising=False)
    monkeypatch.setattr(perfil, "reaplicar", lambda nome, *_a, **_k: reaplicados.append(nome))
    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos, disco, gravados, reaplicados
    a03_gatilhos.esquecer_o_rascunho()


class _Ponte:
    def __init__(self) -> None:
        self.avulsas: list[str] = []

    def chamar(self, metodo: str, **_) -> bool:
        self.avulsas.append(metodo)
        return True


def test_o_arrasto_da_03_grava_a_intensidade_daquele_controle_e_reaplica(a03) -> None:
    from pacotes import Contexto, gesto_da_pagina

    from hefesto_dualsense4unix.profiles.schema import TriggersConfig

    mod, disco, gravados, reaplicados = a03
    fn = gesto_da_pagina("03-gatilhos.html", mod.GESTO_DA_INTENSIDADE)
    assert fn is not None, "o trilho da 03 não tem dono"
    ctx = Contexto(state={"active_profile": "régua"}, mesa=[], conectados=[], estados={})
    ponte = _Ponte()

    fn(ctx, {"uniq": "aa:bb:cc:00:00:01", "valor": "50"}, ponte)
    dele = disco["perfil"].controllers["aabbcc000001"]  # type: ignore[attr-defined]
    padrao = TriggersConfig()
    assert dele.triggers.intensidade == 0.5 and dele.triggers.left == padrao.left, (
        "o trilho grava só a escala, e o efeito do lado fica o que era")
    assert reaplicados == ["régua"]

    fn(ctx, {"uniq": "aa:bb:cc:00:00:01", "valor": "50"}, ponte)
    assert len(gravados) == 1, "o segundo evento do mesmo arrasto (change e click) não regrava"

    fn(ctx, {"uniq": "aa:bb:cc:00:00:01", "valor": "100"}, ponte)
    volta = (disco["perfil"].controllers or {}).get("aabbcc000001")  # type: ignore[attr-defined]
    assert volta is None or "intensidade" not in volta.model_dump(mode="json").get(
        "triggers", {}), "100% é o firmware sem o byte: não vira opinião no perfil"

    for ruim in ("205", "abc", ""):
        with pytest.raises(RuntimeError):
            fn(ctx, {"uniq": "aa:bb:cc:00:00:01", "valor": ruim}, ponte)
    with pytest.raises((RuntimeError, ValueError)):
        fn(ctx, {"valor": "50"}, ponte)


def test_trocar_o_efeito_na_03_nao_apaga_a_intensidade(a03) -> None:
    from hefesto_dualsense4unix.profiles.schema import Profile

    mod, *_ = a03
    prof = Profile.model_validate({"name": "régua", "match": {"type": "any"}, "controllers": {
        "aabbcc000001": {"triggers": {"intensidade": 1.5}}}})
    novo = mod._com_os_gatilhos(prof, "aa:bb:cc:00:00:01",
                                {"left": {"mode": "Rigid", "params": [0, 180]}})
    assert novo.controllers["aabbcc000001"].triggers.intensidade == 1.5


def test_a_coluna_pinta_a_intensidade_lida_do_perfil(a03) -> None:
    from pacotes import Contexto, perfil

    mod, *_ = a03
    uniq = "aa:bb:cc:00:00:01"
    mesa = [{"pref": "p1", "jogador": 1, "uniq": uniq, "nome": "Régua", "via": "USB",
             "cor": "starlight-blue", "mascara": "DualSense"}]
    falso = {"uniq": uniq, "player": 1, "transport": "usb", "is_primary": True,
             "inputs": {"l2_raw": 0, "r2_raw": 0}}
    guardado = perfil.ativo
    perfil.ativo = lambda _n: {  # type: ignore[assignment]
        "triggers": {}, "controllers": {"aabbcc000001": {"triggers": {"intensidade": 1.5}}}}
    try:
        r = mod.pacote(Contexto(state={"active_profile": "régua"}, mesa=mesa,
                                conectados=[falso], estados={}))
    finally:
        perfil.ativo = guardado  # type: ignore[assignment]
    c = mod.CAMPO_DA_INTENSIDADE
    assert r["colunas"][uniq][c] == 150 and r["colunas"][uniq][f"{c}-pct"] == 150
    # o lugar vazio fica como o gerador o desenha: cursor no zero e travessão no número
    assert not [k for pref, col in r["colunas"].items() if pref != uniq for k in col if c in k]


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
    """A prova da D-2010-A-VIBRACAO-NO-NIBBLE-BAIXO-E-O-GATILHO-NO-ALTO."""
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
    """A prova da D-2010-A-INTENSIDADE-A-ZERO-ATENUA-E-NAO-CALA."""
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


def test_o_firmware_recebe_a_forca_absoluta_e_nao_o_fator_relativo_da_peca() -> None:
    """O global a 200% e a peça a 40%: o mapa guarda 0,2 (peça / global) e o funil dá 0,4 ao motor.

    O firmware tem de tirar os passos de 40% (4, metade), não os de 20% (6): com o fator relativo o
    byte do motor (102 = 255 · 0,4) dividido por 0,25 satura em 255, e a soma cai a 25%. O controle
    sem peça própria herda o global: a economia (30%) chega ao firmware também para ele.
    """
    from hefesto_dualsense4unix.core import ds_output_report as rep

    ctl = _controlador(_MAC[:2])
    ctl.set_rumble_base(2.0)
    ctl.set_rumble_scales({_MAC[0]: 0.2})
    assert ctl._handles[_MAC[0]]._escala_da_vibracao == pytest.approx(0.4)
    h = ctl._handles[_MAC[0]]
    h.setRightMotor(102)
    c = _common(h.prepareReport())
    assert c[rep.COMMON_REDUCE_MOTOR_POWER] & 0x07 == 4, hex(c[rep.COMMON_REDUCE_MOTOR_POWER])
    assert c[2] == 204, "o motor saturou: o firmware tirou mais que o funil"
    ctl.set_rumble_base(0.3)
    ctl.set_rumble_scales(None)
    assert [ctl._handles[k]._escala_da_vibracao for k in _MAC[:2]] == [0.3, 0.3]
    ctl.set_rumble_base(None)
    assert [ctl._handles[k]._escala_da_vibracao for k in _MAC[:2]] == [1.0, 1.0], (
        "o automático muda com a bateria: o firmware fica cheio e o software segue")


# --- O PERFIL: onde a intensidade do gatilho mora e quem a lê ------------------------------------


def _perfil(**campos: object):
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile.model_validate({"name": "Bancada", "match": {"type": "any"}, **campos})


def test_a_intensidade_do_gatilho_mora_no_controle_e_o_dump_sem_ela_e_o_de_antes() -> None:
    import json

    sem = _perfil()
    assert "intensidade" not in json.dumps(sem.model_dump(mode="json")), (
        "o perfil sem intensidade ganhou uma chave nova no disco")
    com = _perfil(controllers={_MAC[1]: {"triggers": {"intensidade": 0.45}}})
    dump = com.model_dump(mode="json")
    assert dump["controllers"][_MAC[1]]["triggers"]["intensidade"] == 0.45
    assert _perfil(**{k: v for k, v in dump.items() if k != "name"}).controllers[
        _MAC[1]].triggers.intensidade == 0.45, "a intensidade não volta do disco"
    with pytest.raises(ValueError):
        _perfil(controllers={_MAC[1]: {"triggers": {"intensidade": 2.5}}})


def test_a_economia_e_o_automatico_nao_perdem_a_intensidade() -> None:
    from hefesto_dualsense4unix.profiles.schema import (
        TriggersConfig,
        gatilhos_na_economia,
        perfil_no_modo,
    )

    dele = TriggersConfig.model_validate({"right": {"mode": "Rigid", "params": [2, 200]},
                                          "intensidade": 1.5})
    assert gatilhos_na_economia(dele, TriggersConfig()).intensidade == 1.5
    auto = _perfil(triggers={"modo": "automatico"},  # noqa-acento: chave ASCII
                   controllers={_MAC[2]: {"triggers": {"right": {"mode": "Rigid"},
                                                       "intensidade": 0.3}}})
    vista = perfil_no_modo(auto)
    assert vista.controllers[_MAC[2]].triggers.intensidade == 0.3, (
        "no Automático o efeito sai, mas o trilho multiplica o do jogo e tem de ficar")


def test_o_gerente_publica_a_intensidade_de_cada_controle() -> None:
    from hefesto_dualsense4unix.profiles.manager import (
        ProfileManager,
        _controllers_to_specs,
        _controllers_to_trigger_scales,
    )
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    perfil = _perfil(controllers={
        _MAC[0]: {"triggers": {"intensidade": 0.5}},
        _MAC[1]: {"triggers": {"intensidade": 1.0}},
        _MAC[3]: {"triggers": {"intensidade": 2.0}},
    })
    assert _controllers_to_trigger_scales(perfil.controllers) == {_MAC[0]: 0.5, _MAC[3]: 2.0}
    assert not _controllers_to_specs(perfil.controllers, perfil.leds), (
        "o controle que só tem intensidade ganhou um efeito de gatilho próprio")

    class Espiao(FakeController):
        def __init__(self, **kw: object) -> None:
            super().__init__(**kw)
            self.publicadas: list[object] = []

        def set_trigger_scales(self, scales: object = None) -> None:
            self.publicadas.append(None if scales is None else dict(scales))  # type: ignore[call-overload]

    fc = Espiao(transport="usb")
    fc.connect()
    ProfileManager(controller=fc).apply(perfil)
    assert fc.publicadas == [{_MAC[0]: 0.5, _MAC[3]: 2.0}], fc.publicadas


def test_o_gerente_publica_a_base_do_global_para_o_firmware() -> None:
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    class Espiao(FakeController):
        def __init__(self, **kw: object) -> None:
            super().__init__(**kw)
            self.bases: list[float | None] = []

        def set_rumble_base(self, base: float | None = None) -> None:
            self.bases.append(base)

    for rumble, esperado in (({"policy": "custom", "custom_mult": 2.0}, 2.0),
                             ({"policy": "economia"}, 0.3), (None, 1.0),
                             ({"policy": "auto"}, None)):
        fc = Espiao(transport="usb")
        fc.connect()
        ProfileManager(controller=fc).apply(_perfil(**({"rumble": rumble} if rumble else {})))
        assert fc.bases == [esperado], (rumble, fc.bases)


# --- O PADRÃO DO COMPUTADOR: sem jogo, a intensidade do gatilho mora no `maquina.json` ------------
# A-INTENSIDADE-DO-GATILHO-VALE-NO-PADRAO-DO-COMPUTADOR-01 (21/10/2026). O disco é o de verdade, no
# lar isolado da suíte: o perfil por `save_profile` e o computador pelo `maquina.json`.

_UM = "aa:bb:cc:00:00:01"


@pytest.fixture
def a03_no_disco(monkeypatch):
    """O pacote da 03 com o disco isolado de verdade; só o reaplicar no daemon é de papel."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos, perfil

    reaplicados: list[str] = []
    monkeypatch.setattr(perfil, "reaplicar", lambda nome, *_a, **_k: reaplicados.append(nome))
    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos, reaplicados
    a03_gatilhos.esquecer_o_rascunho()


def _jogo(nome: str, **campos: object):
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import Profile

    return save_profile(Profile.model_validate(
        {"name": nome, "match": {"type": "criteria", "window_class": [nome.lower()]}, **campos}))


def _arrastar(mod, ativo: str, valor: str) -> None:
    from pacotes import Contexto, gesto_da_pagina

    fn = gesto_da_pagina("03-gatilhos.html", mod.GESTO_DA_INTENSIDADE)
    assert fn is not None, "o trilho da 03 não tem dono"
    fn(Contexto(state={"active_profile": ativo}, mesa=[], conectados=[], estados={}),
       {"uniq": _UM, "valor": valor}, _Ponte())


def _escala_do_computador() -> float | None:
    from hefesto_dualsense4unix.utils import maquina as m

    dele = m.carregar_maquina().computador.controles.get(_MAC[0])
    return dele.triggers.intensidade if dele is not None and dele.triggers is not None else None


def _o_gerente_publica(nome: str) -> list[object]:
    """O que o `ProfileManager` publica ao aplicar ``nome`` com o computador por baixo."""
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import carregar_o_que_vale
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    class Espiao(FakeController):
        def __init__(self, **kw: object) -> None:
            super().__init__(**kw)
            self.publicadas: list[object] = []

        def set_trigger_scales(self, scales: object = None) -> None:
            self.publicadas.append(None if scales is None else dict(scales))  # type: ignore[call-overload]

    fc = Espiao(transport="usb")
    fc.connect()
    ProfileManager(controller=fc).apply(carregar_o_que_vale(nome))
    return fc.publicadas


@pytest.mark.parametrize("ativo", ["Freestyle", ""])
def test_sem_jogo_o_trilho_grava_no_computador_e_vale_em_todo_jogo(a03_no_disco, ativo) -> None:
    """Sem jogo (o Freestyle, ou nenhum perfil), o arrasto vai ao `maquina.json` e a perfil nenhum.

    O gerente aplica a escala lida dali num jogo sem escolha própria, e a coluna da 03 a pinta.
    Antes desta sprint o gesto recusava sem perfil, e o `maquina.json` recusava o gatilho.
    """
    from pacotes import Contexto

    mod, reaplicados = a03_no_disco
    caminhos = [_jogo("Freestyle"), _jogo("Jogo Y")]
    antes = [c.read_bytes() for c in caminhos]

    _arrastar(mod, ativo, "40")

    assert _escala_do_computador() == 0.4, "o trilho sem jogo não chegou ao padrão do computador"
    assert [c.read_bytes() for c in caminhos] == antes, "o trilho sem jogo mudou um perfil"
    assert reaplicados == [ativo]
    assert _o_gerente_publica("Jogo Y") == [{_MAC[0]: 0.4}], (
        "o jogo sem escolha própria não recebeu a intensidade do computador")
    mesa = [{"pref": "p1", "jogador": 1, "uniq": _UM, "nome": "Régua", "via": "USB",
             "cor": "starlight-blue", "mascara": "DualSense"}]
    falso = {"uniq": _UM, "player": 1, "transport": "usb", "is_primary": True,
             "inputs": {"l2_raw": 0, "r2_raw": 0}}
    r = mod.pacote(Contexto(state={"active_profile": ativo}, mesa=mesa, conectados=[falso],
                            estados={}))
    assert r["colunas"][_UM][mod.CAMPO_DA_INTENSIDADE] == 40, "a coluna não leu o computador"

    _arrastar(mod, ativo, "100")
    assert _escala_do_computador() is None, "100% no computador é tirar a escolha, não gravar 1,0"


def test_com_jogo_o_trilho_grava_no_jogo_e_o_100_dele_vence_o_do_computador(a03_no_disco) -> None:
    """Com um jogo ativo, o arrasto vai ao perfil dele; o computador e o outro jogo ficam.

    O 100% do jogo por cima de 40% do computador grava o 1,0: sem ele, os 40% voltariam a valer.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.utils import maquina as m

    mod, _ = a03_no_disco
    assert m.gravar_o_computador({"controles": {_MAC[0]: {"triggers": {"intensidade": 0.4}}}})
    _jogo("Jogo X", controllers={_MAC[0]: {"triggers": {"left": {"mode": "Rigid",
                                                                   "params": [0, 180]}}}})
    outro = _jogo("Jogo Y")
    antes = outro.read_bytes()

    _arrastar(mod, "Jogo X", "150")
    dele = load_profile("Jogo X").controllers[_MAC[0]].triggers
    assert dele.intensidade == 1.5 and (dele.left.mode, dele.left.params) == ("Rigid", [0, 180]), (
        "o trilho grava a escala no jogo e o efeito dele fica")
    assert _escala_do_computador() == 0.4 and outro.read_bytes() == antes
    assert _o_gerente_publica("Jogo X") == [{_MAC[0]: 1.5}]
    assert _o_gerente_publica("Jogo Y") == [{_MAC[0]: 0.4}]

    _arrastar(mod, "Jogo X", "100")
    assert load_profile("Jogo X").controllers[_MAC[0]].triggers.intensidade == 1.0
    assert _o_gerente_publica("Jogo X") == [None], "o 100% do jogo deixou a do computador valer"


def test_o_computador_guarda_so_a_intensidade_e_nunca_o_efeito() -> None:
    """O efeito do gatilho é de cada jogo: o `maquina.json` com um lado recusa o documento."""
    from hefesto_dualsense4unix.utils import maquina as m

    assert m.gravar_o_computador({"controles": {_MAC[0]: {"triggers": {"intensidade": 0.7}}}})
    with pytest.raises(ValueError, match=r"triggers\.left"):
        m.MaquinaConfig.model_validate({"computador": {"controles": {
            _MAC[0]: {"triggers": {"left": {"mode": "Rigid"}, "intensidade": 0.7}}}}})


def test_a_migracao_leva_ao_computador_so_a_intensidade_do_freestyle() -> None:
    """A semente e o ceder da migração tiram do Freestyle só a intensidade; o efeito fica nele.

    MORDIDAS: tire o `_so_a_parte_do_computador` da `semente_do_freestyle` (o `maquina.json` recusa
    o lado e a migração não semeia), ou o `_sem_a_parte_do_computador` do `ceder_ao_computador` (o
    efeito do gatilho do Freestyle some junto).
    """
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
    from hefesto_dualsense4unix.profiles.loader import load_profile

    _jogo("Freestyle", controllers={_MAC[0]: {"triggers": {
        "left": {"mode": "Rigid", "params": [0, 180]}, "intensidade": 0.6}}})

    assert opc.migrar_uma_vez() is not None, "a migração não semeou o computador"
    assert _escala_do_computador() == 0.6, "a intensidade do Freestyle não foi ao computador"
    dele = load_profile("Freestyle").controllers[_MAC[0]].triggers
    assert (dele.left.mode, dele.left.params) == ("Rigid", [0, 180]), (
        "a migração tirou do Freestyle o efeito do gatilho, que é dele")
    assert "intensidade" not in dele.model_fields_set, "a intensidade ficou nos dois lugares"


def test_voltar_ao_do_computador_no_gatilho_tira_so_a_intensidade_do_jogo() -> None:
    """O «voltar ao do computador» do cartão `gatilho` tira do jogo a escala, nunca o efeito.

    MORDIDA: tire o `_sem_a_parte_do_computador` do `voltar_ao_do_computador`, e o lado do jogo
    sai junto com a intensidade.
    """
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
    from hefesto_dualsense4unix.profiles.loader import load_profile

    _jogo("Jogo X", controllers={_MAC[0]: {"triggers": {
        "left": {"mode": "Rigid", "params": [0, 180]}, "intensidade": 1.5}}})

    opc.voltar_ao_do_computador(_cartao_da_03(), _UM, "Jogo X")

    dele = load_profile("Jogo X").controllers[_MAC[0]].triggers
    assert (dele.left.mode, dele.left.params) == ("Rigid", [0, 180]), (
        "voltar ao do computador apagou o efeito do gatilho do jogo")
    assert "intensidade" not in dele.model_fields_set


def _cartao_da_03() -> str:
    """O cartão do computador em que a intensidade mora, lido do dono (sem carregar o GTK)."""
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

    (nome,) = [n for n, s in opc.SECOES.items() if s.pagina == "03-gatilhos.html"]
    return nome
