"""O desenho da aba Experimental (a 07): extensões, lançadores e as janelas deles.

Só desenho. O que o produto pinta por cima (nomes dos controles, contagens,
jogos de cada lançador) entra pelos endereços `data-campo`; aqui moram os dados
de exemplo e a forma de cada peça.
"""
# ruff: noqa: E501
from __future__ import annotations

import functools
import itertools
import json
import math
import pathlib
import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from html.parser import HTMLParser
from typing import Any, NamedTuple

from hefesto_dualsense4unix.interface.desenho_dos_lancadores import (
    CONFIGURAR_ROTULO,
    IDENTIFICAR_ROTULO,
    _a,
    _e,
)

_PASTA = pathlib.Path(__file__).with_name("experimental")

ROTULO_DA_TIRA = "Experimental"

CSS = (_PASTA / "experimental.css").read_text(encoding="utf-8")
SCRIPT = (_PASTA / "comportamento.js").read_text(encoding="utf-8")
_ICONES: dict[str, str] = json.loads((_PASTA / "icones.json").read_text(encoding="utf-8"))

BOTOES = (
    ("identificar-lancador", IDENTIFICAR_ROTULO, "#"),
    ("criar-perfil-para-um-jogo", "Criar perfis", "#escolher-jogo"),
    ("configurar-lancador", CONFIGURAR_ROTULO, "#lanc-conf"),
)


class Fila(NamedTuple):
    chave: str
    nome: str
    jogos: str
    achado: bool
    configurar: str
    virou: str = ""


LANCADORES = (
    Fila("steam", "Steam", "48 jogos", True, "#lanc-conf"),
    Fila("lutris", "Lutris", "12 jogos", True, "#lanc-conf"),
    Fila("heroic", "Heroic (Epic · GOG)", "", False, "#lanc-conf"),
    Fila("flatpak", "Flatpak", "", False, "#lanc-conf"),
    Fila("retroarch", "RetroArch", "", False, "#lanc-conf",
         virou="https://github.com/Hefesto-Team/hefesto-mod-retroarch"),
)

FRASE_DO_QUE_VIROU = "Virou extensão:"
DICA_DO_QUE_VIROU = "Para seguir com ele, instale de"


class Extensao(NamedTuple):
    chave: str
    nome: str
    dica: str
    janela: str
    cor: str = "purple"
    versao: str = "0.1.0"
    selo: str = "Oficial"
    ligada: bool = True
    menu: str = ""
    processo: str = ""
    porque: str = ""
    pede: str = ""


PROCESSO = {"ligando": ("Ligando", "amarelo"), "voltando": ("Voltando", "amarelo"),
            "parou": ("Caiu", "vermelho"), "recusada": ("Recusada", "vermelho"),
            "desligada": ("Desligada", "mudo")}
DICA_DE_TENTAR = "Desligue e ligue para tentar de novo."
ROTULO_DO_SIM = "Aceitar e ligar"


def processo_de(ligada: bool, estado: str) -> str:
    """A chave de ``PROCESSO`` de uma extensão: o registro diz se ligou, o supervisor se roda.

    Ligada no registro e ainda ``desligada`` no supervisor é a que o serviço não subiu: «Ligando».
    """
    if not ligada:
        return "desligada"
    return "ligando" if estado == "desligada" else (estado if estado in PROCESSO else "")


EXTENSOES = (
    Extensao("kytyps5", "KytyPS5", "Os jogos do KytyPS5 na fila dos lançadores, com o perfil de cada um",
             "#modificacao", "cyan"),  # (noqa-acento)
    Extensao("exemplo", "Minha extensão", "Uma extensão com opções em três grupos",
             "#modificacao"),  # (noqa-acento)
)


def _icone(chave: str, tamanho: int = 16) -> str:
    """O ícone da chave; extensão que o desenho não conhece ganha o genérico, nunca um erro."""
    return (f'<svg viewBox="0 0 24 24" width="{tamanho}" height="{tamanho}" fill="none" '
            f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
            f'stroke-linejoin="round">{_ICONES.get(chave) or _ICONES["extensao"]}</svg>')  # (noqa-acento)


def _engrenagem() -> str:
    return (f'<svg viewBox="0 0 24 24" width="15" height="15" fill="none" '
            f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{_ICONES["engrenagem"]}</svg>')


def botao_ativo(gesto: str, achado: bool) -> bool:
    """O «Identificar» acende para quem não foi achado; os outros dois, para quem foi."""
    return (gesto == "identificar-lancador") != achado


def _botao(gesto: str, rotulo: str, destino: str, chave: str, ativo: bool) -> str:
    """Um dos três botões da fila. O apagado fica à vista sem gesto, sem destino e sem chave.

    O ``pointer-events:none`` só barra o mouse: o Enter num botão focado e o ``click()`` da ponte
    ainda o disparavam. O que não tem gesto não tem o que disparar (o mesmo do ⋮ apagado).
    """
    if not ativo:
        return f'<span class="btn mini apagado" aria-disabled="true">{rotulo}</span>'
    if gesto == "identificar-lancador":
        return f'<button class="btn mini" data-gesto="{gesto}" data-v="{_a(chave)}">{rotulo}</button>'
    return f'<a class="btn mini" href="{destino}" data-gesto="{gesto}" data-v="{_a(chave)}">{rotulo}</a>'


def _fila_que_virou_html(fila: Fila) -> str:
    """A linha da migração: o nome, a frase e o repositório; a dica traz o endereço do «Instalar»."""
    repositorio = fila.virou.rstrip("/").rsplit("/", 1)[-1]
    dica = f"{FRASE_DO_QUE_VIROU} {repositorio}. {DICA_DO_QUE_VIROU} {fila.virou}"
    return f'''          <div class="lf ausente lf-virou" data-lancador="{_a(fila.chave)}">
            <span class="ext-ico lf-ico">{_icone(fila.chave)}</span>
            <span class="lf-nome"><span class="lanc-nome" title="{_a(fila.nome)}">{_e(fila.nome)}</span></span>
            <span class="lanc-jogos" title="{_a(dica)}">{_e(FRASE_DO_QUE_VIROU)} <code>{_e(repositorio)}</code></span>
          </div>'''


def fila_html(fila: Fila) -> str:
    """Uma linha de lançador: os mesmos três botões, acesos pelo que o lançador é."""
    if fila.virou:
        return _fila_que_virou_html(fila)
    botoes = []
    for gesto, rotulo, destino in BOTOES:
        destino = fila.configurar if gesto == "configurar-lancador" else destino
        ativo = botao_ativo(gesto, fila.achado)
        botoes.append(_botao(gesto, rotulo, destino, fila.chave, ativo))
    contagem = f'<span class="lf-n">{_e(fila.jogos)}</span>' if fila.achado else ""
    nome_cl = "lf-nome lf-nome-2" if fila.achado else "lf-nome"
    vazio = "" if fila.achado else '\n            <span class="lanc-jogos"></span>'
    classe = "lf" if fila.achado else "lf ausente"
    return f'''          <div class="{classe}" data-lancador="{_a(fila.chave)}">
            <span class="ext-ico lf-ico">{_icone(fila.chave)}</span>
            <span class="{nome_cl}"><span class="lanc-nome">{_e(fila.nome)}</span>{contagem}</span>{vazio}
            <span class="lf-botoes">{"".join(botoes)}</span>
          </div>'''


def _chave_html(ext: Extensao) -> str:
    """A chave da linha: Ligada, Desligada, Aceitar e ligar ou, ligada e sem rodar, a palavra do processo.

    O clique segue o registro (a ligada desliga): a vermelha diz na dica como tentar de novo.
    """
    palavra, cor = PROCESSO.get(ext.processo, ("", "")) if ext.ligada else ("", "")
    if not ext.ligada and ext.pede:
        classe, texto, dica = "nj-tog pede", ROTULO_DO_SIM, ext.pede
    elif not ext.ligada:
        classe, texto, dica = "nj-tog", "Desligada", "Liga ou desliga"
    elif palavra:
        classe, texto = f"nj-tog ligado {cor}", palavra
        dica = " ".join(x for x in (ext.porque, DICA_DE_TENTAR if cor == "vermelho" else "")
                        if x) or "Liga ou desliga"
    else:
        classe, texto, dica = "nj-tog ligado", "Ligada", "Liga ou desliga"
    return (f'<span class="{classe}" data-gesto="ligar-modificacao" data-v="{_a(ext.chave)}" '
            f'data-dica="{_a(dica)}"><span class="pino"></span><span class="txt">{texto}</span></span>')


SELO_DA_ORIGEM = {"oficial": "Oficial", "comunidade": "Comunidade", "local": "Local"}
ACOES_DO_MENU = (("atualizar", "Atualizar"), ("permissoes", "Ver permissões"), ("remover", "Remover"))  # (noqa-acento)

ROTULO_DA_CONFIRMACAO = "Confirmar remoção"
ONDE_DA_CONF = "conf"


def menu_html(chave: str, permissoes: Sequence[str] | None = None, *, remover: bool = False,
              fecha: bool = False, apagado: bool = False) -> str:
    """O conteúdo do ⋮ de uma extensão: três botões e, se pedido, o que ela pode fazer.

    ``remover`` é o primeiro clique em Remover: o botão passa a dizer «Confirmar remoção».
    ``fecha`` é o ⋮ da janela «Configurar»: a confirmação fecha a janela do lançador que sai.
    ``apagado`` é o lançador que vem com o Hefesto: os três ficam à vista, sem gesto.
    """
    if apagado:
        return "".join(f'<span class="btn mini apagado" aria-disabled="true">{rotulo}</span>'
                       for _acao, rotulo in ACOES_DO_MENU)
    botoes = []
    for acao, rotulo in ACOES_DO_MENU:
        alvo = f'data-gesto="mais-da-modificacao" data-v="{_a(chave)}:{acao}"'
        if fecha:
            alvo += f' data-onde="{ONDE_DA_CONF}"'
        if remover and acao == "remover":
            botoes.append(f'<a class="btn mini" href="#" {alvo}>{ROTULO_DA_CONFIRMACAO}</a>' if fecha
                          else f'<button class="btn mini" {alvo}>{ROTULO_DA_CONFIRMACAO}</button>')
        else:
            botoes.append(f'<button class="btn mini" {alvo}>{rotulo}</button>')
    if permissoes is None:
        return "".join(botoes)
    itens = "".join(f"<span>{_e(x)}</span>" for x in permissoes) or "<span>Nenhuma permissão.</span>"
    return f'{"".join(botoes)}<span class="ext-perm">{itens}</span>'


def _selo_da_extensao(ext: Extensao) -> str:
    origem = next((k for k, v in SELO_DA_ORIGEM.items() if v == ext.selo), "oficial")
    return f'<span class="lanc-selo {origem}">{ext.selo}</span>'


def extensao_html(ext: Extensao) -> str:
    """Uma linha do quadro «Extensões». Nome, versão e dica vêm do manifesto de terceiros: escapados."""
    menu = (f'\n            <div class="ext-menu ext-pop aberto" data-menu="{_a(ext.chave)}">{ext.menu}</div>'
            if ext.menu else "")
    return f'''          <div class="ext" data-modificacao="{_a(ext.chave)}">
            <span class="ext-ico" style="color:var(--{ext.cor})">{_icone(ext.chave)}</span>
            <div class="ext-quem" data-dica="{_a(ext.nome)}">
              <span class="ext-sub"><span class="ext-nome">{_e(ext.nome)}</span>{_selo_da_extensao(ext)}<span class="ext-ver">{_e(ext.versao)}</span></span>
              <span class="ext-faz" data-dica="{_a(ext.dica)}">{_e(ext.dica)}</span>
            </div>
            {_chave_html(ext)}
            <a class="ext-conf" href="{_a(ext.janela)}" data-gesto="configurar-modificacao" data-v="{_a(ext.chave)}" data-dica="Configurações: {_a(ext.nome)}">{_engrenagem()}</a>
            <button class="ext-mais" data-gesto="mais-da-modificacao" data-v="{_a(ext.chave)}" data-dica="Atualizar, ver as permissões ou remover">⋮</button>{menu}
          </div>'''


VAZIA = "Nenhuma extensão instalada. Instale uma de um endereço, logo abaixo."


def extensoes_html(exts: Sequence[Extensao] = EXTENSOES) -> str:
    """As linhas do quadro «Extensões»; sem nenhuma, a frase que diz o que fazer."""
    if not exts:
        return f'          <div class="ext-vazia">{VAZIA}</div>'
    return "\n".join(extensao_html(e) for e in exts)


def conta_das_extensoes(n: int) -> str:
    """O contador do topo do quadro."""
    return "Nenhuma instalada" if n == 0 else f"{n} instalada" + ("" if n == 1 else "s")


def fila_com_novo_html(filas: Sequence[Fila] = LANCADORES) -> str:
    """A fila inteira: uma linha por lançador e, no fim, a que adiciona outro."""
    linhas = "\n".join(fila_html(f) for f in filas)
    return f'''{linhas}
          <a class="lf lf-novo" href="#novo-lancador" data-gesto="adicionar-lancador" data-dica="Um programa desta máquina ou um pacote de extensão">
            <span class="ext-ico lf-ico"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5.5v13M5.5 12h13"/></svg></span>
            <span class="lanc-nome">Adicionar um lançador</span>
          </a>'''


def miolo() -> str:
    """Os dois quadros da aba: Extensões e Lançadores."""
    return f'''
    <div class="quadro">
      <input class="abre" type="checkbox" id="cx7-1" checked>
      <div class="quadro-topo">
        <label class="quadro-titulo" for="cx7-1">Extensões</label>
        <span class="conta" data-campo="mod-conta">{conta_das_extensoes(len(EXTENSOES))}</span>
      </div>
      <div class="quadro-corpo">
        <div class="ext-lista">
{extensoes_html()}
        </div>
        <div class="ext-instalar ext-instalar-pe" id="ext-instalar">
          <span class="ext-inst-rot">Instalar de um endereço</span>
          <input type="text" data-linha="mod-endereco" placeholder="https://github.com/…">
          <a class="btn" href="#" data-gesto="escolher-arquivo-da-modificacao" data-hef-forma="ext-instalar">Escolher a pasta…</a>
          <button class="btn roxo" data-gesto="instalar-modificacao" data-hef-forma="ext-instalar">Instalar</button>
        </div>
      </div>
    </div>

    <div class="quadro estica">
      <input class="abre" type="checkbox" id="cx7-2" checked>
      <div class="quadro-topo">
        <label class="quadro-titulo" for="cx7-2" data-dica="O perfil casa pelo processo e pela janela do jogo">Lançadores</label>
      </div>
      <div class="quadro-corpo">
        <div class="lanc-fila">
{fila_com_novo_html()}
        </div>
      </div>
    </div>
'''


class OpcaoDaJanela(NamedTuple):
    """Uma opção de modificação já com o valor de agora, pronta para virar uma linha da janela."""

    mod: str
    id: str
    rotulo: str
    tipo: str
    valor: str | bool | float | Sequence[str] | Mapping[str, Any]
    escolhas: tuple[str, ...] = ()
    grupo: str = ""
    minimo: float = 0
    maximo: float = 0
    passo: float = 1
    jogos: tuple[tuple[str, str], ...] = ()
    nota: str = ""
    formas: tuple[tuple[str, tuple[tuple[float, float], ...]], ...] = ()
    botoes: tuple[str, ...] = ()
    modo: str = ""


GESTO_DO_CSS = "editar-o-css-da-modificacao"
ROTULO_DO_CSS = "Editar o meu CSS"


OPCOES_DO_DESENHO = (
    OpcaoDaJanela("exemplo", "quando", "Quando", "escolha", "Os jogos que eu escolher",
                  ("Os jogos que eu escolher", "Qualquer jogo", "Só quando eu ligar"), "Geral"),
    OpcaoDaJanela("exemplo", "avisar", "Avisar quando sair versão nova", "ligado", False, (), "Geral"),
    OpcaoDaJanela("exemplo", "brilho", "Brilho da luz", "deslizante", "70", (), "Luz e vibração",
                  0, 100, 5),
    OpcaoDaJanela("exemplo", "vibracao", "Vibração dos jogos", "escolha", "Como o jogo pede",
                  ("Como o jogo pede", "Mais fraca", "Mais forte"), "Luz e vibração"),
    OpcaoDaJanela("exemplo", "espera", "Espera, em segundos", "numero", "3", (), "Avançado"),
    OpcaoDaJanela("exemplo", "avisar-por", "Avisar por", "escolha", "A barra de luz",
                  ("A barra de luz", "O som", "Os dois"), "Avançado"),
    OpcaoDaJanela("exemplo", "css", "Usar o meu CSS", "css", False, (), "Avançado",
                  nota="Linha 2: url()"),
)

FORMAS_DO_DESENHO = (
    ("Toque", ((1.0, 0.3),)),
    ("Duplo", ((1.0, 0.15), (0.0, 0.15), (1.0, 0.15))),
    ("Pulso", ((1.0, 0.1), (0.7, 0.1), (0.4, 0.1))),
    ("Onda", ((0.3, 0.2), (0.6, 0.2), (1.0, 0.3), (0.6, 0.2), (0.3, 0.2))),
    ("Nada", ()),
)
BOTOES_DO_DESENHO = ("cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2",
                     "dpad_up", "dpad_down", "touchpad_left_press", "touchpad_right_press")
PREFIXO_DA_ENTRADA = "entrada_"
GLIFO_DA_ENTRADA = {"l2": "l2", "r2": "r2", "analogico_esquerdo": "stick_l",
                    "analogico_direito": "stick_r", "touchpad": "touchpad",
                    "sacudir": "giroscopio", "inclinar": "acelerometro"}
OPCOES_DO_DESENHO_C = (
    OpcaoDaJanela("exemplo", "toques", "Toque de cada botão", "por_botao",
                  {"cross": "Toque", "circle": "Duplo", "square": "Pulso", "triangle": "Onda",
                   "touchpad_right_press": "Nada"}, (), "Toques",
                  formas=FORMAS_DO_DESENHO, botoes=BOTOES_DO_DESENHO),
    OpcaoDaJanela("exemplo", "endereco", "Endereço do aparelho na rede", "endereco", "", (),
                  "Ligação"),
    *OPCOES_DO_DESENHO,
)
AGORA_DO_DESENHO = ("conexoes", "aparelhos")  # (noqa-acento)
ESTADO_DO_DESENHO: dict[str, Any] = {
    "ligado": True,
    "conexoes": [  # (noqa-acento)
        {"id": "usb", "tipo": "Adaptador", "transporte": "usb", "estado": "ligado"},
        {"id": "bt", "tipo": "Bluetooth", "transporte": "bluetooth", "estado": "desligado"},
        {"id": "rede", "tipo": "Telefone", "transporte": "rede", "estado": "procurando",
         "motivo": "Esperando o app na rede"},
    ],
    "aparelhos": [
        {"nome": "Aparelho 1", "estado": "ligado", "bateria": 80, "forca": 0.7},
        {"nome": "Aparelho 2", "estado": "ligado", "bateria": 45, "forca": 0.3},
    ],
}


def _controle_da_opcao(o: OpcaoDaJanela) -> str:
    alvo = f'data-gesto="guardar-opcao-da-modificacao" data-v="{_a(o.mod)}:{_a(o.id)}"'
    if o.tipo == "escolha":
        itens = "".join(
            f'<option{" selected" if e == o.valor else ""}>{_e(e)}</option>' for e in o.escolhas)
        return f'<select class="ext-sel" {alvo} aria-label="{_a(o.rotulo)}">{itens}</select>'
    if o.tipo in ("ligado", "css"):
        classe, texto = ("nj-tog ligado", "Ligado") if o.valor else ("nj-tog", "Desligado")
        chave = (f'<span class="{classe}" {alvo}><span class="pino"></span>'
                 f'<span class="txt">{texto}</span></span>')
        if o.tipo == "ligado":
            return chave
        editar = (f'<button class="btn mini" data-gesto="{GESTO_DO_CSS}" '
                  f'data-v="{_a(o.mod)}:{_a(o.id)}">{ROTULO_DO_CSS}</button>')
        return f"{editar}{chave}"
    if o.tipo == "cor":
        return (f'<input class="ext-cor-in" type="color" {alvo} '
                f'value="{_a(o.valor)}" aria-label="{_a(o.rotulo)}">')
    if o.tipo == "deslizante":
        return (f'<span class="ext-desl"><input type="range" min="{o.minimo:g}" '
                f'max="{o.maximo:g}" step="{o.passo:g}" value="{_a(o.valor)}" {alvo} '
                f'aria-label="{_a(o.rotulo)}" '
                f'oninput="this.nextElementSibling.textContent=this.value">'
                f'<b>{_e(o.valor)}</b></span>')
    if o.tipo == "jogos":
        return _jogos_da_opcao(o)
    if o.tipo == "por_botao":
        return _por_botao_da_opcao(o)
    if o.tipo == "endereco":
        return (f'<input class="ext-end" type="text" inputmode="url" spellcheck="false" '
                f'placeholder="{DICA_DO_ENDERECO}" {alvo} value="{_a(o.valor)}" '
                f'aria-label="{_a(o.rotulo)}">')
    return (f'<input class="ext-num" type="text" inputmode="decimal" {alvo} '
            f'value="{_a(o.valor)}" aria-label="{_a(o.rotulo)}">')


def _jogos_da_opcao(o: OpcaoDaJanela) -> str:
    """Uma caixa por jogo que tem perfil; a lista nasce vazia e a caixa age no ``change``."""
    if not o.jogos:
        return '<span class="ext-vazia">Nenhum jogo tem perfil ainda.</span>'
    marcados = set(o.valor) if isinstance(o.valor, (list, tuple)) else set()
    caixas = "".join(
        f'<label class="jg-l" id="{PEDACO}op-{_a(o.id)}-{_a(chave)}"><input type="checkbox"{" checked" if chave in marcados else ""} '
        f'data-gesto="guardar-opcao-da-modificacao" data-v="{_a(o.mod)}:{_a(o.id)}:{_a(chave)}">'
        f'<span class="jg-n">{_e(nome)}</span></label>'
        for chave, nome in o.jogos)
    return f'<div class="jg-lista ext-jogos" aria-label="{_a(o.rotulo)}">{caixas}</div>'


DICA_DO_ENDERECO = "IP:porta"
GLIFO_DO_BOTAO = {"l3": "stick_l", "r3": "stick_r", "create": "share",
                  "touchpad_left_press": "touchpad", "touchpad_middle_press": "touchpad",
                  "touchpad_right_press": "touchpad"}
_TERCA_DO_TOUCHPAD = {"touchpad_left_press": 3.0, "touchpad_middle_press": 11.67,
                      "touchpad_right_press": 20.33}
_ONDA_L, _ONDA_A = 48.0, 12.0


def _onda_da_forma(passos: Sequence[tuple[float, float]]) -> str:
    """A forma desenhada: um retângulo por passo, a largura pelo tempo e a altura pela força.

    A forma sem passos (a que não toca) é a linha tracejada do zero.
    """
    total = sum(s for _f, s in passos)
    if total <= 0:
        corpo = f'<line class="onda-zero" x1="2" y1="13" x2="{2 + _ONDA_L:g}" y2="13"/>'
    else:
        x, partes = 2.0, []
        for forca, segundos in passos:
            largura = _ONDA_L * segundos / total
            altura = _ONDA_A * max(0.0, min(1.0, forca))
            if altura > 0:
                partes.append(f'<rect x="{x:.1f}" y="{14 - altura:.1f}" width="{largura * 0.9:.1f}" '
                              f'height="{altura:.1f}" rx="1"/>')
            x += largura
        corpo = "".join(partes) or f'<line class="onda-zero" x1="2" y1="13" x2="{2 + _ONDA_L:g}" y2="13"/>'
    return f'<svg class="onda" width="52" height="14" viewBox="0 0 52 14" aria-hidden="true">{corpo}</svg>'


def _por_botao_da_opcao(o: OpcaoDaJanela) -> str:
    """Uma linha por botão: o glifo, a onda da forma escolhida e a lista das formas.

    A lista age no ``change``, com o botão no ``data-v``; o valor de cada botão é o do rascunho.
    """
    formas = dict(o.formas)
    escolhidas = o.valor if isinstance(o.valor, Mapping) else {}
    primeira = next(iter(formas), "")
    linhas = []
    for botao in o.botoes:
        atual = escolhidas.get(botao) or primeira
        itens = "".join(f'<option{" selected" if nome == atual else ""}>{_e(nome)}</option>'
                        for nome in formas)
        linhas.append(
            f'<div class="tql" id="{PEDACO}op-{_a(o.id)}-{_a(botao)}"><svg class="tq-gl" viewBox="0 0 32 32" width="22" height="22" '
            f'aria-hidden="true"><use href="#bt-{_a(botao)}"/></svg>'
            f'{_onda_da_forma(formas.get(atual, ()))}'
            f'<select class="ext-sel" data-gesto="guardar-opcao-da-modificacao" '
            f'data-v="{_a(o.mod)}:{_a(o.id)}:{_a(botao)}" aria-label="{_a(o.rotulo)}">{itens}'
            "</select></div>")
    return f'<div class="tq-lista" aria-label="{_a(o.rotulo)}">{"".join(linhas)}</div>'


def entrada_da_opcao(o: OpcaoDaJanela) -> str | None:
    """A chave da entrada do controle que a opção escolhe (``entrada_<chave>``), ou ``None``."""
    if o.tipo in _EMPILHADAS or not o.id.startswith(PREFIXO_DA_ENTRADA):
        return None
    return o.id[len(PREFIXO_DA_ENTRADA):]


def glifo_da_entrada(o: OpcaoDaJanela) -> str | None:
    """O glifo do mapa do controle para a linha da entrada; ``None`` se a entrada não tem glifo."""
    chave = entrada_da_opcao(o)
    return GLIFO_DA_ENTRADA.get(chave) if chave is not None else None


_DEGRAUS_DA_ONDA = 9


def _rampa(t: float) -> float:
    return t


def _ao_quadrado(t: float) -> float:
    return t * t


_FORMA_DA_ENTRADA: dict[str, Callable[[float], float]] = {"direto": _rampa, "suave": _ao_quadrado}


def _onda_da_entrada(escolha: object) -> str:
    """O desenho do efeito da entrada contínua, no mesmo traço e tamanho da onda dos toques.

    «Nenhum» é o zero tracejado; «Direto» é a rampa reta (a força segue a entrada) e «Suave» a
    mesma curva ao quadrado (o começo é leve), como a extensão as aplica. Um valor sem desenho
    deixa o lugar vazio, do mesmo tamanho.
    """
    nome = str(escolha).strip().casefold()
    cabeca = '<svg class="onda" width="52" height="14" viewBox="0 0 52 14" aria-hidden="true">'
    if nome == "nenhum":
        return (f'{cabeca}<line class="onda-zero" x1="2" y1="13" x2="{2 + _ONDA_L:g}" y2="13"/>'
                "</svg>")
    forma = _FORMA_DA_ENTRADA.get(nome)
    if forma is None:
        return f"{cabeca}</svg>"
    passo = _ONDA_L / _DEGRAUS_DA_ONDA
    barras = []
    for i in range(_DEGRAUS_DA_ONDA):
        altura = max(1.2, _ONDA_A * forma((i + 1) / _DEGRAUS_DA_ONDA))
        barras.append(f'<rect x="{2 + i * passo:.1f}" y="{14 - altura:.1f}" '
                      f'width="{passo * 0.9:.1f}" height="{altura:.1f}" rx="1"/>')
    return f"{cabeca}{''.join(barras)}</svg>"


def _linha_da_entrada(o: OpcaoDaJanela) -> str:
    """A linha da entrada no arranjo dos botões de cima: o glifo, o desenho do efeito escolhido,
    o rótulo na dica e a lista."""
    onda = _onda_da_entrada(o.valor) if o.tipo == "escolha" else ""
    return (f'<div class="tql" id="{PEDACO}op-{_a(o.id)}" data-dica="{_a(o.rotulo)}">'
            f'<svg class="tq-gl" viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">'
            f'<use href="#en-{_a(entrada_da_opcao(o) or "")}"/></svg>'
            f'{onda}{_controle_da_opcao(o)}</div>')


def _simbolo_do_glifo(ident: str, arquivo: str, terca: float | None = None) -> str:
    """Um glifo de ``assets/glyphs`` como ``<symbol>`` de uma cor só, ``currentColor``."""
    pasta = pathlib.Path(__file__).resolve().parents[3] / "assets" / "glyphs"
    bruto = (pasta / f"{arquivo}.svg").read_text(encoding="utf-8")
    achado = re.search(r"<svg\b[^>]*>(.*)</svg>", bruto, flags=re.S)
    miolo = re.sub(r"<!--.*?-->", "", achado.group(1) if achado else "", flags=re.S)
    miolo = re.sub(r"#[0-9a-fA-F]{6}\b", "currentColor", miolo)
    if terca is not None:
        miolo += (f'<rect x="{terca:g}" y="8" width="8.67" height="16" '
                  'fill="currentColor" opacity=".4"/>')
    return f'<symbol id="{ident}" viewBox="0 0 32 32">{" ".join(miolo.split())}</symbol>'


def sprite_dos_botoes() -> str:
    """Os glifos dos botões do ``por_botao`` (``bt-<botão>``) e das entradas do controle
    (``en-<entrada>``) como ``<symbol>``, uma vez na página.

    Só o gerador o chama: os glifos moram em ``assets/glyphs`` do repositório, e a janela do produto
    os usa pelo ``<use>`` da página publicada.
    """
    from hefesto_dualsense4unix.mods.manifesto import BOTOES_DO_POR_BOTAO

    simbolos = [_simbolo_do_glifo(f"bt-{botao}", GLIFO_DO_BOTAO.get(botao, botao),
                                  _TERCA_DO_TOUCHPAD.get(botao))
                for botao in BOTOES_DO_POR_BOTAO]
    simbolos += [_simbolo_do_glifo(f"en-{entrada}", glifo)
                 for entrada, glifo in GLIFO_DA_ENTRADA.items()]
    return ('<svg class="bt-sprite" width="0" height="0" aria-hidden="true" '
            f'style="position:absolute">{"".join(simbolos)}</svg>')


def _grupos_das_opcoes(opcoes: Sequence[OpcaoDaJanela]) -> dict[str, list[OpcaoDaJanela]]:
    """Os grupos na ordem em que aparecem; a opção sem grupo vai ao primeiro."""
    nomes = [o.grupo for o in opcoes if o.grupo]
    primeiro = nomes[0] if nomes else ""
    grupos: dict[str, list[OpcaoDaJanela]] = {}
    for o in opcoes:
        grupos.setdefault(o.grupo or primeiro, []).append(o)
    return grupos


def _nota_da_opcao(opcao: OpcaoDaJanela) -> str:
    """A nota da opção, em vermelho sob o rótulo; vazia sem nota."""
    return f'<span class="ky-recusa">{_e(opcao.nota)}</span>' if opcao.nota else ""


def _cartoes_das_opcoes(opcoes: Sequence[OpcaoDaJanela]) -> str:
    """O arranjo aprovado das janelas da 07: um cartão por grupo, uma linha por opção.

    Rótulo à esquerda e controle à direita; a opção de jogos põe o rótulo em cima e a lista de
    caixas embaixo, na largura do cartão.
    """
    cartoes = []
    for n, (nome, itens) in enumerate(_grupos_das_opcoes(opcoes).items()):
        chave, linhas = chave_da_aba(nome, itens)
        cartoes.append(f'<div class="ac-card"><div class="ac-topo">'
                       f'<span class="ac-tit">{_e(nome or "Opções")}'
                       f'{_bolinha_da_aba(f"cartao-{n}", chave)}</span></div>'
                       f'{_linhas_da_aba(f"cartao-{n}", linhas, chave)}</div>')
    return f'<div class="ky-grade">{"".join(cartoes)}</div>'


def chave_da_aba(nome: str, itens: Sequence[OpcaoDaJanela]
                 ) -> tuple[OpcaoDaJanela | None, list[OpcaoDaJanela]]:
    """A chave da aba e as linhas que ficam: a opção ``ligado`` de rótulo igual ao nome do grupo
    liga e desliga a aba inteira, e por isso sai da lista e vira a bolinha do rótulo da aba."""
    alvo = nome.strip().casefold()
    chave = next((o for o in itens if o.tipo == "ligado" and alvo
                  and o.rotulo.strip().casefold() == alvo), None)
    return chave, [o for o in itens if o is not chave]


def _bolinha_da_aba(n: int | str, chave: OpcaoDaJanela | None) -> str:
    """A bolinha da chave da aba, verde ligada e cinza desligada; o clique é o da chave de
    ``ligado`` (``guardar-opcao-da-modificacao``). Pedaço próprio: o clique repinta só ela."""
    if chave is None:
        return ""
    ligada = bool(chave.valor)
    estado = "Ligado" if ligada else "Desligado"
    return (f'<span class="mj-aba-chave" id="{PEDACO}chave-da-aba-{n}">'
            f'<i class="mj-bolinha{" on" if ligada else ""}" role="switch" '
            f'aria-checked="{str(ligada).lower()}" aria-label="{_a(chave.rotulo)}" '
            f'data-dica="{_a(chave.rotulo)}: {estado}" data-gesto="guardar-opcao-da-modificacao" '
            f'data-v="{_a(chave.mod)}:{_a(chave.id)}"></i></span>')


def _linhas_da_aba(n: int | str, itens: Sequence[OpcaoDaJanela], chave: OpcaoDaJanela | None) -> str:
    """As linhas de uma aba; com a chave da aba desligada, apagadas e ainda mexíveis."""
    linhas = _linhas_das_opcoes(itens)
    if chave is None:
        return linhas
    return (f'<div class="mj-da-chave{"" if chave.valor else " apagada"}" '
            f'id="{PEDACO}da-chave-{n}">{linhas}</div>')


_EMPILHADAS = ("jogos", "por_botao")


def _linha_da_opcao(o: OpcaoDaJanela) -> str:
    """A linha de uma opção: rótulo à esquerda e controle à direita, ou a lista embaixo."""
    if o.tipo in _EMPILHADAS:
        return (f'<div id="{PEDACO}op-{_a(o.id)}"><div class="ky-rot"><span>{_e(o.rotulo)}</span></div>'
                f'{_controle_da_opcao(o)}</div>')
    return (f'<div class="ky-linha" id="{PEDACO}op-{_a(o.id)}"><div class="ky-rot"><span>{_e(o.rotulo)}</span>'
            f'{_nota_da_opcao(o)}</div>'
            f'<div class="ky-ctrl">{_controle_da_opcao(o)}</div></div>')


def _linhas_das_opcoes(itens: Sequence[OpcaoDaJanela]) -> str:
    """Uma linha por opção; as entradas do controle com glifo, juntas, no arranjo dos botões.

    Cada opção é um pedaço ``#mod-op-<id>`` (:class:`PinturaDaJanela`): o clique repinta só ela.
    """
    partes = []
    for com_glifo, juntas in itertools.groupby(itens, key=lambda o: glifo_da_entrada(o) is not None):
        if com_glifo:
            partes.append(f'<div class="tq-lista">{"".join(map(_linha_da_entrada, juntas))}</div>')
        else:
            partes.extend(map(_linha_da_opcao, juntas))
    return "".join(partes)


def _abas_das_opcoes(opcoes: Sequence[OpcaoDaJanela], aba: str) -> str:
    """O lado dos ajustes do arranjo C: os grupos do manifesto em abas, um cartão só.

    As abas são rádios (o navegador troca a tela sem gesto); ``aba`` é o grupo que nasce aberto, o
    da última opção mudada, para a janela redesenhada não voltar à primeira. As telas se empilham
    na mesma célula (``--n`` é o número de abas): a janela tem a altura da maior e não pula sob o
    clique. Com um grupo só, é o cartão de sempre.
    """
    grupos = _grupos_das_opcoes(opcoes)
    if len(grupos) < 2:
        return _cartoes_das_opcoes(opcoes)
    aberta = aba if aba in grupos else next(iter(grupos))
    telas = []
    for n, (nome, itens) in enumerate(grupos.items()):
        chave, linhas = chave_da_aba(nome, itens)
        telas.append(
            f'<input type="radio" name="mj-aba" id="mj-aba-{n}"{" checked" if nome == aberta else ""}>'
            f'<label for="mj-aba-{n}">{_e(nome)}{_bolinha_da_aba(n, chave)}</label>'
            f'<div class="mj-tela" id="{PEDACO}tela-{n}">{_linhas_da_aba(n, linhas, chave)}</div>')
    partes = "".join(telas)
    return f'<div class="ac-card mj-abas" style="--n:{len(grupos)}">{partes}</div>'


PEDACOS_DO_AGORA = ("conexoes", "nivel", "perfil", "aparelhos")  # (noqa-acento)
NIVEL_MAXIMO = 10
SEM_VALOR = "—"
DICA_DO_PARAR = "Todos os aparelhos a zero na hora. O nível e o perfil ficam guardados."
GESTO_DO_PARAR = "parar-tudo-da-modificacao"
PALAVRA_DO_ESTADO = {"ligado": "Ligado", "procurando": "Procurando", "desligado": "Desligado",
                     "falhou": "Falhou"}
COR_DO_ESTADO = {"ligado": "verde", "procurando": "amarelo", "desligado": "mudo",
                 "falhou": "laranja"}
_TRACO_DO_ICONE = ('viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" '
                   'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"')
ICONE_DO_TRANSPORTE = {
    "usb": ('<rect x="4" y="8" width="11" height="8" rx="1.5"/><rect x="15" y="9.5" width="5" '
            'height="5" rx=".6"/><line x1="17" y1="11" x2="17" y2="13"/>'
            '<line x1="7" y1="12" x2="12" y2="12"/>'),
    "bluetooth": '<polyline points="7,7 17,16 12,20 12,4 17,8 7,17"/>',
    "rede": ('<path d="M3 9.5a13 13 0 0 1 18 0"/><path d="M6 13a8.5 8.5 0 0 1 12 0"/>'
             '<path d="M9 16.5a4 4 0 0 1 6 0"/><circle cx="12" cy="19.5" r=".8"/>'),
    "local": ('<rect x="3" y="4" width="18" height="14" rx="2"/><line x1="3" y1="8" x2="21" y2="8"/>'
              '<line x1="8" y1="21" x2="16" y2="21"/>'),
}
ICONE_DO_APARELHO = ('<rect x="7" y="3" width="10" height="18" rx="5"/><path d="M3 9 q-1.5 3 0 6"/>'
                     '<path d="M21 9 q1.5 3 0 6"/>')


def icone_html(desenho: str, cor: str) -> str:
    return f'<svg class="ic c-{cor}" {_TRACO_DO_ICONE}>{desenho}</svg>'


def estado_html(estado: str) -> str:
    """A pílula do estado: a bolinha e a palavra, na cor do estado."""
    cor = COR_DO_ESTADO.get(estado, "mudo")
    return f'<span class="est est-{cor}"><i></i>{PALAVRA_DO_ESTADO.get(estado, SEM_VALOR)}</span>'


def bateria_html(bateria: Any) -> str:
    """A pilha do aparelho, cheia até a bateria; vazio quando a extensão não a dá."""
    if isinstance(bateria, bool) or not isinstance(bateria, int):
        return ""
    return (f'<span class="bat" data-dica="Bateria {bateria}%">'
            f'<i style="width:{max(0, min(100, bateria))}%"></i></span>')


def _forca_html(forca: Any) -> str:
    """A onda da força de agora, com a altura da força; vazio quando a extensão não a dá."""
    if isinstance(forca, bool) or not isinstance(forca, (int, float)):
        return ""
    f = max(0.0, min(1.0, float(forca)))
    return (f'<span class="vivo" data-dica="Força agora: {round(f * 100)}%">'
            f'<svg viewBox="0 0 120 18" preserveAspectRatio="none" aria-hidden="true">'
            f'<path d="M0 9 Q7.5 {9 - 8 * f:.1f} 15 9 T30 9 T45 9 T60 9 T75 9 T90 9 T105 9 T120 9"/>'
            "</svg></span>")


def itens_do_estado(estado: Mapping[str, Any] | None, chave: str) -> list[dict[str, Any]]:
    """Os objetos de ``chave`` no estado; o texto solto (o formato antigo) é só o nome."""
    bruto = estado.get(chave) if estado else None
    if not isinstance(bruto, list):
        return []
    return [x if isinstance(x, dict) else {"nome": str(x)} for x in bruto]


def _conexao_html(c: Mapping[str, Any]) -> str:
    estado = str(c.get("estado") or "ligado")
    motivo = c.get("motivo")
    dica = f' data-dica="{_a(motivo)}"' if isinstance(motivo, str) and motivo else ""
    desenho = ICONE_DO_TRANSPORTE.get(str(c.get("transporte")), ICONE_DO_TRANSPORTE["local"])
    return (f'<div class="cx-linha"{dica}>{icone_html(desenho, COR_DO_ESTADO.get(estado, "mudo"))}'
            f'<span class="cx-rot">{_e(c.get("tipo") or c.get("id") or SEM_VALOR)}</span>'
            f"{estado_html(estado)}</div>")


def _aparelho_html(ap: Mapping[str, Any]) -> str:
    """Um aparelho: o nome, a pilha e, ligado, a onda da força; senão, a pílula do estado."""
    estado = str(ap.get("estado") or "ligado")
    vivo = _forca_html(ap.get("forca")) if estado == "ligado" else estado_html(estado)
    cor = "acessorio" if estado == "ligado" else COR_DO_ESTADO.get(estado, "mudo")
    return (f'<div class="ap">{icone_html(ICONE_DO_APARELHO, cor)}'
            f'<span class="ap-nome">{_e(ap.get("nome") or SEM_VALOR)}</span>'
            f'{bateria_html(ap.get("bateria"))}{vivo}</div>')


def _topo_do_agora(vivo: bool, processo: str, porque: str) -> str:
    """O canto do «Agora»: Ligada, Parada ou, sem conexão, a palavra do processo na cor dele."""
    palavra, cor = PROCESSO.get(processo, ("", ""))
    if vivo or not palavra:
        return f'<span class="ja-srv">{"Ligada" if vivo else "Parada"}</span>'
    dica = " ".join(x for x in (porque, DICA_DE_TENTAR if cor == "vermelho" else "") if x)
    atributo = f' data-dica="{_a(dica)}"' if dica else ""
    return f'<span class="ja-srv est est-{cor}"{atributo}><i></i>{palavra}</span>'


def agora_html(pedacos: Sequence[str], estado: Mapping[str, Any] | None, *, processo: str = "",
               porque: str = "", gestao: Gestao | None = None) -> str:
    """O miolo da coluna «Agora»: só os pedaços que o manifesto declara, do ``acessorios.estado``.

    Sem estado, ou com a extensão parada (``ligado`` falso), o nível e o perfil ficam vazios: nenhum
    número que a extensão não deu. As conexões e os aparelhos são os que ela publicou, parada ou não:
    o «Parar tudo» zera a força, e o adaptador segue ligado (a conexão que cai já devolve o estado
    vazio, sem item nenhum). O perfil e os nomes vêm de terceiros: escapados. ``processo`` e
    ``porque`` são os do supervisor: sem conexão, o canto diz se ela caiu, liga ou foi recusada.
    ``gestao`` são os aparelhos geridos sem ``grupo``: cada linha ganha a chave e as ações.
    """
    vivo = bool(estado and estado.get("ligado") is True)
    linhas = ['<div class="ja-ag-topo"><span class="pc-sub">Agora</span>'
              f"{_topo_do_agora(vivo, processo, porque)}</div>"]
    declarados = [x for x in PEDACOS_DO_AGORA if x in pedacos]
    for pedaco in declarados:
        if pedaco == "conexoes":  # (noqa-acento)
            itens = "".join(_conexao_html(c) for c in itens_do_estado(estado, pedaco))
            linhas.append(f'<div class="ja-cxs" data-agora="{pedaco}">'
                          f'{itens or f"""<div class="cx-linha vazia"><span class="cx-rot">{SEM_VALOR}</span></div>"""}'
                          "</div>")
            if len(declarados) > 1:
                linhas.append('<div class="ja-sep"></div>')
        elif pedaco == "nivel":
            nivel = estado.get("nivel") if vivo and estado else None
            nivel = nivel if isinstance(nivel, int) and not isinstance(nivel, bool) else None
            numero = (f"<b>{nivel}</b><span>/ {NIVEL_MAXIMO}</span>" if nivel is not None
                      else f"<b>{SEM_VALOR}</b>")
            degraus = "".join(f'<i class="{"on" if nivel is not None and n <= nivel else ""}">'
                              "</i>" for n in range(1, NIVEL_MAXIMO + 1))
            linhas.append(
                '<div class="ja-nivel-caixa" data-agora="nivel"><div class="ja-nivel-linha">'
                f'<span class="ja-rot">Nível</span><span class="ja-nivel">{numero}</span></div>'
                f'<div class="ja-degraus">{degraus}</div></div>')
        elif pedaco == "perfil":
            perfil = estado.get("perfil") if vivo and estado else None
            texto = _e(perfil) if isinstance(perfil, str) and perfil.strip() else SEM_VALOR
            linhas.append('<div class="ja-perfil-linha" data-agora="perfil"><span class="ja-rot">'
                          f'Perfil</span><span class="ja-perfil-nome">{texto}</span></div>')
        else:
            itens = (aparelhos_na_coluna_html(gestao) if gestao and not gestao.aparelhos.grupo
                     else "".join(_aparelho_html(a) for a in itens_do_estado(estado, pedaco)))
            vazio = (f'<div class="ap vazio">{icone_html(ICONE_DO_APARELHO, "mudo")}'
                     f'<span class="ap-nome">{SEM_VALOR}</span></div>')
            linhas.append(f'<div class="ja-aps" data-agora="aparelhos">{itens or vazio}</div>')
    return "".join(linhas)


def parar_tudo_html(mod: str) -> str:
    """O «Parar tudo» do topo da janela: o gesto ``para`` vai só a esta extensão."""
    return (f'<button class="ja-parar" data-gesto="{GESTO_DO_PARAR}" data-v="{_a(mod)}" '
            f'data-dica="{DICA_DO_PARAR}"><svg viewBox="0 0 16 16" width="13" height="13">'
            '<rect x="3" y="3" width="10" height="10" rx="1.5" fill="currentColor"/></svg>'
            "Parar tudo</button>")


def _arranjo_c(nome: str, ajustes: str, *, mod: str, agora: Sequence[str],
               estado: Mapping[str, Any] | None, parar: str, processo: str = "",
               porque: str = "", faixa: str = "", gestao: Gestao | None = None) -> str:
    """A janela do arranjo C: «Parar tudo» no topo, a coluna «Agora» e os ajustes, e o rodapé.

    ``faixa`` é a do controle livre, fixa embaixo das duas colunas; sem ``agora``, os ajustes
    ocupam a largura inteira.
    """
    coluna = (f'<div class="ja-agora" id="mod-agora">{agora_html(agora, estado, processo=processo, porque=porque, gestao=gestao)}</div>'
              if agora else "")
    opcoes = f'<div class="ja-opcoes">{ajustes}</div>' if ajustes else ""
    classe = ("ja-corpo" + ("" if agora else " sem-agora")
              + (" com-faixa" if faixa and (agora or ajustes) else ""))
    fecha = _o_fecho(mod)
    return f'''    <div class="tn-topo ja-topo">
      <span class="tn-tit">Configurar · {_e(nome)}</span>{parar}
      <a class="tn-x" href="#" data-dica="Fechar"{fecha}>\u00d7</a>
    </div>
    <div class="{classe}">
      {coluna}
      {opcoes}
      {faixa}
    </div>
    <div class="tn-rod">
      <a class="btn" href="#"{fecha}>Cancelar</a>
      <a class="btn roxo" href="#" data-gesto="{GESTO_DO_GUARDAR}" data-v="{_a(mod)}">Guardar</a>
    </div>'''


GESTO_DO_GUARDAR = "guardar-modificacao"
VAZIO_DA_JANELA = '<div class="ext-vazia">Esta extensão não tem opções para ajustar.</div>'
GESTO_DO_CANCELAR = "cancelar-modificacao"


def _o_fecho(mod: str) -> str:
    """O gesto do Cancelar e do X, só na janela de uma extensão (o desenho sem ``mod`` fecha e só)."""
    return f' data-gesto="{GESTO_DO_CANCELAR}" data-v="{_a(mod)}"' if mod else ""


PEDACO = "mod-"
_SEM_FECHO = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
                        "source", "track", "wbr"})
_ABA_MARCADA = re.compile(r'(<input type="radio" name="mj-aba" id="mj-aba-\d+") checked>')
_BARRA_DO_LIVRE = re.compile(r'<div class="mj-trilho.*?</output></div>', re.S)


class Pedaco(NamedTuple):
    """Um pedaço ``id="mod-…"`` do miolo: o miolo dele, o dele sem os pedaços de dentro e o pai."""

    miolo: str
    proprio: str
    pai: str


class _Cortador(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=False)
        self.linhas = [0]
        for n, letra in enumerate(html):
            if letra == "\n":
                self.linhas.append(n + 1)
        self.pilha: list[tuple[str, str]] = []
        self.abertos: dict[str, tuple[int, str]] = {}
        self.cortes: dict[str, tuple[int, int, str]] = {}
        self.feed(html)
        self.close()

    def _onde(self) -> int:
        linha, coluna = self.getpos()
        return self.linhas[linha - 1] + coluna

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SEM_FECHO:
            return
        ident = next((v for k, v in attrs if k == "id"), None) or ""
        ident = ident if ident.startswith(PEDACO) else ""
        if ident:
            pai = next((i for _t, i in reversed(self.pilha) if i), "")
            self.abertos[ident] = (self._onde() + len(self.get_starttag_text() or ""), pai)
            self.cortes[ident] = (0, 0, pai)
        self.pilha.append((tag, ident))

    def handle_endtag(self, tag: str) -> None:
        if tag in _SEM_FECHO or all(t != tag for t, _i in self.pilha):
            return
        while self.pilha:
            aberta, ident = self.pilha.pop()
            if ident:
                inicio, pai = self.abertos.pop(ident)
                self.cortes[ident] = (inicio, self._onde(), pai)
            if aberta == tag:
                break


def _sem_o_que_a_pessoa_muda(html: str) -> str:
    return _BARRA_DO_LIVRE.sub("", _ABA_MARCADA.sub(r"\1>", html))


@functools.lru_cache(maxsize=8)
def pedacos_da_janela(html: str) -> tuple[str, dict[str, Pedaco]]:
    """O esqueleto do miolo e os pedaços ``id="mod-…"`` dele, os de fora antes dos de dentro.

    O esqueleto e o miolo próprio de cada pedaço deixam de fora o miolo dos pedaços de dentro, a aba
    marcada e a barra do livre: quem muda essas duas é a pessoa, na tela.
    """
    cortes = _Cortador(html).cortes

    def proprio(inicio: int, fim: int, dono: str) -> str:
        partes, onde = [], inicio
        for ini, fi, pai in sorted(cortes.values()):
            if pai == dono and inicio <= ini and fi <= fim:
                partes.append(html[onde:ini])
                onde = fi
        return _sem_o_que_a_pessoa_muda("".join(partes) + html[onde:fim])

    pedacos = {ident: Pedaco(html[ini:fi], proprio(ini, fi, ident), pai)
               for ident, (ini, fi, pai) in cortes.items() if fi >= ini}
    return proprio(0, len(html), ""), pedacos


class PinturaDaJanela:
    """O que a janela de uma extensão tem na tela, para o tique e o gesto mandarem só o que mudou.

    A janela inteira (``#mod-janela``) só se repinta quando o esqueleto muda: uma aba, uma opção
    ou um pedaço que nasce ou some. O resto vai nos pedaços ``#mod-…`` que mudaram (uma opção, um
    botão, a tela de uma aba, os modos do livre), e a lista que a pessoa rolou fica onde estava,
    na aba em que ela estava. Os pedaços já mandados voltam a cada tique (a ponte pula o que já
    pintou), para o que ficou adiado sob um clique em voo chegar no tique seguinte.
    """

    def __init__(self) -> None:
        self.base = ""
        self.na_tela: dict[str, Pedaco] = {}
        self.mandados: set[str] = set()

    def esquecer(self) -> None:
        self.base, self.na_tela, self.mandados = "", {}, set()

    def blocos(self, novo: str) -> dict[str, str]:
        if not novo:
            self.esquecer()
            return {}
        raiz, pedacos = pedacos_da_janela(novo)
        if not self.base or raiz != pedacos_da_janela(self.base)[0]:
            self.base, self.na_tela, self.mandados = novo, dict(pedacos), set()
            return {"#mod-janela": novo}
        cobertos: set[str] = set()
        for ident, pedaco in pedacos.items():
            velho = self.na_tela.get(ident)
            if pedaco.pai in cobertos or velho is None or velho.proprio != pedaco.proprio:
                cobertos.add(ident)
                self.na_tela[ident] = pedaco
                if pedaco.pai not in cobertos:
                    self.mandados.add(ident)
        self.mandados &= pedacos.keys()
        return {"#mod-janela": self.base,
                **{f"#{i}": self.na_tela[i].miolo for i in pedacos if i in self.mandados}}


def janela_pintada(blocos: Mapping[str, Any]) -> str:
    """O miolo que a ponte deixa na janela da extensão: ``#mod-janela`` e, por cima, cada pedaço
    ``#mod-…`` dos ``blocos``, na ordem em que vêm."""
    html = str(blocos.get("#mod-janela") or "")
    for seletor, miolo in blocos.items():
        corte = _Cortador(html).cortes.get(seletor[1:]) if seletor != "#mod-janela" else None
        if corte is not None and corte[1] >= corte[0]:
            html = html[:corte[0]] + str(miolo) + html[corte[1]:]
    return html


def modificacao_miolo_html(nome: str, opcoes: Sequence[OpcaoDaJanela], *, mod: str = "",
                           agora: Sequence[str] = (), estado: Mapping[str, Any] | None = None,
                           parar_tudo: bool = False, aba: str = "", processo: str = "",
                           porque: str = "", acoes: Sequence[AcaoDaJanela] = (),
                           aparelhos: AparelhosDaJanela | None = None,
                           em_curso: frozenset[tuple[str, str]] = frozenset(),
                           livre: LivreAoVivo | None = None, controles: str = "") -> str:
    """O conteúdo da janela de uma extensão: um cartão por grupo, «Para» no topo, Cancelar e Guardar.

    Cada opção vira uma linha do cartão do grupo dela; o Guardar grava o rascunho. ``agora`` são os
    pedaços da coluna «Agora» (``estado`` é o último ``acessorios.estado``) e ``parar_tudo`` põe o
    botão no topo, os dois só com ``mod``. Com ``agora``, as ações, os ``aparelhos`` ou o ``livre``, é
    o arranjo C: a coluna à esquerda e os grupos em abas (``aba`` é a aberta); ``em_curso`` são os
    pares (ação, alvo) que esperam a extensão, e a opção ``livre`` vai à faixa de baixo.
    ``controles`` é a aba dos cartões dos controles de cada aparelho (``aparelhos_controles``), que
    só aparece quando algum aparelho do ``estado`` os tem.
    """
    parar = parar_tudo_html(mod) if parar_tudo and mod else ""
    agora = agora if mod else ()
    livre_op = next((o for o in opcoes if o.tipo == "livre"), None) if mod else None
    vazio = "" if livre_op else VAZIO_DA_JANELA
    opcoes = [o for o in opcoes if o.tipo != "livre"]
    acoes = tuple(acoes) if mod else ()
    gestao = Gestao(mod, aparelhos, estado, em_curso) if mod and aparelhos else None
    cartoes = controles_dos_aparelhos_html(mod, estado, em_curso) if mod and controles else ""
    cc = (controles, cartoes) if cartoes else ("", "")
    if agora or acoes or gestao or livre_op or cartoes:
        if acoes or (gestao and gestao.aparelhos.grupo) or cartoes:
            ajustes = _abas_com_as_pecas(opcoes, aba, mod=mod, acoes=acoes, gestao=gestao,
                                         controles=cc)
        else:
            ajustes = _abas_das_opcoes(opcoes, aba) if opcoes else vazio
        fora = dica_da_barra_fora(nome, processo)
        faixa = (faixa_do_livre_html(livre_op, livre or LivreAoVivo(), gestao, fora=fora)
                 if livre_op else "")
        return _arranjo_c(nome, ajustes, mod=mod, agora=agora, estado=estado, parar=parar,
                          processo=processo, porque=porque, faixa=faixa, gestao=gestao)
    corpo = _cartoes_das_opcoes(opcoes) if opcoes else vazio
    fecha = _o_fecho(mod)
    return f'''    <div class="tn-topo">
      <span class="tn-tit">Configurar · {_e(nome)}</span>
      <span class="pc-para"><span class="ext-rot">Para</span>Todos</span>{parar}
      <a class="tn-x" href="#" data-dica="Fechar"{fecha}>\u00d7</a>
    </div>
    <div class="tn-corpo">
      {corpo}
    </div>
    <div class="tn-rod">
      <a class="btn" href="#"{fecha}>Cancelar</a>
      <a class="btn roxo" href="#" data-gesto="{GESTO_DO_GUARDAR}" data-v="{_a(mod)}">Guardar</a>
    </div>'''


class JogoDaLista(NamedTuple):
    """Uma linha da janela «Criar perfis»: a chave que o gesto leva, o nome e se já tem perfil."""

    chave: str
    nome: str
    tem: bool = False


def lista_de_jogos_html(jogos: Sequence[JogoDaLista]) -> str:
    """A lista da janela «Criar perfis»: um «Criar» por jogo que ainda não tem perfil."""
    itens = []
    for jogo in jogos:
        fim = ('<span class="cj-tem">Tem perfil</span>' if jogo.tem else
               f'<button class="btn mini" data-gesto="criar-perfil-do-jogo" '
               f'data-v="{_a(jogo.chave)}">Criar</button>')
        itens.append(f'<li><span class="cj-nome">{_e(jogo.nome)}</span>{fim}</li>')
    return '<ul class="cj-lista">' + "".join(itens) + "</ul>"


SEM_JOGOS = "Nenhum jogo aqui ainda. Quando houver, eles aparecem nesta lista."


def escolha_miolo_html(nome: str, jogos: Sequence[JogoDaLista], *, desenho: bool = False) -> str:
    """O conteúdo da janela «Criar perfis · <lançador>».

    ``desenho`` acende o que o desenho aprovado tem e o produto ainda não atende («Criar para todos»).
    """
    lista = lista_de_jogos_html(jogos) if jogos else f'<div class="ext-vazia">{SEM_JOGOS}</div>'
    busca = '<input class="cj-busca" type="text" placeholder="Procurar um jogo">' if jogos else ""
    todos = '\n      <a class="btn roxo" href="#">Criar para todos</a>' if desenho else ""
    return f'''    <div class="tn-topo">
      <span class="tn-tit" data-dica="Cada jogo ganha um perfil que entra sozinho">Criar perfis · {_e(nome)}</span>
      <a class="tn-x" href="#" data-dica="Fechar">\u00d7</a>
    </div>
    <div class="tn-corpo">
      {busca}
      {lista}
    </div>
    <div class="tn-rod">
      <a class="btn" href="#">Fechar</a>{todos}
    </div>'''


class Conf(NamedTuple):
    """O que a janela «Configurar» diz de um lançador."""

    chave: str
    nome: str
    entrou: str
    onde: str
    jogos: str
    impedimentos: int | None = None
    pastas: tuple[str, ...] = ()
    perfil_por_jogo: bool | None = None
    modificacao: str = ""
    menu: str = ""


GESTO_DE_ESCOLHER = "escolher-o-lancador"
GESTO_DO_GUARDAR_LANCADOR = "guardar-lancador"
CAMPO_DO_PERFIL = "perfil-por-jogo"
ROTULO_DE_ESCOLHER = "Escolher o arquivo…"


def _linha_conf(rotulo: str, valor: str) -> str:
    return f'<div class="lc-linha"><span>{_e(rotulo)}</span><span class="lc-val">{valor}</span></div>'


def _perfil_por_jogo(ligado: bool) -> str:
    classe, texto = ("nj-tog ligado", "Ligado") if ligado else ("nj-tog", "Desligado")
    return ('<div class="lc-linha"><span data-dica="O perfil entra sozinho quando o jogo abre">'
            'Cada jogo ganha o seu perfil</span><span class="lc-val">'
            f'<span class="{classe}" data-on="Ligado" data-off="Desligado" data-linha="{CAMPO_DO_PERFIL}">'
            f'<span class="pino"></span><span class="txt">{texto}</span></span></span></div>')


def _mais_da_conf(c: Conf) -> str:
    """O ⋮ do topo da janela: o mesmo menu da linha da extensão; no que vem com o Hefesto, apagado."""
    if c.modificacao:
        botao = (f'<button class="ext-mais" data-gesto="mais-da-modificacao" data-v="{_a(c.modificacao)}" '
                 f'data-onde="{ONDE_DA_CONF}" data-dica="Atualizar, ver as permissões ou remover">⋮</button>')
        if not c.menu:
            return botao
        return f'{botao}<div class="ext-menu ext-pop aberto" data-menu="{_a(c.modificacao)}">{c.menu}</div>'
    classe = "ext-menu ext-pop aberto" if c.menu else "ext-menu ext-pop"
    return (f'<button class="ext-mais" data-gesto="mais-da-modificacao" data-v="{_a(c.chave)}" '
            'data-dica="Vem com o Hefesto: não se atualiza nem se remove">⋮</button>'
            f'<div class="{classe}">{menu_html(c.chave, apagado=True)}</div>')


def lanc_conf_miolo_html(c: Conf) -> str:
    """O conteúdo da janela «Configurar · <lançador>», no arranjo aprovado em 19/10.

    Onde ele está (com o «Escolher o arquivo…», menos no lançador de extensão), as pastas dos jogos,
    os impedimentos, a chave do perfil por jogo e o Cancelar/Guardar; o ⋮ fica no topo.
    """
    linhas = [_linha_conf("Como entrou", _e(c.entrou))]
    escolher = ("" if c.modificacao else
                f'<button class="btn mini" data-gesto="{GESTO_DE_ESCOLHER}" data-v="{_a(c.chave)}">'
                f"{ROTULO_DE_ESCOLHER}</button>")
    if c.onde or escolher:
        onde = f"<code data-dica=\"{_a(c.onde)}\">{_e(c.onde)}</code>" if c.onde else ""
        linhas.append(_linha_conf("Onde ele está", onde + escolher))
    if c.pastas:
        pastas = "".join(f"<code>{_e(x)}</code>" for x in c.pastas)
        contagem = f"<small>{_e(c.jogos)}</small>" if c.jogos else ""
        linhas.append(_linha_conf("Pastas dos jogos", pastas + contagem))
    elif c.jogos:
        linhas.append(_linha_conf("Jogos", f"<small>{_e(c.jogos)}</small>"))
    if c.impedimentos is not None:
        if c.impedimentos:
            frase = (f"{c.impedimentos} jogo não recebe gatilhos e vibração" if c.impedimentos == 1
                     else f"{c.impedimentos} jogos não recebem gatilhos e vibração")
            valor = (f'<small>{frase}</small><a class="btn mini" href="#impedimentos" '
                     f'data-gesto="ver-impedimentos" data-v="{_a(c.chave)}">Ver e resolver</a>')
        else:
            valor = ('<small>Nenhum jogo com impedimento</small><a class="btn mini" href="#impedimentos" '
                     f'data-gesto="ver-impedimentos" data-v="{_a(c.chave)}">Conferir de novo</a>')
        linhas.append(_linha_conf("Impedimentos", valor))
    if c.perfil_por_jogo is not None:
        linhas.append(_perfil_por_jogo(c.perfil_por_jogo))
    corpo = "\n      ".join(linhas)
    return f'''    <div class="tn-topo">
      <span class="tn-tit">Configurar · {_e(c.nome)}</span>
      {_mais_da_conf(c)}
      <a class="tn-x" href="#" data-dica="Fechar">\u00d7</a>
    </div>
    <div class="tn-corpo">
      {corpo}
    </div>
    <div class="tn-rod">
      <a class="btn" href="#">Cancelar</a>
      <a class="btn roxo" href="#" data-gesto="{GESTO_DO_GUARDAR_LANCADOR}" data-hef-forma="lanc-janela" data-v="{_a(c.chave)}">Guardar</a>
    </div>'''


class LinhaDeImpedimento(NamedTuple):
    chave: str
    jogo: str
    frase: str
    botao: str


def impedimentos_miolo_html(nome: str, linhas: Sequence[LinhaDeImpedimento]) -> str:
    """O conteúdo da janela dos impedimentos: uma linha por jogo e a cura de cada um."""
    if linhas:
        corpo = "\n      ".join(
            _linha_conf(i.jogo, f'<small>{_e(i.frase)}</small><a class="btn mini" href="#impedimentos" '
                                f'data-gesto="resolver-impedimento" data-v="{_a(i.chave)}">{_e(i.botao)}</a>')
            for i in linhas)
        titulo = (f"{nome} · {len(linhas)} jogo com impedimento" if len(linhas) == 1
                  else f"{nome} · {len(linhas)} jogos com impedimento")
        todos = (f'<a class="btn roxo" href="#impedimentos" data-gesto="resolver-todos-os-impedimentos">'
                 f"{'Resolver o jogo' if len(linhas) == 1 else 'Resolver os ' + _numero(len(linhas))}</a>")
    else:
        corpo = '<div class="ext-vazia">Nenhum jogo com impedimento.</div>'
        titulo, todos = f"{nome} · sem impedimentos", ""
    return f'''    <div class="tn-topo">
      <span class="tn-tit">{_e(titulo)}</span>
      <a class="tn-x" href="#" data-dica="Fechar">\u00d7</a>
    </div>
    <div class="tn-corpo">
      {corpo}
    </div>
    <div class="tn-rod">
      <a class="btn" href="#">Fechar</a>
      {todos}
    </div>'''


def _numero(n: int) -> str:
    return {2: "dois", 3: "três", 4: "quatro", 5: "cinco"}.get(n, str(n))


CONF_DE_EXEMPLO = Conf("steam", "Steam", "Do sistema", "~/.steam/steam", "48 jogos", 2,
                       ("~/Jogos/SteamLibrary",), True)
IMPEDIMENTOS_DE_EXEMPLO = (
    LinhaDeImpedimento("entrada:1", "Sackboy: A Big Adventure",
                       "O Steam Input está ligado: o jogo vê um controle de Xbox", "Desligar o Steam Input"),
    LinhaDeImpedimento("proton:2", "Resident Evil Village",
                       "Fora do Proton fixado: a vibração e os gatilhos não chegam", "Usar o Proton fixado"),
)


JOGOS_DA_STEAM = (
    JogoDaLista("steam_app_1", "Sackboy: A Big Adventure", True),
    JogoDaLista("steam_app_2", "Resident Evil Village"),
    JogoDaLista("steam_app_3", "Mortal Kombat 1", True),
    JogoDaLista("steam_app_4", "Hades II"),
    JogoDaLista("steam_app_5", "Hollow Knight: Silksong"),
)


def _fragmento(nome: str) -> str:
    return (_PASTA / f"{nome}.html").read_text(encoding="utf-8")


JANELAS = ("novo-lancador", "escolher-jogo", "impedimentos", "lanc-conf",
           "modificacao")  # (noqa-acento)


def telas() -> str:
    """Todas as janelas da aba, em ordem, prontas para entrar antes do fim da página."""
    partes = []
    for nome in JANELAS:
        texto = _fragmento(nome)
        texto = texto.replace("{{ESCOLHA}}", escolha_miolo_html("Steam", JOGOS_DA_STEAM, desenho=True))
        texto = texto.replace("{{CONF}}", lanc_conf_miolo_html(CONF_DE_EXEMPLO))
        texto = texto.replace("{{IMPEDIMENTOS}}", impedimentos_miolo_html("Steam", IMPEDIMENTOS_DE_EXEMPLO))
        texto = texto.replace("{{MODIFICACAO}}", modificacao_miolo_html(
            "Minha extensão", OPCOES_DO_DESENHO_DAS_PECAS, mod="exemplo", agora=AGORA_DO_DESENHO,
            estado=ESTADO_DOS_GERIDOS_DO_DESENHO, parar_tudo=True, acoes=ACOES_DO_DESENHO,
            aparelhos=APARELHOS_DO_DESENHO, em_curso=frozenset({("testar", "ap-2")}),
            livre=LIVRE_DO_DESENHO, controles=CONTROLES_DO_DESENHO))
        partes.append(texto.strip())
    return ("\n".join(partes) + f"\n{sprite_dos_botoes()}"
            f"\n<script data-aba=\"experimental\">\n{SCRIPT}</script>\n")


class AcaoDaJanela(NamedTuple):
    """Uma ação do manifesto: o botão que age na hora, sem rascunho e sem «Guardar»."""

    id: str
    rotulo: str
    grupo: str = ""
    icone: str = ""


class AparelhosDaJanela(NamedTuple):
    """As ações de cada aparelho gerido e a aba em que a lista mora (sem ela, a coluna «Agora»)."""

    acoes: tuple[AcaoDaJanela, ...]
    grupo: str = ""


class LivreAoVivo(NamedTuple):
    """O que a faixa do controle livre mostra agora: o valor, se grava e o rastro dos últimos
    segundos, como (instante, valor de 0 a 1), com ``agora`` no mesmo relógio."""

    valor: float = 0.0
    gravando: bool = False
    rastro: tuple[tuple[float, float], ...] = ()
    agora: float = 0.0


class Gestao(NamedTuple):
    """A lista dos aparelhos geridos de uma extensão, pronta para virar cartões ou linhas."""

    mod: str
    aparelhos: AparelhosDaJanela
    estado: Mapping[str, Any] | None
    em_curso: frozenset[tuple[str, str]] = frozenset()


GESTO_DA_ACAO = "acao-da-modificacao"
GESTO_DO_LIVRE = "mover-o-livre-da-modificacao"
GESTO_DE_SOLTAR = "soltar-o-livre-da-modificacao"
GESTO_DE_GRAVAR = "gravar-o-livre-da-modificacao"
GESTO_DE_ESQUECER_A_FORMA = "esquecer-a-forma-do-livre"
GESTO_DO_MODO = "modo-do-livre-da-modificacao"
MODOS_DA_FAIXA = (
    ("soltar", "Volta a zero ao soltar", "M10 3v10M6 9l4 4 4-4M4 17h12"),
    ("segurar", "Fica onde parou", "M5 9h10v8H5zM7 9V6.5a3 3 0 0 1 6 0V9"),
    ("repetir", "Repete o que você desenhou",
     "M4 10a6 6 0 0 1 10.2-4.2M14.5 3v3h-3M16 10a6 6 0 0 1-10.2 4.2M5.5 17v-3h3"))
ACAO_DE_LIGAR = "ligar"
EM_CURSO = "Em curso"
DICA_DA_CHAVE = "Liga ou desliga este aparelho"
DICA_DO_GRAVAR = "Grava o que você arrastar como uma forma nova, para os botões do controle"
DICA_DA_BARRA_FORA = "{nome} não está rodando: a barra não chega a ela."
CAMPO_DA_BARRA_FORA = "mod-livre-fora"


def dica_da_barra_fora(nome: str, processo: str) -> str:
    """A dica da barra do livre fora da porta, ou vazio na porta: a regra da montagem e do tique."""
    return DICA_DA_BARRA_FORA.format(nome=nome) if processo in PROCESSO else ""

RASTRO_S = 10.0
_TRACO_DA_ACAO = ('viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" '
                  'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"')
ICONE_DA_ACAO = {
    "procurar": '<circle cx="7" cy="7" r="4.5"/><line x1="10.5" y1="10.5" x2="14" y2="14"/>',
    "testar": '<path d="M1 8 Q3 3 5 8 T9 8 T13 8 T15 8"/>',
    "esquecer": '<path d="M3 4.5h10M6 4.5V3h4v1.5M4.5 4.5l.7 9h5.6l.7-9"/>',
    "ligar": '<path d="M8 2v6"/><path d="M4.6 4.6a5 5 0 1 0 6.8 0"/>',
    "atualizar": '<path d="M13 8a5 5 0 1 1-1.5-3.6"/><polyline points="13,2 13,5 10,5"/>',
}


def _icone_da_acao(icone: str) -> str:
    desenho = ICONE_DA_ACAO.get(icone, "")
    return f"<svg {_TRACO_DA_ACAO}>{desenho}</svg>" if desenho else ""


def valor_da_acao(mod: str, acao_id: str, alvo: str = "") -> str:
    """O ``data-v`` do botão de ação, o mesmo no cartão e na linha: ``mod:ação`` e, num aparelho,
    ``:alvo``."""
    return f"{mod}:{acao_id}" + (f":{alvo}" if alvo else "")


def acao_html(mod: str, acao: AcaoDaJanela, *, alvo: str = "", em_curso: bool = False,
              forte: bool = False) -> str:
    """Um botão de ação (:func:`valor_da_acao`). Enquanto a extensão não devolve o estado, ele diz
    «Em curso»."""
    v = valor_da_acao(mod, acao.id, alvo)
    classe = "btn mj-acao" + (" forte" if forte else "") + (" em-curso" if em_curso else "")
    ocupado = ' aria-busy="true"' if em_curso else ""
    return (f'<button class="{classe}" data-gesto="{GESTO_DA_ACAO}" data-v="{_a(v)}"{ocupado}>'
            f'{_icone_da_acao(acao.icone)}<span>{EM_CURSO if em_curso else _e(acao.rotulo)}</span>'
            "</button>")


def barra_de_acoes_html(mod: str, acoes: Sequence[AcaoDaJanela],
                        em_curso: frozenset[tuple[str, str]] = frozenset()) -> str:
    """As ações de uma aba, numa fileira; a primeira é a forte."""
    return "".join(acao_html(mod, a, em_curso=(a.id, "") in em_curso, forte=n == 0)
                   for n, a in enumerate(acoes))


def _aparelhos_geridos(estado: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Os aparelhos do estado que têm ``id``: só eles recebem gesto."""
    return [ap for ap in itens_do_estado(estado, "aparelhos")
            if isinstance(ap.get("id"), str) and ap.get("id")]


def _chave_do_aparelho(g: Gestao, ap: Mapping[str, Any]) -> str:
    """A chave do cartão, quando o manifesto declara ``ligar``: o clique pede o contrário."""
    if not any(a.id == ACAO_DE_LIGAR for a in g.aparelhos.acoes):
        return ""
    ligado = ap.get("ligado") is not False
    em_curso = (ACAO_DE_LIGAR, str(ap["id"])) in g.em_curso
    classe = "mj-chave" + (" on" if ligado else "") + (" em-curso" if em_curso else "")
    v = valor_da_acao(g.mod, ACAO_DE_LIGAR, str(ap["id"]))
    return (f'<span class="{classe}" role="switch" aria-checked="{"true" if ligado else "false"}" '
            f'data-gesto="{GESTO_DA_ACAO}" data-v="{_a(v)}" '
            f'data-ligado="{"0" if ligado else "1"}" data-dica="{DICA_DA_CHAVE}"></span>')


def _botoes_do_aparelho(g: Gestao, ap: Mapping[str, Any]) -> str:
    alvo = str(ap["id"])
    return "".join(acao_html(g.mod, a, alvo=alvo, em_curso=(a.id, alvo) in g.em_curso)
                   for a in g.aparelhos.acoes if a.id != ACAO_DE_LIGAR)


def _por_cento(bateria: Any) -> str:
    if isinstance(bateria, bool) or not isinstance(bateria, int):
        return ""
    return f'<span class="mj-pct">{max(0, min(100, bateria))}%</span>'


def aparelhos_geridos_html(g: Gestao) -> str:
    """Os cartões dos aparelhos geridos, dois por fileira: o nome, a pilha, a chave, a força de
    agora e um botão por ação. O aparelho desligado fica apagado e segue com as ações."""
    cartoes = []
    for ap in _aparelhos_geridos(g.estado):
        estado = str(ap.get("estado") or "ligado")
        vivo = _forca_html(ap.get("forca")) if estado == "ligado" else estado_html(estado)
        fora = "" if ap.get("ligado") is not False else " fora"
        cartoes.append(
            f'<div class="mj-ap{fora}" data-alvo="{_a(ap["id"])}"><div class="mj-ap-cab">'
            f'{icone_html(ICONE_DO_APARELHO, "acessorio" if estado == "ligado" else "mudo")}'
            f'<span class="mj-ap-nome">{_e(ap.get("nome") or ap["id"])}</span>'
            f'{bateria_html(ap.get("bateria"))}{_por_cento(ap.get("bateria"))}'
            f'{_chave_do_aparelho(g, ap)}</div>'
            f'<div class="mj-ap-meio">{vivo}</div>'
            f'<div class="mj-ap-pe">{_botoes_do_aparelho(g, ap)}</div></div>')
    busca = ANDAMENTO_DO_PAREAR.ver(g.mod, g.estado)
    if not cartoes:
        return busca.html(vazio=True) or f'<div class="mj-ap-vazio">{SEM_APARELHOS}</div>'
    return busca.html(vazio=False) + "".join(cartoes)


SEM_APARELHOS = "Nenhum aparelho por aqui ainda."
COMECO_DO_MOTIVO_DA_BUSCA = "Procurando"
CHAVE_DAS_CONEXOES = "conexoes"  # (noqa-acento)
PRAZO_DA_BUSCA_S = 20.0
SILENCIO_QUE_ENCERRA_A_BUSCA_S = 5.0
FIM_DA_BUSCA_VISIVEL_S = 12.0
SEM_RAZAO_DA_BUSCA = "Ligue o aparelho e deixe-o perto."


class Andamento(NamedTuple):
    """O que a janela diz do «Parear» agora: ``busca`` (os segundos que faltam, ``None`` passado o
    prazo) ou o fim dela (``achou``, os nomes; ``razao``, a dica quando não achou nenhum)."""

    fase: str = ""
    restam: int | None = None
    achou: tuple[str, ...] = ()
    razao: str = ""

    def html(self, *, vazio: bool) -> str:
        """A faixa do andamento; vazia quando não há busca nem fim a mostrar. Sem aparelho, ela é a
        própria linha do aviso (``mj-ap-vazio``) e divide a linha do Parear."""
        if not self.fase:
            return ""
        if self.fase == "busca":
            corpo = ('<span class="est est-amarelo"><i></i>Procurando aparelhos</span>'
                     + (f'<span class="mj-busca-resta">{self.restam} s</span>'
                        if self.restam is not None else ""))
            dica = ""
        elif self.achou:
            corpo = f'<span class="mj-busca-fim">Achou {_e(", ".join(self.achou))}</span>'
            dica = ""
        else:
            corpo = '<span class="mj-busca-fim">Não achou nenhum aparelho</span>'
            dica = f' data-dica="{_a(self.razao)}"'
        classe = "mj-busca" + (" mj-ap-vazio" if vazio else "") + f" mj-busca-{self.fase}"
        return f'<div class="{classe}" role="status"{dica}>{corpo}</div>'


class AndamentoDoPareamento:
    """O dono do andamento do «Parear» de cada extensão, lido do estado que ela devolve: a busca
    começa quando uma conexão «procurando» tem o motivo começado por
    :data:`COMECO_DO_MOTIVO_DA_BUSCA` e termina quando ela deixa de tê-lo. O fim fica à vista
    :data:`FIM_DA_BUSCA_VISIVEL_S`, com o que apareceu de novo ou a razão."""

    def __init__(self, relogio: Callable[[], float] = time.monotonic) -> None:
        self._relogio = relogio
        self._trava = threading.Lock()
        self._buscas: dict[str, tuple[float, frozenset[str], float]] = {}
        self._fins: dict[str, tuple[float, Andamento]] = {}

    def limpar(self) -> None:
        with self._trava:
            self._buscas.clear()
            self._fins.clear()

    @staticmethod
    def _procurando(estado: Mapping[str, Any] | None) -> bool:
        return any(c.get("estado") == "procurando"
                   and str(c.get("motivo") or "").startswith(COMECO_DO_MOTIVO_DA_BUSCA)
                   for c in itens_do_estado(estado, CHAVE_DAS_CONEXOES))

    @staticmethod
    def _nomes(estado: Mapping[str, Any] | None) -> dict[str, str]:
        return {str(ap.get("id") or ap.get("nome")): str(ap.get("nome") or ap.get("id"))
                for ap in itens_do_estado(estado, "aparelhos")}

    @staticmethod
    def _razao(estado: Mapping[str, Any] | None) -> str:
        motivos = [f'{c.get("tipo") or "Conexão"}: {c.get("motivo") or PALAVRA_DO_ESTADO[c["estado"]]}'
                   for c in itens_do_estado(estado, CHAVE_DAS_CONEXOES)
                   if c.get("estado") in ("falhou", "procurando")]
        return ". ".join(motivos) + "." if motivos else SEM_RAZAO_DA_BUSCA

    def ver(self, mod: str, estado: Mapping[str, Any] | None) -> Andamento:
        agora = self._relogio()
        with self._trava:
            procurando = self._procurando(estado)
            nomes = self._nomes(estado)
            visto = self._buscas.get(mod)
            if visto is not None and agora - visto[2] > SILENCIO_QUE_ENCERRA_A_BUSCA_S:
                del self._buscas[mod]
            if procurando:
                desde, antes, _ = self._buscas.get(mod, (agora, frozenset(nomes), agora))
                self._buscas[mod] = (desde, antes, agora)
                self._fins.pop(mod, None)
                restam = PRAZO_DA_BUSCA_S - (agora - desde)
                return Andamento("busca", max(0, math.ceil(restam)) if restam > 0 else None)
            if mod in self._buscas:
                _, antes, _ = self._buscas.pop(mod)
                novos = tuple(n for i, n in nomes.items() if i not in antes)
                self._fins[mod] = (agora, Andamento(
                    "fim", None, novos, "" if novos else self._razao(estado)))
            quando, fim = self._fins.get(mod, (0.0, Andamento()))
            if fim.fase and agora - quando <= FIM_DA_BUSCA_VISIVEL_S:
                return fim
            self._fins.pop(mod, None)
            return Andamento()


ANDAMENTO_DO_PAREAR = AndamentoDoPareamento()


def aparelhos_na_coluna_html(g: Gestao) -> str:
    """Os aparelhos geridos na coluna «Agora» (o manifesto sem ``grupo``): uma linha por aparelho,
    com a chave e as ações em ícone."""
    linhas = []
    for ap in itens_do_estado(g.estado, "aparelhos"):
        if not (isinstance(ap.get("id"), str) and ap.get("id")):
            linhas.append(_aparelho_html(ap))
            continue
        alvo = str(ap["id"])
        botoes = "".join(
            f'<button class="btn ico mj-acao{" em-curso" if (a.id, alvo) in g.em_curso else ""}" '
            f'data-gesto="{GESTO_DA_ACAO}" data-v="{_a(valor_da_acao(g.mod, a.id, alvo))}" '
            f'data-dica="{_a(a.rotulo)}" aria-label="{_a(a.rotulo)}">'
            f'{_icone_da_acao(a.icone) or _e(a.rotulo[:1])}</button>'
            for a in g.aparelhos.acoes if a.id != ACAO_DE_LIGAR)
        fora = "" if ap.get("ligado") is not False else " fora"
        nome = str(ap.get("nome") or alvo)
        linhas.append(
            f'<div class="ap mj-ap-linha{fora}" data-alvo="{_a(alvo)}">'
            f'{icone_html(ICONE_DO_APARELHO, "acessorio")}'
            f'<span class="ap-nome" data-dica="{_a(nome)}">{_e(nome)}</span>'
            f'{bateria_html(ap.get("bateria"))}{botoes}{_chave_do_aparelho(g, ap)}</div>')
    return "".join(linhas)


ROTULO_DA_PALETA = "Cor"


def com_controles(estado: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Os aparelhos geridos que publicaram ``controles``: só eles ganham cartão."""
    return [ap for ap in _aparelhos_geridos(estado) if ap.get("controles")]


def _fundo_do_ponto(cor: Any) -> str:
    """A cor do ponto da paleta; a lista de duas ou três vira fatias iguais, como no arranjo C."""
    cores = [c for c in (cor if isinstance(cor, list) else [cor])
             if isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", c)]
    if len(cores) < 2:
        return cores[0] if cores else "transparent"
    passo = 360 // len(cores)
    fatias = ",".join(f"{c} 0 {passo * (n + 1)}deg" if n + 1 < len(cores) else f"{c} 0"
                      for n, c in enumerate(cores))
    return f"conic-gradient({fatias})"


def _pedido_do_controle(mod: str, alvo: str, c: Mapping[str, Any], quer: str) -> str:
    """O gesto de um controle: a ação é o ``id`` dele, o ``alvo`` é o aparelho e ``data-quer`` é o
    valor pedido (``1``/``0`` na chave, o ``id`` da opção nas outras)."""
    return (f'data-gesto="{GESTO_DA_ACAO}" data-v="{_a(valor_da_acao(mod, str(c["id"]), alvo))}" '
            f'data-quer="{_a(quer)}"')


def _chave_do_controle(mod: str, alvo: str, c: Mapping[str, Any], em_curso: bool) -> str:
    ligada = c.get("valor") is True
    classe = "mj-chave" + (" on" if ligada else "") + (" em-curso" if em_curso else "")
    dica = str(c.get("dica") or c.get("rotulo") or "")
    atributo = f' data-dica="{_a(dica)}"' if dica else ""
    return (f'<span class="{classe}" role="switch" aria-checked="{str(ligada).lower()}" '
            f'{_pedido_do_controle(mod, alvo, c, "0" if ligada else "1")}{atributo}></span>')


def _botoes_do_controle(mod: str, alvo: str, c: Mapping[str, Any], opcoes: Sequence[Any]) -> str:
    botoes = []
    for op in opcoes:
        aceso = op["id"] == c.get("valor")
        if c["tipo"] == "paleta":
            miolo = f'<i style="background:{_fundo_do_ponto(op.get("cor"))}"></i>'
            dica = str(op.get("rotulo") or op["id"])
        else:
            miolo, dica = _e(op.get("rotulo") or op["id"]), ""
        atributo = f' data-dica="{_a(dica)}"' if dica else ""
        classe = ' class="on"' if aceso else ""
        botoes.append(f'<button{classe} aria-pressed="{str(aceso).lower()}" '
                      f'{_pedido_do_controle(mod, alvo, c, str(op["id"]))}{atributo}>{miolo}</button>')
    return "".join(botoes)


def _linha_do_controle(mod: str, alvo: str, c: Mapping[str, Any], em_curso: bool) -> str:
    """Uma linha do cartão: o rótulo e o controle. A paleta põe as cores de um ponto numa fileira
    e as de dois ou três noutra, como no arranjo C."""
    rotulo = str(c.get("rotulo")
                 or (ROTULO_DA_PALETA if c["tipo"] == "paleta" else ""))
    if c["tipo"] == "chave":
        miolo = _chave_do_controle(mod, alvo, c, em_curso)
    else:
        opcoes = list(c.get("opcoes") or [])  # (noqa-acento)
        fileiras = ([[o for o in opcoes if not isinstance(o.get("cor"), list)],
                     [o for o in opcoes if isinstance(o.get("cor"), list)]]
                    if c["tipo"] == "paleta" else [opcoes])
        classe = "mj-cores" + (" mj-pontos" if c["tipo"] == "paleta" else "") + (
            " em-curso" if em_curso else "")
        miolo = "".join(f'<span class="{classe}" role="group">'
                        f"{_botoes_do_controle(mod, alvo, c, f)}</span>" for f in fileiras if f)
    dica = f' data-dica="{_a(c["dica"])}"' if c.get("dica") and c["tipo"] != "chave" else ""
    return (f'<div class="mj-cc-linha" data-controle-do-aparelho="{_a(c["id"])}"{dica}>'
            f'<span class="mj-cc-rot">{_e(rotulo)}</span>'
            f'<span class="mj-cc-ctrl">{miolo}</span></div>')


def controles_dos_aparelhos_html(mod: str, estado: Mapping[str, Any] | None,
                                 em_curso: frozenset[tuple[str, str]] = frozenset()) -> str:
    """Um cartão por aparelho com ``controles``: o nome e, à direita, a primeira chave; embaixo,
    uma linha por controle. O desligado fica apagado; o aparelho sem controles não ganha cartão."""
    cartoes = []
    for ap in com_controles(estado):
        alvo = str(ap["id"])
        controles = list(ap["controles"])
        cabeca = next((c for c in controles if c["tipo"] == "chave"), None)
        chave = (_chave_do_controle(mod, alvo, cabeca, (str(cabeca["id"]), alvo) in em_curso)
                 if cabeca else "")
        linhas = "".join(_linha_do_controle(mod, alvo, c, (str(c["id"]), alvo) in em_curso)
                         for c in controles if c is not cabeca)
        fora = "" if ap.get("ligado") is not False else " fora"
        cartoes.append(
            f'<div class="mj-ap mj-cc{fora}" data-alvo="{_a(alvo)}"><div class="mj-ap-cab">'
            f'{icone_html(ICONE_DO_APARELHO, "acessorio")}'
            f'<span class="mj-ap-nome">{_e(ap.get("nome") or alvo)}</span>{chave}</div>'
            f"{linhas}</div>")
    return "".join(cartoes)


def _grupos_com_as_pecas(opcoes: Sequence[OpcaoDaJanela], acoes: Sequence[AcaoDaJanela],
                         aparelhos: AparelhosDaJanela | None, controles: str = "") -> list[str]:
    """As abas na ordem: a dos aparelhos, as das ações, as das opções e, por último, a dos
    controles dos aparelhos (só quando algum os tem), como a Luz no arranjo C; se ela é a aba de
    uma opção, fica no lugar daquela."""
    nomes = [aparelhos.grupo if aparelhos else "", *(a.grupo for a in acoes),
             *(o.grupo for o in opcoes), controles]
    ordem = list(dict.fromkeys(n for n in nomes if n))
    return ordem or ["Opções"]


def _abas_com_as_pecas(opcoes: Sequence[OpcaoDaJanela], aba: str, *, mod: str,
                       acoes: Sequence[AcaoDaJanela], gestao: Gestao | None,
                       controles: tuple[str, str] = ("", "")) -> str:
    """As abas do arranjo C com as ações e a lista dos aparelhos geridos.

    Cada aba é: a fileira das ações dela (``#mod-acoes-<n>``), a lista dos aparelhos se ela é a do
    ``grupo`` deles (``#mod-aparelhos``), os cartões dos controles se ela é a do ``grupo`` deles
    (``#mod-controles``; ``controles`` é o par aba e cartões, a aba vazia quando nenhum aparelho
    os tem) e as linhas das opções. A ação sem ``grupo`` vai à primeira aba, como a opção sem
    grupo. A ponte repinta os blocos a cada tique, e a aba não pula. Ações e aparelhos da mesma
    aba moram na caixa ``.mj-sec``: o aviso de lista vazia divide a linha com o botão.
    """
    nomes = _grupos_com_as_pecas(opcoes, acoes, gestao.aparelhos if gestao else None,
                                 controles[0])
    primeiro = nomes[0]
    por_aba: dict[str, list[OpcaoDaJanela]] = {n: [] for n in nomes}
    for o in opcoes:
        por_aba[o.grupo or primeiro].append(o)
    acoes_da: dict[str, list[AcaoDaJanela]] = {n: [] for n in nomes}
    for a in acoes:
        acoes_da[a.grupo or primeiro].append(a)
    aberta = aba if aba in por_aba else primeiro
    em_curso = gestao.em_curso if gestao else frozenset()
    telas = []
    for n, nome in enumerate(nomes):
        partes = []
        fileira = ""
        if acoes_da[nome]:
            fileira = (f'<div class="mj-acoes" id="mod-acoes-{n}">'
                       f"{barra_de_acoes_html(mod, acoes_da[nome], em_curso)}</div>")
        lista = (f'<div class="mj-aps" id="mod-aparelhos">{aparelhos_geridos_html(gestao)}</div>'
                 if gestao and gestao.aparelhos.grupo == nome else "")
        partes.append(f'<div class="mj-sec">{fileira}{lista}</div>' if fileira and lista
                      else fileira + lista)
        if controles[0] and controles[0] == nome:
            partes.append(f'<div class="mj-aps mj-ccs" id="mod-controles">{controles[1]}</div>')
        chave, linhas = chave_da_aba(nome, por_aba[nome])
        if linhas:
            partes.append(_linhas_da_aba(n, linhas, chave))
        telas.append(
            f'<input type="radio" name="mj-aba" id="mj-aba-{n}"{" checked" if nome == aberta else ""}>'
            f'<label for="mj-aba-{n}">{_e(nome)}{_bolinha_da_aba(n, chave)}</label>'
            f'<div class="mj-tela" id="{PEDACO}tela-{n}">{"".join(partes)}</div>')
    return f'<div class="ac-card mj-abas" style="--n:{len(nomes)}">{"".join(telas)}</div>'


def acoes_por_aba(opcoes: Sequence[OpcaoDaJanela], acoes: Sequence[AcaoDaJanela],
                  aparelhos: AparelhosDaJanela | None,
                  controles: str = "") -> dict[int, tuple[AcaoDaJanela, ...]]:
    """As ações de cada aba pelo número dela, o mesmo de ``#mod-acoes-<n>``: quem repinta usa.
    ``controles`` é a aba dos controles dos aparelhos, só quando algum os tem."""
    nomes = _grupos_com_as_pecas(opcoes, acoes, aparelhos, controles)
    return {n: tuple(a for a in acoes if (a.grupo or nomes[0]) == nome)
            for n, nome in enumerate(nomes) if any((a.grupo or nomes[0]) == nome for a in acoes)}


def _y_do_rastro(v: float) -> str:
    return f"{96 - 92 * max(0.0, min(1.0, v)):.1f}"


def rastro_html(vivo: LivreAoVivo) -> str:
    """O rastro dos últimos ``RASTRO_S`` segundos do controle livre, em degraus: cada valor vale
    até o seguinte, e a linha fica vermelha enquanto grava."""
    inicio = vivo.agora - RASTRO_S
    antes = [v for t, v in vivo.rastro if t < inicio]
    atual = antes[-1] if antes else (0.0 if vivo.rastro else vivo.valor)
    pontos = [f"0,{_y_do_rastro(atual)}"]
    for t, v in vivo.rastro:
        if t < inicio:
            continue
        x = f"{(t - inicio) / RASTRO_S * 1000:.0f}"
        pontos += [f"{x},{_y_do_rastro(atual)}", f"{x},{_y_do_rastro(v)}"]
        atual = v
    pontos.append(f"1000,{_y_do_rastro(atual)}")
    classe = "mj-rastro gravando" if vivo.gravando else "mj-rastro"
    return (f'<svg class="{classe}" viewBox="0 0 1000 100" preserveAspectRatio="none" '
            f'aria-hidden="true"><line x1="0" y1="50" x2="1000" y2="50"/>'
            f'<polyline points="{" ".join(pontos)}"/></svg>')


def alvos_do_livre_html(g: Gestao | None) -> str:
    """Quem recebe o controle livre: um chip por aparelho gerido, aceso se ligado. O clique é a
    mesma chave do cartão (a ação ``ligar``), e só aparece quando o manifesto a declara."""
    if g is None or not any(a.id == ACAO_DE_LIGAR for a in g.aparelhos.acoes):
        return ""
    chips = []
    for ap in _aparelhos_geridos(g.estado):
        ligado = ap.get("ligado") is not False
        em_curso = " em-curso" if (ACAO_DE_LIGAR, str(ap["id"])) in g.em_curso else ""
        v = valor_da_acao(g.mod, ACAO_DE_LIGAR, str(ap["id"]))
        chips.append(f'<span class="chip mj-alvo{" on" if ligado else ""}{em_curso}" '
                     f'data-gesto="{GESTO_DA_ACAO}" data-v="{_a(v)}" '
                     f'data-ligado="{"0" if ligado else "1"}" data-dica="{DICA_DA_CHAVE}">'
                     f'{_e(ap.get("nome") or ap["id"])}</span>')
    return "".join(chips)


def _formas_do_livre_html(o: OpcaoDaJanela) -> str:
    """As formas gravadas: um chip com a onda e o nome, e o «x» que a esquece (no rascunho)."""
    formas = o.valor if isinstance(o.valor, Mapping) else {}
    chips = []
    for nome, passos in formas.items():
        pares = [(float(f), float(t)) for f, t in passos]
        duracao = sum(t for _f, t in pares)
        chips.append(
            f'<span class="chip mj-forma" data-dica="{len(pares)} passos, {duracao:.1f} s">'
            f'{_onda_da_forma(pares)}<span>{_e(nome)}</span>'
            f'<button class="mj-x" data-gesto="{GESTO_DE_ESQUECER_A_FORMA}" '
            f'data-v="{_a(o.mod)}:{_a(o.id)}:{_a(nome)}" aria-label="Esquecer «{_a(nome)}»" '
            f'data-dica="Esquecer «{_a(nome)}»">\u00d7</button></span>')
    return "".join(chips)


def modos_do_livre_html(o: OpcaoDaJanela) -> str:
    """Os três modos do que a barra faz ao soltar, em glifos (a frase do efeito vai na dica e no
    ``aria-label``); aceso, o ``modo`` de agora. Sem ``modo`` (o ``livre`` sem ``modos``), nada."""
    if not o.modo:
        return ""
    aceso = ' class="on"'
    botoes = "".join(
        f'<button{aceso if valor == o.modo else ""} data-modo="{valor}" '
        f'data-gesto="{GESTO_DO_MODO}" data-v="{_a(o.mod)}:{_a(o.id)}:{valor}" '
        f'aria-pressed="{str(valor == o.modo).lower()}" aria-label="{dica}" data-dica="{dica}">'
        f'<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">'
        f'<path d="{traco}"/></svg></button>'
        for valor, dica, traco in MODOS_DA_FAIXA)
    return f'<span class="seg mj-modos" role="group" aria-label="Ao soltar">{botoes}</span>'


def faixa_do_livre_html(o: OpcaoDaJanela, vivo: LivreAoVivo, gestao: Gestao | None, *,
                        fora: str = "") -> str:
    """A faixa fixa embaixo do arranjo C: o rastro, a barra que se arrasta, os modos (com
    ``modos``), o «Gravar», quem recebe e as formas gravadas.

    A barra é um ``range``: o ``input`` é o gesto vivo (lê e manda, nunca grava; a porta segura em
    20 por segundo) e o ``change`` é o soltar, que sempre sai. O rastro e os chips de quem recebe
    são blocos próprios (``#mod-livre-rastro`` e ``#mod-livre-alvos``), repintados pelo tique sem
    tocar na barra que o dedo está arrastando. Com ``fora`` (a dica), a barra nasce apagada; o
    trilho tem o endereço ``CAMPO_DA_BARRA_FORA``, e o tique o apaga ou acende sem refazê-lo.
    """
    v = round(max(0.0, min(1.0, vivo.valor)) * 100)
    trilho = ((f'class="mj-trilho fora" data-dica="{_a(fora)}"' if fora else 'class="mj-trilho"')
              + f' data-campo="{CAMPO_DA_BARRA_FORA}" data-hef-alvo="classe"'
              ' data-hef-classe="fora" data-hef-razao="sim"')
    gravar = ("btn mj-gravar on", "true") if vivo.gravando else ("btn mj-gravar", "false")
    return f'''<div class="mj-faixa" data-livre="{_a(o.id)}">
      <div class="mj-faixa-topo"><span class="pc-sub">{_e(o.rotulo)}</span></div>
      <div class="mj-livre-rastro" id="mod-livre-rastro">{rastro_html(vivo)}</div>
      <div {trilho} style="--v:{v}"><input type="range" min="0" max="100" step="1" value="{v}" data-hef-vivo="{GESTO_DO_LIVRE}" data-gesto="{GESTO_DE_SOLTAR}" data-v="{_a(o.mod)}:{_a(o.id)}" aria-label="{_a(o.rotulo)}" oninput="this.parentNode.style.setProperty('--v',this.value);this.nextElementSibling.textContent=this.value"><output>{v}</output></div>
      <div class="mj-faixa-pe" id="{PEDACO}livre-pe">{modos_do_livre_html(o)}
        <button class="{gravar[0]}" data-gesto="{GESTO_DE_GRAVAR}" data-v="{_a(o.mod)}:{_a(o.id)}" aria-pressed="{gravar[1]}" data-dica="{DICA_DO_GRAVAR}"><i></i>Gravar</button>
        <span class="mj-alvos" id="mod-livre-alvos">{alvos_do_livre_html(gestao)}</span>
        <span class="mj-formas">{_formas_do_livre_html(o)}</span>
      </div>
    </div>'''


ACOES_DO_DESENHO = (AcaoDaJanela("parear", "Parear", "Aparelhos", "procurar"),)
APARELHOS_DO_DESENHO = AparelhosDaJanela((
    AcaoDaJanela(ACAO_DE_LIGAR, "Ligar", icone="ligar"),
    AcaoDaJanela("testar", "Testar", icone="testar"),
    AcaoDaJanela("esquecer", "Esquecer", icone="esquecer"),
), "Aparelhos")
FORMAS_GRAVADAS_DO_DESENHO = {
    "Meu 1": ((0.2, 0.4), (0.6, 0.4), (1.0, 0.6), (0.4, 0.4)),
    "Meu 2": ((0.8, 0.2), (0.0, 0.2), (0.8, 0.2), (0.0, 0.2)),
}
CORES_DO_DESENHO: tuple[tuple[str, Any, str], ...] = (
    ("vermelho", "#ff5555", "Vermelho"), ("verde", "#50fa7b", "Verde"), ("azul", "#6c8cff", "Azul"),
    ("outono", "#ffb86c", "Outono"), ("magenta", "#ff79c6", "Magenta"), ("agua", "#8be9fd", "Água"),
    ("lilas", "#bd93f9", "Lilás"),
    ("fantasia", ["#8be9fd", "#ff79c6", "#ffb86c"], "Fantasia"),
    ("brasa", ["#bd93f9", "#ffb86c", "#ff5555"], "Brasa"),
    ("neon", ["#8be9fd", "#6c8cff", "#ff5555"], "Neon"))
CONTROLES_DO_DESENHO = "Luz e vibração"
ESTADO_DOS_GERIDOS_DO_DESENHO: dict[str, Any] = {
    **ESTADO_DO_DESENHO,
    "aparelhos": [
        {"id": "ap-1", "nome": "Aparelho 1", "estado": "ligado", "ligado": True, "bateria": 80,
         "forca": 0.7, "controles": [
             {"id": "luz", "tipo": "chave", "valor": True, "dica": "Acesa"},
             {"id": "cor", "tipo": "paleta", "valor": "magenta",
              "opcoes": [{"id": i, "cor": c, "rotulo": r}  # (noqa-acento)
                         for i, c, r in CORES_DO_DESENHO]}]},
        {"id": "ap-2", "nome": "Aparelho 2", "estado": "ligado", "ligado": True, "bateria": 45,
         "forca": 0.3, "controles": [{"id": "luz", "tipo": "chave", "valor": False,
                                      "dica": "Acesa"}]},
        {"id": "ap-3", "nome": "Aparelho 3", "estado": "ligado", "ligado": True, "bateria": 62,
         "forca": 0.5},
        {"id": "ap-4", "nome": "Aparelho 4", "estado": "ligado", "ligado": False, "bateria": 18,
         "forca": 0.0},
    ],
}
OPCOES_DO_DESENHO_DAS_PECAS = (
    OPCOES_DO_DESENHO_C[0]._replace(formas=(*FORMAS_DO_DESENHO, *FORMAS_GRAVADAS_DO_DESENHO.items())),
    *OPCOES_DO_DESENHO_C[1:],
    OpcaoDaJanela("exemplo", "ao-vivo", "Ao vivo", "livre",
                  {n: [list(p) for p in f] for n, f in FORMAS_GRAVADAS_DO_DESENHO.items()},
                  modo="soltar"),
)
LIVRE_DO_DESENHO = LivreAoVivo(0.65, False, tuple(
    (t / 10, 0.35 + 0.3 * ((t % 20) / 20 if (t // 20) % 2 == 0 else 1 - (t % 20) / 20))
    for t in range(0, 100, 2)), 10.0)
