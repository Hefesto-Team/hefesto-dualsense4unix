#!/usr/bin/env python3
"""AS OPÇÕES DE INICIALIZAÇÃO QUE ELA DECLARA — uma tabela, um dono.

POR QUE ISTO EXISTE, e a medição é de 21/09/2026
------------------------------------------------
A Steam guarda **UMA** linha de ``LaunchOptions`` por jogo, e tudo que quiser
estar ali disputa a mesma linha. Na máquina dela havia DOIS donos:

* o Hefesto, que põe o atalho ``hefesto-launch`` (sem ele, no rádio o jogo
  tende a não enxergar controle nenhum);
* uma tabela declarativa dela, fora deste produto, que reescrevia a linha com
  as variáveis de vídeo do jogo — e apagava o atalho ao fazê-lo.

O resultado foi medido no diário de um dia inteiro: **de hora em hora** o
PRAGMATA perdia o atalho e o vigia o repunha, das 04:31 às 22:00. Quem abrisse
o jogo na janela errada jogava sem controle. *Duas ferramentas escrevendo a
mesma linha não é configuração; é sorteio.*

A DECISÃO É `D-2109-AS-OPCOES-POR-JOGO-TEM-UM-DONO-SO`, e a ordem dela, de
21/09/2026, é esta: *"PODE CORRIGIR E INTEGRAR ELE AO NOSSO APP.
DESATIVA O ORIGINAL ENTÃAO."*  <!-- noqa-acento: citação literal dela, a
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

O JOGO QUE ELA TIROU DO ATALHO continua fora dele: o appid que está no
``jogos_sem_wrapper.txt`` recebe as opções dela SEM o atalho. O produto não
briga com a dona da máquina — é a mesma regra do
``apply_wrapper_vdf_text(excluir=…)``.

SÓ COM A STEAM FECHADA, pelo mesmo motivo de sempre: a Steam viva regrava o
``localconfig.vdf`` ao sair e engole a edição. Com jogo aberto nem se cogita.
Quem chama de hora em hora é o ``hefesto-steam-input-guard``, na mesma carona
do reparo do atalho — e ali "adiei" não é falha.

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
from pathlib import Path
from typing import TypedDict

try:  # importado como módulo do pacote (GUI/daemon/testes)
    from .steam_launch_options import (
        WRAPPER_PREFIX,
        discover_vdfs,
        e_a_arvore_canonica,
        is_sandboxed_layout,
        ler_jogos_sem_wrapper,
        steam_game_running,
        steam_running,
    )
except ImportError:  # pragma: no cover - executado como script avulso pelo vigia
    from steam_launch_options import (  # type: ignore[no-redef]
        WRAPPER_PREFIX,
        discover_vdfs,
        e_a_arvore_canonica,
        is_sandboxed_layout,
        ler_jogos_sem_wrapper,
        steam_game_running,
        steam_running,
    )

#: Onde a tabela mora, no molde do `jogos_sem_wrapper.txt`.
TABELA_RELPATH = "hefesto-dualsense4unix/opcoes_por_jogo.txt"

#: O cabeçalho que nasce com o arquivo — ele tem de se explicar sozinho para
#: quem o abrir num editor, porque é ali que ela escreve.
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
NADA = "nada_a_fazer"
ADIADO_JOGO = "adiado_jogo_aberto"
ADIADO_STEAM = "adiado_steam_aberta"
ERRO = "erro"

_APPID = re.compile(r"^[0-9]{1,10}$")


def tabela_path(config_home: Path | None = None) -> Path:
    """Caminho da tabela (XDG), sem tocar no disco — gêmeo do `sem_wrapper_path`."""
    if config_home is not None:
        base = config_home
    else:
        env = os.environ.get("XDG_CONFIG_HOME")
        base = Path(env) if env else Path.home() / ".config"
    return base / TABELA_RELPATH


def parse(texto: str) -> dict[str, str]:
    """``{appid: opções}`` de um texto de tabela. Nunca levanta.

    LINHA TORTA É LINHA IGNORADA, e de propósito: um arquivo que ela editou à
    mão com um erro de digitação não pode derrubar o vigia nem apagar as
    opções dos OUTROS jogos. O que se perde é uma linha, e o ``--listar`` a
    mostra faltando.

    O SEPARADOR É TAB, e o espaço vale como tolerância: as opções contêm
    espaços por natureza (``VKD3D_CONFIG=… %command%``), então só o PRIMEIRO
    separador conta — o resto da linha é o valor, inteiro.
    """
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


def tirar(appid: int | str, config_home: Path | None = None) -> bool:
    """Tira um jogo da tabela. ``False`` quando ele já não estava lá."""
    chave = str(appid).strip()
    tabela = ler(config_home)
    if chave not in tabela:
        return False
    del tabela[chave]
    gravar(tabela, config_home)
    return True


def linha_desejada(opcoes: str, *, com_atalho: bool) -> str:
    """A linha final do vdf: o atalho na frente, as opções dela atrás.

    O ATALHO VEM DO DONO (``steam_launch_options.WRAPPER_PREFIX``) e não é
    redigitado aqui: ele muda de forma quando o install muda de caminho, e uma
    segunda cópia envelheceria calada — que é o defeito que esta casa persegue.
    """
    limpo = opcoes.strip()
    return f"{WRAPPER_PREFIX} {limpo}" if com_atalho else limpo


def _valor_do_vdf(bruto: str) -> str:
    """O valor como o vdf o escreve, com as aspas escapadas."""
    return bruto.replace("\\", "\\\\").replace('"', '\\"')


def definir_opcoes_vdf_text(
    texto: str, desejadas: dict[str, str]
) -> tuple[str, list[str], list[tuple[str, str]]]:
    """Põe ``desejadas`` (``{appid: linha pronta}``) na árvore CANÔNICA do vdf.

    PURA, e é a metade testável: o parse por pilha de linhas é o mesmo do
    ``read_launch_options_by_appid`` — conteúdo fora do padrão passa intacto,
    byte a byte. Um app cuja linha JÁ é a desejada é pulado (idempotente), e um
    app sem a linha ``LaunchOptions`` a GANHA, com a indentação dos vizinhos.

    Devolve ``(texto_novo, aplicados, [(appid, motivo)])``.
    """
    linhas = texto.splitlines(keepends=True)
    pilha: list[str] = []
    saida: list[str] = []
    aplicados: list[str] = []
    pulados: list[tuple[str, str]] = []
    vistos: set[str] = set()
    appid_atual: str | None = None
    tem_linha = False
    indent_do_bloco = "\t\t\t\t\t\t"
    inicio_do_bloco = -1

    for linha in linhas:
        nu = linha.strip()
        if nu.startswith('"') and nu.endswith('"') and nu.count('"') == 2:
            pilha.append(nu.strip('"'))
            saida.append(linha)
            continue
        if nu == "{":
            saida.append(linha)
            # A ÂNCORA É SEM O APPID: `e_a_arvore_canonica` mede o caminho do
            # PAI (`…/Software/Valve/Steam/apps`), e a pilha aqui já tem o
            # appid no topo — é o mesmo `stack[:-1]` do escritor irmão.
            if pilha and _APPID.match(pilha[-1]) and e_a_arvore_canonica(pilha[:-1]):
                appid_atual = pilha[-1]
                tem_linha = False
                inicio_do_bloco = len(saida)
            continue
        if nu == "}":
            if appid_atual is not None and appid_atual in desejadas and not tem_linha:
                base = saida[inicio_do_bloco] if inicio_do_bloco < len(saida) else ""
                indent = base[: len(base) - len(base.lstrip())] or indent_do_bloco
                valor = _valor_do_vdf(desejadas[appid_atual])
                saida.append(f'{indent}"LaunchOptions"\t\t"{valor}"\n')
                aplicados.append(appid_atual)
                vistos.add(appid_atual)
            appid_atual = None
            if pilha:
                pilha.pop()
            saida.append(linha)
            continue
        casou = re.match(r'^(\s*)"LaunchOptions"(\s*)"((?:[^"\\]|\\.)*)"(\s*)$', linha)
        if casou and appid_atual is not None and appid_atual in desejadas:
            atual = casou.group(3)
            querido = _valor_do_vdf(desejadas[appid_atual])
            tem_linha = True
            vistos.add(appid_atual)
            if atual == querido:
                pulados.append((appid_atual, "ja_e_o_desejado"))
                saida.append(linha)
                continue
            saida.append(
                f'{casou.group(1)}"LaunchOptions"{casou.group(2)}"{querido}"{casou.group(4)}'
            )
            aplicados.append(appid_atual)
            continue
        if casou and appid_atual is not None:
            tem_linha = True
        saida.append(linha)

    for appid in desejadas:
        if appid not in vistos:
            pulados.append((appid, "jogo_nao_esta_neste_vdf"))
    return "".join(saida), aplicados, pulados


class Relato(TypedDict):
    """O que ``aplicar`` devolve — e o que o ``--json`` publica.

    É ``TypedDict`` e não dataclass de propósito: quem consome isto é o
    ``json.dumps`` do ``--json`` e o ``_imprimir`` do vigia, os dois em cima de
    chaves. A forma TIPADA existe porque a primeira versão era
    ``dict[str, object]`` e cobrava quatro ``type: ignore`` para somar 1 a um
    contador — o tipo frouxo não estava protegendo nada.
    """

    status: str
    aplicados: list[dict[str, str]]
    pulados: list[dict[str, str]]
    erros: list[dict[str, str]]
    vdfs: int


def aplicar(
    home: Path | None = None,
    vdfs: list[Path] | None = None,
    *,
    config_home: Path | None = None,
    dry_run: bool = False,
) -> Relato:
    """Aplica a tabela aos ``localconfig.vdf`` elegíveis. NUNCA levanta.

    Os portões são os mesmos do reparo do atalho, e na mesma ordem: jogo aberto
    recusa antes de tudo (fechar o vdf debaixo de um jogo vivo é o estrago que
    não se desfaz), Steam aberta adia. Tabela vazia é ``nada_a_fazer`` — e não
    um vdf reescrito com o que já estava lá.

    Devolve ``{"status", "aplicados", "pulados", "erros", "vdfs"}``.
    """
    tabela = ler(config_home)
    relato: Relato = {
        "status": NADA, "aplicados": [], "pulados": [], "erros": [], "vdfs": 0,
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
    alvos = list(vdfs) if vdfs is not None else discover_vdfs(home)
    aplicados: list[dict[str, str]] = []
    pulados: list[dict[str, str]] = []
    erros: list[dict[str, str]] = []
    for vdf in alvos:
        if is_sandboxed_layout(vdf):
            pulados.append({"vdf": str(vdf), "appid": "", "reason": "vdf_sandbox"})
            continue
        try:
            texto = vdf.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError as exc:
            erros.append({"vdf": str(vdf), "appid": "", "reason": str(exc)})
            continue
        novo, feitos, deixados = definir_opcoes_vdf_text(texto, desejadas)
        relato["vdfs"] += 1
        pulados.extend(
            {"vdf": str(vdf), "appid": a, "reason": m} for a, m in deixados
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
        except OSError as exc:
            erros.append({"vdf": str(vdf), "appid": "", "reason": str(exc)})
            continue
        aplicados.extend({"vdf": str(vdf), "appid": a, "reason": ""} for a in feitos)

    relato["aplicados"], relato["pulados"], relato["erros"] = aplicados, pulados, erros
    if erros:
        relato["status"] = ERRO
    elif aplicados:
        relato["status"] = APLICADO
    return relato


def _imprimir(relato: Relato) -> int:
    """A saída do vigia: uma linha por ato, no formato dos irmãos."""
    for item in relato["aplicados"]:
        print(f"[opcoes-por-jogo] {item['appid']}: aplicado")
    for item in relato["erros"]:
        print(f"[opcoes-por-jogo] erro: {item['reason']}", file=sys.stderr)
    print(f"[opcoes-por-jogo] resultado={relato['status']}")
    # 3 = ADIADO, o mesmo código que a sentinela usa: não é falha, e o `-` da
    # unidade do vigia existe justamente para não pintar o guard de vermelho.
    if relato["status"] in (ADIADO_JOGO, ADIADO_STEAM):
        return 3
    return 1 if relato["status"] == ERRO else 0


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
