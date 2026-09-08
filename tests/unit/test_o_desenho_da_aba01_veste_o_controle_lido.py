#!/usr/bin/env python3
"""O DESENHO DA ABA 01 VESTE O CONTROLE LIDO — os 28 modelos dela, não os 4 do mockup.

A LEI, e ela é dela (03/09/2026):

    "imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
    glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho
    entende? nada hardcoded. trazer tudo que eu já mapeei."   (noqa-acento: citação literal dela)

    "os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
    players com cada controle — tudo isso muda de acordo com o controle
    identificado no canto superior. é white no p1, mas a borda de tudo é cosmic
    red e os svgs não são os que o meu mapa cataloga. isso tá errado"

O DEFEITO ESTAVA FOTOGRAFADO antes desta régua existir. Com os dois controles
dela na mesa, a `01-jogar` publicada mostrava, com quatro pixels entre uma coisa
e outra (medido na foto, no pixel):

    rótulo do cartão (lido do aparelho)   White · USB      Galactic Purple · BT
    desenho do controle (do MOCKUP)       #ae335a          #7eb8d4
                                          Cosmic Red       Starlight Blue

AS DUAS METADES, e a segunda é a que quase ninguém vê:

1. o `<svg>` ganha ENDEREÇO com o alvo `atributo`, e o pacote emite o colorway
   do controle daquela coluna;
2. **a folha das 28 cores sai de dentro dos desenhos e é publicada UMA vez na
   página.** Sem isto o endereço da metade 1 escreve um modelo que regra
   nenhuma casa: `monta._so_o_colorway` deixa em cada SVG só as regras do
   modelo pedido, e o desenho cai nos ``fill`` crus do ``ds_limpo.svg`` —
   ``rgb(58, 63, 75)``. *Trocar-se-ia uma cor errada por um cinza.*

O QUE ESTA RÉGUA MEDE NO MOTOR, e não no texto: com a página aberta num
WebKit offscreen, ela escreve cada um dos 28 colorways do mapa dela no desenho
do P1 e lê o ``fill`` COMPUTADO do chassi. O hexadecimal esperado sai de
``monta.cor_da_zona`` — que lê a folha gerada do
``docs/data/cores-do-dualsense.csv`` —, nunca digitado aqui.

**A MORDIDA QUE ELA SOFRE:** devolver a poda ao ``_desenho`` (a folha de volta
para dentro de cada SVG) deixa 24 dos 28 modelos no cinza cru, e
:func:`test_os_vinte_e_oito_modelos_dela_pintam_no_motor` reprova nomeando
quantos caíram.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# O import do PACOTE é o que põe `interface/` no `sys.path` (`pacotes/__init__`
# faz o `insert`), e é o que deixa `import monta` funcionar logo abaixo.
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a01_jogar

import monta

#: A BANCADA, e não o publicado. É onde `aba01.py` escreve, e é o desenho de
#: HOJE — apontar para `paginas/` daria verde sobre a página congelada, que é a
#: armadilha mais cara do `COMO-OLHAR-A-TELA.md`.
BANCADA = RAIZ / "mockup/01-jogar.html"

#: O `fill` cru do `ds_limpo.svg` — o que o chassi mostra quando regra nenhuma
#: casa. Ele não é digitado: é lido do desenho, no mesmo `<g class="z-casca">`
#: que a folha pinta.
CRU = re.compile(r'<g id="jg-p1-corpo" class="z-casca"[^>]*>\s*(?:<title>[^<]*</title>\s*)?'
                 r'<path[^>]*fill="(#[0-9a-fA-F]{6})"')

#: O ENDEREÇO COMPLETO do desenho: os três atributos juntos. Dois deles sem o
#: terceiro não pintam nada — `data-hef-alvo="atributo"` sem
#: `data-hef-atributo` não sabe o que escrever, e com o nome errado escreve
#: outro atributo e deixa o colorway cravado.
ENDERECO = ('data-campo="desenho" data-hef-alvo="atributo"'
            ' data-hef-atributo="data-colorway"')


def _pagina() -> str:
    if not BANCADA.is_file():
        pytest.skip(f"a bancada não tem {BANCADA.name} — rode aba01.py")
    return BANCADA.read_text(encoding="utf-8")


def _fileira_de_cartoes(doc: str) -> str:
    """Só a fileira dos quatro cartões — dono único do corte, nas duas réguas.

    O FIM ERA `class="col-atencao"` ATÉ 07/09/2026, quando a coluna Atenção saiu
    da Jogar por ordem dela; agora é a `.faixa-final`, que é o que ficou logo
    abaixo dos cartões.

    E O CORTE PASSOU A LEVANTAR, em vez de devolver o resto da página. Com
    `split()` um delimitador que some devolve TUDO o que vem depois, calado — as
    duas réguas deste arquivo procuram por AUSÊNCIA (`data-controle="dualsense"`
    e a folha podada), e uma fileira que engordasse para a legenda inteira só
    poderia ficar mais verde. O `index` reprova na hora, que é o que uma delas
    espera de um delimitador.
    """
    i = doc.index('data-lista="cartoes"')
    fileira = doc[i:doc.index('<div class="faixa-final', i)]
    assert len(fileira) > 2000, "a régua não achou a fileira de cartões"
    return fileira


def _colorways_da_folha(css: str) -> set[str]:
    """Os modelos que uma folha declara. A mesma leitura dos dois lados."""
    return set(re.findall(r'svg\[data-colorway="([^"]+)"\]', css))


# ---------------------------------------------------------------------------
# 1. o endereço existe, nos quatro cartões
# ---------------------------------------------------------------------------
def test_os_quatro_desenhos_tem_endereco_com_o_alvo_de_atributo() -> None:
    doc = _pagina()
    achei = doc.count(ENDERECO)
    assert achei == len(monta.MESA), (
        f"esperava {len(monta.MESA)} desenhos endereçados e achei {achei}. "
        "Sem os TRÊS atributos juntos o piloto cai no ramo padrão e escreve o "
        "valor como TEXTO por cima do controle.")
    # E O ENDEREÇO MORA NO PRÓPRIO `<svg>`: escrito num pai, o `escrever()`
    # acharia o pai e o seletor `svg[data-colorway=…]` da folha nunca casaria.
    assert doc.count(f"<svg {ENDERECO}") == len(monta.MESA), (
        "o endereço saiu de cima do `<svg>` — a folha das cores casa pelo "
        "seletor `svg[data-colorway=…]`, e num `<div>` ele não vale")


def test_o_desenho_nao_diz_ser_o_dono_da_coluna() -> None:
    """O `data-controle="dualsense"` do arquivo sai dos quatro desenhos.

    Ele diz o TIPO do desenho, não o controle da coluna — e o piloto e a
    `regua_do_mockup` acham o dono de um campo por
    ``closest('[data-controle],[data-uniq]')``, que num elemento com o atributo
    devolve **ele mesmo**. Com ele, o campo `desenho` sairia das duas leituras
    com dono ``"dualsense"``, que não é coluna nenhuma da carga: o endereço
    nasceria morto na régua, com o atributo presente e a tela igualmente errada.
    """
    doc = _pagina()
    fileira = _fileira_de_cartoes(doc)
    assert 'data-controle="dualsense"' not in fileira


# ---------------------------------------------------------------------------
# 2. a folha das 28 é da PÁGINA, e sai de dentro dos desenhos
# ---------------------------------------------------------------------------
def test_a_folha_das_cores_e_publicada_uma_vez_com_os_vinte_e_oito() -> None:
    doc = _pagina()
    assert doc.count('<style id="cores-do-dualsense-folha">') == 1, (
        "a tabela das cores tem de estar publicada exatamente uma vez: quatro "
        "cópias podadas são quatro escolhas cravadas, e quatro cópias inteiras "
        "são 180 KB de CSS repetido")
    # O NÚMERO NÃO SE DIGITA: sai do `monta.DS`, que é a folha que
    # `scripts/gerar_cores_do_dualsense.py` escreveu do CSV dela.
    dela = _colorways_da_folha(monta.DS)
    assert len(dela) >= 28, "o `ds_limpo.svg` perdeu modelos — não há o que medir"
    assert _colorways_da_folha(doc) == dela


def test_nenhum_desenho_carrega_a_propria_folha_podada() -> None:
    doc = _pagina()
    fileira = _fileira_de_cartoes(doc)
    assert "cores-do-dualsense-folha" not in fileira, (
        "um desenho voltou a carregar a folha podada — com ela, escrever "
        "outro colorway não casa regra nenhuma e o chassi cai no cinza cru")


# ---------------------------------------------------------------------------
# 3. o pacote escreve o que LEU, e cala o que não leu
# ---------------------------------------------------------------------------
def test_o_pacote_promete_o_desenho_entre_os_campos_do_cartao() -> None:
    assert "desenho" in a01_jogar.POR_CARTAO, (
        "sem o nome em `POR_CARTAO` a cobertura conta menos do que o pacote "
        "emite — e ela é O instrumento com que esta casa prova um endereço")


def test_o_pacote_emite_o_colorway_do_controle_e_nao_o_do_desenho() -> None:
    """Com um controle Nova Pink na mesa, o pacote emite `nova-pink`.

    O modelo é escolhido de propósito FORA dos quatro do desenho
    (`cosmic-red`, `starlight-blue`, `galactic-purple`, `white`): é o caso que
    a versão anterior não sabia mostrar.
    """
    uniq = "aa:bb:cc:00:00:01"
    ctx = Contexto(
        state={},
        mesa=[{"uniq": uniq, "pref": "p1", "cor": "nova-pink",
               "nome": "Nova Pink", "via": "USB"}],
        conectados=[{"uniq": uniq, "connected": True, "player_slot": 1,
                     "battery_pct": 80, "transport": "usb"}],
    )
    cartao = a01_jogar.pacote(ctx)["cartoes"][uniq]
    assert cartao["desenho"] == "nova-pink"
    # E A BORDA CONCORDA: as duas saem do mesmo dono, `monta.cor_da_zona`.
    assert cartao["plastico"] == monta.cor_da_zona("nova-pink")


def test_sem_cor_lida_o_desenho_nao_afirma_modelo_nenhum() -> None:
    """Vazio e desconhecido calam — a regra dela, campo sem informação não mostra nada.

    Pelo RÁDIO a cor às vezes não vem, e o primeiro tique de uma sessão tem a
    mesa sem cor. Emitir o colorway do mockup nesses dois casos é exatamente o
    defeito que este trabalho existe para matar; emitir um slug que a folha não
    tem seria pior ainda, porque o desenho ficaria cinza e a borda ao lado sem
    cor, sem ninguém saber por quê.
    """
    assert a01_jogar._colorway_do_desenho("") == ""
    assert a01_jogar._colorway_do_desenho("modelo-que-nao-existe") == ""
    # e ele CALA JUNTO com a borda: as duas perguntam ao mesmo dono
    for slug in ("", "modelo-que-nao-existe"):
        assert bool(a01_jogar._colorway_do_desenho(slug)) == \
            bool(a01_jogar._cor_do_plastico(slug))


# ---------------------------------------------------------------------------
# 4. E NO MOTOR: os 28 pintam, e o vazio volta ao neutro
# ---------------------------------------------------------------------------
#: O roteiro vai numa ida só ao WebKit: um round-trip por modelo custaria 29
#: cargas de página para medir o que uma mede.
ROTEIRO = """
(function(){
  const svg = document.querySelector('[data-controle="p1"] svg[data-campo="desenho"]');
  if(!svg) return JSON.stringify({erro: 'não achei o desenho do p1'});
  const casca = svg.querySelector('.z-casca path:not([fill="none"])');
  if(!casca) return JSON.stringify({erro: 'não achei o chassi do desenho'});
  const fora = {pintou: {}};
  for(const c of MODELOS){
    svg.setAttribute('data-colorway', c);
    fora.pintou[c] = getComputedStyle(casca).fill;
  }
  svg.removeAttribute('data-colorway');
  fora.apagado = getComputedStyle(casca).fill;
  return JSON.stringify(fora);
})()
"""


def _no_webkit(roteiro: str) -> dict:
    """Abre a bancada num WebKit offscreen e devolve o que o roteiro mediu.

    `Gtk.OffscreenWindow` e não `Gtk.Window`: sob Xvfb não há gerenciador de
    janelas e uma janela comum fica 1x1 para sempre. E offscreen também porque
    ela tem UMA tela — janela de teste não nasce na frente dela.
    """
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v: object, res: object) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def carregou(v: object, evento: object) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    view.connect("load-changed", carregou)
    view.load_uri(BANCADA.as_uri())
    # O `timeout_add` PENDENTE DISPARA NO LAÇO DO PRÓXIMO TESTE de GUI do
    # mesmo processo — 05/09/2026, e a cura já existia em cinco arquivos
    # irmãos (*"Já matou onze medições"*). Aqui ela faltava: medido no
    # lote-00 da suíte, DUAS voltas em três davam *"o WebKit não respondeu
    # em 30 s"* com o `saiu` VAZIO — o laço não estourou, ele foi MORTO por
    # um `main_quit` que outro teste deixou armado. Reprodutível só na
    # ordem aleatória, que é o que o torna invisível quando se roda o
    # arquivo sozinho.
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


def _rgb(hexa: str) -> str:
    """`#ae335a` → `rgb(174, 51, 90)`, a forma em que o WebKit devolve o `fill`."""
    h = hexa.lstrip("#")
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def _como_o_motor_diz(valor: str) -> str:
    """O que o WebKit devolve para o valor que a folha dela escreveu.

    SEIS DOS 28 NÃO SÃO HEXADECIMAL, e eles são a prova mais dura de que a
    tabela compartilhada funciona: `god-of-war-20th` e `spider-man-2` pintam com
    um `<linearGradient>`, e os sete sem hex medido pintam com o
    `<pattern id="hachura-sem-hex">`. Os três moram no `<defs>` que a página
    publica UMA vez — logo, o `url(#…)` de um SVG resolve num `<defs>` que está
    em OUTRO `<svg>` da mesma página. Medido neste motor em 03/09/2026: o WebKit
    devolve `url("#hachura-sem-hex")`, com aspas.
    """
    if valor.startswith("#"):
        return _rgb(valor)
    return valor.replace("url(#", 'url("#').replace(")", '")')


def test_os_vinte_e_oito_modelos_dela_pintam_no_motor() -> None:
    """Cada modelo do mapa dela pinta o chassi com a cor que ela mapeou.

    ESTE É O TESTE QUE A FOLHA PODADA REPROVA. Com a poda de volta, o SVG do P1
    só traz as regras do `cosmic-red`: os outros 27 modelos caem no `fill` cru
    e a asserção lista quantos.
    """
    doc = _pagina()
    achou = CRU.search(doc)
    assert achou, "o chassi do desenho do P1 mudou de forma — não há neutro a medir"
    cru = _rgb(achou.group(1))

    modelos = sorted(_colorways_da_folha(monta.DS))
    medido = _no_webkit(ROTEIRO.replace("MODELOS", json.dumps(modelos)))
    assert "erro" not in medido, medido.get("erro")

    # O ESPERADO SAI DO DONO, e não de uma tabela aqui: `cor_da_zona` lê a folha
    # que `gerar_cores_do_dualsense.py` escreveu do CSV dela.
    cinzas = [c for c in modelos if medido["pintou"][c] == cru]
    assert not cinzas, (
        f"{len(cinzas)} dos {len(modelos)} modelos dela caíram no cinza cru "
        f"({cru}) — a folha da página não os traz: {cinzas[:6]}")
    erradas = {c: (medido["pintou"][c], monta.cor_da_zona(c, "casca"))
               for c in modelos
               if medido["pintou"][c] != _como_o_motor_diz(monta.cor_da_zona(c, "casca"))}
    assert not erradas, f"o chassi não vestiu a cor do mapa dela: {erradas}"


def test_sem_colorway_o_desenho_volta_ao_neutro_e_nao_ao_mockup() -> None:
    """Apagar o atributo devolve o desenho ao cinza cru — não ao Cosmic Red.

    É a regra dela: campo sem informação não mostra nada. Manter o colorway do
    mockup sobre um aparelho que é outro é o defeito que esta leva existe para
    matar, e pelo rádio a cor pode não vir nunca.
    """
    doc = _pagina()
    achou = CRU.search(doc)
    assert achou, "o chassi do desenho do P1 mudou de forma"
    medido = _no_webkit(ROTEIRO.replace("MODELOS", "[]"))
    assert "erro" not in medido, medido.get("erro")
    assert medido["apagado"] == _rgb(achou.group(1))
