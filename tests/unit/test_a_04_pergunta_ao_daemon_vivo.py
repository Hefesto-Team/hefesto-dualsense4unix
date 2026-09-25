"""A-04-PERGUNTA-AO-DAEMON-VIVO-01 — a aba Iluminação mostra o que está aceso.

**MEDIDO ANTES DA CURA, 25/09/2026**, na mesa de quatro real da A-MARCA
(`IpcServer`, `ProfileManager.apply`, o merge do `PyDualSenseController` e
`SysfsLedNode` sobre arquivos), com o perfil A a 82% e o B a 82% no Fraco:

    o P3 clicado em Forte, autoswitch para o B   aparelho Forte · pílula Fraco
    o P1 solto a 60%, autoswitch para o B        barra (0,0,153) · trilho «82%»
    sem a paleta, o P3 fóssil deslocado para o   o trilho a 50% mandou o ciano
    azul pelo daemon                             fóssil, e a barra acendeu ciano
    o P2 «Desligado»: troca manual, boot, Salvar a barra voltava (209,0,0), e o
                                                 disco tinha perdido o laranja

A REGRA DA CASA: *pergunte ao daemon vivo, não ao perfil*. O daemon publica
`brilho_da_barra` e `brilho_das_luzes` por controle (`_brilhos_acesos`, do
dono do merge), a aba lê dali e cai no disco quando ele não diz; e o
«Desligar» é o brilho em 0% (`D-2509-O-DESLIGAR-E-O-BRILHO-EM-ZERO`).

A MESA é a da A-MARCA com duas coisas a mais, as duas do produto: o tique
publica os dois brilhos pelo MESMO método que o `state_full` chama, e a
ponte leva a pílula ao handler real do `led.player_brightness_set`.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.led_control import (
    BRILHOS_DAS_LUZES,
    LedSettings,
    player_slot_color,
)
from tests.unit import test_a_marca_da_cor_nao_some as marca
from tests.unit.test_a_marca_da_cor_nao_some import (
    BRILHO_GLOBAL,
    COR_DELE,
    GLOBAL,
    LARANJA,
    MACS,
    NOME,
    UNIQS,
    Mesa,
)

#: O perfil para onde a troca AUTOMÁTICA vai: o mesmo global, sem opinião
#: por controle, e as luzes no Fraco.
NOME_B = "regua-a04-b"
IDS = ["P1", "P2", "P3", "P4"]
ROXO = player_slot_color(8)


def _na(rgb: tuple[int, int, int], brilho: float) -> tuple[int, int, int]:
    return LedSettings(lightbar=rgb).apply_brightness(brilho).lightbar


class _Ponte(marca.PonteDoDaemon):
    """A ponte da A-MARCA, com a pílula entregue ao handler REAL."""

    def player_led_brightness_set_detalhado(self, brilho: str,
                                            uniq: str | None = None) -> Any:
        payload: dict[str, Any] = {"brilho": brilho}
        if uniq:
            payload["uniq"] = uniq
        self.enviados.append(payload)
        return self.mesa.rodar(self.mesa.server._handle_led_player_brightness_set(payload))


class MesaViva(Mesa):
    """A mesa da A-MARCA com o tique que publica os brilhos, e o perfil ativo que anda."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.ativo = NOME
        super().__init__(*args, **kwargs)
        self.ponte = _Ponte(self)

    def publicado(self) -> list[dict[str, Any]]:
        """O tique do `state_full`, com os dois brilhos pelo método que ele chama."""
        saida = super().publicado()
        for entrada in saida:
            entrada.update(self.server._brilhos_acesos(entrada["uniq"]))
        return saida

    def ctx(self, conectados: list[dict[str, Any]] | None = None) -> Any:
        c = super().ctx(conectados)
        c.state["active_profile"] = self.ativo
        return c

    def salvar_b(self, *, paleta: bool = True) -> None:
        from hefesto_dualsense4unix.profiles.loader import save_profile
        from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

        save_profile(Profile(name=NOME_B, match=MatchAny(), leds=LedsConfig(
            lightbar=GLOBAL, lightbar_brightness=BRILHO_GLOBAL,
            player_led_brightness="fraco", auto_player_colors=paleta)),
            origem="regua")

    def trocar(self, nome: str, origem: str) -> None:
        """A troca de perfil pela porta do produto: `autoswitch` ou a manual do IPC."""
        from hefesto_dualsense4unix.profiles.loader import load_profile

        if origem == "manual":
            self.rodar(self.server._handle_profile_switch({"name": nome}))
        else:
            self.pm.apply(load_profile(nome), origin=origem)
        self.ativo = nome

    def clicar_na_pilula(self, n: int, palavra: str) -> None:
        self.a04.brilho_luzes(self.ctx(), {"uniq": UNIQS[n - 1], "luzes": palavra,
                                           "tipo": "button", "evento": "click"},
                              self.ponte)

    def coluna(self, n: int, tique: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return self.a04.pacote(self.ctx(tique))["colunas"][UNIQS[n - 1]]

    def pilula(self, n: int) -> list[str]:
        import re

        return re.findall(r'class="on" data-gesto="brilho-luzes" data-luzes="(\w+)"',
                          self.coluna(n).get("brilho-luzes", ""))

    def degrau(self, n: int) -> tuple[int | None, int | None]:
        """(o que o merge manda, o que o Hefesto levou ao handle) das luzes do P<n>."""
        with self.ctl._io_lock:
            decidido = self.ctl._merged_desired_for_key(MACS[n - 1]).player_led_brightness
        return decidido, self.ctl._handles[MACS[n - 1]].__dict__.get("_brilho_das_luzes")

    def luz(self, n: int) -> tuple[int, int, int]:
        no = self.ctl._sysfs[MACS[n - 1]].get_rgb()
        with self.ctl._io_lock:
            decidido = self.ctl._merged_desired_for_key(MACS[n - 1]).led
        assert no == decidido, f"o nó do P{n} acende {no} e o produto decidiu {decidido}"
        return no

    def disco(self, nome: str, n: int) -> Any:
        from hefesto_dualsense4unix.profiles.loader import load_profile

        dele = load_profile(nome).controllers.get(self.a04.chave_do_override(UNIQS[n - 1]))
        return None if dele is None else dele.leds


#: O handle falso da A-MARCA, guardado antes de o transporte o trocar.
_HANDLE_DA_MESA = marca._handle_falso


def _handle(via: str) -> Any:
    """O handle falso no transporte pedido (`conType` é o que o backend lê)."""
    h = _HANDLE_DA_MESA()
    if via == "bt":
        h.conType = SimpleNamespace(name="BT")
    return h


@pytest.fixture
def mesa_de(tmp_path, monkeypatch):
    """A mesa de quatro, no transporte e no alvo pedidos."""
    import pacotes
    from pacotes import a04_iluminacao

    feitas: list[MesaViva] = []

    def montar(alvo: str = "todos", via: str = "usb") -> MesaViva:
        monkeypatch.setattr(marca, "_handle_falso", lambda: _handle(via))
        m = MesaViva(tmp_path / f"mesa-{len(feitas)}", pacotes, a04_iluminacao, alvo=alvo)
        feitas.append(m)
        vias = {m.ctl._detect_transport(h) for h in m.ctl._handles.values()}
        assert vias == {via}, f"a mesa pediu {via} e o backend leu {vias}"
        m.salvar_b()
        return m

    yield montar
    for m in feitas:
        m.fechar()


MATRIZ = [pytest.param(n, via, alvo, id=f"P{n}-{via}-{alvo}")
          for n in (1, 2, 3, 4) for via in ("usb", "bt") for alvo in ("todos", "um")]


# ---------------------------------------------------------------------------
# 1. A pílula das luzes de número
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("n", "via", "alvo"), MATRIZ)
def test_a_pilula_acende_o_degrau_que_o_aparelho_recebe(mesa_de, n, via, alvo):
    """O Forte clicado atravessa a troca AUTOMÁTICA, e a pílula diz Forte.

    A troca MANUAL solta a camada da usuária, e aí vale o Fraco do perfil B —
    no aparelho e na pílula.

    **A MORDIDA:** faça `brilho_das_luzes_acesas` devolver o disco
    (`brilho_das_luzes_do_controle`) e a pílula acende Fraco com o aparelho
    no Forte.
    """
    forte, fraco = BRILHOS_DAS_LUZES["forte"], BRILHOS_DAS_LUZES["fraco"]
    mesa = mesa_de(alvo, via)
    mesa.clicar_na_pilula(n, "forte")
    mesa.trocar(NOME_B, "autoswitch")
    assert mesa.degrau(n) == (forte, forte), "a régua precisa do Forte no aparelho"
    assert mesa.pilula(n) == ["forte"], (
        f"P{n}: o aparelho está no Forte e a pílula acende {mesa.pilula(n)}")
    for outro in {1, 2, 3, 4} - {n}:
        assert mesa.pilula(outro) == ["fraco"], f"o Forte do P{n} vazou para o P{outro}"
    mesa.trocar(NOME_B, "manual")
    assert mesa.degrau(n) == (fraco, fraco)
    assert mesa.pilula(n) == ["fraco"]


# ---------------------------------------------------------------------------
# 2. O trilho da barra
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("paleta", [True, False], ids=["com-paleta", "sem-paleta"])
@pytest.mark.parametrize(("n", "via", "alvo"), MATRIZ)
def test_o_trilho_mostra_o_brilho_aceso(mesa_de, n, via, alvo, paleta):
    """O P<n> solto a 60% segue a 60% depois do autoswitch, e o trilho diz 60%.

    A caixa `#RRGGBB` e a marca seguem a cor dele: invertida com o brilho do
    disco (82%), a luz a 60% não casava com tom nenhum. A troca MANUAL devolve
    os 82% do perfil B, no plástico e na tela.

    **A MORDIDA:** faça `brilho_aceso` devolver `brilho_do_controle` e o
    trilho diz 82% sobre a barra a 60%.
    """
    mesa = mesa_de(alvo, via)
    if not paleta:
        # Sem a paleta, os quatro escolhem cor no perfil A; no B (sem opinião
        # por controle) quem não passou pelo trilho vai ao global.
        mesa.clicar_no_tom(1, COR_DELE[1])
        mesa.clicar_no_tom(4, COR_DELE[4])
        mesa.desligar_a_paleta(GLOBAL)
        mesa.salvar_b(paleta=False)
    mesa.soltar(n, 60)
    mesa.trocar(NOME_B, "autoswitch")
    assert mesa.luz(n) == _na(COR_DELE[n], 0.60), "a régua precisa da barra a 60%"
    coluna = mesa.coluna(n)
    assert (coluna["brilho"], coluna["brilho-pct"]) == ("60%", 60), (
        f"P{n}: a barra acende a 60% e o trilho diz {coluna['brilho']}")
    assert coluna["hex"] == marca._hexa(COR_DELE[n]), (
        f"P{n}: a caixa diz {coluna['hex']} sobre a barra {mesa.luz(n)}")
    if paleta:
        assert mesa.fora_do_lugar() == []
    mesa.trocar(NOME_B, "manual")
    assert mesa.coluna(n)["brilho"] == f"{round(BRILHO_GLOBAL * 100)}%"


@pytest.mark.parametrize(("n", "via", "alvo"), MATRIZ[::3])
def test_o_clique_depois_do_autoswitch_age_so_naquele_controle(mesa_de, n, via, alvo):
    """Depois da troca automática, a pílula e o trilho respondem ao clique.

    O Médio vai só ao P<n>; o trilho a 40% acende a cor dele a 40% e grava no
    perfil ATIVO, que agora é o B.
    """
    mesa = mesa_de(alvo, via)
    mesa.clicar_na_pilula(n, "forte")
    mesa.soltar(n, 60)
    mesa.trocar(NOME_B, "autoswitch")
    mesa.clicar_na_pilula(n, "medio")  # noqa-acento: chave ASCII do perfil
    assert mesa.degrau(n)[0] == BRILHOS_DAS_LUZES["medio"]  # noqa-acento: chave ASCII
    assert mesa.pilula(n) == ["medio"]  # noqa-acento: chave ASCII
    for outro in {1, 2, 3, 4} - {n}:
        assert mesa.pilula(outro) == ["fraco"]
    mesa.soltar(n, 40)
    assert mesa.luz(n) == _na(COR_DELE[n], 0.40)
    assert mesa.coluna(n)["brilho"] == "40%"
    assert mesa.disco(NOME_B, n).lightbar_brightness == pytest.approx(0.40)
    assert mesa.fora_do_lugar() == []


# ---------------------------------------------------------------------------
# 3. Sem a paleta, o gesto de brilho manda a cor acesa
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize(("n", "para"), [(2, 3), (3, 1)], ids=["P2", "P3"])
def test_sem_a_paleta_o_trilho_manda_a_cor_que_o_daemon_acende(mesa_de, via, n, para):
    """O fóssil sem a paleta: o daemon o desloca, e o trilho não o ressuscita.

    **A MORDIDA:** devolva o `return guardada` sem a pergunta do fóssil no
    ramo sem a paleta de `_a_cor_guardada_que_vale`, e o trilho manda o
    laranja (ou o ciano) fóssil.
    """
    mesa = mesa_de("todos", via)
    mesa.desligar_a_paleta(GLOBAL)
    mesa.fossilizar(n, escolhida_para=para)
    fossil = COR_DELE[n]
    acesa = mesa.luz(n)
    tom = mesa.a04._o_tom_que_acende(acesa, BRILHO_GLOBAL)
    assert tom is not None and tom != fossil, (
        f"a régua precisa do daemon deslocando o fóssil do P{n}, e ele acende {acesa}")
    mesa.soltar(n, 50)
    assert tuple(mesa.ponte.enviados[-1]["rgb"]) == tom, (
        f"o trilho mandou {mesa.ponte.enviados[-1]['rgb']}, e o daemon acendia {tom}")
    assert mesa.luz(n) == _na(tom, 0.50)


# ---------------------------------------------------------------------------
# 4. Sem o daemon dizer, a aba cai no disco
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("sem", ["daemon-velho", "nao-sei"])
def test_sem_o_daemon_dizer_a_aba_cai_no_disco(mesa_de, sem):
    """Daemon de outra versão (sem as chaves) ou o «não sei» dele: o disco.

    **A MORDIDA:** faça `brilho_aceso` devolver `None` sem o daemon, e o
    trilho vira travessão.
    """
    mesa = mesa_de()
    mesa.clicar_na_pilula(3, "forte")
    mesa.soltar(1, 60)
    tique = mesa.publicado()
    for entrada in tique:
        if sem == "daemon-velho":
            entrada.pop("brilho_da_barra")
            entrada.pop("brilho_das_luzes")
        else:
            entrada["brilho_da_barra"] = entrada["brilho_das_luzes"] = None
    assert mesa.coluna(1, tique)["brilho"] == "60%"
    assert mesa.coluna(2, tique)["brilho"] == f"{round(BRILHO_GLOBAL * 100)}%"
    import re

    achou = re.findall(r'class="on" data-gesto="brilho-luzes" data-luzes="(\w+)"',
                       mesa.coluna(3, tique)["brilho-luzes"])
    assert achou == ["forte"]


def test_o_state_full_publica_os_dois_brilhos(mesa_de):
    """O enriquecimento REAL do `state_full` põe as duas chaves em cada controle."""
    mesa = mesa_de()
    mesa.clicar_na_pilula(3, "forte")
    mesa.soltar(1, 60)
    entradas = [{"uniq": u, "connected": True, "index": i, "is_primary": i == 0}
                for i, u in enumerate(UNIQS)]
    mesa.server._enrich_controllers_per_controller(entradas, None)
    assert [(e["brilho_da_barra"], e["brilho_das_luzes"]) for e in entradas] == [
        (0.60, "fraco"), (BRILHO_GLOBAL, "fraco"), (BRILHO_GLOBAL, "forte"),
        (BRILHO_GLOBAL, "fraco")]


# ---------------------------------------------------------------------------
# 5. O «Desligar» é o brilho em 0%
# ---------------------------------------------------------------------------
CAMINHOS = ["autoswitch", "manual", "boot", "salvar", "aplicar"]


def _reaplicar(mesa: MesaViva, caminho: str) -> None:
    from pacotes import rodape

    from hefesto_dualsense4unix.profiles.loader import load_profile

    clique = {"tipo": "button", "evento": "click"}
    if caminho in ("autoswitch", "manual"):
        mesa.trocar(NOME, caminho)
    elif caminho == "boot":
        mesa.ctl.clear_user_output_overrides()
        mesa.pm.apply(load_profile(NOME), origin="system")
    elif caminho == "salvar":
        rodape.salvar(mesa.ctx(), clique, None)
        mesa.ctl.clear_user_output_overrides()
        mesa.pm.apply(load_profile(NOME), origin="system")
    elif caminho == "aplicar":
        from tests.unit.test_a_barra_nao_escurece_ao_reaplicar import _PonteDoRodape

        rodape.aplicar(mesa.ctx(), clique, _PonteDoRodape(mesa))
    else:
        raise AssertionError(caminho)


@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("caminho", CAMINHOS)
@pytest.mark.parametrize("n", [1, 2], ids=["P1-sem-cor", "P2-laranja"])
def test_o_desligar_sobrevive_a_reaplicar_o_perfil(mesa_de, n, caminho, via):
    """O controle «Desligado» fica apagado em todo caminho, e a cor dela fica no disco.

    **AS MORDIDAS:** devolva o preto como a cor gravada do «Desligar» (o
    `_guardar_a_cor_no_perfil` no ramo `apagando`) e a troca manual, o boot
    e o Salvar acendem a barra; e o laranja some do disco.
    """
    mesa = mesa_de("todos", via)
    mesa.a04.apagar(mesa.ctx(), {"uniq": UNIQS[n - 1], "tipo": "button",
                                 "evento": "click"}, mesa.ponte)
    assert mesa.luz(n) == (0, 0, 0)
    for _ in range(2):
        _reaplicar(mesa, caminho)
        assert mesa.luz(n) == (0, 0, 0), f"P{n} acendeu {mesa.luz(n)} depois de {caminho}"
    leds = mesa.disco(NOME, n)
    assert leds.lightbar_brightness == 0.0
    if n == 2:
        assert tuple(leds.lightbar) == LARANJA, f"o «Desligar» apagou do disco o laranja: {leds}"
    assert mesa.coluna(n)["brilho"] == "0%"
    for outro in {1, 2, 3, 4} - {n}:
        assert mesa.luz(outro) != (0, 0, 0), f"o «Desligar» do P{n} apagou o P{outro}"


@pytest.mark.parametrize("n", [1, 2], ids=["P1-sem-cor", "P2-laranja"])
def test_o_trilho_acende_de_novo_na_cor_dele(mesa_de, n):
    """Depois do «Desligar», subir o trilho acende a cor dele — a escolhida, ou a do número."""
    mesa = mesa_de()
    mesa.a04.apagar(mesa.ctx(), {"uniq": UNIQS[n - 1]}, mesa.ponte)
    mesa.trocar(NOME, "manual")
    mesa.soltar(n, 70)
    assert mesa.luz(n) == _na(COR_DELE[n], 0.70)
    assert mesa.fora_do_lugar() == []


@pytest.mark.parametrize("n", [1, 2], ids=["P1-sem-cor", "P2-laranja"])
def test_um_tom_numa_barra_apagada_a_acende_no_brilho_do_perfil(mesa_de, n):
    """O tom da guia não aceita o toque sem agir: a barra apagada acende no brilho do perfil.

    O 0% do controle sai do disco junto, e o trilho diz o brilho do perfil.

    **A MORDIDA:** tire o `religar` de `_escrever_a_cor` e o roxo sai a 0%.
    """
    mesa = mesa_de()
    mesa.a04.apagar(mesa.ctx(), {"uniq": UNIQS[n - 1]}, mesa.ponte)
    mesa.trocar(NOME, "manual")
    mesa.clicar_no_tom(n, ROXO)
    assert mesa.luz(n) == _na(ROXO, BRILHO_GLOBAL)
    leds = mesa.disco(NOME, n)
    assert "lightbar_brightness" not in leds.model_fields_set, (
        f"o 0% ficou no disco depois do tom: {leds}")
    assert mesa.coluna(n)["brilho"] == f"{round(BRILHO_GLOBAL * 100)}%"
    mesa.trocar(NOME, "manual")
    assert mesa.luz(n) == _na(ROXO, BRILHO_GLOBAL), "o perfil reaplicado apagou o tom"


# ---------------------------------------------------------------------------
# 6. Os outros dois chamadores do brilho: o Salvar e o Aplicar do rodapé
# ---------------------------------------------------------------------------
def test_o_salvar_depois_do_autoswitch_grava_o_que_esta_aceso(mesa_de):
    """O P1 a 60% atravessou o autoswitch; o Salvar grava o azul a 60% no perfil B.

    **A MORDIDA:** devolva `brilho_do_controle` ao Salvar do rodapé e ele grava
    a luz escura `(0,0,153)` como a cor do P1, que o perfil reaplicado escurece.
    """
    from pacotes import rodape

    mesa = mesa_de()
    mesa.soltar(1, 60)
    mesa.trocar(NOME_B, "autoswitch")
    rodape.salvar(mesa.ctx(), {"tipo": "button", "evento": "click"}, None)
    leds = mesa.disco(NOME_B, 1)
    assert (tuple(leds.lightbar), leds.lightbar_brightness) == (COR_DELE[1], 0.60), leds
    mesa.trocar(NOME_B, "manual")
    assert mesa.luz(1) == _na(COR_DELE[1], 0.60)


def test_o_aplicar_carimba_o_brilho_da_cor(mesa_de):
    """A cor do «Aplicar» leva o brilho dela, e ele atravessa a troca automática.

    **A MORDIDA:** tire o `brilho_da_cor` do `DraftApplier` e o daemon diz
    «não sei» sobre a cor que o Aplicar acendeu.
    """
    from pacotes import rodape

    from tests.unit.test_a_barra_nao_escurece_ao_reaplicar import _PonteDoRodape

    mesa = mesa_de()
    mesa.gravar_o_brilho(2, 0.40)
    rodape.aplicar(mesa.ctx(), {"tipo": "button", "evento": "click"}, _PonteDoRodape(mesa))
    assert mesa.luz(2) == _na(LARANJA, 0.40)
    mesa.trocar(NOME_B, "autoswitch")
    assert mesa.server._brilhos_acesos(UNIQS[1])["brilho_da_barra"] == pytest.approx(0.40)
    assert mesa.coluna(2)["brilho"] == "40%"


# ---------------------------------------------------------------------------
# 7. O brilho da cor, no dono do merge
# ---------------------------------------------------------------------------
def test_o_brilho_da_cor_so_explica_a_mesma_cor(mesa_de):
    """O carimbo vale enquanto o override guardar a MESMA cor, e morre com ela.

    **A MORDIDA:** tire a comparação `carimbo[0] == tuple(cor)` de
    `brilho_da_barra_para`, e a cor que chegou sem brilho herda o de outra.
    """
    from hefesto_dualsense4unix.core.controller import OutputSpec

    mesa = mesa_de()
    ctl, u = mesa.ctl, UNIQS[0]
    ctl.apply_output_for(u, OutputSpec(led=_na(ROXO, 0.5)), brilho_da_cor=0.5)
    assert ctl.brilho_da_barra_para(u) == 0.5
    ctl.apply_output_for(u, OutputSpec(led=(10, 20, 30)))
    assert ctl.brilho_da_barra_para(u) is None, "a cor sem brilho herdou o da cor de antes"
    ctl.apply_output_for(u, OutputSpec(led=_na(ROXO, 0.5)), brilho_da_cor=0.5)
    ctl.clear_user_output_overrides()
    assert ctl.brilho_da_barra_para(u) == pytest.approx(BRILHO_GLOBAL)
    assert u not in ctl._brilho_da_cor
    ctl.apply_output_for(u, OutputSpec(led=_na(ROXO, 0.5)), brilho_da_cor=0.5)
    ctl.reset_output_overrides(None)
    assert ctl._brilho_da_cor == {}
    assert ctl.brilho_da_barra_para("sem-mac") is None
    assert ctl.brilho_das_luzes_para("sem-mac") is None
