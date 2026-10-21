"""O PERFIL DE DESEMPENHO É DE CADA CONTROLE — A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01.

Decisões de 26/09/2026: o perfil de desempenho mora em cada cartão da aba
Conexões (`D-2609-O-PERFIL-DE-DESEMPENHO-E-POR-CONTROLE`), «Eu escolho» virou
«Personalizado» (`D-2609-EU-ESCOLHO-VIRA-PERSONALIZADO`), os outros dois viraram
«Perfil máximo» e «Perfil econômico» (pedido na mesma noite) e o cartão e a aba
Sistema falam o MESMO perfil, por um dono e pelo mesmo gesto do daemon
(`D-2609-A-CONEXOES-E-A-SISTEMA-FALAM-O-MESMO-PERFIL`).

A Conexões deixou de ter os botões (13/10/2026, mudança 12 do desenho do todo, pedido da Vitória:
*«remove os botões do perfil econômico e perfil máximo. Isso já existe na aba sistema.»*): o gesto
`perfil-do-controle`, o `perfil_na_linha` e o campo `perfil` do cartão saíram de lá. O que
ficou, e a mordida que o derruba:

1. o dono (`secao_orcamento`): os três rótulos (o botão por controle, o disco dele e quem vencia
   saíram com o cartão em 17/10/2026, porque nenhuma tela os chamava);
2. a aba Sistema segue falando o perfil, pelo mesmo dono;
3. a Conexões não tem mais o perfil por controle — MORDIDA: devolver um botão
   `perfil-do-controle` ao cartão do gerador → reprova.

O LAR É DE MENTIRA: o `conftest` desvia o `HOME` e os `XDG_*`; o `maquina.json`
e o perfil gravados aqui moram dentro dele.

A régua dela, a de toda decisão: *«nunca é pensada só em um modo, rota, forma
de conexão se cabo ou se bt, ou só pro player 1.»* <!-- noqa-acento: citação literal -->
"""
from __future__ import annotations

import pathlib
import re
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest


from tests.unit.test_a_marca_da_cor_nao_some import NOME, UNIQS


RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINAS = [RAIZ / "mockup/08-conexoes.html",
           RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"]
PAGINAS_09 = [RAIZ / "mockup/09-sistema.html",
              RAIZ / "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html"]


def _orc() -> Any:
    from hefesto_dualsense4unix.app.actions.config import secao_orcamento

    return secao_orcamento


def _a08() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def test_os_rotulos_sao_os_do_desenho_e_personalizado_e_o_terceiro() -> None:
    orc = _orc()
    assert [orc.ROTULOS_DOS_PERFIS[p] for p in orc.PERFIS] == [
        "Perfil máximo", "Perfil econômico", "Personalizado"]


@pytest.mark.parametrize("arquivo", PAGINAS_09, ids=["bancada", "publicada"])
def test_a_sistema_diz_personalizado_e_a_relacao_com_o_cartao(arquivo: pathlib.Path) -> None:
    html = arquivo.read_text(encoding="utf-8")
    botoes = re.findall(
        r'data-gesto="perfil-da-mesa" data-v="(\w+)"[^>]*(?:title|data-dica)="([^"]*)">([^<]+)<',
        html)
    orc = _orc()
    assert [(v, r) for v, _t, r in botoes] == [
        (p, orc.ROTULOS_DOS_PERFIS[p]) for p in orc.PERFIS], botoes
    dicas = {v: t for v, t, _r in botoes}
    # O desenho do todo (A-ABA-SISTEMA-DO-TODO-01, publicado em 16/10/2026) trocou as três dicas
    # longas pelas curtas aprovadas, e o «vale para todos» passou para a dica do rótulo (a
    # D-1610-O-PERFIL-DE-BATERIA-E-SO-O-GLOBAL-NA-SISTEMA): o mockup e a publicada dizem o mesmo.
    assert dicas == {"tudo_ligado": "Nada é limitado",
                     "bateria_longa": "Vibração em 30% da força",
                     "eu_escolho": "Você escolhe em cada aba"}, dicas
    # O-PERFIL-DE-BATERIA-POR-CONTROLE-QUE-NINGUEM-CHAMA-SAI-01 (17/10/2026): o desenho diz
    # «Vale para todos os controles» (a Conexões perdeu o perfil por controle); a publicada guarda
    # a frase velha até o `--publicar 09` do fecho, e a velha só vale até lá.
    velha = ('data-dica="Vale para todos; cada controle pode ter o seu em Conexões">'
             "Perfil global de bateria")
    nova = 'data-dica="Vale para todos os controles">Perfil global de bateria'
    assert (nova in html) if arquivo.parent.name == "mockup" else (nova in html or velha in html)
    assert "Eu escolho" not in html


def test_a_conexoes_nao_tem_o_perfil_por_controle() -> None:
    """O perfil de desempenho mora só na Sistema: nem botão, nem gesto, nem campo no cartão.

    A publicada guarda o desenho velho até o `--publicar` do fecho, e é conferida só depois dele.
    """
    a08 = _a08()
    for saiu in ("perfil_do_controle_gesto", "perfil_na_linha", "economia_do_controle"):
        assert not hasattr(a08, saiu), f"`{saiu}` voltou à Conexões"
    html = PAGINAS[0].read_text(encoding="utf-8")
    # `data-campo="perfil"` segue no «Perfil ativo» do cabeçalho (`pa-nome`); o cartão não o tem
    assert html.count('data-campo="perfil"') == html.count('class="pa-nome" data-campo="perfil"')
    for saiu in ('data-gesto="perfil-do-controle"', 'class="gc-perfil"',
                 "economia-do-controle", "eco-luz"):
        assert saiu not in html, f"{saiu} voltou ao cartão da Conexões"


@pytest.fixture
def declarar() -> Iterator[Any]:
    """Grava no `maquina.json` do lar de mentira, e a ativação o lê de lá."""
    from hefesto_dualsense4unix.profiles.schema import registrar_declaracao_da_mesa
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina, gravar_maquina

    registrar_declaracao_da_mesa(carregar_maquina)

    def gravar(corpo: dict[str, Any]) -> None:
        assert gravar_maquina(corpo), f"o lar de mentira recusou {corpo}"

    yield gravar
    registrar_declaracao_da_mesa(None)


def _o_clique_chega_ao_daemon(mesa: Any, declarar: Any, corpo: dict[str, Any]) -> None:
    """O que o `machine.declare` faz depois de gravar: `reaplicar_se_a_economia_mudou`."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    antes = carregar_maquina()
    declarar(corpo)
    vivo = SimpleNamespace(controller=mesa.ctl, _maquina=carregar_maquina(), _native_mode=False,
                           _reapply_last_profile=lambda: mesa.trocar(NOME, "system"))
    assert Daemon.reaplicar_se_a_economia_mudou(vivo, antes)  # type: ignore[arg-type]


def _donos_da_luz(mesa: Any) -> dict[int, str | None]:
    """A camada dona das luzes de número de cada controle (`usuaria` ou `perfil`)."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    with mesa.ctl._io_lock:
        return {n: (mesa.ctl._desired_owner_by_uniq.get(norm_mac(UNIQS[n - 1])) or {})
                .get("player_led_brightness") for n in (1, 2, 3, 4)}


