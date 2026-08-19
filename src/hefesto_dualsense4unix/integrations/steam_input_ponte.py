"""PONTE-STEAM-INPUT-01 — a lista de exceções passa a LIGAR, não só a preservar.

O DEFEITO, nomeado pelo próprio produto
---------------------------------------
O `prontuario_dos_jogos` já dizia, no estorvo `excecao_inerte`: *"Este jogo
está na sua lista de exceções do Steam Input, mas o Steam Input está DESLIGADO
para ele. A lista só preserva o que já estava ligado — ela nunca liga."* E a
cura escrita ao lado mandava ELA abrir a Steam e clicar. Um diagnóstico
perfeito e uma cura que o produto não aplicava: o defeito mais caro desta casa.

O PREÇO, medido na noite de 18→19/08/2026
------------------------------------------
DON'T SCREAM (appid 2497900) é da classe *"só aceita Steam Input"*: motor
Unreal, fala XInput, e quem lhe entregava um dispositivo XInput era o espelho
Xbox do Steam Input. Com o Steam Input desligado o jogo não via controle
nenhum, e o guarda (`scripts/disable_steam_input.sh`) desligava a única ponte
que o fazia funcionar. O diagnóstico da própria janela dizia, textualmente:
*"o Hefesto vai desligá-lo no próximo ciclo do guarda, porque esse jogo não
está na sua lista de exceções"*.

A lista é o gesto dela dizendo *"a entrada deste jogo vem da Steam"*. Se o
gesto não liga a ponte, ele é decoração.

ONDE A CHAVE MORA DE VERDADE (medido em 19/08/2026, e é o contrário do que se
supunha)
------------------------------------------------------------------------------
`ARVORE-ERRADA-01` (16/08) já havia medido que o `localconfig.vdf` dela tem
TRÊS blocos chamados `apps`, e fixou que o das `LaunchOptions` é
``UserLocalConfigStore/Software/Valve/Steam/apps``. É tentador aplicar a mesma
âncora aqui. **Seria escrever num lugar que a Steam não lê.** A contagem no
arquivo vivo dela, hoje::

    árvore `apps`                                    apps  LaunchOptions  a CHAVE
    .../Software/Valve/Steam/apps                      63       63           0
    .../WebStorage/apps                                 3        3           0
    UserLocalConfigStore/apps                          11       11          11

As onze — e SÓ as onze — ocorrências de `UseSteamControllerConfig` estão na
árvore ``UserLocalConfigStore/apps``, que é justamente a que o
`e_a_arvore_canonica` recusa. **Cada chave tem a sua árvore viva**, e "canônica"
é uma propriedade do par (chave, arquivo), não do arquivo. Por isso este módulo
não confia em caminho fixo: ele PROCURA a árvore viva e recusa escrever quando
não consegue prová-la.

AS DUAS RÉGUAS
--------------
A lição do `O PORTÃO PODE OLHAR PARA O LUGAR ERRADO` é que uma régua sozinha
mente com convicção. Aqui são duas, e elas medem coisas diferentes:

1. **estrutural** (`ler_arvores`) — navega os blocos e atribui cada chave ao
   appid e à árvore a que ela pertence;
2. **bruta** (`contar_chave_cru`) — conta as linhas da chave no arquivo inteiro
   com um regex que não sabe nada de aninhamento.

Se as duas discordarem, existe uma ocorrência que a navegação não soube
atribuir — e o módulo **recusa escrever** (`reguas_divergem`). Depois da
escrita, a régua estrutural relê o texto produzido e confere valor por valor
(`conferir_escrita`): escrever e acreditar é como o censo do wrapper passou uma
noite verde com o Pragmata quebrado.

O QUE O PRODUTO PODE PROMETER HONESTAMENTE
------------------------------------------
Só isto: **a ponte é construída quando a Steam está FECHADA.** A Steam regrava
o `localconfig.vdf` ao sair e engole qualquer edição feita por baixo — a mesma
disciplina do `apply_wrapper_to_all_games` e do `--apply-quiet` do guarda, e o
`sem_wrapper` já a tinha por escrito: *"assim que a Steam fechar — é o único
instante em que a reposição sobrevive"*. Com a Steam viva este módulo ADIA e
diz que adiou; com um JOGO aberto ele nem cogita (fechar a Steam ali mataria o
jogo). O instante certo já existe e já tem gatilho: o
`hefesto-steam-input-guard`, que acorda quando o `userdata` muda — isto é,
quando a Steam acabou de sair — e a cada 30 minutos como rede.

NENHUM APPID EMBARCADO
----------------------
Decisão dela, 14/08/2026: receita por appid dentro do produto deixa todo jogo
novo desprotegido. O que entra aqui é o MECANISMO; quais jogos entram na lista
é config da máquina dela (`steam_input_apps.txt`).

100% stdlib, como os vizinhos: o guarda o roda com o `python3` do sistema, sem
venv.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

try:  # importado como módulo do pacote (GUI/daemon/testes)
    from .steam_launch_options import (
        discover_vdfs,
        is_sandboxed_layout,
        parse_steam_input_allowlist,
        rotulo_do_jogo,
        steam_game_running,
        steam_input_allowlist_path,
        steam_running,
    )
except ImportError:  # pragma: no cover - executado como script avulso
    from steam_launch_options import (  # type: ignore[no-redef]
        discover_vdfs,
        is_sandboxed_layout,
        parse_steam_input_allowlist,
        rotulo_do_jogo,
        steam_game_running,
        steam_input_allowlist_path,
        steam_running,
    )

#: A chave por jogo. `"0"` é desligado; `"2"` é o "sempre ligado" que a própria
#: Steam escreve quando a pessoa marca a caixa em Propriedades > Controle.
CHAVE = "UseSteamControllerConfig"
_CHAVE_MIN = CHAVE.lower()
LIGADO = "2"
DESLIGADO = "0"

#: A chave global do Steam Input para PlayStation. Ela é IRMÃ da árvore viva
#: (mora no mesmo bloco que o `apps` que guarda o `UseSteamControllerConfig`),
#: e é a segunda âncora para achar essa árvore num arquivo que ainda não tem
#: nenhuma chave por jogo.
_PS_SUPPORT_GLOBAL = "steamcontroller_pssupport"

_PAR_RE = re.compile(r'^\s*"(?P<chave>[^"]*)"\s+"(?P<valor>.*)"\s*$')
_SO_CHAVE_RE = re.compile(r'^\s*"([^"]*)"\s*$')
#: Régua BRUTA: casa a linha da chave sem saber nada de aninhamento.
_CHAVE_CRUA_RE = re.compile(
    r'^\s*"' + CHAVE + r'"\s+"[^"]*"\s*$', re.IGNORECASE | re.MULTILINE
)
#: Decompõe a linha da chave para trocar SÓ o valor, preservando a indentação
#: e os tabs literais que a Steam usa entre chave e valor.
_LINHA_CHAVE_RE = re.compile(
    r'^(?P<prefixo>\s*"' + CHAVE + r'"\s+")(?P<valor>[^"]*)(?P<sufixo>"\s*)$',
    re.IGNORECASE,
)

# --- desfechos ------------------------------------------------------------

#: Ninguém da lista precisava de ponte.
PONTE_NADA = "nada_a_fazer"
#: A ponte foi construída (ou seria, em `dry_run`).
PONTE_LIGADA = "ligado"
#: Há um JOGO da Steam aberto — nada foi tocado.
PONTE_ADIADA_JOGO = "adiado_jogo_aberto"
#: A Steam está viva — a edição seria engolida na saída dela.
PONTE_ADIADA_STEAM = "adiado_steam_aberta"
#: As duas réguas discordaram, ou a árvore viva não se deixou provar.
PONTE_INCERTA = "nao_sei_onde_escrever"
#: Falha de escrita (disco, permissão).
PONTE_ERRO = "erro"

#: Motivos de pular UM appid.
JA_LIGADO = "ja_ligado"
#: Este vdf não conhece o appid em árvore `apps` nenhuma — a ponte não inventa
#: entrada de app que a Steam nunca criou.
JOGO_DESCONHECIDO = "jogo_desconhecido_neste_vdf"
REGUAS_DIVERGEM = "reguas_divergem"
ARVORE_DESCONHECIDA = "arvore_viva_desconhecida"
SANDBOX = "sandbox"


@dataclass(frozen=True)
class ArvoreApps:
    """Um dos blocos `apps` do arquivo, e o que ele guarda desta chave."""

    #: Caminho de blocos até o próprio `apps`, ex.: `UserLocalConfigStore/apps`.
    caminho: str
    #: Caminho do bloco PAI — onde a irmã global é procurada.
    pai: str = ""
    #: appid -> (valor da chave, índice da linha em que ela está).
    chaves: dict[str, tuple[str, int]] = field(default_factory=dict)
    #: appid -> (índice da linha `{`, índice da linha `}`) de cada bloco de app.
    blocos: dict[str, tuple[int, int]] = field(default_factory=dict)
    #: Índice da linha `}` que fecha o PRÓPRIO bloco `apps`.
    fim: int = -1
    #: O bloco pai também guarda o `SteamController_PSSupport`?
    irma_do_pssupport: bool = False


def contar_chave_cru(texto: str) -> int:
    """RÉGUA BRUTA: quantas linhas da chave existem no arquivo inteiro.

    Não sabe de árvore, de appid nem de aninhamento — e é exatamente por isso
    que ela serve de contraprova para a régua estrutural.
    """
    return len(_CHAVE_CRUA_RE.findall(texto))


def ler_arvores(texto: str) -> list[ArvoreApps]:
    """RÉGUA ESTRUTURAL: todo bloco `apps` do arquivo, com o que há dentro.

    Devolve uma `ArvoreApps` por bloco `apps` encontrado, na ordem do arquivo.
    Read-only e tolerante: conteúdo fora do padrão é ignorado em silêncio (o
    `localconfig.vdf` guarda a biblioteca inteira dela e não é nosso).
    """
    linhas = texto.splitlines()
    pilha: list[str] = []
    pendente: str | None = None
    #: profundidade do bloco `apps` -> acumulador
    arvores_abertas: dict[int, ArvoreApps] = {}
    #: chaves escalares vistas em cada caminho de bloco (para achar a irmã)
    escalares: dict[str, set[str]] = {}
    #: (appid, profundidade, índice da linha `{`)
    app_atual: tuple[str, int, int] | None = None
    saida: list[ArvoreApps] = []

    for idx, cru in enumerate(linhas):
        linha = cru.strip()
        if not linha:
            continue
        if linha == "{":
            pilha.append(pendente if pendente is not None else "")
            pendente = None
            if pilha[-1].lower() == "apps":
                arvores_abertas[len(pilha)] = ArvoreApps(
                    caminho="/".join(pilha), pai="/".join(pilha[:-1])
                )
            elif (
                app_atual is None
                and len(pilha) >= 2
                and (len(pilha) - 1) in arvores_abertas
                and pilha[-2].lower() == "apps"
                and pilha[-1].isdigit()
            ):
                app_atual = (pilha[-1], len(pilha), idx)
            continue
        if linha == "}":
            if app_atual is not None and len(pilha) == app_atual[1]:
                arvore = arvores_abertas.get(len(pilha) - 1)
                if arvore is not None:
                    arvore.blocos[app_atual[0]] = (app_atual[2], idx)
                app_atual = None
            fechada = arvores_abertas.pop(len(pilha), None)
            if fechada is not None:
                saida.append(
                    ArvoreApps(
                        caminho=fechada.caminho,
                        pai=fechada.pai,
                        chaves=fechada.chaves,
                        blocos=fechada.blocos,
                        fim=idx,
                    )
                )
            if pilha:
                pilha.pop()
            pendente = None
            continue
        par = _PAR_RE.match(cru)
        if par is not None:
            pendente = None
            chave = par.group("chave").lower()
            escalares.setdefault("/".join(pilha), set()).add(chave)
            if (
                chave == _CHAVE_MIN
                and app_atual is not None
                and len(pilha) == app_atual[1]
            ):
                arvore = arvores_abertas.get(len(pilha) - 1)
                if arvore is not None:
                    arvore.chaves[app_atual[0]] = (par.group("valor"), idx)
            continue
        so_chave = _SO_CHAVE_RE.match(cru)
        if so_chave is not None:
            pendente = so_chave.group(1)
    # A irmã global só se decide DEPOIS de ler o arquivo inteiro: no vdf dela o
    # `SteamController_PSSupport` aparece DUAS linhas ABAIXO do `}` que fecha a
    # árvore viva, e decidir na abertura do bloco daria sempre "não" — o tipo
    # de detalhe de ordem que faz um portão responder o contrário do que vê.
    return [
        ArvoreApps(
            caminho=a.caminho,
            pai=a.pai,
            chaves=a.chaves,
            blocos=a.blocos,
            fim=a.fim,
            irma_do_pssupport=_PS_SUPPORT_GLOBAL in escalares.get(a.pai, set()),
        )
        for a in saida
    ]


def arvore_viva(arvores: Sequence[ArvoreApps]) -> ArvoreApps | None:
    """Qual dos blocos `apps` a Steam usa PARA ESTA CHAVE, ou `None`.

    Duas âncoras, nesta ordem:

    1. **a chave em pessoa** — a árvore que já guarda `UseSteamControllerConfig`
       é a árvore viva, por definição. Foi assim que a medição de 19/08/2026
       derrubou a suposição de que a âncora das `LaunchOptions` valeria aqui;
    2. **a irmã** — num arquivo sem nenhuma chave por jogo (perfil recém-criado),
       vale o bloco `apps` cujo PAI guarda o `SteamController_PSSupport`, o
       equivalente global desta mesma chave.

    Duas árvores com a chave, ou nenhuma âncora, devolvem `None`: escrever no
    escuro é justamente o que este módulo existe para não fazer.
    """
    com_a_chave = [a for a in arvores if a.chaves]
    if len(com_a_chave) == 1:
        return com_a_chave[0]
    if com_a_chave:
        return None
    irmas = [a for a in arvores if a.irma_do_pssupport]
    if len(irmas) == 1:
        return irmas[0]
    return None


def conferir_reguas(texto: str, arvores: Sequence[ArvoreApps]) -> str | None:
    """As duas réguas concordam? Devolve o motivo da divergência, ou `None`."""
    estrutural = sum(len(a.chaves) for a in arvores)
    if estrutural != contar_chave_cru(texto):
        return REGUAS_DIVERGEM
    return None


def _linha_ligada(cru: str) -> str:
    """A mesma linha, com o valor trocado para `LIGADO`."""
    m = _LINHA_CHAVE_RE.match(cru)
    if m is None:  # pragma: no cover - só chega aqui linha que o parser casou
        return cru
    return m.group("prefixo") + LIGADO + m.group("sufixo")


def ligar_no_texto(
    texto: str, appids: Sequence[str]
) -> tuple[str, list[str], list[tuple[str, str]]]:
    """Garante `UseSteamControllerConfig = 2` para `appids`. Função PURA.

    Três casos, e o produto cobre os três — a lista tem de valer para o jogo
    que a Steam nunca tocou tanto quanto para o que ela já desligou:

    - a chave existe e está em `"0"`: troca o valor, preservando a linha;
    - o bloco do app existe sem a chave: insere a linha antes do `}` do bloco;
    - o app nem tem bloco: cria o bloco no fim da árvore viva.

    Devolve ``(texto_novo, ligados, [(appid, motivo_pulado), ...])``. Nada é
    escrito quando as réguas divergem ou a árvore viva não se prova — nesse
    caso TODOS os appids saem pulados, com o motivo.
    """
    alvos = [str(a).strip() for a in appids if str(a).strip()]
    if not alvos:
        return texto, [], []
    arvores = ler_arvores(texto)
    divergencia = conferir_reguas(texto, arvores)
    if divergencia is not None:
        return texto, [], [(a, divergencia) for a in alvos]
    viva = arvore_viva(arvores)
    if viva is None:
        return texto, [], [(a, ARVORE_DESCONHECIDA) for a in alvos]

    #: Todo appid que este vdf conhece, em QUALQUER das suas árvores `apps`.
    #: É a prova de que a Steam já viu o jogo — e o limite do que a ponte
    #: inventa. Um appid que o arquivo inteiro desconhece (erro de digitação na
    #: lista, jogo de outra conta) sai pulado em vez de virar um bloco fantasma:
    #: a lista é o gesto dela, mas escrever entrada de app que a Steam nunca
    #: criou é passar de "obedecer à lista" para "inventar biblioteca".
    #: A árvore canônica das `LaunchOptions` serve de prova aqui mesmo quando a
    #: viva ainda não tem bloco nenhum do jogo — é o caso do jogo recém-instalado.
    conhecidos = {appid for arvore in arvores for appid in arvore.blocos}

    linhas = texto.splitlines(keepends=True)
    trocas: dict[int, str] = {}
    #: índice da linha ANTES da qual inserir -> linhas novas
    insercoes: dict[int, list[str]] = {}
    ligados: list[str] = []
    pulados: list[tuple[str, str]] = []

    for appid in alvos:
        atual = viva.chaves.get(appid)
        if atual is not None:
            valor, idx = atual
            if valor.strip() != DESLIGADO:
                pulados.append((appid, JA_LIGADO))
                continue
            corpo = linhas[idx].rstrip("\r\n")
            eol = linhas[idx][len(corpo):] or "\n"
            trocas[idx] = _linha_ligada(corpo) + eol
            ligados.append(appid)
            continue
        bloco = viva.blocos.get(appid)
        if bloco is not None:
            abre, fecha = bloco
            recuo, eol = _recuo_de(linhas, abre)
            insercoes.setdefault(fecha, []).append(
                f'{recuo}\t"{CHAVE}"\t\t"{LIGADO}"{eol}'
            )
            ligados.append(appid)
            continue
        if appid not in conhecidos:
            pulados.append((appid, JOGO_DESCONHECIDO))
            continue
        recuo, eol = _recuo_de(linhas, viva.fim)
        insercoes.setdefault(viva.fim, []).extend([
            f'{recuo}\t"{appid}"{eol}',
            f"{recuo}\t{{{eol}",
            f'{recuo}\t\t"{CHAVE}"\t\t"{LIGADO}"{eol}',
            f"{recuo}\t}}{eol}",
        ])
        ligados.append(appid)

    if not trocas and not insercoes:
        return texto, ligados, pulados
    saida: list[str] = []
    for idx, cru in enumerate(linhas):
        for nova in insercoes.get(idx, ()):
            saida.append(nova)
        saida.append(trocas.get(idx, cru))
    return "".join(saida), ligados, pulados


def _recuo_de(linhas: Sequence[str], idx: int) -> tuple[str, str]:
    """(indentação, quebra de linha) da linha `idx` — para escrever igual aos vizinhos."""
    corpo = linhas[idx].rstrip("\r\n")
    eol = linhas[idx][len(corpo):] or "\n"
    return corpo[: len(corpo) - len(corpo.lstrip())], eol


def conferir_escrita(
    original: str, novo: str, ligados: Sequence[str]
) -> str | None:
    """SEGUNDA passada, independente da que escreveu. Motivo do erro, ou `None`.

    Relê o texto PRODUZIDO com a régua estrutural e exige três coisas: a árvore
    viva continua provável, todo appid que dizemos ter ligado está de fato em
    `"2"` nela, e a contagem bruta subiu exatamente o número de chaves novas.
    Escrever e acreditar no próprio relatório é o defeito do censo que passou a
    noite verde com o jogo dela quebrado.
    """
    arvores = ler_arvores(novo)
    divergencia = conferir_reguas(novo, arvores)
    if divergencia is not None:
        return divergencia
    viva = arvore_viva(arvores)
    if viva is None:
        return ARVORE_DESCONHECIDA
    antes = ler_arvores(original)
    viva_antes = arvore_viva(antes)
    tinham_chave = set(viva_antes.chaves) if viva_antes is not None else set()
    for appid in ligados:
        valor = viva.chaves.get(appid)
        if valor is None or valor[0].strip() != LIGADO:
            return f"nao_ligou:{appid}"
    novas = len([a for a in ligados if a not in tinham_chave])
    if contar_chave_cru(novo) - contar_chave_cru(original) != novas:
        return REGUAS_DIVERGEM
    return None


@dataclass(frozen=True)
class Pendencia:
    """Um jogo da lista de exceções cuja ponte ainda não está de pé."""

    appid: str
    rotulo: str
    #: Valor atual da chave; `None` = o jogo nem tem a chave no arquivo.
    valor: str | None
    vdf: str


@dataclass(frozen=True)
class Estado:
    """Fotografia read-only: a lista dela contra o que o vdf realmente diz."""

    #: appids da lista de exceções.
    lista: list[str] = field(default_factory=list)
    #: os que já estão ligados — a ponte de pé.
    ligados: list[str] = field(default_factory=list)
    #: os que a lista promete e o vdf desmente.
    pendentes: list[Pendencia] = field(default_factory=list)
    #: vdfs pulados por inteiro (Flatpak/Snap: sandbox).
    sandbox: list[str] = field(default_factory=list)
    #: vdfs em que as réguas discordaram ou a árvore não se provou.
    incertos: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    steam_aberta: bool = False
    jogo_aberto: bool = False

    def frase(self) -> str:
        """Uma linha para a tela. Nomeia o jogo, nunca só conta."""
        if not self.lista:
            return "Nenhum jogo na lista de exceções do Steam Input."
        if not self.pendentes:
            return (
                f"{len(self.ligados)} jogo(s) da lista com o Steam Input "
                "ligado — a ponte está de pé."
            )
        nomes = ", ".join(p.rotulo for p in self.pendentes[:3])
        resto = (
            f" e mais {len(self.pendentes) - 3}" if len(self.pendentes) > 3 else ""
        )
        if self.jogo_aberto:
            quando = (
                " Ligo assim que o jogo e a Steam fecharem — não mexo agora "
                "porque fechar a Steam com um jogo aberto mata o jogo."
            )
        elif self.steam_aberta:
            quando = (
                " Ligo assim que a Steam fechar (com ela viva a edição é "
                "engolida na saída dela)."
            )
        else:
            quando = " Posso ligar agora."
        return (
            f"Na sua lista de exceções, mas com o Steam Input DESLIGADO: "
            f"{nomes}{resto}.{quando}"
        )

    def como_dicionario(self) -> dict[str, object]:
        return {
            "lista": list(self.lista),
            "ligados": list(self.ligados),
            "pendentes": [
                {
                    "appid": p.appid,
                    "rotulo": p.rotulo,
                    "valor": p.valor,
                    "vdf": p.vdf,
                }
                for p in self.pendentes
            ],
            "sandbox": list(self.sandbox),
            "incertos": list(self.incertos),
            "erros": list(self.erros),
            "steam_aberta": self.steam_aberta,
            "jogo_aberto": self.jogo_aberto,
            "frase": self.frase(),
        }


def ler_allowlist(config_home: Path | None = None) -> list[str]:
    """Os appids da lista de exceções dela. Lista vazia se o arquivo não existe.

    A leitura é a MESMA do guarda e do daemon (`parse_steam_input_allowlist`
    sobre `steam_input_allowlist_path`) — duas leituras diferentes do mesmo
    arquivo é como se constrói uma discordância silenciosa.
    """
    try:
        return parse_steam_input_allowlist(
            steam_input_allowlist_path(config_home).read_text(encoding="utf-8")
        )
    except OSError:
        return []


def estado_da_ponte(
    home: Path | None = None,
    vdfs: Sequence[Path] | None = None,
    *,
    allowlist: Sequence[str] | None = None,
    config_home: Path | None = None,
) -> Estado:
    """Lê (e só lê) o que a lista promete e o que o vdf entrega.

    Read-only de propósito, como o censo do wrapper: roda com a Steam ABERTA,
    porque só a ESCRITA é que exige a Steam fechada.
    """
    alvos = (
        [str(a).strip() for a in allowlist if str(a).strip()]
        if allowlist is not None
        else ler_allowlist(config_home)
    )
    ligados: list[str] = []
    pendentes: list[Pendencia] = []
    sandbox: list[str] = []
    incertos: list[str] = []
    erros: list[str] = []
    vistos: set[str] = set()
    for vdf in vdfs if vdfs is not None else discover_vdfs(home):
        if is_sandboxed_layout(vdf):
            sandbox.append(str(vdf))
            continue
        try:
            texto = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            erros.append(f"{vdf}: {exc}")
            continue
        arvores = ler_arvores(texto)
        if conferir_reguas(texto, arvores) is not None:
            incertos.append(str(vdf))
            continue
        viva = arvore_viva(arvores)
        if viva is None:
            incertos.append(str(vdf))
            continue
        conhecidos = {appid for arvore in arvores for appid in arvore.blocos}
        for appid in alvos:
            atual = viva.chaves.get(appid)
            if atual is not None and atual[0].strip() != DESLIGADO:
                if appid not in vistos:
                    vistos.add(appid)
                    ligados.append(appid)
                continue
            if appid in vistos:
                continue
            if appid not in conhecidos:
                # Jogo que este vdf desconhece (não instalado nesta conta, ou
                # um número errado na lista). Não é pendência: seria o D-32 de
                # volta — pré-voo dizendo "precisa" para sempre e a Steam dela
                # sendo fechada para não mudar byte nenhum.
                continue
            vistos.add(appid)
            pendentes.append(
                Pendencia(
                    appid=appid,
                    rotulo=rotulo_do_jogo(appid, home),
                    valor=atual[0] if atual is not None else None,
                    vdf=str(vdf),
                )
            )
    return Estado(
        lista=alvos,
        ligados=ligados,
        pendentes=pendentes,
        sandbox=sandbox,
        incertos=incertos,
        erros=erros,
        steam_aberta=steam_running(),
        jogo_aberto=steam_game_running(),
    )


def garantir_ponte(
    home: Path | None = None,
    vdfs: Sequence[Path] | None = None,
    *,
    allowlist: Sequence[str] | None = None,
    config_home: Path | None = None,
    dry_run: bool = False,
) -> tuple[str, Estado, list[dict[str, str]]]:
    """Constrói a ponte para os jogos da lista, ou ADIA dizendo por quê.

    Devolve ``(status, estado, detalhe)``. `detalhe` é uma linha por appid
    tocado ou pulado: ``{"vdf", "appid", "desfecho"}``.

    A ordem dos portões não é negociável, e é a mesma do
    `apply_wrapper_to_all_games`: **jogo aberto antes de tudo** (fechar a Steam
    ali mataria o jogo e o progresso não salvo), depois Steam aberta (a edição
    seria engolida quando ela sair), e só então a escrita — com backup
    `.bak.steam-input-ponte-<ts>` ao lado, `tmp` + `replace`, e a conferência
    da segunda régua antes de trocar o arquivo.
    """
    estado = estado_da_ponte(
        home, vdfs, allowlist=allowlist, config_home=config_home
    )
    detalhe: list[dict[str, str]] = []
    if not estado.pendentes:
        return PONTE_NADA, estado, detalhe
    if not dry_run and estado.jogo_aberto:
        return PONTE_ADIADA_JOGO, estado, detalhe
    if not dry_run and estado.steam_aberta:
        return PONTE_ADIADA_STEAM, estado, detalhe

    alvos = [p.appid for p in estado.pendentes]
    houve_incerteza = False
    houve_erro = False
    ligou = False
    for vdf in vdfs if vdfs is not None else discover_vdfs(home):
        if is_sandboxed_layout(vdf):
            detalhe.append({"vdf": str(vdf), "appid": "", "desfecho": SANDBOX})
            continue
        try:
            original = vdf.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            # ValueError cobre UnicodeDecodeError. Sem `errors="replace"`: este
            # arquivo é REESCRITO adiante, e trocar bytes por U+FFFD corromperia
            # a biblioteca inteira dela.
            detalhe.append({"vdf": str(vdf), "appid": "", "desfecho": str(exc)})
            houve_erro = True
            continue
        novo, ligados, pulados = ligar_no_texto(original, alvos)
        for appid, motivo in pulados:
            detalhe.append({"vdf": str(vdf), "appid": appid, "desfecho": motivo})
            if motivo in (REGUAS_DIVERGEM, ARVORE_DESCONHECIDA):
                houve_incerteza = True
        if not ligados:
            continue
        problema = conferir_escrita(original, novo, ligados)
        if problema is not None:
            detalhe.append({"vdf": str(vdf), "appid": "", "desfecho": problema})
            houve_incerteza = True
            continue
        if not dry_run:
            try:
                backup = vdf.with_name(
                    vdf.name + f".bak.steam-input-ponte-{int(time.time())}"
                )
                shutil.copy2(vdf, backup)
                tmp = vdf.with_name(vdf.name + ".hefesto-ponte-tmp")
                tmp.write_text(novo, encoding="utf-8")
                shutil.copymode(vdf, tmp)
                tmp.replace(vdf)
            except OSError as exc:
                detalhe.append({"vdf": str(vdf), "appid": "", "desfecho": str(exc)})
                houve_erro = True
                continue
        ligou = True
        for appid in ligados:
            detalhe.append({"vdf": str(vdf), "appid": appid, "desfecho": PONTE_LIGADA})
    if ligou:
        return PONTE_LIGADA, estado, detalhe
    if houve_erro:
        return PONTE_ERRO, estado, detalhe
    if houve_incerteza:
        return PONTE_INCERTA, estado, detalhe
    return PONTE_NADA, estado, detalhe


# --------------------------------------------------------------------------
# CLI — o guarda consome `--ligar`; `--estado` (JSON) é para a GUI e o doctor.
# --------------------------------------------------------------------------

#: Códigos de saída. O `3` do adiamento existe pelo mesmo motivo do
#: `sentinela_do_wrapper`: adiar é o caso NORMAL (ela está jogando), e um
#: oneshot do systemd trataria qualquer != 0 como unit FAILED.
_SAIDA = {
    PONTE_NADA: 0,
    PONTE_LIGADA: 0,
    PONTE_ADIADA_JOGO: 3,
    PONTE_ADIADA_STEAM: 3,
    PONTE_INCERTA: 4,
    PONTE_ERRO: 1,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="steam_input_ponte",
        description=(
            "Garante o Steam Input LIGADO para os jogos da lista de exceções "
            "(a lista deixa de só preservar e passa a construir a ponte). "
            "Sem argumentos, --estado."
        ),
    )
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--estado", action="store_true", help="o estado em JSON (default)")
    grupo.add_argument(
        "--ligar",
        action="store_true",
        help="liga o Steam Input dos jogos da lista (exige a Steam fechada)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="não escreve nada (com --ligar)"
    )
    parser.add_argument(
        "--vdf",
        action="append",
        type=Path,
        default=None,
        metavar="ARQUIVO",
        help="usa este localconfig.vdf em vez de procurar (repetível)",
    )
    args = parser.parse_args(argv)

    if args.ligar:
        status, estado, detalhe = garantir_ponte(vdfs=args.vdf, dry_run=args.dry_run)
        print(f"[steam-input-ponte] resultado={status}")
        for item in detalhe:
            alvo = item["appid"] or item["vdf"]
            print(f"[steam-input-ponte] {alvo}: {item['desfecho']}")
        if status != PONTE_LIGADA:
            # A frase descreve o estado de ANTES da escrita. Depois de ligar,
            # repeti-la seria dizer "posso ligar agora" sobre um jogo que
            # acabou de ser ligado — mentirinha pequena, da família da que fez
            # a janela cantar "Steam Input desligado" sobre um no-op.
            print(f"[steam-input-ponte] {estado.frase()}")
        return _SAIDA.get(status, 1)

    estado = estado_da_ponte(vdfs=args.vdf)
    print(json.dumps(estado.como_dicionario(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
