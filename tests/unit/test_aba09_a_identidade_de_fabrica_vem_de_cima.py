"""A "Identidade de fábrica" da aba 09 nomeia o controle DA FITA, não o do serial.

A LEI É DELA, 03/09/2026:

    "se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. Cada feature
    faz referencia ao controle conectado. Por isso temos o mapa pra  # noqa-acento: ela
    servir como variável de identificação"

O QUE FOI MEDIDO, e é o que estes testes trancam. Mesa dela em 03/09/2026, com
um `White` no cabo e um `Galactic Purple` no rádio — os dois lidos, os dois
sabidos pela mesa:

    a fita, no topo      P1 · White · USB
                         P2 · Galactic Purple · BT
    este painel, abaixo  P1 · White · cabo · <os 17 caracteres>
                         P2 · rádio · o serial só é lido no cabo

O MESMO APARELHO, NA MESMA TELA, nomeado num lugar e anônimo no outro.

A CAUSA: `_linha_de_identidade` lia SÓ `c["modelo"]` do `state_full`, e o
`modelo` sai do serial — que o daemon não publica para quem está no rádio.
Sondado no daemon dela no mesmo dia:

    usb  state_full.serial  os 17 caracteres   modelo "White"
    bt   state_full.serial  None               modelo None

A cor, porém, CHEGA: `mesa_viva.LeitorDeCor` a lê pelo broker e traduz o código
de fábrica pelo mapa dela (`docs/data/cores-do-dualsense.csv`, 28 modelos). O
painel tinha ao lado, na mesma função, a mesa que já sabia — e não a lia.

E O APARELHO DO RÁDIO RESPONDE O SERIAL INTEIRO — `ler_identidade_pelo_cabo`
devolveu 17 caracteres nos DOIS, medido no mesmo dia; a cor é a fatia `[4:6]`
deles. Quem cala é o publicador do daemon, não o transporte. A frase que a tela
escreve neste caso está imprecisa, e a nota de `a09_sistema.SEM_SERIAL_LIDO`
guarda a medição e as duas rotas de cura — nenhuma delas nesta aba.

A CURA NÃO É CÓDIGO NOVO: é chamar `pacotes.identidade_de`, o dono da ordem das
quatro fontes desde a ROTA-A, que as abas 02 e 06 já chamam com `ctx.mesa`.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from hefesto_dualsense4unix.interface import onde, pacotes
from hefesto_dualsense4unix.interface.pacotes import a09_sistema

RAIZ = pathlib.Path(onde.RAIZ)

#: O SERIAL É FORJADO, e a forma importa. Ele identifica a unidade tão bem
#: quanto um MAC, então nenhum caractere aqui pode casar com o padrão real: o
#: prefixo leva `Z` onde o de verdade exige dígito. Dezessete caracteres, que é
#: o comprimento do real — um curto deixaria verde uma régua que mede o texto
#: inteiro.
SERIAL_FORJADO = "ZZZ9ZZ###########"

#: A MESA DELA — os dois controles, os dois com a cor LIDA. É o caso que separa
#: a cura do defeito: o do rádio não tem serial e portanto não tem `modelo`,
#: mas a mesa sabe o nome dele.
MESA_DELA = [
    {"pref": "p1", "uniq": "aa11", "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB", "transporte": "usb", "alvo": True},
    {"pref": "p2", "uniq": "bb22", "jogador": 2, "cor": "galactic-purple",
     "nome": "Galactic Purple", "via": "BT", "transporte": "bt", "alvo": False},
]

#: O QUE O DAEMON PUBLICA sobre os mesmos dois. Copiado da sonda de 03/09: o do
#: rádio vem com `serial` e `modelo` nulos, e é assim para todo controle no
#: rádio de toda mesa — não é peculiaridade da dela.
NO_CABO = {"uniq": "aa11", "connected": True, "transport": "usb",
           "player_slot": 1, "player": None,
           "serial": SERIAL_FORJADO, "modelo": "White"}
NO_RADIO = {"uniq": "bb22", "connected": True, "transport": "bt",
            "player_slot": 2, "player": None, "serial": None, "modelo": None}

#: OS NOMES DO DESENHO. Nenhum é controle dela; são por eles que se reconhece o
#: mockup falando pela máquina.
DO_MOCKUP = ("Cosmic Red", "Starlight Blue")


class JanelaDeMentira:
    """O dublê do `DaemonActionsMixin` — e ele NÃO fala com o systemd.

    Sem ele, `_repouso_do_painel` roda `systemctl status` de verdade na máquina
    de quem executa a régua.
    """

    def _systemctl_status_text(self, unit: str) -> str:
        return "● unidade ativa"


@pytest.fixture
def a09():
    a09_sistema._JANELA_ANTIGA[:] = [JanelaDeMentira()]
    yield a09_sistema
    a09_sistema._JANELA_ANTIGA.clear()


# ---------------------------------------------------------------------------
# 1. O CONTROLE DO RÁDIO GANHA NOME — o defeito que ela veria na mesa dela
# ---------------------------------------------------------------------------
def test_o_controle_do_radio_e_nomeado_pela_mesa() -> None:
    """Sem serial e sem `modelo`, o nome vem da fita — que o leu pelo broker.

    **A MORDIDA:** devolva `str(c.get("modelo") or "")` em `_nome_do_plastico`.
    Executada em 03/09/2026:

        AssertionError: o controle do rádio ficou anônimo no painel técnico
        enquanto a fita, dois centímetros acima, o chama de `Galactic Purple`
    """
    linha = a09_sistema._linha_de_identidade(NO_RADIO, MESA_DELA)
    assert "Galactic Purple" in linha, (
        "o controle do rádio ficou anônimo no painel técnico enquanto a fita, "
        f"dois centímetros acima, o chama de `Galactic Purple`: {linha!r}")


def test_o_controle_do_cabo_continua_nomeado() -> None:
    """A cura não pode custar o que já funcionava.

    O do cabo tem `modelo` publicado, e `identidade_de` o prefere — a mesa é o
    terceiro degrau, não o primeiro. As duas portas dizem `White` aqui, e é
    isso que faz esta linha valer alguma coisa: ela reprovaria se a cura
    tivesse trocado uma fonte pela outra em vez de somá-las.
    """
    linha = a09_sistema._linha_de_identidade(NO_CABO, MESA_DELA)
    assert "White" in linha
    assert SERIAL_FORJADO in linha, "o serial de fábrica saiu da linha do cabo"


def test_o_nome_e_o_mesmo_que_a_fita_escreve() -> None:
    """Duas escritas, uma verdade. É a lei dela, e é o que a foto mostrava rompido.

    A régua compara o painel com o chip da fita da MESMA aba, montados pela
    mesma mesa — se algum dos dois passar a ter tabela própria, os textos se
    afastam e isto reprova.
    """
    fita = a09_sistema._html_da_fita(MESA_DELA)
    for controle, item in ((NO_CABO, MESA_DELA[0]), (NO_RADIO, MESA_DELA[1])):
        nome = item["nome"]
        assert nome in fita, f"a fita deixou de nomear {nome}"
        assert nome in a09_sistema._linha_de_identidade(controle, MESA_DELA), (
            f"a fita diz {nome!r} e o painel técnico diz outra coisa sobre o "
            "MESMO aparelho")


def test_nenhum_nome_do_desenho_entra_na_linha() -> None:
    """Nem por queda, nem por padrão: o mockup não fala pelo painel.

    A mesa aqui é a DELA; se a linha trouxesse `Cosmic Red` seria porque alguém
    escreveu um nome em vez de ler um.
    """
    texto = "\n".join(a09_sistema._linha_de_identidade(c, MESA_DELA)
                      for c in (NO_CABO, NO_RADIO))
    for agulha in DO_MOCKUP:
        assert agulha not in texto, f"o mockup falou pela máquina: {agulha}"


# ---------------------------------------------------------------------------
# 2. SEM LEITURA, SEM NOME — a regra dela, e os dois jeitos de quebrá-la
# ---------------------------------------------------------------------------
def test_o_nao_sei_da_mesa_nao_vira_nome() -> None:
    """`Não sei` é a AUSÊNCIA de leitura, não uma leitura.

    Escrevê-lo poria `P2 · Não sei · rádio` onde cabe `P2 · rádio`.
    """
    mesa = [{"uniq": "bb22", "jogador": 2, "nome": pacotes.NOME_SEM_LEITURA}]
    linha = a09_sistema._linha_de_identidade(NO_RADIO, mesa)
    assert pacotes.NOME_SEM_LEITURA not in linha, linha
    assert linha.startswith("P2 · rádio · "), linha


def test_o_transporte_nao_vira_nome_do_aparelho() -> None:
    """`identidade_de` cai no transporte quando não há nome — e aqui isso não serve.

    A linha já escreve o transporte ao lado, em palavra (`cabo`/`rádio`). Deixar
    o último degrau passar daria `P2 · BT · rádio`, que afirma a mesma coisa
    duas vezes e faz `BT` parecer o modelo do aparelho.

    **A MORDIDA:** apague o filtro `_NAO_E_NOME`. Executada em 03/09/2026:

        AssertionError: 'P2 · BT · rádio · o serial só é lido no cabo'
    """
    linha = a09_sistema._linha_de_identidade(NO_RADIO, [])
    assert " BT " not in linha and " USB " not in linha, linha
    assert linha == f"P2 · rádio · {a09_sistema.SEM_SERIAL_LIDO}", linha


def test_o_travessao_nao_vira_nome_do_aparelho() -> None:
    """Sem nome e sem transporte, `identidade_de` devolve o travessão.

    Um `—` no meio da linha lê como defeito de leitura da PÁGINA, e não como o
    que é: um aparelho sobre o qual não se sabe nada além de que está lá.
    """
    orfao = {"uniq": "cc33", "connected": True, "player_slot": 3}
    linha = a09_sistema._linha_de_identidade(orfao, [])
    assert pacotes.TRAVESSAO not in linha, linha


# ---------------------------------------------------------------------------
# 3. O NÚMERO DO JOGADOR TEM UM DONO SÓ
# ---------------------------------------------------------------------------
def test_o_numero_sai_do_player_slot_e_nao_do_player() -> None:
    """A ordem é a da GTK — `player_slot` na frente, e nunca a posição.

    A conta daqui era `c.get("player") or c.get("player_slot")`, a ordem
    INVERTIDA da de `actions/base.numero_do_controle`. Duas cópias da mesma
    regra é o que fez o mesmo controle ser "Controle 1" numa tela e "Sony 3" na
    outra; `pacotes.jogador_de` é o dono, e a régua `test_os_donos_de_fato`
    já o prende à função da GTK.

    **A MORDIDA:** volte a ler `player` na frente. Executada em 03/09/2026:

        AssertionError: 'P9 · rádio · o serial só é lido no cabo'
    """
    discordante = {**NO_RADIO, "player": 9, "player_slot": 2}
    linha = a09_sistema._linha_de_identidade(discordante, [])
    assert linha.startswith("P2 · "), linha


def test_sem_numero_a_linha_nao_inventa_um() -> None:
    """`jogador_de` devolve `None` em vez de numerar por ordem de chegada.

    *"Melhor calar que numerar por ordem de chegada"* — e um `P?` na tela seria
    pior que o silêncio: ele parece um número que ninguém leu direito.
    """
    sem_slot = {"uniq": "dd44", "connected": True, "transport": "bt"}
    linha = a09_sistema._linha_de_identidade(sem_slot, [])
    assert "P?" not in linha and not linha.startswith("P"), linha


# ---------------------------------------------------------------------------
# 4. A MESA CHEGA AO PAINEL — o caminho inteiro, e não só a função da ponta
# ---------------------------------------------------------------------------
def test_a_mesa_atravessa_a_faixa_lenta_ate_o_painel(a09) -> None:
    """O painel é montado na faixa lenta, e ela tinha de aprender a mesa.

    Sem este teste a cura ficaria numa função que ninguém alimenta: o
    `_repouso_do_painel` é chamado por `_ler_a_faixa_lenta`, três camadas
    abaixo do `pacote(ctx)` que tem o `ctx.mesa` na mão.

    **A MORDIDA:** tire o `mesa=mesa` do `_ler_a_faixa_lenta`. Executada em
    03/09/2026: o painel volta a chamar o controle do rádio de nada.
    """
    estado = {"controllers": [NO_CABO, NO_RADIO]}
    painel = a09._repouso_do_painel(estado, MESA_DELA)
    assert a09.ROTULO_DA_IDENTIDADE in painel
    assert "Galactic Purple" in painel, painel
    # E ele é o FIM do painel, que é o pedaço que a tela mostra sem rolar
    # (`data-hef-rolar="fim"`).
    assert painel.splitlines()[-1].strip().startswith("P2 · Galactic Purple"), painel


def test_a_faixa_lenta_aceita_a_mesa_e_a_repassa(a09, monkeypatch) -> None:
    """`_ler_a_faixa_lenta(state, mesa=…)` entrega a mesa ao painel.

    A régua não mede a assinatura — mede o TEXTO que sai. Uma assinatura que
    aceitasse `mesa` e a jogasse fora passaria num teste de forma e reprova
    aqui.
    """
    monkeypatch.setattr(a09, "_autostart", lambda: "enabled")
    monkeypatch.setattr(a09, "_achados", lambda *_a, **_k: [])
    monkeypatch.setattr(a09, "_perfil_da_bateria", lambda: None)
    monkeypatch.setattr(a09, "_status_do_daemon", lambda _s: "online_systemd")
    estado = {"controllers": [NO_RADIO]}
    *_, painel = a09._ler_a_faixa_lenta(estado, mesa=MESA_DELA)
    assert "Galactic Purple" in painel, painel


# ---------------------------------------------------------------------------
# 5. NENHUMA TABELA DE COR NOVA — a regra que o enunciado desta leva repete
# ---------------------------------------------------------------------------
def _textos_de_codigo(fonte: pathlib.Path) -> list[tuple[int, str]]:
    """As strings que o módulo pode ESCREVER — sem comentário e sem docstring.

    A separação é por AST e não por linha, e a diferença é o que faz a régua
    valer: comentário não entra na árvore nenhuma, e docstring é a PRIMEIRA
    sentença de um módulo, classe ou função. O que sobra é literal de código —
    o único lugar de onde um nome digitado alcançaria a tela.

    Filtrar por "a linha começa com `#`" não serviria: a prosa que conta o
    defeito de 03/09 tem seis linhas de docstring e nenhuma delas começa com
    aspas.
    """
    arvore = ast.parse(fonte.read_text(encoding="utf-8"))
    docs = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef,
                           ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = getattr(no, "body", None) or []
            primeiro = corpo[0] if corpo else None
            if (isinstance(primeiro, ast.Expr)
                    and isinstance(primeiro.value, ast.Constant)
                    and isinstance(primeiro.value.value, str)):
                docs.add(id(primeiro.value))
    return [(no.lineno, no.value) for no in ast.walk(arvore)
            if isinstance(no, ast.Constant) and isinstance(no.value, str)
            and id(no) not in docs]


def test_o_pacote_nao_guarda_uma_segunda_tabela_de_nomes() -> None:
    """Ela mapeou 28 modelos em CSV; um nome digitado aqui seria o de número 29.

    *"eu mapeei as cores, glifos, controles, id e tudo mais. é pro projeto usar
    esse meu trabalho"* — e a única cópia legítima de um nome de colorway neste
    arquivo é a PROSA que conta o defeito. Prosa não chega à tela.

    **A MORDIDA:** escreva `nome = "Cosmic Red"` dentro de qualquer função do
    pacote. Executada em 03/09/2026:

        AssertionError: nome de colorway digitado no código do pacote
    """
    fonte = RAIZ / "src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py"
    culpadas = [f"{linha}: {texto!r}" for linha, texto in _textos_de_codigo(fonte)
                for nome in ("Cosmic Red", "Starlight Blue", "Galactic Purple",
                             "Nova Pink", "Midnight Black")
                if nome in texto]
    assert not culpadas, (
        "nome de colorway digitado no código do pacote — o dono é "
        "`docs/data/cores-do-dualsense.csv`:\n" + "\n".join(culpadas))
