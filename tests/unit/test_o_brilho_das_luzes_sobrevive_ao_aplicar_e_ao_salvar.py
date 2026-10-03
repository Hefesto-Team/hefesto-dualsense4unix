"""O-BRILHO-DAS-LUZES-SOBREVIVE-AO-APLICAR-01 — a pílula, o «Aplicar» e o «Salvar».

A queixa dela, 26/09/2026: *«tentei alterar a força dos leds
fraco medio e forte <!-- noqa-acento: citação literal dela -->
e ao aplicar ele não aplicar e ao salvar ele não salva»*.

**MEDIDO ANTES DA CURA**, na mesa de quatro da A-MARCA (o `IpcServer` real, o
merge do `PyDualSenseController`, o `SysfsLedNode` sobre arquivos, o laranja do
P2 e o ciano do P3 gravados no perfil), com o Forte clicado no P2:

    depois do clique     merge Forte · aparelho Forte · disco Forte · pílula Forte
    depois do «Aplicar»  merge Fraco · pílula Fraco · disco Forte
    depois do «Salvar»   disco Forte · pílula Fraco
    perfil reaplicado    merge Forte · pílula Forte

O valor morria no «Aplicar»: o rascunho não leva o campo, e o `DraftApplier`
troca o mapa inteiro de overrides do daemon (`reset_output_overrides`) pelo do
rascunho. O «Salvar» nunca perdeu o brilho no disco; a tela é que dizia
Fraco, porque a pílula pergunta ao daemon vivo. Dos seis gestos da aba 04 que
gravam no perfil, só este morria no «Aplicar» — e a varredura da seção 2, que
mede os seis, achou a outra metade da classe no «Salvar»: o tom, a caixa
`#RRGGBB` e o interruptor «Cores automáticas» gravam a cor com o número para o
qual ela foi escolhida (`lightbar_para_o_numero`), e o «Salvar» a regravava
sem ele. Sem o número a cor é `LEGADO`, e o tom do número de outro controle
virava fóssil na troca seguinte.

A MATRIZ, a regra dela: os três brilhos, P1 a P4, cabo e rádio.

**AS MORDIDAS**, arrancadas e devolvidas:

* tire o `player_led_brightness` de `DraftConfig._controllers_to_ipc` e a
  seção 1 inteira e a linha `brilho-luzes` da seção 2 reprovam — desde a
  O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01 (26/09/2026) a palavra de cada
  controle viaja no rascunho, e a segunda viagem do rodapé saiu;
* tire o `_com_a_procedencia_da_mesma_cor` do `DraftConfig.with_controller_leds`
  e a varredura reprova no tom, na caixa e nas «Cores automáticas» (P2 e P4) e
  em todo gesto do P2, além do tom que vira fóssil;
* devolva ao «Salvar» a luz acesa no override e a cor que mudou só no
  aparelho vai ao disco (`test_a_cor_que_mudou_so_no_aparelho_nao_vai_ao_disco`);
* tire o `is None` do `rodape.aplicar` e o «Aplicar» pisca verde com o daemon
  calado (`test_sem_resposta_do_daemon_o_aplicar_recusa_dizendo`);
* tire o `_com_o_teto_da_economia` do `DraftApplier.apply` e a seção 3
  reprova — o Forte dela venceria a «Bateria longa».

O LAR É DE MENTIRA: o `conftest` desvia o `HOME` e os `XDG_*`; o perfil e o
`maquina.json` gravados aqui moram dentro dele.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tests.conftest import exigir_gi_real
from tests.unit.ponte_do_rodape import PonteDoRodape

exigir_gi_real("importa as réguas e os pacotes da aba 04, que carregam o GTK")

from tests.unit import test_a_04_pergunta_ao_daemon_vivo as viva
from tests.unit import test_a_barra_nao_escurece_ao_reaplicar as barra
from tests.unit import test_a_marca_da_cor_nao_some as marca
from tests.unit.test_a_marca_da_cor_nao_some import NOME, UNIQS

import pacotes
from pacotes import a04_iluminacao, rodape

CLIQUE = {"tipo": "button", "evento": "click",
          "pagina": "04-iluminacao.html"}  # (noqa-acento: chave do clique)

OUTRA = {"fraco": "forte", "medio": "fraco", "forte": "medio"}  # (noqa-acento) chaves ASCII


class _PonteDaAba(viva._Ponte):
    """A ponte da aba 04 com as duas portas do `perfil.gravar_e_reaplicar`, nos handlers REAIS.

    O interruptor «Cores automáticas» grava o perfil e o reaplica
    (`profile.switch`, depois `launch_env.refresh`). A ponte da A-04 recusa as
    duas, e sem elas a varredura da seção 2 não sabia clicar nele.
    """

    def profile_switch(self, nome: str) -> bool:
        self.mesa.rodar(self.mesa.server._handle_profile_switch({"name": nome}))
        return True

    def profile_reaplicar(self, nome: str) -> bool:
        self.mesa.rodar(self.mesa.server._handle_profile_reaplicar({"name": nome}))
        return True

    def chamar(self, metodo: str, timeout: float | None = None, **params: Any) -> bool:
        if metodo != "launch_env.refresh":
            raise AttributeError(f"a régua não previu a aba chamar {metodo!r}")
        return isinstance(self.mesa.rodar(
            self.mesa.server._handle_launch_env_refresh(params)), dict)


@pytest.fixture
def mesa_de(tmp_path, monkeypatch):
    """A mesa de quatro da A-04-PERGUNTA-AO-DAEMON-VIVO-01, no transporte pedido."""
    feitas: list[Any] = []

    def montar(alvo: str = "todos", via: str = "usb") -> Any:
        monkeypatch.setattr(marca, "_handle_falso", lambda: viva._handle(via))
        m = viva.MesaViva(tmp_path / f"mesa-{len(feitas)}", pacotes, a04_iluminacao,
                          alvo=alvo)
        m.ponte = _PonteDaAba(m)
        feitas.append(m)
        vias = {m.ctl._detect_transport(h) for h in m.ctl._handles.values()}
        assert vias == {via}, f"a mesa pediu {via} e o backend leu {vias}"
        return m

    yield montar
    for m in feitas:
        m.fechar()


class _PonteDoRodape(barra._PonteDoRodape):
    """A ponte do rodapé, que guarda o rascunho que o «Aplicar» leva ao handler REAL."""

    def __init__(self, mesa: Any) -> None:
        super().__init__(mesa)
        self.rascunhos: list[dict[str, Any]] = []

    def profile_reaplicar(self, nome: str) -> Any:
        """O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01: o «Aplicar» manda o nome."""
        self.rascunhos.append(_o_perfil_que_o_daemon_le(nome))
        return super().profile_reaplicar(nome)

    def apply_draft_detalhado(self, payload: dict[str, Any]) -> Any:
        self.rascunhos.append(payload)
        return super().apply_draft_detalhado(payload)

    @property
    def luzes(self) -> list[dict[str, Any]]:
        """A palavra que o rascunho levou de cada controle — só de quem a escreveu."""
        return [{"brilho": palavra, "uniq": uniq}
                for rascunho in self.rascunhos
                for uniq, entrada in sorted((rascunho.get("controllers") or {}).items())
                if (palavra := ((entrada or {}).get("leds") or {}).get(
                    "player_led_brightness")) is not None]


def _o_perfil_que_o_daemon_le(nome: str) -> dict[str, Any]:
    """O perfil do disco na forma do rascunho: o que o `profile.reaplicar` aplica."""
    from hefesto_dualsense4unix.app.draft_config import DraftConfig
    from hefesto_dualsense4unix.profiles.loader import load_profile

    return DraftConfig.from_profile(load_profile(nome)).to_ipc_dict()


def _aplicar(mesa: Any) -> _PonteDoRodape:
    ponte = _PonteDoRodape(mesa)
    rodape.aplicar(mesa.ctx(), CLIQUE, ponte)
    return ponte


def _salvar(mesa: Any) -> None:
    rodape.salvar(mesa.ctx(), CLIQUE, PonteDoRodape())


def _o_global_das_luzes(mesa: Any, palavra: str) -> None:
    """O «Todos» das luzes no perfil, e o perfil reaplicado pela troca manual."""
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

    prof = load_profile(NOME)
    save_profile(prof.model_copy(update={"leds": prof.leds.model_copy(
        update={"player_led_brightness": palavra})}), origem="regua")
    mesa.trocar(NOME, "manual")


def _global_no_disco() -> str:
    from hefesto_dualsense4unix.profiles.loader import load_profile

    return str(load_profile(NOME).leds.player_led_brightness)


def _gestos_que_gravam() -> list[str]:
    """Os gestos da aba 04 que declaram `grava=` — lidos, não digitados."""
    return sorted(nome for (pagina, nome) in pacotes.GESTOS_QUE_MEXEM
                  if pagina == a04_iluminacao.PAGINA)


CLIQUES: dict[str, dict[str, Any]] = {
    "cor": {"hex": "8000FF"},
    "reenviar": {"texto": "#12AB34"},
    "brilho": {"valor": "40", "tipo": "input", "evento": "change"},
    "apagar": {},
    "brilho-luzes": {"luzes": "forte"},
    "auto-cores": {"tipo": "input", "evento": "change"},
}

PINTADO = ("brilho", "brilho-pct", "hex", "brilho-luzes")


def test_a_varredura_conhece_todo_gesto_que_grava() -> None:
    """A lista sai do pacote; a régua sabe clicar em todos, e em nenhum a mais."""
    derivada = _gestos_que_gravam()
    assert derivada, "a varredura não achou gesto nenhum que grava — a leitura quebrou"
    assert set(derivada) == set(CLIQUES), (
        f"a aba 04 grava por {derivada} e a varredura sabe clicar {sorted(CLIQUES)}")


def _o_que_a_tela_mostra(mesa: Any, n: int) -> dict[str, Any]:
    coluna = mesa.coluna(n)
    return {"luz": mesa.luz(n), "luzes": mesa.degrau(n)[0],
            **{campo: coluna.get(campo) for campo in PINTADO}}


def _o_disco(mesa: Any, n: int) -> dict[str, Any]:
    """Os campos escritos na luz do P<n>, e os dois globais da aba que a coluna lê."""
    from hefesto_dualsense4unix.profiles.loader import load_profile

    globais = load_profile(NOME).leds
    saida = {f"global.{campo}": getattr(globais, campo)
             for campo in ("auto_player_colors", "player_led_brightness")}
    leds = mesa.disco(NOME, n)
    if leds is None:
        return saida
    return {**saida, **{campo: getattr(leds, campo) for campo in leds.model_fields_set}}


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_o_tom_regravado_pelo_salvar_nao_vira_fossil(mesa_de, via: str) -> None:
    """O P4 escolhe o tom do número 2; o «Salvar» o regrava; o perfil reaplicado o mantém.

    O tom da guia grava a cor COM o número para o qual foi escolhida
    (`lightbar_para_o_numero`). Sem ele a cor é `LEGADO`, e o resolvedor a
    prova fóssil pela forma: o tom do número de outro controle da mesa.

    **A MORDIDA:** tire o `_a_procedencia_da_mesma_cor` do `_draft_do_ativo`
    e o P4 acende a cor do número dele depois da troca manual.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    from tests.unit.test_a_04_pergunta_ao_daemon_vivo import _na
    from tests.unit.test_a_marca_da_cor_nao_some import BRILHO_GLOBAL

    tom = player_slot_color(2)
    mesa = mesa_de("todos", via)
    mesa.clicar_no_tom(4, tom)
    assert mesa.luz(4) == _na(tom, BRILHO_GLOBAL), "a régua precisa do tom no P4"
    _salvar(mesa)
    assert mesa.disco(NOME, 4).lightbar_para_o_numero == 4, (
        f"o «Salvar» tirou do disco o número do tom: {mesa.disco(NOME, 4)}")
    mesa.trocar(NOME, "manual")
    assert mesa.luz(4) == _na(tom, BRILHO_GLOBAL), (
        f"o tom que ela escolheu virou fóssil depois do «Salvar»: o P4 acende {mesa.luz(4)}")


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_a_cor_que_mudou_so_no_aparelho_nao_vai_ao_disco(mesa_de, via: str) -> None:
    """A cor que muda só no daemon fica fora do disco, e a dela fica com o número dela.

    O P4 escolhe o tom do número 2 (o disco guarda o número 4 com ele); depois
    a luz dele muda só no daemon — é a camada da mão que atravessa a troca
    automática de perfil. Até 27/09 o «Salvar» gravava a cor viva, e a régua
    cobrava que ela fosse sem o número da antiga. Desde 27/09 o Salvar lê o
    disco (`D-2709-O-SALVAR-LE-O-PERFIL`): a cor e o número que ficam são os
    que o clique no tom gravou. A regra da procedência (a cor nova não leva o
    número da antiga) continua medida no dono, o `with_controller_leds`
    (`test_o_aplicar_nao_solta_o_teto_do_controle.py`, seção 4).

    **A MORDIDA:** devolva ao «Salvar» a luz acesa no override e o disco sai
    com o roxo.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    from tests.unit.test_a_04_pergunta_ao_daemon_vivo import ROXO, _na
    from tests.unit.test_a_marca_da_cor_nao_some import BRILHO_GLOBAL

    tom = player_slot_color(2)
    mesa = mesa_de("todos", via)
    mesa.clicar_no_tom(4, tom)
    assert mesa.disco(NOME, 4).lightbar_para_o_numero == 4, "a régua precisa do número no disco"
    mesa.ponte.led_set_detalhado(ROXO, BRILHO_GLOBAL, UNIQS[3])
    assert mesa.luz(4) == _na(ROXO, BRILHO_GLOBAL), "a régua precisa da luz nova no P4"
    _salvar(mesa)
    leds = mesa.disco(NOME, 4)
    assert tuple(leds.lightbar) == tom, (
        f"o «Salvar» gravou a cor que mudou só no aparelho: {leds}")
    assert leds.lightbar_para_o_numero == 4, (
        f"o «Salvar» perdeu o número do tom que ela escolheu: {leds}")


@pytest.fixture
def economia() -> Iterator[Any]:
    """Liga a economia pelo `maquina.json` do lar de mentira — o daemon e a tela o leem."""
    from hefesto_dualsense4unix.profiles.schema import registrar_declaracao_da_mesa
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina, gravar_maquina

    registrar_declaracao_da_mesa(carregar_maquina)

    def ligar(declaracao: dict[str, Any]) -> None:
        assert gravar_maquina(declaracao), f"o lar de mentira recusou {declaracao}"

    yield ligar
    registrar_declaracao_da_mesa(None)


