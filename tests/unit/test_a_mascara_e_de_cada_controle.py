#!/usr/bin/env python3
"""A máscara é de CADA aparelho — e a tela e a escrita finalmente sabem disso.

O PEDIDO É DELA, 03/09/2026: *"É uma máscara por controle. Mesmo caso do
anterior."* — o "anterior" é a decisão dos quatro lugares, do mesmo dia.

**A CASA JÁ TINHA A METADE DIFÍCIL.** ``external_mask`` guarda a escolha por
APARELHO desde 15/08/2026 (MÁSCARA-POR-JOGADOR-01, decisão dela), e
``mascara_efetiva`` é consultada na criação de todo gamepad virtual — os três
degraus do daemon (``virtual_pad``, ``coop``, ``gamepad``) fecharam em 29/08.

FALTAVAM DOIS, e os dois estavam NOMEADOS no próprio módulo:

1. **a escrita.** *"Falta também o lado da escrita: quem grava a escolha dela é
   a rota IPC, que ainda só conhece a máscara da sessão."* ``set_mask`` e
   ``clear_mask`` existiam no registro e **não tinham um chamador em `src/`**;
2. **a tela.** ``mesa_viva`` lia o ``flavor`` da SESSÃO e escrevia o mesmo valor
   nos quatro cartões — a escolha por aparelho vivia no disco e não aparecia em
   lugar nenhum. Os seis chips da aba Jogar eram, por isso, `RECUSA_CALADO`.

AS MORDIDAS, e cada uma reprova um teste diferente:

* faça ``_mascaras_por_aparelho`` devolver ``{}`` → a tela volta a repetir a
  máscara da sessão nos quatro;
* tire o ``por_aparelho`` de ``mesa_viva`` → idem, e pelo outro lado;
* faça ``gamepad.mask.set`` aceitar ``flavor`` desconhecido → a recusa em voz
  alta morre e um erro de digitação vira troca silenciosa de máscara.
"""

from __future__ import annotations

import pytest

UNIQ_A = "aa:bb:cc:00:00:01"
UNIQ_B = "aa:bb:cc:00:00:02"


@pytest.fixture
def registro(tmp_path, monkeypatch):
    """Um registro de máscaras num lar de mentira — nunca o dela."""
    from hefesto_dualsense4unix.daemon.subsystems import external_mask as em

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    em._zerar_registro_de_mascaras()
    yield em.registro_de_mascaras()
    em._zerar_registro_de_mascaras()


def test_sem_escolha_o_aparelho_herda_a_sessao(registro) -> None:
    """Quem não escolheu segue o jogo. É a semântica de `ControllerOverrides`."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva

    assert mascara_efetiva(UNIQ_A, "xbox") == "xbox"
    assert mascara_efetiva(UNIQ_B, "dualsense") == "dualsense"


def test_dois_aparelhos_com_mascaras_diferentes(registro) -> None:
    """O PEDIDO DELA, na forma mais curta que se pode medir.

    Um escolhe DualSense, o outro não escolhe nada — e os dois recebem coisas
    diferentes na MESMA sessão.
    """
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva

    registro.set_mask(UNIQ_A, "dualsense")
    assert mascara_efetiva(UNIQ_A, "xbox") == "dualsense"
    assert mascara_efetiva(UNIQ_B, "xbox") == "xbox"


def test_a_escolha_sobrevive_a_troca_de_sessao(registro) -> None:
    """Trocar a máscara do JOGO não apaga a escolha do APARELHO."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva

    registro.set_mask(UNIQ_A, "dualsense")
    assert mascara_efetiva(UNIQ_A, "xbox") == "dualsense"
    assert mascara_efetiva(UNIQ_A, "dualsense") == "dualsense"


def test_limpar_devolve_a_heranca(registro) -> None:
    """Um registro em que só se entra é uma armadilha."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva

    registro.set_mask(UNIQ_A, "dualsense")
    registro.clear_mask(UNIQ_A)
    assert mascara_efetiva(UNIQ_A, "xbox") == "xbox"


def _mesa(por_aparelho: dict[str, str], da_sessao: str = "xbox"):
    from hefesto_dualsense4unix.interface import mesa_viva

    estado = {
        "controllers": [
            {"connected": True, "uniq": UNIQ_A, "transport": "usb"},
            {"connected": True, "uniq": UNIQ_B, "transport": "bluetooth"},
        ],
        "gamepad_emulation": {"flavor": da_sessao, "por_aparelho": por_aparelho},
    }
    return {c["uniq"]: c["mascara"] for c in mesa_viva.mesa_do_estado(estado, {})}


def test_a_mesa_mostra_a_mascara_de_cada_aparelho() -> None:
    """É O DEFEITO QUE ESTE ARQUIVO CURA, e ele era invisível."""
    vistas = _mesa({UNIQ_A: "dualsense"}, da_sessao="xbox")
    assert vistas[UNIQ_A] == "DualSense", vistas
    assert vistas[UNIQ_B] == "Xbox 360", vistas


def test_sem_por_aparelho_a_mesa_faz_o_que_fazia() -> None:
    """Um daemon velho não pode quebrar a tela."""
    assert set(_mesa({}, da_sessao="dualsense").values()) == {"DualSense"}


def test_o_rotulo_sai_do_dono_da_traducao() -> None:
    """A tela mostra o RÓTULO, e a tradução tem um dono só."""
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    for flavor, rotulo in NOME_DA_MASCARA.items():
        assert _mesa({UNIQ_A: flavor})[UNIQ_A] == rotulo


class _Ponte:
    """Anota o que o gesto mandaria ao daemon, sem mandar nada.

    A ASSINATURA É A DA PONTE DE VERDADE, e isso não é preciosismo — foi este
    dublê que deixou o defeito passar. `pacotes.ponte.chamar` é

        chamar(metodo, timeout=None, **params)  # (assinatura) noqa-acento

    e até 04/09 o dublê era `chamar(self, metodo, params)`  # (assinatura) noqa-acento
    O gesto da máscara passava `p.chamar("gamepad.mask.set", {...})` — o
    dicionário caía no `timeout` da ponte real e o `_safe_call` estourava com
    `'<=' not supported between instances of 'dict' and 'int'`. **Na ponte de
    mentira aquilo casava perfeitamente**, e a régua ficou VERDE sobre um gesto
    que nunca gravou um byte: medido com o daemon dela, `controller_masks.json`
    não existia antes nem depois do clique.

    Um dublê com assinatura mais frouxa que o original não é um dublê — é uma
    segunda API, que aceita o que a primeira recusa.
    """

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict]] = []

    def chamar(self, metodo: str, timeout: float | None = None, **p):  # (parâmetro) noqa-acento
        self.chamadas.append((metodo, p))

    def chamar_detalhado(self, metodo: str, **p) -> tuple[bool, str | None]:
        """A que o gesto da máscara usa desde 11/09/2026 — `(ok, motivo)`."""
        self.chamadas.append((metodo, p))
        return True, None


def _clicar(**o):
    from hefesto_dualsense4unix.interface import pacotes  # noqa: F401
    from hefesto_dualsense4unix.interface.pacotes import Contexto, a01_jogar

    p = _Ponte()
    ctx = Contexto(state={}, mesa=[], conectados=[], estados={})
    a01_jogar.mascara_do_controle(ctx, dict(o), p)
    return p.chamadas


def test_o_chip_grava_a_escolha_daquele_aparelho() -> None:
    """Clicar "Xbox 360" no cartão do P1 grava a máscara DELE."""
    assert _clicar(uniq=UNIQ_A, mascara="Xbox 360") == [
        ("gamepad.mask.set", {"uniq": UNIQ_A, "flavor": "xbox"})]


def test_o_chip_do_dualsense_tambem() -> None:
    """E o outro rótulo, pelo mesmo caminho."""
    assert _clicar(uniq=UNIQ_A, mascara="DualSense") == [
        ("gamepad.mask.set", {"uniq": UNIQ_A, "flavor": "dualsense"})]


def test_o_chip_sem_controle_recusa_dizendo() -> None:
    """Sem `uniq` não há a quem aplicar — e "todos" é o botão de cima."""
    with pytest.raises(RuntimeError, match="Não há controle no lugar P3"):
        _clicar(controle="p3", mascara="Xbox 360")
    with pytest.raises(ValueError, match="não disse em qual controle"):
        _clicar(mascara="Xbox 360")


def test_o_rotulo_sem_motor_recusa_dizendo_o_que_existe() -> None:
    """TRÊS CHIPS DESENHADOS, TRÊS MÁSCARAS DE VERDADE (desde 07/09/2026)."""
    with pytest.raises(RuntimeError, match=r"Wiimote.*não sabe montar"):
        _clicar(uniq=UNIQ_A, mascara="Wiimote")


def test_o_nintendo_pro_deixou_de_ser_recusado_e_chega_ao_daemon() -> None:
    """O outro lado do dia: o chip que era cinza agora escreve."""
    _clicar(uniq=UNIQ_A, mascara="Nintendo Pro")


def test_a_lista_do_que_existe_e_perguntada() -> None:
    """A frase da recusa nomeia as máscaras REAIS, lidas do dono.

    Digitar "DualSense e Xbox 360" na mensagem faria a frase envelhecer no dia
    em que uma terceira máscara nascesse — que é o dia em que alguém mais
    precisa dela.
    """
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascaras_validas
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    with pytest.raises(RuntimeError) as e:
        _clicar(uniq=UNIQ_A, mascara="Wiimote")
    for flavor in mascaras_validas():
        if flavor in NOME_DA_MASCARA:
            assert NOME_DA_MASCARA[flavor] in str(e.value)
