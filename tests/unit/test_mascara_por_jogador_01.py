"""MÁSCARA-POR-JOGADOR-01 — a máscara é do JOGADOR, o jogo é o padrão herdado.

Ela reescreveu em **15/08/2026** a frase de 10/08 que morava em
``profiles/schema.py`` (*"``mode`` e a máscara do gamepad são da SESSÃO, não da
peça"*): vale só para o ``mode``. A máscara passa a ser do jogador, com a do
jogo como padrão herdado (D-5 de 14/08). O diagnóstico inteiro está em
``docs/process/sprints/2026-08-15-MASCARA-POR-JOGADOR-01-*``.

Esta bateria vigia as **três** garantias que a decisão exige, e a quarta que ela
NÃO pode quebrar:

1. quem escolheu, manda — a máscara do aparelho vence a do jogo;
2. quem não escolheu, herda — e é por isso que ninguém precisa escolher;
3. a **cura da SPRINT-GAME-RUMBLE-01 sobrevive**: um vpad com máscara diferente
   *porque a jogadora escolheu* NÃO é derrubado; um vpad com máscara velha
   *porque ficou para trás* AINDA é (senão volta o `P2+ preso no flavor antigo,
   rumble morto`);
4. enquanto o último degrau não chega (a identidade não é passada na criação do
   vpad), o comportamento é **idêntico ao de antes** — meia cura não pode mudar
   comportamento.

Bancada espelhada de ``test_external_mask.py``: faixa forjada ``aa:bb:cc:00:00:*``
(regra da casa — nada de MAC real em arquivo versionado), ``config_dir`` em
``tmp_path``, nenhum aparelho, nenhum ``/dev/uinput``, nenhum ``/dev/uhid``,
nenhum GTK.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    ExternalMaskRegistry,
    _zerar_registro_de_mascaras,
    mascara_efetiva,
    registro_de_mascaras,
    vpad_ficou_para_tras,
)
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    DUALSENSE_EDGE_PRODUCT,
    DUALSENSE_VENDOR,
    XBOX360_PRODUCT,
    XBOX360_VENDOR,
    UinputGamepad,
)

#: Três jogadores da mesa, na faixa forjada da casa (octetos 4 e 5 zerados).
MAC_P1 = "aa:bb:cc:00:00:01"
MAC_P2 = "aa:bb:cc:00:00:02"
MAC_P3 = "aa:bb:cc:00:00:03"

#: Identidade VOLÁTIL — o 8BitDo/Pro degradado, que vale na sessão e não vai ao
#: disco. A máscara dele tem de funcionar igual **na sessão**.
IDENTIDADE_VOLATIL = "dev:0003:057E:2009.0001"

_SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` em tmp + registro do processo ZERADO antes e depois.

    O zerar não é higiene genérica: o registro guarda o disco em memória e só o
    lê uma vez (``_loaded``). Sem isto, o segundo teste herdaria as máscaras do
    primeiro e a bateria mediria a si mesma.
    """
    from hefesto_dualsense4unix.utils import xdg_paths

    target = tmp_path / "config"

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    _zerar_registro_de_mascaras()
    yield target
    _zerar_registro_de_mascaras()


# ===========================================================================
# 1 e 2 — quem escolheu manda; quem não escolheu herda
# ===========================================================================


def test_a_mascara_escolhida_do_jogador_vence_a_do_jogo() -> None:
    """A garantia 1. Sem ela, a D-5 não existe: a escolha dela seria enfeite."""
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    assert mascara_efetiva(MAC_P2, "xbox") == "dualsense"
    # E o contrário também, para o teste não passar por causa de um default:
    registro_de_mascaras().set_mask(MAC_P3, "xbox")
    assert mascara_efetiva(MAC_P3, "dualsense") == "xbox"


def test_sem_escolha_o_jogador_herda_a_mascara_do_jogo() -> None:
    """A garantia 2 — e é ela que torna o recurso seguro diante do risco não medido.

    Ninguém precisa escolher por jogador para o produto funcionar: sem entrada
    no registro, os quatro seguem a máscara do jogo, que é o valor de sempre.
    """
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    assert mascara_efetiva(MAC_P1, "xbox") == "xbox"
    assert mascara_efetiva(MAC_P1, "dualsense") == "dualsense"
    # Ninguém = identidade ausente também herda (o vpad que não sabe de quem é).
    assert mascara_efetiva(None, "dualsense") == "dualsense"


def test_a_mascara_do_externo_volatil_vale_na_sessao() -> None:
    """O 8BitDo/Pro degradado tem máscara também — a regra "universal" de 09/08.

    Identidade volátil não vai ao disco (CLONE-01), mas mandar na sessão ela
    manda: senão a mesa teria jogadores de segunda classe.
    """
    registro_de_mascaras().set_mask(IDENTIDADE_VOLATIL, "dualsense")
    assert mascara_efetiva(IDENTIDADE_VOLATIL, "xbox") == "dualsense"


def test_a_escolha_invalida_nao_vira_mascara_e_o_jogador_segue_herdando() -> None:
    """Lixo não escolhe máscara por ninguém (ESCOLHA-DELA-VENCE-01)."""
    assert registro_de_mascaras().set_mask(MAC_P2, "nintendo") is False
    assert mascara_efetiva(MAC_P2, "xbox") == "xbox"


# ===========================================================================
# 3 — a cura da SPRINT-GAME-RUMBLE-01 sobrevive
# ===========================================================================


def test_a_divergencia_escolhida_nao_derruba_o_vpad() -> None:
    """O P2 escolheu DualSense numa sessão Xbox: o vpad dele SOBREVIVE.

    Este é o lado novo. Hoje `coop.py`:417-424 derrubaria este vpad a cada tick
    — e o jogador ficaria num laço de nascer e morrer.
    """
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    assert vpad_ficou_para_tras("dualsense", MAC_P2, "xbox") is False


def test_o_flavor_que_ficou_para_tras_ainda_derruba_o_vpad() -> None:
    """O lado VELHO, que não pode morrer: senão volta `P2+ preso no flavor antigo`.

    Dois jeitos de ficar para trás, e os dois têm de continuar derrubando:
    a máscara do JOGO mudou (o jogador herda e o vpad não), e a máscara DELE
    mudou (o gesto novo dela ainda não chegou ao vpad).
    """
    # (a) o jogador não escolheu nada e a máscara do jogo virou dualsense:
    assert vpad_ficou_para_tras("xbox", MAC_P1, "dualsense") is True

    # (b) o jogador escolheu xbox e o vpad dele nasceu dualsense:
    registro_de_mascaras().set_mask(MAC_P2, "xbox")
    assert vpad_ficou_para_tras("dualsense", MAC_P2, "xbox") is True

    # (c) vpad sem flavor legível conta como para trás, como sempre contou:
    assert vpad_ficou_para_tras(None, MAC_P1, "xbox") is True


def test_a_mesa_heterogenea_derruba_so_quem_ficou_para_tras() -> None:
    """O laço do co-op inteiro, com quatro jogadores, numa asserção só.

    P1 herda xbox e está em xbox (fica). P2 escolheu dualsense e está em
    dualsense (fica — é a divergência ESCOLHIDA). P3 herda xbox e está preso em
    dualsense (cai). O externo volátil escolheu dualsense e está em xbox (cai).
    """
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")
    registro_de_mascaras().set_mask(IDENTIDADE_VOLATIL, "dualsense")
    mesa = {
        MAC_P1: "xbox",
        MAC_P2: "dualsense",
        MAC_P3: "dualsense",
        IDENTIDADE_VOLATIL: "xbox",
    }

    caem = {
        identidade
        for identidade, flavor in mesa.items()
        if vpad_ficou_para_tras(flavor, identidade, "xbox")
    }

    assert caem == {MAC_P3, IDENTIDADE_VOLATIL}


# ===========================================================================
# O registro do processo é UM — a peça que faltava
# ===========================================================================


def test_duas_instancias_do_registro_divergem_e_por_isso_existe_o_singleton() -> None:
    """A razão MEDIDA de :func:`registro_de_mascaras` — não é preguiça de injeção.

    Duas instâncias no mesmo processo respondem coisas diferentes para *"qual é
    a máscara deste controle?"*, porque cada uma lê o disco uma vez só. Com
    quem CRIA o vpad e quem COMPARA o vpad discordando, o sintoma é o vpad
    recriado em laço eterno.
    """
    escritora = ExternalMaskRegistry()
    leitora = ExternalMaskRegistry()
    leitora.load()  # leu o disco vazio e nunca mais relê

    escritora.set_mask(MAC_P2, "dualsense")

    assert escritora.mask_for(MAC_P2) == "dualsense"
    assert leitora.mask_for(MAC_P2) is None  # a divergência, medida

    # O registro do processo não tem como divergir de si mesmo:
    assert registro_de_mascaras() is registro_de_mascaras()
    registro_de_mascaras().set_mask(MAC_P3, "dualsense")
    assert mascara_efetiva(MAC_P3, "xbox") == "dualsense"


# ===========================================================================
# Os dois backends de vpad nascem com a máscara do jogador
# ===========================================================================


def test_o_vpad_uinput_nasce_com_a_mascara_do_jogador() -> None:
    """Não basta a função responder certo: o device tem de nascer com o VID/PID."""
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    pad = UinputGamepad.for_flavor("xbox", identity=MAC_P2)

    assert pad.flavor == "dualsense"
    assert (pad.vendor, pad.product) == (DUALSENSE_VENDOR, DUALSENSE_EDGE_PRODUCT)


def test_o_vpad_uinput_do_jogador_sem_escolha_segue_o_jogo() -> None:
    """O vizinho de mesa do teste acima não muda de máscara junto com ele."""
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    pad = UinputGamepad.for_flavor("xbox", identity=MAC_P1)

    assert pad.flavor == "xbox"
    assert (pad.vendor, pad.product) == (XBOX360_VENDOR, XBOX360_PRODUCT)


def test_o_uhid_recusa_o_jogador_que_escolheu_xbox() -> None:
    """`xbox` no uhid é `None` = "use o UinputGamepad" — agora POR JOGADOR.

    Sem isto, um jogador marcado como Xbox numa sessão DualSense ganharia um
    DualSense Edge HID de verdade no kernel: a máscara OPOSTA à pedida.
    """
    registro_de_mascaras().set_mask(MAC_P2, "xbox")

    assert UhidDualSense.for_flavor("dualsense", player=2, identity=MAC_P2) is None


def test_o_uhid_aceita_o_jogador_que_escolheu_dualsense_numa_sessao_xbox() -> None:
    """O outro lado da mesma moeda — e é o que dá hidraw (logo, rumble) a ele."""
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    pad = UhidDualSense.for_flavor("xbox", player=2, identity=MAC_P2)

    assert pad is not None
    assert pad.flavor == "dualsense"


# ===========================================================================
# 4 — enquanto o último degrau não chega, NADA muda
# ===========================================================================


def test_sem_identidade_o_vpad_se_comporta_exatamente_como_antes() -> None:
    """A prova de que esta leva não muda comportamento nenhum hoje.

    Com máscaras gravadas para a mesa inteira, um chamador que não passa
    identidade continua recebendo a máscara do JOGO — nos dois backends, e
    inclusive na regra do `None` do uhid (*"sem preferência" = dualsense*).
    """
    registro_de_mascaras().set_mask(MAC_P1, "dualsense")
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    assert UinputGamepad.for_flavor("xbox").flavor == "xbox"
    assert UinputGamepad.for_flavor("dualsense").flavor == "dualsense"
    assert UhidDualSense.for_flavor("xbox", player=1) is None
    assert UhidDualSense.for_flavor(None, player=1) is not None


# ===========================================================================
# A frase dela, reescrita — e que não pode voltar a ser larga
# ===========================================================================


def test_a_frase_de_10_08_vale_so_para_o_mode() -> None:
    """A decisão de 15/08 mora no esquema, não só no documento.

    O esquema é o que a próxima pessoa lê quando pergunta *"por que a máscara
    não é um campo daqui?"*. Enquanto a frase antiga estiver ali, ela responde
    a pergunta ERRADA — e foi ela que segurou o `ExternalMaskRegistry` desligado
    por oito dias.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    doc = ControllerOverrides.__doc__ or ""

    assert "e a máscara do gamepad são da SESSÃO" not in doc, (
        "a frase de 10/08 voltou a valer para a máscara. Ela a reescreveu em "
        "15/08/2026: vale só para o `mode`."
    )
    assert "``mode`` é da SESSÃO" in doc
    assert "15/08/2026" in doc, "decisão reescrita sem data não se sustenta"
    # E a pergunta seguinte — "então onde a máscara mora?" — tem de estar
    # respondida no mesmo lugar, senão a nota só abre um buraco novo.
    assert "external_mask.py" in doc


def _chama_make_virtual_pad_com_identidade(modulo: Path) -> bool:
    """``make_virtual_pad(...)`` deste módulo passa ``identity=``?

    Por AST, e não por ``grep``: ``coop.py`` tem dezenas de ``identity=`` em
    chamadas de log, e um grep de texto daria por ligado o degrau que falta —
    exatamente o erro que o portão da casa existe para não repetir.
    """
    arvore = ast.parse(modulo.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        nome = alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", "")
        if nome != "make_virtual_pad":
            continue
        if any(kw.arg == "identity" for kw in no.keywords):
            return True
    return False


@pytest.mark.xfail(
    strict=True,
    reason=(
        "MEDIDO em 15/08/2026: o último degrau da máscara por jogador NÃO "
        "chegou. `coop.py` e `gamepad.py` chamam `make_virtual_pad` sem "
        "`identity=`, e `make_virtual_pad` nem aceita o parâmetro — os três "
        "arquivos estavam fora do território desta leva (`coop.py` sob edição "
        "de outra frente no mesmo dia). Quando o degrau chegar, este teste "
        "PASSA e o `strict=True` o reprova: APAGUE o marcador. Ver a lápide de "
        "`::vpad_ficou_para_tras` no portão `a casa sabe e o produto não faz`."
    ),
)
def test_o_ultimo_degrau_da_mascara_por_jogador_chegou() -> None:
    """Lápide viva: falha hoje de propósito, e reprova no dia em que curar."""
    assert _chama_make_virtual_pad_com_identidade(
        _SRC / "daemon" / "subsystems" / "coop.py"
    ), "coop.py não passa a identidade do jogador ao criar o vpad"
    assert _chama_make_virtual_pad_com_identidade(
        _SRC / "daemon" / "subsystems" / "gamepad.py"
    ), "gamepad.py não passa a identidade do primário ao criar o vpad"
