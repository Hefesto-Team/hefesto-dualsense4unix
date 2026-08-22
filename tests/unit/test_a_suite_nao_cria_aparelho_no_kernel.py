"""VIGIA-DE-APARELHO-01 — o portão da SUITE-QUE-SUJA-O-JORNAL-01 (E4).

O defeito que este arquivo existe para impedir de voltar, medido em 20/08/2026
na máquina dela: **1289 nós `Hefesto - Dualsense4Unix Virtual Keyboard` num
dia**, criados pelas minhas execuções de `pytest`, cada add/remove de teclado
re-assentando o seat do compositor e derrubando a tela cheia dela no meio de um
jogo. A cura (o dublê de `uinput.Device`) pegou: de 19 a 22/08 o `journalctl -k`
dela não registra UM nó com esse nome. O que faltava é este portão — entre a
descoberta (04/08) e a cura (20/08) foram dezesseis dias em que ninguém notou.

## A régua escolhida, e por que as outras três não servem

Todas foram MEDIDAS nesta máquina em 22/08 antes de serem descartadas:

- **contagem de `/dev/input/event*` antes e depois** — CEGA ao defeito: o nó
  morre quando o descritor que o criou fecha, e isso é dentro do próprio teste.
  `test_a_regua_pega_o_no_de_verdade_que_a_contagem_nao_ve` PROVA isso criando
  um nó de verdade: a contagem é a mesma antes e depois, e o kernel viu o nó.
- **o maior `inputN` de `/sys/class/input`** — parecia a saída e caiu na
  primeira execução deste arquivo: o número cresce e não é reciclado (o nó da
  mordida saiu `input198` com o máximo em 196), mas o sysfs só lista o que está
  VIVO, e o máximo volta a 196 no instante em que o nó morre. Nenhuma régua de
  sysfs enxerga o nó que já morreu. Ela também não atribuiria: 43 aparelhos de
  entrada nasceram nesta máquina em uma hora sem suíte nenhuma (espelhos do
  Steam Input e os controles dela).
- **journal do kernel** — a única régua que sobrevive à morte do nó, e foi com
  ela que os 1289 foram contados. Não serve de portão (não existe no CI, e a
  linha não diz de QUEM é o nó); fica como AVISO no `sessionfinish`, onde é o
  único instrumento que vê nó que nasce em processo FILHO.
- **arquivo fora do `tmp_path`** — é o CANARIO-FS-01 + BERCO-DE-TMP-01, e
  nenhum dos dois vê uinput: nó de entrada não deixa arquivo.

A régua é **a PORTA**: `uinput.Device`, `evdev.UInput` e `os.open` de
`/dev/uinput` / `/dev/uhid`. Atribui (é o nosso processo), não pede privilégio,
e vê o nó transitório. O cego dela é o processo FILHO — coberto pelo aviso.

## O portão tem duas metades, e as duas são necessárias

Este arquivo roda no meio da suíte, então o livro que ele lê só tem quem passou
ANTES dele. A cobertura da sessão inteira é do `_vigia_no_fim_da_sessao` no
conftest, que reprova com `exitstatus = 1`. O que este arquivo garante, e o
`sessionfinish` não garantiria sozinho, é que **a vigia está armada** e que **a
régua morde** — um portão desarmado passa despercebido para sempre.
"""

from __future__ import annotations

import datetime
import os
import pathlib
import time
from typing import Any

import pytest

from tests import conftest as vigia_mod

#: O nome do nó da mordida vem do conftest porque os dois lados precisam
#: concordar: aqui ele é criado, e lá o aviso do journal o EXCLUI. NUNCA o nome
#: de produção (regra E1 da sprint), e ele vive microssegundos.
NOME_DA_MORDIDA = vigia_mod.NOME_DO_NO_DE_MORDIDA


def _uinput_de_verdade() -> Any:
    """A fábrica REAL do python-uinput, guardada pela vigia antes do dublê.

    Vem de `vigia.originais` de propósito: pegar `uinput.Device` do módulo
    devolveria o dublê da sessão (que não cria nada) ou a porta da vigia (que
    recusa) — e o teste da mordida precisa do nó de VERDADE, senão ele prova
    que a régua funciona contra a própria régua.
    """
    vigia = vigia_mod.vigia_da_sessao()
    if vigia is None:
        return None
    return vigia.originais.get("uinput.Device")


def _da_para_criar_no() -> bool:
    """`/dev/uinput` abre para escrita nesta máquina? (No CI, não.)"""
    vigia = vigia_mod.vigia_da_sessao()
    abrir = vigia.originais.get("os.open") if vigia is not None else os.open
    if abrir is None or _uinput_de_verdade() is None:
        return False
    try:
        descritor = abrir("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return False
    os.close(descritor)
    return True


#: Medido UMA vez: a sonda abre e fecha `/dev/uinput`, e não cria nada.
PODE_MORDER = _da_para_criar_no()

sem_uinput = pytest.mark.skipif(
    not PODE_MORDER,
    reason="sem python-uinput ou sem permissão em /dev/uinput (é o caso do CI)",
)


# ---------------------------------------------------------------------------
# O portão
# ---------------------------------------------------------------------------


def test_a_vigia_esta_armada_nas_portas_que_este_ambiente_tem() -> None:
    """Portão desarmado é portão que ninguém vê cair. Este teste é o alarme."""
    vigia = vigia_mod.vigia_da_sessao()
    assert vigia is not None, (
        "a VIGIA-DE-APARELHO-01 não está armada — sem ela nada impede um teste "
        "de criar aparelho de entrada no kernel de quem roda a suíte"
    )
    assert "os.open" in vigia.originais
    assert getattr(os.open, "vigia_de_aparelho", None) == "os.open"

    # Cada fábrica que EXISTE neste ambiente tem de estar coberta. Coberta é
    # "não é mais a original": ou está a porta da vigia, ou está o dublê da
    # `_nenhum_uinput_de_verdade` por cima dela — os dois impedem o nó.
    for modulo, atributo in vigia_mod.FABRICAS_DE_APARELHO:
        porta = f"{modulo}.{atributo}"
        original = vigia.originais.get(porta)
        if original is None:
            continue  # biblioteca ausente neste ambiente
        alvo = __import__(modulo, fromlist=[atributo])
        assert getattr(alvo, atributo) is not original, (
            f"{porta} está exposto: um teste que chame isso cria aparelho de "
            "entrada de verdade na máquina de quem roda a suíte"
        )


def test_o_livro_da_vigia_esta_limpo_ate_aqui() -> None:
    """Ninguém bateu na porta do kernel até este ponto da suíte."""
    problemas = vigia_mod.problemas_da_vigia(vigia_mod.vigia_da_sessao())
    assert problemas == [], (
        "algum teste tentou criar aparelho de entrada de verdade:\n  "
        + "\n  ".join(problemas)
    )


# ---------------------------------------------------------------------------
# A mordida: um nó de VERDADE, criado e destruído aqui dentro
# ---------------------------------------------------------------------------


def _no_do_aparelho(nome: str) -> int | None:
    """O `N` de `/sys/class/input/inputN` do aparelho com este nome, ou None."""
    raiz = pathlib.Path("/sys/class/input")
    for entrada in sorted(raiz.iterdir()):
        if not entrada.name.startswith("input") or not entrada.name[5:].isdigit():
            continue
        try:
            if (entrada / "name").read_text().strip() == nome:
                return int(entrada.name[5:])
        except OSError:
            continue
    return None


def _quantos_event() -> int:
    """A régua (a) da lista lá em cima: quantos `/dev/input/event*` existem."""
    try:
        return len([n for n in os.listdir("/dev/input") if n.startswith("event")])
    except OSError:  # pragma: no cover — /dev/input sempre existe no Linux
        return -1


def _journal_viu(nome: str, desde: str, teto: float = 5.0) -> bool:
    """O journal já registrou `nome`? Espera até `teto` segundos por ele.

    A espera não é zelo: o journald escreve com atraso, medido em 22/08 numa
    série de cinco nós — 0,02 s no caso comum e 0,13 s no pior. A primeira
    versão deste teste perguntava UMA vez e reprovou sozinha na terceira
    execução. Teto alto e saída na primeira resposta: o custo comum é uma
    consulta só.
    """
    limite = time.monotonic() + teto
    while True:
        nascidos = vigia_mod.nascimentos_no_journal(desde) or []
        if nome in nascidos:
            return True
        if time.monotonic() >= limite:
            return False
        time.sleep(0.1)


@sem_uinput
def test_a_regua_pega_o_no_de_verdade_que_a_contagem_nao_ve() -> None:
    """A mordida, e ela é UMA só: um nó de verdade, criado e morto aqui dentro.

    Um nó por execução, e não dois, porque cada nó destes é exatamente o custo
    que a sprint existe para não pagar (add/remove de teclado re-assenta o seat
    do compositor dela). Com esse único nó o teste responde as quatro perguntas
    que decidem a régua:

    1. a PORTA registra a passagem, com nodeid e nome;
    2. o KERNEL confirma o mesmo nó (`/sys/class/input/*/name`) — contagem
       independente, sem a qual a régua estaria medindo a si mesma;
    3. a contagem de `/dev/input/event*` sobe com o nó vivo e volta EXATAMENTE
       ao valor de antes quando ele morre — a prova de que a régua (a) é cega
       ao nó transitório, que é o motivo de a régua ser a porta;
    4. o journal do kernel registra o nascimento e continua registrando depois
       da morte — a régua (c), a única que sobrevive ao nó, e a que valida esta
       aqui contra uma contagem que não é nossa.
    """
    import uinput  # a biblioteca; a FÁBRICA real vem da vigia

    fabrica = _uinput_de_verdade()
    vigia = vigia_mod.VigiaDeAparelho(recusar=False)
    porta = vigia.envolver_fabrica(fabrica, "uinput.Device")
    vigia.quem = "test_a_regua_pega_o_no_de_verdade_que_a_contagem_nao_ve"

    assert NOME_DA_MORDIDA not in vigia_mod.nomes_de_aparelhos_vivos()
    eventos_antes = _quantos_event()
    maior_vivo_antes = vigia_mod.maior_no_de_entrada_vivo()
    desde = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    aparelho = porta((uinput.KEY_F24,), name=NOME_DA_MORDIDA)
    try:
        assert len(vigia.livro) == 1, "a porta não registrou a passagem"
        nascimento = vigia.livro[0]
        assert nascimento.porta == "uinput.Device"
        assert nascimento.quem == vigia.quem
        assert NOME_DA_MORDIDA in nascimento.detalhe

        assert NOME_DA_MORDIDA in vigia_mod.nomes_de_aparelhos_vivos(), (
            "a vigia registrou um nó que o kernel não conhece — a régua está "
            "medindo a si mesma"
        )
        assert _quantos_event() >= eventos_antes + 1
        numero = _no_do_aparelho(NOME_DA_MORDIDA)
        assert numero is not None and numero > maior_vivo_antes, (
            "o kernel reciclou um número de aparelho — a régua (b) mudaria de "
            "forma, e a nota sobre ela neste arquivo teria de ser refeita"
        )
    finally:
        aparelho.destroy()

    assert NOME_DA_MORDIDA not in vigia_mod.nomes_de_aparelhos_vivos(), (
        "o nó da mordida ficou vivo depois do teste"
    )
    assert _quantos_event() == eventos_antes, (
        "a contagem de event* MUDOU depois de o nó morrer — a premissa desta "
        "sprint (o nó não deixa resíduo) caiu, e a escolha de régua muda junto"
    )
    assert not pathlib.Path(f"/sys/class/input/input{numero}").exists(), (
        f"o sysfs ainda tem input{numero} depois de o nó morrer — se ele passou "
        "a guardar memória do número usado, a régua (b) volta a estar na mesa"
    )

    # A régua (c), medida no mesmo nó: o journal LEMBRA do que o sysfs esqueceu.
    if vigia_mod.nascimentos_no_journal(desde) is not None:  # no CI não há
        assert _journal_viu(NOME_DA_MORDIDA, desde), (
            "o journal do kernel não registrou o nó em 5 s — o aviso do fim da "
            "sessão está cego e o buraco do processo filho fica sem instrumento"
        )

    # E a mordida NÃO sujou o livro da sessão: ela passou pela porta dela
    # mesma, não pela da sessão. Sem isto, provar a régua deixaria o portão
    # vermelho para sempre. Afirmação estreita de propósito — se OUTRO teste
    # sujou o livro, quem reprova é o portão acima, e não este.
    da_sessao = vigia_mod.problemas_da_vigia(vigia_mod.vigia_da_sessao())
    assert [p for p in da_sessao if NOME_DA_MORDIDA in p] == []


# ---------------------------------------------------------------------------
# A porta fecha, além de anotar
# ---------------------------------------------------------------------------


def test_a_porta_recusa_e_nao_chama_a_fabrica_de_verdade() -> None:
    """Com `recusar=True` (o padrão da sessão), o nó nem chega a nascer."""

    def _fabrica_proibida(*_a: Any, **_kw: Any) -> Any:
        raise AssertionError("a porta deixou passar: o nó nasceria de verdade")

    vigia = vigia_mod.VigiaDeAparelho()
    vigia.quem = "teste-sintetico"
    porta = vigia.envolver_fabrica(_fabrica_proibida, "evdev.UInput")

    with pytest.raises(OSError) as caiu:
        porta(name="qualquer coisa")

    assert isinstance(caiu.value, vigia_mod.AparelhoRecusadoError)
    assert vigia_mod.problemas_da_vigia(vigia) == [
        "evdev.UInput (name='qualquer coisa') <- teste-sintetico"
    ]


@pytest.mark.parametrize("no", vigia_mod.PORTAS_DE_APARELHO)
def test_os_dois_nos_de_kernel_sao_recusados_no_os_open(no: str) -> None:
    """`/dev/uinput` e `/dev/uhid` não abrem sob teste — e ficam no livro."""
    vigia = vigia_mod.VigiaDeAparelho()
    vigia.quem = "teste-sintetico"
    abrir = vigia.envolver_os_open(os.open)

    with pytest.raises(OSError):
        abrir(no, os.O_RDWR)

    assert [n.porta for n in vigia.livro] == [no]


def test_o_os_open_vigiado_deixa_passar_o_resto(tmp_path: Any) -> None:
    """A porta olha DOIS caminhos; qualquer outro arquivo abre normalmente.

    Sem esta afirmação a vigia seria um `os.open` quebrado para a suíte inteira
    — e o defeito apareceria longe daqui, num teste que nada tem com uinput.
    """
    vigia = vigia_mod.VigiaDeAparelho()
    abrir = vigia.envolver_os_open(os.open)
    alvo = tmp_path / "arquivo.txt"
    alvo.write_text("conteúdo")

    descritor = abrir(str(alvo), os.O_RDONLY)
    try:
        assert os.read(descritor, 32) == "conteúdo".encode()
    finally:
        os.close(descritor)
    assert vigia.livro == []
