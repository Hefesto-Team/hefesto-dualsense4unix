"""MIC-EM-TODO-FORMATO-01 — a voz do usuário ficava para trás no `exit 0` da linha 941."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
DONO_DO_MIC = "scripts/fix_wireplumber_default_source.sh"


def _texto() -> str:
    return INSTALL.read_text(encoding="utf-8")


def _linha_do_exit_da_bifurcacao() -> int:
    """A linha do `exit 0` que encerra o ramo dos formatos não-nativos."""
    linhas = _texto().splitlines()
    inicio = next(
        i for i, s in enumerate(linhas) if s.strip() == 'if [[ "${FORMAT}" != "native" ]]; then'
    )
    for i in range(inicio, len(linhas)):
        if linhas[i].strip() == "exit 0":
            return i + 1
    raise AssertionError("não achei o `exit 0` da bifurcação de formato")


#: dela. A lista é a do `case` de `scripts/fix_wireplumber_default_source.sh`.
_MODOS_DO_MIC = (
    "--install",
    "--disable-source",
    "--reset-only",
    "--enable-mic",
    "--promote-source",
    "--unmute-routes",
)

_MODOS_FORA_DO_MIC = ("--nunca-dorme",)


def _linhas_que_chamam_o_dono() -> list[int]:
    return [
        i + 1
        for i, s in enumerate(_texto().splitlines())
        if DONO_DO_MIC in s and s.strip().startswith("bash ")
    ]


def _modo_da_chamada(linha: int) -> str | None:
    """O `--modo` passado na chamada da linha 1-indexada (None se não achar)."""
    texto = _texto().splitlines()[linha - 1]
    for modo in (*_MODOS_DO_MIC, *_MODOS_FORA_DO_MIC):
        if modo in texto:
            return modo
    return None


def test_o_mic_e_curado_antes_do_exit_dos_formatos_nao_nativos() -> None:
    """A cura. Morde ao apagar o bloco do mic do ramo não-nativo.

    Arranque para ver reprovar: tirar as chamadas de
    `fix_wireplumber_default_source.sh` de antes do `exit 0`. É o estado do
    produto até 10/08/2026 — e o efeito é a voz do usuário perder para o eco em
    flatpak, appimage e deb.
    """
    exit_linha = _linha_do_exit_da_bifurcacao()
    chamadas = _linhas_que_chamam_o_dono()
    assert chamadas, "ninguém chama mais o dono dos drop-ins do WirePlumber"
    assert any(linha < exit_linha for linha in chamadas), (
        f"o mic só é curado depois do `exit 0` da linha {exit_linha} — "
        "flatpak/appimage/deb saem sem o promotor, e o monitor vence a voz dela"
    )


def test_o_ramo_nao_nativo_respeita_as_flags_dela() -> None:
    """A cura não pode decidir no lugar dela."""
    linhas = _texto().splitlines()
    exit_linha = _linha_do_exit_da_bifurcacao()
    trecho = "\n".join(linhas[:exit_linha])
    assert "WITH_WIREPLUMBER_DISABLE_MIC" in trecho
    assert "WITH_WIREPLUMBER_FIX" in trecho
    conferidas = 0
    for linha in _linhas_que_chamam_o_dono():
        if linha >= exit_linha:
            continue
        modo = _modo_da_chamada(linha)
        assert modo is not None, (
            f"a chamada da linha {linha} não passa nenhum modo conhecido de "
            f"{DONO_DO_MIC} — modo novo entra em `_MODOS_DO_MIC` ou em "
            "`_MODOS_FORA_DO_MIC`, com o porquê escrito, para não escapar "
            "destas duas travas por omissão"
        )
        if modo in _MODOS_FORA_DO_MIC:
            continue
        antes = "\n".join(linhas[max(0, linha - 6) : linha])
        assert re.search(r"WITH_WIREPLUMBER_(FIX|DISABLE_MIC)", antes), (
            f"a chamada da linha {linha} ({modo}) não está sob a flag dela"
        )
        conferidas += 1
    assert conferidas, (
        "nenhuma chamada de modo de MICROFONE antes do `exit 0` — se todas "
        "sumiram, é o defeito do MIC-EM-TODO-FORMATO-01 de volta; se todas "
        "viraram `_MODOS_FORA_DO_MIC`, este teste parou de aferir o que "
        "promete"
    )


def test_a_cura_do_alto_falante_nao_fica_sob_flag_de_mic() -> None:
    """SOM-QUE-NAO-DORME-01: sem flag, e nem de carona na flag de outro."""
    linhas = _texto().splitlines()
    fora = [
        linha
        for linha in _linhas_que_chamam_o_dono()
        if _modo_da_chamada(linha) in _MODOS_FORA_DO_MIC
    ]
    assert fora, (
        "ninguém mais chama o `--nunca-dorme` no install — o sink do controle "
        "volta a ser suspenso pelo WirePlumber a cada 5 s de ociosidade, e o "
        "religar do hardware come o começo do som (medido em 15/08 23h45)"
    )
    exit_linha = _linha_do_exit_da_bifurcacao()
    assert any(linha < exit_linha for linha in fora), (
        "o `--nunca-dorme` só roda depois do `exit 0` da bifurcação — "
        "flatpak/appimage/deb saem com o alto-falante dormindo. É a MESMA "
        "forma do defeito que este arquivo inteiro existe para lembrar"
    )
    for linha in fora:
        antes = "\n".join(linhas[max(0, linha - 6) : linha])
        assert not re.search(r"WITH_WIREPLUMBER_(FIX|DISABLE_MIC)", antes), (
            f"a chamada da linha {linha} caiu sob uma flag de MICROFONE — o "
            "sono do alto-falante não é uma decisão sobre o microfone, e "
            "nenhuma flag de mic pode decidir por ele"
        )


def test_as_flags_sao_definidas_antes_da_bifurcacao() -> None:
    """Guarda contra a armadilha de ORDEM em bash."""
    linhas = _texto().splitlines()
    definicoes = [
        i + 1
        for i, s in enumerate(linhas)
        if re.match(r"^WITH_WIREPLUMBER_(FIX|DISABLE_MIC)=", s.strip())
    ]
    assert len(definicoes) >= 2, "as duas flags precisam de default"
    assert max(definicoes) < _linha_do_exit_da_bifurcacao()


PROMOTOR = "51-hefesto-dualsense-no-default-source.conf"


def test_nenhum_formato_empacota_os_dropins_do_wireplumber() -> None:
    """A PREMISSA da cura, travada — se ela cair, a cura vira ruído."""
    receitas = [
        RAIZ / "packaging" / "debian" / "control",
        RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
        RAIZ / "packaging" / "arch" / "PKGBUILD",
        RAIZ / "packaging" / "nix" / "package.nix",
        RAIZ / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.yml",
    ]
    achados: list[str] = []
    conferidas = 0
    for caminho in receitas:
        if not caminho.is_file():
            continue
        conferidas += 1
        texto = caminho.read_text(encoding="utf-8", errors="ignore").lower()
        # SCRIPT `fix_wireplumber_default_source.sh` nos cinco formatos — e o
        if any(marca in texto for marca in ("wireplumber.conf.d", ".conf.d/wireplumber")):
            achados.append(str(caminho.relative_to(RAIZ)))
            continue
        if PROMOTOR.lower() in texto:
            achados.append(str(caminho.relative_to(RAIZ)))
    assert conferidas >= 4, (
        "as receitas de empacotamento mudaram de caminho — este teste ficou "
        f"cego (conferiu só {conferidas})"
    )
    assert not achados, (
        "algum formato passou a empacotar drop-ins do WirePlumber: "
        f"{achados}. A premissa da MIC-EM-TODO-FORMATO-01 mudou — releia o "
        "bloco do mic no ramo não-nativo do install.sh antes de mexer."
    )


_SUPERFICIES_DO_PROMOTOR = (
    ("scripts/fix_wireplumber_default_source.sh", "instala e mantém"),
    ("scripts/doctor.sh", "confere"),
    ("src/hefesto_dualsense4unix/app/actions/emulation_actions.py", "a janela lê"),
    ("src/hefesto_dualsense4unix/integrations/storm_doctor.py", "o diagnóstico lê"),
    ("packaging/cosmic-applet/src/app.rs", "o applet lê"),
)


def test_as_cinco_superficies_falam_do_mesmo_drop_in_promotor() -> None:
    """O nome do promotor é literal em cinco lugares e ninguém os amarrava."""
    faltando = [
        f"{caminho} ({papel})"
        for caminho, papel in _SUPERFICIES_DO_PROMOTOR
        if PROMOTOR not in (RAIZ / caminho).read_text(encoding="utf-8", errors="ignore")
    ]
    assert not faltando, (
        f"estas superfícies não citam o promotor {PROMOTOR!r}: {faltando}. "
        "Se ele foi renomeado, as cinco têm de mudar juntas."
    )


def test_o_applet_nao_chama_de_ligado_um_mic_sem_o_promotor() -> None:
    """O applet do COSMIC tinha o mesmo furo da janela, e foi curado junto."""
    fonte = (RAIZ / "packaging/cosmic-applet/src/app.rs").read_text(encoding="utf-8")
    corpo = fonte[fonte.index("fn mic_is_on()") :]
    corpo = corpo[: corpo.index("\n}\n") + 2]
    assert PROMOTOR in corpo, "o applet decide sem olhar o promotor"
    assert "!suppressed && promoted" in corpo, (
        "o applet voltou a chamar de 'ligado' um microfone que perde para o eco"
    )
