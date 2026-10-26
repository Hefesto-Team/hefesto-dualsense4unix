"""O tema de cores entra pela folha de usuário — O-TEMA-DE-CORES-ENTRA-PELA-FOLHA-DE-USUARIO-01.

Uma modificação troca as cores da interface por um bloco ``:root{…}`` de tokens, que a janela põe
como segunda folha de usuário, depois da da casa. O tema não esconde, não busca nada fora, não
troca o plástico e não deixa o texto abaixo de 4,5:1.

MORDIDAS, uma por vez (cada uma reprova pelo menos um teste daqui): ``COR_DO_TIPO`` de volta em
hex (a régua do token); o ``.radio`` voltando a copiar os tokens da casa (o tema não alcança a
régua); os tokens da régua de volta ao escopo ``.radio .espectro``; a janela sem a segunda folha;
o contraste sem conferir; o ``url()`` aceito.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods import tema as tm

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/08-conexoes.html"
TOPO = RAIZ / "src/hefesto_dualsense4unix/interface/topo.html"

TEMA_VALIDO = ":root{ --c-teclado:#00e5ff; --sala-fone:#00c853; --panel:#1e1f29 }"


@pytest.mark.parametrize(("folha", "pedaco"), [
    (".nota{display:none}", "bloco :root"),
    (":root{display:none}", "não é um token de cor"),
    (":root{--fg:#fff} .botao{display:none}", "bloco :root"),
    (":root{--panel:url(https://exemplo.invalid/x.png)}", "url()"),
    ("@import 'https://exemplo.invalid/a.css'; :root{--fg:#fff}", "@import"),
    (":root{--fg:\\66 \\66 \\66}", "escape"),
    (":root{--cosmic-red:#ffffff}", "plástico"),
    (":root{--h-escolha:40px}", "só as cores"),
    (":root{--c-teclado:var(--red)}", "não é uma cor"),
    (":root{--c-teclado:red}", "não é uma cor"),
])
def test_o_tema_que_nao_e_so_cor_e_recusado_com_a_frase(folha: str, pedaco: str) -> None:
    with pytest.raises(tm.TemaRecusadoError) as recusa:
        tm.validar(folha)
    assert pedaco in recusa.value.frase, recusa.value.frase


def test_o_tema_de_tres_para_um_e_recusado_com_o_par_e_o_numero() -> None:
    casa = tm.tokens_da_casa(TOPO)
    alvo = next(f"#{v:02x}{v:02x}{v:02x}" for v in range(0x30, 0x100)
                if tm.contraste(f"#{v:02x}{v:02x}{v:02x}", casa["--elevated"]) >= 3.0)
    assert 3.0 <= tm.contraste(alvo, casa["--elevated"]) < 3.1
    with pytest.raises(tm.TemaRecusadoError) as recusa:
        tm.validar(f":root{{--texto-mudo:{alvo}}}", casa=casa)
    frase = recusa.value.frase
    assert "«--texto-mudo» sobre «--elevated» dá 3,0" in frase and "4,50:1" in frase, frase
    with pytest.raises(tm.TemaRecusadoError, match="sobre «--app-bg»"):
        tm.validar(":root{--app-bg:#9a9eb8}", casa=casa)
    with pytest.raises(tm.TemaRecusadoError, match="opaca"):
        tm.validar(":root{--panel:rgba(0,0,0,.5)}", casa=casa)


def test_a_casa_de_hoje_passa_na_propria_regua_e_o_tema_valido_sai_importante() -> None:
    casa = tm.tokens_da_casa(TOPO)
    assert casa == {k: v for k, v in tm.tokens_da_casa().items() if k in casa}, (
        "a página publicada e o topo da casa dizem cores diferentes")
    pintados = tm.valores_pintados(casa, {}, tm.apelidos_da_casa())
    assert pintados["--rot-campo"] == casa["--green"], "o rótulo da casa é o verde"
    assert min(tm.contraste(pintados[t], pintados[f])
               for t in tm.TEXTOS for f in tm.FUNDOS) >= tm.LIMIAR_DO_CONTRASTE
    assert min(tm.contraste(pintados[t], pintados[f])
               for t in tm.ACENTOS for f in tm.FUNDOS) >= tm.LIMIAR_DO_ACENTO
    aceito = tm.validar(TEMA_VALIDO, casa=casa)
    assert aceito.tokens == {"--c-teclado": "#00e5ff", "--sala-fone": "#00c853",
                             "--panel": "#1e1f29"}
    assert aceito.folha == (":root{--c-teclado:#00e5ff !important;--sala-fone:#00c853 "
                            "!important;--panel:#1e1f29 !important;}")
    assert not tm.PLASTICOS & tm.TOKENS_DA_CASA
    assert set(tm.tokens_da_casa(TOPO)) >= tm.PLASTICOS, "o plástico da casa mudou de nome"


CLARO_SEM_ACENTOS = (":root{--app-bg:#eef0f5;--panel:#ffffff;--elevated:#f5f6fa;--fg:#1c1e29;"
                     "--texto-suave:#383c4c;--texto-mudo:#545a70;--comment:#4a5486"
                     ";--fundo-da-pagina:#dde1ea")
ACENTOS_ESCUROS = (";--green:#1d7a3c;--cyan:#006d85;--purple:#6a3dc2;--orange:#a35200;"
                   "--pink:#ad2f6c;--red:#c01f2e;--yellow:#7a6400")


def test_o_tema_claro_sem_os_acentos_e_recusado_pelo_rotulo() -> None:
    with pytest.raises(tm.TemaRecusadoError) as recusa:
        tm.validar(CLARO_SEM_ACENTOS + "}")
    assert "«--rot-campo» sobre «--app-bg» dá 1,20:1" in recusa.value.frase, recusa.value.frase


def test_o_acento_claro_sobre_o_fundo_claro_e_recusado_com_o_piso_do_acento() -> None:
    """A prova da D-2010-O-DESTAQUE-DO-TEMA-PASSA-DE-3-PARA-1."""
    with pytest.raises(tm.TemaRecusadoError) as recusa:
        tm.validar(CLARO_SEM_ACENTOS + ";--green:#1d7a3c}")
    frase = recusa.value.frase
    assert "«--yellow» sobre «--app-bg»" in frase and "3,00:1" in frase, frase


def test_o_tema_claro_com_os_acentos_escuros_liga_e_o_rotulo_segue_o_verde() -> None:
    aceito = tm.validar(CLARO_SEM_ACENTOS + ACENTOS_ESCUROS + "}")
    assert "--rot-campo" not in aceito.tokens, "o tema não disse o rótulo"
    pintados = tm.valores_pintados(tm.tokens_da_casa(), aceito.tokens, tm.apelidos_da_casa())
    assert pintados["--rot-campo"] == "#1d7a3c", "o rótulo pinta com o verde do tema"
    assert tm.apelidos_do_root(":root{--a:var(--b);--c:#fff;--d:var( --e )}") == {
        "--a": "--b", "--d": "--e"}


def _lugares(tmp_path: Path) -> instalador.Lugares:
    return instalador.Lugares(
        codigo=tmp_path / "codigo",  # (noqa-acento)
        dados=tmp_path / "dados",
        registro=tmp_path / "mods.json", estado=tmp_path / "estado.json")


def _instalada(lg: instalador.Lugares, mod_id: str, tema: dict[str, Any], *,
               ligada: bool = True, permissoes: tuple[str, ...] = ("tema",),
               ligada_em: str = "2026-10-10T10:00:00") -> None:
    pasta = lg.codigo / mod_id
    pasta.mkdir(parents=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps({
        "id": mod_id, "nome": f"Tema {mod_id}", "versao": "1.0",  # (noqa-acento)
        "api": ">=1,<3",
        "licenca": "MIT", "tipos": ["tema"],
        "permissoes": ["tema"], "tema": tema}),  # (noqa-acento)
        encoding="utf-8")
    registro = instalador.ler_registro(lg.registro)
    registro[mod_id] = instalador.Entrada(
        id=mod_id, nome=f"Tema {mod_id}", versao="1.0", origem="local", endereco=str(pasta),
        permissoes_aceitas=list(permissoes), ligada=ligada, ligada_em=ligada_em)
    instalador.gravar_registro(lg.registro, registro)


def test_o_tema_ligado_vem_do_registro_e_so_com_a_permissao(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    assert tm.tema_da_casa(lg) == tm.TemaDaCasa(), "sem registro, sem tema"
    _instalada(lg, "azul", {"folha": TEMA_VALIDO})
    (lg.codigo / "verde").mkdir(parents=True)
    _instalada(lg, "sem-permissao", {"folha": ":root{--c-mouse:#00ff00}"}, permissoes=())
    _instalada(lg, "desligada", {"folha": ":root{--c-mouse:#00ff00}"}, ligada=False)
    agora = tm.tema_da_casa(lg)
    assert agora.de == "azul" and "--c-teclado:#00e5ff !important" in agora.folha
    assert "--c-mouse" not in agora.folha and not agora.recusa and not agora.avisos


def test_o_tema_em_arquivo_fica_dentro_da_modificacao(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _instalada(lg, "arquivo", {"arquivo": "cores/tema.css"})
    (lg.codigo / "arquivo" / "cores").mkdir()
    (lg.codigo / "arquivo" / "cores" / "tema.css").write_text(TEMA_VALIDO, encoding="utf-8")
    assert "--sala-fone:#00c853" in tm.tema_da_casa(lg).folha
    (tmp_path / "fora.css").write_text(TEMA_VALIDO, encoding="utf-8")
    with pytest.raises(tm.TemaRecusadoError, match="dentro da modificação"):
        tm.folha_do_manifesto({"arquivo": "../../fora.css"}, lg.codigo / "arquivo")
    with pytest.raises(tm.TemaRecusadoError, match="um dos dois"):
        tm.folha_do_manifesto({"arquivo": "a.css", "folha": TEMA_VALIDO}, lg.codigo / "arquivo")


def test_o_tema_reprovado_nao_liga_e_diz_o_par(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _instalada(lg, "apagado", {"folha": ":root{--texto-mudo:#3c3e4c}"})
    _instalada(lg, "antigo", {"folha": TEMA_VALIDO}, ligada_em="2026-10-09T10:00:00")
    agora = tm.tema_da_casa(lg)
    assert agora.folha == "" and agora.de == "apagado"
    assert agora.recusa.startswith("O tema de «Tema apagado» não ligou.")
    assert "«--texto-mudo» sobre «--elevated»" in agora.recusa
    assert agora.avisos == ("«Tema antigo» também tem tema, e vale o da «Tema apagado».",)


def test_o_tema_reprovado_nao_liga_na_chave_e_a_frase_diz_o_par(tmp_path: Path) -> None:
    """O-TEMA-QUE-A-REGUA-RECUSA-NAO-LIGA-NA-CHAVE-01: o «ligar» passa o tema pela régua."""
    lg = _lugares(tmp_path)
    _instalada(lg, "apagado", {"folha": ":root{--texto-mudo:#3c3e4c}"}, ligada=False,
               permissoes=())
    with pytest.raises(instalador.InstalacaoRecusadaError) as recusa:
        instalador.ligar("apagado", permissoes_vistas=["tema"], lugares=lg)
    frase = recusa.value.frase
    assert frase.startswith("O tema de «Tema apagado» não liga. O texto ficaria ilegível:"), frase
    assert "«--texto-mudo» sobre «--elevated»" in frase, frase
    assert instalador.ler_registro(lg.registro)["apagado"].ligada is False
    _instalada(lg, "azul", {"folha": TEMA_VALIDO}, ligada=False, permissoes=())
    assert instalador.ligar("azul", permissoes_vistas=["tema"], lugares=lg).ligada is True


def test_o_manifesto_que_nao_abre_vai_aos_avisos_e_o_outro_tema_liga(tmp_path: Path) -> None:
    """A modificação ligada cujo manifesto não abre não liga tema, e a frase de produto não some."""
    lg = _lugares(tmp_path)
    _instalada(lg, "quebrada", {"folha": TEMA_VALIDO}, ligada_em="2026-10-11T10:00:00")
    (lg.codigo / "quebrada" / "hefesto-mod.json").write_text("{", encoding="utf-8")
    assert tm.tema_da_casa(lg).folha == ""
    sozinha = tm.tema_da_casa(lg)
    assert len(sozinha.avisos) == 1
    assert sozinha.avisos[0].startswith("O manifesto de «Tema quebrada» não abriu:")
    _instalada(lg, "azul", {"folha": TEMA_VALIDO})
    agora = tm.tema_da_casa(lg)
    assert agora.de == "azul" and "--c-teclado:#00e5ff !important" in agora.folha
    assert agora.avisos == sozinha.avisos


from hefesto_dualsense4unix.interface import aba08
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

from tests.conftest import skip_sem_gi_real

_HEXA = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _raiz(html: str) -> dict[str, str]:
    """Os tokens de toda regra ``:root{…}`` da página, sem os comentários."""
    sem = re.sub(r"/\*.*?\*/", "", html, flags=re.S)
    saida: dict[str, str] = {}
    for corpo in re.findall(r"(?<![\w.#-]):root\s*\{([^{}]*)\}", sem):
        for decl in corpo.split(";"):
            nome, _, valor = decl.partition(":")
            if nome.strip().startswith("--"):
                saida[nome.strip()] = valor.strip()
    return saida


def test_a_cor_de_cada_tipo_e_um_token_que_a_folha_da_aba_define_na_raiz() -> None:
    raiz = _raiz(MOCKUP.read_text(encoding="utf-8"))
    for tipo, valor in a08.COR_DO_TIPO.items():
        assert not _HEXA.search(valor), f"COR_DO_TIPO[{tipo!r}] em hex: o tema não o alcança"
        assert valor == f"var(--sala-{tipo})"
        assert tm.token_permitido(f"--sala-{tipo}") and f"--sala-{tipo}" in raiz, tipo
    for tipo in a08.TIPOS_COM_COR_NA_REGUA | {"outro", "ruido"}:
        assert f"--c-{tipo}" in raiz and tm.token_permitido(f"--c-{tipo}"), tipo
        assert tm.cor(raiz[f"--c-{tipo}"]) is not None, tipo
    assert not any(_HEXA.search(str(v)) for v in a08.CATEGORIA_ACESSORIO.values())
    for tipo, valor in a08.COR_DA_FAIXA_NO_MAPA.items():
        padrao = a08.PADRAO_DA_FAIXA_NO_MAPA[tipo]
        assert valor == f"var(--mapa-{tipo},{padrao})", f"COR_DA_FAIXA_NO_MAPA[{tipo!r}]"
        assert tm.token_permitido(f"--mapa-{tipo}") and tm.cor(padrao) is not None, tipo


def test_a_secao_do_radio_herda_os_tokens_da_casa_e_a_regua_nao_os_redefine() -> None:
    css = aba08.CSS_DA_SECAO_DO_RADIO
    casa = tm.tokens_da_casa(TOPO)
    for regra in re.findall(r"\.radio(?:\s+\.espectro)?\s*\{([^{}]*)\}", css):
        nomes = {d.partition(":")[0].strip() for d in regra.split(";")}
        assert not nomes & set(casa), f"o .radio redefine {sorted(nomes & set(casa))}"
        assert not {n for n in nomes if n.startswith("--c-") and n[4:] in a08.COR_DO_TIPO}, (
            "a cor de categoria voltou ao escopo da seção")


def test_o_veu_da_vaga_mistura_o_token_sem_saber_o_hex() -> None:
    assert a08._veu("var(--sala-fone)", .5) == (
        "color-mix(in srgb, var(--sala-fone) 50%, transparent)")
    assert a08._veu("#7eb8d4", .5) == "rgba(126,184,212,0.5)"


SONDA = r"""
(function(){
  const marcado = document.getElementById('cx8-3');
  if (marcado) marcado.checked = true;
  const cor = (sel, prop) => {
    const el = document.querySelector(sel);
    return el ? getComputedStyle(el)[prop] : 'sem ' + sel;
  };
  return JSON.stringify({
    teclado: cor('.radio .ar-linha[data-tipo="teclado"] .ar-faixa i.b', 'backgroundColor'),
    fone: cor('.radio svg.ico[style*="--sala-fone"]', 'color'),
    painel: getComputedStyle(document.querySelector('.radio')).getPropertyValue('--panel').trim(),
    faixa_do_mapa: (() => {
      const fx = document.createElement('i');
      fx.setAttribute('style', '--cor-faixa:' + FAIXA_DO_MAPA
        + ';display:block;width:4px;height:4px;background:var(--cor-faixa, #000)');
      document.body.appendChild(fx);
      return getComputedStyle(fx).backgroundColor;
    })(),
    esconde_a_nota: [...document.querySelectorAll('.nota')].every(
      n => getComputedStyle(n).display === 'none'),
  });
})()
"""


def _no_webkit(tema: str | None) -> dict[str, Any]:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    from gi.repository import WebKit2

    from hefesto_dualsense4unix.interface import janela

    saiu: list[str] = []
    ponte = janela.PonteDaTela(tema_de_cores=tema)
    caixa = Gtk.OffscreenWindow()
    caixa.set_default_size(1212, 1500)
    caixa.add(ponte.view)
    caixa.show_all()

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(300, lambda: (v.evaluate_javascript(
                SONDA.replace("FAIXA_DO_MAPA", json.dumps(a08.COR_DA_FAIXA_NO_MAPA["teclado"])),
                -1, None, None, None, guardou), False)[1])

    ponte.view.connect("load-changed", carregou)
    ponte.view.load_uri(MOCKUP.as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        caixa.destroy()
    assert saiu and not saiu[0].startswith("ERRO"), saiu
    return dict(json.loads(saiu[0]))


def test_no_webkit_o_tema_troca_a_regua_a_sala_e_o_painel_e_a_folha_da_casa_continua() -> None:
    sem = _no_webkit(None)
    com = _no_webkit(tm.validar(TEMA_VALIDO.replace(" }", "; --mapa-teclado:#ff00aa }")).folha)
    assert sem["teclado"] == "rgb(255, 184, 108)", sem
    assert com["teclado"] == "rgb(0, 229, 255)", com
    assert sem["fone"] == "rgb(126, 154, 168)" and com["fone"] == "rgb(0, 200, 83)", (sem, com)
    assert sem["painel"] == "#282a36" and com["painel"] == "#1e1f29", (sem, com)
    assert sem["faixa_do_mapa"] == "rgb(255, 184, 108)", sem
    assert com["faixa_do_mapa"] == "rgb(255, 0, 170)", com
    assert sem["esconde_a_nota"] is True and com["esconde_a_nota"] is True


@skip_sem_gi_real
def test_a_janela_pede_o_tema_ligado_quando_ninguem_diz_qual(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from hefesto_dualsense4unix.interface import janela

    monkeypatch.setattr(tm, "tema_da_casa", lambda: tm.TemaDaCasa(
        recusa="O tema de «X» não ligou. O texto ficaria ilegível: «--fg» sobre «--panel» dá "
               "1,20:1, e o mínimo é 4,50:1.", avisos=("«Y» também tem tema.",)))
    assert janela.folha_do_tema() == ""
    erro = capsys.readouterr().err
    assert "«--fg» sobre «--panel» dá 1,20:1" in erro and "«Y» também tem tema." in erro
    monkeypatch.setattr(tm, "tema_da_casa", lambda: tm.TemaDaCasa(folha=":root{--fg:#fff}",
                                                                  de="x"))
    assert janela.folha_do_tema() == ":root{--fg:#fff}"
    monkeypatch.setattr(tm, "tema_da_casa", lambda: tm.TemaDaCasa(
        folha=tm.validar(TEMA_VALIDO).folha, de="x"))
    assert _no_webkit(janela.TEMA_LIGADO)["teclado"] == "rgb(0, 229, 255)"


def test_o_retratista_le_o_tema_pela_mesma_regua(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface import olhar

    def _sem_foto(*_a: Any, **_k: Any) -> int:
        raise AssertionError("o --tema com o --doc chegou a fotografar")

    monkeypatch.setattr(olhar, "_todas", _sem_foto)
    bom, ruim = tmp_path / "bom.css", tmp_path / "ruim.css"
    bom.write_text(TEMA_VALIDO, encoding="utf-8")
    ruim.write_text(":root{--fg:#30313d}", encoding="utf-8")
    assert olhar._tema_pedido(str(bom)) == tm.validar(TEMA_VALIDO).folha
    with pytest.raises(SystemExit, match="ilegível"):
        olhar._tema_pedido(str(ruim))
    with pytest.raises(SystemExit):
        olhar.main(["--todas", "--doc", "--tema", str(bom)])
