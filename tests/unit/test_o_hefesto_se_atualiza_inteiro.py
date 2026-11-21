"""O Hefesto se atualiza inteiro: o motor das peças, a fila de uma por vez e as peças da volta 1.

O-HEFESTO-SE-ATUALIZA-INTEIRO-01, volta 1 (08/11/2026). TUDO É DE MENTIRA: o lar é ``tmp_path``
com ``XDG_*`` desviados, as peças do motor são dublês, a rede é um dicionário e o ajudante root
é um arquivo vazio cujo ``sudo`` nunca roda (o ``_comando`` das peças é dublado). Teste que vai à
rede reprova pela ``trava_da_rede``.

AS MORDIDAS (feitas na sprint, com a cura devolvida): a versão comparada como texto reprova o
caso do ``5.9`` contra o ``5.10``; o vigia que diz «em dia» sem rede reprova o caso sem rede; a
fila que para na primeira falha reprova o caso da falha; a espera do jogo arrancada reprova o
caso do jogo aberto; a trava de um processo arrancada reprova o caso da segunda fila; a segurada
ignorada reprova o caso do voltar; o umu que extrai caminho de fora reprova o caso do tar mau; o
download sem conferir a soma reprova o caso do sha256 errado; o voltar que chama a peça direto
reprova o caso do jogo aberto e da fila rodando.

O ELO DO PACOTE DO UMU (21/11/2026): o zipapp 1.4.4 traz ``umu/umu_run.py -> umu-run`` e o dublê
passou a ter essa forma. A recusa de todo elo reprova o caso do instalar; o elo aceito sem
conferir o alvo reprova o caso do elo que aponta para fora.
"""
from __future__ import annotations

import io
import json
import os
import socket
import tarfile
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa
from hefesto_dualsense4unix.app.actions import versao_ao_abrir as va
from tests.unit import test_o_avanco_do_dev_so_com_commit_assinado as assinado

Casa = assinado.Casa
casa = assinado.casa
base = assinado.base
_chave = assinado._chave
_git = assinado._git


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    ajudante = casa / "atualizador-raiz"
    ajudante.touch()
    monkeypatch.setattr(pa, "AJUDANTE", ajudante)
    return casa


@pytest.fixture(autouse=True)
def trava_da_rede(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    pedidos: list[object] = []
    conectar = socket.socket.connect

    def _conectar(sock: socket.socket, endereco: object) -> None:
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            pedidos.append(endereco)
            raise OSError(f"o teste do atualizador foi à rede: {endereco}")
        conectar(sock, endereco)

    def _resolver(host: object, *_a: object, **_k: object) -> list[object]:
        pedidos.append(host)
        raise OSError(f"o teste do atualizador foi à rede: {host}")

    monkeypatch.setattr(socket.socket, "connect", _conectar)
    monkeypatch.setattr(socket, "getaddrinfo", _resolver)
    yield pedidos
    assert not pedidos, f"o teste foi à rede: {pedidos}"


class _Diario:
    def __init__(self) -> None:
        self.feito: list[str] = []


def _peca(diario: _Diario, ident: str, *, de: str = "1.0", para: str | None = "1.1",
          falha_em: str = "", volta: int = 1, voltar: bool = False) -> at.Peca:
    def etapa(nome: str) -> Any:
        def fazer(passo: at.Passo, dados: dict[str, Any]) -> dict[str, Any]:
            diario.feito.append(f"{ident}:{nome}")
            passo.fracao(0.5)
            if nome == falha_em:
                raise at.EtapaFalhouError(f"{ident} quebrou no {nome}")
            return {nome: True}
        return fazer

    def voltar_(anterior: dict[str, Any]) -> None:
        diario.feito.append(f"{ident}:voltar:{anterior.get('anterior')}")

    return at.Peca(ident, ident.upper(), "dica", "todos",
                   lambda rede: at.Versoes(de, para if rede else None),
                   etapa("baixar"), etapa("instalar"), etapa("aplicar"),
                   voltar_ if voltar else None, volta=volta)


def _rodar(lista: list[at.Peca], ids: list[str], **k: Any) -> tuple[int, list[str]]:
    servico: list[str] = []
    at.conferir(rede=True, lista=lista)
    rc = at.rodar(ids, lista=lista, jogo_aberto=k.pop("jogo_aberto", lambda: False),
                  reiniciar=lambda: servico.append("reiniciar") or True,
                  reabrir=lambda: servico.append("reabrir") or True,
                  dormir=k.pop("dormir", lambda _s: None), **k)
    return rc, servico


def test_a_versao_se_compara_por_partes() -> None:
    assert at.ordem("5.9") < at.ordem("5.10")
    assert at.ordem("11-7") < at.ordem("11-12")
    assert at.ordem("0.9.5.1") < at.ordem("0.9.5.2")
    assert at.Versoes("5.9", "5.10").tem_nova()
    assert not at.Versoes("5.10", "5.9").tem_nova()


def test_sem_rede_o_vigia_diz_nao_consultado_e_nunca_em_dia() -> None:
    d = _Diario()

    def quebra(_rede: bool) -> at.Versoes:
        raise RuntimeError("a fonte caiu")

    lista = [_peca(d, "a"), at.Peca("b", "B", "dica", "x", quebra),
             _peca(d, "bt", volta=2)]
    estados = {i["id"]: i for i in at.conferir(rede=False, lista=lista)["pecas"]}
    assert estados["a"]["estado"] == at.NAO_CONSULTADO
    assert estados["b"]["estado"] == at.NAO_CONSULTADO
    assert estados["b"]["dica"] == "a fonte caiu"
    assert estados["bt"]["estado"] == at.FIXA
    com_rede = {i["id"]: i["estado"] for i in at.conferir(rede=True, lista=lista)["pecas"]}
    assert com_rede["a"] == at.NOVA


def test_a_fila_roda_uma_peca_por_vez_e_reinicia_no_fim() -> None:
    """Prova da D-0811-O-HEFESTO-SE-ATUALIZA-INTEIRO-VOLTA-1: uma peça por vez, na ordem do
    registro e não na de quem pede, serviço no fim."""
    d = _Diario()
    lista = [_peca(d, "a"), _peca(d, "b")]
    rc, servico = _rodar(lista, ["b", "a"])
    assert rc == 0
    assert d.feito == ["a:baixar", "a:instalar", "a:aplicar", "b:baixar", "b:instalar",
                       "b:aplicar"]
    assert servico == ["reiniciar", "reabrir"]
    andamento = at.ler_o_andamento()
    assert andamento["fase"] == at.FIM
    assert [p["selo"] for p in andamento["pecas"]] == [at.PRONTA, at.PRONTA]
    assert andamento["total"] == {"feitas": 2, "de": 2, "pct": 100, "falhas": 0}
    assert andamento["reinicio"]["selo"] == at.PRONTA
    assert andamento["pecas"][0]["etapas"] == dict.fromkeys(at.ETAPAS, "feito")


def test_a_peca_que_falha_nao_para_as_outras_e_diz_o_porque() -> None:
    d = _Diario()
    lista = [_peca(d, "a", falha_em="instalar"), _peca(d, "b")]
    rc, servico = _rodar(lista, ["a", "b"])
    assert rc == 1
    assert "b:aplicar" in d.feito and "a:aplicar" not in d.feito
    a = at.ler_o_andamento()["pecas"][0]
    assert a["selo"] == at.FALHOU
    assert a["motivo"] == "a quebrou no instalar"
    assert a["etapas"] == {"baixar": "feito", "instalar": "erro", "aplicar": ""}
    assert at.ler_o_andamento()["total"]["falhas"] == 1
    assert servico == ["reiniciar", "reabrir"]


def test_com_jogo_aberto_nada_roda_ate_ele_fechar() -> None:
    d = _Diario()
    lista = [_peca(d, "a")]
    rc, servico = _rodar(lista, ["a"], jogo_aberto=lambda: True, prazo_do_jogo_s=0.0)
    assert rc == 2 and d.feito == [] and servico == []
    assert at.ler_o_andamento()["fase"] == at.PARADO

    tempo = [0.0]
    perguntas = iter([True, True, False, False, False, False, False, False, False, False])

    def dormir(s: float) -> None:
        tempo[0] += 5.0

    rc, _ = _rodar(lista, ["a"], jogo_aberto=lambda: next(perguntas, False),
                   relogio=lambda: tempo[0], dormir=dormir)
    assert rc == 0 and d.feito == ["a:baixar", "a:instalar", "a:aplicar"]


def test_uma_fila_por_vez(monkeypatch: pytest.MonkeyPatch) -> None:
    d = _Diario()
    lista = [_peca(d, "a")]
    trava = at._a_trava()
    assert trava is not None
    try:
        assert at.em_curso()
        rc, _ = _rodar(lista, ["a"])
        assert rc == 3 and d.feito == []
    finally:
        import os

        os.close(trava)
    assert not at.em_curso()


def test_parar_sai_entre_duas_etapas() -> None:
    d = _Diario()

    def baixar(passo: at.Passo, _dados: dict[str, Any]) -> None:
        d.feito.append("a:baixar")
        at.pedir_para_parar()

    lista = [at.Peca("a", "A", "", "", lambda r: at.Versoes("1", "2"), baixar,
                     lambda p, x: d.feito.append("a:instalar"), None)]
    rc, servico = _rodar(lista, ["a"])
    assert rc == 2 and d.feito == ["a:baixar"] and servico == []
    assert at.ler_o_andamento()["fase"] == at.PARADO


def test_a_anterior_se_guarda_e_o_voltar_segura_a_que_saiu() -> None:
    d = _Diario()
    lista = [_peca(d, "a", de="1.0", para="1.1", voltar=True), _peca(d, "b")]
    _rodar(lista, ["a"])
    anterior = at.ler_as_anteriores()["a"]
    assert anterior["anterior"] == "1.0" and anterior["agora"] == "1.1"
    assert anterior["dados"] == {"baixar": True, "instalar": True, "aplicar": True}
    assert at.voltar("b", lista=lista) == "a peça não volta"
    assert at.voltar("a", lista=lista, jogo_aberto=lambda: False) == ""
    assert d.feito[-1] == "a:voltar:1.0"
    assert at.ler_a_escolha().seguradas == {"a": "1.1"}
    estado = {i["id"]: i["estado"] for i in at.conferir(rede=True, lista=lista)["pecas"]}
    assert estado["a"] == at.EM_DIA
    assert at.voltar("a", lista=lista) == "sem versão anterior"


def test_o_voltar_recusa_com_jogo_aberto_e_com_a_fila_rodando() -> None:
    """D-0811-O-HEFESTO-SE-ATUALIZA-INTEIRO-VOLTA-1: o voltar não derruba o jogo nem a fila."""
    d = _Diario()
    lista = [_peca(d, "a", de="1.0", para="1.1", voltar=True)]
    _rodar(lista, ["a"])
    assert at.voltar("a", lista=lista, jogo_aberto=lambda: True) == "há um jogo aberto"
    trava = at._a_trava()
    assert trava is not None
    try:
        assert at.voltar("a", lista=lista, jogo_aberto=lambda: False) \
            == "a atualização está rodando"
    finally:
        os.close(trava)
    assert not [f for f in d.feito if ":voltar" in f]
    assert at.voltar("a", lista=lista, jogo_aberto=lambda: False) == ""
    assert d.feito[-1] == "a:voltar:1.0"
    assert not at.em_curso()


def test_a_escolha_o_prazo_e_a_pergunta() -> None:
    d = _Diario()
    lista = [_peca(d, "a"), _peca(d, "b")]
    assert at.mudar_a_escolha(dias=0).dias == at.DIAS_MINIMO
    assert at.mudar_a_escolha(dias=500).dias == at.DIAS_MAXIMO
    at.mudar_a_escolha(dias=7, perguntada_em=1000.0)
    at.conferir(rede=True, lista=lista)
    assert not at.hora_da_pergunta(1000.0 + 6 * at.DIA_S)
    assert at.hora_da_pergunta(1000.0 + 7 * at.DIA_S)
    at.mudar_a_escolha(sozinho=True)
    assert not at.hora_da_pergunta(1000.0 + 7 * at.DIA_S)
    at.mudar_a_escolha(peca="b", marcada=False)
    assert at.novas(at.ler_a_conferencia()) == ["a"]
    assert at.novas(at.ler_a_conferencia(), so_marcadas=False) == ["a", "b"]


def test_com_atualizar_sozinho_o_vigia_solta_so_as_marcadas(
        monkeypatch: pytest.MonkeyPatch) -> None:
    d = _Diario()
    lista = [_peca(d, "a"), _peca(d, "b")]
    monkeypatch.setattr(at, "pecas", lambda: lista)
    at.mudar_a_escolha(sozinho=True, peca="b", marcada=False, perguntada_em=0.0)
    soltas: list[list[str]] = []
    at.conferir_ao_abrir(soltar_=lambda ids: soltas.append(list(ids)) or True,
                         agora=lambda: 10 * at.DIA_S).join(5)
    assert soltas == [["a"]]
    assert at.ler_a_escolha().perguntada_em == 10 * at.DIA_S
    at.conferir_ao_abrir(soltar_=lambda ids: soltas.append(list(ids)) or True,
                         agora=lambda: 11 * at.DIA_S).join(5)
    assert soltas == [["a"]]


def test_soltar_abre_a_fila_fora_da_janela() -> None:
    abertos: list[list[str]] = []
    assert at.soltar(["proton", "kernel"], abrir=lambda argv, **k: abertos.append(argv))
    assert abertos[0][1:] == ["-m", at.MODULO, "--rodar", "proton", "kernel"]
    assert not at.soltar([], abrir=lambda argv, **k: abertos.append(argv))


def test_o_registro_tem_as_pecas_da_volta_um_na_ordem() -> None:
    pecas = {p.id: p for p in pa.registro()}
    ordem = [p.id for p in pa.registro()]
    assert ordem.index("kernel") < ordem.index("dkms")
    assert ordem[-1] == "hefesto"
    for ident in ("proton", "bluetooth", "som", "portal", "gdk", "python", "nvidia", "kernel",
                  "dkms", "sistema", "mangohud", "umu", "hefesto"):
        assert pecas[ident].volta == 1 and pecas[ident].instalar is not None, ident


def test_o_ajudante_ausente_falha_sem_pedir_senha(monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    monkeypatch.setattr(pa, "AJUDANTE", tmp_path / "nao-existe")
    with pytest.raises(at.EtapaFalhouError, match="rode o install"):
        pa._raiz("apt-lista")


def test_o_ajudante_vai_por_sudo_sem_senha_e_a_barra_le_o_apt(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ajudante = tmp_path / "atualizador-raiz"
    ajudante.write_text("", encoding="utf-8")
    monkeypatch.setattr(pa, "AJUDANTE", ajudante)
    chamados: list[list[str]] = []

    def comando(argv: list[str], *, linha: Any = None, **_k: Any) -> tuple[int, str]:
        chamados.append(list(argv))
        for texto in ("dlstatus:1:25.0:baixando", "pmstatus:linux:80.0:instalando"):
            linha(texto)
        return 0, "ok"

    monkeypatch.setattr(pa, "_comando", comando)
    passo = at.Passo()
    pa._raiz("apt-baixar", "nvidia", passo=passo)
    assert chamados == [["sudo", "-n", str(ajudante), "apt-baixar", "nvidia"]]
    assert passo.fracao_ == pytest.approx(0.8)
    monkeypatch.setattr(pa, "_comando", lambda argv, **k: (1, "E: falta espaço"))
    with pytest.raises(at.EtapaFalhouError, match="falta espaço"):
        pa._raiz("apt-instalar", "nvidia")


APT_LIST = """Listando...
linux-system76/noble 7.2.18-76070218.2026~24.04 amd64 [atualizável de: 7.2.15-76070215.2026]
nvidia-driver-595/noble 595.110.01-1pop1 amd64 [upgradable from: 595.104.02-1pop1]
libnvidia-gl-595/noble 595.110.01-1pop1 amd64 [upgradable from: 595.104.02-1pop1]
curl/noble 8.5.0-2ubuntu10.8 amd64 [upgradable from: 8.5.0-2ubuntu10.6]
"""


def test_o_apt_diz_o_que_sobe_por_grupo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_atualizar_a_lista_do_apt", lambda rede: None)

    def saida(argv: list[str]) -> str | None:
        if argv[:2] == ["apt", "list"]:
            return APT_LIST
        if argv[0] == "dpkg-query":
            return ("nvidia-driver-595\t595.104.02-1pop1\tii \n"
                    "linux-system76\t7.2.15-76070215.2026\tii \n")
        return None

    monkeypatch.setattr(pa, "_saida", saida)
    monkeypatch.setattr(pa.os, "uname",
                        lambda: type("U", (), {"release": "7.2.15-76070215-generic"})())
    nvidia = pa.versoes_da_nvidia(True)
    assert (nvidia.instalada, nvidia.publicada, nvidia.tem_nova()) == \
        ("595.104.02", "595.110.01", True)
    kernel = pa.versoes_do_kernel(True)
    assert (kernel.instalada, kernel.publicada, kernel.tem_nova()) == ("7.2.15", "7.2.18", True)
    sistema = pa.versoes_do_sistema(True)
    assert sistema.tem_nova() and sistema.rotulo == "1 pacote"
    assert "curl" in sistema.dica and "nvidia" not in sistema.dica
    assert nvidia.completa == "595.104.02-1pop1 → 595.110.01-1pop1"
    assert kernel.completa == "7.2.15-76070215 → 7.2.18-76070218"


def test_o_segurado_e_o_da_casa_nao_contam_como_atualizacao(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_atualizar_a_lista_do_apt", lambda rede: None)
    lista = APT_LIST + ("bluez/noble 5.72-0ubuntu5.4 amd64 "
                        "[upgradable from: 5.88-0ubuntu0.1~hefesto24.04.6]\n")

    def saida(argv: list[str]) -> str | None:
        if argv[:2] == ["apt", "list"]:
            return lista
        if argv[:2] == ["apt-mark", "showhold"]:
            return "curl\n"
        return None

    monkeypatch.setattr(pa, "_saida", saida)
    assert not pa.versoes_do_sistema(True).tem_nova()


def test_o_kernel_reconstruido_no_mesmo_numero_difere_na_completa_e_nao_vira_anterior(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_atualizar_a_lista_do_apt", lambda rede: None)
    monkeypatch.setattr(pa, "_metas_do_kernel", lambda: ["linux-generic-hwe-24.04"])
    monkeypatch.setattr(pa, "_saida", lambda argv: (
        "linux-generic-hwe-24.04/noble 7.2.15-77.77 amd64 [upgradable from: 7.2.15-76.76]\n"
        if argv[:2] == ["apt", "list"] else None))
    monkeypatch.setattr(pa.os, "uname",
                        lambda: type("U", (), {"release": "7.2.15-76-generic"})())
    kernel = pa.versoes_do_kernel(True)
    assert kernel.tem_nova() and kernel.instalada == kernel.publicada == "7.2.15"
    assert kernel.completa == "7.2.15-76 → 7.2.15-77"
    peca = next(p for p in pa.registro() if p.id == "kernel")
    at._guardar_a_anterior(peca, kernel, {}, 0.0)
    assert "kernel" not in at.ler_as_anteriores()


def test_a_python_em_dia_diz_quantas_bibliotecas_conferiu(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_no_venv", lambda: True)
    monkeypatch.setattr(pa, "_dependencias_do_produto", lambda: ["evdev", "pydantic", "evdev"])
    monkeypatch.setattr(pa, "_saida", lambda argv: "[]")
    assert pa.versoes_do_python(True).rotulo == "2 bibliotecas em dia"


def test_sem_o_umu_do_hefesto_a_peca_se_oferece(monkeypatch: pytest.MonkeyPatch,
                                                tmp_path: Path) -> None:
    """D-1911-O-UMU-AUSENTE-SE-OFERECE: sem o umu do Hefesto, nenhum ou o de fora, a peça é nova."""
    monkeypatch.setattr(pa, "_release", lambda _repo: {"tag_name": "v1.4.4"})
    monkeypatch.setattr(pa.shutil, "which", lambda _nome: None)
    assert pa.versoes_do_umu(True).tem_nova()
    de_fora = tmp_path / "umu-run"
    de_fora.write_text("#!/bin/sh\necho umu-launcher version 1.2.0\n")
    de_fora.chmod(0o755)
    monkeypatch.setattr(pa.shutil, "which", lambda _nome: str(de_fora))
    monkeypatch.setattr(pa, "_saida", lambda argv: "umu-launcher version 1.2.0")
    assert pa.versoes_do_umu(True).tem_nova()
    assert pa.versoes_do_umu(False).publicada is None


def test_a_rede_que_levanta_deixa_a_instalada_na_conferencia() -> None:
    def versoes(rede: bool) -> at.Versoes:
        if rede:
            raise OSError("o GitHub não respondeu")
        return at.Versoes("1.4.4", None)

    peca = at.Peca("x", "X", "dica", "todos", versoes, lambda *_: None, lambda *_: None,
                   lambda *_: None)
    item = at.conferir(rede=True, lista=[peca])["pecas"][0]
    assert item["de"] == "1.4.4" and "GitHub" in item["dica"]


def test_os_modulos_pedem_o_rebuild_quando_falta_o_kernel_novo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    status = ("hefesto-hid-playstation/1.0.0, 7.2.15-76070215-generic, x86_64: installed\n"
              "hefesto-uhid/1.0.0, 7.2.15-76070215-generic, x86_64: installed\n"
              "hefesto-hid-playstation/1.0.0, 7.2.18-76070218-generic, x86_64: installed\n"
              "nvidia/595.104.02, 7.2.18-76070218-generic, x86_64: installed\n")
    monkeypatch.setattr(pa, "_saida", lambda argv: status if argv[0] == "dkms" else None)
    monkeypatch.setattr(pa, "_kernels_com_headers",
                        lambda: ["7.2.15-76070215-generic", "7.2.18-76070218-generic"])
    falta = pa.versoes_do_dkms(True)
    assert falta.tem_nova() and falta.instalada == "1.0.0"
    monkeypatch.setattr(pa, "_kernels_com_headers", lambda: ["7.2.15-76070215-generic"])
    assert not pa.versoes_do_dkms(True).tem_nova()


class _Resposta(io.BytesIO):
    def __init__(self, dado: bytes) -> None:
        super().__init__(dado)
        self.headers = {"Content-Length": str(len(dado))}

    def __enter__(self) -> _Resposta:
        return self

    def __exit__(self, *_a: object) -> None:
        self.close()


def test_o_download_so_fica_com_a_soma_publicada(monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    import hashlib

    dado = b"x" * 3_000_000
    monkeypatch.setattr(pa.urllib.request, "urlopen", lambda *a, **k: _Resposta(dado))
    passo = at.Passo()
    destino = tmp_path / "m.tar.gz"
    pa._baixar("https://exemplo.invalid/m", destino, passo, hashlib.sha256(dado).hexdigest())
    assert destino.read_bytes() == dado and passo.fracao_ == 1.0
    destino.unlink()
    with pytest.raises(at.EtapaFalhouError, match="sha256"):
        pa._baixar("https://exemplo.invalid/m", destino, at.Passo(), "0" * 64)
    assert not destino.exists()
    assert not list(tmp_path.glob("*.hefesto-download"))


def test_o_ativo_sem_soma_publicada_nao_se_baixa() -> None:
    release = {"assets": [
        {"name": "MangoHud-0.8.5.tar.gz", "browser_download_url": "u"},
        {"name": "MangoHud-v0.8.5-Source.tar.xz", "browser_download_url": "s",
         "digest": "sha256:" + "a" * 64}]}
    with pytest.raises(at.EtapaFalhouError):
        pa._ativo(release, pa._e_o_binario_do_mangohud)
    release["assets"][0]["digest"] = "sha256:" + "b" * 64
    assert pa._ativo(release, pa._e_o_binario_do_mangohud) == (
        "MangoHud-0.8.5.tar.gz", "u", "b" * 64)


def _tar_do_umu(caminho: Path, *, mau: bool = False, elo: str = "umu-run",
                tipo: bytes = tarfile.SYMTYPE) -> Path:
    with tarfile.open(caminho, "w") as tar:
        for nome, conteudo in (("umu/umu-run", b"#!/bin/sh\n"),
                               *([("../fora", b"x")] if mau else [])):
            info = tarfile.TarInfo(nome)
            info.size = len(conteudo)
            info.mode = 0o755
            tar.addfile(info, io.BytesIO(conteudo))
        info = tarfile.TarInfo("umu/umu_run.py")
        info.type, info.linkname = tipo, elo
        tar.addfile(info)
    return caminho


def test_o_umu_instala_aponta_e_volta(lar: Path, tmp_path: Path) -> None:
    for versao in ("1.4.3", "1.4.4"):
        dados = {"tar": str(_tar_do_umu(tmp_path / f"{versao}.tar")), "tag": versao}
        dados.update(pa._instalar_o_umu(at.Passo(), dados))
        pa._aplicar_o_umu(at.Passo(), dados)
    casa = lar / ".local" / "bin" / "umu-run"
    assert casa.is_symlink() and "1.4.4" in str(casa.resolve())
    elo = pa._pasta_do_umu() / "1.4.4" / "umu" / "umu_run.py"
    assert elo.is_symlink() and elo.resolve() == casa.resolve()
    assert dados["anterior_dir"] == "1.4.3"
    pa._voltar_o_umu({"dados": dados})
    assert "1.4.3" in str(casa.resolve())


def test_o_umu_recusa_o_pacote_com_caminho_de_fora(lar: Path, tmp_path: Path) -> None:
    dados = {"tar": str(_tar_do_umu(tmp_path / "mau.tar", mau=True)), "tag": "9.9"}
    with pytest.raises(at.EtapaFalhouError, match="de fora"):
        pa._instalar_o_umu(at.Passo(), dados)
    assert not (lar / "fora").exists()
    assert not (pa._pasta_do_umu() / "9.9").exists()


@pytest.mark.parametrize(("elo", "tipo"), [
    ("../../fora", tarfile.SYMTYPE), ("/etc/hostname", tarfile.SYMTYPE),
    ("../fora", tarfile.LNKTYPE), ("/etc/hostname", tarfile.LNKTYPE)])
def test_o_umu_recusa_o_elo_que_aponta_para_fora(lar: Path, tmp_path: Path, elo: str,
                                                 tipo: bytes) -> None:
    dados = {"tar": str(_tar_do_umu(tmp_path / "elo.tar", elo=elo, tipo=tipo)), "tag": "9.9"}
    with pytest.raises(at.EtapaFalhouError, match="de fora: umu/umu_run"):
        pa._instalar_o_umu(at.Passo(), dados)
    assert not (pa._pasta_do_umu() / "9.9").exists()


def test_o_umu_de_fora_do_hefesto_nao_se_troca(lar: Path, tmp_path: Path) -> None:
    casa = lar / ".local" / "bin" / "umu-run"
    casa.parent.mkdir(parents=True)
    casa.write_text("#!/bin/sh\n", encoding="utf-8")
    dados = {"tar": str(_tar_do_umu(tmp_path / "u.tar")), "tag": "1.4.4"}
    dados.update(pa._instalar_o_umu(at.Passo(), dados))
    with pytest.raises(at.EtapaFalhouError, match="não é do Hefesto"):
        pa._aplicar_o_umu(at.Passo(), dados)
    assert not casa.is_symlink()


def test_o_python_so_olha_as_bibliotecas_do_produto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_no_venv", lambda: True)
    monkeypatch.setattr(pa, "_dependencias_do_produto", lambda: ["evdev", "pydantic"])
    lista = [{"name": "evdev", "version": "1.9.3", "latest_version": "2.0.0"},
             {"name": "pydantic", "version": "2.13.5", "latest_version": "2.14.3"},
             {"name": "setuptools", "version": "70", "latest_version": "80"}]
    monkeypatch.setattr(pa, "_saida", lambda argv: json.dumps(lista))
    versoes = pa.versoes_do_python(True)
    assert versoes.tem_nova() and versoes.rotulo == "2 pacotes"
    assert versoes.dica == "evdev 1.9.3 → 2.0.0 · pydantic 2.13.5 → 2.14.3"
    assert pa.versoes_do_python(False).publicada is None
    segurada = at.Escolha(seguradas={"python": versoes.publicada or ""})
    lista[1] = {"name": "pydantic", "version": "2.13.5", "latest_version": "2.15.0"}
    mais_nova = pa.versoes_do_python(True)
    assert mais_nova.rotulo == "2 pacotes"
    python = next(p for p in at.pecas() if p.id == "python")
    assert at._estado_da_peca(python, mais_nova, segurada, {}) == at.NOVA, \
        "a volta segura as versões de que se voltou, não a contagem: a próxima publicada sobe"
    assert at._estado_da_peca(python, versoes, segurada, {}) == at.EM_DIA
    instalados: list[tuple[str, ...]] = []
    monkeypatch.setattr(pa, "_pip", lambda *a, **k: instalados.append(a) or (0, ""))
    pa._voltar_o_python({"dados": {"pacotes": {"evdev": ["1.9.3", "2.0.0"]}}})
    assert instalados == [("install", "evdev==1.9.3")]


def test_o_proton_le_a_ultima_publicada_pela_rede_de_mentira(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.integrations import proton_pin as pp

    monkeypatch.setattr(pp, "_load_conf", lambda _p: {"name": "GE-Proton11-7", "url": "u",
                                                      "sha256": "a" * 64})
    monkeypatch.setattr(pp, "pino_que_vale", lambda conf, compat=None: "GE-Proton11-7")
    release = {"assets": [
        {"name": "GE-Proton11-12-x86_64.tar.gz", "browser_download_url": "t"},
        {"name": "GE-Proton11-12-x86_64.sha512sum", "browser_download_url": "s"}]}
    monkeypatch.setattr(pp, "_ler_da_rede", lambda url: json.dumps(release).encode())
    versoes = pa.versoes_do_proton(True)
    assert (versoes.instalada, versoes.publicada, versoes.tem_nova()) == ("11-7", "11-12", True)
    assert pa.versoes_do_proton(False).publicada is None


def test_a_ge_segurada_nao_entra_de_novo(tmp_path: Path) -> None:
    from hefesto_dualsense4unix.integrations import proton_pin as pp

    cache = tmp_path / "cache"
    (cache).mkdir()
    (cache / "GE-Proton11-12.tar.gz").write_bytes(b"t")
    pp._gravar_registro(cache, {"name": "GE-Proton11-12", "sha256": "a" * 64, "url": "u"})
    pp.segurar(cache, "GE-Proton11-12")
    pp._gravar_registro(cache, {"name": "GE-Proton11-12", "sha256": "a" * 64, "url": "u"})
    feito = pp.instalar_a_ultima_do_cache({"name": "GE-Proton11-7", "url": "u",
                                           "sha256": "b" * 64},
                                          compat_dir=tmp_path / "compat", cache_dir=cache,
                                          steam_barra=lambda: None)
    assert (feito.estado, feito.versao) == ("segurada", "GE-Proton11-12")


def _a_peca_hefesto(casa: Casa, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(pa, "RAIZ_DO_REPOSITORIO", casa.clone)
    peca = next(p for p in pa.registro() if p.id == "hefesto")
    return next(i for i in at.conferir(rede=True, lista=[peca])["pecas"])


def _baixar(casa: Casa) -> str | None:
    return va.baixar(casa.clone, jogo_aberto=lambda: False)


def test_a_peca_hefesto_le_o_que_a_baixada_conferiu(
        casa: Casa, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-A-PECA-HEFESTO-SO-DIZ-ATUALIZADO-QUANDO-CONFERIU: a baixada conferida diz a versão."""
    sem_baixada = _a_peca_hefesto(casa, monkeypatch)
    assert sem_baixada["estado"] == at.NAO_CONSULTADO
    alvo = casa.publicar(casa.chave, "src/um.py")
    assert _baixar(casa) == alvo
    nova = _a_peca_hefesto(casa, monkeypatch)
    assert nova["estado"] == at.NOVA and nova["para"]
    assert pa.versoes_do_hefesto(False).publicada is None
    va.aplicar(casa.clone, alvo, jogo_aberto=lambda: False, disparar=lambda _i: None)
    assert _a_peca_hefesto(casa, monkeypatch)["estado"] == at.EM_DIA


def test_o_arquivo_solto_no_clone_nao_prende_a_versao_nova(
        casa: Casa, monkeypatch: pytest.MonkeyPatch) -> None:
    (casa.clone / "rascunho.txt").write_text("y\n", encoding="utf-8")
    alvo = casa.publicar(casa.chave, "src/um.py")
    assert _baixar(casa) == alvo
    assert _a_peca_hefesto(casa, monkeypatch)["estado"] == at.NOVA


def test_o_fetch_de_outro_ramo_nao_vira_versao_nova(
        casa: Casa, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _baixar(casa) is None
    assert _a_peca_hefesto(casa, monkeypatch)["estado"] == at.EM_DIA
    _git(casa.autor, "checkout", "-q", "-b", "outro")
    casa.publicar(casa.chave, "src/outro.py")
    _git(casa.autor, "push", "-q", "origin", "outro")
    _git(casa.clone, "fetch", "-q", "origin", "outro")
    assert _git(casa.clone, "rev-parse", "FETCH_HEAD") != casa.topo()
    assert _a_peca_hefesto(casa, monkeypatch)["estado"] == at.EM_DIA


def test_sem_o_remoto_a_peca_diz_que_nao_conferiu(
        casa: Casa, monkeypatch: pytest.MonkeyPatch) -> None:
    casa.publicar(casa.chave, "src/um.py")
    casa.remoto.rename(casa.base / "fora-do-ar.git")
    assert _baixar(casa) is None
    item = _a_peca_hefesto(casa, monkeypatch)
    assert (item["estado"], item["para"]) == (at.NAO_CONSULTADO, "")
    assert "não respondeu" in item["dica"]


def _reescrever_o_dev(casa: Casa, chave: Path, texto: str) -> None:
    casa.escrever("README.md", texto)
    _git(casa.autor, "-c", "commit.gpgsign=true", "-c", "gpg.format=ssh",
         "-c", f"user.signingkey={chave}", "commit", "--amend", "-q", "-m", "reescrito")
    _git(casa.autor, "push", "-q", "-f", "origin", "dev")


def _o_clone_no_publicado(casa: Casa) -> None:
    casa.publicar(casa.chave, "src/um.py")
    _git(casa.clone, "pull", "-q", "--ff-only", "origin", "dev")


def test_o_dev_reescrito_pede_revisao_e_so_oferece_refazer_com_a_ponta_assinada(
        casa: Casa, base: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _o_clone_no_publicado(casa)
    _reescrever_o_dev(casa, casa.chave, "reescrito\n")
    assert _baixar(casa) is None
    item = _a_peca_hefesto(casa, monkeypatch)
    assert item["estado"] == at.REVISAR
    assert "git reset --hard" in item["dica"] and "git branch dev-antes-" in item["dica"]

    _reescrever_o_dev(casa, _chave(base, "de-fora"), "reescrito de novo\n")
    assert _baixar(casa) is None
    item = _a_peca_hefesto(casa, monkeypatch)
    assert item["estado"] == at.REVISAR and "reset" not in item["dica"]


def test_a_reescrita_so_oferece_refazer_pela_linhagem_e_pela_chave_que_o_head_conhece(
        casa: Casa, base: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-A-CHAVE-NOVA-SE-SEGUE-PELA-LINHAGEM-ASSINADA: a oferta anda commit a commit.
    D-2111-A-OFERTA-DE-REFAZER-RESPEITA-A-LISTA-DO-HEAD: a reescrita que troca para a chave que o
    ``HEAD`` não conhece fica sem oferta, de propósito; a assinada pela chave conhecida do ``HEAD``
    ganha a oferta."""
    _o_clone_no_publicado(casa)
    segunda = _chave(base, "segunda")
    _git(casa.autor, "reset", "-q", "--hard", casa.inicio)
    casa.escrever(assinado.LISTA, assinado._linha_da_lista(casa.chave)
                  + assinado._linha_da_lista(segunda))
    casa.commitar(casa.chave)
    casa.escrever(assinado.LISTA, assinado._linha_da_lista(segunda))
    casa.commitar(segunda)
    casa.publicar(casa.chave, "src/da-revogada.py", forcar=True)
    assert _baixar(casa) is None
    item = _a_peca_hefesto(casa, monkeypatch)
    assert item["estado"] == at.REVISAR and "reset" not in item["dica"]

    _git(casa.autor, "reset", "-q", "--hard", "HEAD~1")
    casa.publicar(segunda, "src/da-segunda.py", forcar=True)
    assert _baixar(casa) is None
    item = _a_peca_hefesto(casa, monkeypatch)
    assert item["estado"] == at.REVISAR and "reset" not in item["dica"]

    _git(casa.autor, "reset", "-q", "--hard", "HEAD~2")
    casa.publicar(casa.chave, "src/da-que-o-clone-aceita.py", forcar=True)
    assert _baixar(casa) is None
    assert "git reset --hard" in _a_peca_hefesto(casa, monkeypatch)["dica"]


def test_a_recusa_por_assinatura_pede_revisao(
        casa: Casa, monkeypatch: pytest.MonkeyPatch) -> None:
    casa.publicar(None, "src/um.py")
    assert _baixar(casa) is None
    item = _a_peca_hefesto(casa, monkeypatch)
    assert item["estado"] == at.REVISAR and "sem a assinatura do projeto" in item["dica"]


def test_a_conferencia_de_outro_head_nao_vale(
        casa: Casa, monkeypatch: pytest.MonkeyPatch) -> None:
    casa.publicar(casa.chave, "src/um.py")
    assert _baixar(casa)
    (casa.clone / "trabalho.txt").write_text("y\n", encoding="utf-8")
    _git(casa.clone, "add", "trabalho.txt")
    _git(casa.clone, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "trabalho")
    assert _a_peca_hefesto(casa, monkeypatch)["estado"] == at.NAO_CONSULTADO


def test_os_modulos_do_kernel_cobrem_os_cinco(monkeypatch: pytest.MonkeyPatch) -> None:
    modulos = ("hefesto-hid-playstation", "hefesto-hid-nintendo", "hefesto-rtw88-usb",
               "hefesto-usb-f-hid", "hefesto-uhid")
    monkeypatch.setattr(pa, "_kernels_com_headers", lambda: ["7.2.15-generic", "7.2.18-generic"])
    status = [(m, "1.0.0", "7.2.15-generic", "installed") for m in modulos]
    monkeypatch.setattr(pa, "_dkms_status", lambda: status)
    versoes = pa.versoes_do_dkms(True)
    assert versoes.dica.startswith("5 módulos") and versoes.tem_nova()
    status += [(m, "1.0.0", "7.2.18-generic", "installed") for m in modulos[:4]]
    assert pa.versoes_do_dkms(True).tem_nova()
    status.append((modulos[4], "1.0.0", "7.2.18-generic", "installed"))
    assert not pa.versoes_do_dkms(True).tem_nova()


def test_a_instalacao_que_falha_nao_troca_a_anterior_que_volta() -> None:
    d = _Diario()
    _rodar([_peca(d, "a", de="1.0", para="1.1", voltar=True)], ["a"])
    boa = at.ler_as_anteriores()["a"]
    _rodar([_peca(d, "a", de="1.1", para="1.2", falha_em="instalar", voltar=True)], ["a"])
    assert at.ler_as_anteriores()["a"] == boa, "a 1.2 não entrou: a volta segue sendo à 1.0"
    _rodar([_peca(d, "b", de="2.0", para="2.1", falha_em="instalar", voltar=True)], ["b"])
    assert "b" not in at.ler_as_anteriores(), "sem instalar, não há anterior a que voltar"
    _rodar([_peca(d, "c", de="3.0", para="3.1", falha_em="aplicar", voltar=True)], ["c"])
    assert at.ler_as_anteriores()["c"]["anterior"] == "3.0", "instalou: a anterior fica"


def test_o_fim_da_fila_guarda_a_versao_publicada_para_o_tentar_de_novo() -> None:
    d = _Diario()
    lista = [_peca(d, "a", de="1.0", para="1.1", falha_em="instalar", voltar=True)]
    _rodar(lista, ["a"])
    item = next(i for i in at.ler_a_conferencia()["pecas"] if i["id"] == "a")
    assert item["para"] == "1.1" and item["estado"] == at.NOVA, item
    at.rodar(["a"], lista=lista, jogo_aberto=lambda: False, reiniciar=lambda: True,
             reabrir=lambda: True, dormir=lambda _s: None)
    assert at.ler_o_andamento()["pecas"][0]["para"] == "1.1"
