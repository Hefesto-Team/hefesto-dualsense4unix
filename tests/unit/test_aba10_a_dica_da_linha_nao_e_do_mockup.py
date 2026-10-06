"""ABA 10 — a DICA da linha por controle não pode nomear o aparelho.

A LEI, e é do usuário (03/09/2026):

    *"imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
    glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho
    entende? nada hardcoded. trazer tudo que eu já mapeei. eu quero que cada
    user ao usar seu controle se toque disso que o app se adaptou ao controle
    dele"*  (noqa-acento: citação literal)

O IRMÃO DESTA RÉGUA é ``test_aba10_a_identidade_vem_de_cima.py``, que cobra a
BARRA de 3px. Ele fechou o lugar onde a cor do mockup sobrevivia; este fecha o
único que sobrou nesta aba — e é o mesmo defeito escrito em outro atributo.

O QUE ESTAVA NA TELA DO USUÁRIO, medido em 03/09/2026 com P1 White no cabo e P2
Galactic Purple no rádio (``mockup/10-perfis.html``, linhas 1284 e 1342 da
publicada de então)::

    <tr data-hef-uniq="p1" title="Cosmic Red — 4 de 5 ajustes só deste controle.">
      ...<span data-hef="guarda.nome">P1 • White • USB</span>

A célula dizia o aparelho; o ``title`` da MESMA linha dizia o desenho. E as
duas metades da frase estavam erradas ao mesmo tempo: o perfil do usuário guarda
ZERO ajustes por controle — o painel ao lado já anunciava ``0 de 2``.

POR QUE NÃO SE PINTAVA, e era estrutural, não preguiça: o ``escrever()`` do
piloto conhece sete alvos (``texto``, ``largura``, ``fundo``, ``valor``,
``html``, ``cor``, ``classe``) e **nenhum escreve atributo**. O alvo
``atributo``, que nasceu nesta leva, também não alcançava: a guarda
``atributo_escrevivel`` aceitava só nome ``data-*``/``aria-*``, e ``title``
caía fora por construção.

**O CANAL ABRIU NO MESMO DIA — 03/09/2026.** ``atributo_escrevivel`` passou a
aceitar ``title``, nomeado na lista curta e com a razão escrita no piloto: o
``fim.html`` pedia ``data-hef-atributo="title"`` nas vinte páginas e era
recusado CALADO. **A remoção desta dica deixa de ser a melhor resposta**: com um
canal, ela pode voltar VIVA, com o modelo e a conta do aparelho, em vez de ficar
fora por inércia. As três primeiras seções deste arquivo continuam valendo — o
que mudou é que a quarta virou trabalho, e não mais um bilhete.

TIRAR FOI A CURA, E NÃO PERDEU NADA: o modelo está na PRÓPRIA célula que o
cursor toca (``guarda.nome``, vivo) e a conta está na coluna ao lado
(``guarda.proprio``, o ponto embaixo de cada glifo, alvo ``classe``, vivo; até
02/10/2026 era o próprio glifo, ``guarda.secao``, que desde então diz o
controle agora). É a decisão nº4 dela deste mesmo dia, sobre esta mesma
tabela: *"Meu Deus melhor nenhuma assim. Auto falante é auto falante, gatilho é
gatilho."*

A CÉLULA GANHOU DICA EM 02/10/2026, e não é a volta das oito: ela só existe
onde há o que dizer (*"O controle não diz."* e a máscara que não é a
DualSense, decisão de 29/09: «a dica diz qual»), vem do pacote
(``guarda.dica``) e não nomeia aparelho. A régua de baixo, que olha TODA dica
da tabela contra os 28 modelos, continua cobrindo-a.

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
    ensine o piloto a escrever `title` POR FORA da guarda (`el.title = t`)
        -> `test_alvo_nenhum_do_piloto_escreve_title` reprova. O canal
           legítimo — o alvo `atributo` com o nome na lista curta — já
           existe desde 03/09; ver a §4.
"""
from __future__ import annotations

import re

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva, monta, onde

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

ABRE = re.compile(r'<table[^>]*class="tab miuda"[^>]*>')


def _bancada() -> str:
    return onde.pagina(PAGINA).read_text(encoding="utf-8")


def _publicada() -> str:
    return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")


def _tabela(html: str) -> str:
    """O trecho entre a abertura da tabela por controle e o `</table>` dela."""
    achou = ABRE.search(html)
    assert achou, f"a tabela por controle sumiu de {PAGINA}"
    return html[achou.end():].split("</table>", 1)[0]


def _linhas(html: str) -> list[str]:
    return re.findall(r'<tr data-hef-uniq="[^"]+"[^>]*>', _tabela(html))


NA_MESA = [c["pref"] for c in monta.MESA if c.get("conectado", True)]
VAZIOS = [c["pref"] for c in monta.MESA if not c.get("conectado", True)]


def test_a_linha_de_controle_na_mesa_nao_tem_dica() -> None:
    """MORDIDA: devolva o `title=` ao `<tr>` em `aba10.linha_do_controle`."""
    com_dica = [t for c, t in zip(monta.MESA, _linhas(_bancada()), strict=True)
                if c.get("conectado", True) and "title=" in t]
    assert not com_dica, (
        f"{len(com_dica)} linha(s) de controle NA MESA voltaram a ter dica. "
        f"Atributo nenhum desta página é pintado: o nome do modelo ali fica "
        f"sendo o do DESENHO enquanto a célula ao lado já traz o do aparelho.")


ESPERA_A_PUBLICACAO = False


def test_a_publicada_nao_fica_curada_em_silencio() -> None:
    """Curar a bancada e deixar a publicada é a correção pela metade que esta"""
    ainda = [t for c, t in zip(monta.MESA, _linhas(_publicada()), strict=True)
             if c.get("conectado", True) and "title=" in t]
    assert bool(ainda) == ESPERA_A_PUBLICACAO, (
        f"a publicada tem {len(ainda)} linha(s) com a dica do desenho e a "
        f"declaração diz `ESPERA_A_PUBLICACAO = {ESPERA_A_PUBLICACAO}`. As duas "
        f"discordam: ou a publicação aconteceu e a declaração ficou para trás, "
        f"ou ela foi apagada antes da hora.")


def test_o_lugar_vazio_continua_com_a_dica() -> None:
    """`P3` é um LUGAR, não uma peça: aquela frase não afirma nada sobre"""
    assert VAZIOS, "o desenho não tem lugar vazio — esta régua perdeu o objeto"
    sem_dica = [c["pref"] for c, t in zip(monta.MESA, _linhas(_bancada()), strict=True)
                if not c.get("conectado", True) and "title=" not in t]
    assert not sem_dica, (
        f"o lugar vazio {sem_dica} perdeu a dica que explica por que ele "
        f"continua na tabela. Ela não fala de aparelho nenhum: não envelhece.")


def test_nenhuma_dica_da_tabela_nomeia_um_modelo_do_mapa() -> None:
    """A régua olha TODA dica da tabela por controle, contra os 28 modelos que"""
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
    """Onde o modelo APARECE na tabela, ele tem de estar num elemento que o"""
    modelos = {nome for _, nome in mesa_viva.CORES.values() if nome}
    tabela = _tabela(_bancada())
    solto = re.sub(r'<span data-hef="guarda\.nome">.*?</span>\s*</td>', "", tabela,
                   flags=re.DOTALL)
    achados = sorted({m for m in modelos if m in solto})
    assert not achados, (
        f"{achados} aparece(m) na tabela por controle FORA do único elemento "
        f"que o produto reescreve (`guarda.nome`). Quem lê a tela vê o modelo "
        f"do mockup sobre o aparelho dela.")


def test_alvo_nenhum_do_piloto_escreve_title() -> None:
    """O `escrever()` não pode ganhar um caminho para `title` FORA da guarda."""
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
        "o piloto ganhou um caminho para `title` FORA de `atributo_escrevivel`. "
        "O canal legítimo é o alvo `atributo` com o nome na lista curta — um "
        "atalho aqui tira do piloto a decisão de QUAL atributo pode ser escrito, "
        "que é o que impede um `data-hef-visto` forjado.")
