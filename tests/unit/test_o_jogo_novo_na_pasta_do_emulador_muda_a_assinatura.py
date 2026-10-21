"""O jogo novo na pasta do emulador muda a assinatura das bibliotecas.

Medido em 20/10/2026 (O-JOGO-NOVO-NA-PASTA-DO-EMULADOR-MUDA-A-ASSINATURA-01): com o Dolphin, o
Azahar e o KytyPS5, o jogo posto na pasta que o `.ini` do emulador aponta não mudava a
`assinatura_das_bibliotecas()`, porque as `fontes` do leitor são caminhos fixos da `HOME` e a
pasta de jogos é a que a pessoa escolheu no emulador. A semeadura dos perfis não acordava.

A cura: o leitor diz as pastas que percorreu (`{"jogos": [...], "pastas": [...]}`), e a assinatura
conta a data de cada pasta da última leitura daquela extensão. A lista sozinha continua valendo.

MORDIDA: tire o laço das `pastas` da `assinatura_das_bibliotecas` e o teste do jogo novo reprova.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

MOD = "dolphin-de-mentira"


def _extensao(pasta: Path, saida: object) -> censo.LeitorPorProcesso:
    (pasta / "saida.json").write_text(json.dumps(saida), encoding="utf-8")
    (pasta / "leitor.py").write_text(
        "print(open('saida.json', encoding='utf-8').read())\n", encoding="utf-8")
    return censo.LeitorPorProcesso(modificacao=MOD, rotulo="Dolphin",
                                   comando=(sys.executable, "-I", "leitor.py"), pasta=pasta)


@pytest.fixture
def lar(tmp_path: Path) -> Path:
    alvo = tmp_path / "lar"
    alvo.mkdir()
    return alvo


@pytest.fixture
def roms(tmp_path: Path) -> Path:
    alvo = tmp_path / "outro-disco" / "roms" / "gc"
    alvo.mkdir(parents=True)
    (alvo / "Antigo.iso").write_bytes(b"")
    return alvo


def _ligada(monkeypatch: pytest.MonkeyPatch, leitor: censo.LeitorPorProcesso) -> None:
    bloco = censo.LancadorDaModificacao(chave=MOD, rotulo="Dolphin", leitor=leitor)
    monkeypatch.setattr(censo, "lancadores_das_extensoes",
                        lambda lugares=None: (censo.LancadorDaExtensao(bloco),))


JOGO = {"chave": "antigo", "nome": "Antigo"}


def test_o_jogo_novo_na_pasta_lida_muda_a_assinatura(
    tmp_path: Path, lar: Path, roms: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leitor = _extensao(tmp_path, {"jogos": [JOGO], "pastas": [str(roms)]})
    _ligada(monkeypatch, leitor)
    lida = censo.ler_por_processo(leitor, bwrap=False)
    assert lida.estado == censo.LIDO and [j.chave for j in lida.jogos] == ["antigo"]
    antes = censo.assinatura_das_bibliotecas(lar)
    (roms / "Novo Jogo.iso").write_bytes(b"")
    os.utime(roms, ns=(1, os.stat(roms).st_mtime_ns + 1_000_000_000))
    assert censo.assinatura_das_bibliotecas(lar) != antes


def test_a_lista_sozinha_continua_lida(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    leitor = _extensao(tmp_path, [JOGO])
    lida = censo.ler_por_processo(leitor, bwrap=False)
    assert lida.estado == censo.LIDO and [j.chave for j in lida.jogos] == ["antigo"]
    assert censo.pastas_da_ultima_leitura(MOD) == ()


@pytest.mark.parametrize("pastas", [["relativa/roms"], [7], "/não/é/lista", ["/x\x00y"]])
def test_a_pasta_torta_sai_e_os_jogos_ficam(tmp_path: Path, pastas: object) -> None:
    leitor = _extensao(tmp_path, {"jogos": [JOGO], "pastas": pastas})
    lida = censo.ler_por_processo(leitor, bwrap=False)
    assert lida.estado == censo.LIDO and [j.chave for j in lida.jogos] == ["antigo"]
    assert censo.pastas_da_ultima_leitura(MOD) == ()


def test_o_teto_das_pastas(tmp_path: Path) -> None:
    muitas = [f"/roms/{i}" for i in range(censo.PASTAS_MAXIMAS_DO_LEITOR + 5)]
    leitor = _extensao(tmp_path, {"jogos": [JOGO], "pastas": muitas})
    censo.ler_por_processo(leitor, bwrap=False)
    assert len(censo.pastas_da_ultima_leitura(MOD)) == censo.PASTAS_MAXIMAS_DO_LEITOR
