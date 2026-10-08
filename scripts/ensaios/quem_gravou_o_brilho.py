#!/usr/bin/env python3
"""Quem gravou o brilho de um controle no perfil: a perícia das cópias.

Só LÊ. Não fala com o daemon, não escreve em pasta nenhuma e imprime no
terminal; quem quiser guardar redireciona. Nasceu da sprint
O-BRILHO-BAIXO-QUE-ELA-NAO-ESCOLHEU-01 (ela disse «Não fui eu» sobre o 8% do
controle branco no Freestyle).

O que faz, por ordem:

1. Lê as cópias do perfil em ordem de HORA (o histórico de `personalizado` e de
   `freestyle`, as `freestyle.json.antes-*`, as cópias da casa e o arquivo de
   agora) e diz, por controle, em que par de cópias o
   `controllers[<peça>].leds.lightbar_brightness` muda, e de quanto a quanto.
2. Casa o intervalo de cada mudança com as linhas `profile_salvo` do
   `interface.log*` (e do diário, quando ele alcança): quantas gravações, de que
   janela, de que `origem`, e se foi uma rajada de arraste ou uma gravação de
   abertura.
3. Lê a migração de `profiles/loader.py` e diz se ela toca o brilho.
4. Diz o escritor que a medida sustenta, e o que falta quando ela não alcança.

Os controles saem por LETRA (A, B, C…), na ordem em que aparecem na primeira
cópia: nenhum endereço sai na saída, em forma nenhuma (a máscara é a última
coisa que passa por cima do texto).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
from typing import Any, NamedTuple

HOME = pathlib.Path.home()
RAIZ = pathlib.Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

_ENDERECO_COM_SEPARADOR = re.compile(r"\b[0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5}\b")
_ENDERECO_COLADO = re.compile(r"\b[0-9a-fA-F]{12}\b")
_HORA_DO_NOME = re.compile(r"(\d{8})T(\d{6})")
_LINHA_DO_LOG = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?) \[\w+\s*\] (\S+)\s*(.*)$")
_JANELA = re.compile(r"a janela abriu em (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")
_PARES = re.compile(r"(\w+)=(\S+)")
_DIARIO = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})[^ ]* \S+ [^ ]+\[\d+\]: (.*)$")

#: Duas gravações a menos de tantos segundos uma da outra são o mesmo arraste.
SEGUNDOS_DA_RAJADA = 60.0
#: O `load_profile` semeia os perfis de jogo na PRIMEIRA leitura do processo; a
#: gravação que vem logo depois é o primeiro gesto que lê o perfil.
SEMEADURA = ("perfis_de_jogo_semeados", "perfil_de_jogo_recusado")
SEGUNDOS_DA_SEMEADURA = 2.0


def mascarar(texto: str) -> str:
    """Nenhum endereço de rádio sai, nas formas com separador e colada."""
    texto = _ENDERECO_COM_SEPARADOR.sub("<endereço>", texto)
    return _ENDERECO_COLADO.sub("<endereço>", texto)


class Copia(NamedTuple):
    """Uma versão do perfil, com a hora em que ela era a vigente."""

    hora: dt.datetime
    rotulo: str
    dados: dict[str, Any]


def _hora_da_copia(caminho: pathlib.Path) -> dt.datetime:
    achou = _HORA_DO_NOME.search(caminho.name)
    if achou:
        return dt.datetime.strptime(achou.group(1) + achou.group(2), "%Y%m%d%H%M%S")
    return dt.datetime.fromtimestamp(caminho.stat().st_mtime)


def _ler(caminho: pathlib.Path, rotulo: str) -> Copia | None:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(dados, dict):
        return None
    return Copia(_hora_da_copia(caminho), rotulo, dados)


def achar_as_copias(perfis: pathlib.Path, casa: pathlib.Path | None,
                    estado: pathlib.Path | None) -> list[Copia]:
    """Todas as cópias que existem no disco, SEM ordenar (quem ordena é outro)."""
    achados: list[tuple[pathlib.Path, str]] = []
    for slug in ("personalizado", "freestyle"):
        for p in sorted((perfis / ".historico" / slug).glob("*.json")):
            achados.append((p, f"histórico {slug}"))
    for p in sorted(perfis.glob("freestyle.json.antes-*")):
        achados.append((p, "cópia " + p.name.split(".json.", 1)[1]))
    if (perfis / "freestyle.json").is_file():
        achados.append((perfis / "freestyle.json", "agora"))
    if casa is not None:
        for sub in ("bancada-antes-2709/freestyle.json",
                    "leva-2809/bancada-2809/perfis-antes-da-bancada/profiles/freestyle.json"):
            if (casa / sub).is_file():
                achados.append((casa / sub, "cópia da casa " + sub.split("/")[0]))
    if estado is not None:
        for p in sorted(estado.glob("o-basico-copias/*/antes/copia/profiles/freestyle.json")):
            achados.append((p, "cópia do básico"))
    copias = [c for c in (_ler(p, r) for p, r in achados) if c is not None]
    return copias


def ordenar_copias(copias: list[Copia]) -> list[Copia]:
    """Em ordem de hora; empate pela ordem em que vieram (a sort é estável)."""
    return sorted(copias, key=lambda c: c.hora)


def _brilho_da_peca(dados: dict[str, Any], chave: str) -> float | None:
    controles = dados.get("controllers")
    if not isinstance(controles, dict):
        return None
    peca = controles.get(chave)
    if not isinstance(peca, dict):
        return None
    leds = peca.get("leds")
    if not isinstance(leds, dict):
        return None
    valor = leds.get("lightbar_brightness")
    return float(valor) if isinstance(valor, (int, float)) else None


def letras_das_pecas(copias: list[Copia]) -> dict[str, str]:
    """A letra de cada controle: a ordem em que ele aparece, da cópia mais velha."""
    letras: dict[str, str] = {}
    for c in copias:
        controles = c.dados.get("controllers")
        if not isinstance(controles, dict):
            continue
        for chave in controles:
            if chave not in letras:
                letras[chave] = chr(ord("A") + len(letras))
    return letras


class Mudanca(NamedTuple):
    letra: str
    de: float | None
    para: float | None
    depois_de: Copia
    ate: Copia


def mudancas(copias: list[Copia], letras: dict[str, str]) -> list[Mudanca]:
    """Cada troca de valor, com o par de cópias que a emoldura."""
    saida: list[Mudanca] = []
    for chave, letra in letras.items():
        anterior: Copia | None = None
        valor: float | None = None
        for c in copias:
            if not isinstance(c.dados.get("controllers"), dict) \
                    or chave not in c.dados["controllers"]:
                continue
            novo = _brilho_da_peca(c.dados, chave)
            if anterior is not None and novo != valor:
                saida.append(Mudanca(letra, valor, novo, anterior, c))
            anterior, valor = c, novo
    return sorted(saida, key=lambda m: (m.letra, m.ate.hora))


class Gravacao(NamedTuple):
    hora: dt.datetime
    origem: str
    pid: str
    antes: str
    fonte: str
    depois_do_anterior_s: float | None = None


def _parse_hora(texto: str) -> dt.datetime:
    return dt.datetime.fromisoformat(texto.split(".")[0])


def ler_os_logs(logs: list[pathlib.Path]) -> tuple[list[Gravacao], list[dt.datetime]]:
    """As gravações do `freestyle.json` e as horas em que a janela abriu."""
    gravacoes: list[Gravacao] = []
    aberturas: list[dt.datetime] = []
    for log in logs:
        try:
            linhas = log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        anterior = ""
        hora_do_anterior: dt.datetime | None = None
        for linha in linhas:
            abriu = _JANELA.search(linha)
            if abriu:
                aberturas.append(_parse_hora(abriu.group(1)))
                continue
            casou = _LINHA_DO_LOG.match(linha)
            if not casou:
                continue
            hora, evento, resto = casou.groups()
            if evento == "profile_salvo":
                pares = dict(_PARES.findall(resto))
                if pares.get("arquivo") == "freestyle.json":
                    quando = dt.datetime.fromisoformat(hora)
                    espaco = ((quando - hora_do_anterior).total_seconds()
                              if hora_do_anterior is not None else None)
                    gravacoes.append(Gravacao(
                        quando, pares.get("origem", "?"), pares.get("pid", "?"),
                        anterior, "log", espaco))
            anterior = evento
            hora_do_anterior = dt.datetime.fromisoformat(hora)
    return sorted(gravacoes, key=lambda g: g.hora), sorted(set(aberturas))


def ler_o_diario(origem: str) -> tuple[list[Gravacao], dt.datetime | None]:
    """As gravações do diário do serviço e a hora em que ele COMEÇA a alcançar."""
    if origem == "nenhum":
        return [], None
    if origem == "auto":
        try:
            r = subprocess.run(
                ["journalctl", "--user", "-u", "hefesto-dualsense4unix", "--no-pager",
                 "-o", "short-iso"], capture_output=True, text=True, timeout=90,
                check=False)
            texto = r.stdout
        except (OSError, subprocess.SubprocessError):
            return [], None
    else:
        try:
            texto = pathlib.Path(origem).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return [], None
    gravacoes: list[Gravacao] = []
    primeira: dt.datetime | None = None
    for linha in texto.splitlines():
        casou = _DIARIO.match(linha)
        if not casou:
            continue
        hora = dt.datetime.fromisoformat(casou.group(1))
        if primeira is None:
            primeira = hora
        if "profile_salvo" in casou.group(2) and "arquivo=freestyle.json" in casou.group(2):
            pares = dict(_PARES.findall(casou.group(2)))
            gravacoes.append(Gravacao(hora, pares.get("origem", "?"),
                                      pares.get("pid", "?"), "", "diário"))
    return gravacoes, primeira


class Grupo(NamedTuple):
    abertura: dt.datetime | None
    pid: str
    quantas: int
    primeira: dt.datetime
    ultima: dt.datetime
    rajada: int
    origens: tuple[str, ...]
    antes: str
    atraso_s: float | None
    depois_do_anterior_s: float | None


def agrupar_por_janela(gravacoes: list[Gravacao],
                       aberturas: list[dt.datetime]) -> list[Grupo]:
    """Uma linha por (janela, pid): quantas gravações e de que jeito."""
    por: dict[tuple[dt.datetime | None, str], list[Gravacao]] = {}
    for g in gravacoes:
        abertura = None
        for a in aberturas:
            if a <= g.hora:
                abertura = a
        por.setdefault((abertura, g.pid), []).append(g)
    grupos: list[Grupo] = []
    for (abertura, pid), lista in por.items():
        lista.sort(key=lambda g: g.hora)
        maior = 1
        for i, g in enumerate(lista):
            n = sum(1 for h in lista[i:]
                    if (h.hora - g.hora).total_seconds() <= SEGUNDOS_DA_RAJADA)
            maior = max(maior, n)
        atraso = (lista[0].hora - abertura).total_seconds() if abertura else None
        grupos.append(Grupo(abertura, pid, len(lista), lista[0].hora, lista[-1].hora,
                            maior, tuple(sorted({g.origem for g in lista})),
                            lista[0].antes, atraso, lista[0].depois_do_anterior_s))
    return sorted(grupos, key=lambda g: g.primeira)


def ler_a_migracao(loader: pathlib.Path) -> tuple[int | None, bool | None]:
    """A linha da troca Personalizado→Freestyle e se ela fala de brilho/luz."""
    try:
        fonte = loader.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, None
    inicio = next((i for i, linha in enumerate(fonte)
                   if linha.startswith("def _trocar_o_personalizado")), None)
    if inicio is None:
        return None, None
    fim = next((i for i in range(inicio + 1, len(fonte))
                if fonte[i].startswith("def ")), len(fonte))
    corpo = "\n".join(fonte[inicio:fim])
    return inicio + 1, bool(re.search(r"brightness|brilho|\bleds\b|lightbar", corpo))


def achar_o_trilho(a04: pathlib.Path) -> tuple[int | None, int | None]:
    """As linhas do trilho «Brilho»: quem monta o valor e quem grava."""
    try:
        fonte = a04.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, None
    monta = next((i + 1 for i, linha in enumerate(fonte)
                  if linha.startswith("def _com_o_brilho_gravado")), None)
    grava = next((i + 1 for i, linha in enumerate(fonte)
                  if "gravar_pelo_gesto" in linha
                  and "_com_o_brilho_gravado(prof, uniq, pct)" in linha), None)
    return monta, grava


def sem_repetidas(gravacoes: list[Gravacao]) -> list[Gravacao]:
    """A mesma gravação vista no log e no diário conta uma vez (mesmo segundo e pid)."""
    vistas: dict[tuple[str, str], Gravacao] = {}
    for g in gravacoes:
        vistas.setdefault((g.hora.strftime("%Y%m%dT%H%M%S"), g.pid), g)
    return sorted(vistas.values(), key=lambda g: g.hora)


def _h(hora: dt.datetime) -> str:
    return hora.strftime("%d/%m %H:%M:%S")


def _num(valor: float | None) -> str:
    return "sem override" if valor is None else f"{valor:g}".replace(".", ",")


def _inteiro_em_percentual(valor: float | None) -> bool:
    return valor is not None and abs(valor * 100 - round(valor * 100)) < 1e-9


def relatorio(copias: list[Copia], gravacoes: list[Gravacao], aberturas: list[dt.datetime],
              diario_desde: dt.datetime | None, migracao: tuple[int | None, bool | None],
              trilho: tuple[int | None, int | None], so_a_peca: str | None) -> str:
    saida: list[str] = []
    letras = letras_das_pecas(copias)
    achadas = mudancas(copias, letras)
    todas = achadas
    if so_a_peca:
        achadas = [m for m in achadas if m.letra == so_a_peca]
    saida.append(f"{len(copias)} cópia(s) do perfil lida(s), de {_h(copias[0].hora)} "
                 f"a {_h(copias[-1].hora)}; controles: "
                 f"{', '.join(sorted(letras.values()))}." if copias
                 else "Nenhuma cópia do perfil achada.")
    for letra in sorted({m.letra for m in achadas}):
        saida.append("")
        saida.append(f"Controle {letra}, as mudanças de brilho:")
        for m in (x for x in achadas if x.letra == letra):
            saida.append(
                f"  {_num(m.de)} -> {_num(m.para)}  entre «{m.depois_de.rotulo}» "
                f"de {_h(m.depois_de.hora)} e «{m.ate.rotulo}» de {_h(m.ate.hora)}")
            outros = [x for x in todas
                      if x.ate is m.ate and x.letra != m.letra]
            if outros:
                saida.append(
                    "    até a mesma cópia mudaram também: "
                    + ", ".join(f"{x.letra} ({_num(x.de)} -> {_num(x.para)})"
                                for x in outros)
                    + " (os outros controles moveram junto: não é prova de um gesto "
                    "só, nem de que a seção foi reescrita inteira).")
            nele = [g for g in gravacoes if m.depois_de.hora <= g.hora <= m.ate.hora]
            grupos = agrupar_por_janela(nele, aberturas)
            if diario_desde is not None and m.ate.hora < diario_desde:
                saida.append(f"    o diário do serviço só alcança de {_h(diario_desde)} "
                             "em diante: este intervalo só tem o interface.log")
            if not grupos:
                saida.append("    nenhuma gravação do freestyle.json nos logs deste "
                             "intervalo: o escritor não deixou linha")
                continue
            saida.append(f"    {len(nele)} gravação(ões) do freestyle.json no "
                         f"intervalo, em {len(grupos)} janela(s):")
            for g in grupos:
                abriu = _h(g.abertura) if g.abertura else "antes dos logs"
                atraso = f", a {g.atraso_s:.0f} s da abertura" if g.atraso_s is not None else ""
                tipo = ("rajada de arraste" if g.rajada >= 3 else "gravação avulsa")
                if g.antes in SEMEADURA and g.depois_do_anterior_s is not None \
                        and g.depois_do_anterior_s <= SEGUNDOS_DA_SEMEADURA:
                    tipo = (
                        "primeira leitura de perfil da janela (a semeadura saiu "
                        f"{g.depois_do_anterior_s:.2f} s antes: o `load_profile` a "
                        "dispara); é o primeiro gesto que carrega o perfil, não "
                        "uma gravação de abertura")
                saida.append(
                    f"      janela de {abriu}: {g.quantas} de {_h(g.primeira)} a "
                    f"{_h(g.ultima)}{atraso}; maior rajada em {SEGUNDOS_DA_RAJADA:.0f} s: "
                    f"{g.rajada}; origem {'/'.join(g.origens)}; {tipo}")
            origens = {g.origem for g in nele}
            inteiro = _inteiro_em_percentual(m.para)
            if len(nele) == 1:
                unica = nele[0]
                saida.append(
                    f"    ESCRITOR PROVÁVEL: a única gravação do log neste intervalo, "
                    f"{_h(unica.hora)} (origem {unica.origem}, pid {unica.pid}). "
                    "Provável e não provado: o serviço também grava o perfil, e o "
                    + ("diário dele não alcança esta hora."
                       if diario_desde is not None and m.ate.hora < diario_desde
                       else "diário dele não mostra outra gravação."))
            elif origens == {"interface-nova"} and inteiro:
                monta, grava = trilho
                onde = (f" (a04_iluminacao.py:{monta} monta, :{grava} grava)"
                        if monta and grava else "")
                saida.append(
                    "    ESCRITOR PROVÁVEL: um gesto de janela da interface (todas as "
                    "gravações são `interface-nova`) e o valor é percentual inteiro "
                    f"({_num(m.para)}); o gesto que grava esse campo por controle é o "
                    f"trilho «Brilho» da Iluminação{onde}.")
                saida.append(f"    NÃO FECHA a hora: são {len(nele)} gravações possíveis "
                             "e o log não diz o gesto nem o campo; falta a cópia "
                             "anterior a cada uma e a linha do gesto.")
            else:
                saida.append(f"    INDETERMINADO entre {len(nele)} gravações "
                             f"(origens: {'/'.join(sorted(origens))}).")
    linha, toca = migracao
    saida.append("")
    if linha is None:
        saida.append("A migração Personalizado -> Freestyle: loader.py não achado.")
    elif toca:
        saida.append(f"A migração (loader.py:{linha}) FALA de brilho/luz: leia a função.")
    else:
        saida.append(
            f"A migração Personalizado -> Freestyle (loader.py:{linha}) não toca o "
            "brilho nem os leds: grava os dados como estão, só trocando o nome (e a "
            "regra de janela do próprio Hefesto); ela não é a escritora.")
    return mascarar("\n".join(saida))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--perfis", type=pathlib.Path,
                   default=HOME / ".config/hefesto-dualsense4unix/profiles")
    p.add_argument("--casa", type=pathlib.Path, default=HOME / ".local/state/hefesto-casa")
    p.add_argument("--estado", type=pathlib.Path,
                   default=HOME / ".local/state/hefesto-dualsense4unix")
    p.add_argument("--logs", type=pathlib.Path, nargs="*",
                   help="padrão: interface.log.1 e interface.log do --estado")
    p.add_argument("--diario", default="auto",
                   help="`auto` (journalctl --user, leitura), `nenhum` ou um arquivo")
    p.add_argument("--loader", type=pathlib.Path, default=SRC / "profiles/loader.py")
    p.add_argument("--a04", type=pathlib.Path,
                   default=SRC / "interface/pacotes/a04_iluminacao.py")
    p.add_argument("--peca", help="só este controle (A, B, C…)")
    a = p.parse_args(argv)

    copias = ordenar_copias(achar_as_copias(a.perfis, a.casa, a.estado))
    logs = a.logs if a.logs else [a.estado / "interface.log.1", a.estado / "interface.log"]
    do_log, aberturas = ler_os_logs(logs)
    do_diario, diario_desde = ler_o_diario(a.diario)
    gravacoes = sem_repetidas(do_log + do_diario)
    if not copias:
        print(relatorio([], [], [], None, (None, None), (None, None), None))
        return 1
    print(relatorio(copias, gravacoes, aberturas, diario_desde,
                    ler_a_migracao(a.loader), achar_o_trilho(a.a04), a.peca))
    return 0


if __name__ == "__main__":
    sys.exit(main())
