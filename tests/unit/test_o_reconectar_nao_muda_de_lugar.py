#!/usr/bin/env python3
"""O «Reconectar controles» fica onde está — JOGAR-A-FAIXA-QUE-PULA-01.

NOTA DATADA, 28/10/2026 (A-JOGAR-SE-PUBLICA-COM-OS-CONTROLES-E-A-02-SAI-01): o botão mora no
canto do quadro Status, a faixa final, a frase da mesa, a ressalva da máscara e os chips de
máscara do cartão saíram da Jogar. As cenas que mexiam neles saíram; as que sobram medem o botão
no canto, com os lugares da seção Controles apagados e com o piloto de verdade. O vizinho de
texto longo modelava o recibo pousando na faixa; sem faixa, quem o barra é a primeira régua.
"""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

from tests.conftest import skip_sem_gi_real

CHROME = pathlib.Path("/usr/bin/google-chrome")

LARGURAS = (1228, 1300)

TRES_FRASES = " ".join((painel.recado_do_radio(1, 1), painel._NAO_CONFERIU))

VIVO_DUALSENSE: dict[str, Any] = {
    "connected": True, "native_mode": False, "paused": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense", "backend": "uhid"},
}
VIVO_XBOX: dict[str, Any] = {
    "connected": True, "native_mode": False, "paused": False,
    "gamepad_emulation": {"enabled": True, "flavor": "xbox", "backend": "uinput",
                          "caminho": "xbox"},
}
VIVO_NATIVO: dict[str, Any] = {
    "connected": True, "native_mode": True, "paused": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
}
VIVO_NAVEGACAO: dict[str, Any] = {
    "connected": True, "native_mode": False, "paused": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
}


class PonteDeMentira:
    """Aceita qualquer método e guarda o que foi pedido. Não abre socket."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def chamar(self, metodo: str, **params: Any) -> bool:
        self.chamadas.append((metodo, params))
        return True


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A escolha e o último relato são de MÓDULO — sem isto um teste suja o outro."""
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()
    monkeypatch.setattr(aba, "_PENDENCIA_RELATADA", "")
    yield
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()


def _ctx(state: dict[str, Any]) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicado"])
def test_a_faixa_final_nao_declara_lugar_de_recado(publicado: bool) -> None:
    """O nó que empurrava o botão, nos DOIS lados."""
    corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(encoding="utf-8")
    assert "data-hef-recados=" not in corpo, (
        "a 01 voltou a declarar um lugar de recado: o recibo volta a entrar na "
        "fileira do Reconectar e a empurrá-lo")
    assert 'class="recibo-do-reconectar"' not in corpo


ONDE_O_BOTAO_ESTA = """
  const b = document.querySelector('[data-gesto="reconectar"]');
  const f = b && b.parentElement;
  if (!f || !b) return {erro: 'sem o botão'};
  const cf = getComputedStyle(f);
  const rf = f.getBoundingClientRect(), rb = b.getBoundingClientRect();
  const borda = rf.right - parseFloat(cf.paddingRight) - parseFloat(cf.borderRightWidth);
  const tops = new Set();
  for (const no of b.childNodes) {
    if (no.nodeType !== 3 || !no.textContent.trim()) continue;
    const rg = document.createRange();
    rg.selectNodeContents(no);
    for (const r of rg.getClientRects()) tops.add(Math.round(r.top));
  }
"""

MEDIR = "() => {" + ONDE_O_BOTAO_ESTA + """
  return {x: rb.left, y: rb.top, direita: borda - rb.right, linhas: tops.size};
}"""

CENAS: tuple[tuple[str, str], ...] = (
    ("a página como nasce", "(a) => 0"),
    ("o piloto pousa o recibo de sucesso",
     "(a) => { const f = document.querySelector('[data-hef-recados~=\"sucesso\"]');"
     " if (!f) return 0; const el = document.createElement('div');"
     " el.className = 'hef-recado ' + (f.dataset.hefRecadoClasse || '');"
     " el.style.cssText = 'pointer-events:none;'; el.textContent = a.longa;"
     " f.appendChild(el); return 1; }"),
    ("o botão voa e pousa verde",
     "(a) => { const b = document.querySelector('[data-gesto=\"reconectar\"]');"
     " b.classList.add('hef-em-voo'); b.classList.add('hef-deu-certo'); return 0; }"),
)


@pytest.mark.parametrize("largura", LARGURAS)
def test_o_botao_nao_muda_de_lugar_em_cena_nenhuma(largura: int) -> None:
    """Uma linha, no canto do Status, e x e y iguais (±1 px) nas três cenas."""
    if not CHROME.exists():
        pytest.skip("sem /usr/bin/google-chrome: o layout não se mede sem motor")
    sync_api = pytest.importorskip("playwright.sync_api")
    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA

    argumento = {"longa": TRES_FRASES}
    pagina = onde.pagina("01-jogar.html", publicado=True).as_uri()

    medidas: list[tuple[str, dict[str, Any]]] = []
    with sync_api.sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            for nome, cena in CENAS:
                pg = nav.new_page(viewport={"width": largura, "height": 900},
                                  device_scale_factor=1)
                try:
                    pg.goto(pagina)
                    pg.wait_for_load_state("networkidle")
                    pg.add_style_tag(content=FOLHA_DA_CASA)
                    pg.evaluate(cena, argumento)
                    pg.wait_for_timeout(50)
                    m = pg.evaluate(MEDIR)
                finally:
                    pg.close()
                assert "erro" not in m, f"{largura}px · {nome}: {m.get('erro')}"
                medidas.append((nome, m))
        finally:
            nav.close()

    _, base = medidas[0]
    for nome, m in medidas:
        onde_ = f"{largura}px · {nome}"
        assert m["linhas"] == 1, f"{onde_}: o botão quebrou em {m['linhas']} linhas"
        assert abs(m["direita"] - base["direita"]) <= 1, (
            f"{onde_}: o botão descolou do canto — {base['direita']:.1f} px → "
            f"{m['direita']:.1f} px até a borda do quadro")
        assert abs(m["x"] - base["x"]) <= 1 and abs(m["y"] - base["y"]) <= 1, (
            f"{onde_}: o botão mudou de lugar — x {base['x']:.1f} → {m['x']:.1f}, "
            f"y {base['y']:.1f} → {m['y']:.1f}")


LUGAR_VAZIO = "nao"  # (noqa-acento)

APAGAR_OS_QUATRO = ("for (const el of document.querySelectorAll('[data-controle]'))"
                    " { el.dataset.conectado = a.vazio; el.classList.add('off'); }")
CENAS_DO_ESTADO: tuple[tuple[str, str], ...] = (
    ("o serviço não respondeu: os quatro lugares apagam",
     "(a) => { " + APAGAR_OS_QUATRO + " return 0; }"),
)

TOLERANCIA_DO_ESTADO = 2

MEDIR_O_ESTADO = MEDIR

def _medir_no_chrome(largura: int, cenas: tuple[tuple[str, str], ...],
                     argumento: dict[str, Any], medir: str) -> list[tuple[str, Any]]:
    """Uma página publicada por cena, com a folha do piloto por cima, e a medida."""
    if not CHROME.exists():
        pytest.skip("sem /usr/bin/google-chrome: o layout não se mede sem motor")
    sync_api = pytest.importorskip("playwright.sync_api")
    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA

    pagina = onde.pagina("01-jogar.html", publicado=True).as_uri()
    medidas: list[tuple[str, Any]] = []
    with sync_api.sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            for nome, cena in cenas:
                pg = nav.new_page(viewport={"width": largura, "height": 900},
                                  device_scale_factor=1)
                try:
                    pg.goto(pagina)
                    pg.wait_for_load_state("networkidle")
                    pg.add_style_tag(content=FOLHA_DA_CASA)
                    pg.evaluate(cena, argumento)
                    pg.wait_for_timeout(50)
                    medidas.append((nome, pg.evaluate(medir, argumento)))
                finally:
                    pg.close()
        finally:
            nav.close()
    return medidas


@pytest.mark.parametrize("largura", LARGURAS)
def test_o_botao_nao_muda_de_lugar_quando_o_estado_apaga_os_lugares(largura: int) -> None:
    """A cena do estado contra a página como nasce."""
    medidas = _medir_no_chrome(
        largura, (("a página como nasce", "(a) => 0"), *CENAS_DO_ESTADO),
        {"vazio": LUGAR_VAZIO}, MEDIR_O_ESTADO)
    _, base = medidas[0]
    assert "erro" not in base, f"{largura}px: {base.get('erro')}"
    for nome, m in medidas[1:]:
        onde_ = f"{largura}px · {nome}"
        assert "erro" not in m, f"{onde_}: {m.get('erro')}"
        assert m["linhas"] == 1, f"{onde_}: o botão quebrou em {m['linhas']} linhas"
        assert abs(m["direita"] - base["direita"]) <= 1, (
            f"{onde_}: o botão descolou do canto — {base['direita']:.1f} px → "
            f"{m['direita']:.1f} px")
        dy = m["y"] - base["y"]
        assert abs(m["x"] - base["x"]) <= 1 and abs(dy) <= TOLERANCIA_DO_ESTADO, (
            f"{onde_}: o botão {'subiu' if dy < 0 else 'desceu'} {abs(dy):.0f} px — "
            f"y {base['y']:.1f} → {m['y']:.1f}, x {base['x']:.1f} → {m['x']:.1f}")



@pytest.mark.parametrize("estado", [VIVO_NATIVO, VIVO_NAVEGACAO, VIVO_DUALSENSE, {}],
                         ids=["nativo", "navegacao", "jogo", "sem-daemon"])
def test_a_ressalva_da_mascara_nao_chega_a_tela(estado: dict[str, Any]) -> None:
    """§3.1: em modo nenhum — e era no Nativo e na Navegação que ela era pintada."""
    assert "mascara-ressalva" not in aba.pacote(_ctx(estado))


def test_a_pendencia_nao_acende_a_faixa_e_vai_ao_diario(
        capsys: pytest.CaptureFixture[str]) -> None:
    """§3.2: o daemon ainda não alcançou o Xbox — a dona sabe, a tela não fala."""
    aba.modo_xbox(_ctx(VIVO_DUALSENSE), {"texto": "Xbox"}, PonteDeMentira())
    capsys.readouterr()

    fora = aba.pacote(_ctx(VIVO_DUALSENSE))
    for campo in ("pendente", "pendente-alvo", "pendente-ha"):
        assert campo not in fora, f"a faixa voltou a falar: {campo}={fora[campo]!r}"
    assert aba._faixa_do_pendente(VIVO_DUALSENSE)[1] == "Xbox", (
        "a dona da pendência parou de medir — o diário ficaria mudo junto")

    primeira = capsys.readouterr().err
    assert primeira.count("[relato] 01-jogar.html · pendente:") == 1
    assert "Xbox" in primeira
    aba.pacote(_ctx(VIVO_DUALSENSE))
    assert "[relato]" not in capsys.readouterr().err, (
        "o diário repetiu a mesma pendência no tique seguinte")


def test_o_chip_xbox_pede_com_origem_manual() -> None:
    """§3.2, primeiro elo: sem `manual` o daemon leria reconciliação e poderia recusar."""
    plano = aba._plano_do_chip("xbox")
    pedidos = [p for m, p in plano if m == "gamepad.emulation.set"]
    assert pedidos == [{"enabled": True, "origin": "manual", "caminho": "xbox"}], plano


def test_a_trava_do_jogo_aberto_nao_segura_o_gesto_dela() -> None:
    """§3.2, segundo elo: com o jogo na autoridade, só a AUTOMAÇÃO é segurada."""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    com_jogo = SimpleNamespace(display_authority="game", store=None)
    motivo = "troca_de_mascara:dualsense->xbox"
    assert gamepad._recriacao_bloqueada_por_jogo(
        com_jogo, origin="manual", motivo=motivo) is False
    assert gamepad._recriacao_bloqueada_por_jogo(
        com_jogo, origin="profile", motivo=motivo) is True


def test_o_chip_acende_o_flavor_que_o_daemon_grava() -> None:
    """§3.2, terceiro elo: o chip lê o que o daemon publica, e a pendência some quando chega."""
    assert aba._estado_da_tela(VIVO_DUALSENSE)["modo-aceso"] == "dualsense"
    assert aba._estado_da_tela(VIVO_XBOX)["modo-aceso"] == "xbox"
    aba.modo_xbox(_ctx(VIVO_DUALSENSE), {"texto": "Xbox"}, PonteDeMentira())
    assert aba._faixa_do_pendente(VIVO_XBOX) == ("", "")


UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"


def _controle(uniq: str, transporte: str, jogador: int) -> dict[str, Any]:
    return {"uniq": uniq, "connected": True, "transport": transporte,
            "player": jogador, "battery": 64, "audio": {"mic_mudo": False}}


ESTADO_COM_DOIS: dict[str, Any] = {
    **VIVO_DUALSENSE, "active_profile": "regua",
    "controllers": [_controle(UNIQ_P1, "usb", 1), _controle(UNIQ_P2, "bt", 2)],
}


def _mudo_por(causa: BaseException) -> Exception:
    """O `DaemonMudo` na forma exata em que `mesa_viva.estado_do_daemon` o levanta."""
    import hefesto_vivo as hv

    try:
        try:
            raise causa
        except BaseException as erro:
            raise hv.mesa_viva.DaemonMudo(str(erro)) from erro
    except hv.mesa_viva.DaemonMudo as mudo:
        return mudo


@skip_sem_gi_real
def test_a_folga_repinta_o_ultimo_estado_bom_e_depois_diz_a_verdade() -> None:
    """Os mudos da folga devolvem o último bom; o seguinte, `{}`, e ele não volta."""
    import hefesto_vivo as hv

    folga = hv.FolgaDoServicoMudo()
    assert folga.folga == hv.MUDOS_SEGUIDOS_QUE_VOLTARAM >= 1
    folga.respondeu(ESTADO_COM_DOIS)
    for vez in range(1, folga.folga + 1):
        assert folga.mudo(_mudo_por(TimeoutError("timed out"))) is ESTADO_COM_DOIS, (
            f"o {vez}º tique mudo seguido já apagou os lugares — a folga não segurou")
    assert folga.mudo(_mudo_por(TimeoutError("timed out"))) == {}, (
        "passou da folga e a tela continuou afirmando os controles de antes")
    assert folga.mudo(_mudo_por(TimeoutError("timed out"))) == {}, (
        "a tela já tinha dito que o serviço calou, e o estado velho voltou")
    folga.respondeu(ESTADO_COM_DOIS)
    assert folga.mudo(TimeoutError("timed out")) is ESTADO_COM_DOIS, (
        "o `TimeoutError` direto, que é como um dublê o levanta, ficou sem folga")


@skip_sem_gi_real
@pytest.mark.parametrize("causa", [
    FileNotFoundError(2, "Arquivo ou diretório inexistente"),
    ConnectionResetError(104, "Conexão fechada pela outra ponta"),
    ConnectionRefusedError(111, "Conexão recusada"),
], ids=["sem-socket", "fechada", "recusada"])
def test_o_servico_fora_do_ar_nao_tem_folga(causa: OSError) -> None:
    """Fora do ar não é demora: a verdade se pinta no primeiro tique."""
    import hefesto_vivo as hv

    folga = hv.FolgaDoServicoMudo()
    folga.respondeu(ESTADO_COM_DOIS)
    assert folga.mudo(_mudo_por(causa)) == {}, (
        f"{type(causa).__name__} ganhou folga — o serviço fora do ar ficaria "
        f"escondido atrás dos controles de antes")


@skip_sem_gi_real
def test_sem_resposta_boa_nao_ha_o_que_repintar() -> None:
    """A janela que abre com o serviço mudo pinta a verdade desde o começo."""
    import hefesto_vivo as hv

    assert hv.FolgaDoServicoMudo().mudo(_mudo_por(TimeoutError("timed out"))) == {}


def _vazia_pintada(a: dict[str, Any]) -> bool:
    """A amostra da lista vazia do segundo tique em diante, quando o primeiro já pintou."""
    return a.get("vazios", 0) >= 2 and a.get("p1") == LUGAR_VAZIO


LER_A_FILEIRA = r"""(() => {
  const b = document.querySelector('[data-gesto="reconectar"]');
  const p1 = document.querySelector('[data-controle="p1"]');
  if (!b || !p1) return JSON.stringify({erro: 'sem o botão ou o P1'});
  return JSON.stringify({y: b.getBoundingClientRect().top, p1: p1.dataset.conectado || ''});
})()"""


@pytest.fixture(scope="module")
def tique_mudo() -> dict[str, Any]:
    """O piloto de verdade, oculto, na página publicada: bom → mudo → lista vazia."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import json
    import time

    import hefesto_vivo as hv

    fase: dict[str, Any] = {"como": "bom", "mudos": 0, "vazios": 0}

    def estado(*_a: Any, **_k: Any) -> dict[str, Any]:
        if fase["como"] == "mudo":
            fase["mudos"] += 1
            try:
                raise TimeoutError("timed out")
            except TimeoutError as causa:
                raise hv.mesa_viva.DaemonMudo("timed out") from causa
        if fase["como"] == "vazia":
            fase["vazios"] += 1
            return {**ESTADO_COM_DOIS, "controllers": []}
        return ESTADO_COM_DOIS

    def sem_daemon(metodo: str, *_a: Any, **_k: Any) -> Any:
        raise RuntimeError(f"régua: sem daemon para {metodo}")

    folga = int(hv.MUDOS_SEGUIDOS_QUE_VOLTARAM)
    fora: dict[str, Any] = {"amostras": [], "folga": folga}
    guardado = (hv.mesa_viva.estado_do_daemon, hv.ponte.resultado)
    hv.mesa_viva.estado_do_daemon = estado  # type: ignore[assignment]
    hv.ponte.resultado = sem_daemon  # type: ignore[assignment]
    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre="", prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False, conta_mutacoes=0,
    )
    piloto = hv.Piloto(args)

    def de_pe() -> bool:
        return bool(piloto.pronto and piloto.tela.na_aba
                    and piloto.pagina == "01-jogar.html")

    def amostrar() -> bool:
        if fora.get("parar"):
            return False
        if not de_pe():
            return True
        como, mudos, vazios = fase["como"], fase["mudos"], fase["vazios"]

        def leu(valor: Any, erro: Any) -> None:
            if erro is not None:
                fora["amostras"].append({"erro": str(erro), "fase": como})
                return
            lido = json.loads(str(valor))
            lido.update(fase=como, mudos=mudos, vazios=vazios)
            fora["amostras"].append(lido)

        piloto.ponte.perguntar(LER_A_FILEIRA, leu)
        return True

    def roteiro() -> bool:
        if fora.get("parar"):
            return False
        amostras = fora["amostras"]
        if fase["como"] == "bom":
            if sum(1 for a in amostras if a.get("p1") == "sim") >= 5:
                fase["como"] = "mudo"
        elif fase["como"] == "mudo":
            if fase["mudos"] >= folga + 6:
                fase["como"] = "vazia"
        elif sum(1 for a in amostras if _vazia_pintada(a)) >= 5:
            fora["completou"] = True
            fora["parar"] = True
            Gtk.main_quit()
            return False
        return True

    GLib.timeout_add(40, amostrar)
    GLib.timeout_add(50, roteiro)
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        limite = time.monotonic() + 60.0
        while not fora.get("completou") and time.monotonic() < limite:
            Gtk.main()
    finally:
        fora["parar"] = True
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.mesa_viva.estado_do_daemon,
         hv.ponte.resultado) = guardado  # type: ignore[assignment]
    assert fora.get("completou"), (
        f"o roteiro não chegou ao fim (fase {fase['como']}, {fase['mudos']} mudos, "
        f"{len(fora['amostras'])} amostras) — a régua mediria pela metade")
    erros = [a for a in fora["amostras"] if "erro" in a]
    assert not erros, f"a leitura da fileira falhou: {erros[:3]}"
    return fora


def test_no_webkit_o_tique_mudo_repinta_o_ultimo_estado_bom(tique_mudo: dict[str, Any]) -> None:
    """Dentro da folga os lugares continuam cheios — no motor dela."""
    folga = tique_mudo["folga"]
    dentro = [a for a in tique_mudo["amostras"]
              if a["fase"] == "mudo" and 1 <= a["mudos"] <= folga]
    assert dentro, "nenhuma amostra caiu dentro da folga — a régua não mediu o que promete"
    apagou = [a for a in dentro if a["p1"] != "sim"]
    assert not apagou, (
        f"o serviço demorou {apagou[0]['mudos']} tique(s) e os lugares já apagaram "
        f"— a folga de {folga} não segurou: {apagou[:3]}")


def test_no_webkit_depois_da_folga_a_tela_diz_que_o_servico_calou(
        tique_mudo: dict[str, Any]) -> None:
    """E a folga ACABA: passado o último mudo que ela segura, o P1 apaga."""
    folga = tique_mudo["folga"]
    depois = [a for a in tique_mudo["amostras"]
              if a["fase"] == "mudo" and a["mudos"] >= folga + 2]
    assert depois, "nenhuma amostra depois da folga — a régua não viu a verdade chegar"
    assert any(a["p1"] == LUGAR_VAZIO for a in depois), (
        "passou da folga e a tela continuou afirmando o P1 — estado velho pintado "
        "como se fosse de agora")


def test_no_webkit_o_botao_nao_anda_com_os_lugares_apagados(
        tique_mudo: dict[str, Any]) -> None:
    """O y do botão no repouso, com os lugares apagados e com a lista vazia.

    Com o serviço calado só o Status diz Desligado (D-2010-O-SERVICO-PARADO-NAO-GANHA-FRASE).
    """
    amostras = tique_mudo["amostras"]
    repouso = [a["y"] for a in amostras if a["fase"] == "bom" and a["p1"] == "sim"]
    apagados = [a for a in amostras if a["p1"] == LUGAR_VAZIO and a["fase"] == "mudo"]
    vazia = [a for a in amostras if _vazia_pintada(a)]
    assert repouso and apagados and vazia, (
        "a régua não viu o repouso, os lugares apagados ou a lista vazia — "
        "ficaria verde sobre nada")
    base = repouso[-1]
    for rotulo, grupo in (("com os lugares apagados", apagados),
                          ("com a lista vazia", vazia)):
        pior = max(grupo, key=lambda a: abs(a["y"] - base))
        dy = pior["y"] - base
        assert abs(dy) <= TOLERANCIA_DO_ESTADO, (
            f"no WebKit, {rotulo}, o botão {'subiu' if dy < 0 else 'desceu'} "
            f"{abs(dy):.0f} px — y {base:.1f} → {pior['y']:.1f}")
