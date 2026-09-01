"""A régua das abas vivas: elas falam com o daemon DESTA casa, e leem DESTA árvore.

Nasceu em 30/08/2026, de dois defeitos medidos no mesmo par de horas. Os dois
são a mesma doença — **o mesmo valor com vários donos** — e os dois eram
silenciosos: nenhuma exceção, nenhum log, só a tela mostrando o passado.

1. O SOCKET IGNORAVA A VARIANTE
-------------------------------
`src/hefesto_dualsense4unix/interface/mesa_viva.py` montava o caminho do socket à mão, com
o nome da casa escrito como literal::

    SOCKET = os.path.join(XDG_RUNTIME_DIR, "hefesto-dualsense4unix",
                          "hefesto-dualsense4unix.sock")

MEDIDO em 30/08 às 00:26, com o daemon de dev no ar e vendo um controle dela: as
cinco abas vivas diziam ``[Errno 111] Conexão recusada`` e pintavam **5 valores**
— a tela de "Hefesto desligado" — enquanto o daemon respondia normalmente em
``/run/user/1000/hefesto-dev-dualsense4unix/``, o diretório ao lado.

O dono verdadeiro sempre existiu: `utils/xdg_paths.ipc_socket_path()`, que deriva
o diretório de `identidade.atual().slug` e ainda isola o socket no modo fake
(`BUG-FAKE-SOCKET-SYNC-01`). A cópia à mão errava as DUAS coisas.

2. A ÁRVORE DELA ESTAVA CRAVADA NO PILOTO
------------------------------------------
`controles_vivos.py` e `mesa_viva.py` cravavam
``/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix`` — a árvore DELA — e o
piloto ainda inseria esse caminho no `sys.path` **na frente** do diretório do
próprio arquivo. Rodar o piloto de uma árvore de agente carregava o `mesa_viva`,
o `monta`, o `aba02` e o `02-controles.html` **dela**.

MEDIDO em 30/08 às 00:31, e foi assim que apareceu: curei o socket na árvore de
dev, rodei o piloto de lá, e ele continuou dizendo "Conexão recusada" — porque o
`mesa_viva.__file__` que ele importou era o da árvore dela. **A edição do agente
não valia nada, e nada avisava.**

É a regra da casa "A ÁRVORE DELA FICA EM `dev`, SEMPRE" pelo outro lado: lá o
perigo é o agente ESCREVER na mesa dela; aqui era ele LER dela sem saber.

POR QUE A RÉGUA É POR FORMA, E NÃO SÓ POR VALOR
-----------------------------------------------
O teste do caminho literal pega a CLASSE do defeito — qualquer árvore cravada em
qualquer aba viva, inclusive numa que ainda não existe. O teste da variante pega
o comportamento. Duas réguas independentes é o que revela; é regra desta casa,
e foi ela que achou o segundo defeito depois de o primeiro estar curado.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
#: A PASTA MUDOU E ESTE ARQUIVO FICOU PARA TRÁS — corrigido em 31/08/2026.
#: O commit `48b4e1a2` fez o produto ler de `layout/`; esta constante seguiu
#: apontando para `novo-layout/`, que virou referência congelada. As duas cópias
#: já divergiram 25 KB, então a régua media  (noqa-acento: verbo medir, imperfeito) verbo medir
#: um arquivo que o produto não abre.
#: (noqa-acento: verbo medir, imperfeito — "a régua media", não "a média") verbo medir
#: O ESCAPE É POR LINHA: esta razão nasceu só na linha de baixo do achado, e
#: por isso não o alcançava. A marca tem de estar NA linha da palavra.
#: É a QUARTA migração pela metade achada hoje — depois do gancho da régua de
#: tela (13 reprovações), do portão de dependências que ficou verde medindo a
#: menos, e do `test_arranjo_invariantes`. O padrão: a parte que ninguém roda no
#: dia seguinte é a que fica.
FERRAMENTAS = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

#: As abas vivas de hoje. Uma aba nova entra aqui — e é de propósito que a lista
#: seja escrita: um `glob` deixaria uma aba nova nascer sem régua e ninguém
#: notaria.
ABAS_VIVAS = (
    "controles_vivos.py",
    "jogar_vivo.py",
    "perfis_vivos.py",
    "conexoes_vivas.py",
    "sistema_viva.py",
    "mesa_viva.py",
)

#: A árvore dela. Escrita aqui UMA VEZ, para que a régua a reconheça em qualquer
#: aba — e para que este seja o único arquivo do repositório onde ela aparece
#: como literal, que é justamente o que se está proibindo em toda outra parte.
ARVORE_DELA = "/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix"


def _fonte(nome: str) -> str:
    return (FERRAMENTAS / nome).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. NENHUMA ABA VIVA CRAVA UMA ÁRVORE
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nome", ABAS_VIVAS)
def test_nenhuma_aba_viva_crava_a_arvore_dela(nome: str) -> None:
    """Um caminho absoluto de árvore em CÓDIGO faz o agente medir o passado.

    A régua olha só as linhas de código: a prosa que EXPLICA o defeito curado
    precisa citar o caminho, e proibi-la obrigaria a apagar a explicação — que é
    o oposto do que esta casa faz com defeito medido.
    """
    culpadas = [
        (n, linha.rstrip())
        for n, linha in enumerate(_fonte(nome).splitlines(), 1)
        if ARVORE_DELA in linha
        and not linha.lstrip().startswith(("#", "*", '"', "'"))
        and ":=" not in linha
    ]
    assert not culpadas, (
        f"{nome} crava uma árvore em código: {culpadas}. "
        "Derive do próprio arquivo — `pathlib.Path(__file__).resolve().parents[2]` "
        "—, senão rodar de uma árvore de agente lê a árvore dela."
    )


@pytest.mark.parametrize("nome", ABAS_VIVAS)
def test_toda_aba_viva_deriva_a_raiz_do_proprio_arquivo(nome: str) -> None:
    """A forma positiva da régua acima: não basta não cravar, tem de derivar.

    Sem esta metade, apagar a linha `RAIZ` e passar a abrir `"02-controles.html"`
    relativo ao diretório de trabalho passaria verde — e quebraria de um jeito
    novo, dependente de onde a pessoa estava quando chamou.
    """
    fonte = _fonte(nome)
    assert "Path(__file__).resolve()" in fonte or "__file__" in fonte, (
        f"{nome} não deriva nada de `__file__`: não há como ele saber em que "
        "árvore está."
    )


# ---------------------------------------------------------------------------
# 2. O SOCKET SEGUE A VARIANTE
# ---------------------------------------------------------------------------
def _mesa_viva_recarregado(monkeypatch: pytest.MonkeyPatch, variante: str | None):
    """`mesa_viva` importado com a variante que se pedir.

    Recarregar `identidade` e `xdg_paths` é OBRIGATÓRIO: o `_DIRS` do `xdg_paths`
    é calculado no import, logo ele congela a variante de quem importou primeiro.
    """
    from hefesto_dualsense4unix.utils import identidade

    if variante is None:
        monkeypatch.delenv(identidade.VARIANTE_ENV, raising=False)
    else:
        monkeypatch.setenv(identidade.VARIANTE_ENV, variante)
    monkeypatch.syspath_prepend(str(FERRAMENTAS))
    importlib.reload(identidade)
    xdg = importlib.import_module("hefesto_dualsense4unix.utils.xdg_paths")
    importlib.reload(xdg)
    mesa = importlib.import_module("mesa_viva")
    return importlib.reload(mesa)


@pytest.fixture(autouse=True)
def _devolver_os_modulos():
    """Recarregar módulo global num teste envenena o processo inteiro. Devolve."""
    yield
    from hefesto_dualsense4unix.utils import identidade, xdg_paths

    importlib.reload(identidade)
    importlib.reload(xdg_paths)
    sys.modules.pop("mesa_viva", None)


def test_o_socket_das_abas_muda_com_a_variante(monkeypatch: pytest.MonkeyPatch) -> None:
    """`HEFESTO_VARIANTE=dev` tem de mudar o socket. É a régua que morde.

    Com o caminho montado à mão que havia até 30/08, os dois lados desta
    comparação eram a MESMA string — e era esse o defeito.
    """
    dela = _mesa_viva_recarregado(monkeypatch, None).socket_do_daemon()
    dev = _mesa_viva_recarregado(monkeypatch, "dev").socket_do_daemon()
    assert dela != dev, (
        "o socket é o mesmo nas duas casas: a aba de desenvolvimento vai falar "
        f"com o daemon dela ({dela})"
    )
    assert "hefesto-dev-dualsense4unix" in dev
    assert "hefesto-dev-dualsense4unix" not in dela


def test_o_socket_das_abas_e_o_mesmo_que_o_produto_usa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UM DONO SÓ. A aba não pode ter uma segunda opinião sobre onde o daemon está.

    Comparar com `xdg_paths.ipc_socket_path()` é o que impede a cura de virar
    uma terceira cópia: se alguém reescrever o caminho à mão de novo, mesmo
    acertando a variante, esta régua reprova no dia em que o produto mudar o
    dele — que é exatamente quando as duas versões ficariam vivas ao mesmo tempo.
    """
    for variante in (None, "dev"):
        mesa = _mesa_viva_recarregado(monkeypatch, variante)
        xdg = importlib.import_module("hefesto_dualsense4unix.utils.xdg_paths")
        assert mesa.socket_do_daemon() == str(xdg.ipc_socket_path())


def test_o_socket_e_funcao_e_nao_constante() -> None:
    """Constante calculada no import congela a variante do primeiro importador.

    Uma `SOCKET = …` no topo do módulo passaria nos dois testes acima quando
    rodada sozinha e falharia dentro de um processo que já tivesse importado o
    módulo com a outra variante — o pior tipo de reprovação, a que depende da
    ordem dos testes.
    """
    fonte = _fonte("mesa_viva.py")
    assert re.search(r"^def socket_do_daemon\b", fonte, re.M), (
        "`socket_do_daemon()` sumiu — o socket voltou a ser constante?"
    )
    assert not re.search(r"^SOCKET\s*=", fonte, re.M), (
        "voltou a haver uma constante `SOCKET` no topo: ela congela a variante "
        "de quem importar primeiro."
    )


# ---------------------------------------------------------------------------
# 3. A RÉGUA DE GESTO NÃO PODE DEPENDER DO TAMANHO DA MESA
# ---------------------------------------------------------------------------
def test_a_prova_de_gesto_nao_crava_o_indice_do_card() -> None:
    """`--prova-gesto` clicava `.ctl[1]` — o SEGUNDO card, sempre.

    MEDIDO em 30/08 às 00:37, com o controle dela de hoje: mesa de UM controle
    → `.ctl[1]` é `undefined`, os sete cliques do roteiro batem em `null` e a
    prova produz **zero gestos**, sem uma linha vermelha. Mesa de dois → seis
    gestos, verde. O instrumento desligava exatamente na mesa dela.

    É a forma que esta casa já nomeou onze vezes numa leva só: a régua desliga
    quando o alvo não está onde ela decorou que estaria. Um índice fixo é a
    assinatura dessa forma, e é isso que esta régua proíbe.

    A régua olha só as linhas de CÓDIGO, e essa parte ela aprendeu caindo: a
    primeira versão deste teste reprovou a própria cura, porque o comentário que
    EXPLICA o índice velho o cita literalmente. Proibir a citação obrigaria a
    apagar a explicação do defeito — que é o oposto do que esta casa faz.
    """
    codigo = "\n".join(
        linha for linha in _fonte("controles_vivos.py").splitlines()
        if not linha.lstrip().startswith("#")
    )
    assert "querySelectorAll('.ctl')[1]" not in codigo, (
        "a prova de gesto voltou a cravar o segundo card: numa mesa de um "
        "controle ela clica em `null` e passa calada."
    )
    assert "querySelectorAll('.ctl').length-1" in codigo, (
        "a prova de gesto tem de mirar um card que EXISTA em qualquer mesa."
    )


def test_o_unico_metodo_continua_sendo_leitura() -> None:
    """Esta leva não escreve, e a régua que diz isso tem de continuar de pé.

    Fica aqui e não noutro arquivo porque é a MESMA pergunta: com quem a aba
    fala, e para dizer o quê.
    """
    assert 'METODO = "daemon.state_full"' in _fonte("mesa_viva.py")
