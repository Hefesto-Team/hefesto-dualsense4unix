"""MOVIMENTO-EM-QUALQUER-MASCARA-01 — o giroscópio que o jogo XInput não vê.

O QUE ESTA SPRINT CURA, em uma frase: o DualSense tem giroscópio, o jogo sob
máscara Xbox **não tem onde recebê-lo** (o descritor XInput não carrega
sensores), e por isso a mira por movimento — que é o que faz o giro valer a
pena para quem tem pouca precisão fina na mão — simplesmente não existia
nesses jogos.

A cura é uma TRADUÇÃO: o giro do plástico vira deslocamento no que o jogo já
lê — o analógico direito, o esquerdo, ou o cursor do mouse.

AS SETE ENTREGAS, e cada bloco abaixo morde uma:

| E1 | `core/roteador_de_movimento.py`        | o motor puro, sem aparelho |
| E2 | `profiles/schema.py`                   | o campo do perfil |
| E3 | `core/evdev_reader.py`                 | a fonte: o ângulo integrado |
| E4 | `daemon/sensor_hub.py`                 | a torneira |
| E5 | `daemon/subsystems/gamepad.py`         | a mistura no tique |
| E6 | `integrations/uinput_mouse.py`         | a segunda saída |
| E7 | `profiles/manager.py`                  | o depósito na ativação |

**E TRÊS DESTAS RÉGUAS NASCERAM DE UMA AUDITORIA ADVERSARIAL** feita ANTES de
a primeira linha da E5 entrar (§9 da sprint). Elas estão marcadas com o número
do achado, e a do 9.3 é a mais importante de ler: a régua que a sprint trazia
escrita **daria verde sobre o defeito 9.1**, porque montava os botões à mão no
vocabulário da TELA em vez do vocabulário do LEITOR, que é o que o produto
entrega.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core import remapeamento_de_botao as remap
from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.evdev_reader import MotionSensorReader
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)

# ---------------------------------------------------------------------------
# E1 — o motor puro
# ---------------------------------------------------------------------------


def _arranjo(**kw: Any) -> rot.ArranjoDeMovimento:
    base: dict[str, Any] = {"destino": rot.DESTINO_ANALOGICO_DIREITO}
    base.update(kw)
    return rot.ArranjoDeMovimento(**base)


#: A DERIVA MEDIDA NO DUALSENSE DELA, parado na mesa, em 21/09/2026: 60
#: amostras a 20 Hz pelo nó "Motion Sensors". Pior eixo (y): média 0,72,
#: máximo **0,85 graus/s**. É o número contra o qual a zona morta padrão (3,0)
#: se dimensiona — 3,5x de margem.
DERIVA_MEDIDA_GRAUS_S = 0.85


def test_a_deriva_do_controle_dela_nao_move_a_mira() -> None:
    """O giroscópio do DualSense NÃO marca zero parado: ele deriva.

    Sem corte, a câmera dela passearia sozinha com o controle na mesa — que é
    a queixa mais comum de mira por giroscópio em qualquer produto. Este teste
    usa a deriva MEDIDA no aparelho dela, não um número inventado.
    """
    assert rot.deflexao((0.0, 0.0, 0.0), _arranjo()) == (0, 0)
    for sensibilidade in (1, 6, 12):
        assert rot.deflexao(
            (0.0, DERIVA_MEDIDA_GRAUS_S, 0.0), _arranjo(sensibilidade=sensibilidade)
        ) == (0, 0), (
            f"a deriva de {DERIVA_MEDIDA_GRAUS_S} graus/s moveu a mira na "
            f"sensibilidade {sensibilidade}")


def test_a_zona_morta_alta_e_o_dial_de_quem_tem_tremor() -> None:
    """ARRANQUE a zona morta e este teste reprova — e é o ÚNICO que reprova.

    **O QUE A MORDIDA REVELOU, e a prosa desta régua estava errada antes
    (21/09/2026):** com a zona morta PADRÃO (3,0) o resultado é byte a byte o
    mesmo de sem zona morta nenhuma. A curva (`EXPO_DO_GIRO` 1,6) mais o
    arredondamento do eixo já zeram tudo abaixo de ~7 graus/s sozinhos. A
    primeira redação deste teste usava 2 graus/s e dava VERDE com a cura
    arrancada — mais um instrumento que respondia sobre outra coisa.

    ONDE A ZONA MORTA É A FEATURE INTEIRA: o tremor. Este app é de
    acessibilidade, e um tremor essencial mora na faixa de 15 a 30 graus/s —
    bem acima do que a curva corta. Para essa pessoa o campo `zona_morta_graus_s`
    (1 a 60 na tela) é o que separa uma mira usável de uma câmera que treme
    junto com a mão. O default de 3,0 cobre a DERIVA do aparelho (0,85 medido);
    subir o dial é o que cobre a mão.
    """
    tremor = (0.0, 25.0, 0.0)
    forte = _arranjo(sensibilidade=12)
    assert rot.deflexao(tremor, forte) != (0, 0), (
        "a premissa caiu: 25 graus/s já não passa nem sem zona morta")
    com_dial = _arranjo(sensibilidade=12, zona_morta_graus_s=30.0)
    assert rot.deflexao(tremor, com_dial) == (0, 0), (
        "a zona morta alta não cortou o tremor — o dial não faz nada")


def test_um_gesto_de_verdade_move() -> None:
    """A entrega da E1 numa linha: 120 graus/s viram deflexão."""
    dh, _ = rot.deflexao((0.0, 120.0, 0.0), _arranjo())
    assert dh != 0, "um giro de 120 graus/s não moveu nada"


def test_o_teto_satura_e_nao_estoura_o_eixo() -> None:
    """ARRANQUE o teto e este teste reprova: um giro brusco mandaria um valor
    fora de 0..255 e o jogo leria lixo (ou o uinput recusaria o evento)."""
    dh, _ = rot.deflexao((0.0, 5000.0, 0.0), _arranjo())
    assert abs(dh) <= rot.DEFLEXAO_MAXIMA, (
        f"deflexão {dh} passou do máximo {rot.DEFLEXAO_MAXIMA}")


def test_a_mistura_nao_estoura_o_byte_do_analogico() -> None:
    """ARRANQUE o `_saturar` e este teste reprova.

    O analógico vai ao jogo como BYTE. Somar a mira a um stick já no batente
    produziria 255+ — e o que chega ao jogo não é "mais forte", é outro valor.
    """
    x, y = rot.misturar(250, 5, 120, -120)
    assert 0 <= x <= 255 and 0 <= y <= 255, f"({x}, {y}) saiu da faixa do byte"


def test_o_arranjo_desligado_nao_e_arranjo() -> None:
    """ARRANQUE o ramo `nenhum` de `resolver` e este teste reprova: guardar a
    calibração dela com a mira DESLIGADA é o que permite experimentar sem
    perder o ajuste."""
    assert rot.resolver(ProfileMovimentoConfig(destino="nenhum")) is None
    assert rot.resolver(None) is None


# ---------------------------------------------------------------------------
# E2 — o campo do perfil
# ---------------------------------------------------------------------------


def test_o_perfil_de_ontem_continua_saindo_igual() -> None:
    """ARRANQUE "movimento" da tupla de omissões e este teste reprova.

    Um perfil que nunca ouviu falar de mira por movimento não pode ganhar a
    chave só por passar por um load→save: o Hefesto da versão anterior tem
    `extra="forbid"` e recusaria o arquivo INTEIRO — todos os perfis dela, não
    só os que usam a seção.
    """
    perfil = Profile(name="Antigo", match=MatchAny(type="any"))
    assert "movimento" not in perfil.model_dump()


#: Uma mira FORA do padrão em todo campo que o salvar poderia zerar — com o
#: padrão, um `None` virando `ProfileMovimentoConfig()` passaria despercebido.
_MIRA_DELA = ProfileMovimentoConfig(
    destino="mouse", sensibilidade=9, eixo_horizontal="roll",
    inverter_vertical=True, zona_morta_graus_s=18.0, gatilho="l2")


def test_o_salvar_perfil_transporta_a_mira_por_movimento() -> None:
    """ARRANQUE `movimento=self.source_movimento` de `DraftConfig.to_profile` e
    este teste reprova nas duas linhas.

    O DEFEITO, medido pela suíte em 21/09/2026, no mesmo dia em que o campo
    nasceu: `to_profile` reconstrói o perfil do zero, e a mira não tinha
    transporte — todo «Salvar Perfil» e todo gesto de aba que grava o perfil
    (Controles, Vibração, Perfis) devolvia `movimento=None`, e a mira dela
    sumia do disco sem uma palavra. Com nome novo ela vai junto, como o
    `remapeamento`: é configuração dela, não regra de identidade do perfil.
    """
    from hefesto_dualsense4unix.app.draft_config import DraftConfig

    perfil = Profile(name="Com Mira", match=MatchAny(type="any"), movimento=_MIRA_DELA)
    rascunho = DraftConfig.from_profile(perfil)
    assert rascunho.to_profile("Com Mira").movimento == _MIRA_DELA
    assert rascunho.to_profile("Outro Nome").movimento == _MIRA_DELA


def test_a_mira_sobrevive_a_ida_e_volta_pelo_disco() -> None:
    """O caminho inteiro do Salvar, pelo disco do lar de mentira do conftest.

    `save_profile` → `load_profile` → rascunho → `to_profile` → `save_profile`
    → `load_profile`. A régua de cima mede o rascunho; esta mede que o disco
    devolve o que recebeu, com o perfil sem mira continuando SEM a chave.
    """
    from hefesto_dualsense4unix.app.draft_config import DraftConfig
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

    save_profile(Profile(name="Mira Ida E Volta", match=MatchAny(type="any"),
                         movimento=_MIRA_DELA))
    rascunho = DraftConfig.from_profile(load_profile("Mira Ida E Volta"))
    save_profile(rascunho.to_profile("Mira Ida E Volta"))
    assert load_profile("Mira Ida E Volta").movimento == _MIRA_DELA


def test_teto_abaixo_da_zona_morta_e_recusado_no_load() -> None:
    """ARRANQUE o `model_validator` e este teste reprova — o arranjo silencioso
    que nunca move nada só apareceria no meio da partida dela."""
    with pytest.raises(ValidationError):
        ProfileMovimentoConfig(
            destino="analogico_direito", zona_morta_graus_s=50.0, teto_graus_s=20.0
        )


def test_o_ps_nunca_vira_gatilho_da_mira() -> None:
    """ARRANQUE a derivação de REMAPEAVEIS e este teste reprova: o PS é a saída
    de emergência dela, e prendê-lo a uma feature a tira."""
    with pytest.raises(ValidationError):
        ProfileMovimentoConfig(destino="mouse", gatilho="ps")


def test_o_gatilho_do_perfil_sai_da_lista_do_motor() -> None:
    """A lista é DERIVADA, não digitada: uma segunda cópia envelheceria."""
    for botao in remap.REMAPEAVEIS:
        assert ProfileMovimentoConfig(destino="mouse", gatilho=botao).gatilho == botao
    with pytest.raises(ValidationError):
        ProfileMovimentoConfig(destino="mouse", gatilho="botao_que_nao_existe")


# ---------------------------------------------------------------------------
# E3 — a fonte: o ângulo integrado no ritmo do NÓ, não no do tique
# ---------------------------------------------------------------------------

_EC = SimpleNamespace(EV_SYN=0, EV_ABS=3, SYN_REPORT=0,
                      ABS_RX=3, ABS_RY=4, ABS_RZ=5, ABS_X=0, ABS_Y=1, ABS_Z=2)


def _evento(tipo: int, code: int, *, t: float = 0.0, value: int = 0) -> SimpleNamespace:
    return SimpleNamespace(type=tipo, code=code, value=value, sec=int(t),
                           usec=round((t - int(t)) * 1e6))


def _leitor() -> MotionSensorReader:
    # PATH DE MENTIRA E NÃO `None`: com `None` o construtor chama `_locate()`,
    # que varre `/dev/input` da máquina — a suíte passaria a depender de haver
    # (ou não) um DualSense na mesa dela. É a TELA-DELA-01 aplicada ao sensor.
    return MotionSensorReader(device_path=Path("/dev/hefesto-nao-existe"))


def test_um_giro_rapido_entre_dois_tiques_nao_se_perde() -> None:
    """ARRANQUE a integração e este teste reprova.

    Vinte pacotes de 100 graus/s com 5 ms entre eles são 10 graus de giro. Quem
    multiplicasse a VELOCIDADE pelo período do tique (1/60 s) leria 1,67 —
    um sexto do movimento que a mão dela fez.
    """
    leitor = _leitor()
    for n in range(21):
        leitor._eixos["y"] = 100.0
        leitor._handle_event(_evento(_EC.EV_SYN, _EC.SYN_REPORT, t=n * 0.005), _EC)
    _, y, _ = leitor.consume_angulo()
    assert 9.5 <= y <= 10.5, f"20 pacotes de 100 graus/s deram {y}, não ~10"


def test_o_buraco_de_tempo_nao_vira_virada_de_camera() -> None:
    """ARRANQUE o `_MAIOR_DT_INTEGRAVEL_S` e este teste reprova: uma máquina
    suspensa por 30 s com o controle a 100 graus/s injetaria 3.000 num quadro."""
    leitor = _leitor()
    leitor._eixos["y"] = 100.0
    leitor._integrar_o_angulo(0.0)
    leitor._integrar_o_angulo(30.0)
    assert leitor.consume_angulo() == (0.0, 0.0, 0.0)


def test_o_angulo_drena_e_nao_se_repete() -> None:
    """ARRANQUE o zeramento de `consume_angulo` e este teste reprova: a mira
    andaria para sempre na direção do último movimento."""
    leitor = _leitor()
    leitor._angulo = {"x": 0.0, "y": 7.0, "z": 0.0}
    assert leitor.consume_angulo() == (0.0, 7.0, 0.0)
    assert leitor.consume_angulo() == (0.0, 0.0, 0.0)


def test_o_primeiro_pacote_nao_inventa_intervalo() -> None:
    """ARRANQUE o `if anterior is None` e este teste reprova: o salto nasceria
    no instante em que o controle conecta — com a mão dela no aparelho."""
    leitor = _leitor()
    leitor._eixos["y"] = 500.0
    leitor._handle_event(_evento(_EC.EV_SYN, _EC.SYN_REPORT, t=1.0), _EC)
    assert leitor.consume_angulo() == (0.0, 0.0, 0.0)


def test_o_angulo_some_quando_o_controle_some() -> None:
    """ARRANQUE as duas linhas do `_reset_on_disconnect` e este teste reprova:
    o gesto de pôr o controle de volta na mesa viraria virada de câmera."""
    leitor = _leitor()
    leitor._angulo = {"x": 1.0, "y": 2.0, "z": 3.0}
    leitor._ultimo_syn = 9.0
    leitor._reset_on_disconnect()
    assert leitor.consume_angulo() == (0.0, 0.0, 0.0)
    assert leitor._ultimo_syn is None


def test_a_velocidade_continua_chegando_como_antes() -> None:
    """A régua de NÃO-REGRESSÃO da E3: o `_handle_event` ganhou um ramo novo
    antes do EV_ABS, e o giro que o painel já lia não pode ter mudado."""
    leitor = _leitor()
    leitor._resolucoes = {"y": 1024}
    leitor._handle_event(_evento(_EC.EV_ABS, _EC.ABS_RY, value=1024), _EC)
    assert abs(leitor.snapshot().y - 1.0) < 0.001


# ---------------------------------------------------------------------------
# E5 — a mistura no tique, e os três achados do advogado do diabo
# ---------------------------------------------------------------------------


class _Device:
    """O gamepad virtual de mentira: guarda o que o JOGO receberia."""

    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


class _Mouse:
    def __init__(self) -> None:
        self.movimentos: list[tuple[float, float]] = []

    def emit_gyro_move(self, px_x: float, px_y: float) -> None:
        self.movimentos.append((px_x, px_y))


class _Hub:
    """A torneira de mentira. Conta as DRENAGENS — é o que a 9.2 mede."""

    def __init__(self, *, velocidade: Any = (0.0, 0.0, 0.0),
                 angulo: Any = (0.0, 0.0, 0.0), levanta: bool = False) -> None:
        self._velocidade = velocidade
        self._angulo = angulo
        self._levanta = levanta
        self.drenagens = 0

    def velocidade_do_movimento(self, uniq: str) -> Any:
        if self._levanta:
            raise RuntimeError("o hub caiu")
        return self._velocidade

    def angulo_do_movimento(self, uniq: str) -> Any:
        self.drenagens += 1
        if self._levanta:
            raise RuntimeError("o hub caiu")
        return self._angulo


_UNIQ = "aa:bb:cc:00:00:01"
_ESTADO = SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128,
                          l2_raw=0, r2_raw=0)


def _despachar(monkeypatch: pytest.MonkeyPatch, *, arranjo: Any, hub: _Hub,
               botoes: frozenset[str] = frozenset(), giro_ligado: bool = True,
               estado: Any = _ESTADO, mouse: Any = None) -> _Device:
    from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(gp, "primary_identity", lambda d: _UNIQ)
    monkeypatch.setattr(REGISTRO, "estado",
                        lambda uniq: SimpleNamespace(giroscopio=giro_ligado))
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    rot.definir_ativo(store, arranjo)
    dev = _Device()
    daemon = SimpleNamespace(store=store, _gamepad_device=dev,
                             _mouse_device=mouse,
                             _garantir_sensor_hub=lambda: hub)
    gp.dispatch_gamepad(daemon, estado, botoes)
    return dev


def test_a_mira_vale_na_mascara_xbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ENTREGA INTEIRA NUMA LINHA. ARRANQUE a chamada de
    `aplicar_o_movimento` do `dispatch_gamepad` e este teste reprova.

    `dispatch_gamepad` é o caminho do controle ao vpad, e o vpad é o que veste
    a máscara. A mira entrar AQUI é o que a faz valer em QUALQUER máscara —
    inclusive na Xbox, onde o jogo não tem onde receber o giro nativo.
    """
    dev = _despachar(monkeypatch,
                     arranjo=_arranjo(sensibilidade=12),
                     hub=_Hub(velocidade=(0.0, 120.0, 0.0)))
    assert dev.analog and dev.analog[0]["rx"] != 128, (
        f"o analógico direito saiu em {dev.analog} — a mira não chegou ao jogo")


def test_uma_mira_quebrada_nao_leva_o_controle_junto(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o `try/except` de `aplicar_o_movimento` e este teste reprova.

    O `except` do `dispatch_gamepad` registra um warning e **pula o forward
    inteiro**: os sticks, os botões e os gatilhos dela morreriam no jogo por
    causa de uma mira.
    """
    estado = SimpleNamespace(raw_lx=200, raw_ly=128, raw_rx=128, raw_ry=128,
                             l2_raw=0, r2_raw=0)
    dev = _despachar(monkeypatch,
                     arranjo=_arranjo(destino=rot.DESTINO_MOUSE),
                     hub=_Hub(levanta=True), estado=estado)
    assert dev.analog and dev.analog[0]["lx"] == 200, (
        "o controle dela não chegou ao jogo porque a mira caiu")
    assert dev.buttons, "o `forward_buttons` nem aconteceu"


def test_o_giro_desligado_por_ela_desliga_a_mira(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o portão do `REGISTRO` e este teste reprova: o interruptor de
    sensor dela passaria a mentir."""
    dev = _despachar(monkeypatch, arranjo=_arranjo(sensibilidade=12),
                     hub=_Hub(velocidade=(0.0, 300.0, 0.0)), giro_ligado=False)
    assert dev.analog[0]["rx"] == 128


def test_sem_arranjo_o_tique_nao_paga_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """A régua de CUSTO: sem mira ligada, os quatro eixos vão como vieram."""
    hub = _Hub(velocidade=(0.0, 900.0, 0.0))
    dev = _despachar(monkeypatch, arranjo=None, hub=hub)
    assert dev.analog[0]["rx"] == 128 and dev.analog[0]["ry"] == 128
    assert hub.drenagens == 0, "o tique sem mira consultou o hub"


# --- 9.1 e 9.3: o gatilho fala a língua do LEITOR, não a da TELA -----------


def test_o_gatilho_dispara_com_o_botao_que_o_produto_entrega(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ACHADO 9.1 do advogado do diabo, e a régua é a 9.3.

    `ProfileMovimentoConfig.gatilho` guarda o id da TELA (`l2`); o
    `buttons_pressed` que chega ao `dispatch_gamepad` fala o vocabulário do
    LEITOR EVDEV (`l2_btn`, em `EvdevReader.BUTTON_MAP`). Sem a tradução por
    `remapeamento_de_botao.GATILHOS`, `"l2" not in {"l2_btn"}` é sempre
    verdadeiro e **a mira com gatilho nunca dispararia** — silenciosamente.

    A RÉGUA QUE A SPRINT TRAZIA ESCRITA DARIA VERDE SOBRE ESSE DEFEITO: ela
    injetava `frozenset({"l2"})` à mão. Esta monta o conjunto pelo MESMO
    dicionário que o leitor usa, que é o que o produto entrega.
    """
    nome_no_jogo = remap.GATILHOS["l2"]
    assert nome_no_jogo != "l2", (
        "a premissa do achado 9.1 caiu — o leitor passou a falar o id da tela")
    dev = _despachar(monkeypatch,
                     arranjo=_arranjo(sensibilidade=12, gatilho="l2"),
                     hub=_Hub(velocidade=(0.0, 300.0, 0.0)),
                     botoes=frozenset({nome_no_jogo}))
    assert dev.analog[0]["rx"] != 128, (
        "o gatilho `l2` não ligou a mira com o botão que o leitor entrega — "
        "é o achado 9.1 vivo")


def test_o_gatilho_solto_nao_move(monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o portão do gatilho e este teste reprova: a mira valeria
    sempre, e o arranjo «só enquanto aperto» deixaria de existir."""
    dev = _despachar(monkeypatch,
                     arranjo=_arranjo(sensibilidade=12, gatilho="l2"),
                     hub=_Hub(velocidade=(0.0, 300.0, 0.0)),
                     botoes=frozenset())
    assert dev.analog[0]["rx"] == 128


def test_o_gatilho_le_o_botao_original(monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE `botoes=buttons_pressed` e ponha os botões traduzidos: este
    teste reprova.

    Com o remapeamento `{l2: r2}` ativo, o JOGO vê R2 quando ela aperta L2. A
    mira tem de continuar ligando pelo que a MÃO dela apertou.
    """
    from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(gp, "primary_identity", lambda d: _UNIQ)
    monkeypatch.setattr(REGISTRO, "estado",
                        lambda uniq: SimpleNamespace(giroscopio=True))
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    remap.definir_ativo(store, {"l2": "r2"})
    rot.definir_ativo(store, _arranjo(sensibilidade=12, gatilho="l2"))
    dev = _Device()
    gp.dispatch_gamepad(
        SimpleNamespace(store=store, _gamepad_device=dev, _mouse_device=None,
                        _garantir_sensor_hub=lambda: _Hub(
                            velocidade=(0.0, 300.0, 0.0))),
        _ESTADO, frozenset({remap.GATILHOS["l2"]}))
    assert dev.analog[0]["rx"] != 128, (
        "com o remapeamento ativo a mira deixou de ligar pelo botão que a mão "
        "dela apertou")


# --- 9.2: o acumulador drena ANTES dos portões -----------------------------


def test_o_gatilho_solto_nao_deixa_o_angulo_acumular(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ACHADO 9.2 do advogado do diabo. MOVA a drenagem para DEPOIS dos
    portões — como a sprint a trazia escrita — e este teste reprova.

    O acumulador de ângulo cresce na thread do reader, a ~675 Hz, e só zera em
    `consume_angulo()`. Com a drenagem atrás do portão do gatilho, dez segundos
    de gatilho solto com o controle na mão despejariam o percurso INTEIRO no
    primeiro tique em que ela apertasse. Drenando antes, o que o portão barra é
    descartado — que é o que a mão dela espera.
    """
    hub = _Hub(velocidade=(0.0, 300.0, 0.0), angulo=(0.0, 400.0, 0.0))
    dev = _despachar(monkeypatch,
                     arranjo=_arranjo(destino=rot.DESTINO_MOUSE, gatilho="l2"),
                     hub=hub, botoes=frozenset(), mouse=_Mouse())
    assert hub.drenagens == 1, (
        "o tique com o gatilho solto NÃO drenou o acumulador — o ângulo vai "
        "crescendo e vira um salto quando ela apertar (achado 9.2)")
    assert dev.analog[0]["rx"] == 128


def test_o_giro_desligado_tambem_drena(monkeypatch: pytest.MonkeyPatch) -> None:
    """O mesmo achado 9.2, pelo segundo portão: com o giroscópio desligado por
    ela o acumulador também não pode crescer em silêncio."""
    hub = _Hub(velocidade=(0.0, 300.0, 0.0), angulo=(0.0, 400.0, 0.0))
    _despachar(monkeypatch, arranjo=_arranjo(destino=rot.DESTINO_MOUSE),
               hub=hub, giro_ligado=False, mouse=_Mouse())
    assert hub.drenagens == 1


def test_o_destino_mouse_move_o_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    """A entrega do destino «mouse»: ângulo percorrido vira pixel."""
    mouse = _Mouse()
    _despachar(monkeypatch, arranjo=_arranjo(destino=rot.DESTINO_MOUSE),
               hub=_Hub(velocidade=(0.0, 300.0, 0.0), angulo=(0.0, 10.0, 0.0)),
               mouse=mouse)
    assert mouse.movimentos, "o cursor não andou"
    assert mouse.movimentos[0][0] != 0.0


def test_sem_no_de_mouse_a_mira_nao_inventa_um(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o `if mouse is not None` e este teste reprova (com um
    `AttributeError` que o `except` engoliria): um segundo dono para o cursor
    dela é decisão dela, não efeito colateral de uma mira."""
    dev = _despachar(monkeypatch, arranjo=_arranjo(destino=rot.DESTINO_MOUSE),
                     hub=_Hub(velocidade=(0.0, 300.0, 0.0),
                              angulo=(0.0, 10.0, 0.0)), mouse=None)
    assert dev.analog and dev.buttons, "o forward caiu por falta de nó de mouse"


def test_a_deriva_nao_passeia_o_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o portão `deflexao(velocidade) == (0, 0)` do ramo do mouse e
    este teste reprova.

    A zona morta se mede na VELOCIDADE, mas quem move o cursor é o ÂNGULO — e
    um controle parado com deriva percorre ângulo de verdade. Sem este portão o
    cursor dela passearia sozinho com o controle na mesa.
    """
    mouse = _Mouse()
    _despachar(monkeypatch, arranjo=_arranjo(destino=rot.DESTINO_MOUSE),
               hub=_Hub(velocidade=(0.0, 1.0, 0.0), angulo=(0.0, 8.0, 0.0)),
               mouse=mouse)
    assert mouse.movimentos == [], (
        f"a deriva moveu o cursor em {mouse.movimentos}")


# ---------------------------------------------------------------------------
# E6 — a segunda saída: o carry sub-pixel
# ---------------------------------------------------------------------------


def _mouse_falso() -> Any:
    from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice

    dev = UinputMouseDevice()
    emitidos: list[tuple[int, int]] = []

    class _U:
        REL_X, REL_Y = 0, 1

    class _D:
        def emit(self, code: int, value: int, syn: bool = True) -> None:
            emitidos.append((code, value))

        def syn(self) -> None:
            pass

    dev._device = _D()
    dev._uinput_mod = _U()
    dev._emitidos = emitidos  # type: ignore[attr-defined]
    return dev


def _soma_rel_x(dev: Any) -> int:
    return sum(v for c, v in dev._emitidos if c == 0)


def test_a_mira_fina_nao_e_jogada_fora() -> None:
    """ARRANQUE o carry e este teste reprova: 0,4 px por tique viraria zero
    para sempre, e o ajuste fino — que é o que o giro faz melhor que o stick —
    não moveria nada."""
    dev = _mouse_falso()
    for _ in range(5):
        dev.emit_gyro_move(0.4, 0.0)
    assert _soma_rel_x(dev) == 2, f"5 x 0,4 px deram {_soma_rel_x(dev)}, não 2"


def test_o_carry_do_giro_nao_rouba_o_do_touchpad() -> None:
    """ARRANQUE o par próprio e use `_tp_carry_*`: este teste reprova — o dedo
    dela empurraria a mira e a mira empurraria o dedo."""
    dev = _mouse_falso()
    dev.emit_gyro_move(0.6, 0.0)
    dev.emit_touchpad_move(1, 0)
    antes = _soma_rel_x(dev)
    dev.emit_gyro_move(0.6, 0.0)
    assert _soma_rel_x(dev) - antes == 1, (
        "o carry do giro foi contaminado pelo do touchpad")


def test_sem_device_a_mira_e_no_op() -> None:
    """O roteador NÃO cria nó de mouse por conta própria."""
    from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice

    UinputMouseDevice().emit_gyro_move(99.0, 99.0)  # não levanta


# ---------------------------------------------------------------------------
# E7 — o depósito na ativação, e o contágio que ele impede
# ---------------------------------------------------------------------------


def test_o_jogo_seguinte_nao_herda_a_mira_do_anterior() -> None:
    """ARRANQUE o `definir_ativo` do ramo sem arranjo e este teste reprova.

    É a forma exata do CAMINHO-CONTAGIO-01: a escolha de UM jogo virando padrão
    da máquina sem ninguém pedir. O depósito acontece SEMPRE, inclusive com
    `None` — é o que apaga a mira do jogo anterior.
    """
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    store = SimpleNamespace()
    gerente = ProfileManager.__new__(ProfileManager)
    gerente.store = store  # type: ignore[attr-defined]

    com = Profile(name="Com mira", match=MatchAny(type="any"),
                  movimento=ProfileMovimentoConfig(destino="analogico_direito"))
    sem = Profile(name="Sem mira", match=MatchAny(type="any"))

    gerente.apply_movimento(com)
    assert rot.ativo(store) is not None
    gerente.apply_movimento(sem)
    assert rot.ativo(store) is None, (
        "a mira do jogo anterior sobreviveu ao perfil seguinte")


def test_um_arranjo_torto_nao_derruba_as_luzes_dela() -> None:
    """ARRANQUE o `except ArranjoRecusadoError` e este teste reprova: uma linha
    torta de mira derrubaria a ativação inteira do perfil."""
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    store = SimpleNamespace()
    gerente = ProfileManager.__new__(ProfileManager)
    gerente.store = store  # type: ignore[attr-defined]

    torto = Profile(name="Torto", match=MatchAny(type="any"),
                    movimento=ProfileMovimentoConfig(destino="analogico_direito"))
    # Só um `model_copy` sem validação chega aqui torto — o esquema recusa no load.
    object.__setattr__(torto.movimento, "destino", "destino_que_nao_existe")
    relatorio: dict[str, str] = {}
    gerente.apply_movimento(torto, relatorio=relatorio)
    assert relatorio["movimento"] == "falhou"
    assert rot.ativo(store) is None


def test_a_secao_nova_entra_na_ativacao() -> None:
    """A régua de LIGAÇÃO: uma seção de perfil sem quem a aplique é trabalho
    dela que morre no disco. ARRANQUE a linha do `activate` e ela reprova."""
    import inspect

    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    fonte = inspect.getsource(ProfileManager.activate)
    assert "apply_movimento" in fonte, (
        "`activate` não chama `apply_movimento` — o campo do perfil existe e "
        "nunca chega ao tique")


# ---------------------------------------------------------------------------
# E4 — a torneira, contra o `SensorHub` DE VERDADE
# ---------------------------------------------------------------------------
#
# O `_Hub` de mentira acima mede a MISTURA; estas duas medem a TORNEIRA. As
# duas coisas separadas de propósito: um dublê que respondesse por si só
# deixaria a porta real sem nenhuma régua — que é a forma de defeito que esta
# casa chama de "o instrumento respondia sobre outra coisa que não o produto".


class _ReaderDeMotionFalso:
    def __init__(self, giro: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
        self._giro = giro
        self._angulo = (0.0, 0.0, 0.0)

    def definir_angulo(self, valores: tuple[float, float, float]) -> None:
        self._angulo = valores

    def snapshot(self) -> Any:
        return SimpleNamespace(x=self._giro[0], y=self._giro[1], z=self._giro[2])

    def consume_angulo(self) -> tuple[float, float, float]:
        valores, self._angulo = self._angulo, (0.0, 0.0, 0.0)
        return valores

    def start(self) -> bool:
        # `True` E NÃO `None`: `SensorHub._abrir_um` descarta o reader cujo
        # `start()` não afirma ter aberto. Um dublê que devolvesse `None`
        # nunca entraria no `_motion`, e a régua da demanda mediria um hub
        # vazio — verde sobre nada.
        return True

    def stop(self) -> None:
        pass


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, quanto: float) -> None:
        self.agora += quanto


def _hub_de_verdade(relogio: _Relogio, nodes: dict[str, Any]) -> Any:
    from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub

    hub = SensorHub(
        motion_factory=lambda uniq, node: _ReaderDeMotionFalso((0.0, 42.0, 0.0)),
        touch_factory=lambda uniq, node: _ReaderDeMotionFalso(),
        gamepad_factory=lambda uniq, node: _ReaderDeMotionFalso(),
        descobrir_motion=lambda: dict(nodes),
        descobrir_touch=dict,
        descobrir_gamepad=dict,
        relogio=relogio,
        auto_manutencao=False,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)
    return hub


def test_a_mira_ligada_mantem_o_reader_vivo() -> None:
    """ARRANQUE `self._demanda[uniq] = agora` das duas portas e este teste
    reprova: o TTL de 5 s apagaria o reader no meio da partida e a mira
    morreria sozinha, sem nenhum erro em lugar nenhum — que é a forma de
    defeito mais difícil de diagnosticar que existe."""
    relogio = _Relogio()
    hub = _hub_de_verdade(relogio, {_UNIQ: Path("/dev/input/event-de-mentira")})
    hub.velocidade_do_movimento(_UNIQ)
    hub.reconciliar()
    assert _UNIQ in hub._motion
    relogio.avancar(4.0)
    hub.angulo_do_movimento(_UNIQ)
    relogio.avancar(4.0)
    hub.reconciliar()
    assert _UNIQ in hub._motion, (
        "o reader morreu com 8 s de mira LIGADA — as portas não registram demanda")


def test_sem_reader_a_resposta_e_none_e_nao_zero() -> None:
    """ARRANQUE o `return None` e ponha `(0.0, 0.0, 0.0)`: este teste reprova.

    Zero é um controle PARADO; ausência de reader é outra coisa. Um painel (ou
    uma mira) alimentado por essa confusão descreve um aparelho que não está lá.
    """
    hub = _hub_de_verdade(_Relogio(), {})
    assert hub.velocidade_do_movimento("aa:bb:cc:00:00:99") is None
    assert hub.angulo_do_movimento("aa:bb:cc:00:00:99") is None


def test_a_porta_do_angulo_drena_e_a_da_velocidade_nao() -> None:
    """A separação é a entrega: duas chamadas de `angulo_do_movimento` no mesmo
    tique dividiriam o movimento entre dois consumidores, e a mira dela andaria
    pela metade. ARRANQUE a diferença e este teste reprova."""
    relogio = _Relogio()
    hub = _hub_de_verdade(relogio, {_UNIQ: Path("/dev/input/event-de-mentira")})
    hub.velocidade_do_movimento(_UNIQ)  # registra a demanda — o reader nasce dela
    hub.reconciliar()
    hub._motion[_UNIQ].definir_angulo((0.0, 5.0, 0.0))
    assert hub.velocidade_do_movimento(_UNIQ) == (0.0, 42.0, 0.0)
    assert hub.velocidade_do_movimento(_UNIQ) == (0.0, 42.0, 0.0), (
        "a porta da velocidade DRENOU — ela não pode roubar de ninguém")
    assert hub.angulo_do_movimento(_UNIQ) == (0.0, 5.0, 0.0)
    assert hub.angulo_do_movimento(_UNIQ) == (0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# E8 — A MIRA VALE NOS QUATRO, e não só no P1
# ---------------------------------------------------------------------------
#
# **ORDEM DELA, 21/09/2026:** *"cara nenhuma solução pode ser feita só pro p1"*.
#
# A primeira entrega desta sprint misturava o giro dentro do `dispatch_gamepad`
# — o caminho do PRIMÁRIO. Os jogadores 2 a 4 passam por
# `coop.CoopManager.forward_all`, que tem laço próprio, e ficariam de fora. Eu
# declarei isso como dívida no §10.3 e ela RECUSOU a declaração.
#
# Ela está certa, e a razão é o que o produto é: um roteador de adaptação para
# quem adapta o controle à própria deficiência. Uma feature de acessibilidade
# que só alcança o P1 obriga a pessoa a ser o P1 — e quem escolhe a ordem da
# mesa é o jogo, não ela.


class _VpadDoJogador:
    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


class _ReaderDoJogador:
    def __init__(self, botoes: frozenset[str] = frozenset()) -> None:
        self._botoes = botoes

    def snapshot(self) -> Any:
        return SimpleNamespace(lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                               buttons_pressed=self._botoes)


def _mesa_de_quatro(monkeypatch: pytest.MonkeyPatch, *, arranjo: Any,
                    giro_por_uniq: dict[str, tuple[float, float, float]],
                    botoes_por_uniq: dict[str, frozenset[str]] | None = None,
                    giro_ligado: dict[str, bool] | None = None,
                    ) -> dict[str, _VpadDoJogador]:
    """Monta P2, P3 e P4 no `CoopManager` e roda UM tique de `forward_all`.

    O P1 não entra aqui de propósito: ele tem régua própria (o
    `dispatch_gamepad`), e a pergunta desta seção é justamente se os OUTROS
    recebem o mesmo tratamento.
    """
    from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
    from hefesto_dualsense4unix.daemon.subsystems import coop as co
    from hefesto_dualsense4unix.daemon.subsystems.coop import (
        CoopManager,
        _SecondaryPlayer,
    )

    ligados = giro_ligado or {}
    monkeypatch.setattr(REGISTRO, "estado",
                        lambda uniq: SimpleNamespace(
                            giroscopio=ligados.get(uniq, True)))

    class _HubPorControle:
        def velocidade_do_movimento(self, uniq: str) -> Any:
            return giro_por_uniq.get(uniq)

        def angulo_do_movimento(self, uniq: str) -> Any:
            return (0.0, 0.0, 0.0)

    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    rot.definir_ativo(store, arranjo)
    daemon = SimpleNamespace(store=store, _mouse_device=None,
                             _garantir_sensor_hub=lambda: _HubPorControle())

    gerente = CoopManager.__new__(CoopManager)
    gerente._daemon = daemon  # type: ignore[attr-defined]
    gerente._players = {}  # type: ignore[attr-defined]
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)

    vpads: dict[str, _VpadDoJogador] = {}
    for n, uniq in enumerate(sorted(giro_por_uniq), start=2):
        vpad = _VpadDoJogador()
        vpads[uniq] = vpad
        gerente._players[uniq] = _SecondaryPlayer(  # type: ignore[attr-defined]
            identity=uniq,
            evdev_path=f"/dev/input/event{n}",
            reader=_ReaderDoJogador((botoes_por_uniq or {}).get(uniq, frozenset())),
            player_index=n,
            vpad=vpad,
        )
    gerente.forward_all()
    return vpads


_P2, _P3, _P4 = "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04"


def test_a_mira_vale_para_os_jogadores_2_3_e_4(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A ORDEM DELA NUMA LINHA. ARRANQUE a chamada de `aplicar_o_movimento` do
    `coop.forward_all` e este teste reprova.

    *"cara nenhuma solução pode ser feita só pro p1"* — e era exatamente o que
    a primeira entrega desta sprint fazia.
    """
    vpads = _mesa_de_quatro(
        monkeypatch, arranjo=_arranjo(sensibilidade=12),
        giro_por_uniq={_P2: (0.0, 200.0, 0.0), _P3: (0.0, 200.0, 0.0),
                       _P4: (0.0, 200.0, 0.0)})
    for uniq, vpad in sorted(vpads.items()):
        assert vpad.analog, f"{uniq} não recebeu nada"
        assert vpad.analog[0]["rx"] != 128, (
            f"o jogador {uniq} NÃO mirou por movimento — a mira só vale no P1")


def test_cada_jogador_le_o_proprio_giroscopio(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o `uniq=player.identity` e ponha um endereço fixo: este teste
    reprova.

    Três controles na mesa, um parado. Se o laço perguntasse sempre ao mesmo
    aparelho, o controle parado miraria junto — e o que se move na tela do
    jogo não seria o que a mão daquela pessoa fez.
    """
    vpads = _mesa_de_quatro(
        monkeypatch, arranjo=_arranjo(sensibilidade=12),
        giro_por_uniq={_P2: (0.0, 200.0, 0.0), _P3: (0.0, 0.0, 0.0),
                       _P4: (0.0, -200.0, 0.0)})
    assert vpads[_P2].analog[0]["rx"] > 128, "o P2 girou e não mirou"
    assert vpads[_P3].analog[0]["rx"] == 128, (
        "o P3 estava PARADO e a mira dele se mexeu — o laço leu o giro de outro")
    assert vpads[_P4].analog[0]["rx"] < 128, "o P4 girou ao contrário do P2"


def test_o_interruptor_de_sensor_e_por_controle_tambem_no_coop(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o portão do `REGISTRO` (ou passe o uniq errado) e este teste
    reprova: desligar o giroscópio de UM controle desligaria a mira de todos,
    ou de nenhum."""
    vpads = _mesa_de_quatro(
        monkeypatch, arranjo=_arranjo(sensibilidade=12),
        giro_por_uniq={_P2: (0.0, 200.0, 0.0), _P3: (0.0, 200.0, 0.0)},
        giro_ligado={_P3: False})
    assert vpads[_P2].analog[0]["rx"] != 128, "o P2 tinha o giro LIGADO"
    assert vpads[_P3].analog[0]["rx"] == 128, (
        "o P3 tinha o giro DESLIGADO por ela e mirou assim mesmo")


def test_o_gatilho_e_por_controle_no_coop(monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE `botoes=snap.buttons_pressed` e este teste reprova: o gatilho
    de um jogador ligaria a mira do outro."""
    vpads = _mesa_de_quatro(
        monkeypatch, arranjo=_arranjo(sensibilidade=12, gatilho="l2"),
        giro_por_uniq={_P2: (0.0, 200.0, 0.0), _P3: (0.0, 200.0, 0.0)},
        botoes_por_uniq={_P2: frozenset({remap.GATILHOS["l2"]})})
    assert vpads[_P2].analog[0]["rx"] != 128, "o P2 apertou o gatilho e não mirou"
    assert vpads[_P3].analog[0]["rx"] == 128, (
        "o P3 NÃO apertou o gatilho e mirou — o laço leu os botões de outro")


def test_sem_arranjo_o_coop_nao_paga_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """A régua de CUSTO no laço dos secundários: sem mira ligada, o tique não
    chama o motor nem uma vez por jogador."""
    vpads = _mesa_de_quatro(
        monkeypatch, arranjo=None,
        giro_por_uniq={_P2: (0.0, 900.0, 0.0), _P3: (0.0, 900.0, 0.0)})
    for vpad in vpads.values():
        assert vpad.analog[0]["rx"] == 128 and vpad.analog[0]["ry"] == 128


def test_os_dois_lacos_chamam_o_mesmo_motor() -> None:
    """ARRANQUE o import e copie o bloco para o `coop`: este teste reprova.

    Duas redações da mesma regra fazem a próxima cura alcançar UMA — que é o
    defeito que esta casa nomeia como *"cobrir um chamador deixa a próxima
    pessoa remedindo o mesmo defeito"*.
    """
    import inspect

    from hefesto_dualsense4unix.daemon.subsystems import coop, gamepad

    assert "aplicar_o_movimento" in inspect.getsource(coop.CoopManager.forward_all)
    assert coop.aplicar_o_movimento is gamepad.aplicar_o_movimento, (
        "o co-op tem a própria cópia do motor de mira")
