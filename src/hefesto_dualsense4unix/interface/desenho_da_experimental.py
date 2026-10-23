"""O desenho da aba Experimental (a 07): extensões, lançadores e as janelas deles.

Só desenho. O que o produto pinta por cima (nomes dos controles, contagens,
jogos de cada lançador) entra pelos endereços `data-campo`; aqui moram os dados
de exemplo e a forma de cada peça.
"""
# ruff: noqa: E501  (o gerador emite markup em f-string: a linha longa é o HTML legível no diff)
from __future__ import annotations

import json
import pathlib
from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

from hefesto_dualsense4unix.interface.desenho_dos_lancadores import _a, _e

_PASTA = pathlib.Path(__file__).with_name("experimental")

ROTULO_DA_TIRA = "Experimental"

CSS = (_PASTA / "experimental.css").read_text(encoding="utf-8")
SCRIPT = (_PASTA / "comportamento.js").read_text(encoding="utf-8")
_ICONES: dict[str, str] = json.loads((_PASTA / "icones.json").read_text(encoding="utf-8"))

#: Os três botões de todo lançador, na ordem em que aparecem.
BOTOES = (
    ("identificar-lancador", "Identificar", "#"),
    ("criar-perfil-para-um-jogo", "Criar perfis", "#escolher-jogo"),
    ("configurar-lancador", "Configurar", "#lanc-conf"),
)


class Fila(NamedTuple):
    chave: str
    nome: str
    jogos: str
    achado: bool
    configurar: str
    #: O endereço da extensão em que o lançador virou (``mods/viraram_extensao.json``): a linha
    #: deixa de ter os três botões e diz onde instalar. Nada se instala sozinho.
    virou: str = ""


#: A fila do desenho: os três de fábrica (Steam, Heroic, Flatpak), um lançador de extensão
#: instalada e a linha da migração de um que virou extensão (19/10/2026).
LANCADORES = (
    Fila("steam", "Steam", "48 jogos", True, "#lanc-conf"),
    Fila("lutris", "Lutris", "12 jogos", True, "#lanc-conf"),
    Fila("heroic", "Heroic (Epic · GOG)", "", False, "#lanc-conf"),
    Fila("flatpak", "Flatpak", "", False, "#lanc-conf"),
    Fila("retroarch", "RetroArch", "", False, "#lanc-conf",
         virou="https://github.com/Hefesto-Team/hefesto-mod-retroarch"),
)

#: A linha da migração mostra a frase e o nome do repositório; o endereço inteiro, que se copia
#: para o «Instalar», vai na dica (no tamanho do desenho, a frase longa com o endereço cortava).
FRASE_DO_QUE_VIROU = "Virou extensão:"
DICA_DO_QUE_VIROU = "Para seguir com ele, instale de"


class Extensao(NamedTuple):
    chave: str
    nome: str
    dica: str
    janela: str
    cor: str = "purple"
    #: O que o produto pinta por cima do exemplo: a versão e a origem do registro, a chave e o «⋮» aberto.
    versao: str = "0.1.0"
    selo: str = "Oficial"
    ligada: bool = True
    menu: str = ""


#: As extensões de exemplo do desenho: uma de lançador e uma que só tem opções. As cores são do
#: desenho; no produto, toda extensão ganha o roxo.
EXTENSOES = (
    Extensao("kytyps5", "KytyPS5", "Os jogos do KytyPS5 na fila dos lançadores, com o perfil de cada um",
             "#modificacao", "cyan"),  # (noqa-acento: âncora do HTML)
    Extensao("exemplo", "Minha extensão", "Uma extensão com opções em três grupos",
             "#modificacao"),  # (noqa-acento: âncora do HTML)
)


def _icone(chave: str, tamanho: int = 16) -> str:
    """O ícone da chave; extensão que o desenho não conhece ganha o genérico, nunca um erro."""
    return (f'<svg viewBox="0 0 24 24" width="{tamanho}" height="{tamanho}" fill="none" '
            f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
            f'stroke-linejoin="round">{_ICONES.get(chave) or _ICONES["extensao"]}</svg>')  # (noqa-acento): contrato ASCII


def _engrenagem() -> str:
    return (f'<svg viewBox="0 0 24 24" width="15" height="15" fill="none" '
            f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{_ICONES["engrenagem"]}</svg>')


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
        ativo = (gesto == "identificar-lancador") != fila.achado
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
    classe, texto = ("nj-tog ligado", "Ligada") if ext.ligada else ("nj-tog", "Desligada")
    return (f'<span class="{classe}" data-gesto="ligar-modificacao" data-v="{_a(ext.chave)}" '
            f'data-dica="Liga ou desliga"><span class="pino"></span><span class="txt">{texto}</span></span>')


SELO_DA_ORIGEM = {"oficial": "Oficial", "comunidade": "Comunidade", "local": "Local"}
ACOES_DO_MENU = (("atualizar", "Atualizar"), ("permissoes", "Ver permissões"), ("remover", "Remover"))  # (noqa-acento): contrato ASCII

#: O Remover depois do primeiro clique: apagar o código e os dados pede o segundo.
ROTULO_DA_CONFIRMACAO = "Confirmar remoção"
#: O ⋮ da janela «Configurar» diz de onde veio: o menu dele não se desenha também na linha atrás.
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
    valor: str | bool | float | Sequence[str] | Mapping[str, str]
    escolhas: tuple[str, ...] = ()
    grupo: str = ""
    # O ``deslizante`` desenha a faixa do manifesto; o ``jogos`` desenha uma caixa por jogo,
    # cada um como (chave, nome), marcada se a chave está no valor.
    minimo: float = 0
    maximo: float = 0
    passo: float = 1
    jogos: tuple[tuple[str, str], ...] = ()
    # A linha que a aba diz sob o rótulo, em vermelho (hoje, a forma curta da recusa do CSS de quem
    # usa: «Linha 2: url()»).
    nota: str = ""
    # O ``por_botao``: as formas pelo nome, cada uma com os passos (força, segundos), e os botões
    # da janela; o valor é ``{botão: forma}``.
    formas: tuple[tuple[str, tuple[tuple[float, float], ...]], ...] = ()
    botoes: tuple[str, ...] = ()


GESTO_DO_CSS = "editar-o-css-da-modificacao"
ROTULO_DO_CSS = "Editar o meu CSS"


# O manifesto de exemplo do DESENHO de 19/10/2026: uma extensão que declara três grupos (Geral, Luz
# e vibração, Avançado). O produto desenha o que o manifesto da pessoa trouxer; o exemplo só mostra a
# janela com mais de um grupo.
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

# O arranjo C do DESENHO de 22/10/2026: a mesma extensão de exemplo, agora com a coluna «Agora» (as
# conexões e os aparelhos), o «Parar tudo», os toques por botão e o endereço. Os nomes são genéricos:
# o produto desenha o que o manifesto e o ``acessorios.estado`` de cada extensão trouxerem.
FORMAS_DO_DESENHO = (
    ("Toque", ((1.0, 0.3),)),
    ("Duplo", ((1.0, 0.15), (0.0, 0.15), (1.0, 0.15))),
    ("Pulso", ((1.0, 0.1), (0.7, 0.1), (0.4, 0.1))),
    ("Onda", ((0.3, 0.2), (0.6, 0.2), (1.0, 0.3), (0.6, 0.2), (0.3, 0.2))),
    ("Nada", ()),
)
BOTOES_DO_DESENHO = ("cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2",
                     "dpad_up", "dpad_down", "touchpad_left_press", "touchpad_right_press")
OPCOES_DO_DESENHO_C = (
    OpcaoDaJanela("exemplo", "toques", "Toque de cada botão", "por_botao",
                  {"cross": "Toque", "circle": "Duplo", "square": "Pulso", "triangle": "Onda",
                   "touchpad_right_press": "Nada"}, (), "Toques",
                  formas=FORMAS_DO_DESENHO, botoes=BOTOES_DO_DESENHO),
    OpcaoDaJanela("exemplo", "endereco", "Endereço do aparelho na rede", "endereco", "", (),
                  "Ligação"),  # (noqa-acento): o id é a chave do manifesto
    *OPCOES_DO_DESENHO,
)
AGORA_DO_DESENHO = ("conexoes", "aparelhos")  # (noqa-acento): as chaves do estado
ESTADO_DO_DESENHO: dict[str, Any] = {
    "ligado": True,
    "conexoes": [  # (noqa-acento): a chave do estado
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
        f'<label class="jg-l"><input type="checkbox"{" checked" if chave in marcados else ""} '
        f'data-gesto="guardar-opcao-da-modificacao" data-v="{_a(o.mod)}:{_a(o.id)}:{_a(chave)}">'
        f'<span class="jg-n">{_e(nome)}</span></label>'
        for chave, nome in o.jogos)
    return f'<div class="jg-lista ext-jogos" aria-label="{_a(o.rotulo)}">{caixas}</div>'


#: O que o campo do ``endereco`` mostra vazio: o vazio é o endereço que ainda não se escolheu.
DICA_DO_ENDERECO = "IP:porta"
#: O desenho de cada botão do ``por_botao`` é o glifo da casa (``assets/glyphs``), num ``<symbol>``
#: da página (:func:`sprite_dos_botoes`); as três terças do touchpad levam a terça que aperta.
GLIFO_DO_BOTAO = {"l3": "stick_l", "r3": "stick_r", "create": "share",
                  "touchpad_left_press": "touchpad", "touchpad_middle_press": "touchpad",
                  "touchpad_right_press": "touchpad"}
_TERCA_DO_TOUCHPAD = {"touchpad_left_press": 3.0, "touchpad_middle_press": 11.67,
                      "touchpad_right_press": 20.33}
#: A largura e a altura da onda de uma forma, em unidades do ``viewBox``.
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
            f'<div class="tql"><svg class="tq-gl" viewBox="0 0 32 32" width="22" height="22" '
            f'aria-hidden="true"><use href="#bt-{_a(botao)}"/></svg>'
            f'{_onda_da_forma(formas.get(atual, ()))}'
            f'<select class="ext-sel" data-gesto="guardar-opcao-da-modificacao" '
            f'data-v="{_a(o.mod)}:{_a(o.id)}:{_a(botao)}" aria-label="{_a(o.rotulo)}">{itens}'
            "</select></div>")
    return f'<div class="tq-lista" aria-label="{_a(o.rotulo)}">{"".join(linhas)}</div>'


def sprite_dos_botoes() -> str:
    """Os glifos dos botões do ``por_botao`` como ``<symbol id="bt-<botão>">``, uma vez na página.

    Só o gerador o chama: os glifos moram em ``assets/glyphs`` do repositório, e a janela do produto
    os usa pelo ``<use>`` da página publicada.
    """
    import re

    from hefesto_dualsense4unix.mods.manifesto import BOTOES_DO_POR_BOTAO

    pasta = pathlib.Path(__file__).resolve().parents[3] / "assets" / "glyphs"
    simbolos = []
    for botao in BOTOES_DO_POR_BOTAO:
        bruto = (pasta / f"{GLIFO_DO_BOTAO.get(botao, botao)}.svg").read_text(encoding="utf-8")
        achado = re.search(r"<svg\b[^>]*>(.*)</svg>", bruto, flags=re.S)
        miolo = re.sub(r"<!--.*?-->", "", achado.group(1) if achado else "", flags=re.S)
        miolo = re.sub(r"#[0-9a-fA-F]{6}\b", "currentColor", miolo)
        if botao in _TERCA_DO_TOUCHPAD:
            miolo += (f'<rect x="{_TERCA_DO_TOUCHPAD[botao]:g}" y="8" width="8.67" height="16" '
                      'fill="currentColor" opacity=".4"/>')
        simbolos.append(f'<symbol id="bt-{botao}" viewBox="0 0 32 32">{" ".join(miolo.split())}</symbol>')
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
    for nome, itens in _grupos_das_opcoes(opcoes).items():
        cartoes.append(f'<div class="ac-card"><div class="ac-topo">'
                       f'<span class="ac-tit">{_e(nome or "Opções")}</span></div>'
                       f'{_linhas_das_opcoes(itens)}</div>')
    return f'<div class="ky-grade">{"".join(cartoes)}</div>'


#: As opções que põem o rótulo em cima e a lista embaixo, na largura do cartão.
_EMPILHADAS = ("jogos", "por_botao")


def _linhas_das_opcoes(itens: Sequence[OpcaoDaJanela]) -> str:
    """Uma linha por opção: rótulo à esquerda e controle à direita, ou a lista embaixo."""
    return "".join(
        f'<div class="ky-rot"><span>{_e(o.rotulo)}</span></div>{_controle_da_opcao(o)}'
        if o.tipo in _EMPILHADAS else
        f'<div class="ky-linha"><div class="ky-rot"><span>{_e(o.rotulo)}</span>'
        f'{_nota_da_opcao(o)}</div>'
        f'<div class="ky-ctrl">{_controle_da_opcao(o)}</div></div>' for o in itens)


def _abas_das_opcoes(opcoes: Sequence[OpcaoDaJanela], aba: str) -> str:
    """O lado dos ajustes do arranjo C: os grupos do manifesto em abas, um cartão só.

    As abas são rádios (o navegador troca a tela sem gesto); ``aba`` é o grupo que nasce aberto, o
    da última opção mudada, para a janela redesenhada não voltar à primeira. Com um grupo só, é o
    cartão de sempre.
    """
    grupos = _grupos_das_opcoes(opcoes)
    if len(grupos) < 2:
        return _cartoes_das_opcoes(opcoes)
    aberta = aba if aba in grupos else next(iter(grupos))
    partes = "".join(
        f'<input type="radio" name="mj-aba" id="mj-aba-{n}"{" checked" if nome == aberta else ""}>'
        f'<label for="mj-aba-{n}">{_e(nome)}</label>'
        f'<div class="mj-tela">{_linhas_das_opcoes(itens)}</div>'
        for n, (nome, itens) in enumerate(grupos.items()))
    return f'<div class="ac-card mj-abas">{partes}</div>'


#: Os pedaços da coluna «Agora» que um manifesto pode declarar, na ordem do desenho.
PEDACOS_DO_AGORA = ("conexoes", "nivel", "perfil", "aparelhos")  # (noqa-acento): a chave do estado
NIVEL_MAXIMO = 10
#: O que um pedaço mostra quando a extensão não deu valor (parada, ou ainda sem estado).
SEM_VALOR = "—"
DICA_DO_PARAR = "Todos os aparelhos a zero na hora. O nível e o perfil ficam guardados."
GESTO_DO_PARAR = "parar-tudo-da-modificacao"
#: A palavra e a cor de cada estado de uma conexão ou de um aparelho (``acessorios.estado``).
PALAVRA_DO_ESTADO = {"ligado": "Ligado", "procurando": "Procurando", "desligado": "Desligado",
                     "falhou": "Falhou"}
COR_DO_ESTADO = {"ligado": "verde", "procurando": "amarelo", "desligado": "mudo",
                 "falhou": "laranja"}
_TRACO_DO_ICONE = ('viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" '
                   'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"')
#: O desenho de cada transporte de uma conexão, e o do aparelho.
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


def agora_html(pedacos: Sequence[str], estado: Mapping[str, Any] | None) -> str:
    """O miolo da coluna «Agora»: só os pedaços que o manifesto declara, do ``acessorios.estado``.

    Sem estado, ou com a extensão parada (``ligado`` falso), o nível e o perfil ficam vazios: nenhum
    número que a extensão não deu. As conexões e os aparelhos são os que ela publicou, parada ou não:
    o «Parar tudo» zera a força, e o adaptador segue ligado (a conexão que cai já devolve o estado
    vazio, sem item nenhum). O perfil e os nomes vêm de terceiros: escapados.
    """
    vivo = bool(estado and estado.get("ligado") is True)
    linhas = ['<div class="ja-ag-topo"><span class="pc-sub">Agora</span>'
              f'<span class="ja-srv">{"Ligada" if vivo else "Parada"}</span></div>']
    declarados = [x for x in PEDACOS_DO_AGORA if x in pedacos]
    for pedaco in declarados:
        if pedaco == "conexoes":  # (noqa-acento): a chave do estado
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
            itens = "".join(_aparelho_html(a) for a in itens_do_estado(estado, pedaco))
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
               estado: Mapping[str, Any] | None, parar: str) -> str:
    """A janela do arranjo C: «Parar tudo» no topo, a coluna «Agora» e os ajustes, e o rodapé."""
    return f'''    <div class="tn-topo ja-topo">
      <span class="tn-tit">Configurar · {_e(nome)}</span>{parar}
      <a class="tn-x" href="#" data-dica="Fechar">\u00d7</a>
    </div>
    <div class="ja-corpo">
      <div class="ja-agora" id="mod-agora">{agora_html(agora, estado)}</div>
      <div class="ja-opcoes">{ajustes}</div>
    </div>
    <div class="tn-rod">
      <a class="btn" href="#">Cancelar</a>
      <a class="btn roxo" href="#" data-gesto="{GESTO_DO_GUARDAR}" data-v="{_a(mod)}">Guardar</a>
    </div>'''


GESTO_DO_GUARDAR = "guardar-modificacao"


def modificacao_miolo_html(nome: str, opcoes: Sequence[OpcaoDaJanela], *, mod: str = "",
                           agora: Sequence[str] = (), estado: Mapping[str, Any] | None = None,
                           parar_tudo: bool = False, aba: str = "") -> str:
    """O conteúdo da janela de uma extensão: um cartão por grupo, «Para» no topo, Cancelar e Guardar.

    É o arranjo aprovado em 19/10: cada opção que o manifesto declara vira uma linha
    do cartão do grupo dela. Mudar uma opção só a põe no rascunho da janela; o Guardar grava todas.
    ``agora`` são os pedaços da coluna «Agora» que o manifesto declara (``estado`` é o último
    ``acessorios.estado`` dela) e ``parar_tudo`` põe o botão no topo; os dois só com ``mod``.
    Com ``agora``, a janela é o arranjo C (escolhido em 22/10/2026): a coluna à esquerda e os
    grupos em abas à direita (``aba`` é o grupo aberto), sem o «Para».
    """
    parar = parar_tudo_html(mod) if parar_tudo and mod else ""
    agora = agora if mod else ()
    vazio = '<div class="ext-vazia">Esta extensão não tem opções para ajustar.</div>'
    if agora:
        return _arranjo_c(nome, _abas_das_opcoes(opcoes, aba) if opcoes else vazio, mod=mod,
                          agora=agora, estado=estado, parar=parar)
    corpo = _cartoes_das_opcoes(opcoes) if opcoes else vazio
    return f'''    <div class="tn-topo">
      <span class="tn-tit">Configurar · {_e(nome)}</span>
      <span class="pc-para"><span class="ext-rot">Para</span>Todos</span>{parar}
      <a class="tn-x" href="#" data-dica="Fechar">\u00d7</a>
    </div>
    <div class="tn-corpo">
      {corpo}
    </div>
    <div class="tn-rod">
      <a class="btn" href="#">Cancelar</a>
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
    #: Quantos jogos têm impedimento; `None` quando o lançador não tem essa leitura.
    impedimentos: int | None = None
    #: As pastas em que os jogos dele moram; sem elas, a linha diz só quantos jogos.
    pastas: tuple[str, ...] = ()
    #: A chave «Cada jogo ganha o seu perfil»; `None` no lançador que não entrega jogos.
    perfil_por_jogo: bool | None = None
    #: O lançador que vem de uma extensão: o ⋮ age nela, e onde ele está é ela quem diz.
    modificacao: str = ""
    #: O ⋮ aberto pelo produto: o miolo de `menu_html` na extensão, qualquer texto no que vem com o
    #: Hefesto (o menu dele é sempre o apagado); vazio, ele abre só com o foco.
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
           "modificacao")  # (noqa-acento): contrato ASCII


def telas() -> str:
    """Todas as janelas da aba, em ordem, prontas para entrar antes do fim da página."""
    partes = []
    for nome in JANELAS:
        texto = _fragmento(nome)
        texto = texto.replace("{{ESCOLHA}}", escolha_miolo_html("Steam", JOGOS_DA_STEAM, desenho=True))
        texto = texto.replace("{{CONF}}", lanc_conf_miolo_html(CONF_DE_EXEMPLO))
        texto = texto.replace("{{IMPEDIMENTOS}}", impedimentos_miolo_html("Steam", IMPEDIMENTOS_DE_EXEMPLO))
        texto = texto.replace("{{MODIFICACAO}}", modificacao_miolo_html(
            "Minha extensão", OPCOES_DO_DESENHO_C, mod="exemplo", agora=AGORA_DO_DESENHO,
            estado=ESTADO_DO_DESENHO, parar_tudo=True))
        partes.append(texto.strip())
    return ("\n".join(partes) + f"\n{sprite_dos_botoes()}"
            f"\n<script data-aba=\"experimental\">\n{SCRIPT}</script>\n")
