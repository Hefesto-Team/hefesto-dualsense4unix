"""O PRETO É BANIDO COMO COR DE LIGHTBAR — ordem dela, 22/09/2026.

**A QUEIXA, com as palavras dela:** *"pq o lightbar do starlight blue sempre
desliga após conectar? mesmo o perfil atual não mandando ele desligar e ter
cor? isso é só com ele, independente da ordem"*.

**O PERFIL MANDAVA.** Medido no disco dela no mesmo minuto: a peça daquele
controle tinha `leds.lightbar: [0, 0, 0]`, escrita por um "Salvar Perfil" às
13:53 daquele dia — o Salvar leu *"não sei a cor"* (`lightbar_rgb is None`) e
gravou PRETO. E não era um controle só: **sete dos 29 perfis dela** guardam o
preto na seção GLOBAL, e neles abrir o jogo apagava a barra dos quatro.

**A ORDEM:** *"vamos banir esse preto de aparecer independente do controle
tambem"*. <!-- noqa-acento: citação literal dela -->

O QUE ESTA RÉGUA COBRA, nos cinco pontos do caminho:

1. a leitura (`led_control.cor_escolhida`) — preto é *"sem opinião"*;
2. a aplicação da peça (`_controllers_to_specs`) — peça preta não escreve cor;
3. a aplicação do global (`ProfileManager.apply`) — global preto não escreve;
4. a gravação (`draft_config`) — sem cor lida, o arquivo fica sem o campo;
5. a leitura do arquivo VELHO (`_leds_config_to_draft`) — o preto que já está
   no disco chega à tela como *"sem cor"*, e o Salvar seguinte não o reescreve.

E O CONTRAPESO: **apagar a barra continua possível pelo
brilho**. `lightbar_brightness = 0.0` zera os três canais DEPOIS da escolha da
cor, e essa é a mão dela — o banimento tira do produto o direito de apagar
sozinho, não tira dela o apagar.
"""

from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.core.led_control import PRETO, cor_escolhida
from hefesto_dualsense4unix.profiles.manager import _controllers_to_specs
from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, LedsConfig

#: A faixa sintética da casa — octetos 4 e 5 zerados.
UNIQ = "aa:bb:cc:00:00:01"
#: A cor global do perfil dela, para a peça ter de que divergir.
AZUL = (40, 80, 180)


# ---------------------------------------------------------------------------
# 1. a leitura
# ---------------------------------------------------------------------------
def test_o_preto_nao_e_escolha_e_a_cor_de_verdade_e() -> None:
    """MORDIDA: faça `cor_escolhida` devolver `rgb` sempre — reprova aqui."""
    assert cor_escolhida(PRETO) is None
    assert cor_escolhida((0, 0, 0)) is None
    assert cor_escolhida(AZUL) == AZUL
    assert cor_escolhida(None) is None
    # Um canal aceso já é escolha: o quase-preto NÃO é banido, porque ele só
    # pode ter vindo de alguém escolhendo.
    assert cor_escolhida((0, 0, 1)) == (0, 0, 1)


# ---------------------------------------------------------------------------
# 2. a peça por controle — o caso DELA
# ---------------------------------------------------------------------------
def _spec_da_peca(rgb: tuple[int, int, int], *, brilho: float = 1.0) -> Any:
    peca = ControllerOverrides(
        leds=LedsConfig(lightbar=rgb, lightbar_brightness=brilho)
    )
    saida = _controllers_to_specs({UNIQ: peca}, LedsConfig(lightbar=AZUL))
    return saida.get(UNIQ)


def test_a_peca_preta_nao_escreve_cor_nenhuma() -> None:
    """A peça do Starlight Blue, como estava no disco dela.

    MORDIDA: tire o `cor_escolhida(rgb) is None` de `_controllers_to_specs` e
    a barra volta a receber `(0, 0, 0)` em toda conexão.
    """
    spec = _spec_da_peca(PRETO)
    assert spec is None or spec.led is None, (
        "a peça preta voltou a mandar cor para o aparelho")


def test_a_peca_com_cor_continua_escrevendo() -> None:
    """A cura não pode calar a peça que tem cor — seria o defeito ao contrário."""
    spec = _spec_da_peca((128, 0, 255))
    assert spec is not None and spec.led == (128, 0, 255)


def test_o_brilho_zero_continua_apagando_a_peca() -> None:
    """O contrapeso: apagar pelo brilho é a mão dela, e ela continua valendo."""
    spec = _spec_da_peca((128, 0, 255), brilho=0.0)
    assert spec is not None and spec.led == (0, 0, 0), (
        "o brilho 0 parou de apagar — o banimento comeu o apagar dela")


# ---------------------------------------------------------------------------
# 3. o global — os sete perfis de jogo dela
# ---------------------------------------------------------------------------
class _ControleDeMentira:
    """Só o que a ativação do perfil chama, e guardando o que recebeu."""

    def __init__(self) -> None:
        self.specs: list[Any] = []

    def apply_output_defaults(self, spec: Any) -> None:
        self.specs.append(spec)

    def __getattr__(self, nome: str) -> Any:  # pragma: no cover - borda
        def _qualquer(*_a: Any, **_k: Any) -> None:
            return None

        return _qualquer


def _led_do_global(rgb: tuple[int, int, int], *, brilho: float = 1.0) -> Any:
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    controle = _ControleDeMentira()
    manager = ProfileManager(controller=controle, store=None)
    perfil = Profile(
        name="régua",
        match=MatchAny(),
        leds=LedsConfig(lightbar=rgb, lightbar_brightness=brilho),
    )
    manager.apply(perfil, origin="manual")
    assert controle.specs, "a ativação não chamou `apply_output_defaults`"
    return controle.specs[0].led


def test_o_global_preto_nao_apaga_os_quatro() -> None:
    """Sete perfis de jogo dela guardavam isto — e apagavam a mesa inteira.

    MORDIDA: devolva `led=effective.lightbar` ao `ProfileManager.apply`.
    """
    assert _led_do_global(PRETO) is None


def test_o_global_com_cor_continua_escrevendo() -> None:
    assert _led_do_global(AZUL) == AZUL


def test_o_brilho_zero_continua_apagando_o_global() -> None:
    assert _led_do_global(AZUL, brilho=0.0) == (0, 0, 0)


# ---------------------------------------------------------------------------
# 4. a gravação — a porta por onde o preto entrou
# ---------------------------------------------------------------------------
def test_sem_cor_lida_o_arquivo_fica_sem_o_campo() -> None:
    """`lightbar_rgb is None` é *"não sei"*, e não vira byte no disco.

    MORDIDA: devolva `leds.lightbar_rgb or (0, 0, 0)` ao
    `_leds_draft_to_config` — o campo volta, preto, e a peça nasce apagando.
    """
    from hefesto_dualsense4unix.app.draft_config import (
        LedsDraft,
        _leds_draft_to_config,
    )

    cfg = _leds_draft_to_config(LedsDraft(lightbar_rgb=None))
    assert "lightbar" not in cfg.model_fields_set, cfg.model_dump()
    com_cor = _leds_draft_to_config(LedsDraft(lightbar_rgb=AZUL))
    assert com_cor.lightbar == AZUL


def test_o_preto_que_ja_esta_no_disco_chega_a_tela_como_sem_cor() -> None:
    """Os sete perfis de jogo dela — o preto já gravado não vira escolha.

    Sem esta linha o círculo se fecharia: o arquivo velho pintaria a tela de
    preto e o Salvar seguinte o reescreveria, com o banimento de pé.

    MORDIDA: devolva o `(int(rgb_raw[0]), …)` direto ao `LedsDraft` em
    `_leds_config_to_draft`.
    """
    from hefesto_dualsense4unix.app.draft_config import _leds_config_to_draft

    assert _leds_config_to_draft(LedsConfig(lightbar=PRETO)).lightbar_rgb is None
    assert _leds_config_to_draft(LedsConfig(lightbar=AZUL)).lightbar_rgb == AZUL


def test_sem_cor_lida_nao_nasce_peca_por_controle() -> None:
    """O Salvar com um controle sem leitura não inventa peça para ele.

    MORDIDA: tire o `leds.lightbar_rgb is not None` de `with_controller_leds`.
    """
    from hefesto_dualsense4unix.app.draft_config import DraftConfig, LedsDraft

    draft = DraftConfig()
    draft = draft.model_copy(
        update={"leds": draft.leds.model_copy(update={"lightbar_rgb": AZUL})}
    )
    depois = draft.with_controller_leds(UNIQ, LedsDraft(lightbar_rgb=None))
    peca = depois.controller_override(UNIQ)
    campos = set(peca.leds.model_fields_set if peca and peca.leds else set())
    assert "lightbar" not in campos, campos
