"""VIGIA-DE-APARELHO-01 — o portão da SUITE-QUE-SUJA-O-JORNAL-01 (E4)."""

from __future__ import annotations

import datetime
import os
import pathlib
import time
from typing import Any

import pytest

from tests import conftest as vigia_mod

NOME_DA_MORDIDA = vigia_mod.NOME_DO_NO_DE_MORDIDA


def _uinput_de_verdade() -> Any:
    """A fábrica REAL do python-uinput, guardada pela vigia antes do dublê."""
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


PODE_MORDER = _da_para_criar_no()

sem_uinput = pytest.mark.skipif(
    not PODE_MORDER,
    reason="sem python-uinput ou sem permissão em /dev/uinput (é o caso do CI)",
)


def test_a_vigia_esta_armada_nas_portas_que_este_ambiente_tem() -> None:
    """Portão desarmado é portão que ninguém vê cair. Este teste é o alarme."""
    vigia = vigia_mod.vigia_da_sessao()
    assert vigia is not None, (
        "a VIGIA-DE-APARELHO-01 não está armada — sem ela nada impede um teste "
        "de criar aparelho de entrada no kernel de quem roda a suíte"
    )
    assert "os.open" in vigia.originais
    assert getattr(os.open, "vigia_de_aparelho", None) == "os.open"

    for modulo, atributo in vigia_mod.FABRICAS_DE_APARELHO:
        porta = f"{modulo}.{atributo}"
        original = vigia.originais.get(porta)
        if original is None:
            continue
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
    """O journal já registrou `nome`? Espera até `teto` segundos por ele."""
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
    """A mordida, e ela é UMA só: um nó de verdade, criado e morto aqui dentro."""
    import uinput

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

    if vigia_mod.nascimentos_no_journal(desde) is not None:
        assert _journal_viu(NOME_DA_MORDIDA, desde), (
            "o journal do kernel não registrou o nó em 5 s — o aviso do fim da "
            "sessão está cego e o buraco do processo filho fica sem instrumento"
        )

    da_sessao = vigia_mod.problemas_da_vigia(vigia_mod.vigia_da_sessao())
    assert [p for p in da_sessao if NOME_DA_MORDIDA in p] == []


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
    """A porta olha DOIS caminhos; qualquer outro arquivo abre normalmente."""
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
