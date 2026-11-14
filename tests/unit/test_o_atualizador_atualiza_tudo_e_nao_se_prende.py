"""O atualizador atualiza tudo e não se prende: as seis medidas de 14/11/2026, cada uma com régua.

O-ATUALIZADOR-ATUALIZA-TUDO-E-NAO-SE-PRENDE-01. TUDO É DE MENTIRA: o lar é ``tmp_path`` com
``XDG_*`` desviados, as peças do motor são dublês, o git é um repositório de mentira e a rede é
barrada (``trava_da_rede``). Nenhum caso roda o ajudante root nem toca a Steam.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): a marca que conta toda
linha reprova o caso da árvore que sumiu; a espera tratada como falha reprova o caso da Steam; o
código 9 lido como falha reprova o caso da cura de cima; a falha da GameInput sem o porquê da
compilação reprova o caso do 404; o andamento lido sem encerrar o órfão reprova o caso do PID
morto; a fila sem a conferência na vez da peça reprova o caso das duas rodadas; o ``__main__``
sem entregar ao módulo de nome reprova o caso da classe da falha; o Python sem a roda por pacote
reprova o caso do pacote que não monta.
"""
from __future__ import annotations

import hashlib
import os
import runpy
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa
from hefesto_dualsense4unix.app.actions import versao_ao_abrir as va


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    return casa


@pytest.fixture(autouse=True)
def trava_da_rede(monkeypatch: pytest.MonkeyPatch) -> Any:
    pedidos: list[object] = []

    def _resolver(host: object, *_a: object, **_k: object) -> list[object]:
        pedidos.append(host)
        raise OSError(f"o teste foi à rede: {host}")

    monkeypatch.setattr(socket, "getaddrinfo", _resolver)
    yield pedidos
    assert not pedidos, f"o teste foi à rede: {pedidos}"


class _Diario:
    def __init__(self) -> None:
        self.feito: list[str] = []


def _peca(d: _Diario, ident: str, *, de: str = "1.0", para: str = "1.1",
          instalar: Any = None, baixar: Any = None) -> at.Peca:
    def etapa(nome: str) -> Any:
        def fazer(passo: at.Passo, _dados: dict[str, Any]) -> dict[str, Any]:
            d.feito.append(f"{ident}:{nome}")
            passo.fracao(1.0)
            return {nome: True}
        return fazer

    return at.Peca(ident, ident.upper(), "dica", "todos",
                   lambda rede: at.Versoes(de, para if rede else None),
                   baixar or etapa("baixar"), instalar or etapa("instalar"), etapa("aplicar"))


def _rodar(lista: list[at.Peca], ids: list[str], **k: Any) -> tuple[int, list[str]]:
    servico: list[str] = []

    def anotar(o_que: str) -> bool:
        servico.append(o_que)
        return True

    rc = at.rodar(ids, lista=lista, jogo_aberto=k.pop("jogo_aberto", lambda: False),
                  reiniciar=lambda: anotar("reiniciar"), reabrir=lambda: anotar("reabrir"),
                  dormir=k.pop("dormir", lambda _s: None), **k)
    return rc, servico


def _linha(ident: str) -> dict[str, Any]:
    return next(p for p in at.ler_o_andamento()["pecas"] if p["id"] == ident)


def _git(pasta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(pasta), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var, valor in (("GIT_CONFIG_GLOBAL", os.devnull), ("GIT_CONFIG_NOSYSTEM", "1"),
                       ("GIT_AUTHOR_NAME", "t"), ("GIT_AUTHOR_EMAIL", "t@t.t"),
                       ("GIT_COMMITTER_NAME", "t"), ("GIT_COMMITTER_EMAIL", "t@t.t")):
        monkeypatch.setenv(var, valor)
    pasta = tmp_path / "clone"
    subprocess.run(["git", "init", "-q", "-b", "dev", str(pasta)], check=True)
    (pasta / "README.md").write_text("x\n", encoding="utf-8")
    _git(pasta, "add", "README.md")
    _git(pasta, "commit", "-q", "-m", "início")
    return pasta


def test_a_linha_de_arvore_que_sumiu_nao_prende_e_sai_da_marca(clone: Path) -> None:
    """Medida 1: a marca com três conjuntos que sumiram prendia o Hefesto («trabalho em voo»)."""
    marca = clone / ".git" / va.MARCA_DE_VOO
    marca.write_text("tela-portal\nfio-de-fundo\ntela-monitor\n", encoding="utf-8")
    assert va.por_que_nao(clone, lambda: False) == ""
    assert marca.read_text(encoding="utf-8") == ""

    _git(clone, "worktree", "add", "-q", "-b", "voo/tela-clique",
         str(clone.parent / "voo" / "tela-clique"), "dev")
    marca.write_text("tela-portal\ntela-clique\n", encoding="utf-8")
    assert va.por_que_nao(clone, lambda: False) == va.TRABALHO_EM_VOO
    assert marca.read_text(encoding="utf-8") == "tela-clique\n"


def test_o_voo_e_espera_do_hefesto_e_nao_falha(monkeypatch: pytest.MonkeyPatch) -> None:
    """Medida 1: «em voo» é espera, com o motivo; o erro de verdade continua falha."""
    motivo = [va.TRABALHO_EM_VOO]
    monkeypatch.setattr(va, "por_que_nao", lambda _raiz, *_a: motivo[0])
    monkeypatch.setattr(va, "_install_em_curso", lambda: False)
    with pytest.raises(at.EsperaError, match="trabalho em voo") as espera:
        pa._baixar_o_hefesto(at.Passo(), {})
    assert espera.value.livre() is False
    motivo[0] = ""
    assert espera.value.livre() is True
    motivo[0] = "árvore com mudança"
    with pytest.raises(at.EtapaFalhouError, match="árvore com mudança"):
        pa._baixar_o_hefesto(at.Passo(), {})


def test_a_steam_aberta_espera_a_fila_segue_e_a_peca_aplica_ao_fechar() -> None:
    """Medida 2: a Steam aberta deixa a peça «Esperando», as outras andam, e ao fechar a peça
    volta da etapa em que parou (sem baixar de novo) e termina pronta."""
    d = _Diario()
    steam = {"aberta": True}

    def instalar(_passo: at.Passo, _dados: dict[str, Any]) -> None:
        d.feito.append("proton:instalar")
        if steam["aberta"]:
            raise at.EsperaError("a Steam está aberta", lambda: not steam["aberta"])

    voltas = [0]

    def dormir(_s: float) -> None:
        voltas[0] += 1
        assert _linha("proton")["selo"] == at.ESPERANDO
        assert _linha("proton")["motivo"] == "a Steam está aberta"
        assert _linha("b")["selo"] == at.PRONTA, "a fila não esperou a Steam para seguir"
        if voltas[0] == 3:
            steam["aberta"] = False

    lista = [_peca(d, "proton", instalar=instalar), _peca(d, "b")]
    at.conferir(rede=True, lista=lista)
    rc, servico = _rodar(lista, ["proton", "b"], dormir=dormir)
    assert rc == 0
    assert d.feito == ["proton:baixar", "proton:instalar", "b:baixar", "b:instalar", "b:aplicar",
                       "proton:instalar", "proton:aplicar"]
    assert _linha("proton")["selo"] == at.PRONTA and _linha("proton")["motivo"] == ""
    assert at.ler_o_andamento()["total"]["falhas"] == 0
    assert servico == ["reiniciar", "reabrir"]


def test_a_steam_que_nao_fecha_no_prazo_deixa_a_peca_para_a_proxima() -> None:
    d = _Diario()

    def instalar(_passo: at.Passo, _dados: dict[str, Any]) -> None:
        raise at.EsperaError("a Steam está aberta", lambda: False)

    tempo = [0.0]

    def dormir(_s: float) -> None:
        tempo[0] += 5.0

    lista = [_peca(d, "proton", instalar=instalar)]
    at.conferir(rede=True, lista=lista)
    rc, servico = _rodar(lista, ["proton"], dormir=dormir, relogio=lambda: tempo[0],
                         prazo_do_jogo_s=20.0)
    assert rc == 2 and servico == []
    linha = _linha("proton")
    assert linha["selo"] == at.FILA and linha["motivo"] == "a Steam está aberta"
    assert at.ler_o_andamento()["total"]["falhas"] == 0


def test_o_proton_espera_a_steam_nas_tres_etapas(monkeypatch: pytest.MonkeyPatch) -> None:
    """O instalar, o reinstalar e o aplicar do GE-Proton esperam a Steam; nenhum falha."""
    from hefesto_dualsense4unix.integrations import proton_pin as pp

    gate: list[str | None] = ["steam_aberta"]
    monkeypatch.setattr(pp, "_steam_gate", lambda: gate[0])
    monkeypatch.setattr(pp, "_load_conf", lambda _p: {})
    monkeypatch.setattr(pp, "pino_que_vale", lambda _c, _d=None: "GE-Proton11-12")
    monkeypatch.setattr(pp, "instalar_a_ultima_do_cache", lambda *_a, **_k: pp.Atualizacao(
        "espera_a_steam", "GE-Proton11-13", "a Steam está aberta"))
    with pytest.raises(at.EsperaError, match="a Steam está aberta") as espera:
        pa._instalar_o_proton(at.Passo(), {})
    assert espera.value.livre() is False
    gate[0] = None
    assert espera.value.livre() is True

    gate[0] = "jogo_da_steam_aberto"
    monkeypatch.setattr(pp, "list_installed_appids", lambda *_a, **_k: [])
    monkeypatch.setattr(pp, "lock_proton_for_all_games", lambda **_k: {
        "status": "recusado", "reason": "jogo_da_steam_aberto"})
    with pytest.raises(at.EsperaError, match="há um jogo da Steam aberto"):
        pa._aplicar_o_proton(at.Passo(), {})


def test_a_versao_de_cima_que_ja_traz_a_cura_e_atualizado(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Medida 3: o ajudante sai com 9 («a versão de cima já traz a cura»): a peça fica
    «Atualizado», o serviço não reinicia, e a mesma versão não se oferece de novo."""
    ajudante = tmp_path / "atualizador-raiz"
    ajudante.write_text("", encoding="utf-8")
    monkeypatch.setattr(pa, "AJUDANTE", ajudante)
    chamados: list[list[str]] = []

    def comando(argv: Any, **_k: Any) -> tuple[int, str]:
        chamados.append(list(argv))
        return 9, "a versão de cima já traz a cura"

    monkeypatch.setattr(pa, "_comando", comando)
    construir, instalar, aplicar, voltar = pa._etapas_da_casa("portal")
    portal = at.Peca("portal", "Portal do COSMIC", "dica", "No próximo início",
                     lambda _rede: at.Versoes("1.11.0", "1.11.0", nova=True,
                                              completa="1.11.0+0~hefesto1 → 1.11.0~179"),
                     construir, instalar, aplicar, voltar)
    assert at.conferir(rede=True, lista=[portal])["pecas"][0]["estado"] == at.NOVA
    rc, servico = _rodar([portal], ["portal"])
    assert rc == 0 and servico == []
    linha = _linha("portal")
    assert linha["selo"] == at.ATUALIZADA and linha["motivo"] == "a versão de cima já traz a cura"
    assert linha["etapas"] == dict.fromkeys(at.ETAPAS, "")
    assert at.ler_o_andamento()["total"] == {"feitas": 1, "de": 1, "pct": 100, "falhas": 0}
    assert [c[-2:] for c in chamados] == [["backport-construir", "portal"]]
    item = at.conferir(rede=True, lista=[portal])["pecas"][0]
    assert item["estado"] == at.EM_DIA and item["dica"] == "a versão de cima já traz a cura"
    assert at.novas(at.ler_a_conferencia()) == []


def test_o_404_da_gameinput_falha_com_o_porque_de_cada_caminho(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Medida 4: o release sem o arquivo dá 404, e sem o compilador a falha diz isso, em vez de
    «a compilação aqui não deu o sha256 do pino»."""
    pino = {"name": "peca-gdk-1", "url": "https://x/v{versao}/xgameruntime.dll",
            "sha256": "1" * 64, "gameinput_url": "https://x/v{versao}/gameinput.dll",
            "gameinput_sha256": "2" * 64}
    monkeypatch.setattr(pa, "_pino_da_gdk", lambda: pino)
    monkeypatch.setattr(pa, "_pasta_da_gdk", lambda: tmp_path / "peca")
    monkeypatch.setattr(pa, "_da_release_com_a_soma", lambda _a, _s: "")

    def baixar(url: str, _destino: Path, _passo: at.Passo, _sha: str = "") -> None:
        raise at.EtapaFalhouError(f"o download de {url} parou: HTTP Error 404: Not Found")

    monkeypatch.setattr(pa, "_baixar", baixar)
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _nome: None)
    with pytest.raises(at.EtapaFalhouError) as falha:
        pa._baixar_a_gdk(at.Passo(), {})
    assert "HTTP Error 404" in str(falha.value)
    assert f"sem o {pa.COMPILADOR_DA_GDK} para compilar aqui" in str(falha.value)
    assert "não deu o sha256" not in str(falha.value)


def test_a_gameinput_que_ja_bate_com_o_pino_nao_baixa(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A cópia instalada que já é a do pino serve: nada vai à rede, e a reinstalação se faz."""
    dados = {"xgameruntime.dll": b"MZ peca", "gameinput.dll": b"MZ gameinput"}
    pino = {"name": "peca-gdk-1", "url": "https://x/xgameruntime.dll",
            "sha256": hashlib.sha256(dados["xgameruntime.dll"]).hexdigest(),
            "gameinput_url": "https://x/gameinput.dll",
            "gameinput_sha256": hashlib.sha256(dados["gameinput.dll"]).hexdigest()}
    casa = tmp_path / "peca"
    for arquivo, _c, _u, destino in pa.ARQUIVOS_DA_GDK:
        casa.joinpath(*destino).parent.mkdir(parents=True, exist_ok=True)
        casa.joinpath(*destino).write_bytes(dados[arquivo])
    monkeypatch.setattr(pa, "_pino_da_gdk", lambda: pino)
    monkeypatch.setattr(pa, "_pasta_da_gdk", lambda: casa)
    monkeypatch.setattr(pa, "_baixar", lambda *_a, **_k: pytest.fail("baixou o que já tinha"))
    pa._baixar_a_gdk(at.Passo(), {})
    pa._reinstalar_a_gdk(at.Passo(), {})
    assert (casa / "x86_64-windows" / "xgameruntime.dll").read_bytes() == b"MZ peca"


def test_o_andamento_de_um_processo_morto_nao_prende_a_tela() -> None:
    """Medida 6: «espera o jogo» desde 04:52 com um PID que não existe: ao ler, o andamento se
    encerra (parado, visto, o que estava em curso de volta à fila) e a tela não fica presa."""
    from hefesto_dualsense4unix.interface.pacotes import atualizacoes as gestos

    orfao = {"fase": at.ESPERA_O_JOGO, "inicio": 1000.0, "pid": 2 ** 22 + 7, "pecas": [
        {"id": "hefesto", "nome": "Hefesto", "selo": at.FALHOU, "motivo": "x", "pct": 40,
         "etapas": {"baixar": "feito", "instalar": "erro", "aplicar": ""}},
        {"id": "nvidia", "nome": "Driver Nvidia", "selo": at.INSTALANDO, "pct": 50,
         "etapas": {"baixar": "feito", "instalar": "agora", "aplicar": ""}},
        {"id": "sistema", "nome": "Pacotes", "selo": at.FILA, "pct": 0, "etapas": {}}],
        "reinicio": {"etapas": {}, "pct": 0, "selo": at.FILA}}
    at._gravar_json(at._estado() / at.ARQUIVO_DO_ANDAMENTO, orfao)
    lido = at.ler_o_andamento()
    assert lido["fase"] == at.PARADO and lido["visto"] is True
    assert [p["selo"] for p in lido["pecas"]] == [at.FALHOU, at.FILA, at.FILA]
    assert lido["pecas"][1]["etapas"]["instalar"] == ""
    assert at._ler_json(at._estado() / at.ARQUIVO_DO_ANDAMENTO)["fase"] == at.PARADO
    assert gestos.conteudo(None, agora=1010.0) == ""

    vivo = {**orfao, "fase": at.ANDANDO}
    at._gravar_json(at._estado() / at.ARQUIVO_DO_ANDAMENTO, vivo)
    trava = at._a_trava()
    assert trava is not None
    try:
        assert at.ler_o_andamento()["fase"] == at.ANDANDO, "a fila viva não se encerra"
    finally:
        os.close(trava)


def test_duas_rodadas_seguidas_a_segunda_nao_faz_nada() -> None:
    """Idempotente: depois da primeira, nada é novo; e a fila com a conferência velha confere a
    peça na sua vez e não baixa o que já está na máquina, nem reinicia o serviço."""
    d = _Diario()
    versao = {"a": "1.0"}

    def baixar(_p: at.Passo, _x: dict[str, Any]) -> None:
        d.feito.append("a:baixar")

    def instalar(_p: at.Passo, _x: dict[str, Any]) -> None:
        versao["a"] = "1.1"
        d.feito.append("a:instalar")

    a = at.Peca("a", "A", "dica", "todos", lambda _rede: at.Versoes(versao["a"], "1.1"),
                baixar, instalar, None)
    at.conferir(rede=True, lista=[a])
    ids = at.novas(at.ler_a_conferencia())
    assert ids == ["a"]
    rc, servico = _rodar([a], ids)
    assert rc == 0 and d.feito == ["a:baixar", "a:instalar"] and servico == ["reiniciar", "reabrir"]
    assert at.novas(at.ler_a_conferencia()) == []

    versao["a"] = "1.0"
    at.conferir(rede=True, lista=[a])
    versao["a"] = "1.1"
    rc, servico = _rodar([a], ["a"])
    assert rc == 0 and d.feito == ["a:baixar", "a:instalar"] and servico == []
    assert _linha("a")["selo"] == at.ATUALIZADA
    assert at.ler_o_andamento()["reinicio"]["selo"] == at.ATUALIZADA


@pytest.mark.filterwarnings("ignore:.*found in sys.modules.*:RuntimeWarning")
def test_a_falha_de_uma_peca_chega_ao_motor_rodado_por_python_m(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """``python -m …atualizador --rodar`` roda o módulo como ``__main__``: a falha que a peça
    levanta (a classe do módulo de nome) não era a do ``__main__``, e toda falha virava «levantou».
    O ``__main__`` entrega ao módulo de nome, e a classe é uma só."""
    monkeypatch.setattr(pa, "registro", lambda: [])
    pedidos: list[list[str]] = []

    def rodar(ids: list[str], **_k: Any) -> int:
        pedidos.append(list(ids))
        return 7

    monkeypatch.setattr(at, "rodar", rodar)
    monkeypatch.setattr(sys, "argv", ["atualizador", "--rodar", "proton"])
    with pytest.raises(SystemExit) as saida:
        runpy.run_module(at.MODULO, run_name="__main__", alter_sys=False)
    assert saida.value.code == 7 and pedidos == [["proton"]]


def test_o_python_que_nao_monta_um_pacote_sobe_os_outros(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Medida 5: o pacote só em fonte que não monta aqui fica na versão de agora, com o porquê no
    registro; os outros sobem, e a mesma versão dele não se oferece de novo."""
    atrasadas = {"evdev": ("1.9.3", "2.0.0"), "rich": ("13.0", "14.0")}
    monkeypatch.setattr(pa, "_saida", lambda _argv: "[" + ",".join(
        f'{{"name": "{n}", "version": "{v}", "latest_version": "{u}"}}'
        for n, (v, u) in atrasadas.items()) + "]")
    monkeypatch.setattr(pa, "_dependencias_do_produto", lambda: ["evdev", "rich"])
    pedidos: list[list[str]] = []

    def pip(*args: str, linha: Any = None) -> tuple[int, str]:
        pedidos.append(list(args))
        if any(a.startswith("evdev==2.0.0") for a in args):
            return 1, "ERROR: Failed to build 'evdev' when installing build dependencies"
        return 0, ""

    monkeypatch.setattr(pa, "_pip", pip)
    dados = pa._baixar_o_python(at.Passo(), {})
    assert dados == {"pacotes": {"rich": ["13.0", "14.0"]}}
    assert ["wheel", "--no-deps", "--no-build-isolation", "--wheel-dir",
            str(pa._pasta_do_python()), "evdev==2.0.0"] in pedidos
    assert set(pa._atrasadas()) == {"rich"}
    atrasadas["evdev"] = ("1.9.3", "2.0.1")
    assert set(pa._atrasadas()) == {"evdev", "rich"}
    assert at._de_para(at.Versoes("", "6", rotulo="6 pacotes")) == "6 pacotes", \
        "o registro dizia «python:  -> 6 pronta»"
