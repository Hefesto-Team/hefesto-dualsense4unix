"""A assinatura de disco NÃO separa o jogo quebrado do que funciona.

Esta é a mordida do censo de 16/08/2026. Ela existe para que ninguém —
pessoa ou assistente — volte a ligar a máscara de gamepad ao que o disco diz,
porque o disco não sabe.

O caso que a prova: `Duskfade` (quebrado com máscara DualSense) e
`DON'T SCREAM` (funciona com máscara DualSense) têm a MESMA assinatura —
nenhum import de entrada, `XINPUT1_4.dll` carregado por `LoadLibrary`, zero
SDL. Os dois fixtures abaixo são exatamente esses dois binários, reduzidos ao
que importa. Se algum dia um veredito os separar, ele estará inventando.

Como arrancar a cura e ver morder: em `api_de_entrada.varrer_agulhas`, troque
`mapa.find(a) != -1` por `False`. O `test_xinput_dinamico_e_visto_mesmo_sem_import`
reprova com

    AssertionError: o XInput carregado por LoadLibrary sumiu:
    Duskfade-Win64-Shipping.exe teria passado por 'jogo sem entrada nenhuma'

e o `test_sdl_e_a_unica_evidencia_que_promove` reprova junto.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.api_de_entrada import (
    Familia,
    Veredito,
    escolher_executavel,
    examinar,
    examinar_pasta,
    ler_imports,
    parece_infraestrutura,
)

# ---------------------------------------------------------------------------
# O forjador de PE. Monta um PE32+ mínimo mas VÁLIDO: cabeçalho MZ, assinatura
# PE, um optional header de 64 bits, uma seção `.rdata` e, dentro dela, uma
# tabela de importação de verdade. É o que permite testar o parser sem tocar
# em nenhum byte da biblioteca real dela.
# ---------------------------------------------------------------------------

_BASE_SECAO = 0x1000
_OFFSET_CRU = 0x400


def _forjar_pe(
    dlls_importadas: list[str],
    *,
    strings_soltas: list[str] | None = None,
) -> bytes:
    """Um PE32+ com as DLLs dadas na tabela de importação.

    `strings_soltas` entra depois da tabela, fora dela: é como o binário do
    Duskfade guarda `XINPUT1_4.dll`, que ele carrega por `LoadLibrary` e
    portanto NÃO aparece em import nenhum.
    """
    n_descritores = len(dlls_importadas) + 1
    tam_tabela = n_descritores * 20
    corpo = bytearray(tam_tabela)
    nomes = bytearray()
    for i, dll in enumerate(dlls_importadas):
        rva_nome = _BASE_SECAO + tam_tabela + len(nomes)
        # O descritor tem 20 bytes; o RVA do nome mora no offset 12.
        struct.pack_into("<I", corpo, i * 20 + 12, rva_nome)
        nomes += dll.encode("latin-1") + b"\0"
    dados_secao = bytes(corpo) + bytes(nomes)
    for extra in strings_soltas or []:
        dados_secao += extra.encode("latin-1") + b"\0"

    optional = bytearray(240)
    struct.pack_into("<H", optional, 0, 0x20B)  # PE32+
    # Data directory 1 = import table; em PE32+ os diretórios começam em 112.
    struct.pack_into("<II", optional, 112 + 8, _BASE_SECAO, tam_tabela)

    secao = bytearray(40)
    secao[0:8] = b".rdata\0\0"
    struct.pack_into(
        "<IIII", secao, 8, len(dados_secao), _BASE_SECAO, len(dados_secao), _OFFSET_CRU
    )

    cabecalho_pe = b"PE\0\0" + struct.pack(
        "<HHIIIHH", 0x8664, 1, 0, 0, 0, len(optional), 0x22
    )

    saida = bytearray(_OFFSET_CRU)
    saida[0:2] = b"MZ"
    e_lfanew = 0x80
    struct.pack_into("<I", saida, 0x3C, e_lfanew)
    saida[e_lfanew : e_lfanew + len(cabecalho_pe)] = cabecalho_pe
    pos = e_lfanew + len(cabecalho_pe)
    saida[pos : pos + len(optional)] = optional
    pos += len(optional)
    saida[pos : pos + 40] = secao
    return bytes(saida) + dados_secao


@pytest.fixture
def duskfade(tmp_path: Path) -> Path:
    """O jogo QUEBRADO, como ele é no disco dela (medido 16/08/2026).

    Nenhuma DLL de entrada na tabela de importação; `XINPUT1_4.dll` presente
    só como string, porque o Unreal a carrega por `LoadLibrary`.
    """
    alvo = tmp_path / "Duskfade" / "Duskfade" / "Binaries" / "Win64"
    alvo.mkdir(parents=True)
    exe = alvo / "Duskfade-Win64-Shipping.exe"
    exe.write_bytes(
        _forjar_pe(
            ["WINMM.dll", "USER32.dll", "SETUPAPI.dll", "KERNEL32.dll"],
            strings_soltas=["XINPUT1_4.dll", "RegisterRawInputDevices"],
        )
    )
    return exe


@pytest.fixture
def dont_scream(tmp_path: Path) -> Path:
    """O jogo que FUNCIONA e tem a mesma assinatura do quebrado."""
    alvo = tmp_path / "DONT SCREAM" / "DontScream" / "Binaries" / "Win64"
    alvo.mkdir(parents=True)
    exe = alvo / "DontScream-Win64-Shipping.exe"
    exe.write_bytes(
        _forjar_pe(
            ["WINMM.dll", "USER32.dll", "KERNEL32.dll"],
            strings_soltas=["XINPUT1_4.dll", "RegisterRawInputDevices"],
        )
    )
    return exe


@pytest.fixture
def jogo_sdl(tmp_path: Path) -> Path:
    """Um jogo que fala SDL — o único caso que o disco promove com segurança."""
    alvo = tmp_path / "Grim Fandango"
    alvo.mkdir(parents=True)
    exe = alvo / "GrimFandango.exe"
    exe.write_bytes(_forjar_pe(["SDL2.dll", "KERNEL32.dll"]))
    return exe


# ---------------------------------------------------------------------------
# A MORDIDA
# ---------------------------------------------------------------------------


def test_xinput_dinamico_e_visto_mesmo_sem_import(duskfade: Path) -> None:
    """Ler só a tabela de importação cegaria o detector no caso real."""
    evidencia = examinar(duskfade)
    assert "xinput1_4.dll" not in evidencia.imports, (
        "o fixture tem de imitar o binário real: XInput NÃO está nos imports"
    )
    assert Familia.XINPUT in evidencia.familias, (
        "o XInput carregado por LoadLibrary sumiu: "
        f"{duskfade.name} teria passado por 'jogo sem entrada nenhuma'"
    )
    assert evidencia.carrega_xinput_dinamicamente is True


def test_o_quebrado_e_o_que_funciona_sao_indistinguiveis(
    duskfade: Path, dont_scream: Path
) -> None:
    """O CORAÇÃO DESTE ARQUIVO.

    Duskfade não funciona com a máscara DualSense; DON'T SCREAM funciona. Se o
    disco pudesse separá-los, a cura de detecção seria possível. Ele não pode —
    e enquanto este teste passar, ninguém deve tentar.
    """
    a = examinar(duskfade)
    b = examinar(dont_scream)
    assert a.familias == b.familias, (
        "as assinaturas divergiram: se isto virou verdade, o censo mudou e a "
        "decisão de 16/08 tem de ser reaberta"
    )
    assert a.veredito == b.veredito == Veredito.INDECISO


def test_nunca_existe_veredito_so_xinput() -> None:
    """`SO_XINPUT` não é alcançável — marcar Xbox custa cinco features."""
    assert not hasattr(Veredito, "SO_XINPUT")
    assert {v.value for v in Veredito} == {
        "entende_dualsense",
        "indeciso",
        "sem_evidencia",
    }


def test_sdl_e_a_unica_evidencia_que_promove(jogo_sdl: Path) -> None:
    """SDL mapeia o `054c:0df2` do vpad nativamente — este o disco garante."""
    evidencia = examinar(jogo_sdl)
    assert Familia.SDL in evidencia.familias
    assert evidencia.veredito is Veredito.ENTENDE_DUALSENSE


def test_o_crash_handler_do_unity_nao_e_o_jogo(tmp_path: Path) -> None:
    """Sem isto o censo lia o arquivo errado em sete jogos Unity."""
    raiz = tmp_path / "PEAK"
    (raiz / "PEAK_Data").mkdir(parents=True)
    handler = raiz / "UnityCrashHandler64.exe"
    handler.write_bytes(_forjar_pe(["KERNEL32.dll"]))
    jogo = raiz / "PEAK.exe"
    jogo.write_bytes(_forjar_pe(["KERNEL32.dll"], strings_soltas=["SDL2.dll"]))

    assert parece_infraestrutura("UnityCrashHandler64.exe") is True
    assert parece_infraestrutura("PEAK.exe") is False
    assert escolher_executavel(raiz) == jogo
    assert examinar_pasta(raiz).veredito is Veredito.ENTENDE_DUALSENSE


def test_pasta_sem_executavel_degrada_calada(tmp_path: Path) -> None:
    """Jogo nativo, ou download pela metade: nada de exceção."""
    raiz = tmp_path / "ELDEN RING"
    raiz.mkdir()
    evidencia = examinar_pasta(raiz)
    assert evidencia.executavel is None
    assert evidencia.veredito is Veredito.SEM_EVIDENCIA


def test_arquivo_que_nao_e_pe_devolve_vazio(tmp_path: Path) -> None:
    lixo = tmp_path / "leia-me.txt"
    lixo.write_text("isto não é um PE", encoding="utf-8")
    assert ler_imports(lixo) == ()
    assert examinar(lixo).veredito is Veredito.SEM_EVIDENCIA
