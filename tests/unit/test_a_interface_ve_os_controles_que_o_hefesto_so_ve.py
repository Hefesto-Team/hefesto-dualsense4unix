#!/usr/bin/env python3
"""Os controles que o Hefesto VÊ e NÃO adota chegam à aba 01 e à aba 08.

**EXTERNOS-01, 06/09/2026 — as linhas 16 e 305 de
`docs/data/paridade-gtk-html.csv`**, e as duas descrevem o mesmo silêncio:

* linha 16 (`01-jogar`) — *"com dois DualSense e um 8BitDo na mesa a aba dizia
  '2 controles' ao lado de três cards noutra tela"*. A janela antiga fechou isso
  em 25/08 (a `I5`); a tela nova nasceu com o defeito de volta;
* linha 305 (`08-conexoes`) — *"uma aba chamada Conexões que não lista metade
  dos controles conectados"*.

**O `porque` das duas era o mesmo, e era um grep:** *"não é ausência de dado —
`controller.list {external:true}` responde; ninguém pergunta"*. Esta régua mede
que alguém passou a perguntar, e que a resposta chega à tela.

**O DUBLÊ É DO `controller.list`, E ELE SABE RECUSAR.** Régua que só sabe passar
não é régua (`COMO-EXECUTAR-UMA-SPRINT.md` §4): o teste do daemon mudo exercita
o caminho de erro, e é ele que prova que uma leitura que FALHOU não apaga a
lista boa — a confusão que esta casa chama de *ausência de notícia lida como
sucesso*.

**SEM APARELHO NA BANCADA.** Não havia Nintendo Pro nem 8BitDo na mesa em
06/09/2026 (medido em `/sys/bus/hid/devices`: só `054C:0CE6` e `054C:0DF2`,
os dois Sony). A prova de aparelho fica para a `MESA-DE-QUATRO-01`; o que se
mede aqui é o caminho inteiro do payload até o HTML, com o payload que o daemon
publica — a forma está escrita em `daemon/ipc_handlers._handle_controller_list`.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as jogar

#: UM 8BITDO POR RÁDIO, na forma que o daemon publica
#: (`ipc_handlers._handle_controller_list`, chave `external`). O MAC leva a
#: MÁSCARA DA CASA — octetos 4 e 5 zerados —, e o OUI `e4:17:d8` é o da 8BitDo,
#: que é o único sinal capaz de desmentir o VID que o clone mente.
UM_8BITDO: dict[str, Any] = {
    "name": "8BitDo Pro 2",
    "vid": "2dc8",
    "pid": "6003",
    "bus": "bluetooth",
    "uniq": "e4:17:d8:00:00:2f",
    "driver": "hid-generic",
    "player_slot": 3,
}

#: UM PRO CONTROLLER POR RÁDIO — VID `057e` (Nintendo), que é o que acende o
#: aviso do `hid-nintendo`. É a mesma armadilha que a linha 305 do CSV nomeia
#: como SINAL dela.
UM_PRO: dict[str, Any] = {
    "name": "Pro Controller",
    "vid": "057e",
    "pid": "2009",
    "bus": "bluetooth",
    "uniq": "e4:17:d8:00:00:5b",
    "driver": "hid-nintendo",
    "player_slot": 4,
}

VIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
}


def _ctx(externos: list[dict[str, Any]]) -> Contexto:
    return Contexto(state=dict(VIVO), mesa=[], conectados=[], externos=externos)


# ---------------------------------------------------------------------------
# 1. O CAMPO É PRÓPRIO — e a rota da sprint diz por quê
# ---------------------------------------------------------------------------
def test_o_externo_nao_entra_nos_assentos() -> None:
    """`externos` é campo próprio: nunca dentro de `conectados` nem de `mesa`.

    Somá-lo aos assentos faria o cabeçalho contar jogadores que não existem, a
    fita oferecer um alvo que nenhum gesto alcança e
    `apagar_os_lugares_sem_dono` disputar um cartão que não é dele.
    """
    ctx = _ctx([UM_8BITDO])
    assert ctx.externos == [UM_8BITDO]
    assert ctx.conectados == []
    assert ctx.mesa == []


def test_o_contexto_nasce_sem_externo_nenhum() -> None:
    """Sem a chave, a lista é vazia — e vazia quer dizer "não desenha nada"."""
    assert Contexto(state={}).externos == []


# ---------------------------------------------------------------------------
# 2. A ABA 01 — a linha 16 do CSV
# ---------------------------------------------------------------------------
def test_a_jogar_escreve_o_cartao_do_externo() -> None:
    """O cartão traz o NÚMERO, a MARCA e o transporte, pelos donos da frase."""
    html = jogar.pacote(_ctx([UM_8BITDO]))["externos"]
    assert 'class="ext-cartao"' in html
    # O número é o SLOT GLOBAL de co-op — o mesmo que o Hefesto escreve no LED
    # de player do aparelho. Ele vem do `player_slot` que o daemon mandou, e não
    # de uma conta local (NUMA-05).
    assert "Controle 3" in html
    # A MARCA VEM DO OUI, e é o ponto: `brand_of` é a única função da casa que
    # sabe desmentir o VID mentido por um clone em modo DualShock4.
    assert "8BitDo" in html
    # A PALAVRA DO TRANSPORTE É A DO DONO (`home_actions.palavra_do_transporte`),
    # que é o §2 do "o que se mede antes de escrever" desta sprint: "rádio", e
    # não "bluetooth" nem "BT".
    assert "rádio" in html
    # E A TELA DIZ O QUE O HEFESTO NÃO FAZ com ele, que é a informação que a
    # pessoa procura ao ver um controle que não acende.
    assert "só vê" in html


def test_a_jogar_escreve_um_cartao_por_externo() -> None:
    html = jogar.pacote(_ctx([UM_8BITDO, UM_PRO]))["externos"]
    assert html.count('class="ext-cartao"') == 2
    assert "Controle 3" in html and "Controle 4" in html


def test_a_jogar_apaga_a_secao_quando_nao_ha_externo() -> None:
    """Vazio é o MARCADOR `.nada` — e `""` deixava um travessão solto na grade.

    Uma frase de "nenhum controle externo" acusaria ausência, e nenhuma das duas
    abas acusa: a lista vazia é *"não há"* **e** *"ainda não perguntei"*. O que
    mudou em 07/09/2026 é COMO se diz "nada".

    **O DEFEITO ESTAVA NA TELA DELA, e foi fotografado:** com quatro DualSense na
    mesa e nenhum externo, a aba Jogar mostrava um `—` solto logo abaixo dos
    quatro cartões. `escrever()` troca valor vazio por travessão de propósito
    (`hefesto_vivo.py`), a `.ext-vaga` é `display:contents`, e esse travessão
    virava um item anônimo da grade `.pecas` — um quinto assento com um traço
    dentro. O `<i class="nada">` da página não salvava: o alvo `html` troca o
    miolo inteiro na primeira pintura.

    A MORDIDA: devolva `""` em qualquer um dos DOIS `return` de
    `_html_dos_externos` e esta régua reprova. **São dois de propósito** — a
    saída curta (`if not ctx.externos`) é o caminho que a máquina dela percorre,
    e curar só o de baixo deixa o travessão exatamente onde ela o viu. Foi o que
    aconteceu na primeira volta desta cura.
    """
    import monta

    vazio = jogar.pacote(_ctx([]))["externos"]
    assert vazio == monta.NADA_A_DIZER, (
        f"a Jogar sem externo devolveu {vazio!r} — com `''` o piloto escreve "
        f"`—` e a grade dos assentos ganha um quinto item com um traço dentro")
    # E ELE MEDE ZERO: o CSS da aba esconde o marcador dentro da `.ext-vaga`.
    # Sem esta regra o `<i>` estaria lá e continuaria não mostrando nada — mas
    # por acidente de elemento vazio, não por decisão.
    assert ".ext-vaga > .nada{display:none}" in (
        INTERFACE / "aba01.py").read_text(encoding="utf-8"), (
        "a regra que esconde o marcador saiu do CSS da aba 01")


def test_a_jogar_avisa_a_armadilha_do_driver_so_no_nintendo() -> None:
    """O aviso do `hid-nintendo` nasce no Pro por rádio, e em mais ninguém."""
    do_pro = jogar.pacote(_ctx([UM_PRO]))["externos"]
    assert "por cabo é estável" in do_pro
    do_8bitdo = jogar.pacote(_ctx([UM_8BITDO]))["externos"]
    assert "por cabo é estável" not in do_8bitdo


def test_a_jogar_nao_inventa_cor_de_plastico_para_o_externo() -> None:
    """A folha das 28 cores é dos DualSense — um 8BitDo não tem linha nela.

    Uma borda colorida aqui seria a tela afirmando um modelo que ninguém mediu,
    que é a mesma regra que faz `_cor_do_plastico` devolver `""`.
    """
    html = jogar.pacote(_ctx([UM_8BITDO]))["externos"]
    assert "--plastico" not in html
    assert "data-colorway" not in html


def test_o_externo_nao_usa_a_classe_dos_assentos() -> None:
    """`.cartao` e `data-controle` são dos quatro assentos, e só deles."""
    html = jogar.pacote(_ctx([UM_8BITDO, UM_PRO]))["externos"]
    assert 'class="cartao' not in html
    assert "data-controle" not in html


def test_o_endereco_dos_externos_esta_prometido_na_pagina() -> None:
    """`externos` está em `DA_PAGINA` — senão a `cobertura` mente.

    Emitir uma chave sem pô-la na lista deixa o contador menor que o pacote, que
    é o defeito que aquele número existe para denunciar.
    """
    assert "externos" in jogar.DA_PAGINA


# ---------------------------------------------------------------------------
# 3. A ABA 08 — a linha 305 do CSV
# ---------------------------------------------------------------------------
def test_a_conexoes_lista_o_externo() -> None:
    from pacotes import a08_conexoes as conexoes

    html = conexoes._html_dos_externos(_ctx([UM_PRO]))
    assert 'class="ext-linha"' in html
    assert "Controle 4" in html
    # A MESMA FRASE DA ABA 01, PELO MESMO DONO: é isso que impede as duas abas
    # de discordarem sobre o mesmo aparelho.
    assert "só vê" in html
    assert "por cabo é estável" in html


def test_a_conexoes_apaga_a_lista_quando_nao_ha_externo() -> None:
    from pacotes import a08_conexoes as conexoes

    assert conexoes._html_dos_externos(_ctx([])) == ""


def test_as_duas_abas_dizem_a_mesma_coisa_do_mesmo_aparelho() -> None:
    """O nome e o transporte batem entre as duas — um dono, duas telas."""
    from pacotes import a08_conexoes as conexoes

    do_01 = jogar.pacote(_ctx([UM_8BITDO]))["externos"]
    do_08 = conexoes._html_dos_externos(_ctx([UM_8BITDO]))
    for pedaco in ("Controle 3", "8BitDo", "rádio", "só vê"):
        assert pedaco in do_01 and pedaco in do_08, pedaco


# ---------------------------------------------------------------------------
# 4. O ENDEREÇO EXISTE NA BANCADA — senão o pacote escreve no vazio
# ---------------------------------------------------------------------------
def test_as_duas_paginas_da_bancada_tem_onde_escrever() -> None:
    """O `data-campo` com alvo `html` está nas duas páginas da bancada.

    Endereço que não existe não levanta: `querySelector` devolve `null` e a
    pintura escreve zero, calada. É como a coluna Atenção mentiu por dois dias.
    """
    for arquivo, campo in (("01-jogar.html", "externos"),
                           ("08-conexoes.html", "externos-lista")):
        texto = onde.pagina(arquivo).read_text()
        assert f'data-campo="{campo}" data-hef-alvo="html"' in texto, arquivo


def test_nenhum_aparelho_de_exemplo_nasce_no_desenho() -> None:
    """A página parada não afirma um externo — quem afirma é o produto."""
    for arquivo, marca in (("01-jogar.html", 'class="ext-cartao"'),
                           ("08-conexoes.html", 'class="ext-linha"')):
        assert marca not in onde.pagina(arquivo).read_text(), arquivo


# ---------------------------------------------------------------------------
# 5. O PILOTO — o dublê que sabe RECUSAR
# ---------------------------------------------------------------------------
class _PilotoDeMentira:
    """O mínimo do piloto que a leitura dos externos toca.

    Ela não abre janela, não fala com GTK e não sobe daemon — é a função de
    `hefesto_vivo` chamada sobre um objeto que tem só os quatro atributos que
    ela lê. É o mesmo desenho do dublê da ponte: o que interessa é QUAL função
    foi chamada e com quê.
    """

    def __init__(self) -> None:
        self._externos: list[dict[str, Any]] = []
        self._externos_lidos_em = 0.0
        self._externos_no_ar = False
        # O QUE `_contexto` TAMBÉM LÊ, e só isso: o leitor de cor (que responde
        # `{}` até a primeira pergunta voltar) e a trava das threads dele.
        self.perguntados: set[str] = set()
        self.leitor = _LeitorDeMentira()

    #: OS DOIS TETOS SÃO OS DA CLASSE REAL, emprestados e nunca digitados: um
    #: número escrito aqui faria a régua medir o dublê em vez do produto.
    SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS = (
        __import__("hefesto_dualsense4unix.interface.hefesto_vivo",
                   fromlist=["Piloto"]).Piloto.SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS)
    SEGUNDOS_DE_ESPERA_DOS_EXTERNOS = (
        __import__("hefesto_dualsense4unix.interface.hefesto_vivo",
                   fromlist=["Piloto"]).Piloto.SEGUNDOS_DE_ESPERA_DOS_EXTERNOS)

    #: O MÉTODO REAL, EMPRESTADO — e não uma reescrita. Este dublê existe para
    #: dar ao `_contexto` os quatro atributos que ele lê; o COMPORTAMENTO tem de
    #: ser o do produto, senão a régua mede o dublê. É o defeito que esta casa
    #: nomeia: *"o dublê era mais frouxo que a função real"*.
    _talvez_ler_os_externos = (
        __import__("hefesto_dualsense4unix.interface.hefesto_vivo",
                   fromlist=["Piloto"]).Piloto._talvez_ler_os_externos)


class _LeitorDeMentira:
    """O leitor de cor do plástico, calado. Ele não é o assunto desta régua."""

    def conhecidos(self) -> dict[str, Any]:
        return {}

    def perguntar(self, _uniq: str) -> None:
        return None


def _ler(piloto: _PilotoDeMentira, resposta: Any, levanta: bool = False) -> None:
    """Roda `_talvez_ler_os_externos` com um `controller.list` de mentira.

    A thread é esperada de propósito: sem o `join` a régua leria a lista antes
    de a resposta chegar e passaria por acidente.
    """
    import threading

    from hefesto_dualsense4unix.interface import hefesto_vivo
    from hefesto_dualsense4unix.interface.pacotes import ponte

    chamadas: list[tuple[str, dict[str, Any]]] = []

    def falso(metodo: str, timeout: float | None = None, **params: Any) -> Any:
        chamadas.append((metodo, params))
        if levanta:
            raise RuntimeError("o daemon não respondeu a controller.list")
        return resposta

    vivas = set(threading.enumerate())
    antes = ponte.resultado
    ponte.resultado = falso  # type: ignore[assignment]
    try:
        hefesto_vivo.Piloto._talvez_ler_os_externos(piloto)  # type: ignore[arg-type]
        for t in threading.enumerate():
            if t not in vivas:
                t.join(timeout=5)
    finally:
        ponte.resultado = antes  # type: ignore[assignment]
    # AS CHAMADAS SE SOMAM entre uma leitura e a seguinte: é assim que a régua
    # do teto pode contar quantas perguntas SAÍRAM em duas voltas. Trocar a
    # lista aqui faria a segunda volta apagar a prova da primeira — e o teste do
    # teto passaria por acidente, com zero chamada em vez de uma.
    piloto.chamadas = getattr(piloto, "chamadas", []) + chamadas  # type: ignore[attr-defined]


def test_o_piloto_pergunta_pelos_externos_com_o_opt_in() -> None:
    """A pergunta é `controller.list {"external": True}` — sem o opt-in, nada vem.

    A chave nem aparece na resposta sem ela
    (`ipc_handlers._handle_controller_list`: *"sem opt-in, a chave nem aparece"*).
    """
    p = _PilotoDeMentira()
    _ler(p, {"controllers": [], "external": [UM_8BITDO]})
    assert p.chamadas == [("controller.list", {"external": True})]  # type: ignore[attr-defined]
    assert p._externos == [UM_8BITDO]


def test_o_piloto_nao_repete_a_pergunta_dentro_do_teto() -> None:
    """Uma leitura por `SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS`, e não uma por tique.

    A enumeração custa 10-40 ms e um subprocess — num orçamento de 100 ms,
    perguntar a cada tique comeria até 40% do laço para receber a mesma resposta.
    """
    p = _PilotoDeMentira()
    _ler(p, {"external": [UM_8BITDO]})
    _ler(p, {"external": [UM_PRO]})
    assert len(p.chamadas) == 1  # type: ignore[attr-defined]
    assert p._externos == [UM_8BITDO]


def test_o_daemon_mudo_nao_apaga_a_lista_boa() -> None:
    """**A MORDIDA.** *"Não consegui perguntar"* não vira *"não há controle"*.

    `ponte.resultado` LEVANTA quando o daemon não atende — é a escolha declarada
    em `pacotes/ponte.py`. Um `except` que zerasse a lista transformaria a
    ausência de notícia em sucesso, que é o defeito mais caro desta casa.
    """
    p = _PilotoDeMentira()
    _ler(p, {"external": [UM_8BITDO]})
    p._externos_lidos_em = 0.0
    _ler(p, None, levanta=True)
    assert p._externos == [UM_8BITDO]
    assert p._externos_no_ar is False


def test_a_resposta_sem_a_chave_external_esvazia_a_lista() -> None:
    """Um daemon que responde SEM a chave é resposta boa: não há externo.

    Diferente do daemon MUDO acima — ali ninguém respondeu; aqui alguém
    respondeu "nenhum". As duas se lêem igual na tela e são medidas diferentes.
    """
    p = _PilotoDeMentira()
    _ler(p, {"external": [UM_8BITDO]})
    p._externos_lidos_em = 0.0
    _ler(p, {"controllers": []})
    assert p._externos == []


def test_o_contexto_do_tique_carrega_os_externos_lidos() -> None:
    """**A MORDIDA QUE FALTAVA, e ela reprovou a primeira régua desta sprint.**

    As provas acima mediam `_talvez_ler_os_externos` de um lado e o pacote do
    outro, com um `Contexto` montado à MÃO no meio — e por isso passavam
    inteiras com a cura arrancada: bastava `_contexto` não chamar a leitura, ou
    montar o `Contexto` com `externos=[]`, para a tela voltar a não ver externo
    nenhum **com dezenove testes verdes**.

    É a armadilha nomeada no `COMO-EXECUTAR-UMA-SPRINT.md` §9 — *o dublê que só
    sabe passar* —, achada aqui pelo passo 2 do protocolo: arrancar a cura e
    olhar. Esta prova cobre o FIO, que é a única parte que nenhuma das outras
    tocava.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo

    p = _PilotoDeMentira()
    _ler(p, {"external": [UM_8BITDO]})
    ctx, _ = hefesto_vivo.Piloto._contexto(p, dict(VIVO))  # type: ignore[arg-type]
    assert ctx.externos == [UM_8BITDO]
    # E O EXTERNO NÃO ENCOSTA NOS ASSENTOS pelo caminho do tique, que é onde o
    # engano custaria caro: `conectados` sai de `state["controllers"]`, e o
    # `state` desta prova não traz nenhum.
    assert ctx.conectados == []


def test_o_tique_pergunta_sozinho_pelos_externos() -> None:
    """`_contexto` DISPARA a leitura — senão a lista nunca sai de vazia.

    A outra metade do fio: mesmo carregando `self._externos` para o `Contexto`,
    um tique que não pergunta deixa a lista em `[]` para sempre.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo
    from hefesto_dualsense4unix.interface.pacotes import ponte

    p = _PilotoDeMentira()
    chamadas: list[str] = []

    def falso(metodo: str, timeout: float | None = None, **_: Any) -> Any:
        chamadas.append(metodo)
        return {"external": []}

    antes = ponte.resultado
    ponte.resultado = falso  # type: ignore[assignment]
    try:
        hefesto_vivo.Piloto._contexto(p, dict(VIVO))  # type: ignore[arg-type]
        for t in list(__import__("threading").enumerate()):
            if t is not __import__("threading").current_thread():
                t.join(timeout=5)
    finally:
        ponte.resultado = antes  # type: ignore[assignment]
    assert chamadas == ["controller.list"]


def test_o_teto_de_tempo_e_o_da_janela_antiga() -> None:
    """Um número para a mesma pergunta — o da GTK, não um segundo escolhido aqui."""
    from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin
    from hefesto_dualsense4unix.interface import hefesto_vivo

    assert (hefesto_vivo.Piloto.SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS
            == HomeActionsMixin.EXTERNOS_THROTTLE_S)
