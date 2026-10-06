"""A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01 — reaplicar o perfil não escurece a barra."""
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
    GLOBAL,
    MACS,
    NOME,
    UNIQS,
    VERDE_AGUA,
    Mesa,
)
from tests.unit.ponte_do_rodape import PonteDoRodape

PALETA = tuple(player_slot_color(n) for n in range(1, 9))

CLIQUE_DA_04 = {"tipo": "button", "evento": "click",
                "pagina": "04-iluminacao.html"}  # (noqa-acento: chave do clique)


def _na(rgb: tuple[int, int, int], brilho: float) -> tuple[int, int, int]:
    """`rgb` no `brilho`, pela conta do dono (`LedSettings.apply_brightness`)."""
    return LedSettings(lightbar=rgb).apply_brightness(brilho).lightbar


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
    """O que cada barra ACENDE: o nó de LED de cada controle, P1 a P4."""
    acesas = []
    for m in MACS:
        no = mesa.ctl._sysfs[m].get_rgb()
        with mesa.ctl._io_lock:
            decidido = mesa.ctl._merged_desired_for_key(m).led
        assert no == decidido, f"o nó de {m} acende {no} e o produto decidiu {decidido}"
        acesas.append(no)
    return acesas


class _PonteDoRodape:
    """A ponte do rodapé com o `profile.reaplicar` entregue ao handler REAL."""

    def __init__(self, mesa: Mesa) -> None:
        self.mesa = mesa

    def profile_reaplicar(self, nome: str) -> dict[str, Any]:
        return self.mesa.rodar(self.mesa.server._handle_profile_reaplicar({"name": nome}))

    def __getattr__(self, nome: str) -> Any:
        raise AttributeError(f"a régua não previu o rodapé chamar a ponte em {nome!r}")


def _reaplicar(mesa: Mesa, caminho: str) -> None:
    """O perfil do disco aplicado de novo, pela porta de cada caminho do produto."""
    if caminho == "boot":
        mesa.ctl.clear_user_output_overrides()
        mesa.pm.apply(mesa._perfil(), origin="system")
    elif caminho == "troca-manual":
        mesa.rodar(mesa.server._handle_profile_switch({"name": NOME}))
    elif caminho == "troca-de-jogo":
        from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

        jogo = Profile(name="o-jogo", match=MatchAny(),
                       leds=LedsConfig(lightbar=(255, 255, 255), lightbar_brightness=0.4))
        mesa.pm.apply(jogo, origin="launch")
        mesa.pm.apply(mesa._perfil(), origin="autoswitch")
    elif caminho == "autoswitch":
        mesa.pm.apply(mesa._perfil(), origin="autoswitch")
    elif caminho == "aplicar":
        from pacotes import rodape

        rodape.aplicar(mesa.ctx(), {"tipo": "button", "evento": "click"},
                       _PonteDoRodape(mesa))
    elif caminho == "salvar":
        from pacotes import rodape

        rodape.salvar(mesa.ctx(), CLIQUE_DA_04, PonteDoRodape())
        mesa.pm.apply(mesa._perfil(), origin="system")
    else:
        raise AssertionError(caminho)


CAMINHOS = ["boot", "troca-manual", "troca-de-jogo", "autoswitch", "aplicar", "salvar"]


CAMINHOS_COM_O_PISO = CAMINHOS


@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("alvo", ["todos", "um"])
@pytest.mark.parametrize("caminho", CAMINHOS_COM_O_PISO)
def test_reaplicar_tres_vezes_da_a_luz_da_primeira(mesa_de, caminho, alvo, via):
    """O trilho acende; o perfil reaplicado três vezes acende o mesmo byte."""
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


@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("alvo", ["todos", "um"])
@pytest.mark.parametrize("caminho", CAMINHOS_COM_O_PISO)
def test_sem_a_paleta_o_global_acende_a_conta_do_trilho(mesa_de, caminho, alvo, via):
    """Sem a paleta, o controle no GLOBAL com o brilho dele acende o byte do trilho."""
    mesa = mesa_de(alvo, via)
    mesa.clicar_no_tom(1, COR_DELE[1])
    mesa.desligar_a_paleta(GLOBAL)
    mesa.soltar(1, 60)
    mesa.soltar(2, 50)
    mesa.soltar(4, 30)
    esperada = [_na(COR_DELE[1], 0.60), _na(COR_DELE[2], 0.50),
                _na(COR_DELE[3], BRILHO_GLOBAL), _na(GLOBAL, 0.30)]
    assert _luz(mesa) == esperada, "o trilho não acendeu a conta de uma vez"
    for vez in (1, 2, 3):
        _reaplicar(mesa, caminho)
        assert _luz(mesa) == esperada, f"{caminho}, {vez}ª aplicação sem a paleta"


def test_sem_a_paleta_o_global_nao_perde_o_tom_com_o_perfil_quase_apagado(mesa_de):
    """O perfil a 2% e o P4 no global a 100%: o `#2850B4` inteiro, sem perder o vermelho."""
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

    mesa = mesa_de()
    mesa.desligar_a_paleta(GLOBAL)
    mesa.soltar(4, 100)
    prof = load_profile(NOME)
    save_profile(prof.model_copy(update={"leds": prof.leds.model_copy(
        update={"lightbar_brightness": 0.02})}), origem="regua")
    for _ in range(3):
        mesa.pm.apply(mesa._perfil(), origin="manual")
        assert _luz(mesa)[3] == GLOBAL


def test_a_cor_do_perfil_e_o_par_do_brilho(mesa_de):
    """Publicar o brilho sem a cor diz «não se sabe o global», e o preto não é cor."""
    ctl = mesa_de().ctl
    ctl.set_led_scales(None, brilho_do_perfil=0.5, cor_do_perfil=(40, 80, 180))
    assert ctl._cor_do_perfil == (40, 80, 180)
    ctl.set_led_scales(None, brilho_do_perfil=0.5, cor_do_perfil=(0, 0, 0))
    assert ctl._cor_do_perfil is None, "o preto não é cor"
    ctl.set_led_scales(None, brilho_do_perfil=0.5, cor_do_perfil=[40, 80, 180])
    ctl.set_led_scales(None, brilho_do_perfil=0.5)
    assert ctl._cor_do_perfil is None, "o brilho sem a cor ficou com o global de antes"


def test_sem_no_o_produto_decide_a_mesma_luz(mesa_de):
    """O cabo sem o nó de LED do kernel: o que o produto DECIDE é o mesmo."""
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


def test_o_salvar_nao_grava_a_luz_acesa_como_a_cor(mesa_de):
    """O Salvar do rodapé regrava a cor de cada controle como o disco a tem."""
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from pacotes import a04_iluminacao, rodape

    mesa = mesa_de()
    mesa.soltar(1, 60)
    mesa.soltar(2, 50)
    antes = load_profile(NOME).controllers
    rodape.salvar(mesa.ctx(), CLIQUE_DA_04, PonteDoRodape())
    depois = load_profile(NOME).controllers
    for n in (1, 2):
        chave = a04_iluminacao.chave_do_override(UNIQS[n - 1])
        assert depois[chave].leds == antes[chave].leds, (
            f"o Salvar mudou a luz do P{n} no disco: {antes[chave].leds} -> "
            f"{depois[chave].leds}")
        cor, acesa = depois[chave].leds.lightbar, _luz(mesa)[n - 1]
        assert cor is None or tuple(cor) != acesa, (
            f"o Salvar gravou a luz acesa {acesa} como a cor do P{n}")


def test_sem_a_paleta_o_salvar_grava_o_global_e_nao_a_luz(mesa_de):
    """Sem a paleta, o global dela (`#2850B4`) acende fora dos catorze tons."""
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from pacotes import a04_iluminacao, rodape

    global_dela = marca.GLOBAL
    mesa = mesa_de()
    mesa.clicar_no_tom(1, COR_DELE[1])
    mesa.desligar_a_paleta(global_dela)
    acesa = _luz(mesa)[3]
    assert acesa == _na(global_dela, BRILHO_GLOBAL), "a régua precisa do P4 no global"
    for _ in range(3):
        rodape.salvar(mesa.ctx(), CLIQUE_DA_04, PonteDoRodape())
        mesa.pm.apply(mesa._perfil(), origin="manual")
        assert _luz(mesa)[3] == acesa, "o Salvar e a troca escureceram o P4"
    prof = load_profile(NOME)
    dele = (prof.controllers or {}).get(a04_iluminacao.chave_do_override(UNIQS[3]))
    leds = getattr(dele, "leds", None)
    no_disco = (tuple(leds.lightbar) if leds is not None
                and "lightbar" in leds.model_fields_set else tuple(prof.leds.lightbar))
    assert no_disco == global_dela, f"o Salvar deu ao P4 a cor {no_disco} no disco"


@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("alvo", ["todos", "um"])
@pytest.mark.parametrize("o_que_mudou", ["brilho-do-controle", "brilho-do-perfil"])
def test_o_aplicar_acende_o_brilho_que_o_disco_diz(mesa_de, o_que_mudou, alvo, via):
    """O «Aplicar» leva à barra o brilho do disco, e não só ao resolvido."""
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
    from pacotes import rodape

    mesa = mesa_de(alvo, via)
    mesa.soltar(1, 60)
    mesa.pm.apply(mesa._perfil(), origin="manual")
    if o_que_mudou == "brilho-do-controle":
        mesa.gravar_o_brilho(1, 0.3)
        brilho = {1: 0.3, 2: BRILHO_GLOBAL, 3: BRILHO_GLOBAL, 4: BRILHO_GLOBAL}
    else:
        prof = load_profile(NOME)
        save_profile(prof.model_copy(update={"leds": prof.leds.model_copy(
            update={"lightbar_brightness": 0.5})}), origem="regua")
        brilho = {1: 0.60, 2: 0.5, 3: 0.5, 4: 0.5}
    esperada = [_na(COR_DELE[n], brilho[n]) for n in (1, 2, 3, 4)]
    for vez in (1, 2, 3):
        rodape.aplicar(mesa.ctx(), {"tipo": "button", "evento": "click"},
                       _PonteDoRodape(mesa))
        assert _luz(mesa) == esperada, f"{vez}º «Aplicar» depois do disco mudar"


def test_o_fossil_volta_ao_numero_no_brilho_dele(mesa_de):
    """O P2 laranja a 50%, com a cor fóssil, volta ao vermelho a 50% — não a 82%."""
    mesa = mesa_de()
    mesa.soltar(2, 50)
    mesa.fossilizar(2, escolhida_para=3)
    assert _luz(mesa)[1] == _na(player_slot_color(2), 0.50)


def test_o_preto_gravado_com_brilho_acende_a_paleta_no_brilho_dele(mesa_de):
    """O preto não é cor (22/09): o P3 com o preto e 30% acende o verde a 30%."""
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
    """O perfil a 5% e o P1 a 100%: o azul volta inteiro, numa conta só."""
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
    """O perfil a 9%, o P4 a 50% e o P1 a 100%: o byte do trilho, sem um a menos."""
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


def _tons_de(luz: tuple[int, int, int]) -> set[tuple[int, int, int]]:
    return {t for t in PALETA if _acende_o_tom(luz, t)}


@pytest.mark.parametrize(("n", "para"), [(2, 3), (3, 2)], ids=["P2-fossil", "P3-fossil"])
@pytest.mark.parametrize("alvo", ["todos", "um"])
def test_sem_a_paleta_o_fossil_nao_cai_no_tom_de_outra_peca(mesa_de, n, para, alvo):
    """O fóssil deslocado acende um tom da paleta NO BRILHO DELE, livre pelo tom."""
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


@pytest.mark.parametrize("alvo", ["todos", "um"])
def test_sem_a_paleta_o_fossil_nao_cai_no_tom_do_global(mesa_de, alvo):
    """O global é um tom da paleta, e o fóssil deslocado não cai nele."""
    mesa = mesa_de(alvo)
    mesa.desligar_a_paleta(player_slot_color(1))
    mesa.fossilizar(3, escolhida_para=2)
    mesa.soltar(3, 50)
    for _ in range(3):
        mesa.pm.apply(mesa._perfil(), origin="manual")
        luz = _luz(mesa)
        assert luz[0] == _na(player_slot_color(1), BRILHO_GLOBAL), "o P1 fica no global"
        tom = next((t for t in PALETA if _na(t, 0.5) == luz[2]), None)
        assert tom is not None, f"o P3 acende {luz[2]}, que não é tom da paleta a 50%"
        for k, outra in enumerate(luz, start=1):
            if k != 3:
                assert tom not in _tons_de(outra), (
                    f"o P3 acende o tom {tom}, que o P{k} já acende em {outra}")


def test_o_deslocado_nao_cai_no_tom_de_quem_fica():
    """A mesa pura: o deslocado evita o tom de quem fica, venha antes ou depois."""
    from hefesto_dualsense4unix.core.led_control import DO_GLOBAL

    azul = player_slot_color(1)
    ciano = (0, 255, 255)
    saida = cores_sem_colisao([
        PecaDaMesa(uniq="p1", pedida=_na(azul, 0.82), do_numero=None,
                   procedencia=DO_GLOBAL, numero=1, brilho=0.82),
        PecaDaMesa(uniq="p3", pedida=_na(ciano, 0.5), do_numero=None,
                   procedencia=2, numero=3, brilho=0.5),
    ])
    assert saida["p1"] == _na(azul, 0.82)
    assert azul not in _tons_de(saida["p3"]), saida
    saida = cores_sem_colisao([
        PecaDaMesa(uniq="p1", pedida=_na(ciano, 0.82), do_numero=None,
                   procedencia=2, numero=1, brilho=0.82),
        PecaDaMesa(uniq="p4", pedida=_na(azul, 0.5), do_numero=None,
                   procedencia=4, numero=4, brilho=0.5),
    ])
    assert saida["p4"] == _na(azul, 0.5)
    assert azul not in _tons_de(saida["p1"]), saida


def test_acende_o_tom_e_a_pergunta_do_tom_e_nao_do_byte():
    """O azul a 82% é o azul; o verde-água nunca é o verde nem o ciano."""
    azul = player_slot_color(1)
    assert _acende_o_tom((0, 0, 209), azul)
    assert _acende_o_tom(azul, azul)
    assert not _acende_o_tom((0, 0, 209), player_slot_color(8))
    assert not _acende_o_tom(_na(VERDE_AGUA, 0.82), player_slot_color(3))
    assert not _acende_o_tom(_na(VERDE_AGUA, 0.82), player_slot_color(6))
    for pct in range(1, 101):
        for tom in PALETA:
            assert _acende_o_tom(_na(tom, pct / 100), tom), (tom, pct)


def test_reescalar_faz_a_conta_de_uma_vez_na_paleta_e_a_razao_fora_dela():
    """Tom único da paleta: a conta do trilho. Fora dela ou ambíguo: a razão."""
    for de in (0.05, 0.5, 0.82, 1.0):
        for para in (0.0, 0.3, 0.6, 1.0):
            for tom in PALETA:
                assert reescalar(_na(tom, de), de, para) == _na(tom, para), (tom, de, para)
    from hefesto_dualsense4unix.core.led_control import _escala_crua, fator_do_brilho

    fora = _na((40, 80, 180), 0.82)
    assert reescalar(fora, 0.82, 0.41) == _escala_crua(
        fora, fator_do_brilho(0.41) / fator_do_brilho(0.82))
    assert reescalar(fora, 0.82, 0.41, ((40, 80, 180),)) == _na((40, 80, 180), 0.41)
    assert reescalar((1, 0, 0), 0.005, 1.0) == _escala_crua(
        (1, 0, 0), fator_do_brilho(1.0) / fator_do_brilho(0.005))


def test_o_tom_livre_sai_no_brilho_da_peca():
    """A mesa pura da regra: o fóssil a 60% vai ao primeiro tom livre a 60%."""
    mesa = [
        PecaDaMesa(uniq="p1", pedida=_na(player_slot_color(1), 0.82),
                   do_numero=None, procedencia=1, numero=1, brilho=0.82),
        PecaDaMesa(uniq="p3", pedida=_na((0, 255, 255), 0.6), do_numero=None,
                   procedencia=2, numero=3, brilho=0.6),
    ]
    saida = cores_sem_colisao(mesa)
    assert saida["p1"] == _na(player_slot_color(1), 0.82)
    assert saida["p3"] == _na(player_slot_color(2), 0.6), saida
