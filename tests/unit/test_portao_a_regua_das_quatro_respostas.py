"""A régua CABO · BT · PERFIL · CONTROLE morde — CABO-BT-PERFIL-CONTROLE-01.

**A palavra dela, 08/09/2026:** *"tudo funcionando por cabo ou bt ou tudo
funcionando via perfil e dentro de cada um um setting pra cada controle é assim
que eu queria que sua revisao nos auxiliasse."*  (noqa-acento: citação dela)

O portão é `scripts/check_cabo_bt_perfil_controle.py`, e ele tem TRÊS mordidas.
Cada uma nasceu de um jeito real de a tabela envelhecer:

1. **feature nova sem as quatro respostas** — o caso óbvio;
2. **dívida declarada que já fechou** — a declaração vira propaganda no dia
   seguinte à cura, e é a régua `divida-fechada` do `check_paridade_gtk_html`;
3. **classificação que a tela já não oferece** — a lista de features se LÊ, mas
   a razão se ESCREVE, e escrita envelhece.

**E UMA QUARTA COISA SE TRAVA AQUI, que não é mordida e sim leitura:** `parcial`
é o TERCEIRO valor de `*_aciona` no mapa e quer dizer *aciona, com a dívida na
ressalva*. Lê-lo como `não` reprovou quatro features vivas em 09/09/2026 — o
microfone, o mudo e as cinco lâmpadas de jogador pelo rádio.

**O VALOR SEM ACENTO VEM DA RÉGUA, e não é digitado aqui:** `regua.NAO` é o
dono, declarado uma vez com a isenção do portão de acentuação. Digitá-lo em
cada `assert` seria a segunda cópia de um dado — e é o que dois agentes
independentes fizeram em 09/09, com redações diferentes, antes de o dono
existir.
"""
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
    """O estado de agora é VERDE — e SEM dívida declarada nenhuma.

    ATÉ 09/09/2026 esta régua exigia aqui o nome `volume` na saída: era a única
    dívida declarada, e ela tinha de sair NOMEADA em vez de em silêncio. A
    dívida fechou (MIC-VOLUME-02: a bancada dela mediu o `common[6]`
    obedecendo, ela mandou ligar o byte, e o gesto e o perfil o escrevem por
    `uniq`), então o que se cobra agora é o CONTADOR em zero — e quem guarda a
    propriedade de "dívida aberta sai nomeada" é o teste logo abaixo, com uma
    dívida de mentira, porque hoje não existe nenhuma de verdade para ler.
    """
    assert regua.main() == 0
    saida = capsys.readouterr().out
    assert "VERDE" in saida
    assert "0 em dívida declarada" in saida


def test_divida_aberta_sai_nomeada_e_nao_reprova(regua, monkeypatch, capsys):
    """A dívida DECLARADA fica verde, mas nunca fica calada.

    Nasceu em 12/09/2026, quando a última dívida de verdade fechou: sem ela, a
    propriedade que o `test_a_tela_de_hoje_passa` cobrava parou de ter sujeito, e
    uma propriedade sem sujeito é uma régua desligada em silêncio.

    A dívida de mentira é construída pelo caminho real e não por monkeypatch da
    saída: o gesto `mudo` passa a responder por uma chave do mapa que NÃO
    aciona, e é declarado. O portão tem de ficar verde E dizer o nome.
    """
    monkeypatch.setitem(regua.DO_APARELHO, "mudo", ("luz.lightbar.brilho",))
    monkeypatch.setitem(
        regua.A_DIVIDA_CONHECIDA, "mudo",
        ("2026-01-01-DE-MENTIRA.md", "dívida de mentira, só para provar que a "
                                     "declarada sai nomeada"))
    assert regua.main() == 0
    saida = capsys.readouterr().out
    assert "1 em dívida declarada" in saida
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
    """`parcial` é `com ressalva` — nunca a resposta negativa.

    A linha `audio.microfone@dualsense` responde `radio_aciona=parcial`, e o
    microfone FUNCIONA por rádio na mesa dela. Ler o `parcial` como negativa
    foi o defeito de 09/09/2026, e é ele que este teste impede de voltar.
    """
    linha = {"controle": "dualsense", "radio_aciona": "parcial",
             "radio_ressalva": "a dívida escrita"}
    assert regua._resposta_de_transporte([linha], "radio") == "com ressalva"
    assert regua._resposta_de_transporte([linha], "radio") != regua.NAO


def test_o_gesto_responde_pela_pior_das_chaves(regua):
    """Um gesto com dois atos no aparelho responde pela metade que FALTA."""
    assert regua._pior(["sim", regua.NAO]) == regua.NAO
    assert regua._pior(["sim", "com ressalva"]) == "com ressalva"
    assert regua._pior([]) == "sem linha"
    # o `volume` da 02 é o caso vivo de DUAS chaves num gesto. Até 09/09/2026 ele
    # era também o caso vivo da PIOR delas: o alto-falante respondia `sim` e o
    # microfone a negativa. A MIC-VOLUME-02 fechou essa metade (o `common[6]`
    # passou a ser escrito), então hoje o gesto responde inteiro — o que se trava
    # aqui é o PAR, que é o que faz a régua olhar as duas.
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
    """§3 da sprint: tirar `speaker` de `ControllerOverrides` reprova o `rota`.

    A pergunta 4 dela — *"e, dentro do perfil, é por controle?"* — é lida do
    FONTE do `schema.py`. Sem esta mordida, arrancar o campo deixaria a tabela
    dizendo `sim` sobre um lugar que já não existe.
    """
    real = regua._campos_do_esquema

    def sem_o_speaker(classe: str) -> set[str]:
        campos = real(classe)
        return campos - {"speaker"} if classe == "ControllerOverrides" else campos

    monkeypatch.setattr(regua, "_campos_do_esquema", sem_o_speaker)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "rota" in saida
    assert "não é por controle" in saida


def test_morde_o_transporte_rebaixado_no_mapa(regua, monkeypatch, capsys):
    """§3 da sprint: `luz.lightbar.cor@dualsense` com `radio_aciona=não`.

    Quatro gestos da 04 dependem dessa linha (`cor`, `brilho`, `apagar`,
    `reenviar`) e a régua tem de nomear os quatro, não um.
    """
    real = regua._linhas_do_mapa()
    for linha in real.get("luz.lightbar.cor", []):
        if linha.get("controle") == "dualsense":
            linha["radio_aciona"] = "não"
    monkeypatch.setattr(regua, "_linhas_do_mapa", lambda: real)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    for gesto in ("cor", "brilho", "apagar", "reenviar"):
        assert f"{gesto}: rádio: {regua.NAO}" in saida
