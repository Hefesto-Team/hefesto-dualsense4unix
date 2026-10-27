#!/usr/bin/env python3
"""Com o serviço parado, a aba Jogar marca Desligado e não escreve frase nenhuma.

A queixa de 15/10/2026: «Sair» pela bandeja, a interface aberta com o serviço fora mostrou o Status
em Ligado, o topo com «Nenhum controle» ao lado do ponto verde e a mesa vazia sem dizer por quê,
com o Galactic Purple e o Cosmic Red ligados pelo rádio. O piloto entrega o estado vazio (`{}`)
depois da folga; o pacote é quem lia esse vazio como Ligado.

A ordem de 20/10/2026 (D-2010-O-SERVICO-PARADO-NAO-GANHA-FRASE, que revoga a
D-1610-A-JOGAR-DIZ-DESLIGADO-COM-O-SERVICO-PARADO), com a foto da aba: o Status em Desligado fica
como único sinal; o topo («O Hefesto está desligado») e a mesa («Esta tela parou de ler o serviço…»)
saem, e o topo some inteiro, sem texto e sem ponto.
"""
from __future__ import annotations

import pathlib
import sys
import types
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


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


def _textos(valor: Any) -> list[str]:
    """Todo texto de uma carga, em qualquer fundura."""
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, dict):
        return [t for v in valor.values() for t in _textos(v)]
    if isinstance(valor, (list, tuple)):
        return [t for v in valor for t in _textos(v)]
    return []


FRASES_QUE_SAIRAM = ("O Hefesto está desligado", "Esta tela parou de ler o serviço",
                     "Ela volta sozinha quando ele responder")


def test_com_o_servico_parado_nenhuma_frase_e_escrita() -> None:
    """A mesa, o topo e a coluna de avisos calam; só o Status diz Desligado.

    A MORDIDA: devolva `return "SERVICO_CALADO"` no `if not ctx.state` de `_frase_da_mesa`, o
    `"conta-b"` de `_o_que_o_topo_diz_da_mesa_vazia` ou a linha do selo SERVIÇO em `_avisos`, e
    este teste reprova.

    Prova da D-2010-O-SERVICO-PARADO-NAO-GANHA-FRASE.
    """
    ctx = _parado()
    pacote = aba.pacote(ctx)
    assert pacote["mesa-frase"] == "", f"a mesa disse {pacote['mesa-frase']!r}"
    topo = pacotes.topo(ctx)
    assert topo["conta-b"] == "", f"o topo disse {topo['conta-b']!r}"
    assert topo["servico"] == "parado"  # (noqa-acento)
    textos = _textos(pacote) + _textos(topo) + _textos(aba.coluna_de_atencao(ctx))
    for frase in FRASES_QUE_SAIRAM:
        achou = [t for t in textos if frase in t]
        assert not achou, f"a frase {frase!r} voltou: {achou}"


def test_o_simbolo_das_duas_frases_saiu_do_gerador() -> None:
    """Sem leitor, a constante sai: o nome que sobrasse chamaria o próximo a usá-la."""
    assert not hasattr(aba, "SERVICO_CALADO") and not hasattr(aba, "SERVICO_DESLIGADO")
    for caminho in (INTERFACE / "aba01.py", RAIZ / "mockup" / "01-jogar.html",
                    INTERFACE / "pacotes" / "a01_jogar.py", INTERFACE / "pacotes" / "__init__.py"):
        corpo = caminho.read_text(encoding="utf-8")
        for frase in ("O Hefesto está desligado.\"", "Esta tela parou de ler o serviço",
                      "Ela volta sozinha quando ele responder"):
            assert frase not in corpo, f"{caminho.name} ainda escreve {frase!r}"


def test_com_dois_controles_no_radio_volta_ao_ligado_e_aos_cartoes() -> None:
    """A volta: o primeiro estado que responder desfaz o Desligado, a frase e o topo."""
    ctx = _no_radio()
    fora = aba.pacote(ctx)
    assert fora["hef-posicao"] == "ligado"
    assert fora["mesa-frase"] == ""
    assert set(fora["cartoes"]) == {UNIQ_ROXO, UNIQ_VERMELHO}
    topo = pacotes.topo(ctx)
    assert topo["conta-b"] == "2 BT"
    assert topo["servico"] == "de-pe"  # (noqa-acento)


def test_servico_de_pe_sem_controle_continua_dizendo_que_nao_ha_controle() -> None:
    """O serviço respondeu e a mesa está vazia: aí «Nenhum controle» é verdade, e só o topo diz."""
    ctx = _de_pe_sem_controle()
    assert aba.pacote(ctx)["mesa-frase"] == ""
    assert pacotes.topo(ctx)["conta-b"] == pacotes.SEM_CONTROLE_NA_MESA


class _ServicoNotify:
    """O serviço de mentira com a unit `Type=notify`: o `systemctl start` só volta com o soquete
    de pé (o daemon diz `READY=1` quando escuta). Faz de janela antiga (o que `ativar_o_servico`
    consulta e aciona) e de ponte (o que o Ligado pergunta e manda). `volta_pronto=False` é o
    `Type=simple` de antes: o `start` volta antes do soquete e o modo cai."""

    def __init__(self, estado: str = "inactive", *, volta_pronto: bool = True,
                 rc: int = 0) -> None:
        self.estado = estado
        self.volta_pronto = volta_pronto
        self.rc = rc
        self.de_pe = estado == "active"
        self.verbos: list[str] = []
        self.pedidos: list[tuple[str, bool]] = []
        self._user_stopped_daemon = True

    def _is_service_active(self) -> str:
        return self.estado

    def _daemon_pid_alive(self) -> bool:
        return self.estado == "activating"

    def _invoke_systemctl(self, args: list[str], **_kw: Any) -> Any:
        self.verbos.append(args[0])
        if args[0] == "start" and self.rc == 0:
            self.estado = "active"
            self.de_pe = self.volta_pronto
        return types.SimpleNamespace(returncode=self.rc, stderr="Job failed" if self.rc else "")

    def daemon_state_full(self) -> dict[str, Any] | None:
        return dict(NO_RADIO) if self.de_pe else None

    def chamar(self, metodo: str, **_params: Any) -> bool:
        self.pedidos.append((metodo, self.de_pe))
        return self.de_pe


@pytest.fixture
def unit_instalada(monkeypatch: Any) -> Any:
    """Põe um `_ServicoNotify` no lugar da janela antiga e uma unit instalada de mentira."""
    from pacotes import a09_sistema

    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    def _instala(servico: _ServicoNotify) -> _ServicoNotify:
        monkeypatch.setattr(a09_sistema, "_matriz", lambda: servico)
        monkeypatch.setattr(ServiceInstaller, "detect_installed_unit",
                            lambda _self: pathlib.Path("hefesto-dualsense4unix.service"))
        return servico

    return _instala


def test_clicar_em_ligado_com_o_servico_parado_liga_o_servico(monkeypatch: Any) -> None:
    """O mesmo ato da aba Sistema; e o «Desligado» nunca liga o serviço."""
    from pacotes import a09_sistema

    chamadas: list[str] = []
    monkeypatch.setattr(a09_sistema, "ativar_o_servico",
                        lambda: chamadas.append("ligou") or True)
    monkeypatch.setattr(aba, "_hefesto_o_modo", lambda ctx, o, p: None)
    aba.hefesto(_parado(), {"modo": "gamepad"}, _ServicoNotify())
    assert chamadas == ["ligou"], "o Ligado não ligou o serviço"
    aba.hefesto(_parado(), {"modo": "native"}, None)
    assert chamadas == ["ligou"], "o Desligado ligou o serviço"


def test_o_modo_do_ligado_espera_o_servico_que_acabou_de_subir(unit_instalada: Any) -> None:
    """O `start` da unit `Type=notify` só volta com o soquete de pé, então o Ligado manda o modo
    logo depois, SEM espera própria: o modo chega ao serviço que acabou de subir.
    MORDIDA: com o `systemctl` de mentira voltando antes do soquete (`volta_pronto=False`, o
    `Type=simple` de antes), o modo cai e isto reprova.

    Prova da D-1610-O-LIGADO-ESPERA-O-SERVICO-RESPONDER.
    """
    servico = unit_instalada(_ServicoNotify("inactive"))
    aba.hefesto(_parado(), {"modo": "gamepad"}, servico)
    assert "start" in servico.verbos, "o Ligado não ligou o serviço"
    assert servico.pedidos, "o Ligado não mandou o modo"
    caidos = [metodo for metodo, de_pe in servico.pedidos if not de_pe]
    assert not caidos, f"o modo saiu antes de o serviço responder: {caidos}"


def test_o_ligado_nao_tem_espera_propria() -> None:
    """A espera de 10 s era o remendo de um chamador só; a cura é a unit, e ela não volta."""
    assert not hasattr(aba, "SEGUNDOS_ATE_O_SERVICO_RESPONDER")
    assert not hasattr(aba, "_esperar_o_servico_responder")


def test_o_start_que_falha_chega_a_tela_com_a_recusa_verdadeira(unit_instalada: Any) -> None:
    """Sem o IPC de pé o `start` falha (o `READY=1` não veio): a recusa é a do systemd."""
    servico = unit_instalada(_ServicoNotify("inactive", rc=1))
    with pytest.raises(RuntimeError, match="Job failed"):
        aba.hefesto(_parado(), {"modo": "gamepad"}, servico)
    assert not servico.pedidos, "mandou o modo sobre um serviço que não subiu"


def test_servico_ja_de_pe_nao_liga_de_novo(unit_instalada: Any) -> None:
    """Com o serviço de pé (`active`) o modo sai na hora, sem `start`."""
    servico = unit_instalada(_ServicoNotify("active"))
    aba.hefesto(_no_radio(), {"modo": "gamepad"}, servico)
    assert servico.verbos == [], "o Ligado religou o serviço que já estava de pé"
    assert servico.pedidos


def test_servico_subindo_o_ligado_se_junta_a_subida(unit_instalada: Any) -> None:
    """`activating` é o serviço SUBINDO: nem parado (que mandaria ligar um avulso) nem de pé.
    O `start` se junta à subida, volta pronto, e o modo chega.
    MORDIDA: tire o ramo `activating` de `ativar_o_servico` e o portão do pid avulso (o processo
    já vive) o dá por de pé: nenhum `start`, e o modo cai sobre o soquete que ainda não existe."""
    from pacotes import a09_sistema

    servico = unit_instalada(_ServicoNotify("activating"))
    assert a09_sistema.ativar_o_servico() is True
    assert servico.verbos[-1] == "start", f"não se juntou à subida: {servico.verbos}"
    assert servico._user_stopped_daemon is False, "o desligar do usuário não foi desarmado"
    aba.hefesto(_parado(), {"modo": "gamepad"}, servico)
    assert servico.pedidos
    assert all(de_pe for _m, de_pe in servico.pedidos)


def test_o_estado_activating_e_iniciando_com_ou_sem_processo(monkeypatch: Any) -> None:
    """MORDIDA: tire o ramo `activating` de `_daemon_status` e o processo vivo vira
    `online_avulso` (um daemon improvisado) e o sem processo, `offline`."""
    from hefesto_dualsense4unix.app.actions import daemon_actions as da
    from hefesto_dualsense4unix.utils import single_instance as si

    host = da.DaemonActionsMixin()
    monkeypatch.setattr(host, "_systemctl_oneline",
                        lambda args: "activating" if "is-active" in args else "enabled")
    for pid in (12345, None):
        monkeypatch.setattr(host, "_read_daemon_pid", lambda pid=pid: pid)
        monkeypatch.setattr(si, "is_alive", lambda _pid: True)
        assert host._daemon_status() == "iniciando", f"pid={pid}"


def test_o_prazo_do_start_cobre_o_da_unit(monkeypatch: Any) -> None:
    """O `start`/`restart` bloqueiam até o `READY=1`: o prazo de quem chama passa o
    `TimeoutStartSec` da unit; a consulta continua curta.
    MORDIDA: devolva o `timeout=5` fixo em `_invoke_systemctl` e isto reprova."""
    import subprocess

    from hefesto_dualsense4unix.app.actions import daemon_actions as da
    from hefesto_dualsense4unix.utils import sd_notify

    prazos: dict[str, float] = {}

    def _run(argv: list[str], **kw: Any) -> Any:
        prazos[argv[2]] = kw["timeout"]
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(da.subprocess, "run", _run)
    host = da.DaemonActionsMixin()
    for verbo in ("start", "restart", "is-active", "stop"):
        host._invoke_systemctl([verbo, "hefesto-dualsense4unix.service"])
    assert prazos["start"] > sd_notify.PRAZO_DA_PARTIDA_S
    assert prazos["restart"] > sd_notify.PRAZO_DA_PARTIDA_S
    assert prazos["is-active"] == da.PRAZO_DA_CONSULTA_S == 5.0
    assert prazos["stop"] == da.PRAZO_DA_CONSULTA_S


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
      topo_visivel: vis(con),
      topo: vis(con) ? (con.innerText || '').replace(/\s+/g, ' ').trim() : '',
      bolinha: vis(con) && vis(con.querySelector('.bolinha')),
      frase_acesa: !!nota && nota.classList.contains('ha'),
      frase: nota ? (nota.innerText || '').replace(/\s+/g, ' ').trim() : '',
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


def _no_webkit(roteiro: str, arquivo: str = "01-jogar.html") -> dict[str, Any]:
    """Abre o desenho de uma aba num WebKit offscreen, com o BOOTSTRAP do piloto, e roda o roteiro.

    `arquivo` é o nome do arquivo em `mockup/` (a Jogar, se nada se diz).
    """
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
        except Exception as erro:  # pragma: no cover
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
    view.load_uri((RAIZ / "mockup" / arquivo).as_uri())
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


def test_no_webkit_o_servico_parado_marca_desligado_e_nao_escreve_nada(
        na_tela: dict[str, Any]) -> None:
    """O que a pessoa vê: Desligado aceso, o topo sem texto e sem ponto, e a mesa sem frase.

    A MORDIDA: tire o `display:none` da regra `.fita-linha:has(i[data-servico="parado"]) .conectado`
    (`topo.html`, e o `regerar.py` a leva às dez) e `topo_visivel` volta a ser verdadeiro.
    """
    for nome in ("parado", "parado_de_novo"):
        fora = na_tela[nome]
        assert fora["desligado"] and not fora["ligado"], f"{nome}: o Status não marcou Desligado"
        assert fora["secao_desligado"] and not fora["secao_ligado"], (
            f"{nome}: a seção do Desligado não apareceu: {fora}")
        assert not fora["topo_visivel"], f"{nome}: o topo ficou na tela: {fora['topo']!r}"
        assert fora["topo"] == "" and not fora["bolinha"], f"{nome}: sobrou texto ou ponto"
        assert not fora["frase_acesa"] and fora["frase"] in ("", "—"), (
            f"{nome}: a mesa escreveu {fora['frase']!r}")


def test_no_webkit_com_dois_no_radio_volta_ao_ligado_e_ao_verde(na_tela: dict[str, Any]) -> None:
    """A volta: o serviço respondeu e a tela desfaz o Desligado, a cor, a bolinha e a frase."""
    fora = na_tela["no_radio"]
    assert fora["ligado"] and not fora["desligado"], f"o Status não voltou ao Ligado: {fora}"
    assert fora["secao_ligado"] and not fora["secao_desligado"]
    assert not fora["topo_visivel"], f"o contador voltou ao topo: {fora['topo']!r}"
    assert not fora["frase_acesa"], f"a frase ficou acesa com o serviço de pé: {fora['frase']!r}"


AS_DEZ = ("01-jogar.html", "02-controles.html", "03-gatilhos.html", "04-iluminacao.html",
          "05-vibracao.html", "06-navegacao.html", "07-lancadores.html", "08-conexoes.html",
          "09-sistema.html", "10-perfis.html")

LER_O_TOPO = r"""
(function(){
  const vis = el => !!el && getComputedStyle(el).display !== 'none';
  const fora = {};
  for (const [nome, carga] of CARGAS) {
    window.__hef.pintar(carga);
    const con = document.querySelector('.conectado');
    const linha = document.querySelector('.fita-linha').getBoundingClientRect();
    const chip = document.querySelector('.perfil-ativo').getBoundingClientRect();
    fora[nome] = {achou: !!con, visivel: vis(con),
                  texto: vis(con) ? (con.innerText || '').replace(/\s+/g, ' ').trim() : '',
                  folga_do_chip: Math.round(linha.right - chip.right)};
  }
  return JSON.stringify(fora);
})()
"""


@pytest.fixture(scope="module")
def o_topo_das_dez() -> dict[str, dict[str, Any]]:
    """O topo de cada aba no motor dela: parado, de pé com dois no rádio, e parado de novo."""
    import json

    def so_o_topo(ctx: Contexto) -> dict[str, Any]:
        return {"mesa": dict(pacotes.topo(ctx))}

    cargas = json.dumps([["parado", so_o_topo(_parado())], ["no_radio", so_o_topo(_no_radio())],
                         ["parado_de_novo", so_o_topo(_parado())]])
    return {aba_html: _no_webkit(LER_O_TOPO.replace("CARGAS", cargas), aba_html)
            for aba_html in AS_DEZ}


@pytest.mark.parametrize("aba_html", AS_DEZ)
def test_no_webkit_o_topo_das_dez_some_com_o_servico_parado(
        o_topo_das_dez: dict[str, dict[str, Any]], aba_html: str) -> None:
    """O topo é o mesmo nas dez abas: com o serviço parado ele some em todas, não só na Jogar.

    A regra morou só na `aba01.py` e as outras nove mostravam «● —» em verde com o serviço fora.
    A MORDIDA: devolva a regra à `aba01.py` (fora do `topo.html`), rode o `regerar.py`, e as
    nove reprovam aqui; a volta ao verde com dois no rádio prova que a régua acha o topo.
    """
    fora = o_topo_das_dez[aba_html]
    for nome in ("parado", "no_radio", "parado_de_novo"):
        assert not fora[nome]["achou"], (
            f"{aba_html} {nome}: o contador voltou ao topo: {fora[nome]['texto']!r}")


@pytest.mark.parametrize("aba_html", AS_DEZ)
def test_no_webkit_o_perfil_ativo_fica_a_direita_com_o_servico_parado(
        o_topo_das_dez: dict[str, dict[str, Any]], aba_html: str) -> None:
    """Com o topo fora, o «Perfil ativo» continua encostado na direita, onde ele mora de pé.

    Quem empurrava era a `.conectado`; com ela em `display:none` o chip caía ao lado da marca.
    A MORDIDA: tire a regra `.fita-linha:has(i[data-servico="parado"]) .perfil-ativo` do
    `topo.html`, rode o `regerar.py`, e a folga do chip vira a largura da faixa inteira.

    Prova da D-2110-O-PERFIL-ATIVO-FICA-A-DIREITA-COM-O-SERVICO-PARADO.
    """
    fora = o_topo_das_dez[aba_html]
    de_pe = fora["no_radio"]["folga_do_chip"]
    for nome in ("parado", "parado_de_novo"):
        assert fora[nome]["folga_do_chip"] == de_pe, (
            f"{aba_html} {nome}: o chip saiu da direita (folga {fora[nome]['folga_do_chip']} px, "
            f"de pé {de_pe} px)")
