"""A versão de fora espera a quarentena antes de subir sozinha; pela janela, sobe na hora.

A-VERSAO-DE-FORA-ESPERA-A-QUARENTENA-ANTES-DE-SUBIR-SOZINHA-01 (19/11/2026). TUDO É DE MENTIRA: o
lar é ``tmp_path`` com ``XDG_*`` desviados, a release do GitHub e o ``pip`` são dublês, e a rede é
barrada. Nenhum caso abre unidade nem baixa nada.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o ``published_at`` sem
leitura reprova o caso da release de um dia; as novas sem o filtro reprovam o mesmo caso; o pip
sem o ``--uploaded-prior-to`` reprova o caso do pip; a linha sem a idade reprova o caso da tela;
o vigia do Proton sem a quarentena reprova o caso do Proton. Em 20/11/2026, as do download e do
recuo: o download do MangoHud e do umu sem o corte, o do Proton sem o corte e a release sem data
aceita reprovam o caso do download; o recuo de uma roda por vez, a roda de antes e a volta pelo
índice sem o corte reprovam o caso do recuo.
"""
from __future__ import annotations

import json
import shutil
import socket
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa
from hefesto_dualsense4unix.integrations import proton_pin as pp
from hefesto_dualsense4unix.interface import atualizacoes as tela
from hefesto_dualsense4unix.interface.pacotes import atualizacoes as gestos

AGORA = datetime(2026, 11, 19, 12, 0, tzinfo=UTC).timestamp()


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))

    def _sem_rede(host: object, *_a: object, **_k: object) -> list[object]:
        raise OSError(f"o teste foi à rede: {host}")

    monkeypatch.setattr(socket, "getaddrinfo", _sem_rede)
    return casa


def _iso(segundos: float) -> str:
    return datetime.fromtimestamp(segundos, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _conferir_o_mangohud(monkeypatch: pytest.MonkeyPatch, dias: float) -> dict[str, Any]:
    release = {"tag_name": "v0.8.5", "published_at": _iso(AGORA - dias * at.DIA_S)}
    monkeypatch.setattr(pa, "_release", lambda _repo: release)
    monkeypatch.setattr(pa.shutil, "which", lambda _nome: None)
    peca = at.Peca("mangohud", "MangoHud", "dica", "todos", pa.versoes_do_mangohud)
    return at.conferir(rede=True, lista=[peca], agora=lambda: AGORA)


@pytest.mark.parametrize(("dias", "quarentena", "sozinha"), [
    (1, 3, False), (4, 3, True), (1, 0, True), (0.01, 3, False)])
def test_a_subida_automatica_espera_a_quarentena_e_a_janela_nao(
        monkeypatch: pytest.MonkeyPatch, dias: float, quarentena: int, sozinha: bool) -> None:
    """D-1911-A-VERSAO-DE-FORA-ESPERA-TRES-DIAS: a versão de fora sobe sozinha só depois da
    quarentena; zero é na hora, e a janela não espera."""
    at.gravar_a_escolha(at.Escolha(sozinho=True, quarentena=quarentena))
    conferencia = _conferir_o_mangohud(monkeypatch, dias)
    item = conferencia["pecas"][0]
    assert item["estado"] == at.NOVA
    assert item["publicada_em"] == pytest.approx(AGORA - dias * at.DIA_S, abs=1)
    escolha = at.ler_a_escolha()
    assert at.novas(conferencia, escolha, sozinha_em=AGORA) == (["mangohud"] if sozinha else [])
    assert at.novas(conferencia, escolha) == ["mangohud"]
    assert at.novas(conferencia, escolha, so_marcadas=False) == ["mangohud"]


def test_a_quarentena_de_fabrica_e_de_tres_dias_e_mora_no_atualizador_json() -> None:
    assert at.ler_a_escolha().quarentena == 3
    at.gravar_a_escolha(at.Escolha(quarentena=0))
    assert at.ler_a_escolha().quarentena == 0
    assert json.loads((at._config() / at.ARQUIVO_DA_ESCOLHA).read_text())["quarentena"] == 0


def test_o_vigia_solta_a_fila_sozinha_e_o_rodar_leva_o_corte(
        monkeypatch: pytest.MonkeyPatch) -> None:
    abertos: list[list[str]] = []
    assert at.soltar(["proton"], abrir=lambda argv, **_k: abertos.append(list(argv)),
                     sozinha=True)
    assert abertos[-1][-2:] == ["--sozinha", "proton"]
    assert at.soltar(["proton"], abrir=lambda argv, **_k: abertos.append(list(argv)))
    assert "--sozinha" not in abertos[-1]
    assert at.conferir_ao_abrir.__kwdefaults__["soltar_"] is at.soltar_sozinha
    recebido: dict[str, Any] = {}
    monkeypatch.setattr(at, "rodar", lambda ids, **kw: recebido.update(kw, ids=ids) or 0)
    at.main(["--rodar", "--sozinha", "python"])
    assert recebido["ids"] == ["python"]
    assert recebido["corte"] == pytest.approx(time.time() - 3 * at.DIA_S, abs=60)
    at.main(["--rodar", "python"])
    assert recebido["corte"] is None


def test_o_pip_da_subida_automatica_recebe_o_corte(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-A-VERSAO-DE-FORA-ESPERA-TRES-DIAS: o pip da subida automática só vê o que saiu
    antes do corte; o da janela vê tudo."""
    chamados: list[list[str]] = []

    def saida(argv: list[str]) -> str:
        chamados.append(list(argv))
        return json.dumps([{"name": "evdev", "version": "1.9.3", "latest_version": "2.0.0"}])

    def pip(*args: str, **_k: Any) -> tuple[int, str]:
        chamados.append(list(args))
        return 0, ""

    monkeypatch.setattr(pa, "_saida", saida)
    monkeypatch.setattr(pa, "_pip", pip)
    monkeypatch.setattr(pa, "_dependencias_do_produto", lambda: ["evdev"])
    corte = AGORA - 3 * at.DIA_S
    pa._baixar_o_python(at.Passo(), {"corte": corte})
    lista, roda = chamados[0], chamados[1]
    assert lista[lista.index("--uploaded-prior-to") + 1] == "2026-11-16T12:00:00Z"
    assert roda[roda.index("--uploaded-prior-to") + 1] == "2026-11-16T12:00:00Z"
    chamados.clear()
    pa._baixar_o_python(at.Passo(), {})
    assert not any("--uploaded-prior-to" in c for c in chamados)


def test_a_linha_mostra_a_idade_e_a_dica_a_data_de_subir_sozinha() -> None:
    """D-1911-A-VERSAO-DE-FORA-ESPERA-TRES-DIAS: a idade ao lado da versão, e a data em que sobe
    sozinha na dica."""
    agora = time.mktime((2026, 11, 19, 12, 0, 0, 0, 0, -1))
    publicada = time.mktime((2026, 11, 18, 9, 0, 0, 0, 0, -1))
    conferencia = {"pecas": [{"id": "proton", "nome": "GE-Proton", "estado": at.NOVA,
                              "dica": "Os jogos da Steam e do Heroic", "de": "11-7",
                              "para": "11-12", "publicada_em": publicada}]}
    vista = gestos._com_a_escolha(conferencia, at.Escolha(sozinho=True, quarentena=3),
                                  agora=agora)
    html = tela.html_do_mapa(vista)
    dica = "Publicada em 18/11 · Sobe sozinha em 21/11"
    assert (f'<span style="color:var(--texto-mudo);margin-right:12px" data-dica="{dica}">'
            f'1 dia</span>11-7') in html
    assert f'data-dica="Os jogos da Steam e do Heroic · 11-7 → 11-12 · {dica}"' in html
    desligada = tela.html_do_mapa(gestos._com_a_escolha(conferencia, at.Escolha(), agora=agora))
    assert 'data-dica="Publicada em 18/11">1 dia</span>' in desligada
    assert "Sobe sozinha" not in desligada
    em_dia = {"pecas": [{**vista["pecas"][0], "estado": at.EM_DIA}]}
    assert "1 dia" not in tela.html_do_mapa(em_dia)
    passou = gestos._com_a_escolha(conferencia, at.Escolha(sozinho=True, quarentena=3),
                                   agora=agora + 3 * at.DIA_S)
    assert "Sobe sozinha" not in tela.html_do_mapa(passou)
    assert ">4 dias</span>" in tela.html_do_mapa(passou)


def test_o_vigia_do_proton_espera_a_quarentena_e_a_janela_baixa(tmp_path: Path) -> None:
    """D-1911-A-VERSAO-DE-FORA-ESPERA-TRES-DIAS: o --manter do Proton também espera."""
    release = {"published_at": _iso(time.time() - at.DIA_S), "assets": [
        {"name": "GE-Proton11-12-x86_64.tar.gz", "browser_download_url": "https://x/t.tar.gz"},
        {"name": "GE-Proton11-12-x86_64.sha512sum", "browser_download_url": "https://x/s"}]}
    baixados: list[str] = []

    def ler(url: str) -> bytes:
        if url == pp.GE_ULTIMA_API:
            return json.dumps(release).encode()
        raise OSError("a soma não vem no teste")

    feito = pp.baixar_a_ultima_do_ge(tmp_path / "cache", ler=ler,
                                     baixar=lambda url, _d: baixados.append(url))
    assert feito.estado == "em_quarentena"
    assert "GE-Proton11-12-x86_64 sobe sozinha em" in feito.detalhe
    pedida = pp.baixar_a_ultima_do_ge(tmp_path / "cache", ler=ler, forcar=True,
                                      baixar=lambda url, _d: baixados.append(url))
    assert pedida.estado == "nao_consultado" and "sha512" in pedida.detalhe


def _release_de_fora(dias: float | None, tag: str) -> dict[str, Any]:
    publicada = {} if dias is None else {"published_at": _iso(time.time() - dias * at.DIA_S)}
    return {"tag_name": tag, **publicada, "assets": [
        {"name": f"MangoHud-{tag}.tar.gz", "browser_download_url": "https://x/m",
         "digest": "sha256:" + "0" * 64},
        {"name": f"umu-launcher-{tag}-zipapp.tar", "browser_download_url": "https://x/u",
         "digest": "sha256:" + "0" * 64},
        {"name": f"GE-Proton{tag}-x86_64.tar.gz", "browser_download_url": "https://x/t.tar.gz"},
        {"name": f"GE-Proton{tag}-x86_64.sha512sum", "browser_download_url": "https://x/s"}]}


@pytest.mark.parametrize("dias", [1, None])
def test_o_download_da_subida_automatica_so_leva_o_que_passou_a_quarentena(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dias: float | None) -> None:
    """D-1911-A-VERSAO-DE-FORA-ESPERA-TRES-DIAS: a versão publicada depois da conferência (ou sem
    data) não se baixa na subida automática; a velha e a pedida pela janela, sim."""
    corte = time.time() - 3 * at.DIA_S
    baixados: list[str] = []
    monkeypatch.setattr(pa, "_baixar", lambda url, *_a, **_k: baixados.append(url))
    release = _release_de_fora(dias, "11-13")
    monkeypatch.setattr(pa, "_release", lambda _repo: release)

    def ler(url: str) -> bytes:
        if url == pp.GE_ULTIMA_API:
            return json.dumps(release).encode()
        raise OSError("a soma não vem no teste")

    real = pp.baixar_a_ultima_do_ge
    monkeypatch.setattr(pp, "baixar_a_ultima_do_ge",
                        lambda _cache, **kw: real(tmp_path / "cache", ler=ler, **kw))
    for baixar in (pa._baixar_o_mangohud, pa._baixar_o_umu, pa._baixar_o_proton):
        with pytest.raises(at.NadaAFazerError):
            baixar(at.Passo(), {"corte": corte})
    assert baixados == []
    pa._baixar_o_mangohud(at.Passo(), {})
    pa._baixar_o_umu(at.Passo(), {})
    assert baixados == ["https://x/m", "https://x/u"]
    with pytest.raises(at.EtapaFalhouError, match="sha512"):
        pa._baixar_o_proton(at.Passo(), {})
    release.update(_release_de_fora(4, "11-13"))
    pa._baixar_o_mangohud(at.Passo(), {"corte": corte})
    with pytest.raises(at.EtapaFalhouError, match="sha512"):
        pa._baixar_o_proton(at.Passo(), {"corte": corte})


def test_o_recuo_do_pip_leva_o_corte_da_quarentena(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-A-VERSAO-DE-FORA-ESPERA-TRES-DIAS: o conjunto que não monta cai para uma roda por
    vez, e cada pip que vai ao índice (as rodas, o build isolado e a volta) leva o corte."""
    chamados: list[list[str]] = []
    monkeypatch.setattr(pa, "_saida", lambda _argv: json.dumps(
        [{"name": "evdev", "version": "1.9.3", "latest_version": "2.0.0"},
         {"name": "pydantic", "version": "2.13.5", "latest_version": "2.14.3"}]))
    monkeypatch.setattr(pa, "_dependencias_do_produto", lambda: ["evdev", "pydantic"])

    def pip(*args: str, **_k: Any) -> tuple[int, str]:
        chamados.append(list(args))
        return (1, "o conjunto não monta") if len([a for a in args if "==" in a]) > 1 else (0, "")

    monkeypatch.setattr(pa, "_pip", pip)
    corte = AGORA - 3 * at.DIA_S
    pa._baixar_o_python(at.Passo(), {"corte": corte})
    rodas = [c for c in chamados if c[0] == "wheel"]
    assert len([c for c in rodas if "--no-deps" in c]) == 4
    assert all(c[c.index("--uploaded-prior-to") + 1] == "2026-11-16T12:00:00Z" for c in rodas)
    chamados.clear()
    shutil.rmtree(pa._pasta_do_python())
    pa._voltar_as_de_antes({"evdev": ["1.9.3", "2.0.0"]}, corte)
    pa._baixar_o_python(at.Passo(), {})
    assert chamados[0][-3:-1] == ["--uploaded-prior-to", "2026-11-16T12:00:00Z"]
    assert not any("--uploaded-prior-to" in c for c in chamados[1:])
