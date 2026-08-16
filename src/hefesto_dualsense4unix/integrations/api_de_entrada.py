"""O que um jogo INSTALADO sabe ler de controle, lido no disco, antes de rodar.

A PERGUNTA QUE ESTE MÓDULO RESPONDE — E A QUE ELE SE RECUSA A RESPONDER
------------------------------------------------------------------------
Ele responde: *que APIs de entrada existem dentro do executável deste jogo?*
(SDL, XInput, DirectInput, RawInput, o plugin DualShock da Sony.)

Ele **se recusa** a responder: *este jogo entende a máscara DualSense?* — e a
recusa é medida, não covardia. Ver o parágrafo seguinte, que é a razão de este
arquivo existir com esta forma e não com outra.

O CENSO DE 16/08/2026 DERRUBOU A HEURÍSTICA QUE ESTE MÓDULO IA TER
-------------------------------------------------------------------
O desenho pedido era: *detectar o jogo que só fala XInput e trocar a máscara
para Xbox sozinho*. O censo dos 24 jogos instalados dela (instrumento
`scripts/ensaios/api_de_entrada_dos_jogos.py`) mostrou que **a assinatura de
disco não separa**:

Dos 24 jogos, **14 caem no mesmo balde** — a assinatura "XInput e mais nada":

| jogo | imports do PE | agulhas | funciona hoje com máscara DualSense? |
|---|---|---|---|
| **Duskfade** | (nenhum de entrada) | `rawinput,xinput` | **NÃO** — é o defeito |
| **DON'T SCREAM** | (nenhum de entrada) | `rawinput,xinput` | **SIM** (perfil dela) |
| **Big Walk** | (nenhum de entrada) | `rawinput,xinput` | **SIM** (perfil dela) |
| **Sackboy** | `xinput1_4.dll` | `rawinput,xinput` | **SIM** (perfil dela) |
| **Stray** | `xinput1_3.dll` | `rawinput,xinput` | **SIM** |
| PEAK, MMJ, Mad King, Mr. Sleepy Man, Scarlet Deer Inn, オバケイドロ, REANIMAL,
  DON'T SCREAM TOGETHER | (nenhum de entrada) | `rawinput,xinput` | sem perfil |

Duskfade e DON'T SCREAM têm a **mesma** assinatura na forma que importa:
nenhum import de entrada, `XINPUT1_4.dll` carregado por `LoadLibrary`, zero
SDL na pasta. Um está quebrado, o outro funciona.

**O número que fecha a discussão: a heurística erraria em 13 dos 14.** Ela
marcaria como Xbox um balde onde o defeito é UM jogo, e cada um dos outros
treze perderia as cinco features que a máscara Xbox não tem onde pôr
(giroscópio, touchpad, lightbar, gatilhos adaptativos, bateria;
`docs/protocol/pilha-steam-input-xpad-sdl.md` §1.5). A regra desta casa é que
**hipótese tem de explicar o que JÁ funcionava**, e esta não explica.

E o custo de errar NÃO é simétrico, o que torna a conta pior: marcar Xbox um
jogo que entende DualSense tira cinco features de um jogo que funcionava;
marcar DualSense um jogo XInput-only deixa a pessoa sem controle. Errar para o
lado do DualSense preserva treze jogos e mantém um quebrado — que é o estado
de hoje. Errar para o lado do Xbox conserta um e degrada treze.

Por isso `SO_XINPUT` **não é alcançável a partir da evidência de PE**. O maior
grau que o disco sustenta, para a família Unreal, é `INDECISO`.

AS QUATRO FONTES QUE FORAM PESADAS, E POR QUE TRÊS PERDERAM
-------------------------------------------------------------
1. **Imports do PE + varredura de agulhas** (o que este módulo usa). Funciona
   ANTES da primeira execução, cobre 100% dos jogos com executável, e custa de
   0,02 s a 2,15 s por jogo (medido; o pior caso é um PE de 379 MB). É a única
   fonte que não exige que o jogo já tenha rodado.
2. **O log do Unreal** (`*/Saved/Logs/*.log`, que lista os plugins montados).
   Foi assim que se soube que o Duskfade só monta `XInputDevice`. PERDEU por
   cobertura: varrendo `steamapps/common` E os prefixos de `compatdata`, o log
   existe para **1 dos 24** jogos, e só depois da primeira execução. Nenhum
   jogo que FUNCIONA tem log — então nem como contraprova ele serve, porque não
   há com que comparar o `XInputDevice` do Duskfade. Um sinal que só aparece na
   segunda execução e cobre 4% da biblioteca não sustenta decisão de produto.
3. **`ControllerTypesUsed` do `localconfig.vdf`.** PERDEU por escopo: medido em
   16/08/2026, a chave é **uma só, global da conta** (`localconfig.vdf:1346`),
   listando todo tipo de controle que ela já usou na vida. Não é por jogo, e
   portanto não distingue jogo nenhum.
4. **Arquivos-marca na pasta** (`Engine/`, `*_Data/`, `SDL2.dll`). PERDEU
   sozinha: dá a ENGINE, não a API de entrada. Os cinco Unreal da tabela acima
   têm a mesma marca e comportamentos diferentes.

O QUE ESTE MÓDULO NÃO FAZ, DE PROPÓSITO
-----------------------------------------
Ele **não** troca a máscara de ninguém. Nada em `daemon/launch_env.py` nem em
`profiles/schema.py` consulta este arquivo. Ligar o veredito à máscara é
precisamente a mudança que o censo reprova, e ela não foi feita.
"""
from __future__ import annotations

import logging
import mmap
import struct
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger(__name__)

#: Teto de entradas da tabela de importação. Um PE legítimo tem dezenas; o teto
#: existe para que um arquivo corrompido (ou hostil) não vire laço infinito.
_TETO_IMPORTS = 1024

#: Quanto do cabeçalho se lê de uma vez. `e_lfanew` mora em 0x3C, e nenhum PE
#: real põe o cabeçalho PE além de alguns KB.
_TAM_CABECALHO = 0x400


class Familia(str, Enum):
    """As famílias de API de entrada que este módulo sabe reconhecer."""

    SDL = "sdl"
    XINPUT = "xinput"
    DINPUT = "dinput"
    RAWINPUT = "rawinput"
    DUALSHOCK = "dualshock"


#: As agulhas de cada família, em bytes, como aparecem dentro do PE.
#:
#: Por que varrer o arquivo inteiro e não só os imports: **medido em
#: 16/08/2026**, o `Duskfade-Win64-Shipping.exe` não importa XInput em lugar
#: nenhum da tabela de importação, e ainda assim carrega `XINPUT1_4.dll` por
#: `LoadLibrary` — a string está lá, o import não. Um detector que só lesse a
#: tabela de importação diria "este jogo não fala XInput" sobre um jogo cujo
#: ÚNICO caminho de gamepad é XInput. A varredura é o que fecha esse buraco.
AGULHAS: dict[Familia, tuple[bytes, ...]] = {
    Familia.SDL: (b"SDL2.dll", b"SDL3.dll", b"libSDL2-2.0.so", b"libSDL3.so"),
    Familia.XINPUT: (b"xinput1_", b"XINPUT1_", b"XInput1_", b"Xinput1_"),
    Familia.DINPUT: (b"dinput8.dll", b"DINPUT8.dll"),
    Familia.RAWINPUT: (b"RegisterRawInputDevices",),
    Familia.DUALSHOCK: (b"WinDualShock", b"DualShock"),
}


class Veredito(str, Enum):
    """O que o disco sustenta dizer sobre um jogo — e nada além disso."""

    #: Há SDL ou o plugin DualShock da Sony no binário. O SDL mapeia o
    #: `054c:0df2` do nosso vpad nativamente, então a máscara DualSense chega.
    ENTENDE_DUALSENSE = "entende_dualsense"
    #: Há XInput e NÃO há SDL nem DualShock. Parece "só XInput" — e é
    #: exatamente aqui que o censo mostrou que a aparência mente: Duskfade
    #: (quebrado) e DON'T SCREAM (funciona) caem os dois neste balde.
    INDECISO = "indeciso"
    #: Nenhuma agulha, ou nenhum executável legível.
    SEM_EVIDENCIA = "sem_evidencia"


@dataclass(frozen=True)
class Evidencia:
    """O que se achou no executável de UM jogo. Fatos, e depois o veredito."""

    executavel: Path | None
    #: Nomes de DLL na tabela de importação do PE, em minúsculas.
    imports: tuple[str, ...] = ()
    #: Famílias cujas agulhas apareceram na varredura do arquivo.
    familias: frozenset[Familia] = field(default_factory=frozenset)
    #: True quando a família apareceu na varredura mas NÃO na tabela de
    #: importação — isto é, o jogo carrega a DLL por `LoadLibrary`.
    carrega_xinput_dinamicamente: bool = False

    @property
    def veredito(self) -> Veredito:
        if not self.executavel or not self.familias:
            return Veredito.SEM_EVIDENCIA
        if Familia.SDL in self.familias or Familia.DUALSHOCK in self.familias:
            return Veredito.ENTENDE_DUALSENSE
        if Familia.XINPUT in self.familias:
            # NUNCA `SO_XINPUT`. Ver o cabeçalho: esta é a assinatura que
            # Duskfade e DON'T SCREAM compartilham, e os dois se comportam
            # diferente. O disco não sabe qual é qual.
            return Veredito.INDECISO
        return Veredito.SEM_EVIDENCIA


def _secoes_e_diretorio(
    fh: BinaryIO,
) -> tuple[list[tuple[int, int, int]], int] | None:
    """Devolve ([(vaddr, tamanho, raddr)], rva_da_tabela_de_imports) ou None."""
    cabecalho = fh.read(_TAM_CABECALHO)
    if cabecalho[:2] != b"MZ" or len(cabecalho) < 0x40:
        return None
    (e_lfanew,) = struct.unpack_from("<I", cabecalho, 0x3C)
    fh.seek(e_lfanew)
    assinatura = fh.read(0x18)
    if len(assinatura) < 0x18 or assinatura[:4] != b"PE\0\0":
        return None
    (n_secoes,) = struct.unpack_from("<H", assinatura, 6)
    (tam_opcional,) = struct.unpack_from("<H", assinatura, 20)
    opcional = fh.read(tam_opcional)
    if len(opcional) < 2:
        return None
    (magic,) = struct.unpack_from("<H", opcional, 0)
    # PE32 põe os data directories em 96; PE32+ (64 bits) em 112.
    base = 96 if magic == 0x10B else 112
    if len(opcional) < base + 16:
        return None
    (rva_imports,) = struct.unpack_from("<I", opcional, base + 8)
    secoes: list[tuple[int, int, int]] = []
    for _ in range(n_secoes):
        cru = fh.read(40)
        if len(cru) < 40:
            break
        tam_virtual, vaddr, tam_cru, raddr = struct.unpack_from("<IIII", cru, 8)
        secoes.append((vaddr, max(tam_virtual, tam_cru), raddr))
    return secoes, rva_imports


def ler_imports(executavel: Path) -> tuple[str, ...]:
    """Os nomes de DLL da tabela de importação de um PE, em minúsculas.

    Devolve tupla vazia para qualquer coisa que não seja um PE legível — um ELF
    nativo, um script, um arquivo truncado. Degradar calado aqui é requisito:
    a biblioteca dela tem lançadores de 400 KB e jogos nativos no meio.
    """
    try:
        with executavel.open("rb") as fh:
            achado = _secoes_e_diretorio(fh)
            if achado is None:
                return ()
            secoes, rva_imports = achado
            if not rva_imports or not secoes:
                return ()

            def para_offset(rva: int) -> int | None:
                for vaddr, tamanho, raddr in secoes:
                    if vaddr <= rva < vaddr + tamanho:
                        return raddr + (rva - vaddr)
                return None

            offset = para_offset(rva_imports)
            if offset is None:
                return ()
            nomes: list[str] = []
            for i in range(_TETO_IMPORTS):
                fh.seek(offset + i * 20)
                entrada = fh.read(20)
                # A tabela termina numa entrada toda zerada.
                if len(entrada) < 20 or entrada == b"\0" * 20:
                    break
                (rva_nome,) = struct.unpack_from("<I", entrada, 12)
                if not rva_nome:
                    break
                offset_nome = para_offset(rva_nome)
                if offset_nome is None:
                    continue
                fh.seek(offset_nome)
                cru = fh.read(128).split(b"\0", 1)[0]
                if cru:
                    nomes.append(cru.decode("latin-1").lower())
            return tuple(nomes)
    except (OSError, ValueError, struct.error):
        logger.debug("api_de_entrada_imports_ilegivel", exc_info=True)
        return ()


def varrer_agulhas(executavel: Path) -> frozenset[Familia]:
    """As famílias cujas agulhas aparecem em qualquer ponto do arquivo.

    Usa `mmap`, então o custo é de página tocada, não de arquivo copiado — foi
    o que manteve o pior caso medido (379 MB) em 2,15 s.
    """
    achadas: set[Familia] = set()
    try:
        if executavel.stat().st_size == 0:
            return frozenset()
        with (
            executavel.open("rb") as fh,
            mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mapa,
        ):
            for familia, agulhas in AGULHAS.items():
                if any(mapa.find(a) != -1 for a in agulhas):
                    achadas.add(familia)
    except (OSError, ValueError):
        logger.debug("api_de_entrada_varredura_falhou", exc_info=True)
        return frozenset()
    return frozenset(achadas)


def examinar(executavel: Path) -> Evidencia:
    """Toda a evidência de disco sobre UM executável."""
    imports = ler_imports(executavel)
    familias = varrer_agulhas(executavel)
    tem_import_xinput = any("xinput" in nome for nome in imports)
    return Evidencia(
        executavel=executavel,
        imports=imports,
        familias=familias,
        carrega_xinput_dinamicamente=(
            Familia.XINPUT in familias and not tem_import_xinput
        ),
    )


#: Nomes de executável que NUNCA são o jogo. Medido em 16/08/2026: sem esta
#: lista o censo elegia `UnityCrashHandler64.exe` em **sete** jogos Unity, e o
#: handler não tem entrada nenhuma dentro — o censo dizia "sem evidência" sobre
#: sete jogos por estar lendo o arquivo errado. A lista é de INFRAESTRUTURA de
#: engine, não de jogos: nada aqui é o nome de um título, e um jogo lançado
#: amanhã não precisa entrar nela.
_NAO_SAO_O_JOGO = (
    "unitycrashhandler",
    "unitycrashhandler64",
    "crashreportclient",
    "crashreporter",
    "unrealcefsubprocess",
    "epicwebhelper",
    "eoshelper",
    "vc_redist",
    "dxsetup",
    "dotnetfx",
    "steamerrorreporter",
)


def parece_infraestrutura(nome: str) -> bool:
    """True quando o executável é ferramenta de engine, não o jogo."""
    base = nome.lower().removesuffix(".exe")
    return any(marca in base for marca in _NAO_SAO_O_JOGO)


def escolher_executavel(raiz: Path) -> Path | None:
    """O executável que MELHOR representa o jogo dentro de uma pasta.

    A ordem é medida, não gosto (16/08/2026, nos 24 jogos instalados dela):

    1. `*-Win64-Shipping.exe` — o binário monolítico do Unreal. Quando existe,
       é sempre o jogo, e nunca é o lançador.
    2. o maior `.exe` que não seja infraestrutura — pega Unity, Godot e os
       feitos à mão. O critério de TAMANHO é o que separa o jogo do lançador
       de 400 KB que algumas publicadoras põem na raiz.

    A pasta que não tem `.exe` nenhum devolve None em silêncio: pode ser um
    jogo nativo Linux, ou uma pasta que a Steam ainda não terminou de baixar.
    """
    try:
        candidatos = [p for p in raiz.rglob("*.exe") if p.is_file()]
    except OSError:
        return None
    candidatos = [p for p in candidatos if not parece_infraestrutura(p.name)]
    if not candidatos:
        return None
    shipping = [p for p in candidatos if p.name.lower().endswith("-win64-shipping.exe")]
    alvos = shipping or candidatos

    def tamanho(p: Path) -> int:
        try:
            return p.stat().st_size
        except OSError:
            return 0

    return max(alvos, key=tamanho)


#: Os runtimes de engine que carregam a entrada NO LUGAR do executável.
#:
#: **Medido em 16/08/2026:** o `.exe` de um jogo Unity não tem agulha nenhuma
#: dentro — quem fala com o controle é o `UnityPlayer.dll` ao lado dele, e lá
#: estão `xinput1_3.dll`, `xinput1_4.dll` e `HID.DLL`. Sem esta lista o censo
#: dizia `sem_evidencia` sobre PEAK, Big Walk e Scarlet Deer Inn por estar
#: lendo o arquivo errado — e Big Walk **funciona** hoje com a máscara
#: DualSense, o que faz dele mais uma contraprova da heurística derrubada.
#:
#: Como `_NAO_SAO_O_JOGO`, isto é uma lista de INFRAESTRUTURA DE ENGINE, não de
#: jogos: são três nomes de runtime, e um título lançado amanhã sobre qualquer
#: uma dessas engines já nasce coberto sem ninguém editar nada.
_RUNTIMES_DE_ENGINE = ("UnityPlayer.dll", "GameAssembly.dll", "fmod.dll")


def _runtimes_ao_lado(raiz: Path) -> list[Path]:
    achados: list[Path] = []
    for nome in _RUNTIMES_DE_ENGINE:
        try:
            achados.extend(p for p in raiz.rglob(nome) if p.is_file())
        except OSError:
            continue
    return achados[:4]


def examinar_pasta(raiz: Path) -> Evidencia:
    """A evidência de disco de um jogo, a partir da pasta dele.

    Varre o executável do jogo E os runtimes de engine ao lado dele, e UNE as
    famílias achadas: numa engine como a Unity a entrada mora no runtime, não
    no `.exe`, e olhar só o executável responde "não achei nada" sobre um jogo
    que fala XInput e HID.
    """
    executavel = escolher_executavel(raiz)
    if executavel is None:
        return Evidencia(executavel=None)
    evidencia = examinar(executavel)
    familias = set(evidencia.familias)
    for runtime in _runtimes_ao_lado(raiz):
        familias |= varrer_agulhas(runtime)
    if familias == evidencia.familias:
        return evidencia
    tem_import_xinput = any("xinput" in nome for nome in evidencia.imports)
    return Evidencia(
        executavel=executavel,
        imports=evidencia.imports,
        familias=frozenset(familias),
        carrega_xinput_dinamicamente=(
            Familia.XINPUT in familias and not tem_import_xinput
        ),
    )


__all__ = [
    "AGULHAS",
    "Evidencia",
    "Familia",
    "Veredito",
    "escolher_executavel",
    "examinar",
    "examinar_pasta",
    "ler_imports",
    "parece_infraestrutura",
    "varrer_agulhas",
]
