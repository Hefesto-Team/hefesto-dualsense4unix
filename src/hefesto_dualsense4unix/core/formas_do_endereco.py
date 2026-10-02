"""Toda identidade de aparelho na máscara da casa — um dono só.

O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01 (28/09/2026). A máscara da casa
zera os octetos 4 e 5 de um endereço e deixa o fabricante (1 a 3) e o último
octeto à mostra. Até aqui ela morava em seis cópias no produto, e as seis
divergiam: três devolviam o valor cru quando não o reconheciam, uma peneirava
os dígitos hex de qualquer texto, e a do diário conhecia três formas de
endereço — o «Copiar» da aba Sistema levava o endereço inteiro reconstruído de
uma linha mascarada, pelo nome do endpoint da háptica ao lado do ``uniq=``.

**AS DUAS CAMADAS**, nesta ordem:

1. **os conhecidos** — os endereços e os seriais que quem chama sabe que são
   de um aparelho (os ``uniq`` da mesa, as chaves do ``maquina.json``, o
   ``serial`` do ``state_full``). Todo pedaço de três octetos que carregue o
   octeto 4 ou o 5, nas duas ordens de byte, com ``:`` ``-`` ``_`` ``.``,
   espaço ou colado. É a única camada que pega o despejo invertido com
   espaço, que é a forma em que o ensaio de 15/08 publicou um endereço;
2. **a forma**, sempre, fora dos guardados (abaixo):

   1. a separada, com o MESMO separador (``:`` ``-`` ``_`` ``.``) nos cinco —
      o caminho ``dev_`` do BlueZ entra aqui;
   2. a colada, doze hex entre não alfanuméricos;
   3. ``_<6 hex>``, o sufixo dos nós ``hefesto_som_``, ``_mic_``, ``_haptica_``;
   4. ``HEFESTO<6 hex>``, o nome do endpoint da háptica;
   5. (a invertida com espaço é só da primeira camada);
   6. ``hefesto-<palavra>-<6 hex>``, o rótulo do gravador da ponte;

   mais **o virtual derivado** (o prefixo do vpad com o bit de derivação no
   terceiro octeto), que sai com os quatro bytes do hash zerados — com a
   máscara da casa ao lado, dois bytes do hash bastavam para voltar ao
   endereço —, e **o serial de fábrica**, com os seis primeiros à mostra.

**O ESPAÇO FICA FORA DA FORMA** (contraprova da O-ENDERECO-NUNCA-CHEGA-A-CONVERSA-01,
§2.1.2): seis bytes soltos por espaço são todo despejo de report e toda linha
do ``btmon``, e a forma genérica com espaço corrompia o carimbo, o PID, o UUID
e o despejo. Um endereço de verdade em bytes soltos é da camada dos conhecidos,
que sabe o valor. **Três formas que não são endereço ficam guardadas** antes da
forma: o UUID (o último grupo dele tem doze hex), o appid da Steam na classe da
janela (``steam_app_<N>``) e o carimbo de versão do perfil
(``profiles/loader._carimbo_de_versao``, ``<data>T<hora>_<microssegundos>``).
As duas últimas foram medidas no diário da sessão de 27/09: com seis
algarismos depois do ``_``, a forma 3 as lia como sufixo de nó, e o diário
passava a nomear um jogo errado e um arquivo do histórico que não existe.
**Um SHA de doze hex sai mascarado**, e é escolha medida: um SHA truncado se
relê, um endereço vazado não se apaga.

Este módulo importa só a biblioteca padrão no topo: o ``logging_config`` vai
chamá-lo em toda linha do diário, e o ``uhid_gamepad`` (que diz o prefixo e o
bit do virtual) importa o ``logging_config``. O import do virtual é dentro da
função, uma vez.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

CARACTERES_PUBLICOS_DO_SERIAL = 6

#: A forma do serial de fábrica do DualSense, MEDIDA nos aparelhos da bancada
PADRAO_DE_SERIAL = (
    r"(?<![A-Z0-9])"
    r"[A-Z][0-9]{2}[A-Z0-9][0-9]{2}"
    r"[A-Z0-9]{11}"
    r"(?![A-Z0-9])"
)

_ESCONDIDOS = (3, 4)

_SEPARADORES_DA_FORMA = ":-_."

_SEPARADORES_DOS_CONHECIDOS = (":", "-", "_", ".", " ", "")

_HEX2 = r"[0-9A-Fa-f]{2}"

_SEIS_SEPARADOS = re.compile(
    rf"({_HEX2})([:\-_. ])({_HEX2})\2({_HEX2})\2({_HEX2})\2({_HEX2})\2({_HEX2})"
)
_DOZE_COLADOS = re.compile(r"[0-9A-Fa-f]{12}")

_UUID = re.compile(
    r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}"
    r"-[0-9A-Fa-f]{12}(?![0-9A-Fa-f])"
)
_APPID_DA_STEAM = re.compile(r"steam_app_[0-9]+(?![0-9A-Za-z])")
_CARIMBO_DE_VERSAO = re.compile(r"(?<![0-9])[0-9]{8}T[0-9]{6}_[0-9]{6}(?![0-9A-Za-z])")

_SEPARADA = re.compile(
    rf"(?<![0-9A-Fa-f])({_HEX2})([:\-_.])({_HEX2})\2({_HEX2})\2({_HEX2})\2({_HEX2})\2({_HEX2})"
    r"(?![0-9A-Fa-f])"
)
_COLADA = re.compile(r"(?<![0-9A-Za-z])([0-9A-Fa-f]{12})(?![0-9A-Za-z])")
_SUFIXO_DO_NO = re.compile(r"(?<=_)[0-9A-Fa-f]{4}([0-9A-Fa-f]{2})(?![0-9A-Za-z])")
_NOME_DO_ENDPOINT = re.compile(r"((?i:HEFESTO))[0-9A-Fa-f]{4}([0-9A-Fa-f]{2})(?![0-9A-Fa-f])")
_ROTULO_DO_GRAVADOR = re.compile(
    r"((?i:hefesto)-(?:[A-Za-z]+-)+)[0-9A-Fa-f]{4}([0-9A-Fa-f]{2})(?![0-9A-Za-z])"
)
_SERIAL = re.compile(PADRAO_DE_SERIAL)

_CORRIDA_HEX = re.compile(r"[0-9A-Fa-f]{6,}")


@functools.cache
def _o_virtual() -> tuple[tuple[str, str], int]:
    """O prefixo do vpad e o bit que marca o MAC derivado, lidos do ``uhid_gamepad``."""
    from hefesto_dualsense4unix.integrations import uhid_gamepad

    primeiro, segundo = uhid_gamepad.VPAD_MAC_PREFIXO.lower().split(":")
    return (primeiro, segundo), uhid_gamepad._VPAD_MAC_BIT_DERIVADO


def _mascarado(octetos: Sequence[str]) -> tuple[str, ...]:
    """Os seis octetos na máscara da casa, com a grafia de cada um preservada."""
    prefixo, bit = _o_virtual()
    if (octetos[0].lower(), octetos[1].lower()) == prefixo and int(octetos[2], 16) & bit:
        return (octetos[0], octetos[1], f"{bit:02x}", "00", "00", "00")
    return (octetos[0], octetos[1], octetos[2], "00", "00", octetos[5])


def _octetos_de(valor: str, separadores: str) -> tuple[str, ...] | None:
    """Os seis octetos (minúsculos) de UM endereço, ou ``None``."""
    limpo = valor.strip()
    if _DOZE_COLADOS.fullmatch(limpo):
        return tuple(limpo[i : i + 2].lower() for i in range(0, 12, 2))
    achado = _SEIS_SEPARADOS.fullmatch(limpo)
    if achado is None or achado.group(2) not in separadores:
        return None
    return tuple(achado.group(i).lower() for i in (1, 3, 4, 5, 6, 7))


def _os_seis(octetos: Sequence[str]) -> tuple[str, ...] | None:
    if isinstance(octetos, str):
        return _octetos_de(octetos, ":-_. ")
    lista = list(octetos)
    if len(lista) != 6 or not all(
        isinstance(o, str) and re.fullmatch(_HEX2, o) for o in lista
    ):
        return None
    return tuple(o.lower() for o in lista)


def _janelas(octetos: Sequence[str]) -> Iterator[tuple[int, int, int]]:
    """As janelas de três octetos que carregam um escondido não nulo, nas duas ordens."""
    for inicio in (1, 2, 3):
        direta = (inicio, inicio + 1, inicio + 2)
        if any(octetos[i] != "00" for i in _ESCONDIDOS if i in direta):
            yield direta
            yield (inicio + 2, inicio + 1, inicio)


def formas_do_endereco(octetos: Sequence[str]) -> frozenset[str]:
    """Os pedaços de texto que entregam o 4.º ou o 5.º octeto de UM endereço."""
    seis = _os_seis(octetos)
    if seis is None:
        return frozenset()
    pedacos: set[str] = set()
    for janela in _janelas(seis):
        valores = [seis[i] for i in janela]
        for separador in _SEPARADORES_DOS_CONHECIDOS:
            pedaco = separador.join(valores)
            pedacos.add(pedaco)
            pedacos.add(pedaco.upper())
    return frozenset(pedacos)


def _serial_mascarado(serial: str) -> str:
    if len(serial) <= CARACTERES_PUBLICOS_DO_SERIAL:
        return serial
    return serial[:CARACTERES_PUBLICOS_DO_SERIAL] + "#" * (
        len(serial) - CARACTERES_PUBLICOS_DO_SERIAL
    )


def _serial_conhecido(valor: str) -> bool:
    """Um serial que quem chama declarou: alfanumérico, com algarismo, maior que a parte pública."""
    return (
        len(valor) > CARACTERES_PUBLICOS_DO_SERIAL
        and valor.isascii()
        and valor.isalnum()
        and any(ch.isdigit() for ch in valor)
    )


@dataclass(frozen=True)
class _Conhecidos:
    separadas: tuple[tuple[re.Pattern[str], tuple[int, ...]], ...]
    coladas: dict[str, tuple[int, ...]]
    seriais: re.Pattern[str] | None


def _chave(conhecidos: Iterable[str]) -> tuple[str, ...]:
    """Os conhecidos numa forma só, para o cache: ``e:<12 hex>`` e ``s:<serial>``."""
    chave: set[str] = set()
    for valor in conhecidos:
        if not isinstance(valor, str):
            continue
        octetos = _octetos_de(valor, ":-_. ")
        if octetos is not None:
            if any(octetos[i] != "00" for i in _ESCONDIDOS):
                chave.add("e:" + "".join(octetos))
        elif _serial_conhecido(valor.strip()):
            chave.add("s:" + valor.strip())
    return tuple(sorted(chave))


@functools.lru_cache(maxsize=64)
def _o_que_se_conhece(chave: tuple[str, ...]) -> _Conhecidos:
    separadas: list[tuple[re.Pattern[str], tuple[int, ...]]] = []
    coladas: dict[str, tuple[int, ...]] = {}
    seriais: list[str] = []
    for item in chave:
        tipo, valor = item[:2], item[2:]
        if tipo == "s:":
            seriais.append(valor)
            continue
        octetos = tuple(valor[i : i + 2] for i in range(0, 12, 2))
        for janela in _janelas(octetos):
            a, b, c = (octetos[i] for i in janela)
            zerar = tuple(k for k, i in enumerate(janela) if i in _ESCONDIDOS)
            separadas.append((
                re.compile(
                    rf"(?i)(?<![0-9a-f]){a}(?P<s>[:\-_. ]){b}(?P=s){c}(?![0-9a-f])"
                ),
                zerar,
            ))
            coladas[a + b + c] = tuple(sorted(set(coladas.get(a + b + c, ())) | set(zerar)))
    padrao_dos_seriais = None
    if seriais:
        alternativas = "|".join(re.escape(s) for s in sorted(seriais, key=len, reverse=True))
        padrao_dos_seriais = re.compile(
            rf"(?i)(?<![A-Za-z0-9])(?:{alternativas})(?![A-Za-z0-9])"
        )
    return _Conhecidos(tuple(separadas), coladas, padrao_dos_seriais)


def _pelos_conhecidos(texto: str, dono: _Conhecidos) -> str:
    """A primeira camada: as janelas dos conhecidos zeradas, e os seriais deles."""
    zerar: set[int] = set()
    for padrao, octetos in dono.separadas:
        for achado in padrao.finditer(texto):
            zerar.update(achado.start() + 3 * k for k in octetos)
    if dono.coladas:
        for corrida in _CORRIDA_HEX.finditer(texto):
            hexa = corrida.group(0).lower()
            inicios = (0, 1) if len(hexa) % 2 else (0,)
            for paridade in inicios:
                for i in range(paridade, len(hexa) - 5, 2):
                    da_janela = dono.coladas.get(hexa[i : i + 6])
                    if da_janela:
                        zerar.update(corrida.start() + i + 2 * k for k in da_janela)
    if zerar:
        letras = list(texto)
        for i in zerar:
            letras[i] = letras[i + 1] = "0"
        texto = "".join(letras)
    if dono.seriais is not None:
        texto = dono.seriais.sub(lambda m: _serial_mascarado(m.group(0)), texto)
    return texto


def _separada(achado: re.Match[str]) -> str:
    octetos = [achado.group(i) for i in (1, 3, 4, 5, 6, 7)]
    return achado.group(2).join(_mascarado(octetos))


def _colada(achado: re.Match[str]) -> str:
    doze = achado.group(1)
    return "".join(_mascarado([doze[i : i + 2] for i in range(0, 12, 2)]))


def _pela_forma(trecho: str) -> str:
    """A segunda camada, num trecho sem guardado."""
    trecho = _SEPARADA.sub(_separada, trecho)
    trecho = _COLADA.sub(_colada, trecho)
    trecho = _SUFIXO_DO_NO.sub(r"0000\1", trecho)
    trecho = _NOME_DO_ENDPOINT.sub(r"\g<1>0000\g<2>", trecho)
    trecho = _ROTULO_DO_GRAVADOR.sub(r"\g<1>0000\g<2>", trecho)
    return _SERIAL.sub(lambda m: _serial_mascarado(m.group(0)), trecho)


def _guardados(texto: str) -> list[tuple[int, int]]:
    """Os trechos que a forma não toca, em ordem e sem sobreposição."""
    trechos = sorted(
        achado.span()
        for padrao in (_UUID, _APPID_DA_STEAM, _CARIMBO_DE_VERSAO)
        for achado in padrao.finditer(texto)
    )
    unidos: list[tuple[int, int]] = []
    for inicio, fim in trechos:
        if unidos and inicio < unidos[-1][1]:
            unidos[-1] = (unidos[-1][0], max(fim, unidos[-1][1]))
        else:
            unidos.append((inicio, fim))
    return unidos


def mascarar(texto: str, conhecidos: Iterable[str] = ()) -> str:
    """O texto com toda identidade de aparelho na máscara da casa."""
    if isinstance(conhecidos, str):
        conhecidos = (conhecidos,)
    chave = _chave(conhecidos)
    if chave:
        texto = _pelos_conhecidos(texto, _o_que_se_conhece(chave))
    partes: list[str] = []
    fim = 0
    for inicio, final in _guardados(texto):
        partes.append(_pela_forma(texto[fim:inicio]))
        partes.append(texto[inicio:final])
        fim = final
    partes.append(_pela_forma(texto[fim:]))
    return "".join(partes)


def mascarar_endereco(valor: str | None) -> str | None:
    """Um endereço só -> 'aa:bb:cc:00:00:ff'; None se o valor não é um endereço."""
    if not isinstance(valor, str):
        return None
    octetos = _octetos_de(valor, _SEPARADORES_DA_FORMA)
    if octetos is None:
        return None
    return ":".join(_mascarado(octetos))


__all__ = [
    "CARACTERES_PUBLICOS_DO_SERIAL",
    "PADRAO_DE_SERIAL",
    "formas_do_endereco",
    "mascarar",
    "mascarar_endereco",
]
