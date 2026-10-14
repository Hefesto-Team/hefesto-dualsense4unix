#!/usr/bin/env python3
"""AS OPÇÕES DE INICIALIZAÇÃO QUE ELA DECLARA — uma tabela, um dono.

POR QUE ISTO EXISTE, e a medição é de 21/09/2026
------------------------------------------------
A Steam guarda **UMA** linha de ``LaunchOptions`` por jogo, e tudo que quiser
estar ali disputa a mesma linha. Na máquina do usuário havia DOIS donos:

* o Hefesto, que põe o atalho ``hefesto-launch`` (sem ele, no rádio o jogo
  tende a não enxergar controle nenhum);
* uma tabela declarativa dela, fora deste produto, que reescrevia a linha com
  as variáveis de vídeo do jogo — e apagava o atalho ao fazê-lo.

O resultado foi medido no diário de um dia inteiro: **de hora em hora** o
PRAGMATA perdia o atalho e o vigia o repunha, das 04:31 às 22:00. Quem abrisse
o jogo na janela errada jogava sem controle. *Duas ferramentas escrevendo a
mesma linha não é configuração; é sorteio.*

A DECISÃO É `D-2109-AS-OPCOES-POR-JOGO-TEM-UM-DONO-SO`, e a ordem, de
21/09/2026, é esta: *"PODE CORRIGIR E INTEGRAR ELE AO NOSSO APP.
DESATIVA O ORIGINAL ENTÃAO."*  <!-- noqa-acento: citação literal, a
digitação é a dela -->

O QUE ESTE MÓDULO FAZ
---------------------
Guarda a tabela — ``appid<TAB>opções`` — em
``~/.config/hefesto-dualsense4unix/opcoes_por_jogo.txt``, e a aplica
compondo UMA linha só: **o atalho do Hefesto na frente, as opções dela
atrás**. É o mesmo arranjo que o reparo do wrapper já produzia quando
preservava o que estava escrito; a diferença é que agora existe uma FONTE, e
o que a Steam apagar volta inteiro — não só o atalho.

    tabela:   3357650  VKD3D_CONFIG=no_upload_hvv %command%
    no disco: <atalho do hefesto-launch> VKD3D_CONFIG=no_upload_hvv %command%

O JOGO QUE O USUÁRIO TIROU DO ATALHO continua fora dele: o appid que está no
``jogos_sem_wrapper.txt`` recebe as opções dela SEM o atalho. O produto não
briga com a dona da máquina — é a mesma regra do
``apply_wrapper_vdf_text(excluir=…)``.

SÓ COM A STEAM FECHADA, pelo mesmo motivo de sempre: a Steam viva regrava o
``localconfig.vdf`` ao sair e engole a edição. Com jogo aberto nem se cogita.
Quem chama de hora em hora é o ``hefesto-steam-input-guard``, na mesma carona
do reparo do atalho — e ali "adiei" não é falha.

ONDE A LINHA MORA, E O QUE SE MEDIU EM 08/10/2026
-------------------------------------------------
A Steam lê a opção de um jogo em ``…/Software/Valve/Steam/apps/<appid>``, na
linha ``LaunchOptions`` que é FILHA DIRETA do bloco do jogo — e o bloco de
metade dos jogos tem blocos filhos (``cloud``, ``autocloud``…) ANTES dessa
linha. O escritor antigo fechava o jogo no primeiro ``}`` que via, que era o
do filho, e inseria a linha lá dentro: o relato dizia ``aplicado``, o vdf
ganhava uma linha que ninguém lê, e a Steam lançava o jogo com a opção velha
(o Sackboy, 06/10: ``apps/1599660/cloud/LaunchOptions`` com o MangoHud, e a
do jogo intacta). Não era a conta errada (a máquina tem uma só), nem a nuvem
regravando (a linha sobreviveu a todas as subidas da Steam do dia).

Agora o escritor acompanha a PROFUNDIDADE do bloco do jogo, e o ``aplicar``
só diz ``aplicado`` depois de reler o vdf e achar a opção onde a Steam a lê.
Se o arquivo não a guarda, o relato diz ``desfeito_pela_steam``, nunca verde.
E só a conta LOGADA (``config/loginusers.vdf``) recebe a linha: numa máquina
com duas contas, a outra não é da Steam que vai subir.

NÃO É UM SEGUNDO ESCRITOR DE VDF: quem escreve continua sendo este arquivo
(:func:`aplicar`), pelas mesmas funções puras de parse que o resto do módulo
irmão usa, com backup ``.bak.hefesto-opcoes-<ts>`` ao lado de cada vdf.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict

try:
    from .steam_launch_options import (
        WRAPPER_PREFIX,
        _vdf_unescape,
        discover_vdfs,
        e_a_arvore_canonica,
        garantir_blocos_no_texto,
        is_sandboxed_layout,
        ler_jogos_sem_wrapper,
        sem_wrapper_path,
        steam_game_running,
        steam_running,
    )
    from .vigia_do_jogo_novo import jogos_novos_a_receber
except ImportError:  # pragma: no cover - executado como script avulso pelo vigia
    from steam_launch_options import (  # type: ignore[no-redef]
        WRAPPER_PREFIX,
        _vdf_unescape,
        discover_vdfs,
        e_a_arvore_canonica,
        garantir_blocos_no_texto,
        is_sandboxed_layout,
        ler_jogos_sem_wrapper,
        sem_wrapper_path,
        steam_game_running,
        steam_running,
    )
    from vigia_do_jogo_novo import jogos_novos_a_receber  # type: ignore[no-redef]

#: Onde a tabela mora, no molde do `jogos_sem_wrapper.txt`.
TABELA_RELPATH = "hefesto-dualsense4unix/opcoes_por_jogo.txt"

CABECALHO = """\
# As opções de inicialização que você quer em cada jogo da Steam.
#
# Formato:  <appid><TAB><opções, terminando em %command%>
# Linhas começando com # são comentário.
#
# O Hefesto compõe UMA linha só no localconfig.vdf: o atalho dele na frente
# (que é o que faz o controle chegar no rádio) e as suas opções atrás. O jogo
# que estiver no `jogos_sem_wrapper.txt` recebe as suas opções SEM o atalho.
#
# Quem aplica é o vigia `hefesto-steam-input-guard`, com a Steam fechada.
# Pela linha de comando:  python3 -m hefesto_dualsense4unix.integrations.opcoes_por_jogo --listar
"""

APLICADO = "aplicado"
DESFEITO = "desfeito_pela_steam"
NADA = "nada_a_fazer"
ADIADO_JOGO = "adiado_jogo_aberto"
ADIADO_STEAM = "adiado_steam_aberta"
ERRO = "erro"
SEM_CONTA = "conta_logada_desconhecida"
LINHA_DELA_DIVERGE = "linha_dela_diverge"

#: O que ``conferir`` diz de cada jogo da tabela (só leitura).
OK = "ok"
NOVO = "novo"
DESFEITO_NA_ESCRITA = "desfeito_na_escrita"
DESFEITO_DEPOIS = "desfeito"
FORA_DO_LUGAR = "fora_do_lugar"

#: Os estados que o doctor e a sonda do contrato nomeiam; ``ok`` e ``novo`` não são defeito.
DEFEITOS = (DESFEITO_NA_ESCRITA, DESFEITO_DEPOIS, FORA_DO_LUGAR, SEM_CONTA)

#: O aviso de cada defeito, com o que fazer. Um dono só: o doctor e a sonda só o repetem.
AVISO_DO_DEFEITO = {
    DESFEITO_NA_ESCRITA: (
        "a Steam não guardou a opção que o Hefesto escreveu; ele tenta de novo quando a Steam "
        "fechar, e se repetir confira o localconfig.vdf"
    ),
    DESFEITO_DEPOIS: (
        "a opção que o Hefesto pôs foi reescrita (pela Steam ou à mão); o Hefesto repõe "
        "assim que a Steam fechar"
    ),
    FORA_DO_LUGAR: (
        "a opção está num bloco que a Steam não lê; o Hefesto alinha na próxima aplicação, "
        "com a Steam fechada"
    ),
    SEM_CONTA: (
        "o Hefesto não sabe qual conta a Steam abre (config/loginusers.vdf), e por isso não "
        "escreve as opções por jogo; abra a Steam uma vez com a sua conta"
    ),
}

#: O que o registro anota do ``aplicar`` depois da releitura.
REGISTRO_BASENAME = "opcoes-escritas.json"
ESCRITO_E_CONFERIDO = "aplicado"
ESCRITO_E_DESFEITO = "desfeito"

_APPID = re.compile(r"^[0-9]{1,10}$")

#: O contrato que o relato nomeia quando o vdf não guarda o que o dono escreveu.
CONTRATO_DA_LINHA = (
    "contrato:steam-localconfig — a Steam lê a opção de cada jogo na LaunchOptions "
    "filha direta de Software/Valve/Steam/apps/<appid>, no localconfig.vdf da conta logada"
)

#: SteamID64 = esta base + o número da pasta ``userdata/<conta>``.
_BASE_DO_STEAMID64 = 76561197960265728

_PAR_DO_VDF = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s+"((?:[^"\\]|\\.)*)"\s*$')
_CHAVE_DO_VDF = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*$')


def tabela_path(config_home: Path | None = None) -> Path:
    """Caminho da tabela (XDG), sem tocar no disco — gêmeo do `sem_wrapper_path`."""
    if config_home is not None:
        base = config_home
    else:
        env = os.environ.get("XDG_CONFIG_HOME")
        base = Path(env) if env else Path.home() / ".config"
    return base / TABELA_RELPATH


def parse(texto: str) -> dict[str, str]:
    """``{appid: opções}`` de um texto de tabela. Nunca levanta."""
    achadas: dict[str, str] = {}
    for linha in texto.splitlines():
        crua = linha.strip()
        if not crua or crua.startswith("#"):
            continue
        partes = crua.split("\t", 1) if "\t" in crua else crua.split(None, 1)
        if len(partes) != 2:
            continue
        appid, opcoes = partes[0].strip(), partes[1].strip()
        if not _APPID.match(appid) or not opcoes:
            continue
        achadas[appid] = opcoes
    return achadas


def ler(config_home: Path | None = None) -> dict[str, str]:
    """A tabela do disco. Arquivo ausente ou ilegível = tabela vazia."""
    try:
        return parse(tabela_path(config_home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def gravar(tabela: dict[str, str], config_home: Path | None = None) -> Path:
    """Escreve a tabela inteira, com o cabeçalho. Devolve o caminho."""
    destino = tabela_path(config_home)
    destino.parent.mkdir(parents=True, exist_ok=True)
    corpo = "".join(f"{a}\t{o}\n" for a, o in sorted(tabela.items(), key=lambda x: int(x[0])))
    destino.write_text(CABECALHO + corpo, encoding="utf-8")
    return destino


def definir(appid: int | str, opcoes: str, config_home: Path | None = None) -> str:
    """Põe (ou troca) as opções de UM jogo. Devolve o valor guardado."""
    chave = str(appid).strip()
    if not _APPID.match(chave):
        raise ValueError(f"appid inválido: {appid!r}")
    valor = opcoes.strip()
    if not valor:
        raise ValueError("opções vazias — para tirar o jogo da tabela, use `tirar`")
    tabela = ler(config_home)
    tabela[chave] = valor
    gravar(tabela, config_home)
    return valor


def tirar(
    appid: int | str,
    config_home: Path | None = None,
    estado_home: Path | None = None,
) -> bool:
    """Tira um jogo da tabela e do registro. ``False`` quando ele já não estava lá."""
    chave = str(appid).strip()
    tabela = ler(config_home)
    if chave not in tabela:
        return False
    del tabela[chave]
    gravar(tabela, config_home)
    registro = ler_registro(estado_home)
    if registro.pop(chave, None) is not None:
        gravar_registro(registro, estado_home)
    return True


def registro_path(estado_home: Path | None = None) -> Path:
    """``opcoes-escritas.json`` no state do produto (XDG), sem tocar no disco."""
    if estado_home is not None:
        base = estado_home
    else:
        env = os.environ.get("XDG_STATE_HOME", "").strip()
        base = Path(env) if env else Path.home() / ".local" / "state"
    return base / "hefesto-dualsense4unix" / REGISTRO_BASENAME


def ler_registro(estado_home: Path | None = None) -> dict[str, dict[str, str]]:
    """``{appid: {valor, conta, quando, resultado}}`` do que o ``aplicar`` anotou. Nunca levanta."""
    try:
        caminho = registro_path(estado_home)
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    jogos = dados.get("jogos") if isinstance(dados, dict) else None
    if not isinstance(jogos, dict):
        return {}
    return {
        str(a): {str(k): str(v) for k, v in e.items()}
        for a, e in jogos.items()
        if str(a).isdigit() and isinstance(e, dict)
    }


def gravar_registro(
    registro: dict[str, dict[str, str]], estado_home: Path | None = None
) -> bool:
    """Grava o registro inteiro, por arquivo temporário. Best-effort: ``False`` se falhar."""
    destino = registro_path(estado_home)
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + ".hefesto-tmp")
        tmp.write_text(
            json.dumps({"schema": 1, "jogos": registro}, ensure_ascii=False, indent=2,
                       sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(destino)
    except OSError:
        return False
    return True


def linha_desejada(opcoes: str, *, com_atalho: bool) -> str:
    """A linha final do vdf: o atalho na frente, as opções dela atrás."""
    limpo = opcoes.strip()
    return f"{WRAPPER_PREFIX} {limpo}" if com_atalho else limpo


def _valor_do_vdf(bruto: str) -> str:
    """O valor como o vdf o escreve, com as aspas escapadas."""
    return bruto.replace("\\", "\\\\").replace('"', '\\"')


def _e_chave(nu: str) -> bool:
    """A linha é só ``"chave"`` (o nome de um bloco que vem a seguir)?"""
    return nu.startswith('"') and nu.endswith('"') and nu.count('"') == 2


_TOKEN_DA_LINHA = re.compile(r"""(?:[^\s'"]|'[^']*'|"[^"]*")+""")
_COMANDO = "%command%"


def _tokens(linha: str) -> list[str]:
    """Os tokens da linha, com o que está entre aspas inteiro (``sh -c '…'`` é um só)."""
    return _TOKEN_DA_LINHA.findall(linha)


def _acha(tokens: list[str], trecho: list[str]) -> int | None:
    """A posição onde ``trecho`` aparece inteiro e contíguo em ``tokens``, ou ``None``."""
    if not trecho:
        return None
    for i in range(len(tokens) - len(trecho) + 1):
        if tokens[i: i + len(trecho)] == trecho:
            return i
    return None


def _parte_antes_e_depois(tokens: list[str]) -> tuple[list[str], list[str], bool] | None:
    """``(antes do %command%, depois dele, tinha)``; ``None`` com mais de um ``%command%``."""
    if tokens.count(_COMANDO) > 1:
        return None
    if _COMANDO not in tokens:
        return [], tokens, False
    i = tokens.index(_COMANDO)
    return tokens[:i], tokens[i + 1:], True


def _sem(tokens: list[str], tirar: list[str]) -> list[str]:
    """``tokens`` sem UMA ocorrência de cada item de ``tirar``."""
    resto = list(tokens)
    for t in tirar:
        if t in resto:
            resto.remove(t)
    return resto


#: O que separa um comando do outro na linha: o atalho entra no trecho que roda o jogo.
_OPERADORES = frozenset({"&&", "||", ";", "|", "&"})
_ATRIBUICAO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _inicio_do_trecho_do_jogo(tokens: list[str]) -> int:
    """Onde começa o comando que leva o ``%command%``: depois do último ``&&`` (ou ``;``)."""
    fim = tokens.index(_COMANDO) if _COMANDO in tokens else 0
    return max((i + 1 for i in range(fim) if tokens[i] in _OPERADORES), default=0)


def _atribuicoes_e_resto(tokens: list[str]) -> tuple[list[str], list[str]]:
    """As ``VAR=valor`` do começo e o resto (``gamemoderun``, ``mangohud``…), na ordem dada."""
    i = 0
    while i < len(tokens) and _ATRIBUICAO.match(tokens[i]):
        i += 1
    return tokens[:i], tokens[i:]


def _opcoes_da_linha(linha: str) -> tuple[list[str], list[str]] | None:
    """``(antes, depois)`` do ``%command%`` do que a TABELA escreveu, sem o atalho."""
    tokens = _tokens(linha)
    atalho = _tokens(WRAPPER_PREFIX)
    if tokens[: len(atalho)] == atalho:
        tokens = tokens[len(atalho):]
    partes = _parte_antes_e_depois(tokens)
    return None if partes is None else (partes[0], partes[1])


def compor_linha(vivo: str, desejada: str, anterior: str = "") -> str | None:
    """A linha viva do jogo com o NOSSO trecho trocado pela ``desejada`` e o resto dela intacto.

    O nosso trecho é o atalho do Hefesto e o que a tabela escreveu da última vez
    (``anterior``, do registro do ``aplicar``). Tudo o mais na linha é do usuário e
    sobrevive: o que vem antes do atalho, as variáveis que ele pôs ao lado das da
    tabela, os argumentos depois do ``%command%``. ``None`` quando a composição
    perderia um token dele: mais de um ``%command%`` na linha, na dele ou na da tabela.
    """
    if vivo == desejada:
        return desejada
    if not vivo.strip() or vivo.strip() == _COMANDO:
        return desejada
    vivos, quer = _tokens(vivo), _tokens(desejada)
    if anterior:
        antiga = _tokens(anterior)
        i = _acha(vivos, antiga)
        if i is not None:
            spans = [m.span() for m in _TOKEN_DA_LINHA.finditer(vivo)]
            return vivo[: spans[i][0]] + desejada + vivo[spans[i + len(antiga) - 1][1]:]
    atalho = _tokens(WRAPPER_PREFIX)
    com_atalho = quer[: len(atalho)] == atalho
    pos = _acha(vivos, atalho)
    if pos is None:
        pos = _inicio_do_trecho_do_jogo(vivos)
        antes_do_atalho, resto = vivos[:pos], vivos[pos:]
    else:
        antes_do_atalho, resto = vivos[:pos], vivos[pos + len(atalho):]
    dele = _parte_antes_e_depois(resto)
    nosso = _opcoes_da_linha(desejada)
    if dele is None or nosso is None:
        return None
    antigo = _opcoes_da_linha(anterior) if anterior else ([], [])
    if antigo is None:
        antigo = ([], [])
    pre_dele = _sem(dele[0], nosso[0] + antigo[0])
    pos_dele = _sem(dele[1], nosso[1] + antigo[1])
    tinha_comando = dele[2] or _COMANDO in quer
    novo = list(antes_do_atalho)
    if com_atalho:
        novo += atalho
    # As variáveis antes de qualquer comando: `gamemoderun A=1 %command%` rodaria `A=1`.
    var_dele, cmd_dele = _atribuicoes_e_resto(pre_dele)
    var_nossa, cmd_nosso = _atribuicoes_e_resto(nosso[0])
    novo += var_dele + var_nossa + cmd_dele + cmd_nosso
    if tinha_comando:
        novo.append(_COMANDO)
    novo += pos_dele + nosso[1]
    return " ".join(novo)


def definir_opcoes_vdf_text(
    texto: str,
    desejadas: dict[str, str],
    escritas: dict[str, str] | None = None,
) -> tuple[str, list[str], list[tuple[str, str]]]:
    """Põe ``desejadas`` (``{appid: linha}``) na árvore CANÔNICA, compondo com a linha viva.

    A ``LaunchOptions`` é a filha direta do bloco do jogo (um ``}`` de filho não o fecha);
    as cópias em blocos filhos recebem o mesmo valor. Só o nosso trecho troca
    (:func:`compor_linha`); linha que não se compõe vai a ``pulados`` com ``linha_dela_diverge``.
    """
    return compor_opcoes_vdf_text(texto, desejadas, escritas)[:3]


def compor_opcoes_vdf_text(
    texto: str,
    desejadas: dict[str, str],
    escritas: dict[str, str] | None = None,
    instalados: Sequence[str] = (),
) -> tuple[str, list[str], list[tuple[str, str]], dict[str, str]]:
    """O :func:`definir_opcoes_vdf_text` e, de quebra, o valor composto de cada jogo escrito.

    ``instalados``: o jogo da tabela com ``appmanifest`` e sem bloco ganha o bloco antes.
    """
    escritas = escritas or {}
    texto, _ = garantir_blocos_no_texto(texto, [a for a in desejadas if a in instalados])
    pilha: list[str] = []
    saida: list[str] = []
    aplicados: list[str] = []
    pulados: list[tuple[str, str]] = []
    compostos: dict[str, str] = {}
    vistos: set[str] = set()
    quadro: dict[str, Any] | None = None

    def fechar() -> None:
        assert quadro is not None
        appid = str(quadro["appid"])
        vistos.add(appid)
        linhas: list[tuple[int, bool, re.Match[str]]] = quadro["linhas"]
        diretas = [v for v in linhas if v[1]]
        referencia = (diretas or linhas)[0] if linhas else None
        vivo = _vdf_unescape(referencia[2].group(3)) if referencia else ""
        composto = compor_linha(vivo, desejadas[appid], escritas.get(appid, ""))
        if composto is None:
            pulados.append((appid, LINHA_DELA_DIVERGE))
            return
        querido = _valor_do_vdf(composto)
        mudou = False
        for idx, _, casou in linhas:
            if casou.group(3) != querido:
                saida[idx] = (
                    f'{casou.group(1)}"LaunchOptions"{casou.group(2)}"{querido}"{casou.group(4)}'
                )
                mudou = True
        if not diretas:
            saida.append(f'{quadro["recuo"]}"LaunchOptions"\t\t"{querido}"\n')
            mudou = True
        compostos[appid] = composto
        if mudou:
            aplicados.append(appid)
        else:
            pulados.append((appid, "ja_e_o_desejado"))

    for linha in texto.splitlines(keepends=True):
        nu = linha.strip()
        if _e_chave(nu):
            pilha.append(nu.strip('"'))
            saida.append(linha)
            continue
        if nu == "{":
            saida.append(linha)
            if (
                quadro is None
                and pilha
                and _APPID.match(pilha[-1])
                and e_a_arvore_canonica(pilha[:-1])
            ):
                base = linha[: len(linha) - len(linha.lstrip())]
                quadro = {
                    "appid": pilha[-1], "fundo": len(pilha), "recuo": base + "\t",
                    "linhas": [],
                }
            continue
        if nu == "}":
            if quadro is not None and len(pilha) == quadro["fundo"]:
                if str(quadro["appid"]) in desejadas:
                    fechar()
                quadro = None
            if pilha:
                pilha.pop()
            saida.append(linha)
            continue
        casou = re.match(r'^(\s*)"LaunchOptions"(\s*)"((?:[^"\\]|\\.)*)"(\s*)$', linha)
        if casou and quadro is not None and str(quadro["appid"]) in desejadas:
            quadro["linhas"].append((len(saida), len(pilha) == quadro["fundo"], casou))
        saida.append(linha)

    for appid in desejadas:
        if appid not in vistos:
            pulados.append((appid, "jogo_nao_esta_neste_vdf"))
    return "".join(saida), aplicados, pulados, compostos


def lugares_das_opcoes(texto: str, appid: str) -> tuple[bool, list[tuple[bool, str]]]:
    """``(jogo está na árvore canônica, [(é filha direta, valor)])``, na ordem do arquivo.

    A filha direta do jogo é a que a Steam lê; as de blocos filhos (``cloud``…) são
    as que a versão velha do escritor deixou. Leitor próprio e independente do
    escritor: quem confere não pode errar igual a quem escreveu.
    """
    pilha: list[str] = []
    achados: list[tuple[bool, str]] = []
    presente = False
    fundo: int | None = None
    for linha in texto.splitlines():
        nu = linha.strip()
        if _e_chave(nu):
            pilha.append(nu.strip('"'))
            continue
        if nu == "{":
            if (
                fundo is None
                and pilha
                and pilha[-1] == appid
                and e_a_arvore_canonica(pilha[:-1])
            ):
                fundo = len(pilha)
                presente = True
            continue
        if nu == "}":
            if fundo is not None and len(pilha) == fundo:
                fundo = None
            if pilha:
                pilha.pop()
            continue
        par = _PAR_DO_VDF.match(linha)
        if par and fundo is not None and par.group(1).lower() == "launchoptions":
            achados.append((len(pilha) == fundo, par.group(2)))
    return presente, achados


def opcoes_lidas_do_jogo(texto: str, appid: str) -> list[str]:
    """Todo valor de ``LaunchOptions`` que o bloco canônico do jogo guarda.

    Na ordem do arquivo: a filha direta do jogo (a que a Steam lê) e as de
    blocos filhos (``cloud``…) que a versão velha do escritor deixou.
    """
    return [valor for _, valor in lugares_das_opcoes(texto, appid)[1]]


def conta_logada(raiz: Path) -> str | None:
    """O número da pasta ``userdata/<conta>`` da conta que a Steam vai abrir.

    Lê ``<raiz>/config/loginusers.vdf``: a conta marcada ``MostRecent``, ou, sem
    marca, a de maior ``Timestamp``. ``None`` quando o arquivo não tem conta;
    arquivo ausente ou ilegível levanta ``OSError``, e quem chama decide o que
    fazer sem resposta (``so_a_conta_logada`` pula e diz o motivo no relato).
    """
    texto = (raiz / "config" / "loginusers.vdf").read_text(
        encoding="utf-8", errors="replace")
    pilha: list[str] = []
    contas: dict[str, dict[str, str]] = {}
    for linha in texto.splitlines():
        nu = linha.strip()
        if _e_chave(nu):
            pilha.append(nu.strip('"'))
            continue
        if nu == "{":
            continue
        if nu == "}":
            if pilha:
                pilha.pop()
            continue
        par = _PAR_DO_VDF.match(linha)
        if par and len(pilha) == 2 and pilha[0].lower() == "users":
            contas.setdefault(pilha[1], {})[par.group(1).lower()] = par.group(2)
    contas = {c: d for c, d in contas.items() if c.isdigit()}
    if not contas:
        return None
    marcadas = [c for c, d in contas.items() if d.get("mostrecent") == "1"]

    def _quando(conta: str) -> int:
        bruto = contas[conta].get("timestamp", "")
        return int(bruto) if bruto.isdigit() else 0

    escolhida = max(marcadas or list(contas), key=_quando)
    numero = int(escolhida)
    return str(numero - _BASE_DO_STEAMID64 if numero > _BASE_DO_STEAMID64 else numero)


def so_a_conta_logada(
    alvos: list[Path],
) -> tuple[list[Path], list[dict[str, str]]]:
    """Separa os vdfs da conta logada dos das outras contas da mesma Steam.

    Vdf que não tem a forma ``<raiz>/userdata/<conta>/config/localconfig.vdf``
    passa (foi apontado à mão). Sem ``loginusers.vdf`` que se leia, só passa
    quem é o ÚNICO vdf da raiz: com duas contas e sem resposta, adivinhar é
    escrever na conta errada.
    """
    por_raiz: dict[Path | None, list[Path]] = {}
    for vdf in alvos:
        forma = (
            len(vdf.parents) > 3
            and vdf.parent.name == "config"
            and vdf.parent.parent.parent.name == "userdata"
        )
        por_raiz.setdefault(vdf.parents[3] if forma else None, []).append(vdf)
    aceitos: list[Path] = []
    pulados: list[dict[str, str]] = []
    for raiz, vdfs in por_raiz.items():
        if raiz is None:
            aceitos.extend(vdfs)
            continue
        try:
            logada = conta_logada(raiz)
        except OSError:
            logada = None
        for vdf in vdfs:
            conta = vdf.parent.parent.name
            if (logada is not None and conta == logada) or (
                logada is None and len(vdfs) == 1
            ):
                aceitos.append(vdf)
            else:
                motivo = SEM_CONTA if logada is None else "conta_nao_logada"
                pulados.append({"vdf": str(vdf), "appid": "", "reason": motivo})
    return aceitos, pulados


class Relato(TypedDict):
    """O que ``aplicar`` devolve — e o que o ``--json`` publica."""

    status: str
    aplicados: list[dict[str, str]]
    pulados: list[dict[str, str]]
    erros: list[dict[str, str]]
    desfeitos: list[dict[str, str]]
    vdfs: int


def aplicar(
    home: Path | None = None,
    vdfs: list[Path] | None = None,
    *,
    config_home: Path | None = None,
    estado_home: Path | None = None,
    dry_run: bool = False,
) -> Relato:
    """Aplica a tabela aos ``localconfig.vdf`` da conta logada. NUNCA levanta.

    ``aplicado`` só sai depois de reler o vdf do disco e achar, em cada jogo, a
    opção onde a Steam a lê; o que o arquivo não guarda vai para ``desfeitos``
    e o status é ``desfeito_pela_steam``. O que escreveu (e o que a releitura
    desmentiu) fica no registro do state, para o ``conferir`` saber depois se a
    Steam desfez a opção e o doctor poder dizer.
    """
    tabela = ler(config_home)
    relato: Relato = {
        "status": NADA, "aplicados": [], "pulados": [], "erros": [],
        "desfeitos": [], "vdfs": 0,
    }
    if not tabela:
        return relato
    if steam_game_running():
        relato["status"] = ADIADO_JOGO
        return relato
    if steam_running():
        relato["status"] = ADIADO_STEAM
        return relato

    sem_atalho = set(ler_jogos_sem_wrapper())
    desejadas = {
        appid: linha_desejada(opcoes, com_atalho=appid not in sem_atalho)
        for appid, opcoes in tabela.items()
    }
    todos = list(vdfs) if vdfs is not None else discover_vdfs(home)
    alvos, de_outra_conta = so_a_conta_logada(todos)
    aplicados: list[dict[str, str]] = []
    # Sem saber a conta logada, a tabela não chega à Steam: é erro, nunca
    # «nada a fazer» (o ensaio do engasgo leria rc 0 como «pronto»).
    pulados = [p for p in de_outra_conta if p["reason"] != SEM_CONTA]
    erros = [
        {**p, "reason": f"{SEM_CONTA}: o config/loginusers.vdf não diz qual das contas "
                       f"a Steam abre ({p['vdf']})"}
        for p in de_outra_conta if p["reason"] == SEM_CONTA
    ]
    desfeitos: list[dict[str, str]] = []
    anotar: list[tuple[str, str, str]] = []  # (appid, vdf, resultado)
    escritas = {a: e.get("valor", "") for a, e in ler_registro(estado_home).items()}
    instalados = jogos_novos_a_receber(home, config_home=config_home)
    for vdf in alvos:
        if is_sandboxed_layout(vdf):
            pulados.append({"vdf": str(vdf), "appid": "", "reason": "vdf_sandbox"})
            continue
        try:
            texto = vdf.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError as exc:
            erros.append({"vdf": str(vdf), "appid": "", "reason": str(exc)})
            continue
        novo, feitos, deixados, compostos = compor_opcoes_vdf_text(
            texto, desejadas, escritas, instalados)
        relato["vdfs"] += 1
        pulados.extend(
            {"vdf": str(vdf), "appid": a, "reason": m} for a, m in deixados
        )
        anotar.extend(
            (a, str(vdf), ESCRITO_E_CONFERIDO) for a, m in deixados if m == "ja_e_o_desejado"
        )
        if not feitos or novo == texto:
            continue
        if dry_run:
            aplicados.extend({"vdf": str(vdf), "appid": a, "reason": "dry-run"} for a in feitos)
            continue
        try:
            backup = vdf.with_name(vdf.name + f".bak.hefesto-opcoes-{int(time.time())}")
            backup.write_text(texto, encoding="utf-8", errors="surrogateescape")
            vdf.write_text(novo, encoding="utf-8", errors="surrogateescape")
            no_disco = vdf.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError as exc:
            erros.append({"vdf": str(vdf), "appid": "", "reason": str(exc)})
            continue
        for appid in feitos:
            lidas = opcoes_lidas_do_jogo(no_disco, appid)
            querida = _valor_do_vdf(compostos[appid])
            if lidas and all(valor == querida for valor in lidas):
                aplicados.append({"vdf": str(vdf), "appid": appid, "reason": ""})
                anotar.append((appid, str(vdf), ESCRITO_E_CONFERIDO))
            else:
                desfeitos.append({
                    "vdf": str(vdf), "appid": appid, "reason": CONTRATO_DA_LINHA})
                anotar.append((appid, str(vdf), ESCRITO_E_DESFEITO))

    relato["aplicados"], relato["pulados"], relato["erros"] = aplicados, pulados, erros
    relato["desfeitos"] = desfeitos
    if anotar and not dry_run:
        _anotar_no_registro(anotar, desejadas, estado_home)
    if erros:
        relato["status"] = ERRO
    elif desfeitos:
        relato["status"] = DESFEITO
    elif aplicados:
        relato["status"] = APLICADO
    return relato


def _conta_do_vdf(vdf: str) -> str:
    """``userdata/<conta>/config/localconfig.vdf`` -> ``<conta>``; vazio se a forma for outra."""
    partes = Path(vdf).parts
    return partes[-3] if len(partes) >= 3 and partes[-3].isdigit() else ""


def _anotar_no_registro(
    anotar: list[tuple[str, str, str]],
    desejadas: dict[str, str],
    estado_home: Path | None,
) -> None:
    """Guarda o que o ``aplicar`` fez e releu. Best-effort: o registro nunca derruba o ato."""
    registro = ler_registro(estado_home)
    agora = time.strftime("%Y-%m-%dT%H:%M:%S")
    for appid, vdf, resultado in anotar:
        registro[appid] = {
            "valor": desejadas[appid], "conta": _conta_do_vdf(vdf),
            "quando": agora, "resultado": resultado,
        }
    gravar_registro(registro, estado_home)


def conferir(
    home: Path | None = None,
    vdfs: list[Path] | None = None,
    *,
    config_home: Path | None = None,
    estado_home: Path | None = None,
) -> dict[str, Any]:
    """Confere a tabela contra o que a Steam guarda AGORA. Só lê; NUNCA levanta.

    ``{"jogos": [{appid, estado, vdf}], "defeitos": [mesmos, só os defeitos]}``.
    Um jogo da tabela que não está no vdf da conta logada não entra (a conta não o
    tem). A opção que não está lá nem foi escrita pelo Hefesto nesta conta é ``novo``: o
    ``aplicar`` ainda vai pô-la, não é defeito. É defeito: a releitura do
    ``aplicar`` a desmentiu (``desfeito_na_escrita``), ela foi escrita e conferida
    e sumiu depois (``desfeito``), ou mora só num bloco filho (``fora_do_lugar``).
    """
    resultado: dict[str, Any] = {"jogos": [], "defeitos": []}
    try:
        tabela = ler(config_home)
        if not tabela:
            return resultado
        sem_atalho = set(
            ler_jogos_sem_wrapper(sem_wrapper_path(config_home))
            if config_home is not None else ler_jogos_sem_wrapper()
        )
        todos = list(vdfs) if vdfs is not None else discover_vdfs(home)
        alvos, de_outra_conta = so_a_conta_logada(todos)
        registro = ler_registro(estado_home)
        for p in de_outra_conta:
            if p["reason"] == SEM_CONTA:
                resultado["defeitos"].append(
                    {"appid": "", "estado": SEM_CONTA, "vdf": p["vdf"]})
        for vdf in alvos:
            if is_sandboxed_layout(vdf):
                continue
            texto = vdf.read_text(encoding="utf-8", errors="surrogateescape")
            for appid, opcoes in tabela.items():
                presente, achados = lugares_das_opcoes(texto, appid)
                if not presente:
                    continue
                desejada = linha_desejada(opcoes, com_atalho=appid not in sem_atalho)
                diretas = [v for direta, v in achados if direta]
                if diretas and all(
                    compor_linha(_vdf_unescape(v), desejada, desejada) == _vdf_unescape(v)
                    for _, v in achados
                ):
                    estado = OK
                elif achados and not diretas:
                    estado = FORA_DO_LUGAR
                else:
                    anotado = registro.get(appid, {})
                    # o registro é da conta em que o `aplicar` escreveu: noutra conta
                    # (a Steam trocou de usuário) a opção nunca foi escrita, é `novo`
                    escrito = anotado.get("valor") == linha_desejada(
                        opcoes, com_atalho=appid not in sem_atalho
                    ) and anotado.get("conta") == _conta_do_vdf(str(vdf))
                    if escrito and anotado.get("resultado") == ESCRITO_E_DESFEITO:
                        estado = DESFEITO_NA_ESCRITA
                    elif escrito and anotado.get("resultado") == ESCRITO_E_CONFERIDO:
                        estado = DESFEITO_DEPOIS
                    else:
                        estado = NOVO
                item = {"appid": appid, "estado": estado, "vdf": str(vdf)}
                resultado["jogos"].append(item)
                if estado in DEFEITOS:
                    resultado["defeitos"].append(item)
    except OSError:  # o vdf sumiu entre a descoberta e a leitura: nada a conferir
        return {"jogos": [], "defeitos": []}
    return resultado


def _imprimir(relato: Relato) -> int:
    """A saída do vigia: uma linha por ato, no formato dos irmãos."""
    for item in relato["aplicados"]:
        print(f"[opcoes-por-jogo] {item['appid']}: aplicado")
    for item in relato["desfeitos"]:
        print(
            f"[opcoes-por-jogo] {item['appid']}: {DESFEITO} — o vdf não guarda a opção "
            f"onde a Steam a lê ({item['reason']})",
            file=sys.stderr,
        )
    for item in relato["pulados"]:
        if item["reason"] == LINHA_DELA_DIVERGE:
            print(
                f"[opcoes-por-jogo] {item['appid']}: {LINHA_DELA_DIVERGE} — a linha que "
                "você escreveu não cabe com a da tabela sem perder parte dela; ficou como estava",
                file=sys.stderr,
            )
    for item in relato["erros"]:
        print(f"[opcoes-por-jogo] erro: {item['reason']}", file=sys.stderr)
    print(f"[opcoes-por-jogo] resultado={relato['status']}")
    if relato["status"] in (ADIADO_JOGO, ADIADO_STEAM):
        return 3
    return 1 if relato["status"] in (ERRO, DESFEITO) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="opcoes_por_jogo",
        description=(
            "A tabela de opções de inicialização por jogo: o Hefesto compõe o "
            "atalho dele com as opções que você declarar. Sem argumentos, "
            "--listar."
        ),
    )
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--listar", action="store_true", help="a tabela (default)")
    grupo.add_argument("--json", action="store_true", help="a tabela em JSON")
    grupo.add_argument(
        "--aplicar", action="store_true",
        help="escreve a tabela no vdf (exige Steam fechada; adia se não der)",
    )
    grupo.add_argument(
        "--definir", nargs=2, metavar=("APPID", "OPCOES"),
        help="põe ou troca as opções de um jogo",
    )
    grupo.add_argument("--tirar", metavar="APPID", help="tira um jogo da tabela")
    grupo.add_argument(
        "--conferir", action="store_true",
        help="confere a tabela contra o que a Steam guarda agora (só lê; JSON)",
    )
    parser.add_argument("--dry-run", action="store_true", help="não escreve (com --aplicar)")
    parser.add_argument(
        "--vdf", action="append", type=Path, default=None, metavar="ARQUIVO",
        help="localconfig.vdf explícito (repetível; default: descoberta automática)",
    )
    args = parser.parse_args(argv)

    if args.definir:
        appid, opcoes = args.definir
        try:
            valor = definir(appid, opcoes)
        except ValueError as exc:
            print(f"[opcoes-por-jogo] recusado: {exc}", file=sys.stderr)
            return 2
        print(f"[opcoes-por-jogo] {appid}: {valor}")
        print(f"[opcoes-por-jogo] tabela em {tabela_path()}")
        return 0
    if args.tirar:
        print(f"[opcoes-por-jogo] {args.tirar}: "
              + ("tirado" if tirar(args.tirar) else "não estava na tabela"))
        return 0
    if args.conferir:
        print(json.dumps(conferir(vdfs=args.vdf), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.aplicar:
        return _imprimir(aplicar(vdfs=args.vdf, dry_run=args.dry_run))
    tabela = ler()
    if args.json:
        print(json.dumps(tabela, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not tabela:
        print(f"[opcoes-por-jogo] tabela vazia ({tabela_path()})")
        return 0
    sem_atalho = set(ler_jogos_sem_wrapper())
    for appid, opcoes in sorted(tabela.items(), key=lambda x: int(x[0])):
        marca = " (sem o atalho, por escolha sua)" if appid in sem_atalho else ""
        print(f"[opcoes-por-jogo] {appid}\t{opcoes}{marca}")
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint do vigia
    sys.exit(main())
