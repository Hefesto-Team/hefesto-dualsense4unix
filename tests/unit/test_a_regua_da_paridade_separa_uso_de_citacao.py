"""A régua da paridade separa USAR um símbolo de CITÁ-LO — e o defeito é reincidente.

O QUE ACONTECEU, DUAS VEZES, NA MESMA LINHA
--------------------------------------------
A regra ``divida-fechada`` do ``scripts/check_paridade_gtk_html.py`` vigia as
linhas ``FALTA_NO_HTML``: se o símbolo da janela antiga aparecer no lado HTML, a
dívida fechou e o CSV tem de ser reescrito. É o caso BOM — alguém trabalhou.

Só que ela media a PALAVRA e não o ATO — noqa-acento: verbo MEDIR no pretérito
imperfeito, não o substantivo "média" —, com ``alvo in texto`` sobre o arquivo
inteiro:

* **03/09/2026** — as linhas 315 e 343 do CSV foram promovidas a ``DIFERENTE``
  porque o símbolo "apareceu" no lado HTML. O que apareceu era um COMENTÁRIO
  citando o nome da função da GTK. As duas foram devolvidas a ``FALTA_NO_HTML``
  no mesmo dia, e o ``porque`` de cada uma registra o tombo.
* **06/09/2026** — de novo, na mesma linha 315. Desta vez a citação estava numa
  DOCSTRING que explica o que a janela antiga fazia::

      A LINHA **L315** DO CSV (…) A janela antiga tinha
      (`daemon_actions.on_daemon_migrate_to_systemd`).

  A régua leu o nome dentro da prosa e anunciou que a dívida tinha fechado.

E a ironia estava escrita no próprio arquivo: a classe se apresentava como
*"O código lido UMA vez. A régua reprova por LEITURA, nunca por ``grep``"* — e o
corpo fazia um grep, sem sequer borda de palavra. **O comentário descrevia o
defeito que o código tinha.**

A CURA, E O ALCANCE DELA (que é a parte difícil)
------------------------------------------------
Duas funções, e a assimetria entre elas é o ponto:

``Arvore.ocorre``
    o símbolo APARECE, prosa incluída. Continua servindo às regras de
    ``PRESENTE``, e é de propósito: **muitos sinais deste CSV são citações por
    desenho** — a linha 19 vigia ``test_os_donos_de_fato.py`` (um nome de
    arquivo de teste) e a linha 2 vigia
    ``app/actions/mode_transition.plan_mode_transition`` (um caminho de módulo).
    Os dois só podem viver num comentário.

``Arvore.usa``
    o símbolo é USADO: sai a docstring (pelo ``ast``, que é o dono da gramática)
    e sai o comentário (pelo ``tokenize``, idem). **Só a regra da dívida a
    chama**, porque ``AUSENTE`` afirma *"o lado HTML não faz isto"*, e citar a
    função alheia num comentário não é fazer.

DUAS TENTATIVAS ERRADAS, medidas, para quem for mexer aqui não repeti-las:

1. apagar toda ``ast.Constant`` de texto → **165 falsos**. Cadeia usada como
   VALOR é código: ``"restaurar-de-fabrica"`` é o nome de um gesto e
   ``data-campo="fragil"`` é um endereço de tela;
2. tirar comentário com ``(?m)#[^\\n]*`` → **93 falsos**, porque ele come o
   ``#`` de ``cor = "#A51C48"`` e o resto da linha junto;
3. e a borda de palavra com ``(?<![\\w.])`` → **17 falsos**: excluir o ponto faz
   ``mesa_viva.VIA_DO_TRANSPORTE`` deixar de casar, e acesso por atributo é uso.

De 2 achados para 165, para 93, para 17, para 2. Os números estão aqui porque a
próxima pessoa vai querer "simplificar" uma destas três.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_paridade_gtk_html.py"
DONOS = RAIZ / "scripts" / "check_donos_de_comportamento.py"


def _modulo():
    """O portão como módulo, sem rodar o `main`."""
    spec = importlib.util.spec_from_file_location("_paridade_gtk_html", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_paridade_gtk_html"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def portao():
    return _modulo()


def _arquivo(tmp_path: Path, corpo: str) -> Path:
    p = tmp_path / "alvo.py"
    p.write_text(corpo, encoding="utf-8")
    return p


def test_citar_numa_docstring_nao_e_usar(portao, tmp_path):
    """O caso REAL de 06/09: o nome da função da GTK dentro de uma docstring.

    É a mordida principal. Se ela passar, a régua voltou a confundir a palavra
    com o ato, e a linha 315 do CSV volta a ser promovida por engano.
    """
    alvo = _arquivo(tmp_path, '''
def _o_avulso_saiu(pid):
    """Pede ao daemon avulso que saia.

    A janela antiga tinha (`daemon_actions.on_daemon_migrate_to_systemd`).
    """
    return True
''')
    arvore = portao.Arvore()
    assert arvore.ocorre("on_daemon_migrate_to_systemd", [alvo]) == alvo, (
        "o símbolo ESTÁ no arquivo; `ocorre` tem de continuar vendo-o")
    assert arvore.usa("on_daemon_migrate_to_systemd", [alvo]) is None, (
        "citar numa docstring NÃO é usar — foi este falso que promoveu a "
        "linha 315 do CSV em 03/09 e de novo em 06/09")


def test_citar_num_comentario_nao_e_usar(portao, tmp_path):
    """O caso REAL de 03/09: o comentário de uma linha."""
    alvo = _arquivo(tmp_path, "x = 1  # o mesmo que on_daemon_migrate_to_systemd faz\n")
    arvore = portao.Arvore()
    assert arvore.ocorre("on_daemon_migrate_to_systemd", [alvo]) == alvo
    assert arvore.usa("on_daemon_migrate_to_systemd", [alvo]) is None


def test_chamar_de_verdade_e_usar(portao, tmp_path):
    """O outro lado, e sem ele a cura seria um portão que emudeceu.

    Uma régua que deixa de reprovar é pior que uma que reprova demais: a dívida
    que fecha DE VERDADE tem de continuar acusando, porque é assim que o número
    da paridade não vira propaganda.
    """
    alvo = _arquivo(tmp_path, "def f():\n    return on_daemon_migrate_to_systemd()\n")
    arvore = portao.Arvore()
    assert arvore.usa("on_daemon_migrate_to_systemd", [alvo]) == alvo


def test_cadeia_usada_como_valor_e_codigo(portao, tmp_path):
    """A tentativa errada nº 1, congelada: apagar toda cadeia derrubou 165 linhas.

    O sinal de muitas features É uma cadeia — o nome de um gesto, um endereço de
    tela. Apagar toda `ast.Constant` de texto mata essas linhas.
    """
    alvo = _arquivo(tmp_path, 'GESTOS = ["restaurar-de-fabrica", "refazer-proton"]\n')
    arvore = portao.Arvore()
    assert arvore.usa("restaurar-de-fabrica", [alvo]) == alvo, (
        "cadeia usada como VALOR é código, não prosa")


def test_o_cerquilha_de_uma_cor_nao_come_a_linha(portao, tmp_path):
    """A tentativa errada nº 2, congelada: o regex de comentário custou 93 falsos.

    `(?m)#[^\\n]*` come o `#` de uma cor hexadecimal e tudo o que vem depois.
    Quem sabe qual `#` abre comentário é o `tokenize`.
    """
    alvo = _arquivo(tmp_path, 'COR = "#A51C48"; ALVO = VIA_DO_TRANSPORTE\n')
    arvore = portao.Arvore()
    assert arvore.usa("VIA_DO_TRANSPORTE", [alvo]) == alvo, (
        "o símbolo vem DEPOIS de um '#' que está dentro de aspas")


def test_o_acesso_por_atributo_e_uso(portao, tmp_path):
    """A tentativa errada nº 3, congelada: a borda com ponto custou 17 falsos."""
    alvo = _arquivo(tmp_path, "v = mesa_viva.VIA_DO_TRANSPORTE\n")
    arvore = portao.Arvore()
    assert arvore.usa("VIA_DO_TRANSPORTE", [alvo]) == alvo, (
        "`mesa_viva.VIA_DO_TRANSPORTE` é uso do símbolo, não um sufixo")


def test_a_borda_de_palavra_recusa_sufixo(portao, tmp_path):
    """E o ganho que a borda trouxe, que revelou um segundo defeito.

    A linha 66 do CSV vigiava `player_slot`, que não existe sozinho na página —
    só dentro de `player_slot_color`. A régua a dava por presente por casar
    substring, e aquela linha nunca mordeu. O sinal foi corrigido no CSV.
    """
    alvo = _arquivo(tmp_path, "from x import player_slot_color\n")
    arvore = portao.Arvore()
    assert arvore.usa("player_slot", [alvo]) is None
    assert arvore.ocorre("player_slot", [alvo]) is None
    assert arvore.usa("player_slot_color", [alvo]) == alvo


def test_arquivo_ilegivel_falha_para_o_lado_seguro(portao, tmp_path):
    """Sintaxe quebrada devolve o texto CRU, e a régua continua vendo.

    Uma régua que emudece por causa de um `.py` a meio caminho de uma edição é
    pior que uma que exagera: ela dá verde sobre o que não leu.
    """
    alvo = _arquivo(tmp_path, "def f(:\n    on_daemon_migrate_to_systemd()\n")
    arvore = portao.Arvore()
    assert arvore.usa("on_daemon_migrate_to_systemd", [alvo]) == alvo


# ---------------------------------------------------------------------------
# O SEGUNDO PORTÃO, e ele é a razão de a cura ter virado módulo com dono.
#
# `scripts/check_donos_de_comportamento.py` tinha o MESMO defeito, no mesmo dia:
# a regra `SO-GTK` reprovava `migrar_para_systemd` dizendo "a tela nova já
# CHAMA", e o que a tela nova tinha era a citação numa docstring. O nome da
# função que ele usava era `_cita` e a mensagem dizia `chama` — nome e mensagem
# discordavam, e quem tinha razão era a mensagem.
#
# A regra desta casa: quando a cura conhece a causa, ela cobre TODOS os
# chamadores. Cobrir um deixa a próxima pessoa remedindo o mesmo defeito.
# ---------------------------------------------------------------------------


def _modulo_dos_donos():
    spec = importlib.util.spec_from_file_location("_donos_de_comportamento", DONOS)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_donos_de_comportamento"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def donos():
    return _modulo_dos_donos()


def test_a_separacao_tem_dono_e_o_portao_da_paridade_pergunta_a_ele(portao):
    """A técnica de apagar prosa mora em `scripts/prosa_do_codigo.py`.

    Se o portão da paridade voltar a ter cópia própria, esta régua cai — e é o
    que impede a QUARTA volta do mesmo defeito. O portão dos donos resolve a
    mesma pergunta por outro caminho, declarado no teste abaixo.
    """
    import prosa_do_codigo

    assert portao.prosa_do_codigo is prosa_do_codigo
    assert portao.Arvore.usa.__doc__ and "prosa" in portao.Arvore.usa.__doc__.lower()


def test_o_portao_dos_donos_resolve_a_mesma_pergunta_por_outro_caminho(donos, tmp_path):
    """Dois instrumentos, duas técnicas, e a diferença é do dado que cada um lê.

    O portão dos DONOS coleta os NOMES que o `ast` aponta (`ast.Name`,
    `ast.Attribute`, os imports). É o certo lá: naquele CSV o dono é sempre um
    símbolo do código.

    O portão da PARIDADE não pode fazer isso: **o sinal dele pode ser uma
    cadeia** — `"restaurar-de-fabrica"` é o nome de um gesto, `test_...py` é um
    nome de arquivo — e coletar só nomes derrubaria essas linhas. Por isso ele
    apaga a prosa e procura no que sobra.

    As duas concordam no caso que importa, que é o defeito de 03/09 e 06/09.
    """
    corpo = (
        "def _o_avulso_saiu(pid):\n"
        '    """A janela antiga tinha (`daemon_actions.on_daemon_migrate_to_systemd`)."""\n'
        "    return True\n"
    )
    alvo = tmp_path / "a09.py"
    alvo.write_text(corpo, encoding="utf-8")
    assert donos._cita(alvo, "on_daemon_migrate_to_systemd") is False, (
        "no portão dos donos, `_cita` passou a significar CHAMA — citar não conta")


def test_os_donos_contam_atributo_e_import(donos, tmp_path):
    """O que conta como referência lá: nome, atributo e import."""
    alvo = tmp_path / "x.py"
    alvo.write_text("from a import palavra_do_transporte\nv = _daemon.MIGRAR_NAO_DEU\n",
                    encoding="utf-8")
    assert donos._cita(alvo, "palavra_do_transporte") is True
    assert donos._cita(alvo, "MIGRAR_NAO_DEU") is True
