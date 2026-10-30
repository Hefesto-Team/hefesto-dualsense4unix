"""O tema por escolha, o importado, a logo, o destaque e a herança da extensão que substitui outra
(O-GERENCIADOR-DE-TEMA-E-A-EXTENSAO-DE-FABRICA-01).

Tudo com extensões FALSAS num ``tmp_path``: o mecanismo é de qualquer extensão de tema, e nenhum
nome de extensão real entra aqui.

MORDIDAS (30/10/2026, executadas sobre a cura e devolvidas):

- ``_folha_da_entrada`` sem o ramo das escolhas (a folha do pacote sempre) reprova
  ``test_a_escolha_da_cor_escolhe_a_folha``;
- a régua da logo sem conferir os bytes (``imagem`` aceitando tudo) reprova
  ``test_a_logo_que_nao_e_imagem_nao_entra`` e ``test_a_copia_da_logo_trocada_a_mao_nao_pinta``;
- o destaque sem a régua do contraste (``validar`` do destaque arrancado) reprova
  ``test_o_destaque_ilegivel_nao_liga_e_o_tema_fica``;
- o ``herda`` lido da antiga desligada (``ligadas`` ignorado) reprova
  ``test_a_antiga_desligada_nao_passa_o_que_guardava``;
- o ``_levar_o_meu_css`` arrancado reprova ``test_o_meu_css_da_antiga_vai_para_a_nova``.
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import importados, instalador, meu_css, opcoes
from hefesto_dualsense4unix.mods import tema as tm
from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, Lugares
from hefesto_dualsense4unix.mods.manifesto import Manifesto

CLARO = (":root{--app-bg:#eef0f5;--panel:#ffffff;--elevated:#f5f6fa;--fg:#1c1e29;"
         "--texto-suave:#383c4c;--texto-mudo:#545a70;--comment:#4a5486;"
         "--fundo-da-pagina:#dde1ea;--green:#1d7a3c;--cyan:#006d85;--purple:#6a3dc2;"
         "--orange:#a35200;--pink:#ad2f6c;--red:#c01f2e;--yellow:#7a6400}")
OUTRO = CLARO.replace("#eef0f5", "#f0eee5")

OPCOES = [
    {"id": "tema", "rotulo": "Tema", "tipo": "escolha",
     "escolhas": ["Escuro", "Claro", "Importado"],
     "padrao": "Escuro", "grupo": "Cores",  # (noqa-acento)
     "herda": {"cores_claras": {"true": "Claro", "false": "Escuro"}}},
    {"id": "tema_importado", "rotulo": "Arquivo do tema", "tipo": "importar", "formato": "tema",
     "grupo": "Cores", "aparece_com": {"tema": "Importado"}},
    {"id": "destaque", "rotulo": "Destaque", "tipo": "ligado", "padrao": False,  # (noqa-acento)
     "grupo": "Destaque"},
    {"id": "cor_de_destaque", "rotulo": "Cor", "tipo": "cor", "padrao": "#50fa7b",  # (noqa-acento)
     "grupo": "Destaque", "aparece_com": {"destaque": True}},
    {"id": "botoes", "rotulo": "Botões", "tipo": "escolha",
     "escolhas": ["Do sistema", "Esquerda", "Direita"], "padrao": "Do sistema",  # (noqa-acento)
     "grupo": "Janela", "herda": {"botoes_a_esquerda": {"true": "Esquerda"}}},
    {"id": "logo", "rotulo": "Logo", "tipo": "importar", "formato": "logo", "grupo": "Janela"},
    {"id": "meu_css", "rotulo": "Meu CSS", "tipo": "css", "padrao": False,  # (noqa-acento)
     "grupo": "CSS"},
]
BLOCO = {"folhas_por_escolha": {"Claro": "tema.css"}, "cor_pela_opcao": "tema",
         "importados_por_escolha": {"Importado": "tema_importado"},
         "botoes_pela_opcao": "botoes",
         "lados_por_escolha": {"Esquerda": "esquerda", "Direita": "direita"},
         "destaque_pela_opcao": "cor_de_destaque", "destaque_ligado_pela_opcao": "destaque",
         "logo_pela_opcao": "logo"}
NOVA, ANTIGA = "tema-novo", "tema-velho"


def _manifesto(mod_id: str = NOVA, **mais: Any) -> dict[str, Any]:
    return {"id": mod_id, "nome": f"Extensão {mod_id}", "versao": "2.0.0",  # (noqa-acento)
            "api": ">=2,<3", "licenca": "MIT", "tipos": ["tema"],
            "permissoes": ["tema"], "tema": BLOCO, "opcoes": OPCOES, **mais}  # (noqa-acento)


def _pasta(raiz: Path, manifesto: dict[str, Any]) -> Path:
    pasta = raiz / "fontes" / manifesto["id"] / manifesto["versao"]  # (noqa-acento)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "tema.css").write_text(CLARO, encoding="utf-8")
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return pasta


def _ligada(lg: Lugares, pasta: Path) -> Manifesto:
    resultado = instalador.instalar(str(pasta), lugares=lg)
    instalador.ligar(resultado.entrada.id, permissoes_vistas=resultado.manifesto.permissoes,
                     lugares=lg)
    return instalador.manifesto_instalado(resultado.entrada.id, lugares=lg)


@pytest.fixture
def lg(tmp_path: Path) -> Lugares:
    return Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # (noqa-acento)
                   registro=tmp_path / "mods.json", estado=tmp_path / "estado.json")


@pytest.fixture
def nova(lg: Lugares, tmp_path: Path) -> Manifesto:
    return _ligada(lg, _pasta(tmp_path, _manifesto()))


def _png(largura: int = 64, altura: int = 64) -> bytes:
    def pedaco(tipo: bytes, dados: bytes) -> bytes:
        return (struct.pack(">I", len(dados)) + tipo + dados
                + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF))
    cabeca = struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0)
    linhas = b"".join(b"\x00" + b"\x80\x40\x20" * largura for _ in range(altura))
    return (b"\x89PNG\r\n\x1a\n" + pedaco(b"IHDR", cabeca)
            + pedaco(b"IDAT", zlib.compress(linhas)) + pedaco(b"IEND", b""))


def _arquivo(tmp_path: Path, nome: str, dados: bytes | str) -> Path:
    alvo = tmp_path / "escolhidos" / nome
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(dados, str):
        alvo.write_text(dados, encoding="utf-8")
    else:
        alvo.write_bytes(dados)
    return alvo


def test_a_escolha_da_cor_escolhe_a_folha(lg: Lugares, nova: Manifesto) -> None:
    assert tm.tema_da_casa(lg).folha == "", "Escuro é o da casa: nenhuma folha"
    opcoes.guardar(nova, "tema", "Claro", lg)
    casa = tm.tema_da_casa(lg)
    assert "--app-bg:#eef0f5" in casa.folha and casa.de == NOVA and not casa.recusa
    opcoes.guardar(nova, "tema", "Importado", lg)
    assert tm.tema_da_casa(lg).folha == "", "Importado sem arquivo deixa a cor da casa"


def test_o_lado_vem_da_escolha_e_do_sistema_e_vazio(lg: Lugares, nova: Manifesto) -> None:
    assert tm.tema_da_casa(lg).botoes == ""
    opcoes.guardar(nova, "botoes", "Esquerda", lg)
    assert tm.tema_da_casa(lg).botoes == "esquerda"
    opcoes.guardar(nova, "botoes", "Direita", lg)
    assert tm.tema_da_casa(lg).botoes == "direita"


def test_o_tema_importado_passa_pela_regua_e_pinta(lg: Lugares, nova: Manifesto,
                                                    tmp_path: Path) -> None:
    nome = importados.importar(nova, "tema_importado", _arquivo(tmp_path, "meu.css", OUTRO), lg)
    assert nome == "meu.css"
    assert opcoes.ler(nova, lg)["tema_importado"] == "meu.css"
    opcoes.guardar(nova, "tema", "Importado", lg)
    assert "--app-bg:#f0eee5" in tm.tema_da_casa(lg).folha
    assert importados.caminho(NOVA, "tema_importado", lg) in tm.arquivos_de_opcoes_dos_temas(lg)
    importados.tirar(nova, "tema_importado", lg)
    assert tm.tema_da_casa(lg).folha == ""
    assert opcoes.ler(nova, lg)["tema_importado"] == ""


@pytest.mark.parametrize("texto, trecho", [
    (CLARO.replace("#1c1e29", "#e0e0e0"), "ilegível"),
    (":root{--app-bg:url(https://x.y/a.png)}", "url()"),
    (".quadro{display:none}", ":root"),
    ("x" * (17 * 1024), "16 KB"),
])
def test_o_tema_importado_que_nao_serve_nao_entra(lg: Lugares, nova: Manifesto, tmp_path: Path,
                                                   texto: str, trecho: str) -> None:
    with pytest.raises(InstalacaoRecusadaError, match=trecho):
        importados.importar(nova, "tema_importado", _arquivo(tmp_path, "t.css", texto), lg)
    assert not importados.caminho(NOVA, "tema_importado", lg).exists()
    assert opcoes.ler(nova, lg)["tema_importado"] == ""


def test_a_copia_do_tema_trocada_a_mao_nao_liga(lg: Lugares, nova: Manifesto,
                                                 tmp_path: Path) -> None:
    importados.importar(nova, "tema_importado", _arquivo(tmp_path, "t.css", OUTRO), lg)
    opcoes.guardar(nova, "tema", "Importado", lg)
    importados.caminho(NOVA, "tema_importado", lg).write_text(
        ":root{--fg:#202020}", encoding="utf-8")
    casa = tm.tema_da_casa(lg)
    assert casa.folha == "" and "ilegível" in casa.recusa


def test_a_logo_importada_vira_a_folha_da_logo(lg: Lugares, nova: Manifesto,
                                               tmp_path: Path) -> None:
    importados.importar(nova, "logo", _arquivo(tmp_path, "logo.png", _png()), lg)
    casa = tm.tema_da_casa(lg)
    assert '.logo{background-image:url("data:image/png;base64,' in casa.css
    assert ".logo svg{visibility:hidden !important}" in casa.css
    assert casa.css_de == NOVA and casa.folha == ""


@pytest.mark.parametrize("nome, dados, trecho", [
    ("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>x()</script></svg>',
     "PNG, JPEG ou WebP"),
    ("logo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "PNG, JPEG ou WebP"),
    ("logo.png", _png(2048, 16), "2048 por 16"),
    ("logo.png", _png(8, 8), "8 por 8"),
    ("logo.png", _png() + b"\x00" * (300 * 1024), "256 KB"),
])
def test_a_logo_que_nao_e_imagem_nao_entra(lg: Lugares, nova: Manifesto, tmp_path: Path,
                                           nome: str, dados: bytes, trecho: str) -> None:
    with pytest.raises(InstalacaoRecusadaError, match=trecho):
        importados.importar(nova, "logo", _arquivo(tmp_path, nome, dados), lg)
    assert tm.tema_da_casa(lg).css == ""


def test_a_copia_da_logo_trocada_a_mao_nao_pinta(lg: Lugares, nova: Manifesto,
                                                 tmp_path: Path) -> None:
    importados.importar(nova, "logo", _arquivo(tmp_path, "logo.png", _png()), lg)
    importados.caminho(NOVA, "logo", lg).write_bytes(b'<svg onload="x()"/>')
    assert tm.tema_da_casa(lg).css == ""


def test_o_meu_css_importado_vai_para_o_meu_css_e_liga(lg: Lugares, nova: Manifesto,
                                                       tmp_path: Path) -> None:
    importados.importar(nova, "meu_css", _arquivo(tmp_path, "a.css", ".quadro{gap:2px}"), lg)
    assert meu_css.caminho(NOVA, lg).read_text(encoding="utf-8") == ".quadro{gap:2px}"
    assert opcoes.ler(nova, lg)["meu_css"] is True
    with pytest.raises(InstalacaoRecusadaError, match="url"):
        importados.importar(nova, "meu_css",
                            _arquivo(tmp_path, "b.css", ".a{background:url(x)}"), lg)
    assert meu_css.caminho(NOVA, lg).read_text(encoding="utf-8") == ".quadro{gap:2px}"


def test_o_destaque_troca_o_verde_no_escuro_e_no_claro(lg: Lugares, nova: Manifesto) -> None:
    opcoes.guardar(nova, "cor_de_destaque", "#8be9fd", lg)
    assert tm.tema_da_casa(lg).folha == "", "o destaque desligado não pinta"
    opcoes.guardar(nova, "destaque", True, lg)
    assert tm.tema_da_casa(lg).folha == ":root{--green:#8be9fd !important;}"
    opcoes.guardar(nova, "tema", "Claro", lg)
    opcoes.guardar(nova, "cor_de_destaque", "#005f73", lg)
    casa = tm.tema_da_casa(lg)
    assert "--green:#005f73" in casa.folha and "--app-bg:#eef0f5" in casa.folha


def test_o_destaque_ilegivel_nao_liga_e_o_tema_fica(lg: Lugares, nova: Manifesto) -> None:
    opcoes.guardar(nova, "tema", "Claro", lg)
    opcoes.guardar(nova, "destaque", True, lg)
    opcoes.guardar(nova, "cor_de_destaque", "#f0f0f0", lg)
    casa = tm.tema_da_casa(lg)
    assert "--app-bg:#eef0f5" in casa.folha and "--green:#1d7a3c" in casa.folha
    assert "ilegível" in casa.recusa_do_destaque and not casa.recusa


def _antiga(lg: Lugares, tmp_path: Path) -> Manifesto:
    manifesto = _manifesto(ANTIGA, versao="1.2.0", tema={  # (noqa-acento)
        "arquivo": "tema.css", "botoes": "esquerda", "cor_pela_opcao": "cores_claras",
        "botoes_pela_opcao": "botoes_a_esquerda"}, opcoes=[  # (noqa-acento)
        {"id": "cores_claras", "rotulo": "Cores claras", "tipo": "ligado",
         "padrao": True},  # (noqa-acento)
        {"id": "botoes_a_esquerda", "rotulo": "Botões à esquerda", "tipo": "ligado",
         "padrao": True},  # (noqa-acento)
        {"id": "meu_css", "rotulo": "Usar o meu CSS", "tipo": "css",
         "padrao": False}])  # (noqa-acento)
    return _ligada(lg, _pasta(tmp_path, manifesto))


def _substituir(lg: Lugares, tmp_path: Path) -> Manifesto:
    instalador.instalar(str(_pasta(tmp_path, _manifesto(substitui=[ANTIGA]))), lugares=lg)
    return instalador.manifesto_instalado(NOVA, lugares=lg)


def test_a_antiga_ligada_passa_o_que_se_via(lg: Lugares, tmp_path: Path) -> None:
    antiga = _antiga(lg, tmp_path)
    opcoes.guardar(antiga, "meu_css", True, lg)
    nova = _substituir(lg, tmp_path)
    valores = opcoes.ler(nova, lg)
    assert valores["tema"] == "Claro", "cores_claras no padrão (true) era o que se via"
    assert valores["botoes"] == "Esquerda"
    assert valores["meu_css"] is True
    assert ANTIGA not in instalador.ler_registro(lg.registro)


def test_a_antiga_desligada_nao_passa_o_que_guardava(lg: Lugares, tmp_path: Path) -> None:
    antiga = _antiga(lg, tmp_path)
    opcoes.guardar(antiga, "cores_claras", True, lg)
    instalador.desligar(ANTIGA, lugares=lg)
    valores = opcoes.ler(_substituir(lg, tmp_path), lg)
    assert valores["tema"] == "Escuro" and valores["botoes"] == "Do sistema"


def test_o_que_o_mapa_nao_traduz_fica_no_padrao(lg: Lugares, tmp_path: Path) -> None:
    antiga = _antiga(lg, tmp_path)
    opcoes.guardar(antiga, "botoes_a_esquerda", False, lg)
    assert opcoes.ler(_substituir(lg, tmp_path), lg)["botoes"] == "Do sistema"


def test_o_meu_css_da_antiga_vai_para_a_nova(lg: Lugares, tmp_path: Path) -> None:
    _antiga(lg, tmp_path)
    meu_css.caminho(ANTIGA, lg).parent.mkdir(parents=True, exist_ok=True)
    meu_css.caminho(ANTIGA, lg).write_text(".a{gap:1px}", encoding="utf-8")
    _substituir(lg, tmp_path)
    assert meu_css.caminho(NOVA, lg).read_text(encoding="utf-8") == ".a{gap:1px}"


@pytest.mark.parametrize("mexe, trecho", [
    ({"opcoes": [{**OPCOES[1], "formato": None}, *OPCOES[2:]]}, "formato"),  # (noqa-acento)
    ({"opcoes": [{**OPCOES[0], "id": "x", "rotulo": "x"},  # (noqa-acento)
                 *OPCOES[1:]]}, "não existe"),
    ({"tema": {**BLOCO, "lados_por_escolha": {"Acima": "esquerda"}}}, "Acima"),
    ({"tema": {**BLOCO, "lados_por_escolha": {"Esquerda": "cima"}}}, "esquerda ou direita"),
    ({"tema": {**BLOCO, "logo_pela_opcao": "tema_importado"}}, "importa outra coisa"),
    ({"tema": {**BLOCO, "importados_por_escolha": {"Importado": "logo"}}}, "importa outra coisa"),
    ({"tema": {**BLOCO, "destaque_pela_opcao": "destaque"}}, "tipo cor"),
    ({"tema": {**BLOCO, "arquivo": "tema.css"}}, "não dos dois"),
    ({"tipos": ["processo"], "processo": {"executar": ["true"]}, "tema": None,  # (noqa-acento)
      "opcoes": [OPCOES[5]]}, "só uma extensão de tema importa"),  # (noqa-acento)
])
def test_a_regua_do_manifesto_confere_cada_vinculo(mexe: dict[str, Any], trecho: str) -> None:
    with pytest.raises(ValueError, match=trecho):
        Manifesto.model_validate({**_manifesto(), **mexe})


def test_o_nome_importado_e_so_texto_curto(nova: Manifesto, lg: Lugares) -> None:
    opcao = next(o for o in nova.opcoes if o.id == "logo")
    assert opcoes.validar(opcao, "  a.png ") == "a.png"
    for ruim in ("x" * 61, "a\nb", 3):
        with pytest.raises(InstalacaoRecusadaError):
            opcoes.validar(opcao, ruim)
