#!/usr/bin/env python3
"""Com o serviço parado, a aba Jogar e o topo dizem que o Hefesto está desligado.

A queixa de 15/10/2026: «Sair» pela bandeja, a interface aberta com o serviço fora mostrou o Status
em Ligado, o topo com «Nenhum controle» ao lado do ponto verde e a mesa vazia sem dizer por quê,
com o Galactic Purple e o Cosmic Red ligados pelo rádio. O piloto entrega o estado vazio (`{}`)
depois da folga; o pacote é quem lia esse vazio como Ligado.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import pacotes
from pacotes import Contexto
from pacotes import a01_jogar as aba

UNIQ_ROXO = "aa:bb:cc:00:00:01"
UNIQ_VERMELHO = "aa:bb:cc:00:00:02"

NO_RADIO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
    "controllers": [
        {"uniq": UNIQ_ROXO, "connected": True, "player_slot": 1, "transport": "bt"},
        {"uniq": UNIQ_VERMELHO, "connected": True, "player_slot": 2, "transport": "bt"},
    ],
}


def _parado() -> Contexto:
    """O que o piloto entrega depois da folga: estado vazio, mesa vazia."""
    return Contexto(state={}, mesa=[], conectados=[], estados={})


def _no_radio() -> Contexto:
    mesa = [{"uniq": c["uniq"], "pref": f"p{i}", "transporte": "bt", "jogador": i}
            for i, c in enumerate(NO_RADIO["controllers"], 1)]
    return Contexto(state=NO_RADIO, mesa=mesa,
                    conectados=list(NO_RADIO["controllers"]), estados={})


def _de_pe_sem_controle() -> Contexto:
    return Contexto(state={**NO_RADIO, "controllers": []}, mesa=[], conectados=[], estados={})


def test_o_status_marca_desligado_com_o_servico_parado() -> None:
    """Posição vazia caía no rádio que o gerador marcou (Ligado): o interruptor mentia."""
    fora = aba.pacote(_parado())
    assert fora["hef-posicao"] == aba.POSICAO_COM_O_SERVICO_PARADO == "desligado", (
        f"o Status saiu {fora['hef-posicao']!r} com o serviço parado")
    assert fora["modo-aceso"] == "", "um chip acendeu sobre estado que ninguém leu"
    assert fora["steam-input-aceso"] == ""


def test_a_mesa_diz_por_que_esta_vazia() -> None:
    """A frase do serviço desligado, e nunca a da mesa vazia (haveria controle ligado)."""
    frase = aba.pacote(_parado())["mesa-frase"]
    assert frase == aba.SERVICO_CALADO, f"a mesa disse {frase!r}"
    assert frase != aba.MESA_VAZIA
    assert frase.startswith(aba.SERVICO_DESLIGADO)


def test_o_topo_diz_desligado_e_nao_nenhum_controle() -> None:
    """«Nenhum controle» ao lado do ponto verde lia-se como tela vazia com controle ligado."""
    topo = pacotes.topo(_parado())
    assert topo["conta-b"] == aba.SERVICO_DESLIGADO.rstrip(".")
    assert topo["conta-b"] != pacotes.SEM_CONTROLE_NA_MESA
    # é este campo que apaga o ponto verde no desenho
    assert topo["servico"] == "parado"  # (noqa-acento) chave da página


def test_com_dois_controles_no_radio_volta_ao_ligado_e_aos_cartoes() -> None:
    """A volta: o primeiro estado que responder desfaz o Desligado, a frase e o topo."""
    ctx = _no_radio()
    fora = aba.pacote(ctx)
    assert fora["hef-posicao"] == "ligado"
    assert fora["mesa-frase"] == ""
    assert set(fora["cartoes"]) == {UNIQ_ROXO, UNIQ_VERMELHO}
    topo = pacotes.topo(ctx)
    assert topo["conta-b"] == "2 BT"
    assert topo["servico"] == "de-pe"  # (noqa-acento) chave da página


def test_servico_de_pe_sem_controle_continua_dizendo_que_nao_ha_controle() -> None:
    """O serviço respondeu e a mesa está vazia: aí «Nenhum controle» é verdade."""
    ctx = _de_pe_sem_controle()
    assert aba.pacote(ctx)["mesa-frase"] == aba.MESA_VAZIA
    assert pacotes.topo(ctx)["conta-b"] == pacotes.SEM_CONTROLE_NA_MESA


class _ServicoRecemLigado:
    """A ponte com o serviço que acabou de subir: a unit é `Type=simple`, então o `systemctl start`
    volta antes de o soquete existir (medido em 15/10/2026: 0,5 s até o `ipc_server_listening`).
    Responde só a partir da `acorda_na`-ésima pergunta; antes disso todo pedido cai."""

    def __init__(self, acorda_na: int) -> None:
        self.acorda_na = acorda_na
        self.perguntas = 0
        self.pedidos: list[tuple[str, bool]] = []

    @property
    def de_pe(self) -> bool:
        return self.perguntas >= self.acorda_na

    def daemon_state_full(self) -> dict[str, Any] | None:
        self.perguntas += 1
        # Uma espera sem teto pergunta para sempre: aqui ela reprova em vez de travar a régua.
        assert self.perguntas < 100, "a espera pelo serviço não tem teto"
        return dict(NO_RADIO) if self.de_pe else None

    def chamar(self, metodo: str, **_params: Any) -> bool:
        self.pedidos.append((metodo, self.de_pe))
        return self.de_pe


def test_clicar_em_ligado_com_o_servico_parado_liga_o_servico(monkeypatch: Any) -> None:
    """O mesmo ato da aba Sistema; e o «Desligado» nunca liga o serviço."""
    from pacotes import a09_sistema

    chamadas: list[str] = []
    monkeypatch.setattr(a09_sistema, "ativar_o_servico",
                        lambda: chamadas.append("ligou") or True)
    monkeypatch.setattr(aba, "_hefesto_o_modo", lambda ctx, o, p: None)
    aba.hefesto(_parado(), {"modo": "gamepad"}, _ServicoRecemLigado(acorda_na=1))
    assert chamadas == ["ligou"], "o Ligado não ligou o serviço"
    aba.hefesto(_parado(), {"modo": "native"}, None)
    assert chamadas == ["ligou"], "o Desligado ligou o serviço"


def test_o_modo_do_ligado_espera_o_servico_que_acabou_de_subir(monkeypatch: Any) -> None:
    """Sem a espera, o plano saía no meio segundo em que o soquete ainda não existe: o modo não
    chegava ao serviço e o botão piscava a recusa sobre um clique que tinha ligado tudo."""
    from pacotes import a09_sistema

    monkeypatch.setattr(a09_sistema, "ativar_o_servico", lambda: True)
    servico = _ServicoRecemLigado(acorda_na=3)
    aba.hefesto(_parado(), {"modo": "gamepad"}, servico)
    assert servico.pedidos, "o Ligado não mandou o modo"
    caidos = [metodo for metodo, de_pe in servico.pedidos if not de_pe]
    assert not caidos, f"o modo saiu antes de o serviço responder: {caidos}"


def test_servico_que_nao_responde_no_prazo_recusa_dizendo(monkeypatch: Any) -> None:
    """A espera tem teto: passado o prazo, o plano vai e a recusa é a verdadeira."""
    from pacotes import a09_sistema

    monkeypatch.setattr(a09_sistema, "ativar_o_servico", lambda: True)
    monkeypatch.setattr(aba, "SEGUNDOS_ATE_O_SERVICO_RESPONDER", 0.3)
    servico = _ServicoRecemLigado(acorda_na=10**6)
    try:
        aba.hefesto(_parado(), {"modo": "gamepad"}, servico)
    except RuntimeError as recusa:
        assert str(recusa) == aba.MODO_SEM_CONFIRMACAO
    else:
        raise AssertionError("o serviço não respondeu e o Ligado não disse que não confirmou")
    assert servico.pedidos, "sem resposta no prazo, o Ligado nem tentou o modo"


def test_servico_ja_de_pe_nao_espera(monkeypatch: Any) -> None:
    """Com o serviço de pé (`ativar_o_servico` devolve False) o modo sai na hora, sem pergunta."""
    from pacotes import a09_sistema

    monkeypatch.setattr(a09_sistema, "ativar_o_servico", lambda: False)
    servico = _ServicoRecemLigado(acorda_na=0)
    aba.hefesto(_no_radio(), {"modo": "gamepad"}, servico)
    assert servico.perguntas == 0, "o Ligado perguntou ao serviço que já estava de pé"
    assert servico.pedidos


LER_A_TELA = r"""
(function(){
  const vis = el => !!el && getComputedStyle(el).display !== 'none';
  const ler = () => {
    const con = document.querySelector('.conectado');
    const nota = document.querySelector('.mesa-notas[data-campo="mesa-frase"]');
    return {
      ligado: document.querySelector('.hef-pos.ligado').classList.contains('on'),
      desligado: document.querySelector('.hef-pos.desligado').classList.contains('on'),
      secao_ligado: vis(document.querySelector('.hef-modo.so-ligado')),
      secao_desligado: vis(document.querySelector('.hef-modo.so-desligado')),
      topo: (con.innerText || '').replace(/\s+/g, ' ').trim(),
      cor_do_topo: getComputedStyle(con).color,
      bolinha: vis(con.querySelector('.bolinha')),
      frase_acesa: nota.classList.contains('ha'),
      frase: (nota.innerText || '').replace(/\s+/g, ' ').trim(),
    };
  };
  const fora = {};
  for (const [nome, carga] of CARGAS) { window.__hef.pintar(carga); fora[nome] = ler(); }
  return JSON.stringify(fora);
})()
"""


def _carga(ctx: Contexto) -> dict[str, Any]:
    """A carga que o piloto pinta neste tique: a da aba, o topo e os lugares sem dono."""
    para_pref = {str(m["uniq"]): str(m["pref"]) for m in ctx.mesa}
    carga = pacotes.normalizar(aba.pacote(ctx), para_pref)
    for chave, valor in pacotes.topo(ctx).items():
        carga["mesa"].setdefault(chave, valor)
    com_dono = [str(m["pref"]) for m in ctx.mesa]
    return dict(pacotes.apagar_os_lugares_sem_dono(carga, com_dono, pagina="01-jogar.html"))


def _no_webkit(roteiro: str) -> dict[str, Any]:
    """Abre o desenho da Jogar num WebKit offscreen, com o BOOTSTRAP do piloto, e roda o roteiro."""
    import json

    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    import hefesto_vivo

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.set_default_size(1228, 900)
    janela.show_all()

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as erro:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {erro}")
        Gtk.main_quit()

    def bootou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as erro:  # pragma: no cover
            saiu.append(f"ERRO no BOOTSTRAP: {erro}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None, None, bootou)

    view.connect("load-changed", carregou)
    view.load_uri((RAIZ / "mockup" / "01-jogar.html").as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


@pytest.fixture(scope="module")
def na_tela() -> dict[str, Any]:
    """O desenho da Jogar no motor dela: parado, de pé com dois no rádio, e parado de novo."""
    import json

    cargas = [["parado", _carga(_parado())], ["no_radio", _carga(_no_radio())],
              ["parado_de_novo", _carga(_parado())]]
    return _no_webkit(LER_A_TELA.replace("CARGAS", json.dumps(cargas)))


def test_no_webkit_o_servico_parado_marca_desligado_e_apaga_o_ponto_verde(
        na_tela: dict[str, Any]) -> None:
    """O que a pessoa vê: Desligado aceso, o topo sem a bolinha e noutra cor, a frase na mesa."""
    no_radio = na_tela["no_radio"]
    for nome in ("parado", "parado_de_novo"):
        fora = na_tela[nome]
        assert fora["desligado"] and not fora["ligado"], f"{nome}: o Status não marcou Desligado"
        assert fora["secao_desligado"] and not fora["secao_ligado"], (
            f"{nome}: a seção do Desligado não apareceu: {fora}")
        assert fora["topo"] == aba.SERVICO_DESLIGADO.rstrip("."), (
            f"{nome}: o topo disse {fora['topo']!r}")
        assert not fora["bolinha"], f"{nome}: o ponto verde ficou ao lado do desligado"
        assert fora["cor_do_topo"] != no_radio["cor_do_topo"], (
            f"{nome}: o topo do serviço parado tem a mesma cor ({fora['cor_do_topo']}) do de pé")
        assert fora["frase_acesa"] and fora["frase"] == aba.SERVICO_CALADO, (
            f"{nome}: a mesa não disse por que está vazia: {fora['frase']!r}")


def test_no_webkit_com_dois_no_radio_volta_ao_ligado_e_ao_verde(na_tela: dict[str, Any]) -> None:
    """A volta: o serviço respondeu e a tela desfaz o Desligado, a cor, a bolinha e a frase."""
    fora = na_tela["no_radio"]
    assert fora["ligado"] and not fora["desligado"], f"o Status não voltou ao Ligado: {fora}"
    assert fora["secao_ligado"] and not fora["secao_desligado"]
    assert fora["topo"] == "● 2 BT" and fora["bolinha"], f"o topo não voltou: {fora['topo']!r}"
    assert not fora["frase_acesa"], f"a frase ficou acesa com o serviço de pé: {fora['frase']!r}"
