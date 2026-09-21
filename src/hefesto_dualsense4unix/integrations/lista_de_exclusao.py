"""A lista de exclusão do Hefesto — OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01.

**O QUE ELA É, em uma frase (a do §3 da sprint):** o jogo que está aqui vê o
controle como se o Hefesto não estivesse instalado.

O pedido é dela, 21/09/2026, olhando a aba Lançadores: *"(...) Adicionar jogo a
lista de exclusão do Hefesto (cujo objetivo é garantir que tal jogo não use
nenhuma feature do hefesto)"*. <!-- noqa-acento: citação literal dela -->

ESTA LISTA É UM GUARDA-CHUVA, e não um nono leitor
--------------------------------------------------
Três listas por feature já existiam, cada uma com dono, leitor e régua (medido
na E0, §10.1 da sprint):

- ``entrada`` — o jogo vê só o físico; dono:
  ``steam_launch_options.add_appid_to_steam_input_allowlist``;
- ``pino`` — o Proton pinado; dono: ``proton_pin.nomear_fora_do_pino``;
- ``atalho`` — o atalho de inicialização; dono:
  ``steam_launch_options.marcar_jogo_sem_wrapper``.

Excluir é ESCREVER nas três; tirar é sair delas. Nenhum leitor muda — cada um
continua lendo o mesmo arquivo de antes. A alternativa (cada feature aprender a
perguntar a esta lista) faria oito donos lerem um arquivo novo, e o primeiro que
esquecesse deixaria uma feature viva num jogo que ela excluiu.

TIRAR DEVOLVE SÓ O QUE ESTA LISTA ESCREVEU
------------------------------------------
Se o jogo já estava numa das três por escolha DELA antes de ser excluído, ele
continua lá depois do «Tirar». Quem diz de quem era a linha é o próprio dono:
``"adicionado"`` quer dizer que a escrita foi nossa; ``"ja_estava"`` quer dizer
que era dela. A entrada guarda só as listas em que NÓS escrevemos
(``escritas``), e o «Tirar» só sai delas. Sem isso, excluir e tirar apagaria uma
escolha anterior dela, calado — a exclusão viraria borracha.

A CHAVE É A IDENTIDADE DA JANELA
--------------------------------
``steam_app_<N>`` para a Steam e para todo jogo pelo umu, que é o que
``identidade_de_janela`` devolve e o endereço que o daemon vê em foco. As três
listas falam só dígitos, então só uma chave com ``N`` as alcança; o atalho e o
pino são features só da Steam, e um jogo sem ``N`` não tem o que tirar ali. Os
emuladores entram com a chave do PROCESSO — um processo para todas as ROMs, e a
exclusão vale para o emulador inteiro (§4.3 da sprint).

NUNCA LEVANTA: quem chama é um clique de botão. Um arquivo torto não é
sobrescrito — é recusado com ``"erro"``, porque sobrescrevê-lo apagaria a lista
dela inteira para gravar uma linha.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

#: O arquivo, ao lado das três listas, no ``XDG_CONFIG_HOME``.
RELPATH = "hefesto-dualsense4unix/lista_de_exclusao.json"
FORMATO = 1

#: As três listas por feature, na ordem em que se escreve.
LISTAS: tuple[str, ...] = ("entrada", "pino", "atalho")

#: A nota que acompanha a linha em cada lista — é o que ela lê se abrir o
#: arquivo, e o que diz que a linha não é dela.
NOTA_DAS_LISTAS = "posto pela lista de exclusão do Hefesto"

_STEAM_APP = re.compile(r"^steam_app_(\d+)$")


def caminho(config_home: Path | None = None) -> Path:
    """``$XDG_CONFIG_HOME/hefesto-dualsense4unix/lista_de_exclusao.json``."""
    if config_home is None:
        xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
        config_home = Path(xdg) if xdg else Path.home() / ".config"
    return config_home / RELPATH


def appid_da_chave(chave: str) -> str | None:
    """O ``N`` de ``steam_app_<N>``, ou ``None`` — e só então as três listas."""
    m = _STEAM_APP.match(chave.strip())
    return m.group(1) if m else None


@dataclass(frozen=True)
class Entrada:
    """UM jogo excluído."""

    chave: str
    lancador: str
    nome: str
    quando: str
    nota: str = ""
    #: As listas em que ESTA exclusão escreveu — e só delas o «Tirar» sai.
    escritas: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# As três listas — um adaptador por lista, os donos de verdade fazem a escrita
# ---------------------------------------------------------------------------
_POR: dict[str, Callable[[str], str]] = {
    "entrada": lambda a: slo.add_appid_to_steam_input_allowlist(a, nota=NOTA_DAS_LISTAS),
    "pino": lambda a: proton_pin.nomear_fora_do_pino(a, nota=NOTA_DAS_LISTAS),
    "atalho": lambda a: slo.marcar_jogo_sem_wrapper(a, nota=NOTA_DAS_LISTAS),
}
_TIRAR: dict[str, Callable[[str], str]] = {
    "entrada": lambda a: slo.remove_appid_from_steam_input_allowlist(a),
    "pino": proton_pin.devolver_ao_pino,
    "atalho": slo.desmarcar_jogo_sem_wrapper,
}


# ---------------------------------------------------------------------------
# O arquivo
# ---------------------------------------------------------------------------
class _ArquivoTortoError(Exception):
    """O JSON existe e não se lê — recusa, nunca sobrescreve."""


def _ler_cru(destino: Path) -> list[Entrada]:
    try:
        texto = destino.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    try:
        dado = json.loads(texto)
        jogos = dado["jogos"]
        return [
            Entrada(
                chave=str(j["chave"]),
                lancador=str(j.get("lancador", "")),
                nome=str(j.get("nome", "")),
                quando=str(j.get("quando", "")),
                nota=str(j.get("nota", "")),
                escritas=tuple(x for x in j.get("escritas", ()) if x in LISTAS),
            )
            for j in jogos
        ]
    except (ValueError, KeyError, TypeError) as exc:
        raise _ArquivoTortoError(str(exc)) from exc


def _gravar(destino: Path, entradas: list[Entrada]) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    corpo = json.dumps(
        {"formato": FORMATO, "jogos": [asdict(e) for e in entradas]},
        ensure_ascii=False, indent=2,
    ) + "\n"
    fd, provisorio = tempfile.mkstemp(dir=destino.parent, prefix=".lista_de_exclusao.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as saida:
            saida.write(corpo)
        os.replace(provisorio, destino)
    except BaseException:
        Path(provisorio).unlink(missing_ok=True)
        raise


def ler(config_home: Path | None = None) -> list[Entrada]:
    """Os jogos excluídos. Arquivo ausente ou torto = lista vazia. Nunca levanta."""
    try:
        return _ler_cru(caminho(config_home))
    except (_ArquivoTortoError, OSError):
        return []


def contem(chave: str, config_home: Path | None = None) -> bool:
    """Esta chave está excluída?"""
    alvo = chave.strip()
    return bool(alvo) and any(e.chave == alvo for e in ler(config_home))


# ---------------------------------------------------------------------------
# Os dois atos
# ---------------------------------------------------------------------------
def adicionar(
    chave: str,
    *,
    lancador: str,
    nome: str,
    nota: str = "",
    config_home: Path | None = None,
    escritas_herdadas: tuple[str, ...] = (),
) -> str:
    """Exclui o jogo. Status: ``"adicionado"`` | ``"ja_estava"`` |
    ``"chave_invalida"`` | ``"erro"``. Nunca levanta.

    `escritas_herdadas` é só para a migração (:func:`migrar_a_lista_velha`):
    uma lista em que o jogo já estava e que passa a ser DESTA exclusão.
    """
    alvo = chave.strip()
    if not alvo:
        return "chave_invalida"
    destino = caminho(config_home)
    try:
        atuais = _ler_cru(destino)
    except (_ArquivoTortoError, OSError):
        return "erro"
    if any(e.chave == alvo for e in atuais):
        return "ja_estava"

    escritas = list(escritas_herdadas)
    appid = appid_da_chave(alvo)
    if appid is not None:
        for lista in LISTAS:
            if lista in escritas:
                continue
            status = _POR[lista](appid)
            if status == "adicionado":
                escritas.append(lista)
            elif status != "ja_estava":
                # Uma escrita que falhou desfaz as que já foram feitas: um jogo
                # meio excluído é o estado que a D-2109-A-EXCLUSAO-E-TUDO-OU-NADA
                # existe para não ter.
                for feita in escritas:
                    if feita not in escritas_herdadas:
                        _TIRAR[feita](appid)
                return "erro"

    nova = Entrada(
        chave=alvo, lancador=lancador, nome=nome,
        quando=time.strftime("%Y-%m-%dT%H:%M:%S"), nota=nota,
        escritas=tuple(x for x in LISTAS if x in escritas),
    )
    try:
        _gravar(destino, [*atuais, nova])
    except OSError:
        if appid is not None:
            for feita in nova.escritas:
                if feita not in escritas_herdadas:
                    _TIRAR[feita](appid)
        return "erro"
    return "adicionado"


def tirar(chave: str, *, config_home: Path | None = None) -> str:
    """Devolve o jogo ao Hefesto. Status: ``"removido"`` | ``"nao_estava"`` |
    ``"erro"``. Nunca levanta.

    Sai SÓ das listas em que esta exclusão escreveu (``Entrada.escritas``): uma
    linha que já era dela antes da exclusão continua lá.
    """
    alvo = chave.strip()
    destino = caminho(config_home)
    try:
        atuais = _ler_cru(destino)
    except (_ArquivoTortoError, OSError):
        return "erro"
    achada = next((e for e in atuais if e.chave == alvo), None)
    if achada is None:
        return "nao_estava"
    appid = appid_da_chave(alvo)
    if appid is not None:
        for lista in achada.escritas:
            if _TIRAR[lista](appid) not in ("removido", "nao_estava"):
                return "erro"
    try:
        _gravar(destino, [e for e in atuais if e.chave != alvo])
    except OSError:
        return "erro"
    return "removido"


# ---------------------------------------------------------------------------
# A migração — D-2109-A-LISTA-VELHA-VIRA-EXCLUSAO
# ---------------------------------------------------------------------------
NOTA_DA_MIGRACAO = "veio do «Este jogo não funciona»"


def migrar_a_lista_velha(
    nomear: Callable[[str], str | None],
    *,
    config_home: Path | None = None,
) -> list[str]:
    """Cada jogo que ela marcou com «Este jogo não funciona» entra na lista nova.

    A intenção dela ao clicar era a mesma — *o Hefesto sai do caminho deste
    jogo* —, e a lista velha só tirava a entrada. A linha da lista velha passa a
    ser DESTA exclusão (`escritas_herdadas=("entrada",)`): tirar o jogo da
    exclusão o devolve inteiro, entrada incluída.

    Idempotente: quem já está na lista nova é pulado. Devolve as chaves
    migradas nesta chamada. Nunca levanta.
    """
    try:
        texto = slo.steam_input_allowlist_path().read_text(encoding="utf-8")
        velhos = [a for a in slo.parse_steam_input_allowlist(texto) if a.isdigit()]
    except (OSError, ValueError):
        return []
    migradas: list[str] = []
    for appid in velhos:
        chave = f"steam_app_{appid}"
        try:
            nome = nomear(appid) or f"o jogo {appid}"
        except Exception:
            nome = f"o jogo {appid}"
        status = adicionar(
            chave, lancador="steam", nome=nome, nota=NOTA_DA_MIGRACAO,
            config_home=config_home, escritas_herdadas=("entrada",),
        )
        if status == "adicionado":
            migradas.append(chave)
    return migradas


__all__ = [
    "LISTAS",
    "NOTA_DAS_LISTAS",
    "NOTA_DA_MIGRACAO",
    "Entrada",
    "adicionar",
    "appid_da_chave",
    "caminho",
    "contem",
    "ler",
    "migrar_a_lista_velha",
    "tirar",
]
