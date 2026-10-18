"""O desenho da aba Experimental (a 07): extensões, lançadores e as janelas deles.

Só desenho. O que o produto pinta por cima (nomes dos controles, contagens,
jogos de cada lançador) entra pelos endereços `data-campo`; aqui moram os dados
de exemplo e a forma de cada peça.
"""
# ruff: noqa: E501  (o gerador emite markup em f-string: a linha longa é o HTML legível no diff)
from __future__ import annotations

import json
import pathlib
from typing import NamedTuple

from hefesto_dualsense4unix.integrations import kits_de_brinquedo as kits

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


LANCADORES = (
    Fila("steam", "Steam", "48 jogos", True, "#lanc-conf"),
    Fila("kyty", "Kyty", "2 jogos", True, "#kyty"),
    Fila("heroic", "Heroic (Epic · GOG)", "", False, "#lanc-conf"),
    Fila("lutris", "Lutris", "", False, "#lanc-conf"),
    Fila("flatpak", "Flatpak", "", False, "#lanc-conf"),
    Fila("retroarch", "RetroArch", "", False, "#lanc-conf"),
    Fila("emuladores", "Dolphin · mGBA", "", False, "#lanc-conf"),
)


class Extensao(NamedTuple):
    chave: str
    nome: str
    dica: str
    para: str
    janela: str
    cor: str


EXTENSOES = (
    Extensao("kyty", "Kyty", "Jogos do Kyty com gatilhos, luz e vibração do controle",
             '<div class="ext-para"><span class="ext-rot">Para</span>Todos</div>',
             "#kyty", "cyan"),
    Extensao("lovense", "Lovense",
             "Brinquedos da Lovense com o controle, em três jeitos de ligar",
             '<div class="ext-para" data-dica="Quantas das três formas estão ligadas. '
             'Quem vai para quem fica na engrenagem"><span data-lv-conta>2 de 3 ligadas</span></div>',
             "#lovense", "pink"),
)

#: Os aparelhos de exemplo da janela da Lovense (nome e quantos motores).
APARELHOS = ("Lovense Nora", "Lovense Domi", "Lovense Ferri")

#: Os canais de força, com a dica que o cabeçalho traz.
CANAIS = (
    ("Vibração", "A vibração que o jogo pede ao controle"),
    ("Gatilho", "Os eventos do gatilho"),
    ("Háptica", "O som que vibra"),
)

#: 50% de fábrica, na escala de 0 a 20 da Lovense.
FORCA_DE_FABRICA = 10


class Jogo(NamedTuple):
    nome: str
    kit: kits.KitDoJogo | None = None


#: Um jogo em cada veredito; o IP de mentira nunca chega à tela.
JOGOS_DE_EXEMPLO = (
    Jogo("Mortal Kombat"),
    Jogo("Elden Ring"),
    Jogo("Neon Nights", kits.KitDoJogo("lovense-unity", kits.PORTA_QUE_NADA_ATENDE, 20100, "http")),
    Jogo("Planet Lust", kits.KitDoJogo("lovense-jj", kits.NAO_LIDO)),
    Jogo("MonGirl Conquest", kits.KitDoJogo("lovense-rpgmaker", kits.DESLIGADO)),
    Jogo("Third Crisis", kits.KitDoJogo("lovense-unity", kits.ALCANCA_A_PONTE, 20010, "http")),
    Jogo("Orpheus", kits.KitDoJogo("lovense-unity", kits.APONTA_PARA_OUTRA_MAQUINA, 20010, "http")),
)

MARCA_DO_KIT = "Fala com a Lovense"
_NO_MENU = "No menu Lovense do jogo: IP 127.0.0.1, porta 20010"
_EXTRA_DO_KIT = {
    "lovense-unity": "«Use HTTP» desligado",
    "lovense-jj": "«Conexão HTTP (20010)»",
    "lovense-rpgmaker": "«Mobile»",
}
_OUTRA_MAQUINA = "O jogo fala direto com o app do celular"


def linha_do_kit(kit: kits.KitDoJogo | None) -> str:
    """A única linha que a janela diz sob o jogo; vazia quando não há o que dizer."""
    if kit is None or kit.veredito == kits.ALCANCA_A_PONTE:
        return ""
    if kit.veredito == kits.APONTA_PARA_OUTRA_MAQUINA:
        return _OUTRA_MAQUINA
    extra = _EXTRA_DO_KIT.get(kit.kit)
    return f"{_NO_MENU}, {extra}" if extra else _NO_MENU


def _icone(chave: str, tamanho: int = 16) -> str:
    return (f'<svg viewBox="0 0 24 24" width="{tamanho}" height="{tamanho}" fill="none" '
            f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
            f'stroke-linejoin="round">{_ICONES[chave]}</svg>')


def _engrenagem() -> str:
    return (f'<svg viewBox="0 0 24 24" width="15" height="15" fill="none" '
            f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{_ICONES["engrenagem"]}</svg>')


def _botao(gesto: str, rotulo: str, destino: str, chave: str, ativo: bool) -> str:
    apagado = "" if ativo else " apagado"
    desligado = "" if ativo else ' aria-disabled="true"'
    if gesto == "identificar-lancador":
        return (f'<button class="btn mini{apagado}"{desligado} data-gesto="{gesto}" '
                f'data-v="{chave}">{rotulo}</button>')
    return (f'<a class="btn mini{apagado}"{desligado} href="{destino}" data-gesto="{gesto}" '
            f'data-v="{chave}">{rotulo}</a>')


def fila_html(fila: Fila) -> str:
    """Uma linha de lançador: os mesmos três botões, acesos pelo que o lançador é."""
    botoes = []
    for gesto, rotulo, destino in BOTOES:
        destino = fila.configurar if gesto == "configurar-lancador" else destino
        ativo = (gesto == "identificar-lancador") != fila.achado
        botoes.append(_botao(gesto, rotulo, destino, fila.chave, ativo))
    contagem = f'<span class="lf-n">{fila.jogos}</span>' if fila.achado else ""
    nome_cl = "lf-nome lf-nome-2" if fila.achado else "lf-nome"
    vazio = "" if fila.achado else '\n            <span class="lanc-jogos"></span>'
    classe = "lf" if fila.achado else "lf ausente"
    return f'''          <div class="{classe}" data-lancador="{fila.chave}">
            <span class="ext-ico lf-ico">{_icone(fila.chave)}</span>
            <span class="{nome_cl}"><span class="lanc-nome">{fila.nome}</span>{contagem}</span>{vazio}
            <span class="lf-botoes">{"".join(botoes)}</span>
          </div>'''


def extensao_html(ext: Extensao) -> str:
    return f'''          <div class="ext" data-modificacao="{ext.chave}">
            <span class="ext-ico" style="color:var(--{ext.cor})">{_icone(ext.chave)}</span>
            <div class="ext-quem">
              <span class="ext-sub"><span class="ext-nome">{ext.nome}</span><span class="lanc-selo oficial">Oficial</span><span class="ext-ver">0.1.0</span></span>
              <span class="ext-faz" data-dica="{ext.dica}">{ext.dica}</span>
            </div>
            {ext.para}
            <span class="nj-tog ligado" data-gesto="ligar-modificacao" data-v="{ext.chave}" data-dica="Liga ou desliga"><span class="pino"></span><span class="txt">Ligada</span></span>
            <a class="ext-conf" href="{ext.janela}" data-gesto="configurar-modificacao" data-v="{ext.chave}" data-dica="Configurações: {ext.nome}">{_engrenagem()}</a>
            <button class="ext-mais" data-gesto="mais-da-modificacao" data-v="{ext.chave}" data-dica="Atualizar, abrir a pasta ou remover">⋮</button>
          </div>'''


def miolo() -> str:
    """Os dois quadros da aba: Extensões e Lançadores."""
    extensoes = "\n".join(extensao_html(e) for e in EXTENSOES)
    filas = "\n".join(fila_html(f) for f in LANCADORES)
    return f'''
    <div class="quadro">
      <input class="abre" type="checkbox" id="cx7-1" checked>
      <div class="quadro-topo">
        <label class="quadro-titulo" for="cx7-1">Extensões</label>
        <span class="conta" data-campo="mod-conta">2 instaladas</span>
      </div>
      <div class="quadro-corpo">
        <div class="ext-lista">
{extensoes}
        </div>
        <div class="ext-instalar ext-instalar-pe">
          <span class="ext-inst-rot">Instalar de um endereço</span>
          <input type="text" data-linha="mod-endereco" placeholder="https://github.com/…">
          <a class="btn" href="#" data-gesto="escolher-arquivo-da-modificacao">Escolher a pasta…</a>
          <button class="btn roxo" data-gesto="instalar-modificacao">Instalar</button>
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
{filas}
          <a class="lf lf-novo" href="#novo-lancador" data-gesto="adicionar-lancador" data-dica="Um programa desta máquina ou um pacote de extensão">
            <span class="ext-ico lf-ico"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5.5v13M5.5 12h13"/></svg></span>
            <span class="lanc-nome">Adicionar um lançador</span>
          </a>
        </div>
      </div>
    </div>
'''


def lista_de_jogos_html(jogos: tuple[tuple[str, bool], ...]) -> str:
    """A lista da janela «Criar perfis»: um «Criar» por jogo que ainda não tem perfil."""
    itens = []
    for nome, tem in jogos:
        fim = ('<span class="cj-tem">Tem perfil</span>' if tem else
               '<button class="btn mini" data-gesto="criar-perfil-do-jogo">Criar</button>')
        itens.append(f'<li><span class="cj-nome">{nome}</span>{fim}</li>')
    return '<ul class="cj-lista">' + "".join(itens) + "</ul>"


JOGOS_DA_STEAM = (
    ("Sackboy: A Big Adventure", True),
    ("Resident Evil Village", False),
    ("Mortal Kombat 1", True),
    ("Hades II", False),
    ("Hollow Knight: Silksong", False),
)


def jogos_html(jogos: tuple[Jogo, ...] = JOGOS_DE_EXEMPLO) -> str:
    """As caixas dos jogos; nasce tudo desmarcado, e o kit diz a porta sob o jogo."""
    linhas = []
    for jogo in jogos:
        marca = f'<span class="jg-kit">{MARCA_DO_KIT}</span>' if jogo.kit else ""
        diz = linha_do_kit(jogo.kit)
        sob = f'<span class="jg-porta">{diz}</span>' if diz else ""
        linhas.append(
            f'<label class="jg-l"><input type="checkbox" data-jogo="{jogo.nome}">'
            f'<span class="jg-n">{jogo.nome}</span>{marca}{sob}</label>')
    return '<div class="jg-lista">' + "".join(linhas) + "</div>"


def forca_html(aparelhos: tuple[str, ...] = APARELHOS) -> str:
    """Um deslizante de 0 a 20 por canal e por aparelho; o aparelho recebe o maior dos canais."""
    cab = "".join(f'<span class="fz-cab" data-dica="{dica}">{nome}</span>' for nome, dica in CANAIS)
    corpo = []
    for ap in aparelhos:
        celulas = "".join(
            f'<span class="fz-c"><input type="range" min="0" max="20" step="1" '
            f'value="{FORCA_DE_FABRICA}" aria-label="{nome} de {ap}" '
            f'oninput="this.nextElementSibling.textContent=this.value">'
            f'<b>{FORCA_DE_FABRICA}</b></span>' for nome, _ in CANAIS)
        corpo.append(f'<span class="fz-ap">{ap}</span>{celulas}')
    return '<div class="fz-grade">' + cab + "".join(corpo) + "</div>"


def _fragmento(nome: str) -> str:
    return (_PASTA / f"{nome}.html").read_text(encoding="utf-8")


JANELAS = ("novo-lancador", "escolher-jogo", "lovense", "impedimentos", "lanc-conf",
           "kyty", "buttplug", "acessorios")


def telas() -> str:
    """Todas as janelas da aba, em ordem, prontas para entrar antes do fim da página."""
    partes = []
    for nome in JANELAS:
        texto = _fragmento(nome)
        texto = texto.replace("{{LISTA}}", lista_de_jogos_html(JOGOS_DA_STEAM))
        texto = texto.replace("{{JOGOS}}", jogos_html())
        texto = texto.replace("{{FORCA}}", forca_html())
        partes.append(texto.strip())
    return "\n".join(partes) + f"\n<script data-aba=\"experimental\">\n{SCRIPT}</script>\n"
