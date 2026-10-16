"""A régua CABO · BT · PERFIL · CONTROLE morde — CABO-BT-PERFIL-CONTROLE-01."""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts/check_cabo_bt_perfil_controle.py"


def _regua():
    spec = importlib.util.spec_from_file_location("_regua_das_quatro", PORTAO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def regua():
    return _regua()


def test_a_tela_de_hoje_passa(regua, capsys):
    """O estado de agora é VERDE — e toda dívida aberta sai NOMEADA."""
    assert regua.main() == 0
    saida = capsys.readouterr().out
    assert "VERDE" in saida
    for gesto in regua.A_DIVIDA_CONHECIDA:
        sprint, _razao = regua.A_DIVIDA_CONHECIDA[gesto]
        assert f"dívida: {gesto}" in saida, (
            f"a dívida `{gesto}` está declarada e não sai nomeada — é uma "
            f"dívida em silêncio, que é o que esta régua existe para impedir")
        assert sprint in saida, (
            f"a dívida `{gesto}` sai sem a dona; sem ela ninguém sabe onde o "
            f"fecho está escrito")


def test_divida_aberta_sai_nomeada_e_nao_reprova(regua, monkeypatch, capsys):
    """A dívida DECLARADA fica verde, mas nunca fica calada."""
    monkeypatch.setitem(regua.DO_APARELHO, "mudo", ("luz.lightbar.brilho",))
    monkeypatch.setitem(
        regua.A_DIVIDA_CONHECIDA, "mudo",
        ("2026-01-01-DE-MENTIRA.md", "dívida de mentira, só para provar que a "
                                     "declarada sai nomeada"))
    quantas = len(regua.A_DIVIDA_CONHECIDA)
    assert regua.main() == 0
    saida = capsys.readouterr().out
    assert f"{quantas} em dívida declarada" in saida
    assert "dívida: mudo" in saida
    assert "2026-01-01-DE-MENTIRA.md" in saida


def test_toda_feature_da_tela_esta_classificada(regua):
    """Nenhum `data-gesto` das dez páginas fica sem razão ou sem chave."""
    na_tela = set(regua.gestos_da_tela())
    declarados = set(regua.NAO_E_DO_APARELHO) | set(regua.DO_APARELHO)
    assert not na_tela - declarados, "gesto da tela sem classificação"


def test_morde_feature_nova_sem_as_quatro_respostas(regua, monkeypatch, capsys):
    """MORDIDA 1 — um gesto novo na tela reprova nomeando."""
    monkeypatch.setattr(regua, "gestos_da_tela",
                        lambda: {**_regua().gestos_da_tela(), "luz-nova": ["04"]})
    assert regua.main() == 1
    assert "luz-nova" in capsys.readouterr().out


def test_morde_divida_declarada_que_ja_fechou(regua, monkeypatch, capsys):
    """MORDIDA 2 — a linha da dívida tem de SAIR quando a cura chega."""
    monkeypatch.setitem(
        regua.A_DIVIDA_CONHECIDA, "cor",
        ("2026-01-01-INVENTADA.md", "esta dívida não existe: o `cor` responde "
                                    "as quatro desde sempre"))
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "já respondem as quatro" in saida
    assert "cor" in saida


def test_morde_classificacao_que_a_tela_nao_oferece_mais(regua, monkeypatch,
                                                         capsys):
    """MORDIDA 3 — razão escrita para gesto que saiu da tela reprova."""
    monkeypatch.setitem(regua.NAO_E_DO_APARELHO, "gesto-que-morreu",
                        "razão órfã")
    assert regua.main() == 1
    assert "gesto-que-morreu" in capsys.readouterr().out


def test_parcial_nao_e_nao(regua):
    """`parcial` é `com ressalva` — nunca a resposta negativa."""
    linha = {"controle": "dualsense", "radio_aciona": "parcial",
             "radio_ressalva": "a dívida escrita"}
    assert regua._resposta_de_transporte([linha], "radio") == "com ressalva"
    assert regua._resposta_de_transporte([linha], "radio") != regua.NAO


def test_o_gesto_responde_pela_pior_das_chaves(regua):
    """Um gesto com dois atos no aparelho responde pela metade que FALTA."""
    assert regua._pior(["sim", regua.NAO]) == regua.NAO
    assert regua._pior(["sim", "com ressalva"]) == "com ressalva"
    assert regua._pior([]) == "sem linha"
    assert regua.DO_APARELHO["volume"] == ("audio.microfone.volume",
                                           "audio.alto_falante.volume")


def test_so_o_dualsense_responde(regua):
    """As linhas do `pro` e do `sn30` não respondem pela tela dos quatro.

    Sem o filtro, um `sim` do 8BitDo daria por respondida uma feature que o
    DualSense não tem — e o inverso, um `não` do Pro, reprovaria feature viva.
    """
    outros = [{"controle": "pro", "cabo_aciona": "sim", "cabo_ressalva": ""}]
    assert regua._resposta_de_transporte(outros, "cabo") == "sem linha"


def test_morde_o_campo_arrancado_do_esquema(regua, monkeypatch, capsys):
    """§3 da sprint: tirar `speaker` de `ControllerOverrides` reprova o `rota`."""
    real = regua._campos_do_esquema

    def sem_o_speaker(classe: str, *fonte: object) -> set[str]:
        campos = real(classe, *fonte)
        return campos - {"speaker"} if classe == "ControllerOverrides" else campos

    monkeypatch.setattr(regua, "_campos_do_esquema", sem_o_speaker)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "rota" in saida
    assert "não é por controle" in saida


def test_morde_o_transporte_rebaixado_no_mapa(regua, monkeypatch, capsys):
    """§3 da sprint: `luz.lightbar.cor@dualsense` com `radio_aciona=não`.

    Três gestos da 04 dependem dessa linha (`cor`, `brilho`, `apagar`; o `reenviar` saiu em
    16/10/2026) e a régua tem de nomear os três, não um.
    """
    real = regua._linhas_do_mapa()
    for linha in real.get("luz.lightbar.cor", []):
        if linha.get("controle") == "dualsense":
            linha["radio_aciona"] = "não"
    monkeypatch.setattr(regua, "_linhas_do_mapa", lambda: real)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    for gesto in ("cor", "brilho", "apagar"):
        assert f"{gesto}: rádio: {regua.NAO}" in saida


def test_o_mudo_do_microfone_responde_no_controle(regua):
    """O-MUDO-E-DO-CONTROLE-01 (28/09/2026): o mudo não fica no perfil."""
    linhas = {linha[0]: linha for linha in regua.tabela()}
    for gesto in ("mudo", "custo-mic"):
        _g, _abas, _cabo, _radio, perfil, controle, _falta = linhas[gesto]
        assert (perfil, controle) == ("no controle", "sim"), (
            f"o `{gesto}` não responde pelo dono do mudo: {perfil!r}, {controle!r}")
        assert gesto not in regua.NO_PERFIL, (
            f"o `{gesto}` ainda se declara no perfil — o mudo saiu de lá")


def test_morde_o_mudo_arrancado_do_controle(regua, monkeypatch, capsys):
    """Tirar `microfone_mudo` de `ControleDeclarado` reprova o `mudo` e o `custo-mic`."""
    real = regua._campos_do_esquema

    def sem_o_mudo(classe: str, *fonte: object) -> set[str]:
        campos = real(classe, *fonte)
        return campos - {"microfone_mudo"} if classe == "ControleDeclarado" else campos

    monkeypatch.setattr(regua, "_campos_do_esquema", sem_o_mudo)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    for gesto in ("mudo", "custo-mic"):
        assert f"{gesto}: não está no perfil" in saida



# AS-REGUAS-DO-RAMO-INTEIRO-E-DAS-QUATRO-RESPOSTAS-MORDEM-01: a régua lê as páginas SEM o
# estilo e o registro dos `@gesto` do fonte. Antes, um gesto que só aparecia num seletor de CSS
# entrava, e os que a página gera em JS (ou que moram fora das dez) ficavam invisíveis.


def test_o_gesto_so_no_estilo_nao_conta(regua, tmp_path):
    """MORDIDA: tirar o `_SEM_ESTILO.sub` de `gestos_das_paginas` conta o seletor de CSS."""
    (tmp_path / "01-x.html").write_text(
        '<style>select.pronto[data-gesto="so-no-css"]{width:132px}</style>\n'
        '<button data-gesto="de-verdade">ok</button>\n', encoding="utf-8")
    (tmp_path / "fora-das-dez.html").write_text(
        '<button data-gesto="nao-e-das-dez">ok</button>\n', encoding="utf-8")
    assert regua.gestos_das_paginas(tmp_path) == {"de-verdade": ["01"]}


def test_o_externo_cor_vem_do_registro_e_nao_do_css(regua):
    assert "externo-cor" not in regua.gestos_das_paginas()
    assert regua.gestos_da_tela()["externo-cor"] == ["08"]


def test_morde_gesto_so_no_registro_sem_classe(regua, monkeypatch, capsys):
    """Um `@gesto` sem `data-gesto` na página, e sem classe, reprova nomeando."""
    real = regua.registro_do_fonte

    def com_um_a_mais():
        pares, sem_texto = real()
        return pares | {("05-vibracao.html", "so-no-registro")}, sem_texto

    monkeypatch.setattr(regua, "registro_do_fonte", com_um_a_mais)
    assert "so-no-registro" not in regua.gestos_das_paginas()
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "so-no-registro" in saida
    assert "sem classificação" in saida


@pytest.mark.parametrize("gesto", ["mira-sensibilidade", "mic-existe", "teto-da-vibracao"])
def test_morde_gesto_de_aparelho_que_so_o_registro_mostra(regua, monkeypatch, capsys, gesto):
    """Os de aparelho que a régua de antes não via: sem a classe, reprovam nomeando.

    `mira-sensibilidade` tem a página por constante (`@gesto(PAGINA, …)`, a Calibrar, fora das
    dez); `mic-existe` e `teto-da-vibracao` a 08 gera em JS.
    """
    assert gesto not in regua.gestos_das_paginas()
    assert gesto in regua.gestos_da_tela()
    monkeypatch.delitem(regua.DO_APARELHO, gesto)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert f"{gesto}: gesto sem classificação" in saida


def _fonte(raiz: pathlib.Path, arquivos: dict[str, str]) -> tuple[pathlib.Path, pathlib.Path]:
    src = raiz / "src"
    for nome, texto in arquivos.items():
        caminho = src / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
    return src / "pk" / "pacotes", src


def test_a_leitura_do_fonte_resolve_literal_constante_importada_e_atributo(regua, tmp_path):
    pasta, src = _fonte(tmp_path, {
        "pk/__init__.py": "",
        "pk/desenho.py": 'ABRIR = "abrir-x"\n',
        "pk/nomes.py": 'NOME = "nome-y"\n',
        "pk/pacotes/__init__.py": "",
        "pk/pacotes/a01_x.py": (
            "from pk import desenho\n"
            "from pk.nomes import NOME\n"
            "from ..nomes import NOME as OUTRO\n"
            "from .. import desenho as d2\n"
            'PAGINA = "01-x.html"\n'
            '@gesto(PAGINA, "literal")\n'
            "def a(): ...\n"
            '@gesto("02-y.html", desenho.ABRIR, grava="x")\n'
            "def b(): ...\n"
            "@gesto(PAGINA, NOME)\n"
            "def c(): ...\n"
            '@gesto("*", OUTRO)\n'
            "def e(): ...\n"
            'pacotes.gesto("*", d2.ABRIR)(a)\n'
        ),
    })
    pares, sem_texto = regua.registro_do_fonte(pasta, src)
    assert sem_texto == []
    assert pares == {
        ("01-x.html", "literal"), ("02-y.html", "abrir-x"), ("01-x.html", "nome-y"),
        ("*", "nome-y"), ("*", "abrir-x"),
    }


def test_o_gesto_que_a_leitura_nao_resolve_reprova(regua, tmp_path, monkeypatch, capsys):
    """Nome montado em tempo de execução é um gesto que a régua não vê: ela diz, não cala."""
    pasta, src = _fonte(tmp_path, {
        "pk/pacotes/a01_x.py": (
            'PAGINA = "01-x.html"\n'
            'DOIS = "a"\nDOIS = "b"\n'
            '@gesto(PAGINA, f"montado-{1}")\n'
            "def a(): ...\n"
            "@gesto(PAGINA, DOIS)\n"
            "def b(): ...\n"
        ),
    })
    pares, sem_texto = regua.registro_do_fonte(pasta, src)
    assert pares == set()
    assert [linha.split(" ", 1)[0].rsplit(":", 1)[1] for linha in sem_texto] == ["4", "6"], (
        "a f-string e a constante ambígua (dois valores) ficam sem texto")
    monkeypatch.setattr(regua, "registro_do_fonte", lambda *_a: (set(), sem_texto))
    assert regua.main() == 1
    assert "a leitura do fonte não resolve" in capsys.readouterr().out


def test_o_zero_do_sensor_responde_por_controle_no_arquivo_dele(regua):
    linhas = {linha[0]: linha for linha in regua.tabela()}
    _g, abas, _cabo, _radio, perfil, controle, falta = linhas["calibrar-comecar"]
    assert abas == "calibrar-sensores"
    assert (perfil, controle, falta) == ("só por controle", "sim", "")


def test_morde_o_zero_sem_quem_o_grave(regua, monkeypatch, capsys):
    """Tirar a função que grava o zero reprova o `calibrar-comecar`."""
    fonte, _funcao = regua.NO_ARQUIVO_DO_CONTROLE["calibrar-comecar"]
    monkeypatch.setitem(regua.NO_ARQUIVO_DO_CONTROLE, "calibrar-comecar",
                        (fonte, "gravar_os_zeros_que_nao_existe"))
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "calibrar-comecar: não está no perfil; não é por controle" in saida
