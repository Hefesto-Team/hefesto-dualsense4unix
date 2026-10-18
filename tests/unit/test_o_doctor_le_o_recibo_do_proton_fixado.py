"""O-DOCTOR-LE-O-RECIBO-DO-PROTON-FIXADO-01 — o doctor lê o recibo do Proton fixado.

A O-PROTON-NOVO-SO-ENTRA-NO-LUGAR-DO-FIXADO-SE-PASSAR-NAS-PROVAS-01 foi arquivada
dizendo que o doctor lia o recibo, e nada no produto o lia. Agora o ``hefesto
doctor`` tem um bloco do Proton fixado: se tem o recibo «passou», se o Proton
sumiu do disco, o que o recibo diz de cada Proton instalado e em que versão roda
cada jogo que a Steam mapeou. O recibo e o pino são achados pelo resolvedor das
instalações (``encontrar_arquivo_do_repo``), e não só pelo checkout.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import typer

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.integrations import qualificar_proton as qp

FIXADA = "GE-Proton11-7-x86_64"
SHA = "a" * 64

RECIBO_PASSOU = f"""\
versão,sha256,ficha,rodada,veredito,prova,data
{FIXADA},{SHA},passou,herdada,passou,,2026-10-16
"""
RECIBO_SEM_A_FIXADA = """\
versão,sha256,ficha,rodada,veredito,prova,data
GE-Proton11-8-x86_64,bbbb,passou,herdada,passou,,2026-10-16
"""
SCRIPT_DO_PROTON = "import os\n"


def _proton_de_mentira(compat: Path, nome: str, *, cumpre_o_contrato: bool = True) -> Path:
    """Uma pasta de Proton com o ``proton``, o ``version`` e as strings que o contrato pede."""
    pasta = compat / nome
    wine = pasta / "files" / "lib" / "wine"
    wine.mkdir(parents=True)
    (pasta / "proton").write_text(SCRIPT_DO_PROTON, encoding="utf-8")
    (pasta / "version").write_text(f"1 {nome}\n", encoding="utf-8")
    if cumpre_o_contrato:
        for _componente, arquivos, texto in qp.CONTRATO_DE_STRINGS:
            alvo = wine / arquivos[0]
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with alvo.open("ab") as f:
                f.write(texto.encode("ascii") + b"\0")
    return pasta


def _linhas(
    compat: Path,
    *,
    recibo: str | None,
    pino_sha: str = SHA,
    pino: bool = True,
    mapa: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    return qp.linhas_do_doctor(
        recibo=qp.ler_recibo(recibo) if recibo is not None else None,
        pino={"name": FIXADA, "sha256": pino_sha} if pino else None,
        compat_dir=compat,
        mapa_dos_jogos=mapa or {},
        nome_do_jogo=lambda appid: f"Jogo {appid}",
    )


def _tags(linhas: list[tuple[str, str]]) -> list[str]:
    return [tag for tag, _ in linhas]


def test_o_fixado_com_recibo_passou_e_ok(tmp_path: Path) -> None:
    _proton_de_mentira(tmp_path, FIXADA)
    linhas = _linhas(tmp_path, recibo=RECIBO_PASSOU)
    assert linhas[0] == (
        qp.TAG_OK,
        f"o Proton fixado ({FIXADA}) tem o recibo «passou» com o mesmo sha256",
    )
    assert qp.TAG_WARN not in _tags(linhas), linhas


def test_o_fixado_sem_recibo_avisa(tmp_path: Path) -> None:
    _proton_de_mentira(tmp_path, FIXADA)
    linhas = _linhas(tmp_path, recibo=RECIBO_SEM_A_FIXADA)
    avisos = [msg for tag, msg in linhas if tag == qp.TAG_WARN]
    assert any("não tem linha no recibo" in msg for msg in avisos), linhas


def test_o_fixado_com_outro_sha256_avisa(tmp_path: Path) -> None:
    _proton_de_mentira(tmp_path, FIXADA)
    linhas = _linhas(tmp_path, recibo=RECIBO_PASSOU, pino_sha="c" * 64)
    assert any(tag == qp.TAG_WARN and "sha256" in msg for tag, msg in linhas), linhas


def test_o_fixado_que_sumiu_do_disco_avisa(tmp_path: Path) -> None:
    linhas = _linhas(tmp_path, recibo=RECIBO_PASSOU)
    assert any(
        tag == qp.TAG_WARN and FIXADA in msg and "não está em" in msg for tag, msg in linhas
    ), linhas


def test_sem_o_recibo_na_instalacao_diz_e_nao_avisa(tmp_path: Path) -> None:
    _proton_de_mentira(tmp_path, FIXADA)
    linhas = _linhas(tmp_path, recibo=None)
    assert qp.TAG_WARN not in _tags(linhas), linhas
    assert any("recibo" in msg and "não veio" in msg for _, msg in linhas), linhas


def test_sem_o_pino_na_instalacao_diz_e_nao_avisa(tmp_path: Path) -> None:
    linhas = _linhas(tmp_path, recibo=RECIBO_PASSOU, pino=False)
    assert qp.TAG_WARN not in _tags(linhas), linhas
    assert any("proton-pin.conf" in msg for _, msg in linhas), linhas


def test_o_instalado_que_o_recibo_reprovou_avisa(tmp_path: Path) -> None:
    _proton_de_mentira(tmp_path, FIXADA)
    _proton_de_mentira(tmp_path, "GE-Proton11-8-x86_64")
    recibo = (
        RECIBO_PASSOU
        + "GE-Proton11-8-x86_64,bbbb,passou,a háptica não chegou,reprovou,háptica,2026-10-17\n"
    )
    linhas = _linhas(tmp_path, recibo=recibo)
    da_oito = [(t, m) for t, m in linhas if m.startswith("GE-Proton11-8-x86_64:")]
    assert da_oito and da_oito[0][0] == qp.TAG_WARN, linhas
    assert "reprovou (háptica)" in da_oito[0][1]


def test_o_instalado_que_passou_mas_a_ficha_de_hoje_nao_confere_avisa(tmp_path: Path) -> None:
    _proton_de_mentira(tmp_path, FIXADA, cumpre_o_contrato=False)
    linhas = _linhas(tmp_path, recibo=RECIBO_PASSOU)
    da_fixada = [(t, m) for t, m in linhas if m.startswith(f"{FIXADA}: recibo")]
    assert da_fixada and da_fixada[0][0] == qp.TAG_WARN, linhas


def test_o_instalado_sem_recibo_e_so_informacao(tmp_path: Path) -> None:
    _proton_de_mentira(tmp_path, FIXADA)
    _proton_de_mentira(tmp_path, "GE-Proton9-27", cumpre_o_contrato=False)
    linhas = _linhas(tmp_path, recibo=RECIBO_PASSOU)
    do_outro = [(t, m) for t, m in linhas if m.startswith("GE-Proton9-27:")]
    assert do_outro and do_outro[0][0] == qp.TAG_INFO, linhas
    assert "sem recibo" in do_outro[0][1]


def test_cada_jogo_aparece_na_versao_em_que_roda(tmp_path: Path) -> None:
    _proton_de_mentira(tmp_path, FIXADA)
    linhas = _linhas(tmp_path, recibo=RECIBO_PASSOU, mapa={"10": FIXADA, "20": FIXADA, "0": FIXADA})
    do_mapa = [(t, m) for t, m in linhas if m.startswith(f"{FIXADA}: Jogo")]
    assert do_mapa == [(qp.TAG_INFO, f"{FIXADA}: Jogo 10, Jogo 20")], linhas


def test_o_jogo_cujo_proton_de_terceiros_sumiu_do_disco_avisa_pelo_nome(tmp_path: Path) -> None:
    _proton_de_mentira(tmp_path, FIXADA)
    linhas = _linhas(
        tmp_path, recibo=RECIBO_PASSOU, mapa={"10": "GE-Proton10-34", "20": "proton_10"}
    )
    avisos = [m for t, m in linhas if t == qp.TAG_WARN]
    assert avisos == ["Jogo 10 usa(m) o GE-Proton10-34, que sumiu de " + str(tmp_path)], linhas
    # o Proton da Valve mora fora do compatibilitytools.d: não é dele que se avisa.
    assert any(m == "proton_10: Jogo 20" for _, m in linhas)


def test_o_nome_interno_da_pasta_conta_como_presente(tmp_path: Path) -> None:
    pasta = _proton_de_mentira(tmp_path, FIXADA)
    (pasta / "compatibilitytool.vdf").write_text(
        '"compatibilitytools"\n{\n  "compat_tools"\n  {\n'
        '    "GE-Proton-apelido" // x\n    {\n    }\n  }\n}\n',
        encoding="utf-8",
    )
    linhas = _linhas(tmp_path, recibo=RECIBO_PASSOU, mapa={"10": "GE-Proton-apelido"})
    assert qp.TAG_WARN not in _tags(linhas), linhas


# --- o doctor chama o bloco --------------------------------------------------


@pytest.fixture
def doctor_sem_o_resto(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[tuple[str, str]]], int]:
    """O ``doctor_cmd`` com tudo menos o bloco do Proton trocado por nada; devolve o rc."""

    async def sem_daemon() -> list[tuple[str, str]]:
        return []

    monkeypatch.setattr(cmd_doctor, "_find_doctor_sh", lambda: None)
    monkeypatch.setattr(cmd_doctor, "_avisar_ausente", lambda *a, **k: None)
    monkeypatch.setattr(cmd_doctor, "_print_storm_block", lambda: 0)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_perfis", lambda: False)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_contratos", lambda: 0)
    monkeypatch.setattr(cmd_doctor, "_daemon_checks", sem_daemon)

    def rodar(linhas_do_proton: list[tuple[str, str]]) -> int:
        monkeypatch.setattr(
            qp, "linhas_do_doctor_desta_maquina", lambda home=None: linhas_do_proton
        )
        with pytest.raises(typer.Exit) as saiu:
            cmd_doctor.doctor_cmd()
        return int(saiu.value.exit_code)

    return rodar


def test_o_doctor_imprime_o_bloco_do_proton_fixado(
    doctor_sem_o_resto: Callable[[list[tuple[str, str]]], int], capsys: pytest.CaptureFixture[str]
) -> None:
    rc = doctor_sem_o_resto([(qp.TAG_OK, "o Proton fixado (X) tem o recibo")])
    saida = capsys.readouterr().out
    assert "== Proton fixado" in saida
    assert "[ OK ] o Proton fixado (X) tem o recibo" in saida
    assert rc == 0


def test_o_aviso_do_proton_fixado_sobe_o_codigo_de_saida(
    doctor_sem_o_resto: Callable[[list[tuple[str, str]]], int],
) -> None:
    assert doctor_sem_o_resto([(qp.TAG_WARN, "o pino não tem linha no recibo")]) == 1


# --- o recibo viaja com a instalação, e o doctor o acha ----------------------


def test_o_recibo_e_achado_onde_a_instalacao_o_pos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.utils import repo_files

    share = tmp_path / "share" / "hefesto-dualsense4unix"
    (share / "docs" / "data").mkdir(parents=True)
    (share / qp.CAMINHO_DO_RECIBO).write_text(RECIBO_PASSOU, encoding="utf-8")
    monkeypatch.setattr(repo_files, "bases_de_instalacao", lambda: (share,))
    assert qp.caminho_do_recibo() == share / qp.CAMINHO_DO_RECIBO


def test_o_recibo_e_o_pino_desta_casa_dao_ok_no_doctor(tmp_path: Path) -> None:
    """Ponta a ponta com o recibo e o pino versionados: o fixado instalado confere."""
    from hefesto_dualsense4unix.integrations import proton_pin as pp

    conf = pp.default_pin_conf_path()
    assert conf is not None
    nome = pp.parse_pin_conf(conf.read_text(encoding="utf-8"))["name"]
    compat = tmp_path / ".steam" / "steam" / "compatibilitytools.d"
    compat.mkdir(parents=True)
    _proton_de_mentira(compat, nome)
    linhas = qp.linhas_do_doctor_desta_maquina(home=tmp_path)
    assert linhas[0][0] == qp.TAG_OK, linhas
    assert nome in linhas[0][1]
    assert qp.TAG_WARN not in _tags(linhas), linhas
