"""O Proton se atualiza sozinho: a GE-Proton mais nova publicada vira o pino, e as velhas saem.

O-PROTON-SE-ATUALIZA-SOZINHO-01, 08/11/2026. Prova da D-0811-TUDO-SE-ATUALIZA-SOZINHO. Antes,
nada consultava lançamento novo: o pino ficava na versão do ``proton-pin.conf`` até alguém editar
as três chaves, e a «mais recente que passa» (D-2210) só olhava o que já estava no disco.

TUDO É DE MENTIRA: a casa, a Steam e o Heroic são pastas em ``tmp_path``; a rede é um dicionário
de URL para bytes; o tarball nasce do ``_proton_de_mentira`` da régua da ficha.

AS MORDIDAS (feitas na sprint, com a cura devolvida): o download que não confere o sha512 reprova
o caso do sha512 errado; a extração que não passa pela ficha reprova o caso da que reprova; a casa
do Heroic que não extrai a nova do cache reprova o caso do Flatpak; o prazo da consulta arrancado
reprova o caso do prazo.
"""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import proton_pin as pp
from tests.unit.test_o_fixar_proton_desinstala_as_que_sobram import _vdf
from tests.unit.test_o_proton_novo_so_entra_se_passar import _proton_de_mentira

VELHA = "GE-Proton11-7-x86_64"
NOVA = "GE-Proton11-12-x86_64"
CONF = {"name": VELHA, "url": "u", "sha256": "a" * 64}
SEM_A_STRING = "x86_64-windows/mmdevapi.dll:PROTON_ENABLE_MHWILDS_USB_AUDIO"
URL_DO_TAR = f"https://exemplo.invalid/{NOVA}.tar.gz"
URL_DA_SOMA = f"https://exemplo.invalid/{NOVA}.sha512sum"


@pytest.fixture(autouse=True)
def _a_maquina_viva_nao_decide(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pp, "_steam_gate", lambda: None)
    monkeypatch.setattr(censo, "proton_em_uso",
                        lambda *a, **k: censo.ProtonEmUso(frozenset(), ()))
    monkeypatch.setattr(censo, "casas_do_heroic", lambda *a, **k: ((), ()))


@pytest.fixture
def casa(tmp_path: Path) -> Path:
    lar = tmp_path / "casa"
    raiz = lar / ".steam" / "steam"
    (raiz / "config").mkdir(parents=True)
    (raiz / "steamapps").mkdir()
    _proton_de_mentira(raiz / "compatibilitytools.d" / VELHA)
    (raiz / "config" / "config.vdf").write_text(_vdf({"10": VELHA, "20": VELHA}), encoding="utf-8")
    return lar


def _compat(lar: Path) -> Path:
    return lar / ".steam" / "steam" / "compatibilitytools.d"


def _tarball(tmp: Path, nome: str = NOVA, sem: str = "") -> bytes:
    origem = _proton_de_mentira(tmp / "origem" / nome, sem=sem)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(origem, arcname=nome)
    return buf.getvalue()


def _rede(dado: bytes, *, soma: str | None = None) -> dict[str, bytes]:
    release = {"tag_name": "GE-Proton11-12", "assets": [
        {"name": f"{NOVA}.tar.gz", "browser_download_url": URL_DO_TAR},
        {"name": f"{NOVA}.sha512sum", "browser_download_url": URL_DA_SOMA},
        {"name": "GE-Proton11-12-aarch64.tar.gz", "browser_download_url": "x"},
    ]}
    sha = soma if soma is not None else hashlib.sha512(dado).hexdigest()
    return {pp.GE_ULTIMA_API: json.dumps(release).encode(),
            URL_DA_SOMA: f"{sha}  {NOVA}.tar.gz\n".encode(), URL_DO_TAR: dado}


class _Rede:
    def __init__(self, mapa: dict[str, bytes]) -> None:
        self.mapa = mapa
        self.pedidos: list[str] = []

    def ler(self, url: str) -> bytes:
        self.pedidos.append(url)
        if url not in self.mapa:
            raise OSError("sem rede")
        return self.mapa[url]

    def baixar(self, url: str, dest: Path) -> None:
        dest.write_bytes(self.ler(url))


def _cache(lar: Path) -> Path:
    return lar / "cache"


def _atualizar(lar: Path, rede: _Rede, **kw: object) -> tuple[pp.Atualizacao, pp.Atualizacao]:
    baixada = pp.baixar_a_ultima_do_ge(_cache(lar), ler=rede.ler, baixar=rede.baixar, **kw)  # type: ignore[arg-type]
    instalada = pp.instalar_a_ultima_do_cache(CONF, compat_dir=_compat(lar), cache_dir=_cache(lar),
                                              steam_barra=lambda: None)
    return baixada, instalada


def test_a_mais_nova_publicada_vira_o_pino_todo_jogo_vai_e_a_velha_sai(
        casa: Path, tmp_path: Path) -> None:
    """Prova da D-0811-O-PROTON-SE-ATUALIZA-SOZINHO."""
    rede = _Rede(_rede(_tarball(tmp_path)))
    baixada, instalada = _atualizar(casa, rede)
    assert (baixada.estado, instalada.estado) == ("baixada", "instalada")
    assert pp.pino_que_vale(CONF, _compat(casa)) == NOVA
    vdf = casa / ".steam" / "steam" / "config" / "config.vdf"
    pp.lock_proton_for_all_games(conf=CONF, home=casa, config_vdf=vdf,
                                 state_path=casa / "lock.json", todos=True,
                                 compat_dir=_compat(casa))
    assert set(pp.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8")).values()) == {NOVA}
    sobras = pp.versoes_que_sobram(casa)
    assert [s.pasta.name for s in sobras] == [VELHA]
    saiu, recusadas = pp.desinstalar_as_que_sobram(sobras, steam_barra=lambda: None)
    assert [s.pasta.name for s in saiu] == [VELHA] and not recusadas
    assert sorted(p.name for p in _compat(casa).iterdir()) == [NOVA]


def test_sem_rede_diz_nao_consultado_e_nada_muda(casa: Path) -> None:
    baixada, instalada = _atualizar(casa, _Rede({}))
    assert baixada.estado == "nao_consultado"
    assert instalada.estado == "sem_candidata"
    assert pp.pino_que_vale(CONF, _compat(casa)) == VELHA


def test_sha512_errado_nao_fica_no_cache(casa: Path, tmp_path: Path) -> None:
    baixada, instalada = _atualizar(casa, _Rede(_rede(_tarball(tmp_path), soma="0" * 128)))
    assert baixada.estado == "checksum"
    assert not list(_cache(casa).glob("*.tar.gz*"))
    assert instalada.estado == "sem_candidata"


def test_a_que_reprova_na_ficha_sai_do_disco_e_o_pino_fica(casa: Path, tmp_path: Path) -> None:
    baixada, instalada = _atualizar(casa, _Rede(_rede(_tarball(tmp_path, sem=SEM_A_STRING))))
    assert baixada.estado == "baixada"
    assert instalada.estado == "reprovou"
    assert not (_compat(casa) / NOVA).exists()
    assert pp.pino_que_vale(CONF, _compat(casa)) == VELHA


def test_com_a_steam_aberta_a_extracao_espera(casa: Path, tmp_path: Path) -> None:
    rede = _Rede(_rede(_tarball(tmp_path)))
    pp.baixar_a_ultima_do_ge(_cache(casa), ler=rede.ler, baixar=rede.baixar)
    feita = pp.instalar_a_ultima_do_cache(CONF, compat_dir=_compat(casa), cache_dir=_cache(casa),
                                          steam_barra=lambda: "steam_aberta")
    assert feita.estado == "espera_a_steam"
    assert not (_compat(casa) / NOVA).exists()


def test_a_consulta_respeita_o_prazo_e_o_forcar_o_ignora(casa: Path, tmp_path: Path) -> None:
    rede = _Rede(_rede(_tarball(tmp_path)))
    pp.baixar_a_ultima_do_ge(_cache(casa), ler=rede.ler, baixar=rede.baixar, agora=lambda: 1000.0)
    rede.pedidos.clear()
    perto = pp.baixar_a_ultima_do_ge(_cache(casa), ler=rede.ler, baixar=rede.baixar,
                                     agora=lambda: 1000.0 + pp.INTERVALO_DA_CONSULTA_S - 1)
    assert perto.estado == "em_cache" and rede.pedidos == []
    forcada = pp.baixar_a_ultima_do_ge(_cache(casa), ler=rede.ler, baixar=rede.baixar,
                                       agora=lambda: 1001.0, forcar=True)
    assert forcada.estado == "em_cache" and rede.pedidos == [pp.GE_ULTIMA_API]


def test_a_casa_do_heroic_no_flatpak_recebe_a_nova_do_cache(casa: Path, tmp_path: Path) -> None:
    _atualizar(casa, _Rede(_rede(_tarball(tmp_path))))
    proprio = casa / "heroic" / "tools" / "proton"
    _proton_de_mentira(proprio / VELHA)
    achado = pp._o_pino_que_a_casa_ve(proprio, NOVA, conf=CONF, compat=_compat(casa),
                                      cache=_cache(casa), extrair=True, ve_a_steam=False)
    assert achado == proprio / NOVA
    assert pp.pinned_proton_installed(NOVA, proprio)


def test_a_sobra_do_heroic_so_sai_com_o_manifesto_do_hefesto(
        casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _atualizar(casa, _Rede(_rede(_tarball(tmp_path))))
    heroic = casa / "heroic"
    proprio = heroic / "tools" / "proton"
    _proton_de_mentira(proprio / VELHA)
    (proprio / VELHA / pp.MANIFEST_BASENAME).write_text("{}", encoding="utf-8")
    _proton_de_mentira(proprio / "GE-Proton10-34")
    pp._o_pino_que_a_casa_ve(proprio, NOVA, conf=CONF, compat=_compat(casa), cache=_cache(casa),
                             extrair=True, ve_a_steam=False)
    monkeypatch.setattr(censo, "casas_do_heroic", lambda *a, **k: ((heroic,), ()))
    monkeypatch.setattr(pp, "_load_conf", lambda _p: CONF)
    sobras = pp.sobras_das_casas_do_heroic(casa, compat_dir=_compat(casa))
    assert [s.pasta.name for s in sobras] == [VELHA]
