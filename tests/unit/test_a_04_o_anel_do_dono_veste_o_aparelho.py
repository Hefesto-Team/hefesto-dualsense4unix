#!/usr/bin/env python3
"""A COR DO PLÁSTICO DA 04 NÃO SE CRAVA — nem no anel, nem no antes/depois.

A LEI, e é do usuário (03/09/2026):


O DESENHO GRANDE já vestia o aparelho desde 03/09 de manhã — o `data-colorway`
com o alvo `atributo`, e a folha das cores com os vinte e oito modelos do mapa
dela. O que sobrava na `04-iluminacao` eram **doze `--plastico:#hex`** em dois
lugares, e os dois pareciam curados sem estar:

    4  o anelzinho do dono, dentro de cada botão da fileira de números
    8  os itens do "Trocar o número: o antes e o depois", no rodapé

OS DOIS TINHAM ENDEREÇO E NENHUM TINHA ALVO, e isso é **meia fechadura**. O
`achar()` do piloto encontra pelo endereço; o `data-hef-alvo` é o que diz o que
escrever quando ele chega lá — e sem ele o `escrever()` cai no ramo padrão e
faria `el.textContent = "#e35b8c"` dentro do anel. Os dois contavam com o pai:
a fileira é reescrita inteira pelo alvo `html`, e a seção da troca pelo
`blocos:`. Nenhuma das duas coisas se lê no HTML — a primeira é do pai, e a
segunda mora no JavaScript —, então para as duas réguas desta casa aquilo era
cor congelada, e era acusado com razão pela letra dela: *"um pai endereçado não
dá ao filho o direito de trazer cor congelada"*.

A CURA É O PAR COMPLETO: endereço próprio (`players.dono.N`, um por número, e
`troca.item`) mais `data-hef-alvo="plastico"`, e o pacote emitindo o valor. O
que ela ganha: o anel e o item passam a deixar o **selo da visita**, que é o
único fato que a tela não mostra — que o piloto esteve ali com um valor.

MEDIDO NO WEBKIT DESTA MÁQUINA, com uma mesa forçada a **Nova Pink** e **Astro
Bot** — dois modelos que o desenho da 04 não tem::

    players.dono.1  --plastico #e35b8c   borda computada rgb(227, 91, 140)
    players.dono.2  --plastico #e8e4dc   borda computada rgb(232, 228, 220)
    troca.item x4   selo `data-hef-visto="1"` nos quatro

NADA AQUI É DIGITADO. Os hexes esperados saem de `monta.cor_da_zona`, que lê a
folha que `scripts/gerar_cores_do_dualsense.py` escreve do
`docs/data/cores-do-dualsense.csv`; os alvos que o pintor sabe escrever saem do
próprio `hefesto_vivo.py`; e o veredito sobre a página é o do PORTÃO, carregado
do arquivo — uma segunda régua colada aqui divergiria dele no primeiro ajuste.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

import monta

BANCADA = RAIZ / "mockup/04-iluminacao.html"
PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
PORTAO = RAIZ / "scripts/check_a_cor_vem_do_aparelho.py"

FORA_DO_DESENHO = ("nova-pink", "astro-bot", "sterling-silver")


def _portao() -> Any:
    """O portão da cor, carregado do arquivo. É ELE quem julga a página."""
    spec = importlib.util.spec_from_file_location("portao_da_cor_04", PORTAO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["portao_da_cor_04"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _mesa(*cores: str) -> list[dict[str, Any]]:
    """Uma mesa de mentira, na forma que `mesa_viva.mesa_do_estado` devolve."""
    return [
        {
            "pref": f"p{i}",
            "uniq": f"{i}" * 12,
            "jogador": i,
            "cor": cor,
            "nome": cor.replace("-", " ").title() if cor else "Não sei",
            "via": "USB" if i == 1 else "BT",
            "transporte": "usb" if i == 1 else "bt",
            "alvo": i == 1,
            "mascara": "DualSense",
        }
        for i, cor in enumerate(cores, start=1)
    ]


def _contexto(mesa: list[dict[str, Any]]) -> Contexto:
    return Contexto(
        state={"controllers": []},
        mesa=mesa,
        conectados=[{"uniq": c["uniq"], "transport": c["transporte"]} for c in mesa],
        estados={},
    )


def _colunas(mesa: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return a04.pacote(_contexto(mesa)).get("colunas") or {}


def test_a_bancada_da_04_nao_crava_nenhuma_cor_de_aparelho() -> None:
    """Zero achados do portão da cor na `mockup/04-iluminacao.html`."""
    portao = _portao()
    achados = portao.cravados_de(BANCADA, portao.colorways_do_mapa())
    assert not achados, (
        "a 04 voltou a cravar cor de aparelho:\n  "
        + "\n  ".join(f"linha {a[0]} [{a[1]}] {a[2]} — {a[3]}" for a in achados))


def test_todo_plastico_da_04_tem_o_alvo_que_o_alcanca() -> None:
    """Todo `--plastico:#hex` da bancada mora num elemento que o produto reescreve.

    ESTA É A OUTRA METADE DA PRIMEIRA, e ela é escrita ao contrário de
    propósito: aquela pergunta ao portão *"há achado?"*; esta varre o HTML e
    exige, de cada elemento que carrega a cor, o par endereço + alvo. Se alguém
    afrouxar o portão, esta continua acusando; se alguém mudar o nome do alvo,
    aquela continua acusando. Duas réguas independentes é o que revela.

    A ÚNICA ISENÇÃO É A `.fita`, e ela é LIDA do portão — nunca digitada aqui.
    `hefesto_vivo.pintar` troca o `outerHTML` dela inteiro a cada tique, com o
    que `monta.fita(mesa=…)` monta da mesa VIVA; um chip com `--plastico` ali é
    o que o PRODUTO acabou de escrever. Uma segunda lista neste arquivo seria a
    segunda maneira de divergir em silêncio.
    """
    from html.parser import HTMLParser

    trocados = frozenset(_portao().TROCADOS_INTEIROS)
    vazias = frozenset([
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    ])

    class _Varre(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.nus: list[str] = []
            self.pilha: list[bool] = []

        def handle_starttag(self, tag: str, attrs: Any) -> None:
            d = {k: (v or "") for k, v in attrs}
            classes = (d.get("class") or "").split()
            trocado = any(c in trocados for c in classes)
            coberto = trocado or any(self.pilha)
            if re.search(r"--plastico\s*:\s*#", d.get("style", "")) and not coberto:
                tem_endereco = any(
                    a in d for a in ("data-campo", "data-papel", "data-hef"))
                alvo = (d.get("data-hef-alvo") or "").strip().lower()
                if not (tem_endereco and alvo in (a04.ALVO_DO_PLASTICO, "html")):
                    self.nus.append(
                        f"linha {self.getpos()[0]}: <{tag} "
                        f"class={d.get('class', '')!r} alvo={alvo!r}>")
            if tag not in vazias:
                self.pilha.append(trocado)

        def handle_startendtag(self, tag: str, attrs: Any) -> None:
            self.handle_starttag(tag, attrs)
            if tag not in vazias and self.pilha:
                self.pilha.pop()

        def handle_endtag(self, tag: str) -> None:
            if tag not in vazias and self.pilha:
                self.pilha.pop()

    varre = _Varre()
    varre.feed(BANCADA.read_text(encoding="utf-8"))
    assert not varre.nus, (
        "a 04 tem `--plastico` que o produto não alcança:\n  "
        + "\n  ".join(varre.nus))


def test_o_alvo_do_plastico_e_um_que_o_pintor_sabe_escrever() -> None:
    """O alvo pedido pela página existe no `escrever()` do piloto."""
    sabidos = set(re.findall(r"alvo === '([a-z]+)'", PILOTO.read_text(encoding="utf-8")))
    assert a04.ALVO_DO_PLASTICO in sabidos, (
        f"o pintor não sabe escrever `{a04.ALVO_DO_PLASTICO}` — os que ele sabe "
        f"são {sorted(sabidos)}")


def test_o_anel_de_cada_numero_recebe_a_cor_do_dono_daquele_numero() -> None:
    """`players.dono.N` sai com a casca de quem tem o número N, não a da coluna."""
    mesa = _mesa(*FORA_DO_DESENHO)
    colunas = _colunas(mesa)
    assert len(colunas) == len(mesa), f"colunas do pacote: {sorted(colunas)}"

    esperado = {
        c["jogador"]: str(monta.cor_da_zona(c["cor"])) for c in mesa
    }
    do_desenho = set(re.findall(r"--plastico:(#[0-9a-fA-F]{6})",
                                BANCADA.read_text(encoding="utf-8")))
    for numero, hexa in esperado.items():
        assert hexa.lower() not in {h.lower() for h in do_desenho}, (
            f"o modelo do P{numero} está no desenho ({hexa}) — troque a mesa de "
            "mentira, porque assim esta régua não separa o produto do mockup")

    for uniq, campos in colunas.items():
        for numero in a04.NUMEROS:
            chave = a04.endereco_do_anel(numero)
            assert chave in campos, (
                f"a coluna {uniq} não emite o anel do número {numero}")
            assert campos[chave] == esperado.get(numero, ""), (
                f"o anel do {numero} na coluna {uniq} recebeu "
                f"{campos[chave]!r}, e o dono daquele número é "
                f"{esperado.get(numero, '')!r}")


def test_um_numero_sem_dono_na_mesa_nao_recebe_cor_nenhuma() -> None:
    """Número livre é anel vazio — e o vazio APAGA a variável."""
    colunas = _colunas(_mesa("sterling-silver"))
    campos = next(iter(colunas.values()))
    assert campos[a04.endereco_do_anel(1)] == str(monta.cor_da_zona("sterling-silver"))
    for numero in (2, 3, 4):
        assert campos[a04.endereco_do_anel(numero)] == "", (
            f"o número {numero} não tem dono na mesa e recebeu cor: "
            f"{campos[a04.endereco_do_anel(numero)]!r}")


def test_o_anel_vem_depois_da_fileira_que_o_recria() -> None:
    """A ordem dos campos importa: `players` troca o miolo e RECRIA os anéis."""
    campos = next(iter(_colunas(_mesa("nova-pink", "astro-bot")).values()))
    ordem = list(campos)
    assert "players" in ordem, "a fileira de números saiu do pacote"
    for numero in a04.NUMEROS:
        assert ordem.index(a04.endereco_do_anel(numero)) > ordem.index("players"), (
            f"o anel do {numero} é escrito ANTES da fileira que o recria — o "
            "selo da visita se perde a cada tique")


def test_a_lista_da_troca_casa_item_a_item_com_o_html_que_a_secao_desenha() -> None:
    """`cores_da_troca` na ordem exata em que `secao_da_troca` põe os itens."""
    mesa = _mesa(*FORA_DO_DESENHO)
    html = a04.secao_da_troca(mesa)
    no_html = re.findall(
        r'class="troca-item[^"]*"[^>]*?--plastico:(#[0-9a-fA-F]{6})', html)
    assert no_html, "a seção da troca deixou de desenhar item com cor"
    assert no_html == a04.cores_da_troca(mesa), (
        "a lista do campo e o HTML da seção saíram em ordens diferentes:\n"
        f"  html : {no_html}\n  campo: {a04.cores_da_troca(mesa)}")


def test_a_lista_da_troca_tem_um_valor_por_item_desenhado() -> None:
    """Nem valor sobrando nem faltando — em qualquer tamanho de mesa."""
    for quantos in range(0, len(FORA_DO_DESENHO) + 1):
        mesa = _mesa(*FORA_DO_DESENHO[:quantos])
        itens = a04.secao_da_troca(mesa).count('class="troca-item')
        assert len(a04.cores_da_troca(mesa)) == itens, (
            f"com {quantos} controle(s) a seção desenha {itens} item(ns) e a "
            f"lista traz {len(a04.cores_da_troca(mesa))} valor(es)")


def test_o_pacote_manda_a_lista_da_troca_com_a_mesa_viva() -> None:
    """O campo sai do pacote, com as cores da mesa — e não do desenho."""
    mesa = _mesa("nova-pink", "astro-bot")
    lista = a04.pacote(_contexto(mesa)).get(a04.ITEM_DA_TROCA)
    esperadas = [str(monta.cor_da_zona(c["cor"])) for c in mesa]
    assert lista == esperadas + esperadas, (
        f"o pacote mandou {lista!r} e a mesa é {esperadas!r} nas duas linhas")
