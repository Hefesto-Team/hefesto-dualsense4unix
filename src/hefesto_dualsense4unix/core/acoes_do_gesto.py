#!/usr/bin/env python3
"""O QUE CADA GESTO DO CONTROLE FAZ — o vocabulário, o de fábrica e a tabela.

OS-GESTOS-DO-CONTROLE-FAZEM-O-QUE-DIZEM-01 (29/09/2026). A tabela «Os gestos
do controle» da aba Navegação oferecia trocar o que cada gesto faz, e o daemon
tinha um ato cravado por gesto e nenhum lugar de onde ler outro: a lista
aceitava o clique, mostrava a escolha e não mudava o controle. A pergunta de produto teve a
resposta medida: os
seis gestos funcionavam, e a lista ao lado de cada um era desenho sem dono.
<!-- noqa-acento: citação literal -->

Aqui mora o que os três lados usam, e só isto:

* :data:`GESTOS` — os seis, com o nome que o ``HotkeyManager`` dá a cada um e
  as peças do mapa que a tela desenha;
* :data:`ACOES` — token para (grupo, rótulo), a lista que a tela oferece;
* :data:`PADRAO` — o que cada gesto faz de fábrica, que é o que o daemon fazia
  antes de a tabela existir;
* :func:`tabela` — o de fábrica com a declaração do ``maquina.json`` por cima.
  **É a única leitura**: a tela pinta por ela e o daemon despacha por ela;
* :func:`conferir_o_script` — as guardas do arquivo escolhido, que a tela
  confere ao escolher e o daemon confere de novo ao rodar.

A TABELA É DA MÁQUINA, NÃO DO PERFIL (``D-2909-OS-GESTOS-SAO-DA-MAQUINA``,
decidida pelo usuário em 29/09, «Do computador»): o PS + cima troca de perfil, e um
gesto cujo ato mudasse com o perfil mudaria debaixo do dedo de quem o usa; e
um perfil importado de outra pessoa não pode trazer um script para rodar.

O «— NADA —» VOLTOU NOS SEIS GESTOS (resposta de 01/10, ~23h55, a §14 da
sprint): com visitas, o PS sozinho abria a Steam por cima do jogo, e calar o
gesto era o que ela tentou fazer duas vezes. No PS + L3 e no PS + R3 ele tira
a reescrita do perfil do jogo por um combo errado.

Puro como o ``acoes_de_botao``: sem daemon, sem GTK, sem disco (a não ser o
``stat`` do script, que é a pergunta que ele existe para fazer).
"""
from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.core import acoes_de_botao as _botao


@dataclass(frozen=True)
class Gesto:
    """Um dos seis gestos: a chave do ``maquina.json`` e quem o detecta."""

    chave: str
    numero: int
    nome_no_gerente: str
    botoes: tuple[str, ...]
    pecas: tuple[str, ...]


GESTO_DO_PS = "ps"

GESTOS: dict[str, Gesto] = {
    g.chave: g
    for g in (
        Gesto("ps_options", 1, "gamemode", ("ps", "options"), ("ps", "options")),
        Gesto("ps_cima", 2, "next", ("ps", "dpad_up"), ("ps", "dpad_up")),
        Gesto("ps_baixo", 3, "prev", ("ps", "dpad_down"), ("ps", "dpad_down")),
        Gesto("ps_r3", 4, "ponte", ("ps", "r3"), ("ps", "stick_r")),
        Gesto("ps_l3", 5, "mascara", ("ps", "l3"), ("ps", "stick_l")),
        Gesto(GESTO_DO_PS, 6, "ps_solo", ("ps",), ("ps",)),
    )
}

BOTOES_DO_GESTO_NOVO: tuple[str, ...] = ("cross", "circle", "square", "triangle", "create")
_PECA_DO_BOTAO: dict[str, str] = {"create": "share"}

GESTOS_NOVOS: dict[str, Gesto] = {
    f"ps_{b}": Gesto(f"ps_{b}", 7 + i, f"ps_{b}", ("ps", b), ("ps", _PECA_DO_BOTAO.get(b, b)))
    for i, b in enumerate(BOTOES_DO_GESTO_NOVO)
}

TODOS_OS_GESTOS: dict[str, Gesto] = {**GESTOS, **GESTOS_NOVOS}

BOTOES_PROIBIDOS: tuple[str, ...] = ("l1", "r1", "l2", "r2", "dpad_left", "dpad_right")

BOTOES_DA_ESCOLHA: tuple[str, ...] = (
    *BOTOES_DO_GESTO_NOVO,
    *(g.botoes[1] for g in GESTOS.values() if g.chave != GESTO_DO_PS),
    *BOTOES_PROIBIDOS,
)

PERFIL_SEGUINTE = "perfil_seguinte"
PERFIL_ANTERIOR = "perfil_anterior"
SUSPENDER = "suspender_mouse_e_teclado"
SAIR_DO_MODO_JOGO = "sair_do_modo_jogo"
MODO_SEGUINTE = "modo_seguinte"
MASCARA_SEGUINTE = "mascara_seguinte"
ABRIR_A_STEAM = "abrir_a_steam"
ABRIR_O_HEFESTO = "abrir_o_hefesto"
REINICIAR_O_SERVICO = "reiniciar_o_servico"
PARAR_O_SERVICO = "parar_o_servico"
SCRIPT = "script"
NADA = "nada"

GRUPO_PERFIL = "Perfil"
GRUPO_MOUSE_E_TECLADO = "Mouse e teclado"
GRUPO_MODO = "Modo"
GRUPO_MASCARA = "Máscara"
GRUPO_STEAM = "Modo Steam"
GRUPO_HEFESTO = "Hefesto"
GRUPO_COMANDO = _botao.GRUPO_COMANDO
GRUPO_NENHUM = _botao.GRUPO_NENHUM

ACOES: dict[str, tuple[str, str]] = {
    PERFIL_SEGUINTE: (GRUPO_PERFIL, "Próximo perfil"),
    PERFIL_ANTERIOR: (GRUPO_PERFIL, "Perfil anterior"),
    SUSPENDER: (GRUPO_MOUSE_E_TECLADO, "Suspender mouse e teclado"),
    SAIR_DO_MODO_JOGO: (GRUPO_MOUSE_E_TECLADO, _botao.rotulo(_botao.TOKEN_SAIR_DO_JOGO)),
    MODO_SEGUINTE: (GRUPO_MODO, "Próximo modo"),
    MASCARA_SEGUINTE: (GRUPO_MASCARA, "Próxima máscara"),
    ABRIR_A_STEAM: (GRUPO_STEAM, _botao.rotulo(_botao.TOKEN_STEAM)),
    ABRIR_O_HEFESTO: (GRUPO_HEFESTO, "Abrir o Hefesto"),
    REINICIAR_O_SERVICO: (GRUPO_HEFESTO, "Reiniciar o serviço"),
    PARAR_O_SERVICO: (GRUPO_HEFESTO, "Parar o serviço"),
    SCRIPT: (GRUPO_COMANDO, "Escolher um script…"),
    NADA: (GRUPO_NENHUM, _botao.rotulo(_botao.TOKEN_NADA)),
}

PADRAO: dict[str, str] = {
    "ps_options": SUSPENDER,
    "ps_cima": PERFIL_SEGUINTE,
    "ps_baixo": PERFIL_ANTERIOR,
    "ps_r3": MODO_SEGUINTE,
    "ps_l3": MASCARA_SEGUINTE,
    GESTO_DO_PS: ABRIR_A_STEAM,
}

SAIDAS_DE_EMERGENCIA: tuple[str, ...] = (MODO_SEGUINTE, SUSPENDER)

TETO_DO_SCRIPT_S = 60

MAXIMO_DO_CAMINHO = 4096

VARIAVEL_DO_JOGADOR = "HEFESTO_JOGADOR"
VARIAVEL_DO_TRANSPORTE = "HEFESTO_TRANSPORTE"


@dataclass(frozen=True)
class EscolhaDoGesto:
    """O que um gesto faz agora. ``declarada`` separa a escolha do usuário do de fábrica.

    O PS sozinho precisa da diferença: sem declaração, quem manda é o degrau
    antigo da máquina (``DaemonConfig.ps_button_action``, o do ambiente e do
    ``daemon.reload``), e não o de fábrica desta tabela.
    """

    faz: str
    script: str | None = None
    declarada: bool = False


def _declarados(maquina: Any) -> Mapping[str, Any]:
    if maquina is None:
        return {}
    if isinstance(maquina, Mapping):
        bruto = maquina.get("gestos")
    else:
        bruto = getattr(maquina, "gestos", None)
    return bruto if isinstance(bruto, Mapping) else {}


def _campo(declarado: Any, nome: str) -> Any:
    if isinstance(declarado, Mapping):
        return declarado.get(nome)
    return getattr(declarado, nome, None)


def tabela(maquina: Any) -> dict[str, EscolhaDoGesto]:
    """Gesto -> o que ele faz: o de fábrica com a declaração da máquina por cima.

    Os gestos novos entram quando declarados, e fazem «Nada» até alguém escolher.
    """
    declarados = _declarados(maquina)
    fora: dict[str, EscolhaDoGesto] = {}
    novos = {c: NADA for c in GESTOS_NOVOS if declarados.get(c) is not None}
    for chave, de_fabrica in {**PADRAO, **novos}.items():
        declarado = declarados.get(chave)
        faz = _campo(declarado, "faz") if declarado is not None else None
        if isinstance(faz, str) and faz in ACOES:
            script = _campo(declarado, "script") if faz == SCRIPT else None
            fora[chave] = EscolhaDoGesto(faz, script if isinstance(script, str) else None, True)
        else:
            fora[chave] = EscolhaDoGesto(de_fabrica)
    return fora


def removido(maquina: Any, chave: str) -> bool:
    """O gesto de fábrica que o usuário tirou da tabela (``removido: true`` no ``maquina.json``)."""
    declarado = _declarados(maquina).get(chave)
    return declarado is not None and _campo(declarado, "removido") is True


def gestos_ativos(maquina: Any) -> dict[str, Gesto]:
    """Os gestos com combo que valem agora: os de fábrica não removidos e os novos declarados.

    É a FONTE dos combos do detector (`HotkeyManager._combos_configurados`) e das linhas da
    tabela da tela. O PS sozinho não entra: ele não é combo, e o dono dele é a linha PS de
    «Os botões no computador».
    """
    declarados = _declarados(maquina)
    fora = {c: g for c, g in GESTOS.items() if c != GESTO_DO_PS and not removido(maquina, c)}
    fora.update({c: g for c, g in GESTOS_NOVOS.items() if declarados.get(c) is not None})
    return fora


def combos_ativos(maquina: Any) -> dict[str, tuple[str, ...]]:
    """Gesto -> os botões dele, só dos que valem agora (:func:`gestos_ativos`)."""
    return {c: g.botoes for c, g in gestos_ativos(maquina).items()}


def botao_livre(maquina: Any, botao: str) -> bool:
    """O botão pode virar gesto novo agora? Não se for proibido, nem se um gesto ativo o usa."""
    if botao in BOTOES_PROIBIDOS or botao not in BOTOES_DA_ESCOLHA:
        return False
    return all(botao not in g.botoes for g in gestos_ativos(maquina).values())


def gesto_do_botao(botao: str) -> str | None:
    """A chave do gesto que o PS + ``botao`` forma: o de fábrica ou o novo; ``None`` se não há."""
    for chave, g in TODOS_OS_GESTOS.items():
        if g.botoes == ("ps", botao):
            return chave
    return None


def rotulo(token: str) -> str:
    """O texto da tela para o token; o token cru se ele não existir (defeito à vista)."""
    par = ACOES.get(token)
    return par[1] if par else token


def nome_do_script(caminho: str | None) -> str:
    """O nome do arquivo, que é o rótulo da opção do script escolhido."""
    return os.path.basename(caminho or "") or rotulo(SCRIPT)


def rotulo_da_escolha(escolha: EscolhaDoGesto) -> str:
    """O que a lista mostra: o rótulo do ato, ou o nome do arquivo do script."""
    if escolha.faz == SCRIPT and escolha.script:
        return nome_do_script(escolha.script)
    return rotulo(escolha.faz)


_POR_ROTULO: dict[str, str] = {r: t for t, (_g, r) in ACOES.items()}
if len(_POR_ROTULO) != len(ACOES):  # pragma: no cover
    raise SystemExit("ERRO em acoes_do_gesto: dois tokens com o mesmo rótulo.")


def token_do_rotulo(texto: str) -> str | None:
    """O token do texto que a lista mandou; ``None`` quando não é um rótulo fixo."""
    return _POR_ROTULO.get((texto or "").strip())


def por_grupo() -> list[tuple[str, list[str]]]:
    """``[(grupo, [rótulo, …]), …]`` na ordem da tela — o que o gerador desenha."""
    fora: list[tuple[str, list[str]]] = []
    for _token, (grupo, texto) in ACOES.items():
        if fora and fora[-1][0] == grupo:
            fora[-1][1].append(texto)
        else:
            fora.append((grupo, [texto]))
    return fora


def saidas_sem_gesto(escolhas: Mapping[str, EscolhaDoGesto]) -> list[str]:
    """As saídas de emergência que nenhum gesto faz, em tokens."""
    feitas = {e.faz for e in escolhas.values()}
    return [s for s in SAIDAS_DE_EMERGENCIA if s not in feitas]


SEM_O_ARQUIVO = "o arquivo não existe mais"
NAO_E_ARQUIVO = "não é um arquivo"
DE_OUTRO_DONO = "o arquivo é de outra pessoa"
GRAVAVEL_POR_OUTROS = "outras pessoas podem alterar o arquivo"
PASTA_GRAVAVEL = "outras pessoas podem trocar o arquivo na pasta dele"
SEM_EXECUCAO = "o arquivo não tem permissão de execução"
SEM_O_INTERPRETADOR = "o arquivo não começa com #!"
CAMINHO_INVALIDO = "o caminho não é absoluto"


def conferir_o_script(caminho: str, *, uid: int | None = None) -> str | None:
    """``None`` quando o arquivo pode rodar; senão, o motivo em uma frase."""
    if not isinstance(caminho, str) or "\0" in caminho or not caminho:
        return CAMINHO_INVALIDO
    if not os.path.isabs(caminho) or len(caminho) > MAXIMO_DO_CAMINHO:
        return CAMINHO_INVALIDO
    dono = os.getuid() if uid is None else uid
    real = os.path.realpath(caminho)
    try:
        st = os.stat(real)
    except OSError:
        return SEM_O_ARQUIVO
    if not stat.S_ISREG(st.st_mode):
        return NAO_E_ARQUIVO
    if st.st_uid != dono:
        return DE_OUTRO_DONO
    if st.st_mode & 0o022:
        return GRAVAVEL_POR_OUTROS
    try:
        pasta = os.stat(os.path.dirname(real))
    except OSError:
        return SEM_O_ARQUIVO
    if pasta.st_mode & 0o022 or pasta.st_uid not in (dono, 0):
        return PASTA_GRAVAVEL
    if not st.st_mode & stat.S_IXUSR:
        return SEM_EXECUCAO
    try:
        with open(real, "rb") as fh:
            inicio = fh.read(2)
    except OSError:
        return SEM_O_ARQUIVO
    if inicio != b"#!":
        return SEM_O_INTERPRETADOR
    return None


__all__ = [
    "ACOES",
    "BOTOES_DA_ESCOLHA",
    "BOTOES_DO_GESTO_NOVO",
    "BOTOES_PROIBIDOS",
    "GESTOS",
    "GESTOS_NOVOS",
    "GESTO_DO_PS",
    "PADRAO",
    "SAIDAS_DE_EMERGENCIA",
    "TETO_DO_SCRIPT_S",
    "TODOS_OS_GESTOS",
    "EscolhaDoGesto",
    "Gesto",
    "botao_livre",
    "combos_ativos",
    "conferir_o_script",
    "gesto_do_botao",
    "gestos_ativos",
    "nome_do_script",
    "por_grupo",
    "removido",
    "rotulo",
    "rotulo_da_escolha",
    "saidas_sem_gesto",
    "tabela",
    "token_do_rotulo",
]
