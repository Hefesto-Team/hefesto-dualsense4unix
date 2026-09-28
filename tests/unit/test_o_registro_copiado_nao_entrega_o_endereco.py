"""O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01 — a régua do dono das formas do endereço.

O dono é ``core/formas_do_endereco.py``. Esta régua mede o que ELE faz: as
seis formas, as duas ordens de byte, os separadores, o virtual derivado, o
serial, e o que não pode ser corrompido (o carimbo, o PID, o UUID, o despejo).
E mede os que o chamam (onda 2): os seis mascaradores do produto e o
``_id_visivel`` (régua 3), o diário (4), o «Copiar» (5), o ensaio do touchpad
num clone limpo (6) e as três réguas de forma (7).

**Nenhum endereço aparece literal aqui**: os portões de anonimato varrem
``tests/``. O endereço é montado em tempo de execução, na faixa das fixtures
(``aa:bb:cc``), com os octetos 4 e 5 só de algarismos, para que o par forme
um MM:SS válido: é o carimbo que a contraprova da
O-ENDERECO-NUNCA-CHEGA-A-CONVERSA-01 viu corrompido. O detector de janelas é
desta régua e não do dono: duas réguas independentes é o que revela.

As mordidas estão escritas como teste (``test_mordida_*``): cada uma arranca
uma parte do dono e confere que a régua reprova.
"""
from __future__ import annotations

import ast
import io
import itertools
import logging
import os
import re
import subprocess
import sys
import textwrap
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import structlog

from hefesto_dualsense4unix.core import formas_do_endereco as dono
from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac, vpad_macs_do_aparelho

RAIZ = Path(__file__).resolve().parents[2]

OCTETOS = ("aa", "bb", "cc", "34", "56", "7e")
MASCARADO = ("aa", "bb", "cc", "00", "00", "7e")
SEPARADORES = (":", "-", "_", ".", " ", "")
ENDERECO = ":".join(OCTETOS)
SUFIXO = "".join(OCTETOS[3:])
SUFIXO_MASCARADO = "".join(MASCARADO[3:])
VIRTUAL_MASCARADO = ("02", "fe", "80", "00", "00", "00")


@pytest.fixture(autouse=True)
def _cache_limpo() -> Iterator[None]:
    """O dono guarda os padrões dos conhecidos; uma mordida não pode herdar os de outro teste."""
    dono._o_que_se_conhece.cache_clear()
    yield
    dono._o_que_se_conhece.cache_clear()


def _janelas_que_sobram(texto: str, octetos: tuple[str, ...] = OCTETOS) -> list[str]:
    """Os pedaços com o octeto 4 ou o 5 que sobraram, medidos aqui, sem o dono.

    Por substring e sem alinhar: mais estrito que o dono.
    """
    baixo = texto.lower()
    achados = []
    for inicio in (1, 2, 3):
        direta = [octetos[i] for i in range(inicio, inicio + 3)]
        for ordem in (direta, direta[::-1]):
            for separador in SEPARADORES:
                if separador.join(ordem) in baixo:
                    achados.append(f"janela {inicio} {'direta' if ordem is direta else 'invertida'}"
                                   f" com {separador!r}")
    return achados


def _virtuais() -> list[str]:
    """O virtual que o vpad deste endereço pede, e o seguinte do mesmo aparelho."""
    primeiro, segundo = itertools.islice(vpad_macs_do_aparelho(ENDERECO, 1), 2)
    assert primeiro == vpad_mac(ENDERECO, 1)
    return [primeiro, segundo]


def _hash_que_sobra(saida: str, virtual: str) -> list[int]:
    """Os octetos do hash do virtual (3 a 6) que aparecem na saída, na mesma posição."""
    hash_do_virtual = virtual.lower().split(":")[2:]
    achados = []
    for mac in re.findall(r"02[:\-_.]?fe[:\-_.]?(?:[0-9a-f]{2}[:\-_.]?){3}[0-9a-f]{2}",
                          saida.lower()):
        octetos = re.findall(r"[0-9a-f]{2}", mac)[2:]
        pares = zip(octetos, hash_do_virtual, strict=True)
        achados += [i + 3 for i, (a, b) in enumerate(pares) if a == b]
    return achados


def _formas() -> dict[str, tuple[str, str]]:
    """Forma -> (a linha com o endereço, a linha mascarada), montadas sem o dono."""
    virtual, segundo = _virtuais()
    invertida = " ".join(reversed(OCTETOS))
    invertida_mascarada = " ".join(reversed(MASCARADO))
    return {
        "1 separada com dois-pontos": (f"uniq={ENDERECO}", f"uniq={':'.join(MASCARADO)}"),
        "1 separada com hífen": (f"x={'-'.join(OCTETOS)}", f"x={'-'.join(MASCARADO)}"),
        "1 separada com ponto": (f"x={'.'.join(OCTETOS)}", f"x={'.'.join(MASCARADO)}"),
        "1 o caminho do BlueZ": (
            f"/org/bluez/hci0/dev_{'_'.join(OCTETOS).upper()}/sep1",
            f"/org/bluez/hci0/dev_{'_'.join(MASCARADO).upper()}/sep1",
        ),
        "2 colada": (f"uniq={''.join(OCTETOS)}", f"uniq={''.join(MASCARADO)}"),
        "2 colada em maiúsculas": (
            f"chave={''.join(OCTETOS).upper()}", f"chave={''.join(MASCARADO).upper()}"
        ),
        "3 o sufixo do nó": (
            f"som=hefesto_som_{SUFIXO} mic=hefesto_mic_{SUFIXO.upper()} h=hefesto_haptica_{SUFIXO}",
            f"som=hefesto_som_{SUFIXO_MASCARADO} mic=hefesto_mic_{SUFIXO_MASCARADO.upper()}"
            f" h=hefesto_haptica_{SUFIXO_MASCARADO}",
        ),
        "4 o nome do endpoint": (
            "sink=alsa_output.usb-Sony_DualSense_Wireless_Controller_HEFESTO"
            f"{SUFIXO}-00.HiFi__Speaker__sink uniq={ENDERECO}",
            "sink=alsa_output.usb-Sony_DualSense_Wireless_Controller_HEFESTO"
            f"{SUFIXO_MASCARADO}-00.HiFi__Speaker__sink uniq={':'.join(MASCARADO)}",
        ),
        "5 a invertida com espaço": (
            f"0x09: 09 {invertida} 08 25", f"0x09: 09 {invertida_mascarada} 08 25"
        ),
        "6 o rótulo do gravador da ponte": (
            f"som_gravador_alvo_nao_conferido rotulo=hefesto-ponte-{SUFIXO}-sink",
            f"som_gravador_alvo_nao_conferido rotulo=hefesto-ponte-{SUFIXO_MASCARADO}-sink",
        ),
        "o virtual derivado": (
            f"uhid_device_created mac={virtual}",
            f"uhid_device_created mac={':'.join(VIRTUAL_MASCARADO)}",
        ),
        "o segundo virtual do mesmo aparelho": (
            f"mac={segundo}", f"mac={':'.join(VIRTUAL_MASCARADO)}"
        ),
        "o virtual colado": (
            f"uniq={virtual.replace(':', '')}", f"uniq={''.join(VIRTUAL_MASCARADO)}"
        ),
        "o virtual numerado segue a forma 1": (
            f"mac={':'.join(('02', 'fe', '00', '00', '03', '01'))}",
            f"mac={':'.join(('02', 'fe', '00', '00', '00', '01'))}",
        ),
    }


def test_os_virtuais_da_prova_tem_o_hash_a_mostra() -> None:
    """A premissa: sem o dono, os virtuais sintéticos carregam hash que a régua sabe ver."""
    for virtual in _virtuais():
        octetos = virtual.split(":")
        assert int(octetos[2], 16) & 0x80
        assert octetos[2] != "80" and all(o != "00" for o in octetos[2:]), virtual
        assert _hash_que_sobra(f"mac={virtual}", virtual) == [3, 4, 5, 6]


@pytest.mark.parametrize("forma", sorted(_formas()))
def test_cada_forma_sai_mascarada_com_os_conhecidos(forma: str) -> None:
    linha, esperada = _formas()[forma]
    saida = dono.mascarar(linha, conhecidos=[ENDERECO])
    assert saida == esperada, forma
    assert _janelas_que_sobram(saida) == []
    for virtual in _virtuais():
        assert _hash_que_sobra(saida, virtual) == []


@pytest.mark.parametrize("forma", sorted(_formas()))
def test_sem_os_conhecidos_o_mesmo_menos_a_quinta(forma: str) -> None:
    """A invertida com espaço é só dos conhecidos: o espaço fica fora da forma."""
    linha, esperada = _formas()[forma]
    saida = dono.mascarar(linha)
    if forma.startswith("5 "):
        assert saida == linha
        assert _janelas_que_sobram(saida) != []
    else:
        assert saida == esperada, forma
        assert _janelas_que_sobram(saida) == []


def test_o_texto_inteiro_de_uma_vez_e_idempotente() -> None:
    linhas, esperadas = zip(*_formas().values(), strict=True)
    texto = "\n".join(linhas)
    saida = dono.mascarar(texto, conhecidos=[ENDERECO])
    assert saida == "\n".join(esperadas)
    assert dono.mascarar(saida, conhecidos=[ENDERECO]) == saida
    assert _janelas_que_sobram(saida) == []


@pytest.mark.parametrize("inicio", [1, 2, 3])
@pytest.mark.parametrize("invertida", [False, True])
@pytest.mark.parametrize("separador", SEPARADORES)
def test_toda_janela_dos_conhecidos_nas_duas_ordens_e_em_todo_separador(
    inicio: int, invertida: bool, separador: str
) -> None:
    janela = [OCTETOS[i] for i in range(inicio, inicio + 3)]
    if invertida:
        janela.reverse()
    for caixa in (str.lower, str.upper):
        texto = f"antes {caixa(separador.join(janela))} depois"
        saida = dono.mascarar(texto, conhecidos=[ENDERECO])
        assert _janelas_que_sobram(saida) == [], (inicio, invertida, separador)
        assert saida.startswith("antes ") and saida.endswith(" depois")


@pytest.mark.parametrize(
    "grafia",
    [
        ENDERECO,
        ENDERECO.upper(),
        "-".join(OCTETOS),
        "_".join(OCTETOS).upper(),
        ".".join(OCTETOS),
        " ".join(OCTETOS),
        "".join(OCTETOS),
    ],
)
def test_o_conhecido_vale_em_qualquer_grafia(grafia: str) -> None:
    linha, esperada = _formas()["5 a invertida com espaço"]
    assert dono.mascarar(linha, conhecidos=[grafia]) == esperada


def test_o_conhecido_colado_dentro_de_uma_corrida_hex_maior() -> None:
    """Um despejo sem separador: a janela é alinhada pelo começo da corrida."""
    corrida = "3109" + "".join(reversed(OCTETOS)) + "0825"
    saida = dono.mascarar(f"bruto={corrida}", conhecidos=[ENDERECO])
    assert saida == "bruto=3109" + "".join(reversed(MASCARADO)) + "0825"


def test_o_conhecido_colado_numa_corrida_impar_se_le_nas_duas_paridades() -> None:
    """Corrida ímpar não diz onde começa o octeto: o endereço fica na paridade ímpar aqui."""
    corrida = "a" + "".join(reversed(OCTETOS)) + "08"
    assert len(corrida) % 2 == 1
    saida = dono.mascarar(f"bruto={corrida}", conhecidos=[ENDERECO])
    assert saida == "bruto=a" + "".join(reversed(MASCARADO)) + "08"
    assert _janelas_que_sobram(saida) == []


def test_o_conhecido_solto_vale_como_um() -> None:
    """``str`` é ``Iterable[str]``: iterado, o endereço solto viraria letras e a camada calaria."""
    linha, esperada = _formas()["5 a invertida com espaço"]
    assert dono.mascarar(linha, conhecidos=ENDERECO) == esperada


def test_conhecido_que_nao_e_endereco_nem_serial_e_ignorado() -> None:
    linha, _esperada = _formas()["5 a invertida com espaço"]
    lixo = cast(list[str], [None, 42, "", "dev:0005:054C:0CE6.0003", "path:/dev/hidraw3"])
    assert dono.mascarar(linha, conhecidos=lixo) == linha
    assert dono.mascarar("o controle desconhecido", conhecidos=["desconhecido"]) == (
        "o controle desconhecido"
    )


# --- o que não é endereço fica -------------------------------------------------------


def _linhas_que_nao_sao_endereco() -> dict[str, str]:
    """As cinco da contraprova, o `dev:`, o caminho de /sys e as duas do diário de 27/09.

    Montadas, nunca literais. As duas do diário (o appid da Steam e o carimbo de
    versão do perfil) têm seis algarismos depois do ``_``: a forma 3 as lia como
    sufixo de nó.
    """
    uuid = "-".join(("1f0e2d3c", "4b5a", "6978", "8796", "a5b4c3" + "d2e1f0"))
    par = OCTETOS[3], OCTETOS[4]
    return {
        "o carimbo cujo MM:SS é o par": (
            f"2026-09-28T03:{par[0]}:{par[1]}.123456Z [info     ] poll.tick hz=250"
        ),
        "o carimbo do journal": f"set 28 03:{par[0]}:{par[1]} hefesto-dualsense4unix[1234]: ok",
        "o PID de quatro algarismos": f"daemon_iniciado pid={par[0]}{par[1]}",
        "o UUID": f"/home/x/.cache/sessoes/{uuid}/rascunho/a.txt",
        "o despejo do 0x31": (
            f"report 0x31: 31 01 7f 80 7f 7f 08 00 00 00 00 {par[0]} {par[1]} 00 00 00 12 34"
        ),
        "a linha do btmon": "        a1 31 00 7f 80 7f 7f 08 00 00 00 00 00 12 ab cd ef 01",
        "a instância do HID": "chave=dev:0005:054C:0CE6.0003",
        "o caminho de /sys": (
            "/sys/devices/pci0000:00/0000:00:08.1/0000:0b:00.3/usb3/3-2/3-2:1.3/"
            "0003:054C:0CE6.0007/hidraw/hidraw4"
        ),
        "o appid da Steam de seis algarismos": (
            f"autoswitch_janela_excluida wm_class=steam_app_{par[0]}{par[1]}00"
        ),
        "o carimbo de versão do perfil": (
            "perfil_versionado arquivo=/home/x/.config/perfis/.historico/jogo/"
            f"20260928T031530_{par[0]}{par[1]}12.json"
        ),
    }


@pytest.mark.parametrize("nome", sorted(_linhas_que_nao_sao_endereco()))
def test_o_que_nao_e_endereco_fica(nome: str) -> None:
    linha = _linhas_que_nao_sao_endereco()[nome]
    assert dono.mascarar(linha) == linha
    assert dono.mascarar(linha, conhecidos=[ENDERECO]) == linha


# --- mascarar_endereco -------------------------------------------------------------------


@pytest.mark.parametrize(
    "grafia",
    [
        ENDERECO,
        ENDERECO.upper(),
        "-".join(OCTETOS),
        "_".join(OCTETOS),
        ".".join(OCTETOS),
        "".join(OCTETOS),
        "".join(OCTETOS).upper(),
        f"  {ENDERECO}\n",
    ],
)
def test_mascarar_endereco_em_cada_grafia(grafia: str) -> None:
    assert dono.mascarar_endereco(grafia) == ":".join(MASCARADO)


@pytest.mark.parametrize(
    "valor",
    [
        None,
        "",
        "dev:0005:054C:0CE6.0003",
        "path:/dev/hidraw3",
        "x" + "".join(OCTETOS),  # a peneira faria doze hex daqui
        ENDERECO + "/",
        "".join(OCTETOS)[:-1],
        "".join(OCTETOS) + "0",
        " ".join(OCTETOS),  # o espaço não é da forma
        ":".join(OCTETOS[:3]) + "-" + "-".join(OCTETOS[3:]),  # dois separadores
        f"hefesto-ponte-{SUFIXO}-sink",
    ],
)
def test_mascarar_endereco_descarta_em_vez_de_peneirar(valor: str | None) -> None:
    assert dono.mascarar_endereco(valor) is None


def test_mascarar_endereco_e_o_virtual() -> None:
    for virtual in _virtuais():
        assert dono.mascarar_endereco(virtual) == ":".join(VIRTUAL_MASCARADO)
        assert dono.mascarar_endereco(virtual.replace(":", "").upper()) == ":".join(
            VIRTUAL_MASCARADO
        )
    numerado = ":".join(("02", "fe", "00", "00", "03", "01"))
    assert dono.mascarar_endereco(numerado) == ":".join(("02", "fe", "00", "00", "00", "01"))
    assert dono.mascarar_endereco(":".join(MASCARADO)) == ":".join(MASCARADO)


# --- formas_do_endereco -------------------------------------------------------------------


def _pedacos_esperados(octetos: tuple[str, ...]) -> set[str]:
    esperados: set[str] = set()
    for inicio in (1, 2, 3):
        indices = range(inicio, inicio + 3)
        if all(octetos[i] == "00" for i in indices if i in (3, 4)):
            continue
        direta = [octetos[i] for i in indices]
        for ordem in (direta, direta[::-1]):
            for separador in SEPARADORES:
                esperados |= {separador.join(ordem), separador.join(ordem).upper()}
    return esperados


def test_formas_do_endereco_sao_as_janelas_nas_duas_ordens_e_em_todo_separador() -> None:
    pedacos = dono.formas_do_endereco(OCTETOS)
    assert pedacos == _pedacos_esperados(OCTETOS)
    assert len(pedacos) == 3 * 2 * len(SEPARADORES) * 2
    assert "aabbcc" not in pedacos  # o fabricante não é escondido
    assert dono.formas_do_endereco(ENDERECO) == pedacos
    assert dono.formas_do_endereco("".join(OCTETOS).upper()) == pedacos


def test_formas_do_endereco_sem_o_que_a_mascara_ja_zerou() -> None:
    assert dono.formas_do_endereco(MASCARADO) == frozenset()
    so_o_quinto = ("aa", "bb", "cc", "00", "56", "7e")
    pedacos = dono.formas_do_endereco(so_o_quinto)
    assert pedacos == _pedacos_esperados(so_o_quinto)
    assert "bb:cc:00" not in pedacos and "cc:00:56" in pedacos


@pytest.mark.parametrize(
    "valor",
    [
        ("aa", "bb", "cc", "34", "56"),
        ("aa", "bb", "cc", "34", "56", "zz"),
        "dev:0005:054C:0CE6.0003",
    ],
)
def test_formas_do_endereco_de_um_nao_endereco_e_vazio(valor: Any) -> None:
    assert dono.formas_do_endereco(valor) == frozenset()


# --- o serial -----------------------------------------------------------------------------


def _serial_forjado_na_forma_real() -> str:
    """O mesmo forjado do portão de serial: montado, nunca escrito por extenso."""
    return "Q" + "88" + "X" + "77" + "K" + "9876543210"


def test_o_serial_de_fabrica_sai_com_os_seis_publicos() -> None:
    serial = _serial_forjado_na_forma_real()
    publicos = dono.CARACTERES_PUBLICOS_DO_SERIAL
    mascarado = serial[:publicos] + "#" * (len(serial) - publicos)
    linha = "P1 · DualSense · USB · "
    assert dono.mascarar(linha + serial) == linha + mascarado
    for palavra in ("INDEPENDENTEMENTE", "MICROCASSYVOLTAGE", "REDIMENSIONAMENTO"):
        assert dono.mascarar(palavra) == palavra


def test_o_serial_conhecido_fora_da_forma_tambem_sai() -> None:
    """O conhecido não precisa casar com o padrão: quem chama sabe que é serial."""
    serial = "AB1C05" + "D1234567890"
    assert dono.mascarar(f"serial={serial}") == f"serial={serial}"
    assert dono.mascarar(f"serial={serial}", conhecidos=[serial]) == "serial=AB1C05" + "#" * 11


def _constante_ou_import(caminho: Path, nome: str) -> object:
    """O valor literal de ``nome`` no arquivo, ou ``"dono"`` se ele o importa do dono."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign) and any(
            isinstance(alvo, ast.Name) and alvo.id == nome for alvo in no.targets
        ):
            return ast.literal_eval(no.value)
        if (
            isinstance(no, ast.ImportFrom)
            and no.module == "hefesto_dualsense4unix.core.formas_do_endereco"
            and any(alias.name == nome for alias in no.names)
        ):
            return "dono"
    raise AssertionError(f"{nome} sumiu de {caminho.relative_to(RAIZ)}")


@pytest.mark.parametrize(
    ("caminho", "nome"),
    [
        ("scripts/ensaios/cor_do_plastico.py", "CARACTERES_PUBLICOS_DO_SERIAL"),
        ("tests/unit/test_docs_mac_anonimato.py", "CARACTERES_PUBLICOS_DO_SERIAL"),
        ("tests/unit/test_docs_mac_anonimato.py", "PADRAO_DE_SERIAL"),
    ],
)
def test_o_serial_tem_um_dono_e_as_copias_nao_divergem(caminho: str, nome: str) -> None:
    """Até a onda 2 trocar as cópias por import, elas têm de dizer o mesmo que o dono."""
    valor = _constante_ou_import(RAIZ / caminho, nome)
    assert valor in ("dono", getattr(dono, nome)), (caminho, nome)


# --- o dono não puxa o diário -------------------------------------------------------------


_BIBLIOTECA_PADRAO_DO_DONO = {"__future__", "collections.abc", "dataclasses", "functools", "re"}


def test_o_dono_so_importa_a_biblioteca_padrao_no_topo() -> None:
    """O ``logging_config`` vai chamar o dono; um import do produto no topo é um ciclo."""
    fonte = RAIZ / "src/hefesto_dualsense4unix/core/formas_do_endereco.py"
    modulos = set()
    for no in ast.parse(fonte.read_text(encoding="utf-8")).body:
        if isinstance(no, ast.Import):
            modulos |= {alias.name for alias in no.names}
        elif isinstance(no, ast.ImportFrom):
            modulos.add(no.module or "")
    assert modulos <= _BIBLIOTECA_PADRAO_DO_DONO, modulos - _BIBLIOTECA_PADRAO_DO_DONO


def test_importar_o_dono_nao_puxa_o_diario_nem_o_vpad() -> None:
    codigo = (
        "import sys, hefesto_dualsense4unix.core.formas_do_endereco\n"
        "print(sorted(m for m in sys.modules if m == 'structlog' or m.endswith("
        "('logging_config', 'uhid_gamepad'))))"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, timeout=60,
        env=os.environ.copy(), check=True,
    ).stdout.strip()
    assert saida == "[]", saida


# --- as mordidas --------------------------------------------------------------------------


def _nunca() -> re.Pattern[str]:
    """Um padrão que nunca casa, com os dois grupos que as trocas do dono citam."""
    return re.compile(r"(?!)(x)(x)")


@pytest.mark.parametrize(
    ("atributo", "forma"),
    [
        ("_ROTULO_DO_GRAVADOR", "6 o rótulo do gravador da ponte"),
        ("_NOME_DO_ENDPOINT", "4 o nome do endpoint"),
        ("_SUFIXO_DO_NO", "3 o sufixo do nó"),
        ("_COLADA", "2 colada"),
        ("_SEPARADA", "1 separada com dois-pontos"),
    ],
)
def test_mordida_sem_uma_forma_a_regua_reprova(
    monkeypatch: pytest.MonkeyPatch, atributo: str, forma: str
) -> None:
    linha, _esperada = _formas()[forma]
    assert _janelas_que_sobram(dono.mascarar(linha)) == []
    monkeypatch.setattr(dono, atributo, _nunca())
    assert _janelas_que_sobram(dono.mascarar(linha)) != [], atributo


def test_mordida_sem_o_caso_do_virtual_o_hash_fica(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dono, "_o_virtual", lambda: (("zz", "zz"), 0x80))
    for virtual in _virtuais():
        saida = dono.mascarar(f"uhid_device_created mac={virtual}")
        assert _hash_que_sobra(saida, virtual) == [3, 6], saida


def test_mordida_sem_a_ordem_invertida_o_despejo_vaza(monkeypatch: pytest.MonkeyPatch) -> None:
    def so_a_direta(octetos: Any) -> Iterator[tuple[int, int, int]]:
        for inicio in (1, 2, 3):
            yield (inicio, inicio + 1, inicio + 2)

    monkeypatch.setattr(dono, "_janelas", so_a_direta)
    linha, _esperada = _formas()["5 a invertida com espaço"]
    assert _janelas_que_sobram(dono.mascarar(linha, conhecidos=[ENDERECO])) != []
    assert "7e 56 34" not in dono.formas_do_endereco(OCTETOS)


def test_mordida_zerar_uma_janela_antes_de_achar_a_outra_deixa_o_quinto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A primeira versão da máscara da bancada zerava janela a janela e o quinto sobrava."""
    original = dono._pelos_conhecidos

    def janela_a_janela(texto: str, conhecidos: Any) -> str:
        for padrao, octetos in conhecidos.separadas:
            for achado in padrao.finditer(texto):
                inicio = achado.start()
                letras = list(texto)
                for k in octetos:
                    letras[inicio + 3 * k] = letras[inicio + 3 * k + 1] = "0"
                texto = "".join(letras)
                break
        return texto

    linha, esperada = _formas()["5 a invertida com espaço"]
    assert original(linha, dono._o_que_se_conhece(dono._chave([ENDERECO]))) == esperada
    monkeypatch.setattr(dono, "_pelos_conhecidos", janela_a_janela)
    assert dono.mascarar(linha, conhecidos=[ENDERECO]) != esperada


def test_mordida_o_espaco_na_forma_corrompe_o_despejo(monkeypatch: pytest.MonkeyPatch) -> None:
    com_espaco = dono._SEPARADA.pattern.replace(r"([:\-_.])", r"([:\-_. ])")
    assert com_espaco != dono._SEPARADA.pattern, "a forma mudou de desenho: refaça a mordida"
    monkeypatch.setattr(dono, "_SEPARADA", re.compile(com_espaco))
    linhas = _linhas_que_nao_sao_endereco()
    corrompidas = [nome for nome, linha in linhas.items() if dono.mascarar(linha) != linha]
    assert "o despejo do 0x31" in corrompidas and "a linha do btmon" in corrompidas


def test_mordida_sem_a_guarda_do_uuid_ele_se_corrompe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dono, "_UUID", _nunca())
    linha = _linhas_que_nao_sao_endereco()["o UUID"]
    assert dono.mascarar(linha) != linha


@pytest.mark.parametrize(
    ("guarda", "nome"),
    [
        ("_APPID_DA_STEAM", "o appid da Steam de seis algarismos"),
        ("_CARIMBO_DE_VERSAO", "o carimbo de versão do perfil"),
    ],
)
def test_mordida_sem_a_guarda_a_forma_do_no_corrompe_o_diario(
    monkeypatch: pytest.MonkeyPatch, guarda: str, nome: str
) -> None:
    linha = _linhas_que_nao_sao_endereco()[nome]
    assert dono.mascarar(linha) == linha
    monkeypatch.setattr(dono, guarda, _nunca())
    assert dono.mascarar(linha) != linha


def test_o_guardado_nao_esconde_o_endereco_ao_lado() -> None:
    linhas = _linhas_que_nao_sao_endereco()
    for nome in ("o appid da Steam de seis algarismos", "o carimbo de versão do perfil"):
        linha, esperada = _formas()["3 o sufixo do nó"]
        junto = f"{linhas[nome]} {linha} uniq={ENDERECO}"
        saida = dono.mascarar(junto)
        assert saida == f"{linhas[nome]} {esperada} uniq={':'.join(MASCARADO)}"


def test_mordida_a_peneira_inventa_endereco(monkeypatch: pytest.MonkeyPatch) -> None:
    def peneira(valor: str, _separadores: str) -> tuple[str, ...] | None:
        digitos = "".join(ch for ch in valor.lower() if ch in "0123456789abcdef")
        return tuple(digitos[i : i + 2] for i in range(0, 12, 2)) if len(digitos) == 12 else None

    monkeypatch.setattr(dono, "_octetos_de", peneira)
    assert dono.mascarar_endereco("x" + "".join(OCTETOS)) is not None


# --- régua 3: um dono -----------------------------------------------------------------------
#
# Os seis mascaradores do produto e o `_id_visivel` da aba Perfis chamam o dono. Cada um
# guarda a grafia que devolvia; nenhum devolve o cru.

_OS_QUE_CHAMAM_O_DONO = {
    "battery_journal.mascarar_endereco": (
        "src/hefesto_dualsense4unix/daemon/battery_journal.py", "mascarar_endereco"),
    "gesto_de_reconexao.mascarar": (
        "src/hefesto_dualsense4unix/integrations/gesto_de_reconexao.py", "mascarar"),
    "sinal_da_barra.mascarar": (
        "src/hefesto_dualsense4unix/integrations/sinal_da_barra.py", "mascarar"),
    "o_cabo_em_espera.mascarar": (
        "src/hefesto_dualsense4unix/integrations/o_cabo_em_espera.py", "mascarar"),
    "ar_do_adaptador._mascarar": (
        "src/hefesto_dualsense4unix/integrations/ar_do_adaptador.py", "_mascarar"),
    "a09_sistema.mascarar_o_diario": (
        "src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py", "mascarar_o_diario"),
    "perfis_web._id_visivel": (
        "src/hefesto_dualsense4unix/app/actions/perfis_web.py", "_id_visivel"),
}

_MODULO_DO_DONO = "hefesto_dualsense4unix.core.formas_do_endereco"
_API_DO_DONO = {"mascarar", "mascarar_endereco"}


def _o_corpo_chama_o_dono(fonte: str, nome: str) -> tuple[bool, list[str]]:
    """(o corpo de ``nome`` chama o dono?, as contas próprias que ele ainda tem).

    Conta própria é o que a máscara de antes fazia à mão: ``re``, ``split``, a
    fatia de octeto e a peneira dos dígitos hex.
    """
    arvore = ast.parse(fonte)
    apelidos: set[str] = set()
    nomes: set[str] = set()
    for no in arvore.body:
        if isinstance(no, ast.ImportFrom) and no.module == "hefesto_dualsense4unix.core":
            apelidos |= {a.asname or a.name for a in no.names if a.name == "formas_do_endereco"}
        elif isinstance(no, ast.ImportFrom) and no.module == _MODULO_DO_DONO:
            nomes |= {a.asname or a.name for a in no.names if a.name in _API_DO_DONO}
    funcao = next(
        no for no in ast.walk(arvore)
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef) and no.name == nome
    )
    chama = False
    contas: list[str] = []
    for no in ast.walk(funcao):
        if isinstance(no, ast.Call):
            alvo = no.func
            if (
                isinstance(alvo, ast.Attribute)
                and isinstance(alvo.value, ast.Name)
                and alvo.value.id in apelidos
                and alvo.attr in _API_DO_DONO
            ) or (isinstance(alvo, ast.Name) and alvo.id in nomes):
                chama = True
            if isinstance(alvo, ast.Attribute) and alvo.attr == "split":
                contas.append("split")
        elif isinstance(no, ast.Name) and no.id == "re":
            contas.append("re")
        elif isinstance(no, ast.Subscript) and isinstance(no.slice, ast.Slice):
            contas.append("fatia")
        elif isinstance(no, ast.Constant) and no.value == "0123456789abcdef":
            contas.append("peneira")
    return chama, contas


@pytest.mark.parametrize("nome", sorted(_OS_QUE_CHAMAM_O_DONO))
def test_o_corpo_de_cada_um_chama_o_dono_e_nao_tem_conta_propria(nome: str) -> None:
    caminho, funcao = _OS_QUE_CHAMAM_O_DONO[nome]
    chama, contas = _o_corpo_chama_o_dono((RAIZ / caminho).read_text(encoding="utf-8"), funcao)
    assert chama, f"{nome} não chama o dono"
    assert contas == [], f"{nome} ainda faz conta própria: {contas}"


def _grafias() -> dict[str, str]:
    return {
        "dois-pontos": ENDERECO,
        "hífen": "-".join(OCTETOS),
        "sublinhado": "_".join(OCTETOS),
        "colada": "".join(OCTETOS),
        "maiúsculas": ENDERECO.upper(),
    }


def _valores_que_nao_sao_um_endereco() -> dict[str, str]:
    """Textos com um endereço dentro, numa forma que o dono reconhece."""
    return {
        "o caminho do BlueZ": f"/org/bluez/hci0/dev_{'_'.join(OCTETOS).upper()}",
        "a linha do diário": f"uniq={ENDERECO} rota=2",
        "o nó de som": f"hefesto_som_{SUFIXO}",
        "o endereço com a barra": f"{ENDERECO}/sep1",
    }


def _importar(caminho: str, funcao: str) -> Callable[[Any], Any]:
    import importlib

    modulo = caminho.removeprefix("src/").removesuffix(".py").replace("/", ".")
    return cast(Callable[[Any], Any], getattr(importlib.import_module(modulo), funcao))


def _sem_o_diario() -> list[str]:
    """Os que se importam sem o GTK; o do diário da 09 tem a régua dele abaixo."""
    return sorted(n for n in _OS_QUE_CHAMAM_O_DONO if not n.startswith("a09_sistema"))


#: A grafia que cada um devolvia, e que guarda: o que sai de um endereço de entrada.
_A_GRAFIA_DE_CADA_UM: dict[str, Callable[[str], str]] = {
    "battery_journal.mascarar_endereco": lambda _grafia: ":".join(MASCARADO),
    "gesto_de_reconexao.mascarar": lambda _grafia: ":".join(MASCARADO),
    "sinal_da_barra.mascarar": lambda grafia: dono.mascarar(grafia),
    "o_cabo_em_espera.mascarar": lambda _grafia: "".join(MASCARADO),
    "ar_do_adaptador._mascarar": lambda grafia: dono.mascarar(grafia),
    "perfis_web._id_visivel": lambda _grafia: ":".join(MASCARADO).upper(),
}


def _doze_do_cru(saida: object) -> bool:
    """A saída carrega os doze hex do endereço cru, em qualquer separador?"""
    return "".join(OCTETOS) in re.sub(r"[:\-_. ]", "", str(saida).lower())


@pytest.mark.parametrize("grafia", sorted(_grafias()))
@pytest.mark.parametrize("nome", _sem_o_diario())
def test_cada_um_mascara_o_endereco_em_toda_grafia(nome: str, grafia: str) -> None:
    mascarar = _importar(*_OS_QUE_CHAMAM_O_DONO[nome])
    valor = _grafias()[grafia]
    saida = mascarar(valor)
    assert saida == _A_GRAFIA_DE_CADA_UM[nome](valor), (nome, grafia)
    assert _janelas_que_sobram(str(saida)) == []


@pytest.mark.parametrize("valor", sorted(_valores_que_nao_sao_um_endereco()))
@pytest.mark.parametrize("nome", _sem_o_diario())
def test_o_que_nao_e_um_endereco_nunca_volta_cru(nome: str, valor: str) -> None:
    mascarar = _importar(*_OS_QUE_CHAMAM_O_DONO[nome])
    saida = mascarar(_valores_que_nao_sao_um_endereco()[valor])
    assert saida is not None, nome
    assert not _doze_do_cru(saida), (nome, valor)
    assert _janelas_que_sobram(str(saida)) == []


@pytest.mark.parametrize("nome", _sem_o_diario())
def test_cada_um_tira_o_hash_do_virtual(nome: str) -> None:
    mascarar = _importar(*_OS_QUE_CHAMAM_O_DONO[nome])
    for virtual in _virtuais():
        assert _hash_que_sobra(str(mascarar(virtual)), virtual) == [], nome


#: O corpo do `sinal_da_barra.mascarar` até 28/09/2026: só dois-pontos, e o resto cru.
_O_CORPO_DE_ANTES = textwrap.dedent('''
    def mascarar(mac: str) -> str:
        partes = mac.split(":")
        if len(partes) != 6:
            return mac
        partes[3] = partes[4] = "00"
        return ":".join(partes)
''')


def test_mordida_o_corpo_de_antes_do_sinal_da_barra_reprova() -> None:
    chama, contas = _o_corpo_chama_o_dono(_O_CORPO_DE_ANTES, "mascarar")
    assert not chama and "split" in contas
    espaco: dict[str, Any] = {}
    exec(compile(_O_CORPO_DE_ANTES, "<o corpo de antes>", "exec"), espaco)
    assert _doze_do_cru(espaco["mascarar"](_grafias()["colada"]))
    assert _janelas_que_sobram(espaco["mascarar"](_grafias()["hífen"])) != []


# --- régua 4: o diário nasce mascarado ------------------------------------------------------


class _TerminalDeMentira(io.StringIO):
    """Um buffer que se diz terminal: o `ConsoleRenderer` põe as cores."""

    def isatty(self) -> bool:
        return True


def _a_linha_de_prova(log: Any) -> None:
    virtual = _virtuais()[0]
    log.info(
        "haptica_endpoint_criado",
        uniq=ENDERECO,
        sink=f"alsa_output.usb-Sony_DualSense_Wireless_Controller_HEFESTO{SUFIXO}-00.HiFi",
        rotulo=f"hefesto-ponte-{SUFIXO}-sink",
        mac=virtual,
        chave="".join(OCTETOS),
        nos=[f"hefesto_som_{SUFIXO}", {"mic": f"hefesto_mic_{SUFIXO}"}],
    )


def _o_logger_do_produto(
    fmt: str, buf: io.StringIO, processadores: list[Any] | None = None
) -> Any:
    """Um logger embrulhado num buffer, com a cadeia do produto. Nada do global muda."""
    from hefesto_dualsense4unix.utils import logging_config

    return structlog.wrap_logger(
        structlog.PrintLogger(file=buf),
        processors=processadores or logging_config.cadeia_do_diario(fmt, buf),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
    )


def _o_que_sobra_no_diario(saida: str) -> list[str]:
    sobra = _janelas_que_sobram(saida)
    for virtual in _virtuais()[:1]:
        sobra += [f"hash {i}" for i in _hash_que_sobra(saida, virtual)]
    return sobra


@pytest.mark.parametrize("fmt", ["console", "console colorido", "json"])
def test_a_linha_do_structlog_sai_sem_janela(fmt: str) -> None:
    buf: io.StringIO = _TerminalDeMentira() if fmt == "console colorido" else io.StringIO()
    _a_linha_de_prova(_o_logger_do_produto(fmt.split()[0], buf))
    saida = buf.getvalue()
    assert "haptica_endpoint_criado" in saida
    if fmt == "console colorido":
        assert "\x1b[" in saida, "a prova das cores precisa das cores"
    assert _o_que_sobra_no_diario(saida) == [], fmt
    assert "HEFESTO" + SUFIXO_MASCARADO in saida


def _o_logger_de_biblioteca(buf: io.StringIO, com_o_filtro: bool = True) -> logging.Logger:
    from hefesto_dualsense4unix.utils import logging_config

    logger = logging.Logger("biblioteca-de-mentira")
    manipulador = logging.StreamHandler(buf)
    if com_o_filtro:
        manipulador.addFilter(logging_config.MascaraDoDiario())
    logger.addHandler(manipulador)
    return logger


def _a_linha_de_biblioteca(logger: logging.Logger) -> None:
    caminho = f"/org/bluez/hci0/dev_{'_'.join(OCTETOS).upper()}"
    logger.warning("aparelho %s caiu em %s", ENDERECO, caminho)
    try:
        raise RuntimeError(f"org.bluez.Error.Failed em {caminho} ({''.join(OCTETOS)})")
    except RuntimeError:
        logger.exception("o rádio levantou sobre %s", ENDERECO.upper())


def test_a_linha_do_logging_sai_sem_janela_pelo_filtro() -> None:
    buf = io.StringIO()
    _a_linha_de_biblioteca(_o_logger_de_biblioteca(buf))
    saida = buf.getvalue()
    assert "Traceback" in saida and "caiu em" in saida
    assert _janelas_que_sobram(saida) == []


def test_o_configure_logging_do_produto_fia_a_cadeia_e_o_filtro() -> None:
    """Num processo limpo: o `configure_logging` de verdade, nos dois caminhos."""
    codigo = textwrap.dedent(f'''
        import logging, sys
        from hefesto_dualsense4unix.utils import logging_config
        logging_config.configure_logging(stream=sys.stdout, fmt=sys.argv[1])
        log = logging_config.get_logger("prova")
        log.info("prova", uniq={ENDERECO!r}, sink="HEFESTO" + {SUFIXO!r})
        logging.getLogger("biblioteca").warning("caiu %s", {"_".join(OCTETOS)!r})
    ''')
    for fmt in ("console", "json"):
        saida = subprocess.run(
            [sys.executable, "-c", codigo, fmt], capture_output=True, text=True,
            timeout=60, env=os.environ.copy(), check=True,
        ).stdout
        assert "prova" in saida and "caiu" in saida, saida
        assert _janelas_que_sobram(saida) == [], fmt


def test_mordida_sem_o_dono_na_cadeia_a_linha_vaza() -> None:
    from hefesto_dualsense4unix.utils import logging_config

    buf = io.StringIO()
    sem_o_dono = logging_config.cadeia_do_diario("console", buf)[:-1]
    _a_linha_de_prova(_o_logger_do_produto("console", buf, sem_o_dono))
    assert _o_que_sobra_no_diario(buf.getvalue()) != []


def test_mordida_sem_o_filtro_a_linha_de_biblioteca_vaza() -> None:
    buf = io.StringIO()
    _a_linha_de_biblioteca(_o_logger_de_biblioteca(buf, com_o_filtro=False))
    assert _janelas_que_sobram(buf.getvalue()) != []


def test_um_defeito_no_dono_nao_derruba_o_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """O dono levanta: a linha sai com o nome do erro, sem o endereço, e ninguém cai."""

    def quebrado(texto: str, conhecidos: Any = ()) -> str:
        raise ValueError("defeito de mentira")

    monkeypatch.setattr(dono, "mascarar", quebrado)
    buf = io.StringIO()
    _a_linha_de_prova(_o_logger_do_produto("console", buf))
    _a_linha_de_biblioteca(_o_logger_de_biblioteca(buf))
    saida = buf.getvalue()
    assert saida.count("mascara_do_diario_falhou erro=ValueError") >= 3, saida
    assert _janelas_que_sobram(saida) == []
