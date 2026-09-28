"""O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01 — a régua do dono das formas do endereço.

O dono é ``core/formas_do_endereco.py``. Esta régua mede o que ELE faz: as
seis formas, as duas ordens de byte, os separadores, o virtual derivado, o
serial, e o que não pode ser corrompido (o carimbo, o PID, o UUID, o despejo).
Os seis mascaradores do produto, o diário, o «Copiar» e as três réguas de
forma chamam o dono na onda 2, e as partes deles entram aqui com eles.

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
import itertools
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

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
