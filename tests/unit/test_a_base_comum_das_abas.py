#!/usr/bin/env python3
"""A base comum das abas (A-BASE-COMUM-DAS-ABAS-01): o «?» sai, a base entra, os modos gravam.

O que a régua cobra, e a mordida de cada uma:

1. **Nenhum «?» na posse da base.** O `.ajuda` não mora mais em `topo.html`, `fim.html`, `monta.py`,
   `janela.py`, `hefesto_vivo.py` nem `calibrar.py`; o `botao_cinza` escreve a razão no `data-dica`
   do próprio botão. MORDIDA: devolver o `<span class="ajuda">` ao `botao_cinza` reprova.
2. **O que resta é de outra sprint e só diminui.** Cada gerador de aba que ainda tem `.ajuda`
   está em `ISENTOS` com a sprint dona; o número não cresce, e a isenção sai quando o arquivo zera.
3. **A base entra uma vez em toda página**, no `<style>` e no `<script>` de `id="base-comum"`,
   idêntica aos arquivos `base-comum.css` e `base-comum.js`.
4. **O `.modo-auto` não existe na 01** (nem de 06 a 10), e o do `monta.modo_auto` fala a língua
   do piloto: gesto, `data-modo`, `aria-pressed`.
5. **O modo da vibração e o dos controles gravam e voltam iguais** ao reabrir o perfil.
6. **O menu do botão direito tem dono**: o WebKit cala o dele, e cada item aciona um gesto
   registrado.
7. **Os efeitos que ela cria têm um dono só**, com uma chave por feature.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo, monta, pacotes
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from tests.unit.test_cada_gesto_diz_de_quem_e import _contexto, _perfil, _Ponte

AUTO = "automatico"  # (noqa-acento) valor do contrato, sem acento
RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src/hefesto_dualsense4unix/interface"

#: Os arquivos da posse da base: nenhum `.ajuda`, nenhum «?» de botão.
SEM_AJUDA = ("topo.html", "fim.html", "monta.py", "janela.py", "hefesto_vivo.py", "calibrar.py",
             "base-comum.css", "base-comum.js")

#: O que ainda tem `.ajuda` e é de OUTRA sprint: `arquivo → quantos`. Cada gerador de
#: aba (`abaNN.py`) e as páginas que ela monta saem na sprint da aba (`A-ABA-<nome>-DO-TODO-01`),
#: que troca o «?» pelo `data-dica`. O número só diminui, e a linha sai quando o arquivo zera.
ISENTOS: dict[str, int] = {
    "desenho_dos_lancadores.py": 2,  # sai com: A-ABA-EXPERIMENTAL-DO-TODO-01
}

#: Uma CITAÇÃO que proíbe não é um uso: o guarda do `aba03.py` escreve `'class="ajuda' not in
#: corpo`, e aí o `ajuda` vem seguido da aspa simples que fecha a string, nunca do atributo.
_CLASSE_AJUDA = re.compile(r'class=(?:"ajuda\b(?!\')|\'ajuda\b)')
_CSS_AJUDA = re.compile(r"\.ajuda\b")
#: um botão cujo texto é só «?»
_BOTAO_DE_INTERROGACAO = re.compile(r"<button\b[^>]*>\s*(?:<[^>]+>\s*)*\?\s*<", re.IGNORECASE)


def _fonte(nome: str) -> str:
    return (INTERFACE / nome).read_text(encoding="utf-8")


def _arquivos_da_interface() -> list[pathlib.Path]:
    return sorted(p for p in INTERFACE.iterdir()
                  if p.is_file() and p.suffix in (".py", ".html", ".css", ".js"))


# --- 1. a posse da base não tem «?» ---------------------------------------------------------------

@pytest.mark.parametrize("nome", SEM_AJUDA)
def test_a_posse_da_base_nao_tem_ajuda(nome: str) -> None:
    """Nenhum `class="ajuda`, nenhum seletor `.ajuda` e nenhum botão de «?» na posse da base.

    A única folha que sobra é a `monta.CSS_DO_AJUDA_QUE_SAI`, e só enquanto há `ISENTOS`.
    """
    fonte = _fonte(nome).replace(getattr(monta, "CSS_DO_AJUDA_QUE_SAI", "\0"), "")
    assert not _CLASSE_AJUDA.search(fonte), f"{nome}: ainda escreve um `class=\"ajuda\"`"
    assert not _BOTAO_DE_INTERROGACAO.search(fonte), f"{nome}: tem botão cujo texto é «?»"
    achou = [m for m in _CSS_AJUDA.finditer(fonte)]
    assert not achou, f"{nome}: ainda tem o seletor `.ajuda` ({len(achou)} vezes)"


def test_o_botao_cinza_diz_a_razao_no_proprio_botao() -> None:
    """A razão mora no `data-dica` do botão; não há `<span>` de «?» ao lado.

    MORDIDA: devolver o `<span class="ajuda porque">` ao `botao_cinza` reprova.
    """
    # A decisão: D-1410-A-RAZAO-DO-CINZA-MORA-NO-BOTAO.
    html = monta.botao_cinza("Parar o serviço", "parar", "parar-razao", "Já está parado.")
    assert "ajuda" not in html, html
    assert ">?<" not in html.replace(" ", ""), html
    assert 'data-hef-razao="sim"' in html, html
    assert 'data-dica="Já está parado."' in html, html
    assert html.count("<button") == 1, html


def test_a_citacao_que_proibe_o_ajuda_nao_conta_como_uso() -> None:
    """O guarda de um gerador que cita `'class="ajuda'` para proibi-lo não é um `.ajuda` escrito.

    MORDIDA: troque o regex pelo antigo (`class=["\\']ajuda\\b`) e o guarda do `aba03.py` volta a
    contar como uso — este caso reprova.
    """
    assert not _CLASSE_AJUDA.search("""exigir('class="ajuda' not in corpo, "x")""")
    assert _CLASSE_AJUDA.search('<span class="ajuda porque">?</span>')
    assert _CLASSE_AJUDA.search('<span class="ajuda">?</span>')
    assert _CLASSE_AJUDA.search("<span class='ajuda'>?</span>")
    assert not _CLASSE_AJUDA.findall(_fonte("aba03.py")), "o aba03.py voltou a escrever o `.ajuda`"


def test_o_que_resta_de_ajuda_e_de_outra_sprint_e_so_diminui() -> None:
    """Quem ainda escreve `class="ajuda"` está declarado, e o número não cresce."""
    # A decisão: D-1410-A-RAZAO-DO-CINZA-MORA-NO-BOTAO.
    achados = {p.name: len(_CLASSE_AJUDA.findall(p.read_text(encoding="utf-8")))
               for p in _arquivos_da_interface()
               if p.name not in SEM_AJUDA}
    achados = {nome: n for nome, n in achados.items() if n}
    sem_dono = sorted(set(achados) - set(ISENTOS))
    assert not sem_dono, (
        f"arquivo(s) com `class=\"ajuda\"` e sem sprint dona em ISENTOS: {sem_dono}. "
        "A dica mora no `data-dica` do elemento (A-BASE-COMUM-DAS-ABAS-01).")
    cresceu = {nome: (achados[nome], teto) for nome, teto in ISENTOS.items()
               if achados.get(nome, 0) > teto}
    assert not cresceu, f"o `.ajuda` CRESCEU (agora, teto): {cresceu}"
    zerou = sorted(nome for nome in ISENTOS if not achados.get(nome))
    assert not zerou, f"zerou o `.ajuda`; tire a linha de ISENTOS: {zerou}"


# --- 2. a base entra uma vez em toda página -------------------------------------------------------

def test_a_base_dos_arquivos_e_a_que_o_monta_injeta() -> None:
    css = (INTERFACE / "base-comum.css").read_text(encoding="utf-8")
    js = (INTERFACE / "base-comum.js").read_text(encoding="utf-8")
    assert css == monta.BASE_CSS
    assert js == monta.BASE_JS
    doc = monta.com_a_base("<html><head></head><body></body></html>")
    assert doc.count('id="base-comum"') == 2
    assert f'<style id="base-comum">\n{css}</style>' in doc
    assert f'<script id="base-comum">\n{js}</script>' in doc


def test_a_base_nao_entra_duas_vezes() -> None:
    """MORDIDA: tirar a guarda do `com_a_base` deixa a base dobrada, e esta chamada não reprova."""
    uma = monta.com_a_base("<html><head></head><body></body></html>")
    with pytest.raises(SystemExit):
        monta.com_a_base(uma)
    with pytest.raises(SystemExit):
        monta.com_a_base("<html><body></body></html>")


@pytest.fixture(scope="module")
def paginas_geradas(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """As dez abas e a Calibrar, geradas de novo numa bancada de mentira (em paralelo)."""
    destino = tmp_path_factory.mktemp("bancada-da-base")
    for p in (RAIZ / "mockup").glob("*.html"):
        shutil.copy2(p, destino / p.name)
    ambiente = dict(os.environ, HEFESTO_BANCADA=str(destino), PYTHONPATH=str(RAIZ / "src"))
    geradores = [*sorted(p.name for p in INTERFACE.glob("aba[0-9][0-9].py")), "calibrar.py"]
    filhos = [(nome, subprocess.Popen(
        [sys.executable, str(INTERFACE / nome)], cwd=str(RAIZ), env=ambiente,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)) for nome in geradores]
    for nome, filho in filhos:
        _fora, erro = filho.communicate(timeout=180)
        if filho.returncode != 0:
            from tests.conftest import repassar_a_falta_do_gtk

            repassar_a_falta_do_gtk(subprocess.CompletedProcess(
                filho.args, filho.returncode, _fora, erro))
            raise AssertionError(f"`{nome}` não roda:\n{erro.strip()[-1200:]}")
    paginas = {p.name: p.read_text(encoding="utf-8")
               for p in sorted(destino.glob("*.html"))
               if re.match(r"(0\d|10)-", p.name) or p.name == "calibrar-sensores.html"}
    assert len(paginas) == 11, sorted(paginas)
    return paginas


def test_a_folha_do_ajuda_que_sai_vive_so_enquanto_ha_isentos() -> None:
    """Zerou o último «?» das abas: a folha de transição sai do `monta.py` junto."""
    if not ISENTOS:
        assert not hasattr(monta, "CSS_DO_AJUDA_QUE_SAI"), "ISENTOS zerou; tire a folha do monta"
        return
    assert ".ajuda:hover .dica" in monta.CSS_DO_AJUDA_QUE_SAI
    assert ".ajuda.porque:has(.nada)" in monta.CSS_DO_AJUDA_QUE_SAI


def test_a_pagina_com_o_span_leva_a_folha_e_a_sem_span_nao(
        paginas_geradas: dict[str, str], tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O «?» que ainda sai de uma aba abre a dica e some sem razão; página sem ele não leva a folha.

    MORDIDA: tirar a injeção do `monta.monta` reprova as páginas que ainda têm o span.
    """
    folha = monta.CSS_DO_AJUDA_QUE_SAI
    sem_folha = sorted(n for n, doc in paginas_geradas.items()
                       if _CLASSE_AJUDA.search(doc) and folha not in doc)
    assert not sem_folha, f"página(s) com o «?» e sem a folha dele: {sem_folha}"
    sobrando = sorted(n for n, doc in paginas_geradas.items()
                      if not _CLASSE_AJUDA.search(doc) and folha in doc)
    assert not sobrando, f"página(s) sem nenhum «?» e com a folha dele: {sobrando}"
    # 17/10/2026: com a 07 sem o «?», nenhuma aba gerada o traz mais; a injeção se prova numa
    # página de mentira montada pelo mesmo `monta.monta`, que é o que a mordida de cima arranca.
    if not any(_CLASSE_AJUDA.search(doc) for doc in paginas_geradas.values()):
        monkeypatch.setenv("HEFESTO_BANCADA", str(tmp_path))
        monta.monta("07-lancadores", "Prova", '<div><span class="ajuda">?</span></div>')
        feita = (tmp_path / "07-lancadores.html").read_text(encoding="utf-8")
        assert folha in feita, "a folha não entra numa página que ainda tem o span"


def test_toda_pagina_tem_a_base_uma_vez_e_identica_ao_arquivo(
        paginas_geradas: dict[str, str]) -> None:
    css = (INTERFACE / "base-comum.css").read_text(encoding="utf-8")
    js = (INTERFACE / "base-comum.js").read_text(encoding="utf-8")
    for nome, doc in paginas_geradas.items():
        assert doc.count('<style id="base-comum">') == 1, f"{nome}: o <style> da base"
        assert doc.count('<script id="base-comum">') == 1, f"{nome}: o <script> da base"
        assert f'<style id="base-comum">\n{css}</style>' in doc, f"{nome}: CSS diferente do arquivo"
        assert f'<script id="base-comum">\n{js}</script>' in doc, f"{nome}: JS diferente do arquivo"


def test_o_modo_auto_nao_existe_na_01_nem_de_06_a_10(paginas_geradas: dict[str, str]) -> None:
    """O botão é das abas 02 a 05; a 01 (e as de 06 a 10) não o tem.

    Que ele APAREÇA em 02 a 05 é da sprint de cada aba, que troca o par pelo `monta.modo_auto`.
    """
    com = sorted(nome for nome, doc in paginas_geradas.items()
                 if 'class="modo-auto"' in doc and not re.match(r"0[2-5]-", nome))
    assert not com, f"página(s) com o botão «Modo automático» fora das abas 02 a 05: {com}"


def test_o_modo_auto_fala_a_lingua_do_piloto() -> None:
    html = monta.modo_auto("modo-da-vibracao", ligado=True, governa=".coluna")
    assert 'class="modo-auto"' in html
    assert 'data-gesto="modo-da-vibracao"' in html
    assert 'aria-pressed="true"' in html
    assert 'data-campo="modo-da-vibracao-automatico"' in html
    assert 'data-hef-classe="ligado"' in html
    assert 'data-governa=".coluna"' in html
    assert 'data-modo="personalizado"' in html, "ligado, o próximo pedido é o personalizado"
    desligado = monta.modo_auto("modo-da-vibracao")
    assert 'aria-pressed="false"' in desligado
    assert f'data-modo="{AUTO}"' in desligado


# --- 3. os modos gravam e voltam iguais -----------------------------------------------------------

GESTOS_DO_MODO = [
    ("05-vibracao.html", "modo-da-vibracao", "rumble", "modo"),
    ("02-controles.html", "modo-dos-controles", None, "controles_modo"),
]


def _ler(secao: str | None, campo: str, nome: str) -> Any:
    prof = load_profile(nome)
    return getattr(getattr(prof, secao), campo) if secao else getattr(prof, campo)


@pytest.mark.parametrize(("aba", "gesto", "secao", "campo"), GESTOS_DO_MODO,
                         ids=[g[1] for g in GESTOS_DO_MODO])
def test_o_modo_grava_e_volta_igual_ao_reabrir(
        aba: str, gesto: str, secao: str | None, campo: str) -> None:
    """Automático grava, Personalizado devolve, e o mesmo pedido de novo não regrava.

    MORDIDA: tirar o `save_profile` do gesto reprova na leitura do disco.
    """
    save_profile(_perfil("Jogo X"))
    outro = save_profile(_perfil("Jogo Y"))
    outro_antes = outro.read_bytes()
    fn = pacotes.gesto_da_pagina(aba, gesto)
    assert fn is not None, f"{aba}·{gesto} sem dono"
    ctx = _contexto(pacotes, "Jogo X")

    assert _ler(secao, campo, "Jogo X") is None, "ninguém escolheu: o campo nasce vazio"
    fn(ctx, {"modo": AUTO}, _Ponte())
    assert _ler(secao, campo, "Jogo X") == AUTO

    caminho = save_profile(load_profile("Jogo X"))
    antes = caminho.read_bytes()
    fn(ctx, {"modo": AUTO}, _Ponte())
    assert caminho.read_bytes() == antes, "pedir o modo em que o perfil já está não regrava"

    fn(ctx, {"modo": "personalizado"}, _Ponte())
    assert _ler(secao, campo, "Jogo X") == "personalizado"
    assert outro.read_bytes() == outro_antes, "o gesto mexeu em OUTRO perfil"


@pytest.mark.parametrize(("aba", "gesto", "_s", "_c"), GESTOS_DO_MODO,
                         ids=[g[1] for g in GESTOS_DO_MODO])
def test_o_modo_recusa_pedido_sem_modo_e_sem_perfil(aba: str, gesto: str, _s: Any, _c: Any) -> None:
    save_profile(_perfil("Jogo X"))
    fn = pacotes.gesto_da_pagina(aba, gesto)
    assert fn is not None
    with pytest.raises(ValueError):
        fn(_contexto(pacotes, "Jogo X"), {}, _Ponte())
    with pytest.raises(ValueError):
        fn(_contexto(pacotes, "Jogo X"), {"modo": "qualquer"}, _Ponte())
    with pytest.raises(RuntimeError):
        fn(_contexto(pacotes, ""), {"modo": AUTO}, _Ponte())


def test_o_modo_sobrevive_ao_salvar_do_rodape() -> None:
    """O rascunho da tela (`DraftConfig`) leva o modo de volta ao perfil: salvar não o apaga.

    MORDIDA: tirar `modo=self.rumble.modo` ou `controles_modo=` do `to_profile` reprova.
    """
    # A decisão: D-1410-OS-MODOS-SAO-CAMPOS-DO-PERFIL.
    from hefesto_dualsense4unix.app.draft_config import DraftConfig

    save_profile(_perfil("Jogo X", controles_modo=AUTO, rumble={"modo": AUTO}))
    volta = DraftConfig.from_profile(load_profile("Jogo X")).to_profile("Jogo X")
    assert volta.controles_modo == AUTO
    assert volta.rumble.modo == AUTO


def test_o_perfil_sem_modo_escolhido_sai_igual_ao_de_ontem() -> None:
    """Sem modo escolhido, nem `controles_modo` nem `rumble.modo` vão ao disco ou ao dump.

    Um Hefesto anterior a esta sprint lê o `Profile` e o `RumbleConfig` com `extra="forbid"`: uma
    chave `"modo": null` em todo save o faria recusar TODOS os perfis num downgrade
    (QUEM-E-QUEM-02). MORDIDA: tirar o serializador do `RumbleConfig` reprova.
    """
    # A decisão: D-1410-OS-MODOS-SAO-CAMPOS-DO-PERFIL.
    import json

    caminho = save_profile(_perfil("Jogo X"))
    gravado = json.loads(caminho.read_text(encoding="utf-8"))
    assert "controles_modo" not in gravado
    assert "modo" not in gravado["rumble"]
    dump = load_profile("Jogo X").model_dump(mode="json")
    assert "controles_modo" not in dump and "modo" not in dump["rumble"]
    escolhido = save_profile(_perfil("Jogo Y", controles_modo=AUTO, rumble={"modo": AUTO}))
    gravado = json.loads(escolhido.read_text(encoding="utf-8"))
    assert gravado["controles_modo"] == AUTO and gravado["rumble"]["modo"] == AUTO


def test_os_modos_nao_se_deduzem_do_perfil() -> None:
    """Sem nada escrito a aba segue no Personalizado: o Automático nunca nasce por dedução."""
    # A decisão: D-1410-OS-MODOS-SAO-CAMPOS-DO-PERFIL.
    from hefesto_dualsense4unix.interface.pacotes import a02_controles, a05_vibracao

    vib, ctl = a05_vibracao.modo_da_vibracao_do_perfil, a02_controles.modo_dos_controles_do_perfil
    assert vib(None) == "personalizado"
    assert vib({"rumble": {"passthrough": True}}) == "personalizado"
    assert vib({"rumble": {"modo": AUTO}}) == AUTO
    assert ctl({}) == "personalizado"
    assert ctl({"controles_modo": AUTO}) == AUTO


def test_os_dois_gestos_do_modo_tem_camada() -> None:
    camada = pacotes.camada
    for aba, gesto, _s, _c in GESTOS_DO_MODO:
        assert camada.CAMADA[(aba, gesto)] == camada.JOGO, f"{aba}·{gesto}"


# --- 4. o menu do botão direito -------------------------------------------------------------------

def test_o_webkit_cala_o_menu_dele() -> None:
    """O sinal `context-menu` devolve `True`: o WebKit não abre o Recarregar/Voltar/Inspecionar.

    MORDIDA: devolver `False` (ou tirar a ligação do sinal) reprova.
    """
    # A decisão: D-1410-O-MENU-DO-BOTAO-DIREITO-E-DA-CASA.
    from hefesto_dualsense4unix.interface import janela

    assert janela.PonteDaTela._calar_o_menu_do_webkit(None, None, None, None) is True
    fonte = (INTERFACE / "janela.py").read_text(encoding="utf-8")
    assert 'self.view.connect("context-menu", self._calar_o_menu_do_webkit)' in fonte


def test_todo_item_do_menu_tem_um_gesto_com_dono() -> None:
    """Os `data-gesto` do menu da base existem no despachante, em toda página (`("*", gesto)`)."""
    js = (INTERFACE / "base-comum.js").read_text(encoding="utf-8")
    do_menu = set(re.findall(r'data-gesto="(menu-[a-z-]+)"', js))
    assert do_menu == {"menu-atualizar", "menu-desligar", "menu-reiniciar", "menu-fechar"}, do_menu
    hefesto_vivo._registrar_o_menu()
    sem_dono = sorted(g for g in do_menu if ("*", g) not in pacotes.GESTOS)
    assert not sem_dono, f"item(ns) do menu sem gesto registrado: {sem_dono}"
    assert set(hefesto_vivo.ITENS_DO_MENU_NA_SISTEMA) | {"menu-fechar"} == do_menu
    for na_sistema in hefesto_vivo.ITENS_DO_MENU_NA_SISTEMA.values():
        assert ("09-sistema.html", na_sistema) in pacotes.GESTOS, na_sistema


def test_o_menu_vive_no_nativo() -> None:
    """Atualizar, Desligar, Reiniciar e Fechar não são escolhas do Hefesto: passam no Nativo."""
    camada = pacotes.camada
    estado = {"native_mode": True}
    for g in sorted(camada.GESTOS_DO_MENU):
        for aba in sorted(camada.ABAS_POR_CONTROLE):
            assert camada.recusa_no_nativo(aba, g, estado) is None, f"{aba}·{g}"


def test_os_itens_do_menu_que_mexem_na_maquina_estao_nos_perigosos() -> None:
    """Desligar, Reiniciar e Fechar declaram `grava=`: a régua de clique não os aciona sozinha.

    MORDIDA: tirar o `grava=` dos itens no `hefesto_vivo._registrar_o_menu` reprova.
    """
    # A decisão: D-1410-O-MENU-DO-BOTAO-DIREITO-E-DA-CASA.
    perigosos = pacotes.perigosos()
    fora = sorted(g for g in ("menu-desligar", "menu-reiniciar", "menu-fechar")
                  if ("*", g) not in perigosos)
    assert not fora, f"item(ns) do menu fora dos perigosos: {fora}"
    assert ("*", "menu-atualizar") not in perigosos, "Atualizar só relê a tela"


def test_o_desligar_do_menu_pede_a_confirmacao_da_sistema() -> None:
    """O item «Desligar» troca o texto para «Confirma?» antes do 2º clique, como na aba Sistema."""
    # A decisão: D-1410-O-MENU-DO-BOTAO-DIREITO-E-DA-CASA.
    js = (INTERFACE / "base-comum.js").read_text(encoding="utf-8")
    assert "Confirma?" in js
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    assert a09_sistema.CONFIRMA == "Confirma?"


# --- 4b. a base viva num navegador: o clique direito e o automático ----------------------------

CHROME = pathlib.Path("/usr/bin/google-chrome")

_PAGINA_VIVA = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<div class="area" style="padding:40px;height:300px"><p id="texto">Texto qualquer da aba</p>
%s
<div id="alvo" class="coluna"></div></div></body></html>"""

_GESTO_NO_NAVEGADOR = """async () => {
  const esperar = ms => new Promise(r => setTimeout(r, ms));
  const rel = {};
  const auto = document.querySelector('.modo-auto');
  const alvo = document.getElementById('alvo');
  rel.auto_antes = {modo: auto.dataset.modo,
                    governado: alvo.classList.contains('governado-pelo-jogo')};
  auto.click(); await esperar(80);
  rel.auto_depois = {modo: auto.dataset.modo, pressionado: auto.getAttribute('aria-pressed'),
                     governado: alvo.classList.contains('governado-pelo-jogo')};
  document.getElementById('texto').dispatchEvent(
    new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: 60, clientY: 60}));
  const menu = document.querySelector('.menu-hefesto.vivo');
  rel.menu = menu ? [...menu.querySelectorAll('button')].map(b => ({
    texto: b.textContent.trim(), gesto: b.dataset.gesto || null,
    desabilitado: b.disabled})) : null;
  const desligar = menu && menu.querySelector('[data-gesto="menu-desligar"]');
  if (desligar) {
    desligar.click(); await esperar(80);
    rel.desligar_apos_o_clique = desligar.textContent.trim();
  }
  rel.menu_segue_aberto = !!document.querySelector('.menu-hefesto.vivo');
  document.getElementById('texto').click(); await esperar(80);
  rel.menu_apos_clicar_fora = !!document.querySelector('.menu-hefesto.vivo');
  return rel;
}"""


@pytest.fixture(scope="module")
def vivo() -> dict[str, Any]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema: a régua não tem motor")
    from playwright.sync_api import sync_playwright

    corpo = monta.modo_auto("modo-da-vibracao", governa="#alvo")
    doc = monta.com_a_base(_PAGINA_VIVA % corpo)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 900, "height": 600})
            pg.set_content(doc)
            return dict(pg.evaluate(_GESTO_NO_NAVEGADOR))
        finally:
            navegador.close()


def test_o_automatico_liga_e_a_area_que_ele_governa_esmaece(vivo: dict[str, Any]) -> None:
    """O clique vira `aria-pressed`, o `data-modo` pede o contrário e o alvo ganha a classe."""
    assert vivo["auto_antes"] == {"modo": AUTO, "governado": False}, vivo["auto_antes"]
    assert vivo["auto_depois"] == {"modo": "personalizado", "pressionado": "true",
                                   "governado": True}, vivo["auto_depois"]


def test_o_botao_direito_abre_o_menu_da_casa_com_os_cinco_itens(vivo: dict[str, Any]) -> None:
    """MORDIDA: renomear o ouvinte `contextmenu` no JS da base reprova (o menu nem nasce)."""
    assert vivo["menu"] is not None, "o botão direito não abriu o menu do Hefesto"
    assert [(i["texto"], i["gesto"]) for i in vivo["menu"]] == [
        ("Copiar", None), ("Atualizar", "menu-atualizar"), ("Desligar", "menu-desligar"),
        ("Reiniciar", "menu-reiniciar"), ("Fechar", "menu-fechar")]
    assert vivo["menu"][0]["desabilitado"] is True, "Copiar sem seleção tem de ficar cinza"


def test_desligar_do_menu_pede_dois_cliques_e_clicar_fora_fecha(vivo: dict[str, Any]) -> None:
    assert vivo["desligar_apos_o_clique"] == "Confirma?"
    assert vivo["menu_segue_aberto"] is True, "o menu fechou antes do segundo clique"
    assert vivo["menu_apos_clicar_fora"] is False, "clicar fora não fechou o menu"


_NO_NATIVO = """<!doctype html><html><head><meta charset="utf-8"><style>%s</style></head>
<body class="por-controle nativo"><p id="texto">Texto</p>
<button id="da-aba" data-gesto="cor">Cor</button></body></html>"""

_MEDIR_O_MENU_NO_NATIVO = """() => {
  document.getElementById('texto').dispatchEvent(
    new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: 30, clientY: 30}));
  const pe = el => getComputedStyle(el).pointerEvents;
  const menu = document.querySelector('.menu-hefesto.vivo');
  return {da_aba: pe(document.getElementById('da-aba')),
          menu: menu ? [...menu.querySelectorAll('button[data-gesto]')].map(
            b => [b.dataset.gesto, pe(b)]) : null};
}"""


def test_o_menu_aceita_clique_no_nativo_e_o_botao_da_aba_nao() -> None:
    """A folha do Nativo cinza o que a aba grava, e o menu do botão direito não é da aba.

    MORDIDA: tirar o `.menu-hefesto *` do `:not(...)` do `monta.CSS_DO_NATIVO` reprova
    (os quatro itens ficam com `pointer-events:none` nas cinco abas por controle).
    """
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema: a régua não tem motor")
    from playwright.sync_api import sync_playwright

    doc = monta.com_a_base(_NO_NATIVO % monta.CSS_DO_NATIVO)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 600, "height": 400})
            pg.set_content(doc)
            medido = pg.evaluate(_MEDIR_O_MENU_NO_NATIVO)
        finally:
            navegador.close()
    assert medido["da_aba"] == "none", f"o controle da régua falhou: {medido}"
    assert medido["menu"], medido
    mortos = [g for g, pe in medido["menu"] if pe == "none"]
    assert not mortos, f"item(ns) do menu sem clique no Nativo: {mortos}"


_COM_O_SERVICO = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<i hidden data-campo="servico" data-servico="%s"></i><p id="texto">Texto</p></body></html>"""

_O_ITEM_DO_SERVICO = """async () => {
  const esperar = ms => new Promise(r => setTimeout(r, ms));
  document.getElementById('texto').dispatchEvent(
    new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: 30, clientY: 30}));
  const b = document.querySelector('.menu-hefesto.vivo [data-gesto="menu-desligar"]');
  const antes = b ? b.textContent.trim() : null;
  if (b) { b.click(); await esperar(80); }
  return {antes: antes, depois: b ? b.textContent.trim() : null,
          menu_aberto: !!document.querySelector('.menu-hefesto.vivo')};
}"""


@pytest.mark.parametrize(("servico", "esperado"), [  # (noqa-acento) valor do contrato
    ("de-pe", {"antes": "Desligar", "depois": "Confirma?", "menu_aberto": True}),
    ("parado", {"antes": "Ligar", "depois": "Ligar", "menu_aberto": False}),
    ("pausado", {"antes": "Ligar", "depois": "Ligar", "menu_aberto": False}),
])
def test_o_item_do_servico_diz_desligar_ou_ligar(servico: str, esperado: dict[str, Any]) -> None:
    """De pé, «Desligar» pede dois cliques; parado ou pausado, «Ligar» age no primeiro.

    MORDIDA: fixar o rótulo «Desligar» no JS da base reprova os casos parado e pausado.
    """
    # A decisão: D-1410-O-MENU-DO-BOTAO-DIREITO-E-DA-CASA.
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema: a régua não tem motor")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 600, "height": 400})
            pg.set_content(monta.com_a_base(_COM_O_SERVICO % servico))
            medido = pg.evaluate(_O_ITEM_DO_SERVICO)
        finally:
            navegador.close()
    assert medido == esperado, medido


def test_o_cabecalho_leva_o_estado_do_servico() -> None:
    """O `data-servico` do cabeçalho é endereço do `pacotes.topo`, nas dez abas."""
    topo = (INTERFACE / "topo.html").read_text(encoding="utf-8")
    assert 'data-campo="servico" data-hef-alvo="atributo" data-hef-atributo="data-servico"' in topo
    assert pacotes.servico_do_menu({}) == "parado"
    assert pacotes.servico_do_menu(None) == "parado"
    assert pacotes.servico_do_menu({"paused": True, "connected": True}) == "pausado"
    assert pacotes.servico_do_menu({"connected": True}) == "de-pe"
    ctx = pacotes.Contexto(state={"connected": True}, mesa=[], conectados=[], estados={})
    assert pacotes.topo(ctx)["servico"] == "de-pe"  # (noqa-acento) endereço da página


# --- 5. a dica da casa lê o data-dica -------------------------------------------------------------

def test_a_dica_da_casa_le_o_data_dica_ao_vivo() -> None:
    """O piloto lê `data-dica` primeiro; o `data-hef-razao` escreve a razão no botão cinza."""
    vivo = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    assert "data-dica" in vivo
    assert "data-hef-razao" in vivo
    js = (INTERFACE / "base-comum.js").read_text(encoding="utf-8")
    assert "window.__hefDica" in js, "a dica da base só cria a dela quando o piloto não tem a sua"


_FOCO = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<button id="um" data-dica="A razão do botão">Um</button> <button id="dois">Dois</button>
</body></html>"""

_CAIXA = """() => { const c = document.getElementById('hef-dica');
  return c ? {aberta: getComputedStyle(c).display !== 'none', texto: c.textContent} : null; }"""


def test_a_dica_da_casa_abre_no_foco_do_teclado_e_fecha_ao_sair() -> None:
    """O `data-dica` chega a quem anda pelo teclado ou pelo controle, na camada do produto.

    MORDIDA: tirar o ouvinte `focusin` da `DICA_DA_CASA` reprova (a caixa não abre no Tab).
    """
    # A decisão: D-1410-A-DICA-ABRE-NO-FOCO.
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema: a régua não tem motor")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 600, "height": 400})
            pg.set_content(_FOCO)
            pg.evaluate(hefesto_vivo.DICA_DA_CASA)
            pg.keyboard.press("Tab")
            no_foco = pg.evaluate(_CAIXA)
            pg.keyboard.press("Tab")
            fora = pg.evaluate(_CAIXA)
        finally:
            navegador.close()
    assert no_foco == {"aberta": True, "texto": "A razão do botão"}, no_foco
    assert fora and fora["aberta"] is False, fora


# --- 6. os efeitos que ela cria têm um dono só ----------------------------------------------------

CHAVES = {
    "gatilhos": "gatilhos_meus_efeitos",
    "imersao": "imersao_meus_efeitos",
    "luz": "luz_meus_efeitos",
    "vibracao": "vibracao_meus_efeitos",
    "controles": "controles_meus_efeitos",
}


def test_uma_chave_por_feature_e_a_dos_gatilhos_fica() -> None:
    # A decisão: D-1410-OS-EFEITOS-DELA-TEM-UM-DONO.
    from hefesto_dualsense4unix.interface.pacotes import meus_efeitos

    assert meus_efeitos.CHAVES == CHAVES
    assert meus_efeitos.PREFIXO_DO_MEU == "meu:"


@pytest.mark.parametrize("feature", ["imersao", "luz", "vibracao", "controles"])
def test_criar_efeito_guarda_na_chave_da_feature_e_preserva_o_resto(feature: str) -> None:
    from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs, save_gui_prefs
    from hefesto_dualsense4unix.interface.pacotes import meus_efeitos

    prefs = load_gui_prefs()
    prefs["advanced_editor"] = True
    prefs["gatilhos_meus_efeitos"] = {"Recuo": {"left": {"mode": "Rigid", "params": [1, 2]}}}
    save_gui_prefs(prefs)

    gesto = pacotes.gesto_da_pagina("*", "criar-efeito")
    assert gesto is not None
    gesto(_contexto(pacotes, "Jogo X"),
          {"feature": feature, "nome": " Meu pulso ", "base": "Pulso", "parametros": {"ritmo": 3}},
          _Ponte())

    guardado = load_gui_prefs()
    assert guardado[CHAVES[feature]] == {
        "Meu pulso": {"nome": "Meu pulso", "base": "Pulso", "parametros": {"ritmo": 3}}}
    assert guardado["advanced_editor"] is True, "apagou as outras preferências"
    assert guardado["gatilhos_meus_efeitos"] == {
        "Recuo": {"left": {"mode": "Rigid", "params": [1, 2]}}}, "mexeu na chave dos gatilhos"
    assert meus_efeitos.meus_efeitos(feature) == {
        "Meu pulso": {"nome": "Meu pulso", "base": "Pulso", "parametros": {"ritmo": 3}}}
    for outra in set(CHAVES) - {feature, "gatilhos"}:
        assert meus_efeitos.meus_efeitos(outra) == {}, f"{feature} vazou para {outra}"


def test_criar_efeito_recusa_o_que_nao_e_efeito() -> None:
    from hefesto_dualsense4unix.interface.pacotes import meus_efeitos

    for feature, nome, base, parametros in (
            ("gatilhos", "x", "y", {}), ("luz", "", "y", {}), ("luz", "x", "", {}),
            ("luz", "x" * 41, "y", {}), ("luz", "x", "y", "texto"),
            ("luz", "x", "y", {"a": {"b": 1}}), ("outra", "x", "y", {})):
        with pytest.raises(ValueError):
            meus_efeitos.criar_efeito(feature, nome, base, parametros)
    assert meus_efeitos.meus_efeitos("luz") == {}


def test_a_03_le_a_biblioteca_pelo_dono_novo() -> None:
    """`a03.meus_efeitos()` e a gravação da 03 passam pelo mesmo dono, na chave que já existia."""
    # A decisão: D-1410-OS-EFEITOS-DELA-TEM-UM-DONO.
    from hefesto_dualsense4unix.interface.pacotes import a03_gatilhos, meus_efeitos

    meus_efeitos.guardar_meus_efeitos(
        {"Recuo": {"left": {"mode": "Rigid", "params": [1]}}}, "gatilhos")
    assert meus_efeitos.meus_efeitos("gatilhos") == a03_gatilhos.meus_efeitos()
    assert a03_gatilhos.meus_efeitos()["Recuo"]["left"]["mode"] == "Rigid"
    fonte = (INTERFACE / "pacotes/a03_gatilhos.py").read_text(encoding="utf-8")
    assert "load_gui_prefs" not in fonte, "a 03 voltou a ter a sua própria caixa de efeitos"
