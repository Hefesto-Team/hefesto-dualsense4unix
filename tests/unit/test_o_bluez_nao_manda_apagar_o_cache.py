"""O-BLUEZ-SO-PELA-PORTA-OFICIAL-01 (07/10/2026): ninguém aconselha apagar o cache do BlueZ.

A premissa antiga («sem apagar o `cache/<MAC>` o pareamento novo nasce igual») foi medida no
fonte do BlueZ 5.86 e caiu: `device_remove_stored` (device.c:5402-5456) apaga a pasta do bond e
tira do cache os grupos ServiceRecords, Attributes e Endpoints; sem ServiceRecords o BlueZ refaz
o SDP (device.c:4441-4444). Um conselho que manda `rm` no cache é conselho de arquivo interno que
não muda o resultado, e o usuário o repete sem saber.

A régua varre o que o usuário LÊ (guia, doctor, scripts, produto) atrás do comando e atrás da
premissa que o sustentava («o cache SDP tem de sair junto com o bond»), que também é conselho
de arquivo interno quando escrita em comentário, docstring ou desenho.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

_RM_NO_CACHE = re.compile(r"\brm\b[^\n]*?/var/lib/bluetooth[^\n]*?/cache")

_ISENTOS = {"scripts/bt_ponte_privilegiada.sh"}


def _arquivos() -> list[Path]:
    achados: list[Path] = []
    for pasta, extensoes in (
        ("docs/usage", {".md"}),
        ("scripts", {".sh", ".py"}),
        ("src", {".py"}),
    ):
        for caminho in sorted((RAIZ / pasta).rglob("*")):
            if caminho.suffix in extensoes and "__pycache__" not in caminho.parts:
                achados.append(caminho)
    return achados


def _acha(texto: str) -> list[str]:
    return [linha.strip() for linha in texto.splitlines() if _RM_NO_CACHE.search(linha)]


def test_nenhum_guia_script_ou_modulo_manda_apagar_o_cache_do_bluez() -> None:
    """MORDIDA: devolva o `sudo rm -f /var/lib/bluetooth/*/cache/<MAC>` ao guia ou ao doctor."""
    fora: list[str] = []
    for caminho in _arquivos():
        relativo = str(caminho.relative_to(RAIZ))
        if relativo in _ISENTOS:
            continue
        for linha in _acha(caminho.read_text(encoding="utf-8", errors="replace")):
            fora.append(f"{relativo}: {linha}")
    assert fora == [], "conselho de apagar cache do BlueZ:\n" + "\n".join(fora)


def test_a_regua_enxerga_o_conselho_antigo() -> None:
    """A régua não pode ser cega: o texto que ela existe para barrar tem de casar."""
    antigo = "sudo rm -f /var/lib/bluetooth/*/cache/<ENDERECO_DO_CONTROLE>"
    assert _acha(antigo) == [antigo]
    assert _acha("busctl call org.bluez /org/bluez/hci0 org.bluez.Adapter1 RemoveDevice o /x") == []


_PREMISSA = re.compile(
    r"apagar\s+o\s+cache\s+SDP"
    r"|cache\s+SDP\s+(?:tem\s+de\s+sair|sai)\s+junto"
    r"|o\s+cache\s+sozinho\s+envenena"
    r"|envenena\s+o\s+pareamento"
    r"|pareamento\s+novo\s+nasce\s+com\s+SDP\s+vazio",
    re.IGNORECASE,
)

_DESENHOS = tuple(sorted(str(p.relative_to(RAIZ)) for p in (RAIZ / "mockup").glob("*.html")))
_ISENTOS_DA_PREMISSA = _ISENTOS | {"src/hefesto_dualsense4unix/interface/pagina_do_mapa.py"}


_COMECO_DA_LINHA = re.compile(r"""^\s*(?:#+|//|/?\*+)?\s*(?:print\(\s*f?["'])?""")
_FIM_DA_LINHA = re.compile(r"""["']\)\s*$""")


def _acha_a_premissa(texto: str) -> list[str]:
    corrido = " ".join(
        _FIM_DA_LINHA.sub("", _COMECO_DA_LINHA.sub("", linha)) for linha in texto.splitlines()
    )
    return [" ".join(m.group(0).split()) for m in _PREMISSA.finditer(corrido)]


def test_nenhum_texto_repete_que_o_cache_sdp_tem_de_sair_com_o_bond() -> None:
    """MORDIDA: devolva «apagar o cache SDP» a um comentário, ao guia ou ao desenho."""
    fora: list[str] = []
    for caminho in [*_arquivos(), *(RAIZ / d for d in _DESENHOS)]:
        relativo = str(caminho.relative_to(RAIZ))
        if relativo in _ISENTOS_DA_PREMISSA:
            continue
        for achado in _acha_a_premissa(caminho.read_text(encoding="utf-8", errors="replace")):
            fora.append(f"{relativo}: {achado}")
    assert fora == [], "premissa do cache SDP que o BlueZ já desmentiu:\n" + "\n".join(fora)


def test_a_regua_da_premissa_enxerga_a_frase_antiga_ate_quebrada() -> None:
    """A régua não pode ser cega: a frase velha casa, inclusive partida em duas linhas."""
    assert _acha_a_premissa("desfazer o pareamento, apagar o cache SDP e parear") != []
    assert _acha_a_premissa("o cache sozinho\n   envenena o pareamento seguinte") != []
    assert _acha_a_premissa("# Sem ela o pareamento novo\n# nasce com SDP vazio") != []
    assert _acha_a_premissa("  /* desfazer, apagar o\n     * cache SDP e parear */") != []
    assert _acha_a_premissa(
        'print("  (o bond E o cache SDP saem — o cache sozinho")\n'
        '    print("   envenena a volta)")'
    ) != []
    assert "mockup/mapa-das-portas.html" in _DESENHOS
    assert _acha_a_premissa("o RemoveDevice do BlueZ já tira o [ServiceRecords] do cache") == []
