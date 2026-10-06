"""A ponte de som por rádio é DE CADA CONTROLE, e a frase não mente mais."""
from __future__ import annotations

import os
import threading

import pytest

from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    GerenciadorDeNosDeSom,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    MOTIVO_NO_SEM_PONTE_NO_RADIO,
    POR_RADIO,
    PonteDeSomPorRadio,
    a_ponte_do_radio_pode_subir,
    a_ponte_do_radio_sabe_montar,
    rota_do_no,
)

P1 = "aabbccdd0001"
P2 = "aabbccdd0002"
RADIO = "bluetooth"


def test_o_produto_sabe_montar_o_pacote_desde_a_bancada() -> None:
    """A resposta que mudou em 10/09/2026, e que a tela repetia errada."""
    assert a_ponte_do_radio_sabe_montar() is True

    pode, porque = a_ponte_do_radio_pode_subir()
    assert isinstance(pode, bool)
    assert (porque == "") is pode, (
        "*não sei montar* e *sei, mas falta a libopus aqui* pedem recados "
        "diferentes — juntá-las foi o que fez a tela culpar o aparelho"
    )


def test_a_frase_nao_culpa_mais_o_nosso_conhecimento() -> None:
    """A tela do usuário não pode dizer que o Hefesto não sabe, quando ele sabe."""
    assert "não sabe montar" not in MOTIVO_NO_SEM_PONTE_NO_RADIO
    assert "Ligue-o no cabo" in MOTIVO_NO_SEM_PONTE_NO_RADIO, (
        "a saída que funciona hoje continua tendo de estar na frase"
    )


def test_sem_ponte_injetada_o_radio_continua_recusando() -> None:
    """`None` é *«ninguém me deu ponte»*, e a recusa honesta é o padrão."""
    gerente = GerenciadorDeNosDeSom()
    assert gerente._ponte_do_radio(P1) is None

    rota = rota_do_no(P1, RADIO, (P1,), ponte_do_radio=None)
    assert rota.tem_rota is False
    assert rota.motivo == MOTIVO_NO_SEM_PONTE_NO_RADIO


def test_a_ponte_de_um_nao_publica_o_outro() -> None:
    """DOIS controles no rádio, UMA ponte de pé: só aquele publica."""
    no_ar = {P1}
    gerente = GerenciadorDeNosDeSom(
        ponte_do_radio_por_controle=lambda uniq: (lambda: uniq in no_ar)
    )

    rota_p1 = rota_do_no(P1, RADIO, (P1, P2), ponte_do_radio=gerente._ponte_do_radio(P1))
    rota_p2 = rota_do_no(P2, RADIO, (P1, P2), ponte_do_radio=gerente._ponte_do_radio(P2))

    assert rota_p1.tem_rota is True, "o controle com ponte de pé tem de publicar"
    assert rota_p1.por_onde == POR_RADIO
    assert rota_p2.tem_rota is False, (
        "o P2 não tem ponte no ar e publicou mesmo assim — a ponte está sendo "
        "tratada como global, e o som de um sairia no alto-falante do outro"
    )
    assert rota_p2.motivo == MOTIVO_NO_SEM_PONTE_NO_RADIO


def test_a_injecao_que_explode_nao_derruba_o_no() -> None:
    """Um provedor de ponte que levanta vira `None`, nunca um `True` otimista."""
    def explode(_uniq: str) -> object:
        raise RuntimeError("o broker caiu")

    gerente = GerenciadorDeNosDeSom(ponte_do_radio_por_controle=explode)
    assert gerente._ponte_do_radio(P1) is None


def test_a_ponte_identifica_pelo_uniq_e_nao_pelo_hidraw() -> None:
    """O `hidrawN` muda a cada reconexão; o endereço do controle não."""
    ponte = PonteDeSomPorRadio(
        uniq=P1, abrir_hidraw=lambda: None, fonte_de_pcm=lambda n: b"\x00" * n
    )
    assert ponte.uniq == P1
    assert ponte.esta_de_pe() is False


def test_a_ponte_que_nao_abre_o_hidraw_diz_por_que() -> None:
    """Ela recusa com razão escrita, em vez de subir muda."""
    ponte = PonteDeSomPorRadio(
        uniq=P1, abrir_hidraw=lambda: None, fonte_de_pcm=lambda n: b"\x00" * n
    )
    assert ponte.subir() is False
    assert ponte.motivo, "a ponte não subiu e não disse por quê"
    assert ponte.esta_de_pe() is False


def test_a_ponte_desce_sem_ter_subido() -> None:
    """`descer` é idempotente — o daemon a chama no desligamento sem checar."""
    ponte = PonteDeSomPorRadio(
        uniq=P1, abrir_hidraw=lambda: None, fonte_de_pcm=lambda n: b"\x00" * n
    )
    ponte.descer()
    ponte.descer()
    assert ponte.contagem is None


def test_a_ponte_escreve_o_relatorio_combinado_sem_escolha() -> None:
    """O-SOM-E-A-HAPTICA-NUM-RELATORIO-SO-01: a ponte não aceita arranjo; escreve o ``0x36``."""
    with pytest.raises(TypeError):
        PonteDeSomPorRadio(  # type: ignore[call-arg]
            uniq=P1, abrir_hidraw=lambda: None, fonte_de_pcm=bytes, arranjo=None
        )
    ponte = PonteDeSomPorRadio(uniq=P1, abrir_hidraw=lambda: None, fonte_de_pcm=bytes)
    assert ponte.RELATORIO == "0x36"


class _FonteQueTrava:
    """Uma fonte de PCM que bloqueia até mandarem soltar — como um nó parado."""

    def __init__(self) -> None:
        self.solte = threading.Event()
        self.entrou = threading.Event()

    def __call__(self, quantos: int) -> bytes:
        self.entrou.set()
        self.solte.wait(timeout=30)
        return b"\x00" * quantos


def _um_fd_de_mentira() -> int:
    """Um fd real e escrevível, para o laço ter o que fechar."""
    leitura, escrita = os.pipe()
    os.close(leitura)
    return escrita


def test_descendo_nao_e_de_pe_e_a_thread_viva_nao_e_ignorada() -> None:
    """As DUAS perguntas do ciclo de vida, e elas têm respostas diferentes."""
    fonte = _FonteQueTrava()
    ponte = PonteDeSomPorRadio(
        uniq=P1, abrir_hidraw=_um_fd_de_mentira, fonte_de_pcm=fonte, seco=True
    )
    assert ponte.subir() is True
    assert ponte.esta_de_pe() is True
    assert fonte.entrou.wait(timeout=10), "a thread não chegou a ler a fonte"
    try:
        assert ponte.descer(esperar_s=0.2) is False, (
            "a thread está presa na fonte e `descer` disse que juntou"
        )
        assert ponte.esta_de_pe() is False, (
            "a ponte se declarou DE PÉ enquanto descia — o nó publicaria rota "
            "para um som que não vai mais sair"
        )
        assert ponte._corrida_viva() is True, (
            "a ponte esqueceu a thread que ainda respira — é essa amnésia que "
            "deixava um `subir()` abrir fd por cima da corrida anterior"
        )
    finally:
        fonte.solte.set()
        ponte.descer(esperar_s=10)


def test_subir_recusa_enquanto_a_corrida_anterior_vive() -> None:
    """A guarda que impede duas threads bombeando o mesmo controle."""
    fonte = _FonteQueTrava()
    abertos: list[int] = []

    def abrir() -> int:
        fd = _um_fd_de_mentira()
        abertos.append(fd)
        return fd

    ponte = PonteDeSomPorRadio(
        uniq=P1, abrir_hidraw=abrir, fonte_de_pcm=fonte, seco=True
    )
    assert ponte.subir() is True
    assert fonte.entrou.wait(timeout=10)
    try:
        ponte.descer(esperar_s=0.2)
        assert ponte.subir() is False, (
            "subiu por cima de uma corrida viva — duas threads passariam a "
            "escrever no mesmo controle, ao dobro da cadência"
        )
        assert ponte.motivo, "recusou e não disse por quê"
        assert len(abertos) == 1, (
            f"abriu {len(abertos)} descritores; o segundo receberia do kernel o "
            "mesmo número que a corrida viva ainda usa"
        )
    finally:
        fonte.solte.set()
        ponte.descer(esperar_s=10)


def test_a_thread_fecha_o_PROPRIO_fd_e_nao_o_da_ponte_nova() -> None:  # noqa: N802
    """Cada corrida tem o seu descritor, e o `finally` fecha só o dela."""
    fonte = _FonteQueTrava()
    fd = _um_fd_de_mentira()
    ponte = PonteDeSomPorRadio(
        uniq=P1, abrir_hidraw=lambda: fd, fonte_de_pcm=fonte, seco=True
    )
    assert ponte.subir() is True
    assert fonte.entrou.wait(timeout=10)
    fonte.solte.set()
    assert ponte.descer(esperar_s=10) is True

    with pytest.raises(OSError):
        os.fstat(fd)


def test_o_sinal_de_parada_nao_e_reusado_entre_corridas() -> None:
    """Um `Event` NOVO por subida — `clear()` ressuscitaria a thread velha."""
    ponte = PonteDeSomPorRadio(
        uniq=P1, abrir_hidraw=_um_fd_de_mentira,
        fonte_de_pcm=lambda n: b"\x00" * n, seco=True,
    )
    assert ponte.subir() is True
    primeiro = ponte._parar
    assert ponte.descer(esperar_s=10) is True
    assert ponte._parar is None, "o sinal da corrida encerrada tem de sair"

    assert ponte.subir() is True
    try:
        assert ponte._parar is not primeiro, (
            "o mesmo `Event` foi reusado — um `clear()` nele faria a thread da "
            "corrida anterior voltar a bombear"
        )
    finally:
        ponte.descer(esperar_s=10)
