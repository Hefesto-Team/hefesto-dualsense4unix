"""ABA 10 — a DICA da linha por controle não pode nomear o aparelho.

A LEI, e ela é dela (03/09/2026):

    *"imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
    glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho
    entende? nada hardcoded. trazer tudo que eu já mapeei. eu quero que cada
    user ao usar seu controle se toque disso que o app se adaptou ao controle
    dele"*  (noqa-acento: citação literal dela)

O IRMÃO DESTA RÉGUA é ``test_aba10_a_identidade_vem_de_cima.py``, que cobra a
BARRA de 3px. Ele fechou o lugar onde a cor do mockup sobrevivia; este fecha o
único que sobrou nesta aba — e é o mesmo defeito escrito em outro atributo.

O QUE ESTAVA NA TELA DELA, medido em 03/09/2026 com P1 White no cabo e P2
Galactic Purple no rádio (``mockup/10-perfis.html``, linhas 1284 e 1342 da
publicada de então)::

    <tr data-hef-uniq="p1" title="Cosmic Red — 4 de 5 ajustes só deste controle.">
      ...<span data-hef="guarda.nome">P1 • White • USB</span>

A célula dizia o aparelho; o ``title`` da MESMA linha dizia o desenho. E as
duas metades da frase estavam erradas ao mesmo tempo: o perfil dela guarda
ZERO ajustes por controle — o painel ao lado já anunciava ``0 de 2``.

POR QUE NÃO SE PINTA, e é estrutural, não preguiça: o ``escrever()`` do piloto
conhece sete alvos (``texto``, ``largura``, ``fundo``, ``valor``, ``html``,
``cor``, ``classe``) e **nenhum escreve atributo**. O alvo ``atributo`` que
nasceu nesta leva também não alcança — a guarda ``atributo_escrevivel`` aceita
só nome ``data-*``/``aria-*``, para que ninguém possa forjar o selo
``data-hef-visto``, e ``title`` cai fora por construção. Um ``title`` emitido
pelo gerador fica congelado no arquivo para sempre.

TIRAR FOI A CURA, E NÃO PERDEU NADA: o modelo está na PRÓPRIA célula que o
cursor toca (``guarda.nome``, vivo) e a conta está na coluna ao lado
(``guarda.secao``, alvo ``classe``, vivo). É a decisão nº4 dela deste mesmo
dia, sobre esta mesma tabela: *"Meu Deus melhor nenhuma assim. Auto falante é
auto falante, gatilho é gatilho."*

AS QUATRO MORDIDAS, e cada uma acusa uma metade diferente:

    devolva `title="{c['nome']} — {quantos}."` a `aba10.linha_do_controle`
        -> `test_a_linha_de_controle_na_mesa_nao_tem_dica` reprova, e o
           `exigir` do próprio gerador reprova antes, ao regerar.
    tire a dica do lugar VAZIO junto
        -> `test_o_lugar_vazio_continua_com_a_dica` reprova: a assimetria é
           decisão, não sobra de uma deleção.
    ponha `title="Nova Pink"` numa célula da tabela por controle
        -> `test_nenhuma_dica_da_tabela_nomeia_um_modelo_do_mapa` reprova, e
           ela pega os 28 do CSV, não os 4 do desenho.
    ensine o piloto a escrever `title`
        -> `test_alvo_nenhum_do_piloto_escreve_title` reprova, e aí a cura
           pode ser revista: com um canal de pintura, a dica volta VIVA.
"""
from __future__ import annotations

import re

from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva, monta, onde

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

#: A TABELA POR CONTROLE, e só ela. A fita de chips do topo também nomeia o
#: modelo num `title`, e ali está CERTO: ela é `monta.fita()`, e o piloto troca
#: o `outerHTML` dela inteiro a cada tique com a mesa viva. Medir a página toda
#: acusaria a fita curada e deixaria de separar o que se pinta do que congela.
ABRE = '<table class="tab miuda">'


def _bancada() -> str:
    return onde.pagina(PAGINA).read_text(encoding="utf-8")


def _publicada() -> str:
    return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")


def _tabela(html: str) -> str:
    """O trecho entre a abertura da tabela por controle e o `</table>` dela."""
    assert ABRE in html, f"a tabela por controle sumiu de {PAGINA}"
    return html.split(ABRE, 1)[1].split("</table>", 1)[0]


def _linhas(html: str) -> list[str]:
    return re.findall(r'<tr data-hef-uniq="[^"]+"[^>]*>', _tabela(html))


#: Quem está na mesa do DESENHO e quem é lugar vazio — lido do gerador, nunca
#: digitado aqui. `monta.MESA` é o dono dos quatro lugares desta tabela.
NA_MESA = [c["pref"] for c in monta.MESA if c.get("conectado", True)]
VAZIOS = [c["pref"] for c in monta.MESA if not c.get("conectado", True)]


# --------------------------------------------------------------------------
# 1. A LINHA DE QUEM ESTÁ NA MESA NÃO CARREGA DICA
# --------------------------------------------------------------------------
def test_a_linha_de_controle_na_mesa_nao_tem_dica() -> None:
    """MORDIDA: devolva o `title=` ao `<tr>` em `aba10.linha_do_controle`."""
    com_dica = [t for c, t in zip(monta.MESA, _linhas(_bancada()), strict=True)
                if c.get("conectado", True) and "title=" in t]
    assert not com_dica, (
        f"{len(com_dica)} linha(s) de controle NA MESA voltaram a ter dica. "
        f"Atributo nenhum desta página é pintado: o nome do modelo ali fica "
        f"sendo o do DESENHO enquanto a célula ao lado já traz o do aparelho.")


#: A PUBLICADA AINDA CARREGA A DICA, e isso é ESPERA declarada, não descuido.
#: O gerador escreve a bancada; quem leva a bancada ao produto é ela, por
#: `scripts/check_o_desenho_aprovado.py --aprovar` — *"primeiro nunca terminamos
#: o mockup (…) Vamos concluir lá e depois seguimos pra interface."*
#:
#: O teste abaixo é o que impede esta linha de apodrecer: no dia em que a
#: publicação acontecer ele reprova, e quem publicar troca o `True` por `False`
#: no mesmo commit — a partir daí a régua cobra a publicada para sempre.
ESPERA_A_PUBLICACAO = True


def test_a_publicada_nao_fica_curada_em_silencio() -> None:
    """Curar a bancada e deixar a publicada é a correção pela metade que esta
    casa persegue — e aqui ela seria invisível, porque a régua do mockup não lê
    `title` e portão nenhum compara as duas nesse ponto.

    MORDIDA (as duas, e é por isso que a igualdade é com `==` e não com `not`):
        publique a aba e não mexa em `ESPERA_A_PUBLICACAO` -> reprova;
        troque para `False` antes de publicar -> reprova.
    """
    ainda = [t for c, t in zip(monta.MESA, _linhas(_publicada()), strict=True)
             if c.get("conectado", True) and "title=" in t]
    assert bool(ainda) == ESPERA_A_PUBLICACAO, (
        f"a publicada tem {len(ainda)} linha(s) com a dica do desenho e a "
        f"declaração diz `ESPERA_A_PUBLICACAO = {ESPERA_A_PUBLICACAO}`. As duas "
        f"discordam: ou a publicação aconteceu e a declaração ficou para trás, "
        f"ou ela foi apagada antes da hora.")


# --------------------------------------------------------------------------
# 2. A DICA DO LUGAR VAZIO FICA — a assimetria é decisão
# --------------------------------------------------------------------------
def test_o_lugar_vazio_continua_com_a_dica() -> None:
    """`P3` é um LUGAR, não uma peça: aquela frase não afirma nada sobre
    aparelho nenhum, então não envelhece quando a mesa muda.

    Sem este teste, "tirar as dicas da tabela" levaria as duas juntas na
    próxima limpeza, e a resposta a *"por que este lugar vazio continua aqui?"*
    sairia da tela — que é dado dela, decidido em 31/08/2026.

    MORDIDA: tire o `title` do ramo `else` de `linha_do_controle`.
    """
    assert VAZIOS, "o desenho não tem lugar vazio — esta régua perdeu o objeto"
    sem_dica = [c["pref"] for c, t in zip(monta.MESA, _linhas(_bancada()), strict=True)
                if not c.get("conectado", True) and "title=" not in t]
    assert not sem_dica, (
        f"o lugar vazio {sem_dica} perdeu a dica que explica por que ele "
        f"continua na tabela. Ela não fala de aparelho nenhum: não envelhece.")


# --------------------------------------------------------------------------
# 3. NENHUMA DICA DA TABELA NOMEIA UM MODELO — e são os 28, não os 4
# --------------------------------------------------------------------------
def test_nenhuma_dica_da_tabela_nomeia_um_modelo_do_mapa() -> None:
    """A régua olha TODA dica da tabela por controle, contra os 28 modelos que
    ela mapeou — não contra os quatro do desenho.

    A diferença é o ponto inteiro: uma régua que procurasse "Cosmic Red" e
    "Starlight Blue" ficaria verde no dia em que alguém escrevesse
    `title="Nova Pink"`, e o defeito é o MESMO. Ela mapeou 28; a régua também.

    MORDIDA: ponha `title="Nova Pink"` numa `<td>` de `linha_do_controle`.
    """
    modelos = {nome for _, nome in mesa_viva.CORES.values() if nome}
    assert len(modelos) >= 28, (
        f"o mapa das cores encolheu para {len(modelos)} modelos — esta régua "
        f"mede contra `docs/data/cores-do-dualsense.csv`, e ele é o dono")
    dicas = re.findall(r'title="([^"]*)"', _tabela(_bancada()))
    culpadas = [(d, m) for d in dicas for m in modelos if m in d]
    assert not culpadas, (
        f"{len(culpadas)} dica(s) da tabela por controle nomeiam um modelo: "
        f"{culpadas[:3]}. Nome de aparelho em atributo não pintado é o desenho "
        f"mandando na tela de quem tem outro controle.")


def test_o_nome_do_modelo_so_vive_em_elemento_enderecado() -> None:
    """Onde o modelo APARECE na tabela, ele tem de estar num elemento que o
    piloto pinta — hoje é um só: `guarda.nome`.

    Este é o teste que sobrevive a uma reescrita da tabela: ele não fala de
    `<tr>` nem de `title`, fala do FATO — identidade de aparelho só existe
    nesta página onde há endereço para reescrevê-la.
    """
    modelos = {nome for _, nome in mesa_viva.CORES.values() if nome}
    tabela = _tabela(_bancada())
    # Os pedaços fora de um `<span data-hef="guarda.nome">…</span>`: se um nome
    # de modelo aparecer aqui, ele está num lugar que ninguém repinta.
    #
    # O `</td>` NA ÂNCORA NÃO É ENFEITE: o rótulo curto traz `<span class="pt">`
    # em volta de cada separador, e um `.*?</span>` fecharia no PRIMEIRO deles —
    # `Cosmic Red` vazaria para fora do recorte e a régua acusaria a si mesma.
    # Custou a primeira execução deste arquivo.
    solto = re.sub(r'<span data-hef="guarda\.nome">.*?</span>\s*</td>', "", tabela,
                   flags=re.DOTALL)
    achados = sorted({m for m in modelos if m in solto})
    assert not achados, (
        f"{achados} aparece(m) na tabela por controle FORA do único elemento "
        f"que o produto reescreve (`guarda.nome`). Quem lê a tela vê o modelo "
        f"do mockup sobre o aparelho dela.")


# --------------------------------------------------------------------------
# 4. O TRIPWIRE — o dia em que o piloto souber pintar `title`, revejam a cura
# --------------------------------------------------------------------------
def test_alvo_nenhum_do_piloto_escreve_title() -> None:
    """A razão de a dica ter SAÍDO em vez de virar dado é que não há canal.

    Se alguém abrir um — um alvo que escreva `title`, ou a guarda
    `atributo_escrevivel` passar a aceitá-lo —, esta remoção deixa de ser a
    melhor resposta: a dica pode voltar VIVA, com o modelo e a conta do
    aparelho. Este teste é o bilhete para essa pessoa, e ele reprova no dia
    em que o canal existir.

    MORDIDA: acrescente `el.title = t;` ao `escrever()` de `hefesto_vivo`.
    """
    fonte = hefesto_vivo.PINTAR if hasattr(hefesto_vivo, "PINTAR") else ""
    for nome in dir(hefesto_vivo):
        valor = getattr(hefesto_vivo, nome)
        if nome.isupper() and isinstance(valor, str) and "function escrever" in valor:
            fonte = valor
    assert "function escrever" in fonte, (
        "não achei o `escrever()` do piloto para conferir — se ele mudou de "
        "casa, esta régua precisa de um ponteiro novo, não de ser apagada")
    canais = re.findall(r"\.title\s*=|setAttribute\(\s*['\"]title['\"]", fonte)
    assert not canais, (
        "o piloto aprendeu a escrever `title`. A dica da linha por controle "
        "foi REMOVIDA em 03/09/2026 justamente por não haver canal — com um, "
        "ela deve voltar viva (modelo e conta do aparelho), e não ficar fora "
        "por inércia. Ver `aba10.linha_do_controle`.")
