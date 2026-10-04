#!/usr/bin/env python3
"""CADA BOTÃO DA ABA SISTEMA FAZ O QUE DIZ — SISTEMA-BOTOES-01, 13/09/2026.

A palavra dela está no índice da leva
(o registro «A-TERCEIRA-LISTA-DELA-INDICE» de 13/09/2026): *«não sei
se nossos botões da aba sistema fazem o que deveriam fazer de fato e se
funcionam»*. O estudo mediu os catorze gestos e achou metade deles em parte:
armavam sem a pergunta que o `title` promete, piscavam verde sobre um clique que
não fez nada, e recusavam calados.

O QUE ESTA RÉGUA COBRA — o §V da sprint:

1. **o painel em repouso não pede o diário** (`-n 0` no `systemctl status`);
2. **a pergunta vencida sai no tique seguinte**, e o censo das camadas fica;
3. **o clique que só arma devolve `armou`**, a chave que o piloto lê;
4. **o clique 1 de Parar, Restaurar, Proton, Consertos e Aplicar pergunta** no
   painel, e o clique 2 limpa antes de agir;
5. **o Proton recusa no clique 1** com a Steam aberta ou sem `proton-pin.conf`,
   sem armar e sem chamar a fixação;
6. **os consertos rodam só o vigia da Steam** — o `--install` do WirePlumber
   saiu;
7. **o «Ver os plugins» não está em página nenhuma**;
8. **na tela viva** (piloto oculto): cinco recusas vestem `hef-recusou` sem
   frase na tela, e cinco cliques que armam não piscam e põem a pergunta no
   painel.

NENHUM ATO REAL: o `systemctl` é o da janela de mentira, a Steam, o Proton, a
janela da Steam, o perfil de fábrica e os scripts são dublês. O que a régua mede
é o caminho do clique até o pixel.
"""
from __future__ import annotations

import contextlib
import html
import io
import json
import os
import pathlib
import re
import sys
import textwrap
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "09-sistema.html"
PUBLICADA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas" / PAGINA

ARMAM = ("parar-ou-retomar", "restaurar-de-fabrica",
         "refazer-consertos", "aplicar-aos-jogos")
PERGUNTA_E_O_TITLE = ("parar-ou-retomar", "restaurar-de-fabrica")

RECUSAS = ("atualizar", "corrigir-modo", "fixar-proton",
           "aplicar-aos-jogos")

REPOUSO = "repouso da régua"


class JanelaDeMentira:
    """O dublê de `DaemonActionsMixin`: guarda o que TERIA ido ao systemd."""

    def __init__(self) -> None:
        self.status = "online_systemd"
        self.comandos: list[list[str]] = []
        self._user_stopped_daemon: bool | None = None

    def _daemon_status(self) -> str:
        return self.status

    def _systemctl_status_text(self, unit: str) -> str:
        return "● unidade ativa"

    def _is_service_active(self) -> str:
        return "active"

    def _daemon_pid_alive(self) -> bool:
        return False

    def _find_repo_file(self, relpath: str) -> pathlib.Path:
        return pathlib.Path("/nao-existe") / relpath

    def _invoke_systemctl(self, args, capture=False, check=False):
        self.comandos.append(list(args))

        class R:
            returncode = 0
            stderr = ""

        return R()

    def atos(self) -> list[str]:
        return [a[0] for a in self.comandos if a and a[0] != "reset-failed"]


def _limpar(mod: Any) -> None:
    mod._LENTO.clear()
    mod._ARMADO.clear()
    mod._PAINEL[0] = None
    mod._PERGUNTA.clear()
    mod._ANTES_DO_CONSERTO.clear()


@pytest.fixture
def a09(monkeypatch):
    from pacotes import a09_sistema as mod

    mod._JANELA_ANTIGA[:] = [JanelaDeMentira()]
    monkeypatch.setattr(mod, "_autostart", lambda: "enabled")
    _limpar(mod)
    yield mod
    mod._JANELA_ANTIGA.clear()
    _limpar(mod)


@pytest.fixture
def janela(a09):
    return a09._JANELA_ANTIGA[0]


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={"paused": False, "controllers": []},
                            mesa=[], conectados=[], estados={})


@pytest.fixture
def pin(monkeypatch, tmp_path):
    """O Proton de mentira: um `proton-pin.conf` que existe e a Steam fechada."""
    from hefesto_dualsense4unix.integrations import proton_pin

    conf = tmp_path / "proton-pin.conf"
    conf.write_text("# conf de prova\n", encoding="utf-8")
    estado: dict[str, Any] = {"steam": False, "conf": lambda: conf, "travou": [],
                              "com": [], "pino": True}
    monkeypatch.setattr(proton_pin, "default_pin_conf_path",
                        lambda: estado["conf"]())
    monkeypatch.setattr(proton_pin, "pino_instalado_nesta_maquina",
                        lambda: estado["pino"])
    monkeypatch.setattr(proton_pin, "steam_running", lambda: estado["steam"])
    monkeypatch.setattr(proton_pin, "default_lock_state_path",
                        lambda *a, **k: tmp_path / "proton-lock-state.json")
    monkeypatch.setattr(proton_pin, "lock_proton_for_all_games",
                        lambda *a, **k: (estado["travou"].append(a),
                                         estado["com"].append(k))[0] or {})
    return estado


@pytest.fixture
def armaveis(a09, pin, monkeypatch, tmp_path):
    """O que os cinco precisam para ARMAR sem tocar na máquina de ninguém."""
    from hefesto_dualsense4unix.app.actions import footer_actions

    asset = tmp_path / "personalizado.json"
    asset.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(footer_actions, "_meu_perfil_asset", lambda: asset)
    monkeypatch.setattr(a09._daemon, "medir_jogos_com_steam_input", lambda: [])
    return pin


def _clique(texto: str) -> dict[str, str]:
    return {"texto": texto}


def _gesto(nome: str) -> Any:
    import pacotes

    acao = pacotes.gesto_da_pagina(PAGINA, nome)
    assert acao is not None, f"o `{nome}` perdeu o dono"
    return acao


def _title_publicado(nome: str) -> str:
    """O `title` do botão na página que o PRODUTO renderiza."""
    for tag in re.findall(r"<button\b[^>]*>", PUBLICADA.read_text(encoding="utf-8")):
        if f'data-gesto="{nome}"' in tag:
            achado = re.search(r'title="([^"]*)"', tag)
            return html.unescape(achado.group(1)) if achado else ""
    return ""


def _sem_quebra(texto: str) -> str:
    return " ".join(str(texto).split())


def _vencer(mod: Any) -> None:
    """Empurra o relógio do consentimento para trás — o prazo é do produto."""
    mod._ARMADO["ate"] -= mod.segundos_para_confirmar() + 1


def test_o_painel_em_repouso_nao_pede_o_diario(monkeypatch):
    """Sem `-n 0`, o `status` emenda as últimas linhas do diário do daemon."""
    from hefesto_dualsense4unix.app.actions import daemon_actions as da

    pedidos: list[list[str]] = []

    class R:
        stdout = "● unidade"
        stderr = ""

    matriz = da.DaemonActionsMixin()
    monkeypatch.setattr(matriz, "_invoke_systemctl",
                        lambda args, **k: pedidos.append(list(args)) or R())

    assert matriz._systemctl_status_text("hefesto.service") == "● unidade"
    (args,) = pedidos
    assert args[:2] == ["status", "hefesto.service"], args
    assert "-n" in args and args[args.index("-n") + 1] == "0", (
        f"o `status` do repouso pede o diário junto: {args}")


def test_a_chave_do_clique_que_so_arma_e_a_do_piloto(a09):
    """As duas pontas do contrato com a FRASES-E-DICAS-01 dizem a mesma palavra."""
    pytest.importorskip("gi", reason="o piloto importa o GTK")
    import hefesto_vivo as hv

    assert a09.ARMOU == hv.CHAVE_DO_CLIQUE_QUE_SO_ARMOU


@pytest.mark.parametrize("nome", ARMAM)
def test_o_clique_1_arma_pergunta_e_nao_age(a09, ctx, janela, armaveis, nome):
    """O clique 1 devolve `armou`, a pergunta vai ao painel, e nada sai."""
    carga = _gesto(nome)(ctx, _clique(a09._rotulo_do_desenho(nome)), None)

    assert carga.get(a09.ARMOU) is True, f"o clique 1 do `{nome}` não disse que só armou"
    assert a09._armado_agora() == nome
    assert carga["blocos"][f'[data-gesto="{nome}"]'] == a09.CONFIRMA
    texto = carga.get("mesa", {}).get(a09.REGISTRO, "")
    assert texto == a09._PAINEL[0], "a pergunta foi à tela e não ficou guardada"
    assert texto.rstrip().endswith(a09.CLIQUE_DE_NOVO), texto
    if nome in PERGUNTA_E_O_TITLE:
        dica = _title_publicado(nome)
        assert dica, f"o `{nome}` perdeu o `title` na página publicada"
        assert _sem_quebra(dica) in _sem_quebra(texto), (
            f"a pergunta do `{nome}` não é o `title` que o botão promete: {texto!r}")
    assert janela.atos() == [], f"o clique 1 do `{nome}` mandou {janela.atos()}"
    assert armaveis["travou"] == []


def test_o_clique_2_limpa_o_painel_antes_de_agir(a09, ctx, janela):
    """A pergunta não pode ficar dizendo «clique de novo» sobre um ato já dado."""
    a09.desligar(ctx, _clique(a09._rotulo_do_desenho(a09.DESLIGAR)), None)
    a09.desligar(ctx, _clique(a09.CONFIRMA), None)

    assert janela.atos() == ["stop"]
    assert a09._PAINEL[0] is None, a09._PAINEL[0]
    assert a09._no_painel(REPOUSO) == REPOUSO


def test_a_pergunta_vencida_sai_no_tique_seguinte(a09, ctx):
    """Aos 20 s o botão volta ao rótulo do desenho — e o painel volta junto."""
    carga = a09.desligar(ctx, _clique(a09._rotulo_do_desenho(a09.DESLIGAR)), None)
    pergunta = carga["mesa"][a09.REGISTRO]
    assert a09._no_painel(REPOUSO) == pergunta

    _vencer(a09)

    assert a09._no_painel(REPOUSO) == REPOUSO, (
        "o consentimento venceu e o painel continua pedindo o segundo clique")


def test_a_recusa_de_outro_botao_tira_a_pergunta_no_tique(a09, ctx, pin):
    """Outro botão desarmou o `desligar`: a pergunta dele não vale mais."""
    a09.desligar(ctx, _clique(a09._rotulo_do_desenho(a09.DESLIGAR)), None)
    pin["steam"] = True
    with pytest.raises(RuntimeError):
        a09.fixar_proton(ctx, {}, None)

    assert a09._armado_agora() == ""
    assert a09._no_painel(REPOUSO) == REPOUSO


def test_o_proton_com_a_steam_aberta_recusa_no_clique_1(a09, ctx, pin):
    """Na máquina dela a Steam fica aberta: o botão armava calado e recusava calado.

    MORDIDA: tire o `_porque_o_proton_nao_trava` de `fixar_proton`.
    """
    pin["steam"] = True
    with pytest.raises(RuntimeError):
        a09.fixar_proton(ctx, {}, None)

    assert a09._PAINEL[0] is None, "a recusa escreveu no painel"
    assert pin["travou"] == []


def test_o_proton_sem_o_pino_no_disco_recusa_no_clique_1_com_a_frase_dele(a09, ctx, pin):
    """O `proton-pin.conf` presente e o Proton pinado ausente — o install sem
    rede, ou feito antes de existir Steam (INSTALL-UNIVERSAL, 18/09/2026). O
    botão armava, e no clique 2 a tela dizia "a Steam recusou a mudança": uma
    causa falsa.

    MORDIDA: tire a pergunta ao `pino_instalado_nesta_maquina` de
    `_porque_o_proton_nao_trava`.
    """
    pin["pino"] = False
    with pytest.raises(RuntimeError) as recusa:
        a09.fixar_proton(ctx, {}, None)

    assert str(recusa.value) == a09._daemon.frase_sem_o_proton_pinado()
    assert pin["travou"] == []


def test_o_proton_no_clique_2_trava_todo_jogo(a09, ctx, pin):
    """A ordem dela de 17/09 chega ao botão — INSTALL-UNIVERSAL, 18/09/2026."""
    with contextlib.redirect_stderr(io.StringIO()):
        a09.fixar_proton(ctx, {}, None)

    assert len(pin["travou"]) == 1, pin
    assert pin["com"][0].get("todos") is True, pin["com"]


def _sem_caminho() -> None:
    return None


def _levanta() -> None:
    raise FileNotFoundError("proton-pin.conf")


@pytest.mark.parametrize("como", ["arquivo-ausente", "sem-caminho", "levanta"])
def test_o_proton_sem_o_conf_recusa_em_vez_de_rebentar(a09, ctx, pin, tmp_path, como):
    """Instalação por pacote não tem `proton-pin.conf`: recusa, nunca exceção crua."""
    pin["conf"] = {"arquivo-ausente": lambda: tmp_path / "nao-existe.conf",
                   "sem-caminho": _sem_caminho, "levanta": _levanta}[como]

    with pytest.raises(RuntimeError):
        a09.fixar_proton(ctx, {}, None)

    assert pin["travou"] == []


def test_os_consertos_so_rodam_o_vigia_da_steam(a09, ctx, monkeypatch):
    """O `--install` do WirePlumber é o gesto contrário ao de ligar o mic.

    MORDIDA: devolva `("scripts/fix_wireplumber_default_source.sh",
    ["--install"])` a `CONSERTOS`.
    """
    import subprocess

    rodou: list[list[str]] = []

    class Proc:
        returncode = 0
        stdout = "[steam-input] resultado=aplicado\n"
        stderr = ""

    def run(args, **_k):
        rodou.append([pathlib.Path(args[1]).name, *args[2:]])
        return Proc()

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(a09._daemon, "medir_jogos_com_steam_input", lambda: [])
    acao = _gesto("refazer-consertos")

    acao(ctx, _clique(a09._rotulo_do_desenho("refazer-consertos")), None)
    with contextlib.redirect_stderr(io.StringIO()):
        acao(ctx, _clique(a09.CONFIRMA), None)

    assert rodou == [["disable_steam_input.sh", "--apply-quiet"]], rodou
    assert a09._PAINEL[0] is None


def test_o_title_dos_consertos_nao_promete_o_que_nao_faz():
    """Nenhum script põe a linha de inicialização, e o áudio saiu com o `--install`."""
    dica = _title_publicado("refazer-consertos")
    assert dica, "o botão dos consertos perdeu o `title`"
    for promessa in ("linha de inicialização", "áudio"):
        assert promessa not in dica, dica


@pytest.mark.parametrize("publicado", [True, False], ids=["publicado", "bancada"])
def test_o_ver_os_plugins_nao_esta_em_pagina_nenhuma(a09, publicado):
    """D-OS-PLUGINS-APARECEM-ONDE-AGEM, dela, em `docs/data/decisoes-dela.csv`.

    MORDIDA: devolva o `item_cinza("Ver os plugins", …)` ao gerador e publique.
    """
    import onde

    corpo = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    assert 'data-gesto="ver-plugins"' not in corpo
    assert "Ver os plugins" not in corpo
    assert a09.BOTOES_CINZAS == ("reiniciar",)


ROTEIRO = (
    ("recusa", "atualizar"), ("recusa", "corrigir-modo"),
    ("steam", "aberta"), ("recusa", "fixar-proton"), ("steam", "fechada"),
    ("arma", "parar-ou-retomar"), ("foto", "depois-a-pergunta-do-parar"),
    ("arma", "restaurar-de-fabrica"),
    ("arma", "refazer-consertos"), ("arma", "aplicar-aos-jogos"),
    ("vence", "aplicar-aos-jogos"), ("foto", "depois-a-pergunta-vencida"),
    ("rearma", "aplicar-aos-jogos"), ("recusa", "aplicar-aos-jogos"),
    ("janela", "jogo_aberto"), ("rearma", "aplicar-aos-jogos"),
    ("recibo", "aplicar-aos-jogos"), ("foto", "depois-o-recibo-do-jogo-aberto"),
)

PASSO_MS = 50
TETO_S = 10.0
TETO_DA_PAGINA_S = 30.0
TETO_DO_ROTEIRO_S = 180.0

TRECHO = 40

VIGIAR_E_CLICAR = r"""
(function(sel, marco){
  const b = document.querySelector(sel);
  if(!b) return 'NAO ACHEI ' + sel;
  window.__reguaTrilhas = window.__reguaTrilhas || {};
  const trilha = window.__reguaTrilhas[marco] = [];
  let visto = null;
  function anotar(){
    const el = document.querySelector(sel);
    const assinatura = el
      ? el.className + '|' + (el.getAttribute('data-hef-voo') || '') : '';
    if(assinatura === visto) return;
    visto = assinatura;
    trilha.push({t: performance.now(), classes: el ? el.className : '',
                 voo: el ? (el.getAttribute('data-hef-voo') || '') : ''});
  }
  new MutationObserver(anotar).observe(document.documentElement,
    {subtree: true, childList: true, attributes: true});
  anotar();
  b.click();
  return 'cliquei';
})(%s, %s)
"""

LER_A_TRILHA = r"""
(function(marco){
  const t = (window.__reguaTrilhas || {})[marco];
  return JSON.stringify({agora: performance.now(), trilha: t === undefined ? null : t});
})(%s)
"""

LER_O_PAINEL = r"""
(function(g){
  const p = document.querySelector('[data-campo="registro-texto"]');
  const b = document.querySelector('[data-gesto="' + g + '"]');
  return JSON.stringify({painel: p ? (p.textContent || '').trim() : null,
                         rotulo: b ? (b.textContent || '').trim() : null});
})(%s)
"""

LER_A_TELA = r"""
(function(frase){
  const em = function(atr){
    return Array.prototype.filter.call(document.querySelectorAll('[' + atr + ']'),
      function(e){ return (e.getAttribute(atr) || '').indexOf(frase) >= 0; }).length;
  };
  const visivel = document.body ? (document.body.innerText || '') : '';
  return JSON.stringify({
    recados: document.querySelectorAll('.hef-recado').length,
    visivel: visivel.indexOf(frase) >= 0,
    dica: em('data-hef-dica'),
    title: em('title'),
  });
})(%s)
"""


def _pousou(trilha: list[dict]) -> dict | None:
    """A foto em que o botão SAIU do voo depois de ter entrado nele."""
    voou = False
    for foto in trilha:
        if foto.get("voo"):
            voou = True
        elif voou:
            return foto
    return None


def _acesas(trilha: list[dict]) -> list[dict]:
    return [foto for foto in trilha
            if {"hef-deu-certo", "hef-recusou"} & set(str(foto["classes"]).split())]


@pytest.fixture(scope="module")
def na_tela(tmp_path_factory) -> dict:
    """Abre o piloto DE VERDADE, oculto, na 09, e anda o `ROTEIRO`."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import time as _time

    import hefesto_vivo as hv
    from hefesto_dualsense4unix.app.actions import footer_actions
    from hefesto_dualsense4unix.integrations import proton_pin
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    a9 = sys.modules[hv.pacotes.gesto_da_pagina(PAGINA, "atualizar").__module__]

    berco = tmp_path_factory.mktemp("sistema-botoes")
    conf = berco / "proton-pin.conf"
    conf.write_text("# conf de prova\n", encoding="utf-8")
    asset = berco / "personalizado.json"
    asset.write_text("{}", encoding="utf-8")
    steam = {"aberta": False, "janela": "nao_fechou"}
    travou: list[object] = []
    fechou: list[object] = []
    leitura = a9._tela.Leitura(
        status="online_systemd", autostart=True, state={"paused": False},
        achados=None, deteccao=None, ambiente=None, perfil=None)

    def janela_da_steam(fn: object, *_a: object, **_k: object) -> tuple[str, None]:
        # `nao_fechou` é a recusa que SEGUE sendo recusa; o `jogo_aberto` virou
        # recibo (03/10/2026) e o roteiro troca para ele no passo `janela`.
        fechou.append(fn)
        return (steam["janela"], None)

    dubles: dict[tuple[Any, str], Any] = {
        (proton_pin, "default_pin_conf_path"): lambda: conf,
        (proton_pin, "pino_instalado_nesta_maquina"): lambda: True,
        (proton_pin, "steam_running"): lambda: steam["aberta"],
        (proton_pin, "lock_proton_for_all_games"): lambda *a, **k: travou.append(a) or {},
        (slo, "with_steam_closed"): janela_da_steam,
        (footer_actions, "_meu_perfil_asset"): lambda: asset,
        (a9._daemon, "medir_jogos_com_steam_input"): lambda: [],
        (a9, "_leitura"): lambda _ctx: leitura,
        (hv.mesa_viva, "estado_do_daemon"): lambda *a, **k: {
            "active_profile": "regua", "paused": False, "controllers": []},
        (hv.ponte, "chamar"): lambda *a, **k: False,
        (hv.ponte, "chamar_detalhado"): lambda *a, **k: (False, None),
    }
    velhos = {chave: getattr(*chave) for chave in dubles}
    pacote_velho = hv.pacotes.PACOTES.get(PAGINA)
    janela_velha = list(a9._JANELA_ANTIGA)
    for (dono, nome), valor in dubles.items():
        setattr(dono, nome, valor)
    a9._JANELA_ANTIGA[:] = [JanelaDeMentira()]
    _limpar(a9)
    hv.pacotes.PACOTES[PAGINA] = lambda _ctx: {
        a9.REGISTRO: a9._no_painel(REPOUSO), "blocos": a9.blocos_dos_botoes(True)}

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre=PAGINA, prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    faltou: dict[str, str] = {}
    fora: dict[str, Any] = {"faltou": faltou, "travou": travou, "fechou": fechou,
                            "clique_de_novo": a9.CLIQUE_DE_NOVO}
    diario = io.StringIO()
    no_ar = {"sim": True}
    passos = list(ROTEIRO)
    fotos = os.environ.get("SISTEMA_BOTOES_FOTOS", "")

    def js(valor: object) -> str:
        return json.dumps(valor)

    def esperar(marco: str, pergunta: str, achar, depois, o_que: str) -> None:
        comeco = _time.monotonic()

        def perguntar() -> bool:
            if no_ar["sim"]:
                piloto.ponte.perguntar(pergunta, respondeu)
            return False

        def respondeu(valor, erro) -> None:
            if not no_ar["sim"]:
                return
            lido = None
            if erro is None and valor is not None:
                try:
                    lido = json.loads(str(valor))
                except ValueError:
                    lido = None
            achado = None if lido is None else achar(lido)
            if achado is not None:
                fora[marco] = achado
                depois()
            elif _time.monotonic() - comeco >= TETO_S:
                visto = f"ERRO {erro}" if erro is not None else repr(lido)
                faltou[marco] = (f"{o_que} — não chegou em {TETO_S:.0f} s; a "
                                 f"última leitura foi …{visto[-400:]}")
                depois()
            else:
                GLib.timeout_add(PASSO_MS, perguntar)

        perguntar()

    def clicar(gesto_: str, marco: str) -> None:
        piloto.ponte.perguntar(
            VIGIAR_E_CLICAR % (js(f'[data-gesto="{gesto_}"]'), js(marco)),
            lambda v, e: fora.__setitem__(f"{marco}:clique", str(v)))

    def proximo() -> None:
        if not passos:
            fora["diario"] = diario.getvalue()
            Gtk.main_quit()
            return
        tipo, alvo = passos.pop(0)
        if tipo == "steam":
            steam["aberta"] = alvo == "aberta"
            proximo()
        elif tipo == "foto":
            if fotos:
                piloto.tela.fotografar(str(pathlib.Path(fotos) / f"{alvo}.png"))
            proximo()
        elif tipo == "janela":
            steam["janela"] = alvo
            proximo()
        elif tipo == "recusa":
            recusa(alvo)
        elif tipo == "recibo":
            recusa(alvo, recibo=True)
        elif tipo in ("arma", "rearma"):
            arma(alvo, f"{tipo}:{alvo}")
        else:
            vence(alvo)

    def recusa(gesto_: str, recibo: bool = False) -> None:
        marco = f"{'recibo' if recibo else 'recusa'}:{gesto_}"

        def assentou_a_recusa(lido: dict) -> dict | None:
            trilha = lido.get("trilha")
            if not isinstance(trilha, list):
                return None
            pouso = _pousou(trilha)
            if pouso is None:
                return None
            if lido["agora"] - pouso["t"] < hv.MS_DA_PISCADA + 300:
                return None
            return {"pouso": pouso, "trilha": trilha}

        def ler_a_tela() -> None:
            desfecho = list(piloto.desfechos.get(f"{PAGINA}:{gesto_}", ()))
            fora[f"{marco}:desfecho"] = desfecho
            frase = str(desfecho[1]).split(": ", 1)[-1] if len(desfecho) == 2 else ""
            fora[f"{marco}:frase"] = frase
            if recibo:
                esperar(f"{marco}:painel", LER_O_PAINEL % js(gesto_),
                        lambda lido: lido if "Steam fica" in (lido.get("painel") or "")
                        else None, proximo, "o painel dizer o recibo do jogo aberto")
                return
            esperar(f"{marco}:tela", LER_A_TELA % js(frase[:TRECHO] or "sem frase de recusa"),
                    lambda lido: lido, proximo, f"a leitura da tela depois do {gesto_}")

        def agora_clica() -> None:
            clicar(gesto_, marco)
            esperar(marco, LER_A_TRILHA % js(marco), assentou_a_recusa, ler_a_tela,
                    f"o {gesto_} pousar e a piscada passar")

        if a9._armado_agora() == gesto_:
            esperar(f"{marco}:armado", LER_O_PAINEL % js(gesto_),
                    lambda lido: lido if lido.get("rotulo") == a9.CONFIRMA else None,
                    agora_clica, f"o {gesto_} vestir «Confirma?»")
        else:
            agora_clica()

    def arma(gesto_: str, marco: str) -> None:
        def pousou_e_passou(lido: dict) -> dict | None:
            trilha = lido.get("trilha")
            if not isinstance(trilha, list):
                return None
            pouso = _pousou(trilha)
            if pouso is None or lido["agora"] - pouso["t"] < hv.MS_DA_PISCADA + 300:
                return None
            return {"pouso": pouso, "trilha": trilha}

        def ler_o_painel() -> None:
            fora[f"{marco}:desfecho"] = list(
                piloto.desfechos.get(f"{PAGINA}:{gesto_}", ()))
            esperar(f"{marco}:painel", LER_O_PAINEL % js(gesto_),
                    lambda lido: lido if lido.get("rotulo") == a9.CONFIRMA else None,
                    proximo, f"o {gesto_} vestir «Confirma?»")

        clicar(gesto_, marco)
        esperar(marco, LER_A_TRILHA % js(marco), pousou_e_passou, ler_o_painel,
                f"o {gesto_} pousar e o prazo da piscada passar")

    def vence(gesto_: str) -> None:
        a9._ARMADO["ate"] = 0.0
        desenho = a9._rotulo_do_desenho(gesto_)
        esperar(f"vence:{gesto_}", LER_O_PAINEL % js(gesto_),
                lambda lido: lido if (lido.get("painel") == REPOUSO
                                      and lido.get("rotulo") == desenho) else None,
                proximo, "o tique tirar a pergunta vencida e repor o rótulo")

    def comecar() -> bool:
        if not (piloto.pagina == PAGINA and piloto.pronto):
            return True
        esperar("repouso", LER_O_PAINEL % js("desligar"),
                lambda lido: lido if lido.get("painel") == REPOUSO else None,
                em_repouso, "o painel em repouso")
        return False

    def em_repouso() -> None:
        if fotos:
            piloto.tela.fotografar(str(pathlib.Path(fotos) / "depois-repouso.png"))
        proximo()

    GLib.timeout_add(300, lambda: piloto._ir(PAGINA) and False)
    GLib.timeout_add(600, comecar)
    guarda = GLib.timeout_add(int(TETO_DO_ROTEIRO_S * 1000), Gtk.main_quit)
    try:
        limite = _time.monotonic() + TETO_DO_ROTEIRO_S
        with contextlib.redirect_stderr(diario):
            while "diario" not in fora and _time.monotonic() < limite:
                Gtk.main()
    finally:
        no_ar["sim"] = False
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        for (dono, nome), valor in velhos.items():
            setattr(dono, nome, valor)
        if pacote_velho is None:
            hv.pacotes.PACOTES.pop(PAGINA, None)
        else:
            hv.pacotes.PACOTES[PAGINA] = pacote_velho
        _limpar(a9)
        a9._JANELA_ANTIGA[:] = janela_velha
    assert "diario" in fora, (
        f"o roteiro não chegou ao fim — voltou {sorted(fora)}, faltou {faltou}")
    return fora


def _marco(medido: dict, marco: str) -> Any:
    falta = medido["faltou"].get(marco)
    assert falta is None, f"o marco `{marco}` não chegou: {falta}"
    assert marco in medido, f"o roteiro não passou por `{marco}`: {sorted(medido)}"
    return medido[marco]


@pytest.mark.parametrize("gesto_", RECUSAS)
def test_na_tela_a_recusa_veste_o_botao_e_nao_escreve(na_tela: dict, gesto_: str) -> None:
    """Sem frase na tela, a piscada de recusa é o que diz que o clique não valeu."""
    marco = f"recusa:{gesto_}"
    assert na_tela.get(f"{marco}:clique") == "cliquei", na_tela.get(f"{marco}:clique")
    desfecho = _marco(na_tela, f"{marco}:desfecho")
    assert desfecho and desfecho[0] == "recusou dizendo", desfecho

    classes = str(_marco(na_tela, marco)["pouso"]["classes"]).split()
    assert "hef-recusou" in classes and "hef-deu-certo" not in classes, classes

    tela = _marco(na_tela, f"{marco}:tela")
    assert tela == {"recados": 0, "visivel": False, "dica": 0, "title": 0}, (
        f"a frase da recusa do `{gesto_}` chegou à tela: {tela} — "
        f"{na_tela[f'{marco}:frase']!r}")

    prefixo = f"[gesto falhou] {PAGINA} · {gesto_}: "
    assert any(linha.startswith(prefixo)
               for linha in str(na_tela["diario"]).splitlines()), (
        f"a recusa do `{gesto_}` não chegou ao diário")


def test_na_tela_nenhuma_recusa_fixou_o_proton_nem_fechou_a_steam(na_tela: dict) -> None:
    """A Steam aberta recusou antes da fixação; a janela da Steam só no clique 2."""
    _marco(na_tela, "recusa:fixar-proton")
    assert na_tela["travou"] == []
    # uma por clique 2 do roteiro: a recusa (`nao_fechou`) e o recibo (`jogo_aberto`)
    assert len(na_tela["fechou"]) == 2, (
        f"a janela da Steam foi pedida {len(na_tela['fechou'])} vez(es) — o "
        "clique 1 do «Aplicar aos jogos» não pode fechar a Steam")


def test_na_tela_o_jogo_aberto_nao_falha_e_o_painel_diz_o_que_o_gesto_fez(
        na_tela: dict) -> None:
    """O-APLICAR-SOLUCOES-COM-JOGO-ABERTO-DIZ-O-QUE-FEZ-01, no WebKit de verdade."""
    marco = "recibo:aplicar-aos-jogos"
    assert na_tela.get(f"{marco}:clique") == "cliquei", na_tela.get(f"{marco}:clique")
    desfecho = _marco(na_tela, f"{marco}:desfecho")
    assert desfecho and desfecho[0] == "aplicou", desfecho
    classes = str(_marco(na_tela, marco)["pouso"]["classes"]).split()
    assert "hef-recusou" not in classes, classes
    painel = _marco(na_tela, f"{marco}:painel")["painel"]
    assert painel.endswith("A Steam fica para quando o jogo fechar."), painel
    assert "O ambiente do Hefesto está em:" in painel or "Nenhum outro lançador" in painel
    falhas = [linha for linha in str(na_tela["diario"]).splitlines()
              if linha.startswith(f"[gesto falhou] {PAGINA} · aplicar-aos-jogos")]
    assert len(falhas) == 1, f"só a recusa `nao_fechou` falha, e falhou {falhas}"


@pytest.mark.parametrize("marco", [f"arma:{g}" for g in ARMAM]
                         + ["rearma:aplicar-aos-jogos"])
def test_na_tela_o_clique_que_arma_nao_pisca_e_pergunta(na_tela: dict, marco: str) -> None:
    """O estudo mediu o Parar e o Restaurar piscando verde sem uma palavra."""
    gesto_ = marco.split(":", 1)[1]
    assert na_tela.get(f"{marco}:clique") == "cliquei", na_tela.get(f"{marco}:clique")
    assert _marco(na_tela, f"{marco}:desfecho") == ["aplicou", ""]
    armou = _marco(na_tela, marco)
    assert _acesas(armou["trilha"]) == [], (
        f"o clique que só armou o `{gesto_}` piscou: {_acesas(armou['trilha'])}")

    painel = str(_marco(na_tela, f"{marco}:painel")["painel"])
    assert na_tela["clique_de_novo"] in painel, painel
    if gesto_ in PERGUNTA_E_O_TITLE:
        assert _sem_quebra(_title_publicado(gesto_)) in _sem_quebra(painel), painel


def test_na_tela_a_pergunta_vencida_sai_no_tique(na_tela: dict) -> None:
    """O painel volta ao repouso junto com o rótulo — sem clique nenhum."""
    lido = _marco(na_tela, "vence:aplicar-aos-jogos")
    assert lido["painel"] == REPOUSO


def test_a_largura_da_pergunta_e_a_do_painel(a09) -> None:
    """A pergunta usa a largura medida do painel, e nenhuma palavra muda."""
    dica = _title_publicado(a09.DESLIGAR)
    pergunta = a09._pergunta_do_botao(a09.DESLIGAR)
    assert pergunta.split("\n\n")[0] == textwrap.fill(dica, a09.LARGURA_DA_PERGUNTA)
