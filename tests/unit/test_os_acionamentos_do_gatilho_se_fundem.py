"""OS-ACIONAMENTOS-DO-GATILHO-SE-FUNDEM-E-SE-RENOMEIAM-01 — a lista de onze e as chaves velhas.

A lista da tela cai de dezenove para onze. Perfil gravado com uma chave que saiu continua
abrindo, pelo bloco que a TABELA abaixo diz (escrita à mão, e não uma igualdade entre a
chave velha e a nova: uma igualdade passaria com as duas erradas juntas).
"""

from __future__ import annotations

import pathlib
import sys

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.app.actions.trigger_specs import (
    PRESETS,
    PRESETS_ANTIGOS,
    get_spec,
    na_lista_de_onze,
    preset_to_positional_params,
)
from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.trigger_effects import (
    TRADUCAO_DAS_CHAVES_VELHAS,
    bloco_do_efeito,
    build_from_name,
    frequencia_limpa,
    vibration,
)
from hefesto_dualsense4unix.profiles.trigger_presets import (
    FEEDBACK_POSITION_LABELS,
    FEEDBACK_POSITION_PRESETS,
    VIBRATION_POSITION_LABELS,
    VIBRATION_POSITION_PRESETS,
)

ONZE = (
    "Off", "Resistance", "Weapon", "Bow", "Galloping", "Machine", "Vibration",
    "SlopeFeedback", "MultiPositionFeedback", "MultiPositionVibration", "Custom",
)

#: chave velha, ajustes de um perfil antigo → o bloco de 11 bytes que sai (em hex).
#: Quem diz o bloco é esta tabela; o que a tradução faz está escrito ao lado.
BLOCO_ESPERADO_POR_CHAVE_VELHA: dict[tuple[str, tuple[int, ...]], str] = {
    # Resistência, início na posição, força de byte posta em 0 a 8
    ("Rigid", (5, 200)): "21e0030080b62d00000000",
    ("Rigid", (0, 255)): "21ff03ffffff3f00000000",
    # Resistência, início 0
    ("SimpleRigid", (6,)): "21ff036ddbb62d00000000",
    # Resistência, início na posição
    ("Feedback", (5, 4)): "21e00300806d1b00000000",
    # Disparo (a arma oficial 0x25)
    ("PulseB", (2, 7, 180)): "2584000500000000000000",
    # Disparo, a força de 0 a 8 posta em byte (5 de 8 vira 5 do Disparo)
    ("SemiAutoGun", (3, 6, 5)): "2548000400000000000000",
    # Metralhadora do início ao fim do curso; 60 Hz vai para o divisor limpo, 50
    ("AutoGun", (2, 6, 60)): "26fc0340dbb62d00003200",
    # Disparo no padrão (2, 5, 200)
    ("Pulse", ()): "2524000500000000000000",
    # a única que NÃO muda de bloco: o arco do firmware (0x22) de hoje
    ("PulseA", (2, 7, 180)): "2284002d00000000000000",
}

BLOCO_DAS_QUE_JA_ERAM_DA_LISTA: dict[tuple[str, tuple[int, ...]], str] = {
    ("Resistance", (5, 6)): "21e0030080b62d00000000",
    ("Weapon", (2, 7, 180)): "2584000500000000000000",
    ("Machine", (2, 9, 4, 40)): "26fc03c0b66d1b00002800",
}


def _hex(nome: str, params: object) -> str:
    return bloco_do_efeito(build_from_name(nome, params)).hex()  # type: ignore[arg-type]


def test_a_lista_da_tela_tem_onze_acionamentos() -> None:
    assert tuple(p.name for p in PRESETS) == ONZE
    assert len(PRESETS) == 11


def test_as_chaves_que_sairam_da_lista_seguem_lidas_pelo_spec() -> None:
    saidas = {"Rigid", "SimpleRigid", "Feedback", "Pulse", "PulseA", "PulseB",
              "SemiAutoGun", "AutoGun"}
    assert {p.name for p in PRESETS_ANTIGOS} == saidas
    assert saidas.isdisjoint(p.name for p in PRESETS)
    for chave in saidas:
        assert get_spec(chave) is not None, chave


@pytest.mark.parametrize(("chave", "params"), sorted(BLOCO_ESPERADO_POR_CHAVE_VELHA))
def test_a_chave_velha_abre_pelo_bloco_da_tabela(chave: str, params: tuple[int, ...]) -> None:
    """Mordida: tirar a tradução de `Rigid` (ou a de qualquer outra) reprova aqui."""
    assert _hex(chave, list(params)) == BLOCO_ESPERADO_POR_CHAVE_VELHA[(chave, params)]


@pytest.mark.parametrize(("chave", "params"), sorted(BLOCO_DAS_QUE_JA_ERAM_DA_LISTA))
def test_as_da_lista_nao_mudam_de_bloco(chave: str, params: tuple[int, ...]) -> None:
    assert _hex(chave, list(params)) == BLOCO_DAS_QUE_JA_ERAM_DA_LISTA[(chave, params)]


def test_o_perfil_antigo_com_ajustes_nomeados_abre_pelo_mesmo_bloco() -> None:
    assert _hex("Rigid", {"position": 5, "force": 200}) == "21e0030080b62d00000000"
    assert _hex("SimpleRigid", {"strength": 6}) == "21ff036ddbb62d00000000"
    assert _hex("Feedback", {"position": 5, "strength": 4}) == "21e00300806d1b00000000"
    assert _hex("PulseB", {"start": 2, "end": 7, "force": 180}) == "2584000500000000000000"
    assert _hex("AutoGun", {"start": 2, "strength": 6, "frequency": 60}) == "26fc0340dbb62d00003200"


def test_a_chave_velha_com_a_quantidade_errada_segue_recusada() -> None:
    with pytest.raises(TypeError):
        build_from_name("Rigid", [5])
    with pytest.raises(ValueError):
        build_from_name("Rigid", [5, 300])


def test_a_arma_automatica_calada_fica_desligada() -> None:
    desligado = "0000000000000000000000"
    assert _hex("AutoGun", [2, 0, 60]) == desligado
    assert _hex("AutoGun", [2, 6, 0]) == desligado


def test_a_frequencia_vai_para_o_divisor_limpo_mais_proximo() -> None:
    assert [frequencia_limpa(f) for f in (1, 8, 33)] == [1, 8, 33]
    assert [frequencia_limpa(f) for f in (34, 40, 60, 75, 90, 120, 160, 255)] == [
        40, 40, 50, 50, 100, 125, 125, 250]
    for f in range(1, 256):
        limpa = frequencia_limpa(f)
        assert limpa <= 33 or 1000 % limpa == 0, f


def test_a_vibracao_comeca_em_0x26_e_amplitude_zero_apaga() -> None:
    assert vibration(3, 4, 40).mode == 0x26
    assert _hex("Vibration", [3, 4, 40]) == "26f80300b66d1b00002800"
    assert _hex("Vibration", [0, 8, 10])[:2] == "26"
    assert _hex("Vibration", [3, 0, 40]) == "0000000000000000000000"


def test_a_vibracao_e_a_metralhadora_da_posicao_ao_fim() -> None:
    assert bloco_do_efeito(vibration(3, 4, 40)) == bloco_do_efeito(
        build_from_name("Machine", [3, 9, 4, 40]))


def test_a_tela_mostra_a_chave_velha_pela_linha_nova() -> None:
    assert na_lista_de_onze("Rigid", [5, 200]) == ("Resistance", [5, 6])
    assert na_lista_de_onze("SimpleRigid", [6]) == ("Resistance", [0, 6])
    assert na_lista_de_onze("Feedback", [5, 4]) == ("Resistance", [5, 4])
    assert na_lista_de_onze("PulseB", [2, 7, 180]) == ("Weapon", [2, 7, 180])
    assert na_lista_de_onze("SemiAutoGun", [3, 6, 5]) == ("Weapon", [3, 6, 159])
    assert na_lista_de_onze("AutoGun", [2, 6, 60]) == ("Machine", [2, 9, 6, 50])
    assert na_lista_de_onze("Pulse", []) == ("Weapon", [2, 5, 200])
    assert na_lista_de_onze("PulseA", [2, 7, 180]) == ("Bow", [2, 7, 6, 6])
    assert na_lista_de_onze("Machine", [1, 2, 3, 4]) == ("Machine", [1, 2, 3, 4])


def test_toda_chave_velha_traduzida_aponta_para_a_lista_de_onze() -> None:
    for chave in TRADUCAO_DAS_CHAVES_VELHAS:
        spec = get_spec(chave)
        assert spec is not None
        padrao = preset_to_positional_params(spec, {})
        nova, _ajustes = na_lista_de_onze(chave, padrao)
        assert nova in ONZE, chave
        assert get_spec(nova) is not None


def _relatorio(efeito: object, conexao: ConnectionType) -> bytes:
    """O bloco do gatilho direito como o `prepareReport` o põe no report (cabo ou rádio)."""
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.leftMotor = 0
    inst.rightMotor = 0
    inst.light = DSLight()
    inst.audio = DSAudio()
    inst.triggerL = DSTrigger()
    inst.triggerR = DSTrigger()
    inst.conType = conexao
    inst._suppress_leds = True
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._bt_seq = 0
    inst._raw_trigger_right = None
    inst._raw_trigger_left = None
    bp.PyDualSenseController._apply_trigger(inst, "right", efeito)  # type: ignore[arg-type]
    quadro = bytes(inst.prepareReport())
    inicio = 11 if conexao == ConnectionType.USB else 13
    assert quadro[0] == (0x02 if conexao == ConnectionType.USB else 0x31)
    return quadro[inicio:inicio + 11]


@pytest.mark.parametrize(("chave", "params"), sorted(BLOCO_ESPERADO_POR_CHAVE_VELHA))
def test_o_mesmo_bloco_entra_no_report_do_cabo_e_no_do_radio(
    chave: str, params: tuple[int, ...],
) -> None:
    esperado = bytes.fromhex(BLOCO_ESPERADO_POR_CHAVE_VELHA[(chave, params)])
    efeito = build_from_name(chave, list(params))
    assert _relatorio(efeito, ConnectionType.USB) == esperado
    assert _relatorio(efeito, ConnectionType.BT) == esperado


def test_os_presets_de_posicao_ganham_os_nomes_do_catalogo_e_a_chave_velha_segue_lida() -> None:
    assert list(FEEDBACK_POSITION_PRESETS) == [
        "rampa_crescente", "rampa_decrescente", "plateau_central", "parede_no_fim",
        "parede_macia", "linear_medio"]
    assert list(VIBRATION_POSITION_PRESETS) == [
        "pulso_crescente", "vibra_em_degraus", "duas_ondas_no_curso", "sobe_e_desce",
        "vibra_no_fim"]
    rotulos = {
        "parede_no_fim": "Parede no fim", "parede_macia": "Parede macia",
        "vibra_em_degraus": "Vibra em degraus", "duas_ondas_no_curso": "Duas ondas no curso",
        "sobe_e_desce": "Sobe e desce", "vibra_no_fim": "Vibra no fim",
    }
    for chave, rotulo in rotulos.items():
        rotulos_da_chave = {**FEEDBACK_POSITION_LABELS, **VIBRATION_POSITION_LABELS}
        assert rotulos_da_chave[chave] == rotulo
    velhos = {"stop_hard": "parede_no_fim", "stop_macio": "parede_macia",
              "machine_gun": "vibra_em_degraus", "galope": "duas_ondas_no_curso",
              "senoide": "sobe_e_desce", "vibracao_final": "vibra_no_fim"}
    for velho, novo in velhos.items():
        tabela = (FEEDBACK_POSITION_PRESETS if novo in FEEDBACK_POSITION_PRESETS
                  else VIBRATION_POSITION_PRESETS)
        rotulos_t = (FEEDBACK_POSITION_LABELS if novo in FEEDBACK_POSITION_LABELS
                     else VIBRATION_POSITION_LABELS)
        assert velho in tabela
        assert tabela[velho] == tabela[novo]
        assert rotulos_t[velho] == rotulos_t[novo]


# --- a aba: onze opções, e o perfil antigo abre com o acionamento certo ----------------------

INTERFACE = pathlib.Path(__file__).resolve().parents[2] / "src/hefesto_dualsense4unix/interface"
sys.path.insert(0, str(INTERFACE))

_UNIQ = "aa:bb:cc:00:00:01"
_FALSO = {"uniq": _UNIQ, "player": 1, "transport": "usb", "is_primary": True,
          "inputs": {"l2_raw": 0, "r2_raw": 0}}
_MESA = [{"pref": "p1", "jogador": 1, "uniq": _UNIQ, "nome": "Régua", "via": "USB",
          "cor": "starlight-blue", "mascara": "DualSense"}]


def _a03_com_o_perfil(monkeypatch: pytest.MonkeyPatch, esquerdo: dict, direito: dict):
    from pacotes import Contexto, perfil
    from pacotes import a03_gatilhos as a03

    cru = {"name": "Régua", "version": 1, "priority": 50, "match": {"type": "manual"},
           "triggers": {"left": esquerdo, "right": direito}}
    monkeypatch.setattr(perfil, "ativo", lambda _nome: dict(cru))
    a03.esquecer_o_rascunho()
    ctx = Contexto(state={"active_profile": "Régua"}, mesa=_MESA, conectados=[_FALSO],
                   estados={})
    return a03, a03.pacote(ctx)


def test_a_lista_da_aba_tem_so_os_onze(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mordida: tirar de `_rotuladas` o descarte do que a lista de onze não tem."""
    import re

    a03, _ = _a03_com_o_perfil(monkeypatch, {"mode": "Off", "params": []},
                               {"mode": "Off", "params": []})
    valores = re.findall(r'<option value="([^"]*)"', a03.html_das_opcoes_de_modo())
    assert set(valores) - {"—"} <= set(ONZE), (
        f"a aba oferece o que a lista de onze não tem: {sorted(set(valores) - set(ONZE))}")
    assert len(set(valores) - {"—"}) >= 10


def test_o_perfil_antigo_abre_com_o_acionamento_certo(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Rigid` abre como Resistência e `AutoGun` como Metralhadora, com os ajustes na ordem nova.

    Mordida: tirar a tradução do `_do_lado` (a coluna volta a dizer `Rigid`).
    """
    _a03, r = _a03_com_o_perfil(
        monkeypatch, {"mode": "Rigid", "params": [5, 200]},
        {"mode": "AutoGun", "params": [2, 6, 60]})
    col = r["colunas"][_UNIQ]
    assert (col["modo-chave-e"], col["modo-chave-d"]) == ("Resistance", "Machine")
    assert (col["modo-e"], col["modo-d"]) == ("Resistência", "Metralhadora")


@pytest.mark.parametrize(("esquerdo", "direito"), [
    ({"mode": "Rigid", "params": [5, 200]}, {"mode": "SimpleRigid", "params": [6]}),
    ({"mode": "Feedback", "params": [5, 4]}, {"mode": "PulseB", "params": [2, 7, 180]}),
    ({"mode": "SemiAutoGun", "params": [3, 6, 5]}, {"mode": "AutoGun", "params": [2, 6, 60]}),
    ({"mode": "PulseA", "params": [2, 7, 180]}, {"mode": "Rigid", "params": []}),
])
def test_o_perfil_antigo_nos_padroes_abre_sem_imersao_e_nao_em_branco(
    monkeypatch: pytest.MonkeyPatch, esquerdo: dict, direito: dict,
) -> None:
    """A chave velha nos padrões do modo dela abre com «Nenhum», como abria antes da fusão.

    Os números traduzidos não são os padrões do acionamento novo, mas não são ajuste da
    pessoa: o campo em branco diria «números próprios» de um perfil que nunca mexeu ali.
    Mordida: tirar de `_imersao_que_casa` o caso dos padrões do modo antigo (volta o vazio).
    """
    a03, r = _a03_com_o_perfil(monkeypatch, esquerdo, direito)
    col = r["colunas"][_UNIQ]
    assert (col[f"{a03.CAMPO_DA_IMERSAO}-e"], col[f"{a03.CAMPO_DA_IMERSAO}-d"]) == (
        a03.SEM_IMERSAO, a03.SEM_IMERSAO)


def test_o_perfil_antigo_com_numeros_proprios_segue_em_branco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fora dos padrões e sem imersão que case, o campo fica vazio: «Nenhum» seria mentir."""
    a03, r = _a03_com_o_perfil(
        monkeypatch, {"mode": "Rigid", "params": [3, 120]},
        {"mode": "Off", "params": []})
    col = r["colunas"][_UNIQ]
    assert col[f"{a03.CAMPO_DA_IMERSAO}-e"] == ""
