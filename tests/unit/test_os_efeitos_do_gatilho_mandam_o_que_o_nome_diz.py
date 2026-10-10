"""A régua dos efeitos do gatilho: o bloco lido como o CONTROLE o lê.

Os outros testes do gatilho travam o que o código MONTA (o modo, os bytes que
o usuário aprovou em 01/08). Nenhum pergunta o que o aparelho FAZ com o bloco, e os
nomes herdados de 2020 (`PULSE_A = 0x22`, `PULSE_B = 0x06`, `PULSE_AB = 0x26`)
escondem que o mesmo byte de modo é, no firmware, o arco, a vibração simples e
a vibração oficial: um efeito montado no layout errado passa em todo teste.

O decodificador abaixo nasce da REGRA, o fato público de qual byte é o quê em
cada modo (`docs/protocol/dualsense-referencia-canonica.md`, «O empacotamento
dos 11 bytes»); não copia código de ninguém.

    byte 0     modo
    0x21/0x26  [1,2] zonas ativas u16 ; [3..6] amplitude u32 (3 bits por zona,
               valor guardado = força - 1) ; 0x26 ainda leva a frequência no [9]
    0x25       [1,2] (1<<início)|(1<<fim) ; [3] força - 1
    0x22       [1,2] (1<<início)|(1<<fim) ; [3,4] (força-1) | (estalo-1)<<3
    0x23       [1,2] zonas ; [3] segundo pé | primeiro pé<<3 ; [4] frequência
    0x27       [1,2] zonas ; [3] ampA | ampB<<3 ; [4] frequência ; [5] período
    0x06       [1] frequência ; [2] amplitude ; [3] posição (curso de 0 a 147)
    0x02       a arma simples, sem parâmetro
    0x00, 0x05 desligado

Só valem os bits 0 a 9 da máscara: o curso tem dez zonas.

A TABELA DE ISENÇÃO diz o que ainda está errado hoje, efeito por efeito, e com
o ID da sprint que o cura. Ela só encolhe: uma isenção cujo efeito já saiu certo
reprova (a linha velha se apaga), e um efeito FORA da tabela que falhe reprova.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS
from hefesto_dualsense4unix.core.controller import TriggerEffect
from hefesto_dualsense4unix.core.trigger_effects import (
    PRESET_FACTORIES,
    _arco_do_firmware,
    build_from_name,
    custom,
)
from hefesto_dualsense4unix.profiles.trigger_presets import VIBRATION_POSITION_PRESETS

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP_GATILHOS = RAIZ / "mockup" / "03-gatilhos.html"

ZONAS_DO_CURSO = 10
CURSO_DO_0X06 = 147

_MODOS_COM_MASCARA = (0x21, 0x22, 0x23, 0x25, 0x26, 0x27)
_MODOS_DESLIGADOS = (0x00, 0x05)
_MODOS_DA_REGUA = (
    *_MODOS_COM_MASCARA, 0x06, 0x02, *_MODOS_DESLIGADOS,
)


def bloco_de(efeito: TriggerEffect) -> bytes:
    """O bloco de 11 bytes como o relatório o monta (`common[10:21]`).

    O modo no byte 0, as forças 0 a 5 nos bytes 1 a 6 e a sétima no byte 9
    (`backend_pydualsense.py`, o laço dos dois gatilhos).
    """
    f = efeito.forces
    return bytes([efeito.mode, f[0], f[1], f[2], f[3], f[4], f[5], 0, 0, f[6], 0])


@dataclass(frozen=True)
class Lido:
    """O que o controle entende de um bloco."""

    modo: int
    mascara: int = 0
    amplitude_bruta: int = 0
    frequencia: int | None = None
    periodo: int | None = None
    posicao: int | None = None
    #: força (1 a 8) de cada zona ativa, nos modos que a guardam por zona
    forca_por_zona: dict[int, int] = field(default_factory=dict)

    @property
    def zonas(self) -> tuple[int, ...]:
        """As zonas ativas dentro do curso (bits 0 a 9, e só eles)."""
        return tuple(z for z in range(ZONAS_DO_CURSO) if self.mascara >> z & 1)


def decodificar(bloco: bytes) -> Lido:
    """Lê um bloco de 11 bytes pela regra do firmware; modo fora da lista reprova."""
    assert len(bloco) == 11, f"o bloco tem 11 bytes, não {len(bloco)}"
    modo = bloco[0]
    if modo in _MODOS_DESLIGADOS or modo == 0x02:
        return Lido(modo=modo)
    if modo == 0x06:
        return Lido(modo=modo, frequencia=bloco[1], amplitude_bruta=bloco[2], posicao=bloco[3])
    if modo not in _MODOS_COM_MASCARA:
        raise AssertionError(
            f"modo 0x{modo:02X} fora da régua (só o Custom manda o que a pessoa digita)"
        )
    mascara = bloco[1] | bloco[2] << 8
    if modo in (0x21, 0x26):
        bruto = int.from_bytes(bloco[3:7], "little")
        zonas = [z for z in range(ZONAS_DO_CURSO) if mascara >> z & 1]
        return Lido(
            modo=modo,
            mascara=mascara,
            amplitude_bruta=bruto,
            frequencia=bloco[9] if modo == 0x26 else None,
            forca_por_zona={z: (bruto >> (3 * z) & 0x07) + 1 for z in zonas},
        )
    if modo == 0x23:
        return Lido(modo=modo, mascara=mascara, amplitude_bruta=bloco[3], frequencia=bloco[4])
    if modo == 0x27:
        return Lido(
            modo=modo,
            mascara=mascara,
            amplitude_bruta=bloco[3],
            frequencia=bloco[4],
            periodo=bloco[5],
        )
    # 0x22 (arco) e 0x25 (arma): início e fim viram bits, a força vem do byte 3
    return Lido(modo=modo, mascara=mascara, amplitude_bruta=bloco[3] | bloco[4] << 8)


# --- as regras: cada uma devolve o NOME da regra quebrada, ou nada ------------

BIT_FORA_DO_CURSO = "bit_de_zona_fora_do_curso"
SEM_ZONA_ATIVA = "efeito_sem_zona_ativa"
FORCA_EM_ZONA_INATIVA = "forca_em_zona_inativa"
POSICAO_FORA_DO_CURSO = "posicao_fora_do_curso"
MACHINE_SEM_INICIO = "machine_com_inicio_fora_de_1_a_8"
REPETE_SEM_FREQUENCIA = "promete_repeticao_e_manda_frequencia_zero"
FIRMEZA_SEM_O_FUNDO = "firmeza_que_nao_chega_ao_fundo"
ARMA_SEM_DOIS_PONTOS = "arma_ou_arco_sem_inicio_e_fim_na_mascara"
VALOR_FORA_DOS_BITS = "valor_que_passa_dos_bits_do_modo"
PONTO_FORA_DO_DOMINIO = "inicio_ou_fim_fora_do_dominio_do_modo"
PATAS_FORA_DE_ORDEM = "galope_com_a_primeira_pata_depois_da_segunda"

#: O domínio do início e do fim de cada modo de dois pontos, no gerador do
#: Nielk1: a arma, início de 2 a 7 e fim até 8; o arco, fim até 8 (a zona 9
#: é do galope, que vai até ela).
DOMINIO_DOS_PONTOS = {0x25: (2, 7, 8), 0x22: (0, 7, 8)}

#: Quantos bits o campo de valor de cada modo tem: a arma, três (força - 1); o
#: arco, seis (força - 1 e estalo - 1); o galope, seis (as duas patas).
BITS_DO_VALOR = {0x25: 3, 0x22: 6, 0x23: 6}


def violacoes(
    lido: Lido, *, repete: bool = False, segue_ate_o_fundo: bool = False
) -> frozenset[str]:
    """As regras que o bloco quebra, lido como o controle o lê."""
    achadas: set[str] = set()
    if lido.modo in _MODOS_COM_MASCARA:
        if lido.mascara >> ZONAS_DO_CURSO:
            achadas.add(BIT_FORA_DO_CURSO)
        if not lido.zonas:
            achadas.add(SEM_ZONA_ATIVA)
        if lido.modo in (0x21, 0x26):
            inativas = lido.amplitude_bruta
            for z in lido.zonas:
                inativas &= ~(0x07 << (3 * z))
            if inativas:
                achadas.add(FORCA_EM_ZONA_INATIVA)
    if lido.modo in (0x25, 0x22) and len(lido.zonas) != 2:
        achadas.add(ARMA_SEM_DOIS_PONTOS)
    if lido.modo in BITS_DO_VALOR and lido.amplitude_bruta >> BITS_DO_VALOR[lido.modo]:
        achadas.add(VALOR_FORA_DOS_BITS)
    if lido.modo in DOMINIO_DOS_PONTOS and len(lido.zonas) == 2:
        menor, maior_inicio, maior_fim = DOMINIO_DOS_PONTOS[lido.modo]
        inicio, fim = lido.zonas
        if not (menor <= inicio <= maior_inicio and fim <= maior_fim):
            achadas.add(PONTO_FORA_DO_DOMINIO)
    if lido.modo == 0x23:
        # o byte 3 leva a segunda pata nos bits 0-2 e a primeira nos bits 3-5;
        # a primeira vai de 0 a 6 e a segunda vem depois dela, até 7
        primeira, segunda = lido.amplitude_bruta >> 3 & 0x07, lido.amplitude_bruta & 0x07
        if primeira >= segunda:
            achadas.add(PATAS_FORA_DE_ORDEM)
    if lido.modo == 0x06 and (lido.posicao or 0) > CURSO_DO_0X06:
        achadas.add(POSICAO_FORA_DO_CURSO)
    if lido.modo == 0x27 and not (lido.zonas and 1 <= lido.zonas[0] <= 8):
        achadas.add(MACHINE_SEM_INICIO)
    if repete and not lido.frequencia:
        achadas.add(REPETE_SEM_FREQUENCIA)
    if segue_ate_o_fundo and lido.modo != 0x00 and lido.mascara and (
        ZONAS_DO_CURSO - 1 not in lido.zonas
    ):
        achadas.add(FIRMEZA_SEM_O_FUNDO)
    return frozenset(achadas)


# --- os efeitos, com os padrões da tela ---------------------------------------

_SPEC_POR_NOME = {p.name: p for p in PRESETS}

#: Fora da régua: o Montar do zero manda o que a pessoa digitar.
FORA_DA_REGUA = frozenset({"Custom"})

#: O efeito que carrega uma firmeza que, uma vez começada, vai até o fundo do curso.
SEGUEM_ATE_O_FUNDO = frozenset(
    {"Rigid", "SimpleRigid", "Resistance", "Feedback", "SlopeFeedback"}
)

#: Os efeitos cuja palavra, na tela, é repetição: o gatilho tem de bater.
REPETEM = frozenset(
    {"Galloping", "AutoGun", "Machine", "Vibration", "MultiPositionVibration"}
)

#: O perfil salvo da Vibração por posição em lista de listas (`[[v], …]`), o
#: formato aninhado que a aba antiga gravava. É um caso à parte da mesma fábrica.
VIBRACAO_ANINHADA = "MultiPositionVibration (perfil em lista de listas)"


def _efeito_com_os_padroes(nome: str) -> TriggerEffect:
    """O preset como a tela do usuário o aplica: com o padrão de cada controle."""
    return build_from_name(nome, [p.default for p in _SPEC_POR_NOME[nome].params])


def _efeito_aninhado() -> TriggerEffect:
    forcas = VIBRATION_POSITION_PRESETS["machine_gun"]
    return build_from_name("MultiPositionVibration", [[v] for v in forcas])


def _nomes_dos_casos() -> list[str]:
    """Os casos da régua: cada fábrica menos as de fora, mais o perfil aninhado.

    Só os NOMES: o efeito nasce dentro do teste, para uma fábrica que passe a
    recusar os padrões reprovar o caso dela e não a coleta inteira.
    """
    nomes = [nome for nome in PRESET_FACTORIES if nome not in FORA_DA_REGUA]
    return [*nomes, VIBRACAO_ANINHADA]


def _efeito_do_caso(caso: str) -> TriggerEffect:
    if caso == VIBRACAO_ANINHADA:
        return _efeito_aninhado()
    return _efeito_com_os_padroes(caso)


def _nome_da_fabrica(caso: str) -> str:
    return "MultiPositionVibration" if caso == VIBRACAO_ANINHADA else caso


def _violacoes_do_caso(caso: str) -> frozenset[str]:
    nome = _nome_da_fabrica(caso)
    return violacoes(
        decodificar(bloco_de(_efeito_do_caso(caso))),
        repete=nome in REPETEM,
        segue_ate_o_fundo=nome in SEGUEM_ATE_O_FUNDO,
    )


#: efeito -> (a sprint que o cura, as regras que ele ainda quebra). Só encolhe.
_METRALHADORA = "A-METRALHADORA-BATE-ENQUANTO-O-DEDO-APERTA-01"
_DISPARO = "O-DISPARO-E-A-ARMA-SEMI-AUTOMATICA-MANDAM-O-MODO-DE-ARMA-01"
_ARCO = "O-ARCO-E-O-GALOPE-MANDAM-O-MODO-QUE-O-CONTROLE-LE-01"

ISENCOES: dict[str, tuple[str, frozenset[str]]] = {
    # a Arma automática e a Vibração (a Metralhadora saiu em 08/10/2026)
    # sai com: A-METRALHADORA-BATE-ENQUANTO-O-DEDO-APERTA-01
    "AutoGun": (_METRALHADORA, frozenset({
        BIT_FORA_DO_CURSO, FORCA_EM_ZONA_INATIVA, REPETE_SEM_FREQUENCIA,
    })),
    # sai com: A-METRALHADORA-BATE-ENQUANTO-O-DEDO-APERTA-01
    "Vibration": (_METRALHADORA, frozenset({
        BIT_FORA_DO_CURSO, REPETE_SEM_FREQUENCIA,
    })),
    # O Disparo, o Pulso (curva B) e o Pulso (curva A) saíram desta tabela em
    # 08/10/2026 (arma `0x25` e arco `0x22` no layout do modo). Os três de baixo
    # têm a sensação que a mão do usuário aprovou em 01/08 e ficam como estão até a
    # sessão às cegas: os bytes só mudam se ela escolher o modo próprio.
    # sai com: O-DISPARO-E-A-ARMA-SEMI-AUTOMATICA-MANDAM-O-MODO-DE-ARMA-01
    "SemiAutoGun": (_DISPARO, frozenset({BIT_FORA_DO_CURSO, FORCA_EM_ZONA_INATIVA})),
    # sai com: O-ARCO-E-O-GALOPE-MANDAM-O-MODO-QUE-O-CONTROLE-LE-01
    "Bow": (_ARCO, frozenset({BIT_FORA_DO_CURSO, FORCA_EM_ZONA_INATIVA})),
    # sai com: O-ARCO-E-O-GALOPE-MANDAM-O-MODO-QUE-O-CONTROLE-LE-01
    "Galloping": (_ARCO, frozenset({
        BIT_FORA_DO_CURSO, FORCA_EM_ZONA_INATIVA, REPETE_SEM_FREQUENCIA,
    })),
}


# --- a tabela de isenção: o que ainda está errado, e quem cura -----------------


def test_todo_efeito_da_fabrica_passa_pela_regua_menos_o_montar_do_zero() -> None:
    assert set(PRESET_FACTORIES) >= FORA_DA_REGUA
    assert len(_nomes_dos_casos()) == len(PRESET_FACTORIES) - len(FORA_DA_REGUA) + 1
    for nome in PRESET_FACTORIES:
        assert nome in _SPEC_POR_NOME, f"{nome} sem controles na tela"


@pytest.mark.parametrize("caso", sorted(_nomes_dos_casos()))
def test_o_efeito_manda_o_que_o_nome_diz_ou_esta_na_tabela(caso: str) -> None:
    quebradas = _violacoes_do_caso(caso)
    if caso not in ISENCOES:
        assert not quebradas, (
            f"{caso} manda um bloco que o controle lê errado ({sorted(quebradas)}) "
            "e não está na tabela de isenção"
        )
        return
    sprint, declaradas = ISENCOES[caso]
    assert quebradas, (
        f"{caso} já sai certo: apague a linha da tabela (era a cura de {sprint})"
    )
    assert quebradas == declaradas, (
        f"{caso} quebra {sorted(quebradas)}, e a tabela diz {sorted(declaradas)} "
        f"(sprint {sprint}): acerte a linha"
    )


def test_a_tabela_de_isencao_so_cita_efeito_que_existe() -> None:
    assert set(ISENCOES) <= set(_nomes_dos_casos())


# --- o decodificador, com fixtures sintéticas ---------------------------------


def _hex(texto: str) -> bytes:
    return bytes.fromhex(texto)


class TestDecodificador:
    def test_vibracao_oficial_lida_com_frequencia_no_byte_9(self) -> None:
        lido = decodificar(_hex("26 FC 03 C0 B6 6D 1B 00 00 28 00"))
        assert lido.modo == 0x26
        assert lido.zonas == (2, 3, 4, 5, 6, 7, 8, 9)
        assert lido.frequencia == 40
        assert set(lido.forca_por_zona.values()) == {4}
        assert violacoes(lido, repete=True) == frozenset()

    def test_vibracao_oficial_le_a_forca_de_cada_zona_menos_um(self) -> None:
        # as dez forças 0,1,2,…,7,8,8 do preset «rampa crescente»: zona z = força z
        lido = decodificar(_hex("26 FE 03 40 34 D6 3F 00 00 64 00"))
        assert lido.forca_por_zona == {z: z for z in range(1, 9)} | {9: 8}
        assert lido.frequencia == 100

    def test_machine_lida_com_frequencia_no_byte_4_e_periodo_no_5(self) -> None:
        lido = decodificar(_hex("27 02 02 1B 32 08 00 00 00 00 00"))
        assert lido.modo == 0x27
        assert lido.zonas == (1, 9)
        assert lido.frequencia == 50
        assert lido.periodo == 8
        assert violacoes(lido, repete=True) == frozenset()

    def test_machine_com_inicio_zero_e_denunciada(self) -> None:
        lido = decodificar(_hex("27 01 02 1B 32 08 00 00 00 00 00"))
        assert MACHINE_SEM_INICIO in violacoes(lido)

    def test_machine_com_inicio_um_nao_e_denunciada(self) -> None:
        lido = decodificar(_hex("27 02 02 1B 32 08 00 00 00 00 00"))
        assert MACHINE_SEM_INICIO not in violacoes(lido)

    def test_vibracao_simples_le_a_frequencia_no_byte_1_e_a_posicao_no_3(self) -> None:
        lido = decodificar(_hex("06 28 05 40 00 00 00 00 00 00 00"))
        assert (lido.frequencia, lido.amplitude_bruta, lido.posicao) == (40, 5, 0x40)
        assert violacoes(lido) == frozenset()

    def test_posicao_do_0x06_passa_do_curso_aos_148(self) -> None:
        assert violacoes(decodificar(_hex("06 02 05 93 00 00 00 00 00 00 00"))) == frozenset()
        passou = decodificar(_hex("06 02 05 94 00 00 00 00 00 00 00"))
        assert violacoes(passou) == {POSICAO_FORA_DO_CURSO}

    def test_o_arco_com_o_mesmo_byte_de_zona_nao_tem_frequencia(self) -> None:
        lido = decodificar(_hex("22 02 02 1B 00 00 00 00 00 00 00"))
        assert lido.modo == 0x22
        assert lido.zonas == (1, 9)
        assert lido.frequencia is None
        assert REPETE_SEM_FREQUENCIA in violacoes(lido, repete=True)

    def test_o_galope_le_a_frequencia_no_byte_4(self) -> None:
        lido = decodificar(_hex("23 01 02 37 0A 00 00 00 00 00 00"))
        assert lido.zonas == (0, 9)
        assert lido.frequencia == 10
        assert violacoes(lido, repete=True) == frozenset()

    def test_o_galope_com_as_patas_iguais_ou_trocadas_e_denunciado(self) -> None:
        """As patas 7 e 7 (`0x3F`) não cabem: a primeira vai até 6, antes da segunda."""
        for byte3 in ("3F", "3E", "00"):
            lido = decodificar(_hex(f"23 01 02 {byte3} 0A 00 00 00 00 00 00"))
            assert violacoes(lido, repete=True) == {PATAS_FORA_DE_ORDEM}, byte3

    def test_a_arma_e_o_arco_fora_do_dominio_dos_pontos_sao_denunciados(self) -> None:
        # arma com início 1, arma com fim 9, arco com fim 9
        for bloco in ("25 82 00 05", "25 04 02 05", "22 01 02 2D"):
            lido = decodificar(_hex(bloco + " 00 00 00 00 00 00 00"))
            assert violacoes(lido) == {PONTO_FORA_DO_DOMINIO}, bloco
        for bloco in ("25 04 01 05", "22 01 01 2D", "22 80 01 2D"):
            lido = decodificar(_hex(bloco + " 00 00 00 00 00 00 00"))
            assert violacoes(lido) == frozenset(), bloco

    def test_a_arma_le_a_forca_menos_um_no_byte_3(self) -> None:
        lido = decodificar(_hex("25 24 00 05 00 00 00 00 00 00 00"))
        assert lido.modo == 0x25
        assert lido.zonas == (2, 5)
        assert lido.amplitude_bruta == 5
        assert violacoes(lido) == frozenset()

    def test_arma_ou_arco_com_um_ponto_so_ou_tres_e_denunciado(self) -> None:
        um = decodificar(_hex("25 04 00 05 00 00 00 00 00 00 00"))
        tres = decodificar(_hex("22 8C 00 2D 00 00 00 00 00 00 00"))
        assert violacoes(um) == {ARMA_SEM_DOIS_PONTOS}
        assert violacoes(tres) == {ARMA_SEM_DOIS_PONTOS}

    def test_a_arma_com_a_forca_fora_dos_tres_bits_e_denunciada(self) -> None:
        passou = decodificar(_hex("25 24 00 08 00 00 00 00 00 00 00"))
        assert violacoes(passou) == {VALOR_FORA_DOS_BITS}

    def test_o_arco_e_o_galope_com_valor_fora_dos_seis_bits_sao_denunciados(self) -> None:
        arco = decodificar(_hex("22 84 00 40 00 00 00 00 00 00 00"))
        galope = decodificar(_hex("23 01 02 77 0A 00 00 00 00 00 00"))
        assert violacoes(arco) == {VALOR_FORA_DOS_BITS}
        assert violacoes(galope, repete=True) == {VALOR_FORA_DOS_BITS}

    def test_desligados_e_arma_simples_nao_quebram_nada(self) -> None:
        for modo in (0x00, 0x05, 0x02):
            assert violacoes(decodificar(bytes([modo]) + bytes(10))) == frozenset()

    def test_bit_de_zona_fora_do_curso_e_denunciado(self) -> None:
        # a máscara 0x0702 liga o bit 10, que o curso de dez zonas não tem
        # o bloco antigo do Pulso (curva A), com os parâmetros em ordem
        lido = decodificar(_hex("22 02 07 B4 00 00 00 00 00 00 00"))
        assert lido.zonas == (1, 8, 9)
        assert violacoes(lido) == {
            BIT_FORA_DO_CURSO, ARMA_SEM_DOIS_PONTOS, VALOR_FORA_DOS_BITS,
        }
        # e a zona 12 também
        assert BIT_FORA_DO_CURSO in violacoes(
            decodificar(_hex("21 00 10 00 00 00 00 00 00 00 00"))
        )

    def test_efeito_sem_zona_ativa_e_denunciado(self) -> None:
        assert SEM_ZONA_ATIVA in violacoes(decodificar(_hex("21 00 00 00 00 00 00 00 00 00 00")))

    def test_forca_em_zona_inativa_e_denunciada(self) -> None:
        # a zona 0 está ativa; a força da zona 1 (bits 3 a 5) não tem zona que a use
        lido = decodificar(_hex("21 01 00 08 00 00 00 00 00 00 00"))
        assert violacoes(lido) == {FORCA_EM_ZONA_INATIVA}

    def test_firmeza_que_para_antes_do_fundo_e_denunciada(self) -> None:
        sem_fundo = decodificar(_hex("21 FE 01 00 00 00 00 00 00 00 00"))
        assert violacoes(sem_fundo, segue_ate_o_fundo=True) == {FIRMEZA_SEM_O_FUNDO}
        com_fundo = decodificar(_hex("21 FE 03 00 00 00 00 00 00 00 00"))
        assert violacoes(com_fundo, segue_ate_o_fundo=True) == frozenset()

    def test_modo_fora_da_lista_reprova(self) -> None:
        with pytest.raises(AssertionError, match="fora da régua"):
            decodificar(_hex("3C 00 00 00 00 00 00 00 00 00 00"))

    def test_bloco_de_monta_o_layout_do_relatorio(self) -> None:
        efeito = TriggerEffect(mode=0x26, forces=(1, 2, 3, 4, 5, 6, 7))
        assert bloco_de(efeito) == bytes([0x26, 1, 2, 3, 4, 5, 6, 0, 0, 7, 0])


def _bloco_do_relatorio(efeito: TriggerEffect) -> bytes:
    """O bloco do gatilho direito como o backend o escreve no relatório."""
    from pydualsense.enums import ConnectionType
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    from hefesto_dualsense4unix.core import backend_pydualsense as bp

    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.leftMotor = 0
    inst.rightMotor = 0
    inst.light = DSLight()
    inst.audio = DSAudio()
    inst.triggerL = DSTrigger()
    inst.triggerR = DSTrigger()
    inst.conType = ConnectionType.USB
    inst._suppress_leds = True
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._bt_seq = 0
    inst._raw_trigger_right = None
    inst._raw_trigger_left = None
    bp.PyDualSenseController._apply_trigger(inst, "right", efeito)
    return bytes(inst._build_common(rumble_asserted=False)[10:21])


@pytest.mark.parametrize("caso", sorted(_nomes_dos_casos()))
def test_a_regua_le_o_bloco_que_o_relatorio_manda(caso: str) -> None:
    """O `bloco_de` da régua é o que o backend põe no relatório, efeito a efeito.

    Sem isto a régua leria a própria cópia do layout, e um backend que mudasse
    de lugar um byte passaria nela.

    Mordida: pôr a sétima força no byte 4 do `bloco_de`.
    """
    efeito = _efeito_do_caso(caso)
    assert bloco_de(efeito) == _bloco_do_relatorio(efeito)


# --- os blocos da sessão às cegas: o que ela digita no Montar do zero ---------

#: O modo próprio de cada efeito de 01/08 que a sessão às cegas compara com o
#: bloco de hoje (`docs/process/sprints/*-O-DISPARO-E-A-ARMA-*` e
#: `*-O-ARCO-E-O-GALOPE-*`), com os padrões da tela: modo e as sete forças como
#: o Montar do zero as recebe. A régua os lê como o controle lê; o byte errado
#: no roteiro, digitado por ela, não vai ao gatilho.
BLOCOS_DA_SESSAO_AS_CEGAS: dict[str, tuple[int, tuple[int, ...]]] = {
    "SemiAutoGun (arma 0x25)": (0x25, (0x48, 0x00, 0x04, 0, 0, 0, 0)),
    "Bow (arco 0x22)": (0x22, (0x82, 0x00, 0x35, 0, 0, 0, 0)),
    "Galloping (galope 0x23)": (0x23, (0x01, 0x02, 0x37, 0x0A, 0, 0, 0)),
    "PulseB (vibração simples 0x06)": (0x06, (40, 5, 70, 0, 0, 0, 0)),
}


@pytest.mark.parametrize("nome", sorted(BLOCOS_DA_SESSAO_AS_CEGAS))
def test_os_blocos_do_roteiro_das_cegas_passam_pela_regua(nome: str) -> None:
    """Mordida: pôr o bit do fim do galope fora do curso (`0x04` no byte 2)."""
    modo, forces = BLOCOS_DA_SESSAO_AS_CEGAS[nome]
    efeito = custom(modo, forces)
    assert violacoes(
        decodificar(bloco_de(efeito)), repete=modo == 0x23
    ) == frozenset(), nome


def test_os_blocos_do_roteiro_sao_os_dos_padroes_da_tela_no_modo_proprio() -> None:
    """O roteiro não inventa byte: a arma da Semi-automática é a do Disparo com
    os padrões dela, e o arco e o galope têm os valores da tela."""
    semi = _SPEC_POR_NOME["SemiAutoGun"]
    inicio, fim, forca = (p.default for p in semi.params)
    assert BLOCOS_DA_SESSAO_AS_CEGAS["SemiAutoGun (arma 0x25)"] == (
        0x25,
        build_from_name("Weapon", [inicio, fim, round(forca / 8 * 255)]).forces,
    )
    arco = [p.default for p in _SPEC_POR_NOME["Bow"].params]
    assert BLOCOS_DA_SESSAO_AS_CEGAS["Bow (arco 0x22)"] == (
        0x22, _arco_do_firmware(*arco).forces,
    )
    inicio, fim, pata1, pata2, frequencia = (
        p.default for p in _SPEC_POR_NOME["Galloping"].params
    )
    # as patas da tela encostam no domínio do galope: a primeira até 6, a
    # segunda depois dela
    pata1 = min(pata1, 6)
    pata2 = max(pata1 + 1, min(pata2, 7))
    mascara = (1 << inicio) | (1 << fim)
    assert BLOCOS_DA_SESSAO_AS_CEGAS["Galloping (galope 0x23)"] == (
        0x23,
        (mascara & 0xFF, mascara >> 8, pata2 | pata1 << 3, frequencia, 0, 0, 0),
    )


# --- o curso inteiro da tela, não só os padrões --------------------------------

#: Os efeitos de dois pontos curados em 08/10/2026: a tela deixa início e fim
#: de 0 a 9, e o bloco tem de caber no domínio do modo em toda combinação.
DOIS_PONTOS_CURADOS = ("Weapon", "PulseA", "PulseB")


@pytest.mark.parametrize("nome", DOIS_PONTOS_CURADOS)
def test_todo_inicio_e_fim_da_tela_cabe_no_modo(nome: str) -> None:
    """Mordida: o fim do arco até 9 (a zona 9 não é do arco) reprova o PulseA."""
    inicio_spec, fim_spec, forca_spec = _SPEC_POR_NOME[nome].params
    for inicio in range(inicio_spec.min_value, inicio_spec.max_value + 1):
        for fim in range(max(inicio + 1, fim_spec.min_value), fim_spec.max_value + 1):
            for forca in (forca_spec.min_value + 1, 64, 128, forca_spec.max_value):
                efeito = build_from_name(nome, [inicio, fim, forca])
                assert violacoes(decodificar(bloco_de(efeito))) == frozenset(), (
                    nome, inicio, fim, forca,
                )


# --- a promessa da tela: quem diz «enquanto apertado» tem de bater ------------

_PROMETE = re.compile(r"enquanto|contínu|continu", re.IGNORECASE)


def _promessas_da_tela() -> set[str]:
    """Os efeitos cuja descrição, na tela ou no desenho, promete repetição."""
    prometem = {p.name for p in PRESETS if _PROMETE.search(p.description)}
    html = MOCKUP_GATILHOS.read_text(encoding="utf-8")
    opcoes = re.findall(r'<option value="([A-Za-z]+)"[^>]*? title="([^"]*)"', html)
    assert len(opcoes) >= 10, "o desenho perdeu as opções do seletor de modo"
    prometem |= {valor for valor, titulo in opcoes if _PROMETE.search(titulo)}
    return prometem & set(PRESET_FACTORIES)


def test_quem_promete_repeticao_na_tela_esta_na_lista_dos_que_repetem() -> None:
    prometem = _promessas_da_tela()
    assert prometem, "a régua não leu promessa nenhuma: o desenho mudou?"
    assert prometem <= REPETEM, (
        f"a tela promete repetição para {sorted(prometem - REPETEM)} "
        "e a régua não cobra frequência deles"
    )
