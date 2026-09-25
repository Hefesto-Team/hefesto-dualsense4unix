"""A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01 — reaplicar o perfil não escurece a barra.

**OS DOIS ACHADOS DA CONFERÊNCIA DA A-MARCA-DA-COR-NAO-SOME-01, 24/09/2026**,
medidos de novo antes da cura na mesa de quatro real (a `Mesa` daquela régua:
`IpcServer`, `ProfileManager.apply`, `SysfsLedNode` sobre arquivos e a paleta
de `make_auto_output_provider`), com o perfil a 82%:

1. **o brilho entrava duas vezes em quem não tem cor gravada.** O P1 a 60%
   acendia `(0,0,153)` pelo trilho e `(0,0,111)` a cada perfil reaplicado
   pelo boot, pela troca de jogo ou pelo autoswitch; o P4 a 30%, de
   `(76,0,38)` a `(27,0,13)`; o trilho seguinte a 40% publicava `(0,0,74)`.
   A RAIZ: o fator de brilho por controle (`backend._scaled_led`) caía sobre
   a cor RESOLVIDA, e com ela sobre o override por controle, que já traz o
   brilho dele. Quem tinha cor gravada não escurecia porque o manager não lhe
   publicava fator — a guarda estava na ponta errada. Pelo Salvar do rodapé o
   brilho também entrava duas vezes: ele gravava a luz ACESA como a cor
   escolhida, e a troca de perfil seguinte a escurecia de novo;
2. **sem a paleta, o fóssil ia para o tom de outra peça.** O do P3 saía no
   azul cheio `(0,0,255)`, ao lado do P1 azul a 82%, `(0,0,209)`: o byte
   estava livre, a cor não, e o brilho do P3 sumia.

A REGRA, em todo caminho (boot, troca manual, troca de jogo, autoswitch,
Salvar): a barra de cada controle acende a cor dele no brilho dele, numa conta
só — a mesma que o trilho faz —, e três aplicações seguidas do perfil dão o
mesmo byte que a primeira.

AS MORDIDAS, arrancadas e devolvidas com md5 (a lista está no relatório da
sprint): o `_scaled_led` de volta sobre a cor resolvida; o `rodape` gravando a
luz acesa; o `_scaled_led` pela razão em vez do `reescalar`; o
`_controllers_to_led_scales` pulando quem tem cor; o `_primeiro_tom_livre` com
o tom cheio e comparando bytes; o manager sem publicar o brilho do perfil; e o
`_brilho_da_peca_locked` sem o arredondamento.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.led_control import (
    LedSettings,
    PecaDaMesa,
    _acende_o_tom,
    cores_sem_colisao,
    player_slot_color,
    reescalar,
)
from tests.unit import test_a_marca_da_cor_nao_some as marca
from tests.unit.test_a_marca_da_cor_nao_some import (
    BRILHO_GLOBAL,
    COR_DELE,
    MACS,
    NOME,
    UNIQS,
    VERDE_AGUA,
    Mesa,
)

#: A PALETA AUTOMÁTICA, os oito tons do número.
PALETA = tuple(player_slot_color(n) for n in range(1, 9))


def _na(rgb: tuple[int, int, int], brilho: float) -> tuple[int, int, int]:
    """`rgb` no `brilho`, pela conta do dono (`LedSettings.apply_brightness`)."""
    return LedSettings(lightbar=rgb).apply_brightness(brilho).lightbar


#: O handle falso da `Mesa`, guardado antes de qualquer troca pelo transporte.
_HANDLE_DA_MESA = marca._handle_falso


def _handle(via: str) -> Any:
    """O handle falso da `Mesa`, no transporte pedido (`conType` é o que o backend lê)."""
    h = _HANDLE_DA_MESA()
    if via == "bt":
        h.conType = SimpleNamespace(name="BT")
    return h


@pytest.fixture
def mesa_de(tmp_path, monkeypatch):
    """A mesa de quatro da A-MARCA, com o transporte dos quatro escolhido."""
    import pacotes
    from pacotes import a04_iluminacao

    feitas: list[Mesa] = []

    def montar(alvo: str = "todos", via: str = "usb") -> Mesa:
        monkeypatch.setattr(marca, "_handle_falso", lambda: _handle(via))
        m = Mesa(tmp_path / f"mesa-{len(feitas)}", pacotes, a04_iluminacao, alvo=alvo)
        feitas.append(m)
        vias = {m.ctl._detect_transport(h) for h in m.ctl._handles.values()}
        assert vias == {via}, f"a mesa pediu {via} e o backend leu {vias}"
        return m

    yield montar
    for m in feitas:
        m.fechar()


def _luz(mesa: Mesa) -> list[tuple[int, int, int]]:
    """O que cada barra ACENDE: o nó de LED de cada controle, P1 a P4.

    E o nó tem de ser o que o produto decidiu (`_merged_desired_for_key`):
    uma luz que concorda com a régua e discorda do resolvido mediria o
    instrumento, não o produto.
    """
    acesas = []
    for m in MACS:
        no = mesa.ctl._sysfs[m].get_rgb()
        with mesa.ctl._io_lock:
            decidido = mesa.ctl._merged_desired_for_key(m).led
        assert no == decidido, f"o nó de {m} acende {no} e o produto decidiu {decidido}"
        acesas.append(no)
    return acesas


def _reaplicar(mesa: Mesa, caminho: str) -> None:
    """O perfil do disco aplicado de novo, pela porta de cada caminho do produto."""
    if caminho == "boot":
        # O daemon que nasce não tem a camada da mão: é o restauro de boot
        # (`origin="system"`) sobre ela vazia.
        mesa.ctl.clear_user_output_overrides()
        mesa.pm.apply(mesa._perfil(), origin="system")
    elif caminho == "troca-manual":
        mesa.rodar(mesa.server._handle_profile_switch({"name": NOME}))
    elif caminho == "troca-de-jogo":
        # O jogo abre com o perfil DELE e fecha devolvendo o dela — a prova
        # que ela faz com a mão: mexer no brilho, trocar de jogo e voltar.
        from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

        jogo = Profile(name="o-jogo", match=MatchAny(),
                       leds=LedsConfig(lightbar=(255, 255, 255), lightbar_brightness=0.4))
        mesa.pm.apply(jogo, origin="launch")
        mesa.pm.apply(mesa._perfil(), origin="autoswitch")
    elif caminho == "autoswitch":
        mesa.pm.apply(mesa._perfil(), origin="autoswitch")
    elif caminho == "salvar":
        from pacotes import rodape

        rodape.salvar(mesa.ctx(), {"tipo": "button", "evento": "click"}, None)
        mesa.pm.apply(mesa._perfil(), origin="system")
    else:
        raise AssertionError(caminho)


CAMINHOS = ["boot", "troca-manual", "troca-de-jogo", "autoswitch", "salvar"]


# ---------------------------------------------------------------------------
# 1. o brilho entra uma vez só — P1 a P4, USB e BT, «Todos» e um controle só
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("alvo", ["todos", "um"])
@pytest.mark.parametrize("caminho", CAMINHOS)
def test_reaplicar_tres_vezes_da_a_luz_da_primeira(mesa_de, caminho, alvo, via):
    """O trilho acende; o perfil reaplicado três vezes acende o mesmo byte.

    A mesa: P1 e P4 sem cor gravada (a paleta do número), P2 laranja e P3
    ciano escolhidos. O P1 vai a 60%, o P4 a 30% e o P2 a 50% pelo trilho; o
    P3 fica no brilho do perfil. A luz de cada um é a cor dele no brilho dele,
    numa conta só — a do trilho —, e três aplicações do perfil não a mexem.
    Depois, o trilho do P1 a 40% e mais uma aplicação.

    **A MORDIDA:** devolva o `_scaled_led` para depois do merge (sobre a cor
    resolvida) e o P1 e o P4 saem `(0,0,111)` e `(27,0,13)` já na primeira.
    """
    mesa = mesa_de(alvo, via)
    mesa.soltar(1, 60)
    mesa.soltar(4, 30)
    mesa.soltar(2, 50)
    brilho = {1: 0.60, 2: 0.50, 3: BRILHO_GLOBAL, 4: 0.30}
    esperada = [_na(COR_DELE[n], brilho[n]) for n in (1, 2, 3, 4)]
    assert _luz(mesa) == esperada, "o trilho não acendeu a conta de uma vez"
    for vez in (1, 2, 3):
        _reaplicar(mesa, caminho)
        assert _luz(mesa) == esperada, (
            f"{caminho}, {vez}ª aplicação: a barra saiu da luz da primeira")
    mesa.soltar(1, 40)
    esperada[0] = _na(COR_DELE[1], 0.40)
    assert _luz(mesa) == esperada, "o trilho a 40% depois das três aplicações"
    _reaplicar(mesa, caminho)
    assert _luz(mesa) == esperada, f"{caminho} depois do trilho a 40%"


def test_sem_no_o_produto_decide_a_mesma_luz(mesa_de):
    """O cabo sem o nó de LED do kernel: o que o produto DECIDE é o mesmo.

    Sem o nó a luz vai pelo fluxo da pydualsense no próximo `_reapply_desired`
    (limitação documentada do caminho degradado em
    `reassert_resolved_outputs`); o que se mede aqui é a decisão, que é o que
    esse caminho escreve.

    **A MORDIDA:** a do teste acima.
    """
    mesa = mesa_de()
    mesa.soltar(1, 60)
    mesa.soltar(4, 30)
    for m in MACS:
        mesa.ctl._sysfs[m] = None
    esperada = [_na(COR_DELE[1], 0.60), _na(COR_DELE[2], BRILHO_GLOBAL),
                _na(COR_DELE[3], BRILHO_GLOBAL), _na(COR_DELE[4], 0.30)]
    for caminho in ("boot", "troca-de-jogo", "autoswitch"):
        for _ in range(3):
            _reaplicar(mesa, caminho)
            with mesa.ctl._io_lock:
                decidida = [mesa.ctl._merged_desired_for_key(m).led for m in MACS]
            assert decidida == esperada, caminho


def test_o_salvar_grava_a_cor_pedida_e_nao_a_acesa(mesa_de):
    """O Salvar do rodapé guarda a cor de cada controle ANTES do brilho.

    A luz publicada é pós-brilho (D8). Gravada como a cor escolhida, ao lado
    do brilho do controle, ela era escalada de novo na aplicação seguinte: o
    P1 a 60% ia ao disco como `#000099`, e o trilho seguinte a 40% acendia
    `#00003D`.

    **A MORDIDA:** devolva o `rgb = list(base)` cru ao `rodape._draft_do_ativo`
    e esta reprova com o `(0, 0, 153)` no disco.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from pacotes import a04_iluminacao, rodape

    mesa = mesa_de()
    mesa.soltar(1, 60)
    mesa.soltar(2, 50)
    rodape.salvar(mesa.ctx(), {"tipo": "button", "evento": "click"}, None)
    disco = load_profile(NOME).controllers
    for n, cor in ((1, COR_DELE[1]), (2, COR_DELE[2])):
        leds = disco[a04_iluminacao.chave_do_override(UNIQS[n - 1])].leds
        assert tuple(leds.lightbar) == cor, (
            f"o Salvar gravou {tuple(leds.lightbar)} como a cor do P{n}, e ela é {cor}")


# ---------------------------------------------------------------------------
# 2. o brilho do controle vale para a cor do número de quem tem cor gravada
# ---------------------------------------------------------------------------
def test_o_fossil_volta_ao_numero_no_brilho_dele(mesa_de):
    """O P2 laranja a 50%, com a cor fóssil, volta ao vermelho a 50% — não a 82%.

    **A MORDIDA:** devolva o `"lightbar" in campos` à guarda de
    `manager._controllers_to_led_scales` e o P2 volta ao vermelho a 82%.
    """
    mesa = mesa_de()
    mesa.soltar(2, 50)
    mesa.fossilizar(2, escolhida_para=3)
    assert _luz(mesa)[1] == _na(player_slot_color(2), 0.50)


def test_o_preto_gravado_com_brilho_acende_a_paleta_no_brilho_dele(mesa_de):
    """O preto não é cor (22/09): o P3 com o preto e 30% acende o verde a 30%.

    **A MORDIDA:** a do teste acima; aqui o P3 acende o verde a 82%.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
    from pacotes import a04_iluminacao

    mesa = mesa_de()
    prof = load_profile(NOME)
    chave = a04_iluminacao.chave_do_override(UNIQS[2])
    dele = prof.controllers[chave]
    leds = dele.leds.model_copy(update={"lightbar": (0, 0, 0), "lightbar_brightness": 0.3})
    save_profile(prof.model_copy(update={"controllers": {
        **prof.controllers, chave: dele.model_copy(update={"leds": leds})}}),
        origem="regua")
    mesa.pm.apply(mesa._perfil(), origin="manual")
    assert _luz(mesa)[2] == _na(player_slot_color(3), 0.3)


def test_o_controle_acima_do_brilho_do_perfil_nao_perde_a_cor(mesa_de):
    """O perfil a 5% e o P1 a 100%: o azul volta inteiro, numa conta só.

    Pela razão, a cor do perfil (`(0,0,12)`) vezes vinte dava `(0,0,240)`: o
    controle de quem precisa de mais luz perdia a cor que o de menos luz tem.

    **A MORDIDA:** troque o `reescalar` do `_scaled_led` pela razão e esta
    reprova com o `(0, 0, 240)`.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

    mesa = mesa_de()
    mesa.soltar(1, 100)
    prof = load_profile(NOME)
    save_profile(prof.model_copy(update={"leds": prof.leds.model_copy(
        update={"lightbar_brightness": 0.05})}), origem="regua")
    mesa.pm.apply(mesa._perfil(), origin="manual")
    assert _luz(mesa)[0] == (0, 0, 255)
    assert _luz(mesa)[3] == _na(COR_DELE[4], 0.05)


def test_o_brilho_da_peca_nao_carrega_o_ruido_do_ponto_flutuante(mesa_de):
    """O perfil a 9%, o P4 a 50% e o P1 a 100%: o byte do trilho, sem um a menos.

    O fator é `0.5 / 0.09`, e a volta `0.09 * (0.5 / 0.09)` dá `0.4999…`: o
    rosa acendia `(127,0,63)` onde o trilho acende `(127,0,64)`, e o azul a
    100% saía `(0,0,254)`. Medido: 134 pares de percentuais erravam assim nos
    três tons com o 128.

    **A MORDIDA:** tire o `round(..., 9)` de `_brilho_da_peca_locked` e esta
    reprova com o `(127, 0, 63)`.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

    mesa = mesa_de()
    mesa.soltar(1, 100)
    mesa.soltar(4, 50)
    prof = load_profile(NOME)
    save_profile(prof.model_copy(update={"leds": prof.leds.model_copy(
        update={"lightbar_brightness": 0.09})}), origem="regua")
    for _ in range(3):
        mesa.pm.apply(mesa._perfil(), origin="manual")
        luz = _luz(mesa)
        assert luz[0] == (0, 0, 255)
        assert luz[3] == _na(COR_DELE[4], 0.50)


# ---------------------------------------------------------------------------
# 3. sem a paleta, o deslocado sai no brilho dele e num tom que ninguém acende
# ---------------------------------------------------------------------------
def _tons_de(luz: tuple[int, int, int]) -> set[tuple[int, int, int]]:
    return {t for t in PALETA if _acende_o_tom(luz, t)}


@pytest.mark.parametrize(("n", "para"), [(2, 3), (3, 2)], ids=["P2-fossil", "P3-fossil"])
@pytest.mark.parametrize("alvo", ["todos", "um"])
def test_sem_a_paleta_o_fossil_nao_cai_no_tom_de_outra_peca(mesa_de, n, para, alvo):
    """O fóssil deslocado acende um tom da paleta NO BRILHO DELE, livre pelo tom.

    O caso da conferência: o P1 azul escolhido, a paleta desligada, e o P3
    fóssil ia para o azul cheio ao lado do P1 azul a 82%. Aqui o fóssil é o
    P2 ou o P3, reaplicado três vezes, e de novo depois do trilho dele a 50%.

    **AS MORDIDAS:** o `_primeiro_tom_livre` com o tom cheio (sem
    `_na_escala`) reprova no brilho; com o `_tomado` comparando só bytes, o P3
    reprova no tom do P1.
    """
    mesa = mesa_de(alvo)
    mesa.clicar_no_tom(1, COR_DELE[1])
    mesa.desligar_a_paleta(VERDE_AGUA)
    mesa.fossilizar(n, escolhida_para=para)
    for brilho, passo in ((BRILHO_GLOBAL, "reaplicado"), (0.50, "trilho a 50%")):
        if brilho != BRILHO_GLOBAL:
            mesa.soltar(n, 50)
        for _ in range(3):
            mesa.pm.apply(mesa._perfil(), origin="manual")
            luz = _luz(mesa)
            dele = luz[n - 1]
            tom = next((t for t in PALETA if _na(t, brilho) == dele), None)
            assert tom is not None, (
                f"{passo}: o P{n} acende {dele}, que não é tom da paleta a {brilho}")
            for k, outra in enumerate(luz, start=1):
                if k != n:
                    assert tom not in _tons_de(outra), (
                        f"{passo}: o P{n} acende o tom {tom}, que o P{k} já acende em {outra}")


# ---------------------------------------------------------------------------
# 4. os donos das duas contas
# ---------------------------------------------------------------------------
def test_acende_o_tom_e_a_pergunta_do_tom_e_nao_do_byte():
    """O azul a 82% é o azul; o verde-água nunca é o verde nem o ciano."""
    azul = player_slot_color(1)
    assert _acende_o_tom((0, 0, 209), azul)
    assert _acende_o_tom(azul, azul)
    assert not _acende_o_tom((0, 0, 209), player_slot_color(8))
    assert not _acende_o_tom(_na(VERDE_AGUA, 0.82), player_slot_color(3))
    assert not _acende_o_tom(_na(VERDE_AGUA, 0.82), player_slot_color(6))
    # a conta do produto, em cada brilho do trilho, para os oito tons
    for pct in range(1, 101):
        for tom in PALETA:
            assert _acende_o_tom(_na(tom, pct / 100), tom), (tom, pct)


def test_reescalar_faz_a_conta_de_uma_vez_na_paleta_e_a_razao_fora_dela():
    """Tom único da paleta: a conta do trilho. Fora dela ou ambíguo: a razão."""
    for de in (0.05, 0.5, 0.82, 1.0):
        for para in (0.0, 0.3, 0.6, 1.0):
            for tom in PALETA:
                assert reescalar(_na(tom, de), de, para) == _na(tom, para), (tom, de, para)
    # o global dela, fora da paleta: vale a razão
    fora = _na((40, 80, 180), 0.82)
    assert reescalar(fora, 0.82, 0.41) == _na(fora, 0.41 / 0.82)
    # abaixo de 1% o vermelho, o rosa e o laranja acendem o mesmo (1, 0, 0):
    # não há tom único, e o brilho não troca a cor por palpite
    assert reescalar((1, 0, 0), 0.005, 1.0) == _na((1, 0, 0), 1.0 / 0.005)


def test_o_tom_livre_sai_no_brilho_da_peca():
    """A mesa pura da regra: o fóssil a 60% vai ao primeiro tom livre a 60%."""
    mesa = [
        PecaDaMesa(uniq="p1", pedida=_na(player_slot_color(1), 0.82),
                   do_numero=None, procedencia=1, numero=1, brilho=0.82),
        PecaDaMesa(uniq="p3", pedida=_na((0, 255, 255), 0.6), do_numero=None,
                   procedencia=2, numero=3, brilho=0.6),
    ]
    saida = cores_sem_colisao(mesa)
    assert saida["p1"] == (0, 0, 209)
    assert saida["p3"] == _na(player_slot_color(2), 0.6), saida
