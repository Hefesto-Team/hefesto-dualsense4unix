"""O Tema claro aceita o CSS de quem usa (O-TEMA-ACEITA-O-CSS-DE-QUEM-USA-01).

Medido em 22/10/2026: a folha do tema só aceita ``:root{...}`` de cores com contraste, e quem
queria mexer no layout não tinha onde. Agora a extensão de tema declara uma opção ``css`` (desligada
de início), a pessoa escreve o ``<dados>/<id>/meu.css`` e a janela o põe POR CIMA do tema, pelo
mesmo vigia, sem reabrir. A régua é de segurança: nada busca arquivo nem endereço, nada escapa, o
teto é 16 KB, e o recusado diz a linha. O WebKit só deixa a folha de usuário vencer a da página com
``!important``, e é o ``meu_css.aplicar`` que o põe.

Tudo em lugares de mentira no ``tmp_path``; a sonda do WebKit abre uma ``PonteDaTela`` de verdade.

MORDIDAS (22/10/2026, executadas sobre a cura e devolvidas):
- o ``!important`` não posto (``marca`` vazia) reprova a sonda e ``test_toda_declaracao_ganha_...``;
- a régua de ``url(`` arrancada reprova ``test_o_que_busca_ou_escapa_nao_se_aplica_e_diz_a_linha``;
- o ``meu.css`` fora de ``arquivos_de_opcoes_dos_temas`` reprova ``test_o_vigia_olha_o_meu_css...``;
- a folha de quem usa fora do ``_por_as_folhas`` reprova a sonda;
- o ``tema_da_casa`` sem olhar a opção ``css`` reprova ``test_a_opcao_desligada_tira_o_css...``.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador, meu_css, opcoes, tema
from hefesto_dualsense4unix.mods.manifesto import Manifesto

TEMA_CLARO = (":root{--app-bg:#eef0f5;--panel:#ffffff;--elevated:#f5f6fa;--fg:#1c1e29;"
              "--texto-suave:#383c4c;--texto-mudo:#545a70;--comment:#4a5486;"
              "--fundo-da-pagina:#dde1ea;--green:#1d7a3c;--cyan:#006d85;--purple:#6a3dc2;"
              "--orange:#a35200;--pink:#ad2f6c;--red:#c01f2e;--yellow:#7a6400}")
OPCAO_DO_CSS = {"id": "meu_css", "rotulo": "Usar o meu CSS", "tipo": "css",
                "padrao": False}  # (noqa-acento)
BASE = {"id": "tema-x", "nome": "Tema X", "api": ">=2,<3", "licenca": "MIT",
        "versao": "1.0.0",  # (noqa-acento)
        "tipos": ["tema"], "permissoes": ["tema"], "tema": {"arquivo": "tema.css"},  # (noqa-acento)
        "opcoes": [OPCAO_DO_CSS]}  # (noqa-acento)


def _lugares(raiz: Path) -> instalador.Lugares:
    return instalador.Lugares(codigo=raiz / "codigo", dados=raiz / "dados",  # (noqa-acento)
                              registro=raiz / "mods.json", estado=raiz / "estado.json")


def _instalada(lg: instalador.Lugares, mod_id: str = "tema-x", *, com_opcao: bool = True,
               ligada: bool = True, permissoes: tuple[str, ...] = ("tema",),
               ligada_em: str = "2026-10-22T10:00:00") -> None:
    pasta = lg.codigo / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "tema.css").write_text(TEMA_CLARO, encoding="utf-8")
    manifesto = {**BASE, "id": mod_id, "nome": f"Tema {mod_id}",
                 "opcoes": [OPCAO_DO_CSS] if com_opcao else []}  # (noqa-acento)
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    registro = instalador.ler_registro(lg.registro)
    registro[mod_id] = instalador.Entrada(
        id=mod_id, nome=f"Tema {mod_id}", versao="1.0.0", origem="local", endereco=str(pasta),
        permissoes_aceitas=list(permissoes), ligada=ligada, ligada_em=ligada_em)
    instalador.gravar_registro(lg.registro, registro)


def _escrever(lg: instalador.Lugares, texto: str, mod_id: str = "tema-x") -> Path:
    alvo = meu_css.caminho(mod_id, lg)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(texto, encoding="utf-8")
    return alvo


def _ligar_a_opcao(lg: instalador.Lugares, valor: bool = True, mod_id: str = "tema-x") -> None:
    opcoes.guardar(instalador.manifesto_instalado(mod_id, lugares=lg), "meu_css", valor, lg)


@pytest.fixture
def lg(tmp_path: Path) -> instalador.Lugares:
    return _lugares(tmp_path)


# --- a folha: o que entra, e como ---------------------------------------------------------


def test_toda_declaracao_ganha_o_important_para_vencer_a_pagina() -> None:
    assert meu_css.aplicar(".a{color:red}") == ".a{color:red !important;}"
    assert meu_css.aplicar(".a{color:red !important;margin:0}") == (
        ".a{color:red !important;margin:0 !important;}")
    assert meu_css.aplicar("@media (min-width:600px){.a{width:10px}}") == (
        "@media (min-width:600px){.a{width:10px !important;}}")
    assert meu_css.aplicar(".a{color:red;&:hover{color:blue}}") == (
        ".a{color:red !important;&:hover{color:blue !important;}}")


def test_os_quadros_da_animacao_ficam_sem_important() -> None:
    """O ``!important`` num quadro de ``@keyframes`` o invalida: o quadro sai como veio."""
    saida = meu_css.aplicar("@keyframes gira{from{opacity:0}to{opacity:1}}.a{animation:gira 1s}")
    assert "@keyframes gira{from{opacity:0;}to{opacity:1;}}" in saida
    assert ".a{animation:gira 1s !important;}" in saida


def test_vazio_e_so_comentario_sao_folha_vazia_e_nao_recusa() -> None:
    assert meu_css.aplicar("") == ""
    assert meu_css.aplicar("/* só um comentário */\n\n") == ""
    assert meu_css.aplicar(meu_css.EXEMPLO) == "", "o exemplo comentado precisa nascer inerte"


def test_a_cadeia_com_chave_e_ponto_e_virgula_nao_quebra_a_regra() -> None:
    assert meu_css.aplicar('.a::after{content:"a;b}"}') == '.a::after{content:"a;b" !important;}' \
        or meu_css.aplicar('.a::after{content:"a;b}"}') == '.a::after{content:"a;b}" !important;}'


@pytest.mark.parametrize("texto, linha, trecho", [
    ("\n\n.a{background:url(x.png)}", 3, "url()"),
    (".a{color:red}\n@import 'x.css';", 2, "@import"),
    (".a{content:'\\41'}", 1, "barra invertida"),
    (".a{content:'<'}", 1, "«<»"),
    (".a{width:expression(1)}", 1, "expression()"),
    (".a{background:image-set(x 1x)}", 1, "função de imagem"),
    ('.a{content:"/*";background:url(//x)}', 1, "url()"),
    ("\n.a{color:red", 2, "chave que nunca fecha"),
    (".a{color:red}\n}", 2, "chave que fecha sem ter aberto"),
    (".a{b}", 1, "não é uma declaração"),
    ("@font-face{font-family:x}", 1, "@font-face"),
    ("@charset 'utf-8';", 1, "fora de uma regra"),
])
def test_o_que_busca_ou_escapa_nao_se_aplica_e_diz_a_linha(texto: str, linha: int,
                                                           trecho: str) -> None:
    with pytest.raises(meu_css.CssRecusadoError) as achado:
        meu_css.aplicar(texto)
    frase = achado.value.frase
    assert frase.startswith("O seu CSS não foi aplicado: a linha "), frase
    assert f"a linha {linha} " in frase and trecho in frase, frase


def test_o_comentario_nao_esconde_nem_acusa() -> None:
    assert meu_css.aplicar("/* url(x) e @import */ .a{color:red}") == ".a{color:red !important;}"
    with pytest.raises(meu_css.CssRecusadoError, match="linha 3"):
        meu_css.aplicar("/* a\nb */\n.a{background:url(x)}")


def test_passar_de_16_kb_recusa_sem_ler() -> None:
    grande = ".a{color:red}\n" * 1200
    assert len(grande.encode()) > meu_css.TAMANHO_MAXIMO
    with pytest.raises(meu_css.CssRecusadoError, match="16 KB"):
        meu_css.aplicar(grande)


# --- o arquivo ----------------------------------------------------------------------------


def test_garantir_cria_o_exemplo_uma_vez_e_nunca_reescreve(lg: instalador.Lugares) -> None:
    alvo = meu_css.garantir("tema-x", lg)
    assert alvo == lg.dados / "tema-x" / "meu.css"
    assert alvo.read_text(encoding="utf-8") == meu_css.EXEMPLO
    alvo.write_text(".a{color:red}", encoding="utf-8")
    assert meu_css.garantir("tema-x", lg).read_text(encoding="utf-8") == ".a{color:red}"


def test_ler_diz_a_folha_ou_a_recusa_e_nunca_escreve(lg: instalador.Lugares) -> None:
    assert meu_css.ler("tema-x", lg) == meu_css.FolhaDeQuemUsa()
    assert not (lg.dados / "tema-x").exists(), "ler criou a pasta"
    _escrever(lg, ".a{color:red}")
    assert meu_css.ler("tema-x", lg).folha == ".a{color:red !important;}"
    _escrever(lg, "\n.a{background:url(x)}")
    ruim = meu_css.ler("tema-x", lg)
    assert ruim.folha == "" and "linha 2" in ruim.recusa
    _escrever(lg, "x" * (meu_css.TAMANHO_MAXIMO + 1))
    assert "16 KB" in meu_css.ler("tema-x", lg).recusa


def test_ler_nao_abre_o_que_nao_e_arquivo_comum(lg: instalador.Lugares) -> None:
    alvo = meu_css.caminho("tema-x", lg)
    alvo.parent.mkdir(parents=True)
    os.mkfifo(alvo)
    assert "arquivo comum" in meu_css.ler("tema-x", lg).recusa


def test_ler_diz_quando_nao_e_utf8(lg: instalador.Lugares) -> None:
    alvo = _escrever(lg, "")
    alvo.write_bytes(b"\xff\xfe.a{color:red}")
    assert "não pôde ser lido" in meu_css.ler("tema-x", lg).recusa


# --- o manifesto e a opção ----------------------------------------------------------------


def test_a_opcao_css_so_cabe_em_tema_e_so_uma() -> None:
    assert Manifesto.model_validate(BASE).opcao_do_css is not None
    sem_tema = {**BASE, "tipos": ["processo"], "tema": {}, "permissoes": [],  # (noqa-acento)
                "processo": {"executar": ["python3", "m.py"]}}
    with pytest.raises(ValueError, match="css"):
        Manifesto.model_validate(sem_tema)
    duas = {**BASE, "opcoes": [OPCAO_DO_CSS,  # (noqa-acento)
                               {**OPCAO_DO_CSS, "id": "outro"}]}
    with pytest.raises(ValueError, match="css"):
        Manifesto.model_validate(duas)


def test_a_opcao_css_nasce_desligada_e_so_aceita_ligado_ou_desligado(
        lg: instalador.Lugares) -> None:
    _instalada(lg)
    manifesto = instalador.manifesto_instalado("tema-x", lugares=lg)
    assert opcoes.ler(manifesto, lg)["meu_css"] is False
    with pytest.raises(instalador.InstalacaoRecusadaError, match="ligado ou desligado"):
        opcoes.guardar(manifesto, "meu_css", "talvez", lg)


# --- o tema da casa -----------------------------------------------------------------------


def test_a_opcao_desligada_tira_o_css_e_ligada_o_poe(lg: instalador.Lugares) -> None:
    _instalada(lg)
    _escrever(lg, ".quadro{border-radius:2px}")
    assert tema.tema_da_casa(lg).css == "", "o CSS valeu com a opção desligada"
    _ligar_a_opcao(lg)
    casa = tema.tema_da_casa(lg)
    assert casa.css == ".quadro{border-radius:2px !important;}" and casa.css_de == "tema-x"
    assert casa.folha and casa.recusa_do_css == ""
    _ligar_a_opcao(lg, False)
    assert tema.tema_da_casa(lg).css == ""


def test_desligar_a_extensao_tira_o_css_na_hora(lg: instalador.Lugares) -> None:
    _instalada(lg)
    _escrever(lg, ".a{color:red}")
    _ligar_a_opcao(lg)
    assert tema.tema_da_casa(lg).css
    instalador.desligar("tema-x", lugares=lg)
    assert tema.tema_da_casa(lg).css == ""


def test_sem_a_permissao_tema_nao_ha_css(lg: instalador.Lugares) -> None:
    _instalada(lg, permissoes=())
    _escrever(lg, ".a{color:red}")
    _ligar_a_opcao(lg)
    assert tema.tema_da_casa(lg).css == ""


def test_o_css_ruim_nao_se_aplica_e_a_aba_diz_a_linha(lg: instalador.Lugares) -> None:
    _instalada(lg)
    _escrever(lg, ".a{color:red}\n.b{background:url(x)}")
    _ligar_a_opcao(lg)
    casa = tema.tema_da_casa(lg)
    assert casa.css == "" and casa.folha, "a recusa derrubou o tema ou aplicou o ruim"
    assert casa.recusa_do_css.startswith("«Tema tema-x»: O seu CSS não foi aplicado: a linha 2")
    manifesto = instalador.manifesto_instalado("tema-x", lugares=lg)
    assert "a linha 2" in tema.css_da_extensao(manifesto, lg).recusa


def test_a_ligada_por_ultimo_vence_o_css(lg: instalador.Lugares) -> None:
    _instalada(lg, "tema-a", ligada_em="2026-10-22T09:00:00")
    _instalada(lg, "tema-b", ligada_em="2026-10-22T11:00:00")
    for mod_id, cor in (("tema-a", "red"), ("tema-b", "blue")):
        _escrever(lg, f".a{{color:{cor}}}", mod_id)
        _ligar_a_opcao(lg, mod_id=mod_id)
    assert tema.tema_da_casa(lg).css == ".a{color:blue !important;}"


def test_o_vigia_olha_o_meu_css_so_de_quem_aceita(lg: instalador.Lugares) -> None:
    _instalada(lg, "com-css")
    _instalada(lg, "sem-css", com_opcao=False)
    arquivos = tema.arquivos_de_opcoes_dos_temas(lg)
    assert meu_css.caminho("com-css", lg) in arquivos
    assert meu_css.caminho("sem-css", lg) not in arquivos
    assert opcoes.caminho("sem-css", lg) in arquivos


def test_o_meu_css_sobrevive_a_instalar_de_novo(lg: instalador.Lugares, tmp_path: Path) -> None:
    pasta = tmp_path / "fonte" / "tema-y"
    pasta.mkdir(parents=True)
    (pasta / "tema.css").write_text(TEMA_CLARO, encoding="utf-8")
    manifesto = {**BASE, "id": "tema-y", "nome": "Tema Y"}
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    instalador.instalar(str(pasta), lugares=lg)
    meu = _escrever(lg, ".a{color:red}", "tema-y")
    manifesto["versao"] = "1.0.1"  # (noqa-acento)
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    instalador.instalar(str(pasta), lugares=lg)
    assert meu.read_text(encoding="utf-8") == ".a{color:red}", "a atualização apagou o meu.css"


# --- a janela de configurar e o gesto -----------------------------------------------------

INTERFACE = (pathlib.Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
             / "interface")


def _a07() -> Any:
    sys.path.insert(0, str(INTERFACE))
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


class _Ponte:
    escolher_arquivo = None


@pytest.fixture
def lar(lg: instalador.Lugares, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(instalador.Lugares, "do_xdg", classmethod(lambda cls: lg))
    a07 = _a07()
    monkeypatch.setattr(a07.VIGIA, "_disparar", lambda: None)
    a07.REGISTRO.esquecer()
    a07._MEXIDA.limpar()
    a07._ESCOLHA.limpar()
    yield lg
    a07.REGISTRO.esquecer()
    a07._MEXIDA.limpar()
    a07._ESCOLHA.limpar()


@pytest.fixture
def ctx() -> Any:
    sys.path.insert(0, str(INTERFACE))
    import pacotes

    return pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})


def test_a_janela_traz_o_botao_a_chave_e_a_nota_da_recusa(lar: Any, ctx: Any) -> None:
    a07 = _a07()
    _instalada(lar)
    janela = a07.configurar_modificacao(ctx, {"v": "tema-x"}, _Ponte())["blocos"]["#mod-janela"]
    assert "Usar o meu CSS" in janela and "Editar o meu CSS" in janela
    assert 'data-gesto="editar-o-css-da-modificacao" data-v="tema-x:meu_css"' in janela
    assert "não foi aplicado" not in janela
    _escrever(lar, "\n.a{background:url(x)}")
    _ligar_a_opcao(lar)
    a07.REGISTRO.esquecer()
    outra = a07.configurar_modificacao(ctx, {"v": "tema-x"}, _Ponte())["blocos"]["#mod-janela"]
    assert "O seu CSS não foi aplicado: a linha 2" in outra


def test_o_botao_cria_o_arquivo_com_o_exemplo_e_pede_o_editor(
        lar: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    a07 = _a07()
    _instalada(lar)
    abertos: list[Path] = []
    monkeypatch.setattr(a07, "_abrir_no_editor", abertos.append)
    a07.editar_o_css_da_modificacao(ctx, {"v": "tema-x:meu_css"}, _Ponte())
    alvo = meu_css.caminho("tema-x", lar)
    assert abertos == [alvo] and alvo.read_text(encoding="utf-8") == meu_css.EXEMPLO


def test_o_botao_recusa_extensao_sem_a_opcao_e_nao_cria_nada(
        lar: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    a07 = _a07()
    _instalada(lar, com_opcao=False)
    monkeypatch.setattr(a07, "_abrir_no_editor", lambda alvo: pytest.fail("abriu o editor"))
    with pytest.raises(RuntimeError, match="não aceita o CSS"):
        a07.editar_o_css_da_modificacao(ctx, {"v": "tema-x:meu_css"}, _Ponte())
    assert not meu_css.caminho("tema-x", lar).exists()


def test_a_chave_do_css_liga_e_desliga_pelo_guardar(lar: Any, ctx: Any) -> None:
    a07 = _a07()
    _instalada(lar)
    a07.configurar_modificacao(ctx, {"v": "tema-x"}, _Ponte())
    a07.guardar_opcao_da_modificacao(ctx, {"v": "tema-x:meu_css", "evento": "click"}, _Ponte())
    a07.guardar_modificacao(ctx, {"v": "tema-x"}, _Ponte())
    manifesto = instalador.manifesto_instalado("tema-x", lugares=lar)
    assert opcoes.ler(manifesto, lar)["meu_css"] is True


# --- a página: o que o WebKit pinta -------------------------------------------------------

_SONDA = r"""
import json
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.interface.janela import PonteDaTela
from hefesto_dualsense4unix.mods import meu_css

TEMA = ":root{--cor:#111111 !important;}"
MEU = meu_css.aplicar(":root{--cor:#222222} #caixa{width:200px}")
PAGINA = ("<html><head><style>:root{--cor:#000000}#caixa{width:100px;height:10px;"
          "background:var(--cor)}</style></head><body><div id='caixa'></div>"
          "<script>window.__marca = Math.random();</script></body></html>")
ponte = PonteDaTela(folha=None, tema_de_cores=TEMA, meu_css=MEU)
janela = Gtk.OffscreenWindow()
janela.set_default_size(400, 200)
janela.add(ponte.view)
janela.show_all()
ponte.view.load_html(PAGINA, "file:///sonda/")

def girar(segundos):
    fim = GLib.get_monotonic_time() + int(segundos * 1e6)
    while GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)

def ler():
    caixa = {}
    ponte.perguntar(
        "JSON.stringify([document.getElementById('caixa').offsetWidth,"
        "getComputedStyle(document.getElementById('caixa')).backgroundColor, window.__marca])",
        lambda valor, erro: caixa.update(valor=valor))
    fim = GLib.get_monotonic_time() + 5_000_000
    while "valor" not in caixa and GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)
    return json.loads(caixa.get("valor") or "[null, null, null]")

def esperar(largura):
    for _ in range(40):
        lido = ler()
        if lido[0] == largura:
            return lido
        girar(0.05)
    return lido

girar(1.0)
saida = {"com": esperar(200)}
ponte.trocar_o_tema(TEMA, "")
saida["sem"] = esperar(100)
ponte.trocar_o_tema(TEMA, MEU)
saida["volta"] = esperar(200)
ponte.trocar_o_tema("")
saida["so_o_meu"] = esperar(200)
print(json.dumps(saida))
"""


@pytest.fixture(scope="module")
def pintura() -> dict[str, list[Any]]:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a PonteDaTela, que carrega o GTK")
    filho = subprocess.run([sys.executable, "-c", _SONDA], env=dict(
        os.environ, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True, timeout=180)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


def test_o_css_de_quem_usa_vence_a_pagina_e_o_tema_sem_recarregar(
        pintura: dict[str, list[Any]]) -> None:
    assert pintura["com"][0] == 200, f"o layout da pessoa não venceu a página: {pintura}"
    assert pintura["com"][1] == "rgb(34, 34, 34)", f"o CSS não veio depois do tema: {pintura}"
    assert pintura["sem"][0] == 100 and pintura["sem"][1] == "rgb(17, 17, 17)", pintura
    assert pintura["volta"][0] == 200 and pintura["so_o_meu"][0] == 200, pintura
    marcas = {pintura[k][2] for k in pintura}
    assert len(marcas) == 1 and None not in marcas, f"a página recarregou: {pintura}"
