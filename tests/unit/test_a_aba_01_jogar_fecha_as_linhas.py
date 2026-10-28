#!/usr/bin/env python3
"""As duas decisões da aba Jogar que a ONDA2-01 fecha, e a que ela NÃO fecha.

NOTA DATADA, 28/10/2026: o esmaecido do «Player N» do cartão saiu com o cartão
(A-JOGAR-SE-PUBLICA-COM-OS-CONTROLES-E-A-02-SAI-01); a seção Controles escreve o número sem ele.
"""
from __future__ import annotations

import pathlib
import shutil
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.interface import onde
from pacotes import TRAVESSAO, Contexto
from pacotes import a01_jogar as aba

VIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
}

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


def _pagina() -> str:
    """O HTML publicado: os cartões saíram do desenho e ficam no produto até o --publicar."""
    return onde.pagina("01-jogar.html", publicado=True).read_text()


def _ctx(controles: list[dict[str, Any]], **estado: Any) -> Contexto:
    return Contexto(state={**VIVO, **estado, "controllers": controles},
                    mesa=[], conectados=controles, estados={})


def test_o_cadeado_diz_o_que_o_daemon_guardou() -> None:
    """A trava mostra o estado do daemon, não o último clique."""
    assert aba._cadeado({**VIVO, "freestyle_ligado": True}) == aba.CADEADO_LIGADO
    assert (aba._cadeado({**VIVO, "freestyle_ligado": False})
            == aba.CADEADO_DESLIGADO)
    assert aba.CADEADO_LIGADO != aba.CADEADO_DESLIGADO, (
        "as duas palavras do interruptor ficaram iguais — a pílula não teria "
        "como dizer travado de destravado")


def test_sem_daemon_a_caixa_nao_afirma_uma_escolha_dela() -> None:
    """Sem estado, a trava fica no TRAVESSÃO — nem acesa, nem apagada."""
    assert aba._cadeado({}) == TRAVESSAO
    assert aba._cadeado({**VIVO}) == TRAVESSAO, "daemon sem a chave acendeu a trava"
    assert aba._cadeado({**VIVO, "freestyle_ligado": "sim"}) == TRAVESSAO, (
        "uma string ligou o cadeado — só o `True` literal pode")
    assert TRAVESSAO not in (aba.CADEADO_LIGADO, aba.CADEADO_DESLIGADO), (
        "o travessão virou uma das duas palavras do interruptor — o 'não sei' "
        "passaria a acender ou a apagar a pílula, que é a afirmação que ele "
        "existe para não fazer")


_ECOA = object()


class _PonteDeMentira:
    """Guarda o que foi chamado — e responde ao cadeado como o serviço responde."""

    def __init__(self, cadeado: Any = _ECOA) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []
        self.cadeado = cadeado

    def freestyle_set(self, ligado: Any = None) -> Any:
        self.chamadas.append(("freestyle_set", (), {"ligado": ligado}))
        if isinstance(self.cadeado, BaseException):
            raise self.cadeado
        return bool(ligado) if self.cadeado is _ECOA else self.cadeado

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True
        return registrar


def test_o_cadeado_manda_o_valor_absoluto_e_nunca_um_toggle() -> None:
    """O clique manda a escolha do usuário, não um "inverta o que você tiver"."""
    for guardado, pedido in ((False, True), (True, False)):
        p = _PonteDeMentira()
        aba.cadeado(_ctx([], freestyle_ligado=guardado),
                    {"evento": "click"}, p)
        assert p.chamadas, "o cadeado não chamou NADA"
        nome, _, kwargs = p.chamadas[0]
        assert nome == "freestyle_set", (
            f"o cadeado chamou {nome!r} — o escritor é o da janela antiga")
        assert kwargs.get("ligado") is pedido, (
            f"com o cadeado guardado em {guardado} o clique pediu "
            f"{kwargs.get('ligado')!r}, esperava {pedido!r}. `None` é TOGGLE, e "
            f"dois toggles num clique são um no-op")


def test_um_clique_grava_uma_vez_so_no_disco_dela() -> None:
    """O ouvinte do piloto está em dois eventos; só um pode virar escrita."""
    p = _PonteDeMentira()
    ctx = _ctx([], freestyle_ligado=False)
    aba.cadeado(ctx, {"evento": "change"}, p)
    assert p.chamadas == [], (
        "o `change` gravou: um gesto na trava grava DUAS vezes no disco dela se "
        "a caixa voltar, e o filtro é a única coisa entre ela e as duas")

    aba.cadeado(ctx, {"evento": "click"}, p)
    assert len(p.chamadas) == 1, (
        "o `click` NÃO gravou — e é o único evento que um `<button>` emite. O "
        "filtro ficou no `change`, e a trava virou enfeite")

    aba.cadeado(ctx, {}, p)
    assert len(p.chamadas) == 2, (
        "um clique sem `evento` foi engolido — o padrão tem de ser `click`")


def test_o_cadeado_confirma_em_verde() -> None:
    """O gesto PEDE o verde voltando calado — e só quando o serviço confirmou."""
    p = _PonteDeMentira()
    assert aba.cadeado(_ctx([], freestyle_ligado=False),
                       {"evento": "click"}, p) is None
    assert p.chamadas, "o cadeado não chamou NADA"

    p = _PonteDeMentira(cadeado=None)
    with pytest.raises(RuntimeError) as caiu:
        aba.cadeado(_ctx([], freestyle_ligado=False), {"evento": "click"}, p)
    assert str(caiu.value) == aba.CADEADO_RECUSA, (
        f"a recusa disse {str(caiu.value)!r} — a frase é a da janela antiga, e "
        f"texto de tela novo é palavra dela")
    assert p.chamadas, "o gesto recusou sem sequer tentar escrever"

    p = _PonteDeMentira(cadeado=RuntimeError("o socket recusou"))
    with pytest.raises(RuntimeError):
        aba.cadeado(_ctx([], freestyle_ligado=True), {"evento": "click"}, p)


def test_o_cadeado_esta_na_pagina_com_os_dois_lados() -> None:
    """Endereço de pintura E endereço de clique — um sem o outro é meio botão."""
    doc = _pagina()

    assert doc.count('data-campo="cadeado" data-hef-alvo="classe"') == 1
    assert doc.count('data-hef-classe="ligada" '
                     f'data-hef-quando="{aba.CADEADO_LIGADO}"') == 1, (
        "a pílula da trava perdeu a classe ou a palavra que a acende. Sem a "
        "classe o piloto acende `on`, que folha nenhuma pinta; sem o `quando` o "
        "alvo `classe` vira BOOLEANO e a trava acende também no DESLIGADO e no "
        "travessão")
    assert doc.count('data-gesto="cadeado"') == 1
    assert aba.CADEADO_ROTULO in doc, "o rótulo do cadeado não está na tela"
    assert aba.CADEADO_DICA in doc, "o cadeado está sem a razão na dica"


def test_o_cadeado_esta_publicado() -> None:
    """A caixa está na página que o PRODUTO abre — medido no arquivo, não na prosa."""
    import inspect

    alvo = onde.pagina("01-jogar.html", publicado=True)
    assert alvo.exists(), f"a página que o produto abre não existe: {alvo}"
    linhas = alvo.read_text().splitlines()
    onde_esta = [n for n, linha in enumerate(linhas, 1)
                 if 'data-gesto="cadeado"' in linha]
    assert len(onde_esta) == 1, (
        f"a caixa do cadeado aparece {len(onde_esta)} vez(es) na página "
        f"publicada ({alvo}). Zero quer dizer que ela NÃO está no que o produto "
        f"renderiza — e aí o gesto está ligado a um botão que ela não tem como "
        f"clicar; mais de uma, que o clique tem dois endereços iguais")

    fonte = inspect.getsource(aba.cadeado).lower()
    assert "mockup" not in fonte, (
        f"o fonte do gesto `cadeado` ainda manda quem lê procurar a caixa na "
        f"bancada — e ela está PUBLICADA, em {alvo}:{onde_esta[0]}, que é o "
        f"arquivo que o piloto abre. Fato errado se SUBSTITUI: o que fica "
        f"escrito é a razão de o `--prova-gesto` não clicar esta caixa, que é "
        f"`PERIGOSOS` (o gesto grava preferência dela no disco)")


@pytest.mark.skipif(not pathlib.Path("/usr/bin/google-chrome").exists()
                    or shutil.which("python3") is None,
                    reason="sem o Chrome do sistema não há tela a ler")
def test_o_cadeado_continua_na_tela_com_o_hefesto_desligado() -> None:
    """A régua que LÊ A TELA, e é a única que pega este defeito.

    O quadro **Modo** tem duas seções que se trocam com o interruptor
    (`.so-ligado` e `.so-desligado`), e a troca automática de PERFIL vale nas
    duas. Uma trava aninhada dentro de uma delas sumiria na outra posição — e
    sumiria em SILÊNCIO: nenhuma contagem de `data-campo` vê isso, porque o
    endereço continua no arquivo.

    **É a diferença entre a ordem no arquivo e o aninhamento no DOM**, e só o
    navegador responde por ela: a régua pergunta ao `getComputedStyle` nas DUAS
    posições do interruptor.

    **O SELETOR PERDEU A TAG EM 19/09** (`TRAVA-PILULA-01`): ele dizia
    `label.cadeado`, e a trava virou `<button class="cadeado">`. Um seletor com
    a tag velha casa ZERO elemento, e a régua passou a reprovar pela guarda de
    vácuo logo abaixo — que é exatamente o que ela existe para fazer. A classe
    é o endereço; a tag, não.

    A MORDIDA: mova o `<button class="cadeado">` para dentro do
    `<div class="hef-modo so-ligado">`, gere de novo e esta régua reprova na
    posição Desligado.
    """
    playwright = pytest.importorskip("playwright.sync_api")

    alvo = onde.pagina("01-jogar.html", publicado=True)
    with playwright.sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                               args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(f"file://{alvo}")
        pg.wait_for_load_state("load")
        medido = pg.evaluate("""(() => {
          const ler = () => {
            const c = document.querySelector('.cadeado');
            const l = document.querySelector('.hef-modo.so-ligado');
            const d = document.querySelector('.hef-modo.so-desligado');
            if(!c || !l || !d) return null;
            const vis = (el) => getComputedStyle(el).display !== 'none'
                                && el.getBoundingClientRect().height > 0;
            return {cadeado: vis(c), ligado: vis(l), desligado: vis(d)};
          };
          const fora = {ligado: ler()};
          document.getElementById('hef-desligado').checked = true;
          fora.desligado = ler();
          return fora;
        })()""")
        b.close()

    assert medido["ligado"] and medido["desligado"], (
        "a régua não achou o cadeado nem as duas seções — seletor que casa ZERO "
        "elemento é ERRO, nunca medida")
    assert medido["ligado"]["ligado"] and not medido["ligado"]["desligado"], (
        "o interruptor não trocou as seções — a régua está medindo o próprio "
        "instrumento")
    assert medido["desligado"]["desligado"] and not medido["desligado"]["ligado"]

    assert medido["ligado"]["cadeado"], "o cadeado sumiu com o Hefesto LIGADO"
    assert medido["desligado"]["cadeado"], (
        "o cadeado sumiu com o Hefesto DESLIGADO — ele foi aninhado dentro de "
        "uma seção do interruptor, e a troca automática de perfil vale nos dois")



def test_o_marcador_do_primario_anda_e_o_alvo_da_fita_nao() -> None:
    """Passo 3 — dois controles, um primário; troque e o marcador muda de cartão.

    Linha 18 do CSV: *"`is_primary` não é lido em `interface/pacotes/`; a classe
    `.cartao.alvo` existe mas responde a outra pergunta (o alvo de edição da
    fita)"*. A régua mede as DUAS metades: o marcador anda **e** o alvo não vai
    junto.

    **POR QUE O ALVO ENTRA NESTA RÉGUA:** se alguém reusar `.cartao.alvo` para o
    primário, o defeito só aparece no dia em que ela editar a fita com um
    controle que não é o primário — tarde, e na tela do usuário. Aqui aparece agora: o
    pacote não emite `alvo` nenhum, e quem o escreve é o piloto.

    A MORDIDA: troque `_e_o_primario` por `return "1"` e as duas primeiras
    afirmações reprovam (os dois cartões acendem); troque por `return ""` e a
    terceira reprova.
    """
    c1 = {"uniq": P1, "connected": True, "player_slot": 1, "player": 1,
          "is_primary": True, "transport": "usb"}
    c2 = {"uniq": P2, "connected": True, "player_slot": 2, "player": 2,
          "is_primary": False, "transport": "bt"}

    assert aba._e_o_primario(c1) == "1", "o primário não foi marcado"
    assert aba._e_o_primario(c2) == "", "um cartão que não é o primário acendeu"

    assert aba._e_o_primario({**c1, "is_primary": False}) == ""
    assert aba._e_o_primario({**c2, "is_primary": True}) == "1"

    fora = aba.pacote(_ctx([c1, c2]))
    for uniq, campos in (fora["cartoes"] or {}).items():
        assert "alvo" not in campos, (
            f"o cartão {uniq} passou a emitir `alvo` — o alvo de edição da fita "
            "é escolha dela, escrita pelo piloto, e não fato do serviço")


def test_so_o_true_literal_acende_o_marcador() -> None:
    """Chave ausente não é "não é o primário" — é *não sei*, e não se afirma."""
    assert aba._e_o_primario({}) == "", "sem a chave, o cartão afirmou"
    assert aba._e_o_primario({"is_primary": None}) == ""
    assert aba._e_o_primario({"is_primary": 1}) == "", "um `1` inteiro acendeu"
    assert aba._e_o_primario({"is_primary": "sim"}) == ""


def test_o_servico_calado_para_de_afirmar_e_nao_escreve() -> None:
    """Passo 5 — com o estado vazio nada é afirmado, e (20/10/2026) nada é escrito: só o Status."""
    ctx = Contexto(state={}, mesa=[], conectados=[], estados={})
    fora = aba.pacote(ctx)

    assert aba._avisos(ctx) == [] or all(
        a["selo"] != "SERVIÇO" for a in aba._avisos(ctx)), (
        "a coluna de avisos escreveu que o serviço parou")
    assert fora["hef-posicao"] == "desligado", (
        "o interruptor não disse Desligado com o serviço calado")
    assert fora["modo-aceso"] == "", "um chip da fileira acendeu sem estado"
    assert fora["cadeado"] == TRAVESSAO, "o cadeado afirmou uma escolha dela"
    assert "mesa-frase" not in fora, "a frase da mesa voltou com o cartão que saiu"
    assert not fora["cartoes"], "um cartão foi afirmado sem estado"


def test_com_o_servico_vivo_a_coluna_nao_traz_o_selo_do_servico() -> None:
    """O selo SERVIÇO saiu da escada junto com a frase."""
    c1 = {"uniq": P1, "connected": True, "player_slot": 1, "player": 1,
          "is_primary": True, "transport": "usb"}
    fora = aba._avisos(_ctx([c1]))
    assert "SERVIÇO" not in [a["selo"] for a in fora]
    assert "SERVIÇO" not in aba.ORDEM_DA_GRAVIDADE
    assert not hasattr(aba, "SELO_DO_SERVICO")


def test_nenhuma_das_frases_novas_fala_de_maquina() -> None:
    """As palavras proibidas do glossário não entram em texto de tela."""
    from hefesto_dualsense4unix.app.actions import home_actions

    de_maquina = ("uinput", "hidraw", "vpad", "evdev", "uniq")
    minhas = [aba.PRIMARIO_DICA,
              aba.MARCA_DO_PRIMARIO]
    da_ponte = [
        home_actions.texto_da_ponte(cena)
        for cena in (
            {"connected": True, "native_mode": False,
             "gamepad_emulation": {"enabled": False, "flavor": "dualsense"}},
            {"connected": True, "native_mode": False, "controllers": [],
             "gamepad_emulation": {"enabled": True, "flavor": "dualsense"}},
            {"connected": True, "native_mode": False,
             "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
             "controllers": [{"uniq": P1, "connected": True, "player_slot": 1}]},
            {"connected": True, "native_mode": True,
             "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
             "controllers": [{"uniq": P1, "connected": True, "player_slot": 1}]},
            None,
        )
    ]
    assert len(set(da_ponte)) == 5, (
        f"as cinco pontes deixaram de ser cinco frases distintas: {da_ponte!r}")

    for frase in minhas + da_ponte:
        baixa = f" {frase.lower()} "
        for palavra in de_maquina:
            assert palavra not in baixa, (
                f"a palavra {palavra!r} chegou a texto de tela: {frase!r}. O "
                f"glossário (`docs/A-LINGUA-DESTA-CASA`) a proíbe")

    for frase in minhas:
        assert " mesa " not in f" {frase.lower()} ", (
            f'a palavra "mesa" entrou numa frase desta aba: {frase!r}. Decisão '
            f"dela, 06/09: o termo sai da tela e entra o simples")


def _daemon_que_grava(ativo: str | None) -> Any:
    """O escritor REAL do daemon, sobre um objeto que só sabe o perfil ativo.

    `Daemon.gravar_o_modo_escolhido` lê do daemon só o `store.active_profile`;
    o resto (o perfil que recebe e a regra da seção) é do dono, em
    `profiles.manager`. Subir um `Daemon` inteiro aqui mediria o co-op e o
    vpad, e esta régua mede o CAMINHO da escolha até a outra tela.
    """
    from types import SimpleNamespace

    return SimpleNamespace(store=SimpleNamespace(active_profile=ativo))


def test_o_modo_clicado_entra_no_perfil_ativo(tmp_path, monkeypatch) -> None:
    """Passo 1 — o caminho clicado na 01 é o que a aba 10 lê. UM dono, duas telas.

    Linha 5 do CSV: *"nada. `_ESCOLHA`/`_ROTULO` são dicionários de módulo lidos
    só dentro do próprio arquivo"*, e a consequência: *"ela escolhe 'Xbox' na 01,
    clica em 'Salvar Perfil' na 10, e o perfil grava a máscara que estava no
    disco — a escolha do usuário não entra."*

    **QUEM GRAVA É O DAEMON** desde a O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01
    (29/09/2026): a janela gravava depois da resposta, e com quatro controles a
    troca passava do teto dela. As duas metades da estrada, medidas aqui:

    1. o chip «Xbox» pede o caminho à porta que grava — `gamepad.emulation.set`
       com `origin: "manual"`, que o handler traduz em `grava_o_modo="ipc"`;
    2. o escritor do daemon, `Daemon.gravar_o_modo_escolhido`, põe o caminho na
       seção `mode` do perfil ativo, e a aba 10 o LÊ por
       `perfis_web._pacote_do_editor`, que é o que o quadro «Modo» daquela aba
       mostrava. Ler o `.json` direto provaria só que alguém gravou um arquivo;
       ler por aqui prova que **a outra tela vê**.

    A MORDIDA: tire o `origin: "manual"` do passo `gamepad.emulation.set` do
    plano (`mode_transition.plan_mode_transition`) e a primeira metade
    reprova; faça o escritor do daemon gravar em outro perfil
    (`nome_do_perfil_que_grava(None)`) e a segunda reprova, com a aba 10 sem
    modo. A régua 1 de `test_o_modo_se_grava_onde_ele_muda.py` mede o setter
    chamando o escritor depois do aparelho.
    """
    from hefesto_dualsense4unix.app.actions import perfis_web
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    monkeypatch.setattr("hefesto_dualsense4unix.utils.xdg_paths.profiles_dir",
                        lambda: tmp_path)
    monkeypatch.setattr(loader, "_profiles_dir", lambda: tmp_path, raising=False)
    nome = "Régua do Modo"
    loader.save_profile(Profile(name=nome, match=MatchAny(), priority=40),
                        origem="régua")
    assert perfis_web._pacote_do_editor(loader.load_profile(nome))["modo"] == (
        perfis_web.MODO_SEM_OPINIAO), "o perfil da régua já nasceu com modo"

    passos = dict(aba._plano_do_chip("xbox"))
    pedido = passos.get("gamepad.emulation.set")
    assert pedido == {"enabled": True, "origin": "manual", "caminho": "xbox"}, (
        f"o chip «Xbox» não pede o caminho à porta que grava: {passos}")

    Daemon.gravar_o_modo_escolhido(
        _daemon_que_grava(nome), "gamepad", caminho="xbox", porta="ipc")

    lido = perfis_web._pacote_do_editor(loader.load_profile(nome))["modo"]
    assert lido == "gamepad", (
        f"a aba 10 continua vendo {lido!r} depois de o daemon gravar o «Xbox» — "
        f"a escolha dela não atravessou as duas telas")
    modo = loader.load_profile(nome).mode
    assert modo is not None and modo.caminho == "xbox", (
        f"o caminho não entrou na seção `mode`: {modo!r}")
    assert modo.gamepad_flavor == "xbox", (
        f"o caminho e a máscara não andaram em par (D-2710): {modo!r}")


def test_a_escrita_no_perfil_nunca_levanta(monkeypatch) -> None:
    """Ela vem DEPOIS de o aparelho trocar — e não pode falhar.

    Uma exceção aqui transformaria uma troca de modo bem-sucedida em recusa:
    o setter do daemon devolveria erro sobre um vpad que já trocou.

    A MORDIDA: tire o `try` de `Daemon.gravar_o_modo_escolhido` e esta régua
    reprova com o `OSError` do dublê.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles import manager

    def _explode(*_a: Any, **_kw: Any) -> Any:
        raise OSError("o disco recusou")

    monkeypatch.setattr(manager, "gravar_o_modo_no_perfil_ativo", _explode)
    assert Daemon.gravar_o_modo_escolhido(
        _daemon_que_grava("Qualquer"), "gamepad", caminho="xbox", porta="ipc"
    ) is None, (
        "a gravação levantou — o setter devolveria recusa sobre um modo que o "
        "aparelho já aplicou")


def test_sem_perfil_ativo_nao_se_inventa_um() -> None:
    """Sem perfil valendo, não há onde gravar — e não se escolhe um.

    Sem o nome no daemon e sem o perfil do boot no disco, o dono
    (`manager.nome_do_perfil_que_grava`) responde `None`, e nenhum `.json`
    muda nem nasce.

    O FREESTYLE ESTÁ NO DISCO DE PROPÓSITO: é o nome padrão que um escritor
    que «cai num nome» escolheria. A régua lê a pasta que o `loader` usa (a do
    lar de mentira do conftest), e não uma pasta que nenhum escritor alcança.
    Até 29/09 ela olhava um `tmp_path` que o `loader` nunca via (ele importa
    `profiles_dir` por nome, e o desvio no módulo de origem não o alcança), e
    passava com o escritor gravando no Freestyle.

    A MORDIDA: faça `Daemon.gravar_o_modo_escolhido` cair num nome padrão
    (`nome_do_perfil_que_grava(...) or "Freestyle"`) e esta régua reprova com
    o Freestyle regravado.
    """
    import hashlib

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.utils.session import resolve_boot_profile

    loader.save_profile(Profile(name=loader.NOME_DO_PADRAO, match=MatchAny()),
                        origem="régua")
    assert resolve_boot_profile() is None, "premissa: nenhum perfil do boot no disco"
    pasta = loader.profiles_dir()

    def _retrato() -> dict[str, str]:
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(pasta.glob("*.json"))}

    antes = _retrato()
    assert antes, "premissa: o Freestyle da régua está na pasta que o loader lê"
    assert Daemon.gravar_o_modo_escolhido(
        _daemon_que_grava(None), "gamepad", caminho="xbox", porta="ipc"
    ) is None
    assert _retrato() == antes, (
        "o escritor escolheu um perfil para receber o modo sem ninguém valendo")


def test_a_secao_do_modo_e_a_regra_do_dono() -> None:
    """A máscara não se apaga fora do `gamepad`, e no `gamepad` anda em par com o caminho.

    NOTA DATADA (27/10/2026, D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES): o caminho escolhido
    leva a máscara junto; antes, `None` queria dizer «mantém a atual».
    """
    from hefesto_dualsense4unix.profiles.manager import secao_do_modo_com_o_caminho
    from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig

    antes = ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
    fora = secao_do_modo_com_o_caminho(antes, kind="native")
    assert fora.kind == "native" and fora.gamepad_flavor == "xbox", (
        "o modo apagou a máscara padrão do perfil — a máscara não é do modo")

    fica = secao_do_modo_com_o_caminho(antes, kind="gamepad")
    assert fica.gamepad_flavor == "xbox", (
        "a máscara do disco foi apagada por um clique que não a escolheu — é a "
        "cicatriz do `or \"xbox\"` pelo avesso")
    do_zero = secao_do_modo_com_o_caminho(None, kind="gamepad", caminho="xbox")
    assert (do_zero.caminho, do_zero.gamepad_flavor) == ("xbox", "xbox"), (
        "o caminho escolhido não levou a máscara do par")


def _painel_do_produto() -> Any:
    from hefesto_dualsense4unix.app.actions.jogar import painel

    return painel


_ESTADO_DO_WEBKIT: dict[str, Any] = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "freestyle_ligado": False,
    "controllers": [
        {"uniq": P1, "connected": True, "transport": "usb", "player": 1},
        {"uniq": P2, "connected": True, "transport": "bt", "player": 2},
    ],
}

_LER_O_CADEADO = r"""
(function(){
  const c = document.querySelector('[data-gesto="cadeado"]');
  if(!c) return JSON.stringify({achou: false});
  const cs = getComputedStyle(c);
  return JSON.stringify({
    achou: true,
    verde: c.classList.contains('hef-deu-certo'),
    em_voo: c.classList.contains('hef-em-voo'),
    contorno: cs.outlineColor,
    contorno_larg: cs.outlineWidth,
  });
})()
"""

_CLICAR_NO_CADEADO = r"""
(function(){
  const c = document.querySelector('[data-gesto="cadeado"]');
  if(!c) return 'NAO ACHEI O CADEADO NA PAGINA PUBLICADA';
  c.click();
  return 'cliquei';
})()
"""

_VIGIAR_O_CADEADO = r"""
(function(){
  const seletor = '[data-gesto="cadeado"]';
  const c = document.querySelector(seletor);
  // a caixa existe E a página já pintou uma vez e tem o ouvinte de clique: antes disso o clique
  // não chega ao piloto
  const h = window.__hef;
  if(!c || !h || !h.ouvindo || !h.voltouDoVoo
     || document.documentElement.classList.contains('hef-esperando'))
    return JSON.stringify({achou: false});
  const v = window.__vigia = {voou: 0, pousou: 0, verde: 0, verde_apagou: 0,
                              recusou: 0, recusou_apagou: 0, larguras: [], duracoes: [],
                              desde: 0};
  const nomes = function(t){ return new Set((t || '').split(/\s+/).filter(Boolean)); };
  new MutationObserver(function(registros){
    const meus = registros.filter(function(r){ return r.target.matches(seletor); });
    meus.forEach(function(r, i){
      const antes = nomes(r.oldValue);
      const depois = nomes(i + 1 < meus.length ? meus[i + 1].oldValue
                           : r.target.getAttribute('class'));
      const mudou = function(n){
        return (!antes.has(n) && depois.has(n)) ? 1 : ((antes.has(n) && !depois.has(n)) ? -1 : 0);
      };
      if(mudou('hef-em-voo') > 0) v.voou += 1;
      if(mudou('hef-em-voo') < 0) v.pousou += 1;
      if(mudou('hef-recusou') > 0) v.recusou += 1;
      if(mudou('hef-recusou') < 0) v.recusou_apagou += 1;
      if(mudou('hef-deu-certo') > 0){
        v.verde += 1; v.desde = performance.now();
        v.larguras.push(getComputedStyle(r.target).outlineWidth);
      }
      if(mudou('hef-deu-certo') < 0){
        v.verde_apagou += 1; v.duracoes.push(performance.now() - v.desde);
      }
    });
  }).observe(document.documentElement, {attributes: true, subtree: true,
                                        attributeFilter: ['class'], attributeOldValue: true});
  return JSON.stringify({achou: true});
})()
"""

_LER_O_VIGIA = "JSON.stringify(window.__vigia || null)"

PRAZO_DA_TELA_S = 30.0


@pytest.fixture(scope="module")
def no_webkit() -> dict:
    """Abre o piloto DE VERDADE, oculto, e clica a caixa nos TRÊS desfechos.

    Linear: cada passo espera a CONDIÇÃO que o próximo precisa, com prazo, e o que estoura o
    prazo diz qual condição não veio. Só a piscada (e o apagar dela) é medida SEM derrubar o
    roteiro: é o que a primeira régua afirma, e as outras duas precisam dos cliques seguintes.
    """
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import json
    import time as _time

    import hefesto_vivo as hv

    guardado = (hv.mesa_viva.estado_do_daemon, hv.ponte.freestyle_set)
    da_piscada_ms = int(hv.MS_DA_PISCADA)
    hv.mesa_viva.estado_do_daemon = (  # type: ignore[assignment]
        lambda *a, **k: _ESTADO_DO_WEBKIT)

    resposta: dict[str, Any] = {"como": "eco"}

    def _ponte_do_cadeado(ligado: Any = None) -> Any:
        if resposta["como"] == "levanta":
            raise RuntimeError("o socket recusou o freestyle.set")
        return bool(ligado) if resposta["como"] == "eco" else None

    hv.ponte.freestyle_set = _ponte_do_cadeado  # type: ignore[assignment]

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre="01-jogar.html", prova_no_aparelho=False, entre=2500,
        espera=1200, incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, Any] = {"piscada_ms": da_piscada_ms, "sem_prazo": []}
    contexto = GLib.MainContext.default()

    def girar_ate(condicao: Any, o_que: str, prazo_s: float = PRAZO_DA_TELA_S) -> bool:
        """Gira o laço do GTK até a condição; estourou o prazo, devolve False e diz o quê."""
        limite = _time.monotonic() + prazo_s
        while not condicao():
            if _time.monotonic() >= limite:
                fora["sem_prazo"].append(f"em {prazo_s:.0f} s não aconteceu: {o_que}")
                return False
            contexto.iteration(False)
            _time.sleep(0.005)
        return True

    def perguntar(js: str, o_que: str) -> Any:
        """Pergunta à página e espera a resposta (a ponte é assíncrona)."""
        caixa: list[Any] = []

        def _leu(valor: Any, erro: Any) -> None:
            caixa.append(f"ERRO {erro}" if erro is not None else str(valor))

        piloto.ponte.perguntar(js, _leu)
        if not girar_ate(lambda: bool(caixa), f"a página responder a «{o_que}»"):
            pytest.fail(fora["sem_prazo"][-1])
        return caixa[0]

    def vigia() -> dict[str, Any]:
        lido: dict[str, Any] | None = json.loads(
            perguntar(_LER_O_VIGIA, "a leitura do vigia da caixa"))
        assert lido is not None, "o vigia da caixa não está na página"
        return lido

    def exigir(condicao: Any, o_que: str, prazo_s: float = PRAZO_DA_TELA_S) -> None:
        """Condição que o roteiro precisa para seguir: sem ela, a prova está pela metade."""
        if not girar_ate(condicao, o_que, prazo_s):
            pytest.fail(" | ".join(fora["sem_prazo"]))

    def espera_vigia(
        chave: str, quantos: int, o_que: str, prazo_s: float = PRAZO_DA_TELA_S
    ) -> bool:
        """Espera o vigia contar `quantos` do evento `chave`; True se veio, False no prazo."""
        return girar_ate(lambda: vigia()[chave] >= quantos, o_que, prazo_s)

    def clicar(rotulo: str) -> None:
        fora[rotulo] = perguntar(_CLICAR_NO_CADEADO, rotulo)

    assert args.abre == hv.PRIMEIRA, f"o piloto nasce em {hv.PRIMEIRA}, não em {args.abre}"
    try:
        exigir(lambda: piloto.pronto and piloto.pagina == args.abre,
               "a página 01-jogar.html abrir no WebKit (piloto.pronto)")
        exigir(
            lambda: json.loads(perguntar(_VIGIAR_O_CADEADO, "vigiar a caixa"))["achou"],
            "a caixa do cadeado aparecer na página que o piloto abriu",
        )
        chave = "01-jogar.html:cadeado"
        fora["antes"] = json.loads(perguntar(_LER_O_CADEADO, "ler a caixa antes do clique"))

        clicar("clique-1")
        piscou = espera_vigia(
            "verde", 1, "a caixa piscar verde depois do serviço confirmar o clique 1")
        if piscou:
            apagou = espera_vigia(
                "verde_apagou", 1, "a piscada verde apagar sozinha", 2 * da_piscada_ms / 1000 + 20)
            lido = vigia()
            fora["confirmou"] = {"verde": True, "contorno_larg": lido["larguras"][0]}
            fora["depois-da-piscada"] = {
                "verde": not apagou, "duracao_ms": (lido["duracoes"] or [None])[0]}
        else:
            fora["confirmou"] = {"verde": False, "contorno_larg": "0px"}
            fora["depois-da-piscada"] = {"verde": False, "duracao_ms": None}
        exigir(lambda: vigia()["pousou"] >= 1, "o clique 1 pousar (a caixa sair do voo)")
        verdes_antes = vigia()["verde"]

        resposta["como"] = "none"
        piloto.desfechos.pop(chave, None)
        clicar("clique-2")
        exigir(lambda: vigia()["pousou"] >= 2, "o clique 2 pousar (a caixa sair do voo)")
        exigir(lambda: chave in piloto.desfechos, "o piloto anotar o desfecho do clique 2")
        fora["desfecho-sem-resposta"] = list(piloto.desfechos[chave])
        fora["sem-resposta"] = {"verde": vigia()["verde"] > verdes_antes}
        exigir(lambda: vigia()["recusou_apagou"] >= vigia()["recusou"],
               "a piscada de recusa do clique 2 apagar")

        resposta["como"] = "levanta"
        clicar("clique-3")
        exigir(lambda: vigia()["pousou"] >= 3, "o clique 3 pousar (a caixa sair do voo)")
        fora["levantou"] = {"verde": vigia()["verde"] > verdes_antes}
        fora["desfechos"] = {k: list(v) for k, v in piloto.desfechos.items()}
    finally:
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.mesa_viva.estado_do_daemon,
         hv.ponte.freestyle_set) = guardado  # type: ignore[assignment]
    return fora


def test_o_verde_do_cadeado_no_webkit_e_do_servico(no_webkit: dict) -> None:
    """A piscada acende quando o serviço confirmou — e SÓ então."""
    assert no_webkit["clique-1"] == "cliquei", no_webkit["clique-1"]
    antes, certo = no_webkit["antes"], no_webkit["confirmou"]
    assert antes["achou"], "a caixa do cadeado não está na página que o piloto abriu"

    assert not antes["verde"], "a caixa já estava piscando ANTES do clique"

    assert certo["verde"], (
        "o serviço confirmou e a caixa não piscou — é o gesto desta aba cujo "
        "efeito não aparece em lugar nenhum da tela, e sem a piscada ele "
        f"responde ao clique dela com nada ({no_webkit['sem_prazo']})")
    assert certo["contorno_larg"] != "0px", (
        f"a classe entrou e a folha não pegou: `outline-width` "
        f"{certo['contorno_larg']!r}. É a diferença entre a régua verde e o "
        f"olho dela vendo alguma coisa")

    assert not no_webkit["depois-da-piscada"]["verde"], (
        f"a piscada não apagou sozinha: {no_webkit['sem_prazo']}")
    assert no_webkit["depois-da-piscada"]["duracao_ms"] >= 0.9 * no_webkit["piscada_ms"], (
        f"a piscada durou {no_webkit['depois-da-piscada']['duracao_ms']} ms, menos que os "
        f"{no_webkit['piscada_ms']} ms do produto")


def test_o_cadeado_nao_pisca_sobre_o_que_nao_foi_guardado(no_webkit: dict) -> None:
    """O serviço não respondeu — e a tela NÃO pode dizer que guardou."""
    assert no_webkit["clique-2"] == "cliquei", no_webkit["clique-2"]
    assert not no_webkit["sem-resposta"]["verde"], (
        "a caixa piscou VERDE com o serviço sem responder — o verde é o recibo "
        "de uma escrita que não aconteceu")

    classe, frase = no_webkit["desfecho-sem-resposta"]
    assert classe == "recusou dizendo" and aba.CADEADO_RECUSA in frase, (
        f"o gesto não recusou com a frase do dono — o desfecho foi "
        f"{classe!r}: {frase!r}. Um gesto que não pisca e não diz nada ao "
        f"diário é o clique que some calado")

    assert no_webkit["clique-3"] == "cliquei", no_webkit["clique-3"]
    assert not no_webkit["levantou"]["verde"], (
        "a ponte levantou e a caixa piscou VERDE mesmo assim")
