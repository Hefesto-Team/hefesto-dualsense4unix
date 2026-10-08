"""O-BLUEZ-SO-PELA-PORTA-OFICIAL-01 (07/10/2026): ninguém aconselha apagar o cache do BlueZ.

A premissa antiga («sem apagar o `cache/<MAC>` o pareamento novo nasce igual») foi medida no
fonte do BlueZ 5.86 e caiu: `device_remove_stored` (device.c:5402-5456) apaga a pasta do bond e
tira do cache os grupos ServiceRecords, Attributes e Endpoints; sem ServiceRecords o BlueZ refaz
o SDP (device.c:4441-4444). Um conselho que manda `rm` no cache é conselho de arquivo interno que
não muda o resultado, e o usuário o repete sem saber.

A régua varre o que o usuário LÊ (guia, doctor, scripts, produto) atrás do comando.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# `rm` (qualquer flag) numa linha que fala de /var/lib/bluetooth/.../cache.
_RM_NO_CACHE = re.compile(r"\brm\b[^\n]*?/var/lib/bluetooth[^\n]*?/cache")

# O que o BlueZ não expõe e a ponte privilegiada paga: a remoção do cache da ORIGEM, em disco,
# dentro de `_apagar` (que recusa tudo fora da forma esperada). Nada mais.
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
