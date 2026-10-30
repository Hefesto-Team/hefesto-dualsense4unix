"""A janela de uma extensão de tema, no arranjo da Lovense: a coluna «Agora» com o tema em uso,
as abas dos grupos do manifesto à direita e a faixa «Ao vivo» com a paleta que a tela pinta.

Cada peça sai do papel que o bloco ``tema`` dá à opção (a cor, o importado, o destaque, os
botões, a logo e o CSS), nunca do id: qualquer extensão de tema ganha a mesma janela.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence

from hefesto_dualsense4unix.interface.desenho_da_experimental import (
    GESTO_DE_IMPORTAR,
    GESTO_DE_TIRAR,
    PEDACO,
    ROTULO_DE_IMPORTAR,
    ROTULO_DE_TIRAR,
    ROTULO_DE_TROCAR,
    OpcaoDaJanela,
    _arranjo_c,
    _bolinha_da_aba,
    _controle_da_opcao,
    _grupos_das_opcoes,
    _linha_da_opcao,
    _nota_da_opcao,
    _radio_da_aba,
    chave_da_aba,
)
from hefesto_dualsense4unix.interface.desenho_dos_lancadores import _a, _e
from hefesto_dualsense4unix.mods import retrato_do_tema as rt
from hefesto_dualsense4unix.mods.retrato_do_tema import Carta, Retrato

GESTO_DE_EXPORTAR = "exportar-o-tema-da-modificacao"
GESTO_DA_OPCAO = "guardar-opcao-da-modificacao"
ROTULO_DE_EXPORTAR = "Exportar"
DICA_DO_IMPORTAR_TEMA = "Um .css só com :root{…} de cores"
DICA_DO_EXPORTAR = "Salva o tema em uso como .css"
DICA_DA_LOGO = "PNG, JPEG ou WebP, até 256 KB"
DICA_DO_CONTRASTE = "O menor contraste do texto sobre o fundo. O mínimo é 4,5."
DICA_DO_SISTEMA = "Segue o lado do sistema"
PALAVRA_DA_ORIGEM = {rt.DE_FABRICA: "De fábrica", rt.IMPORTADO: "Importado"}
LADO_DA_BARRA = {"esquerda": "esq", "direita": "dir"}
SEM = "—"
_PECAS_DA_MINI = (("--m-bg", "--app-bg"), ("--m-pn", "--panel"), ("--m-el", "--elevated"),
                  ("--m-fg", "--fg"), ("--m-sv", "--texto-mudo"), ("--m-ac", "--green"),
                  ("--m-rx", "--purple"), ("--m-rs", "--pink"))


def _numero(razao: float) -> str:
    return f"{razao:.1f}".replace(".", ",")


def recusa_curta(frase: str) -> str:
    """A palavra que a tela diz em vermelho; a frase inteira vai na dica."""
    return "Ilegível" if "ilegível" in frase.casefold() else "Não ligou"


def _recusa(frase: str) -> str:
    return (f'<span class="tm-recusa" data-dica="{_a(frase)}">{recusa_curta(frase)}</span>'
            if frase else "")


def _estilo_das_cores(cores: Mapping[str, str]) -> str:
    return ";".join(f"{var}:{_a(cores[token])}" for var, token in _PECAS_DA_MINI if token in cores)


def mini_html(cores: Mapping[str, str], lado: str = "", *, logo: bool = False,
              classe: str = "") -> str:
    """A janela em miniatura pintada com ``cores``: a barra com os botões no ``lado``, a logo,
    o texto, um cartão e o destaque. Sem cores, o lugar vazio do tema por importar."""
    if not cores:
        return f'<span class="{" ".join(("tm-mini vazio", classe)).strip()}"><b>+</b></span>'
    barra = LADO_DA_BARRA.get(lado, "sis")
    marca = '<span class="logo tm-mini-logo"></span>' if logo else '<i class="tm-mini-logo"></i>'
    return (f'<span class="{" ".join(("tm-mini", classe)).strip()}" '
            f'style="{_estilo_das_cores(cores)}">'
            f'<span class="tm-mini-barra {barra}"><i></i><i></i><i></i></span>'
            f'<span class="tm-mini-corpo">{marca}'
            '<span class="tm-mini-txt"><i class="l1"></i><i class="l2"></i></span>'
            '<span class="tm-mini-cartao"><i class="bt"></i><i class="tg"></i><i class="rs"></i>'
            "</span></span></span>")


def coluna_html(retrato: Retrato, nome: str) -> str:
    """A coluna «Agora»: de onde vem o tema, a miniatura viva, o nome e o resto em uso."""
    carta = retrato.carta
    origem = PALAVRA_DA_ORIGEM.get(carta.origem if carta else rt.DE_FABRICA, "")
    dica = f' data-dica="{_a(carta.arquivo)}"' if carta and carta.arquivo else ""
    p = retrato.papeis
    linhas = []
    if p.destaque:
        ponto = (f'<i class="tm-ponto" style="--c:{_a(retrato.destaque)}"></i>'
                 f"<b>{_e(retrato.destaque)}</b>" if retrato.destaque else f"<b>{SEM}</b>")
        linhas.append(f'<div class="tm-l"><span class="ja-rot">Destaque</span>{ponto}</div>')
    if p.botoes:
        linhas.append('<div class="tm-l"><span class="ja-rot">Botões</span>'
                      f"<b>{_e(retrato.botoes or SEM)}</b></div>")
    if p.logo:
        linhas.append('<div class="tm-l"><span class="ja-rot">Logo</span>'
                      f'<b{_dica(retrato.logo)}>{"Importada" if retrato.logo else "Da casa"}</b>'
                      "</div>")
    if p.css:
        linhas.append('<div class="tm-l"><span class="ja-rot">CSS</span>'
                      f'<b>{"Ligado" if retrato.css_ligado else "Desligado"}</b></div>')
    return (f'<div class="ja-ag-topo"><span class="pc-sub">Agora</span>'
            f'<span class="ja-srv tm-origem"{dica}>{origem}</span></div>'
            f'{mini_html(retrato.cores, retrato.lado, logo=bool(p.logo), classe="grande")}'
            f'<div class="tm-nome" data-dica="{_a(nome)}">{_e(retrato.escolhida or SEM)}</div>'
            f'<div class="tm-linhas">{"".join(linhas)}</div>')


def _dica(texto: str) -> str:
    return f' data-dica="{_a(texto)}"' if texto else ""


def _botao(gesto: str, v: str, rotulo: str, dica: str = "", classe: str = "btn mini") -> str:
    return (f'<button class="{classe}" data-gesto="{gesto}" data-v="{_a(v)}"{_dica(dica)}>'
            f"{rotulo}</button>")


def _cartao_da_escolha(o: OpcaoDaJanela, carta: Carta, importado: str) -> str:
    origem = PALAVRA_DA_ORIGEM.get(carta.origem, "")
    pe = (f'<span class="tm-carta-pe"><b>{_e(carta.escolha)}</b>'
          f'{f"<em>{origem}</em>" if origem != carta.escolha else ""}</span>')
    if not carta.cores and carta.origem == rt.IMPORTADO and importado:
        return (f'<button class="tm-carta vazia" data-gesto="{GESTO_DE_IMPORTAR}" '
                f'data-v="{_a(o.mod)}:{_a(importado)}" data-dica="{DICA_DO_IMPORTAR_TEMA}">'
                f"{mini_html({})}{pe}</button>")
    marcada = carta.escolha == o.valor
    return (f'<label class="tm-carta{" on" if marcada else ""}"{_dica(carta.arquivo)}>'
            f'<input type="radio" name="tm-{_a(o.id)}" value="{_a(carta.escolha)}"'
            f'{" checked" if marcada else ""} data-gesto="{GESTO_DA_OPCAO}" '
            f'data-v="{_a(o.mod)}:{_a(o.id)}">{mini_html(carta.cores)}{pe}</label>')


def _cores_html(o: OpcaoDaJanela, retrato: Retrato, importado: OpcaoDaJanela | None) -> str:
    alvo = importado.id if importado else ""
    cartas = "".join(_cartao_da_escolha(o, c, alvo) for c in retrato.cartas)
    acoes = []
    if importado is not None:
        arquivo = importado.valor if isinstance(importado.valor, str) else ""
        v = f"{o.mod}:{importado.id}"
        acoes.append(_botao(GESTO_DE_IMPORTAR, v, ROTULO_DE_TROCAR if arquivo else
                            ROTULO_DE_IMPORTAR, arquivo or DICA_DO_IMPORTAR_TEMA))
        if arquivo:
            acoes.append(_botao(GESTO_DE_TIRAR, v, ROTULO_DE_TIRAR, arquivo))
    acoes.append(_botao(GESTO_DE_EXPORTAR, o.mod, ROTULO_DE_EXPORTAR, DICA_DO_EXPORTAR))
    return (f'<div class="tm-sec" id="{PEDACO}op-{_a(o.id)}">'
            f'<div class="tm-cartas" style="--n:{max(1, len(retrato.cartas))}">{cartas}</div>'
            f'<div class="tm-acoes">{"".join(acoes)}{_recusa(o.nota)}</div></div>')


def _destaque_html(o: OpcaoDaJanela, retrato: Retrato) -> str:
    valor = str(o.valor or "").lower()
    alvo = f'data-gesto="{GESTO_DA_OPCAO}" data-v="{_a(o.mod)}:{_a(o.id)}"'
    prontas = "".join(
        f'<label class="tm-cor{" on" if c == valor else ""}" style="--c:{c}" data-dica="{c}">'
        f'<input type="radio" name="tm-{_a(o.id)}" value="{c}"{" checked" if c == valor else ""} '
        f"{alvo}></label>" for c in rt.destaques_legiveis(retrato.cores))
    livre = (f'<label class="tm-cor livre" style="--c:{_a(valor)}" data-dica="Outra cor">'
             f'<input type="color" value="{_a(valor)}" {alvo} aria-label="{_a(o.rotulo)}"></label>')
    amostra = (f'<span class="tm-amostra" style="{_estilo_das_cores(retrato.cores)}">'
               '<i class="bt">Aplicar</i><i class="tg"></i><i class="ab">Aba</i>'
               '<i class="ch"></i></span>')
    return (f'<div class="tm-sec" id="{PEDACO}op-{_a(o.id)}">'
            f'<div class="tm-cores">{prontas}{livre}</div>{amostra}{_recusa(o.nota)}</div>')


def _botoes_html(o: OpcaoDaJanela, retrato: Retrato) -> str:
    cartoes = []
    for escolha in o.escolhas:
        lado = retrato.papeis.lados.get(escolha, "")
        marcada = escolha == o.valor
        cartoes.append(
            f'<label class="tm-lado{" on" if marcada else ""}"'
            f'{"" if lado else _dica(DICA_DO_SISTEMA)}>'
            f'<input type="radio" name="tm-{_a(o.id)}" value="{_a(escolha)}"'
            f'{" checked" if marcada else ""} data-gesto="{GESTO_DA_OPCAO}" '
            f'data-v="{_a(o.mod)}:{_a(o.id)}">'
            f'<span class="tm-mini-barra {LADO_DA_BARRA.get(lado, "sis")}"><i></i><i></i><i></i>'
            f"</span><b>{_e(escolha)}</b></label>")
    return (f'<div class="tm-sec" id="{PEDACO}op-{_a(o.id)}"><span class="tm-sec-rot">'
            f'{_e(o.rotulo)}</span><div class="tm-lados">{"".join(cartoes)}</div></div>')


def _logo_html(o: OpcaoDaJanela) -> str:
    arquivo = o.valor if isinstance(o.valor, str) else ""
    v = f"{o.mod}:{o.id}"
    botoes = _botao(GESTO_DE_IMPORTAR, v, ROTULO_DE_TROCAR if arquivo else ROTULO_DE_IMPORTAR,
                    arquivo or DICA_DA_LOGO)
    if arquivo:
        botoes += _botao(GESTO_DE_TIRAR, v, ROTULO_DE_TIRAR, arquivo)
    return (f'<div class="tm-sec" id="{PEDACO}op-{_a(o.id)}"><span class="tm-sec-rot">'
            f'{_e(o.rotulo)}</span><div class="tm-logo-linha"><span class="logo tm-logo"></span>'
            f'<span class="tm-acoes">{botoes}{_recusa(o.nota)}</span></div></div>')


def _css_html(o: OpcaoDaJanela, retrato: Retrato) -> str:
    codigo = "\n".join(retrato.css_linhas)
    rotulo = "" if o.grupo else f'<span class="tm-sec-rot">{_e(o.rotulo)}</span>'
    return (f'<div class="tm-sec" id="{PEDACO}op-{_a(o.id)}">{rotulo}'
            f'<div class="tm-acoes">{_controle_da_opcao(o)}{_nota_da_opcao(o)}</div>'
            f'<pre class="tm-codigo{"" if codigo else " vazio"}">{_e(codigo) or SEM}</pre></div>')


def _peca(o: OpcaoDaJanela, retrato: Retrato, por_id: Mapping[str, OpcaoDaJanela],
          aparecem: Collection[str]) -> str:
    p = retrato.papeis
    if o.id == p.cor and retrato.cartas:
        importado = next((por_id[i] for i in p.importados.values() if i in por_id), None)
        return _cores_html(o, retrato, importado)
    if o.id in p.importados.values() and p.cor in por_id:
        return ""
    if o.id == p.destaque and o.tipo == "cor":
        return _destaque_html(o, retrato)
    if o.id == p.botoes and o.tipo == "escolha":
        return _botoes_html(o, retrato)
    if o.id == p.logo:
        return _logo_html(o)
    if o.id == p.css:
        return _css_html(o, retrato)
    return _linha_da_opcao(o) if o.id in aparecem else ""


def _abas_html(opcoes: Sequence[OpcaoDaJanela], retrato: Retrato, aba: str, mod: str,
               aparecem: Collection[str]) -> str:
    grupos = _grupos_das_opcoes(opcoes)
    aberta = aba if aba in grupos else next(iter(grupos), "")
    por_id = {o.id: o for o in opcoes}
    telas = []
    for n, (nome, itens) in enumerate(grupos.items()):
        chave, resto = chave_da_aba(nome, itens)
        miolo = "".join(_peca(o, retrato, por_id, aparecem) for o in resto)
        if chave is not None:
            miolo = (f'<div class="mj-da-chave{"" if chave.valor else " apagada"}" '
                     f'id="{PEDACO}da-chave-{n}">{miolo}</div>')
        telas.append(f'{_radio_da_aba(n, nome, aberta, mod)}'
                     f'<label for="mj-aba-{n}">{_e(nome)}{_bolinha_da_aba(n, chave)}</label>'
                     f'<div class="mj-tela tm-tela" id="{PEDACO}tela-{n}">{miolo}</div>')
    return (f'<div class="ac-card mj-abas" style="--n:{len(grupos)}">{"".join(telas)}</div>'
            if telas else "")


def faixa_html(retrato: Retrato) -> str:
    """A faixa «Ao vivo»: a paleta que a tela pinta agora, cada cor com o papel e o valor na
    dica, e o menor contraste do texto."""
    pecas = "".join(
        f'<i style="--c:{_a(retrato.cores[t])}" data-dica="{_a(rt.papel_do_token(t))} · '
        f'{_a(retrato.cores[t])}"></i>' for t, _ in rt.PAPEL_DOS_TOKENS if t in retrato.cores)
    contraste = (f'<span class="tm-contraste" data-dica="{DICA_DO_CONTRASTE}">'
                 f"{_numero(retrato.contraste)}:1</span>" if retrato.contraste else "")
    return (f'<div class="mj-faixa tm-faixa" id="{PEDACO}tema-vivo">'
            f'<div class="mj-faixa-topo"><span class="pc-sub">Ao vivo</span>{contraste}</div>'
            f'<div class="tm-paleta">{pecas}</div></div>')


def janela_do_tema_html(nome: str, opcoes: Sequence[OpcaoDaJanela], retrato: Retrato, *,
                        mod: str, aba: str = "", parar: str = "",
                        aparecem: Collection[str] = ()) -> str:
    """O miolo da janela de uma extensão de tema, no arranjo C da Lovense."""
    return _arranjo_c(nome, _abas_html(opcoes, retrato, aba, mod, aparecem), mod=mod, agora=(),
                      estado=None, parar=parar, faixa=faixa_html(retrato),
                      coluna=coluna_html(retrato, nome), corpo="tm-corpo")


__all__ = ["GESTO_DE_EXPORTAR", "coluna_html", "faixa_html", "janela_do_tema_html", "mini_html",
           "recusa_curta"]
