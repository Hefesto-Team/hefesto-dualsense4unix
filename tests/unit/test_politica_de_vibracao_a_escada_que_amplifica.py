"""A escada da intensidade (30/100/150) e o teto que satura em 255.

Três decisões dela, de 11/08/2026:

1. **`Balanceado` passa de 0,7 a 1,0.** O tooltip da tela sempre prometeu *"do
   jeito que o jogo pediu, sem aumentar nem diminuir"*, e o número dizia outra
   coisa. Agora a promessa é verdade.
2. **`Máximo` passa de 1,0 a 1,5, e AMPLIFICA.** Um "Máximo" que valia 1,0 era
   idêntico a não mexer em nada. Amplificar é multiplicar **e saturar em 255**:
   sem a saturação, `200 * 1,5` daria 300, e 300 num byte é 44 — o motor cairia
   a um sexto justamente no pico. É a mordida principal deste arquivo.
3. **O deslizador vai até 200, e o esquema do perfil valida até 2,0 — mais que o
   botão, de propósito.** Os quatro botões são presets seguros; o deslizador é o
   ajuste livre de quem aceita o preço. O 2,0 no BOTÃO foi considerado e
   **descartado por ela**: satura a partir de 128, e metade da faixa que o jogo
   pede vira força constante (medição SATURA-01). A 1,5 satura a partir de 170 —
   um terço, não a metade.

E uma decisão de projeto, do mesmo dia: **`Auto` NUNCA amplifica**. Ele existe
para poupar bateria; a escada dele (1,0 / 0,7 / 0,3) é própria e não acompanha
o "Máximo".

**Este arquivo não importa GTK de propósito** (GUARDA-GI-REAL-01): tudo aqui é
conta, esquema e texto de `.glade` lido como arquivo. Um skip de módulo por
falta de PyGObject afundaria junto a prova da saturação, que é a que não pode
faltar. O que precisa de widget mora em
`test_politica_de_vibracao_o_alcance_na_tela.py`.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.rumble import RumbleEngine, _effective_mult
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_POLICY_MULT,
    reassert_rumble,
)
from hefesto_dualsense4unix.profiles.schema import (
    RUMBLE_CUSTOM_MULT_MAX,
    RumbleConfig,
)

_GLADE = (
    Path(__file__).resolve().parents[2]
    / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
)


def _config(policy: str, custom_mult: float = 1.0) -> DaemonConfig:
    cfg = DaemonConfig()
    cfg.rumble_policy = policy  # type: ignore[assignment]
    cfg.rumble_policy_custom_mult = custom_mult
    return cfg


def _propriedade_do_adjustment(nome: str) -> float:
    fonte = _GLADE.read_text(encoding="utf-8")
    bloco = re.search(
        r'<object class="GtkAdjustment" id="rumble_policy_adj">(.*?)</object>',
        fonte,
        re.DOTALL,
    )
    assert bloco is not None, "rumble_policy_adj sumiu do glade"
    achado = re.search(rf'<property name="{nome}">([\d.]+)</property>', bloco.group(1))
    assert achado is not None, f"o adjustment perdeu a propriedade {nome}"
    return float(achado.group(1))


# ---------------------------------------------------------------------------
# A escada
# ---------------------------------------------------------------------------


def test_a_escada_da_intensidade_e_30_100_150() -> None:
    """Os três degraus, no dono único, e cada um com a sua razão de ser."""
    assert RUMBLE_POLICY_MULT["economia"] == pytest.approx(0.3)
    # Se este voltar a 0,7, o tooltip do botão volta a mentir.
    assert RUMBLE_POLICY_MULT["balanceado"] == pytest.approx(1.0)
    # Se este voltar a 1,0, "Máximo" volta a ser idêntico a "Balanceado".
    assert RUMBLE_POLICY_MULT["max"] == pytest.approx(1.5)
    assert RUMBLE_POLICY_MULT["max"] > RUMBLE_POLICY_MULT["balanceado"], (
        'um botão chamado "Máximo" tem de entregar mais que o "Balanceado"'
    )


def test_balanceado_entrega_exatamente_o_que_o_jogo_pediu() -> None:
    """O que o tooltip promete: sem aumentar nem diminuir."""
    mult, _, _ = _effective_mult(_config("balanceado"), 80, 1.0, 1.0, 0.0)
    assert mult == pytest.approx(1.0)

    controller = MagicMock()
    engine = RumbleEngine(controller, time_fn=lambda: 1.0)
    engine.link(_config("balanceado"), None)
    engine.set(200, 137)
    engine.tick()
    controller.set_rumble.assert_called_once_with(weak=200, strong=137)


def test_maximo_amplifica_acima_do_que_o_jogo_pediu() -> None:
    controller = MagicMock()
    engine = RumbleEngine(controller, time_fn=lambda: 1.0)
    engine.link(_config("max"), None)
    engine.set(100, 60)
    engine.tick()
    mult = RUMBLE_POLICY_MULT["max"]
    controller.set_rumble.assert_called_once_with(
        weak=round(100 * mult), strong=round(60 * mult)
    )


@pytest.mark.parametrize("bruto", [200, 220, 255])
def test_amplificar_satura_em_255_e_nunca_da_a_volta(bruto: int) -> None:
    """A MORDIDA: amplificar é multiplicar **e** saturar.

    Sem o recorte em 255, `200 * 1,5 = 300`, e 300 escrito num byte é **44** —
    o motor cairia a um sexto exatamente no pico da cena. Um valor "acima do
    máximo" que vira lixo é pior que não amplificar.

    Os brutos desta lista estão TODOS acima do ponto de saturação do degrau
    (170, para mult 1,5) — a asserção afirma que dali para cima o motor fica
    NO teto, e é justamente por saturar que a variação some. O preço está
    medido e aceito: é por causa dele que o botão parou em 1,5 e não em 2,0.
    """
    assert bruto * RUMBLE_POLICY_MULT["max"] > 255, (
        "o bruto escolhido tem de estourar o teto, senão o teste não fala de "
        "saturação nenhuma"
    )
    controller = MagicMock()
    engine = RumbleEngine(controller, time_fn=lambda: 1.0)
    engine.link(_config("max"), None)
    engine.set(bruto, bruto)
    engine.tick()

    kwargs = controller.set_rumble.call_args.kwargs
    for valor in (kwargs["weak"], kwargs["strong"]):
        assert valor == 255, "acima do teto, o motor tem de ficar NO teto"
        assert 0 <= valor <= 255, "o valor tem de caber num byte de motor"


def test_o_caminho_do_rumble_fixado_tambem_satura() -> None:
    """O rumble que ELA fixa passa pela mesma conta — e satura igual.

    Duas conclusões numa: a intensidade vale também para a vibração fixada
    (o rodapé da aba diz isso, e é ele quem tem razão — `docs/usage/modos.md`
    dizia o contrário até 11/08/2026), e o recorte existe nos dois caminhos,
    não só no `RumbleEngine`.
    """
    daemon = MagicMock()
    daemon.config = _config("max")
    daemon.config.rumble_active = (200, 30)
    daemon.store.snapshot.return_value.controller.battery_pct = 80
    daemon._last_auto_mult = 1.0
    daemon._last_auto_change_at = 0.0

    reassert_rumble(daemon, 1.0)

    mult = RUMBLE_POLICY_MULT["max"]
    daemon.controller.set_rumble.assert_called_once_with(
        weak=min(255, round(200 * mult)),  # estoura o teto e para nele
        strong=round(30 * mult),  # bem abaixo do teto: amplifica de verdade
    )


# ---------------------------------------------------------------------------
# O teto, com um dono só
# ---------------------------------------------------------------------------


def test_o_teto_do_deslizador_e_o_do_esquema_do_perfil() -> None:
    teto = RUMBLE_CUSTOM_MULT_MAX
    assert teto == pytest.approx(2.0)
    assert _propriedade_do_adjustment("upper") == RUMBLE_CUSTOM_MULT_MAX * 100
    RumbleConfig(policy="custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX)


def test_o_deslizador_vai_mais_longe_que_o_botao_maximo() -> None:
    """Não é incoerência — é a divisão de papéis que ela decidiu em 11/08.

    Os quatro botões são presets SEGUROS: quem só quer clicar não pode cair
    numa armadilha, e por isso o Máximo parou em 1,5 (satura a partir de 170,
    um terço da faixa). O deslizador é o ajuste LIVRE de quem quer ir além e
    aceita o preço — a 2,0 satura a partir de 128, metade da faixa, e foi por
    isso que o 2,0 foi descartado como PRESET, não como limite.

    Igualar os dois apagaria a decisão nos dois sentidos: baixar o teto
    tiraria dela a escolha; subir o botão devolveria a armadilha.
    """
    teto_do_botao = RUMBLE_POLICY_MULT["max"]
    assert teto_do_botao < RUMBLE_CUSTOM_MULT_MAX, (
        "o preset ficou tão longe quanto o ajuste livre — some a diferença "
        "entre atalho seguro e escolha informada"
    )
    assert teto_do_botao > 1.0, 'e mesmo assim o "Máximo" tem de amplificar'


def test_o_rascunho_da_janela_aceita_o_mesmo_teto_do_perfil() -> None:
    """As duas pontas eram inconsistentes — o rascunho aceitava o que o perfil
    recusava, e a divergência só aparecia no "Salvar Perfil"."""
    from hefesto_dualsense4unix.app.draft_config import RumbleDraft

    RumbleDraft(policy="custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX)
    with pytest.raises(ValueError):
        RumbleDraft(policy="custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX + 0.1)


def test_o_deslizador_nasce_num_degrau_que_existe() -> None:
    """O valor de partida era 70 — o Balanceado velho. Virou âncora morta."""
    partida = _propriedade_do_adjustment("value")
    assert partida == RUMBLE_POLICY_MULT["balanceado"] * 100
    assert partida in {v * 100 for v in RUMBLE_POLICY_MULT.values()}


# ---------------------------------------------------------------------------
# O Auto nunca amplifica
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bateria", [0, 5, 19, 20, 35, 50, 51, 80, 100])
def test_o_auto_nunca_amplifica(bateria: int) -> None:
    """Ele existe para POUPAR bateria — amplificar seria o oposto, e sozinho."""
    mult, _, _ = _effective_mult(_config("auto"), bateria, 1.0, 1.0, 0.0)
    assert mult <= 1.0, "o Auto passou de 100% — ele nunca deve aumentar"
    assert any(
        mult == pytest.approx(degrau) for degrau in (1.0, 0.7, 0.3)
    ), f"degrau fora da escada própria do Auto: {mult}"


def test_o_texto_do_auto_na_tela_nao_promete_o_que_ele_nao_faz() -> None:
    """O rótulo dizia "100% (Máximo)" e "70% (Balanceado)".

    Os dois viraram mentira no dia em que Máximo passou a valer 200% e
    Balanceado 100%. E "debounce" é jargão, que ela nunca vê.
    """
    fonte = _GLADE.read_text(encoding="utf-8")
    # Só o TEXTO que ela lê — o comentário do XML ao redor não é tela, e
    # deixá-lo entrar aqui faria o portão reprovar a explicação da mudança.
    bloco = re.search(
        r'id="rumble_policy_auto_label">.*?<property name="label"[^>]*>(.*?)</property>',
        fonte,
        re.DOTALL,
    )
    assert bloco is not None, "o rótulo do Auto sumiu do glade"
    texto = bloco.group(1)
    assert "(Máximo)" not in texto
    assert "(Balanceado)" not in texto
    assert "debounce" not in texto.lower()
    assert "nunca passa de 100%" in texto, (
        "o rótulo tem de DIZER que o Auto não amplifica"
    )


def test_o_glade_tem_o_rotulo_do_aviso_de_alcance() -> None:
    """Sem o widget no glade, a função que escreve o aviso nunca chega à tela.

    O comportamento dela está em `test_politica_de_vibracao_o_alcance_na_tela`;
    aqui só se confere que existe onde pendurá-lo, e isto é leitura de arquivo.
    """
    assert 'id="rumble_policy_aviso"' in _GLADE.read_text(encoding="utf-8")
