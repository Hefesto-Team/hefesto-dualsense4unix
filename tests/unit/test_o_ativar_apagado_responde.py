"""O Ativar apagado da aba Perfis responde ao clique (D-09S-BOTAO-SEM-TRABALHO na aba 10).

A-ABA-ATIVAR-TEM-REGUA-QUE-COBRA-O-BOTAO-APAGADO-QUE-RESPONDE-01. O Ativar nasce do mesmo
`monta.botao_cinza` dos botões da aba 09 e acende o cinza com a recusa do serviço que não subiu
(D-2210-UM-CLIQUE-RELIGA-E-TROCA); um clique nele tenta de novo. A regra é a da 09: apagado e
ainda responde, porque `disabled` mataria o clique e tiraria o botão da navegação pelo controle.

Três metades, como na 09:

1. o DESENHO: o Ativar leva `data-hef-classe="apagado"`, `data-hef-atributo="aria-disabled"` e o
   `data-hef-gesto`, e nunca `disabled`;
2. o PACOTE e o desenho falam do mesmo campo;
3. a TELA VIVA, no WebKit do piloto, com o desenho de hoje: a razão acende o cinza e o
   `aria-disabled`, o meio do botão apagado recebe o clique, o clique chega ao gesto e a recusa
   pisca no botão; a razão vazia apaga o cinza de volta.

AS MORDIDAS (executadas em 02/11/2026):

* `disabled` no `extra` do `ATIVAR` de `aba10.py`, com o desenho regerado: a metade do desenho
  reprova, e a viva também (o clique não chega ao gesto);
* `data-hef-atributo="aria-disabled"` fora do `monta.botao_cinza`, com o desenho regerado: a
  metade do desenho reprova e a viva lê o `aria-disabled` ausente;
* `pointer-events:none` no `.btn.apagado` do desenho: o meio do botão deixa de ser o botão, e a
  metade do clique reprova.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.interface import monta as _monta
from hefesto_dualsense4unix.interface import onde as _onde
from hefesto_dualsense4unix.interface.pacotes import a10_perfis as a10

PAGINA = "10-perfis.html"
GESTO = "ativar"
ENSAIO = _onde.pagina(PAGINA)
RAZAO = a10.SERVICO_NAO_LIGOU


def _o_ativar() -> str:
    achados = re.findall(rf'<button[^>]*data-hef-gesto="{GESTO}"[^>]*>',
                         ENSAIO.read_text(encoding="utf-8"))
    assert len(achados) == 1, f"o desenho tem {len(achados)} botões Ativar: {achados}"
    return str(achados[0])


class TestODesenho:
    """A peça inteira no Ativar do desenho de hoje."""

    def test_o_ativar_e_a_peca_do_cinza(self) -> None:
        """D-09S-BOTAO-SEM-TRABALHO na 10: o Ativar veste o `aria-disabled` e leva o gesto."""
        botao = _o_ativar()
        for exigido in ('data-hef-alvo="classe"', 'data-hef-classe="apagado"',
                        'data-hef-atributo="aria-disabled"', 'data-hef-razao="sim"',
                        f'data-campo="{a10.CAMPO_DA_RAZAO_DO_ATIVAR}"'):
            assert exigido in botao, f"o Ativar não tem {exigido}: {botao}"

    def test_o_ativar_nunca_emite_disabled(self) -> None:
        """D-09S-BOTAO-SEM-TRABALHO na 10: apagado e ainda responde; `disabled` mataria o clique."""
        botao = _o_ativar()
        solto = re.search(r"(?<![-\w])disabled(?=[\s=>])", botao)
        assert not solto, f"o Ativar emite `disabled` e o clique morre: {botao}"

    def test_a_peca_nunca_emite_disabled(self) -> None:
        """D-09S-BOTAO-SEM-TRABALHO na origem: `monta.botao_cinza` nunca emite `disabled`."""
        for razao in ("", RAZAO):
            botao = _monta.botao_cinza("Ativar", "regua.campo", tom="verde", razao=razao)
            assert 'data-hef-atributo="aria-disabled"' in botao, botao
            assert not re.search(r"(?<![-\w])disabled(?=[\s=>])", botao), botao


class TestOPacote:
    """O campo que o pacote escreve é o que o desenho endereça."""

    def test_o_pacote_escreve_o_campo_do_ativar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.interface.pacotes import Contexto, normalizar

        monkeypatch.setattr(a10, "_RECUSA_DO_ATIVAR", [RAZAO])
        ctx = Contexto(state={}, mesa=[], conectados=[], estados={})
        mesa = normalizar(dict(a10.pacote(ctx)))["mesa"]
        assert mesa.get(a10.CAMPO_DA_RAZAO_DO_ATIVAR) == RAZAO, sorted(mesa)


LER_O_ATIVAR = r"""
(function(){
  const b = document.querySelector('[data-hef-gesto="ativar"]');
  if(!b) return JSON.stringify(null);
  return JSON.stringify({
    apagado: b.classList.contains('apagado'),
    aria: b.getAttribute('aria-disabled'),
    desligado: !!b.disabled,
    razao: b.getAttribute('data-dica'),
    recusou: b.classList.contains('hef-recusou'),
  });
})()
"""

CLICAR_NO_MEIO = r"""
(function(){
  const b = document.querySelector('[data-hef-gesto="ativar"]');
  if(!b) return JSON.stringify({achei: false});
  const r = b.getBoundingClientRect();
  const no_meio = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  const alcanca = !!no_meio && (no_meio === b || b.contains(no_meio));
  if(alcanca) no_meio.click();
  return JSON.stringify({achei: true, alcanca: alcanca,
                         quem: no_meio ? no_meio.tagName + '.' + no_meio.className : null});
})()
"""


@pytest.fixture(scope="module")
def na_tela() -> dict[str, Any]:
    """Abre o desenho de hoje da 10 no motor do produto, oculto, e clica no Ativar apagado."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica: o WebKit não abre")

    import argparse
    import tempfile
    import time as _time

    import hefesto_vivo as hv

    berco = pathlib.Path(tempfile.mkdtemp(prefix="a10-ativar-"))
    shutil.copytree(_onde.PUBLICADO, berco / _onde.PUBLICADO.name, dirs_exist_ok=True)
    shutil.copy2(ENSAIO, berco / _onde.PUBLICADO.name / PAGINA)

    chave = (PAGINA, GESTO)
    guardado = (hv.onde.PUBLICADO, hv.mesa_viva.estado_do_daemon,
                hv.pacotes.PACOTES.get(PAGINA), hv.pacotes.GESTOS.get(chave))
    hv.onde.PUBLICADO = berco / _onde.PUBLICADO.name
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: {"active_profile": "regua"}

    carga = {"o_que": {a10.CAMPO_DA_RAZAO_DO_ATIVAR: RAZAO}}
    hv.pacotes.PACOTES[PAGINA] = lambda ctx: dict(carga["o_que"])

    chegou: list[str] = []

    def recusa_como_o_produto(ctx: Any, o: dict[str, Any], p: Any) -> dict[str, Any]:
        chegou.append(str(o.get("gesto") or ""))
        raise RuntimeError(RAZAO)

    hv.pacotes.GESTOS[chave] = recusa_como_o_produto

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre=PAGINA, prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, Any] = {}

    def ler(rotulo: str) -> Any:
        def _leu(valor: Any, erro: Any) -> None:
            fora[rotulo] = f"ERRO {erro}" if erro is not None else json.loads(str(valor))
        return _leu

    def pintados() -> int:
        return piloto.tiques.get(PAGINA, 0) if piloto.pagina == PAGINA else 0

    def com_a_razao() -> bool:
        if pintados() < 1:
            return True
        piloto.ponte.perguntar(LER_O_ATIVAR, ler("com-razao"))
        GLib.timeout_add(600, clicar)
        return False

    def clicar() -> bool:
        piloto.ponte.perguntar(CLICAR_NO_MEIO, ler("clique"))
        GLib.timeout_add(500, depois_do_clique)
        return False

    def depois_do_clique() -> bool:
        fora["chegou-ao-gesto"] = list(chegou)
        piloto.ponte.perguntar(LER_O_ATIVAR, ler("depois-do-clique"))
        GLib.timeout_add(1700, sem_a_razao)
        return False

    def sem_a_razao() -> bool:
        carga["o_que"] = {a10.CAMPO_DA_RAZAO_DO_ATIVAR: ""}
        antes = pintados()
        GLib.timeout_add(100, lambda: leu_sem_a_razao(antes))
        return False

    def leu_sem_a_razao(antes: int) -> bool:
        if pintados() < antes + 2:
            return True
        piloto.ponte.perguntar(LER_O_ATIVAR, ler("sem-razao"))
        GLib.timeout_add(400, fim)
        return False

    def fim() -> bool:
        fora["fim"] = True
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(PAGINA))
    GLib.timeout_add(100, com_a_razao)
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        limite = _time.monotonic() + 60.0
        while "fim" not in fora and _time.monotonic() < limite:
            Gtk.main()
    finally:
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.onde.PUBLICADO, hv.mesa_viva.estado_do_daemon,
         pacote_antigo, gesto_antigo) = guardado
        if pacote_antigo is not None:
            hv.pacotes.PACOTES[PAGINA] = pacote_antigo
        if gesto_antigo is not None:
            hv.pacotes.GESTOS[chave] = gesto_antigo
        else:
            hv.pacotes.GESTOS.pop(chave, None)
        shutil.rmtree(berco, ignore_errors=True)
    if "sem-razao" not in fora:
        pytest.fail(f"o roteiro não chegou ao fim: {sorted(fora)}")
    return fora


class TestNaTelaViva:
    """O Ativar apagado medido no motor que o usa."""

    def test_a_razao_acende_o_cinza_e_veste_o_aria(self, na_tela: dict[str, Any]) -> None:
        """D-09S-BOTAO-SEM-TRABALHO na 10: a recusa pinta o cinza, o `aria-disabled` e a dica."""
        visto = na_tela["com-razao"]
        assert visto is not None, "o Ativar sumiu da página"
        assert visto["apagado"] is True, visto
        assert visto["aria"] == "true", visto
        assert visto["desligado"] is False, visto
        assert visto["razao"] == RAZAO, visto

    def test_o_ativar_apagado_ainda_responde_ao_clique(self, na_tela: dict[str, Any]) -> None:
        """D-09S-BOTAO-SEM-TRABALHO na 10: o meio do Ativar apagado chega ao gesto."""
        visto = na_tela["clique"]
        assert visto["achei"] is True, "o Ativar sumiu da página"
        assert visto["alcanca"] is True, (
            f"o meio do Ativar apagado é {visto['quem']!r}: o clique não chega a ele")
        assert na_tela["chegou-ao-gesto"] == [GESTO], na_tela["chegou-ao-gesto"]
        depois = na_tela["depois-do-clique"]
        assert depois and depois["recusou"] is True, (
            f"o gesto recusou e o Ativar apagado não piscou a recusa: {depois}")

    def test_a_razao_vazia_apaga_o_cinza_de_volta(self, na_tela: dict[str, Any]) -> None:
        """D-09S-BOTAO-SEM-TRABALHO na 10: o cinza é estado; sem razão o Ativar volta aceso."""
        visto = na_tela["sem-razao"]
        assert visto["apagado"] is False, visto
        assert visto["aria"] == "false", visto
        assert visto["razao"] is None, visto
