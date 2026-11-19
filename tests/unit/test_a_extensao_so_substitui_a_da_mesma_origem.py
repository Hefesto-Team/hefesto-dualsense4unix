"""O ``substitui`` só manda embora a extensão da mesma origem; a de outro lugar recusa antes.

Extensões FALSAS, de tema e sem processo, num lar de mentira no ``tmp_path``: duas pastas de
autores diferentes (raízes diferentes), e os endereços git só pela função pura.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import (
    Entrada,
    InstalacaoRecusadaError,
    Lugares,
    ler_registro,
    ligar,
)

INTERFACE = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix" / "interface"

ANTIGA, NOVA = "da-pessoa", "de-outro-autor"
NOMES = {ANTIGA: "Da pessoa", NOVA: "De outro autor"}
RECUSA = ("«De outro autor» diz que substitui «Da pessoa», que veio de outro lugar; "
          "remova «Da pessoa» antes, se quiser.")


def _pasta(raiz: Path, mod_id: str, *, substitui: tuple[str, ...] = ()) -> Path:
    pasta = raiz / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    manifesto: dict[str, Any] = {
        "id": mod_id, "nome": NOMES[mod_id], "versao": "1.0.0",  # (noqa-acento)
        "api": ">=2,<3", "licenca": "MIT", "tipos": ["tema"], "tema": {},
        "permissoes": [], "descricao": "Muda um detalhe.", "opcoes": [],  # (noqa-acento)
    }
    if substitui:
        manifesto["substitui"] = list(substitui)
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return pasta


@pytest.fixture
def lg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lugares:
    lugares = Lugares(codigo=tmp_path / "codigo",  # (noqa-acento)
                      dados=tmp_path / "dados",
                      registro=tmp_path / "config" / "mods.json",
                      estado=tmp_path / "run" / "mods-estado.json")
    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lugares))
    return lugares


def _a_da_pessoa(lg: Lugares, raiz: Path) -> Path:
    """A antiga instalada, ligada e com dados."""
    instalador.instalar(str(_pasta(raiz, ANTIGA)), lugares=lg)
    ligar(ANTIGA, permissoes_vistas=[], lugares=lg)
    dados = lg.dados / ANTIGA / "guardado.json"
    dados.parent.mkdir(parents=True, exist_ok=True)
    dados.write_text("{}", encoding="utf-8")
    return dados


def test_a_de_outro_lugar_recusa_e_a_instalada_fica_inteira(lg: Lugares, tmp_path: Path) -> None:
    """D-1911-A-EXTENSAO-SO-SUBSTITUI-A-DA-MESMA-ORIGEM: a de outra origem recusa antes."""
    dados = _a_da_pessoa(lg, tmp_path / "autor-a")
    antes = ler_registro(lg.registro)[ANTIGA].model_dump()
    with pytest.raises(InstalacaoRecusadaError) as recusa:
        instalador.instalar(str(_pasta(tmp_path / "autor-b", NOVA, substitui=(ANTIGA,))),
                            lugares=lg)
    assert recusa.value.frase == RECUSA
    registro = ler_registro(lg.registro)
    assert set(registro) == {ANTIGA}
    assert registro[ANTIGA].model_dump() == antes
    assert (lg.codigo / ANTIGA / "hefesto-mod.json").is_file()
    assert dados.read_text(encoding="utf-8") == "{}"
    assert not (lg.codigo / NOVA).exists()
    assert not lg.diario_dos_gestos.exists() or NOVA not in lg.diario_dos_gestos.read_text(
        encoding="utf-8")


def test_a_da_mesma_origem_herda_o_ligado_e_a_antiga_sai(lg: Lugares, tmp_path: Path) -> None:
    _a_da_pessoa(lg, tmp_path / "autor-a")
    feito = instalador.instalar(str(_pasta(tmp_path / "autor-a", NOVA, substitui=(ANTIGA,))),
                                lugares=lg)
    assert feito.substituidas == [ANTIGA]
    registro = ler_registro(lg.registro)
    assert set(registro) == {NOVA} and registro[NOVA].ligada
    assert not (lg.codigo / ANTIGA).exists() and not (lg.dados / ANTIGA).exists()


def _entrada(origem: str, endereco: str) -> Entrada:
    return Entrada(id=ANTIGA, nome="Da pessoa", versao="1", origem=origem,  # type: ignore[arg-type]
                   endereco=endereco)


@pytest.mark.parametrize(("tipo", "nova", "origem", "antiga", "mesma"), [
    ("comunidade", "https://github.com/Time/hefesto-mod-tema",
     "comunidade", "https://github.com/Time/hefesto-mod-tema-claro", True),
    ("comunidade", "git@github.com:Time/b.git",
     "comunidade", "https://GitHub.com/time/a", True),
    ("comunidade", "ssh://git@github.com:22/Time/b",
     "comunidade", "https://github.com/Time/a.git", True),
    ("comunidade", "https://github.com/outro/a",
     "comunidade", "https://github.com/Time/a", False),
    ("comunidade", "https://codeberg.org/Time/a",
     "comunidade", "https://github.com/Time/a", False),
    ("comunidade", "https://github.com/a", "comunidade", "https://github.com/b", False),
    ("comunidade", "file:///srv/autor-a/b", "comunidade", "file:///srv/autor-a/a", True),
    ("comunidade", "file:///srv/autor-b/b", "comunidade", "file:///srv/autor-a/a", False),
    ("oficial", "https://codeberg.org/x/b", "oficial", "https://github.com/y/a", True),
    ("local", "/home/x/fontes/b", "local", "/home/x/fontes/a", True),
    ("local", "/home/x/outras/b", "local", "/home/x/fontes/a", False),
    ("local", "/srv/Time/b", "comunidade", "file:///srv/Time/a", False),
])
def test_a_mesma_origem_pelo_endereco(tipo: str, nova: str, origem: str, antiga: str,
                                      mesma: bool) -> None:
    assert instalador.mesma_origem(tipo, nova, _entrada(origem, antiga)) is mesma  # type: ignore[arg-type]


@pytest.fixture
def a07(lg: Lugares, monkeypatch: pytest.MonkeyPatch) -> Any:
    sys.path.insert(0, str(INTERFACE))
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    monkeypatch.setattr(a07_lancadores.VIGIA, "_disparar", lambda: None)
    a07_lancadores.REGISTRO.esquecer()
    a07_lancadores._MEXIDA.limpar()
    yield a07_lancadores
    a07_lancadores.REGISTRO.esquecer()
    a07_lancadores._MEXIDA.limpar()


def test_a_aba_diz_que_ficou_ligada_no_lugar_da_antiga(a07: Any, lg: Lugares,
                                                     tmp_path: Path) -> None:
    _a_da_pessoa(lg, tmp_path / "autor-a")
    recado = a07._instalar_a_modificacao(
        str(_pasta(tmp_path / "autor-a", NOVA, substitui=(ANTIGA,))))
    assert recado == ("De outro autor instalada. Saiu a Da pessoa. "
                      "Ficou ligada no lugar da antiga.")


def test_a_recusa_fica_na_linha_de_instalar_e_a_lista_nao_muda(a07: Any, lg: Lugares,
                                                               tmp_path: Path) -> None:
    _a_da_pessoa(lg, tmp_path / "autor-a")
    origem = str(_pasta(tmp_path / "autor-b", NOVA, substitui=(ANTIGA,)))
    with pytest.raises(RuntimeError, match="veio de outro lugar"):
        a07._instalar_a_modificacao(origem)
    blocos = a07._resposta(None)["blocos"]
    assert "Não instalou</span>" in blocos["#ext-instalar"]
    assert "remova «Da pessoa» antes, se quiser." in blocos["#ext-instalar"]
    assert f'value="{origem}"' in blocos["#ext-instalar"]
    assert "Da pessoa" in blocos[".ext-lista"] and "De outro autor" not in blocos[".ext-lista"]
    a07._instalar_a_modificacao(str(_pasta(tmp_path / "autor-a", "de-outro-autor")))
    assert "tm-recusa" not in a07._resposta(None)["blocos"]["#ext-instalar"]
