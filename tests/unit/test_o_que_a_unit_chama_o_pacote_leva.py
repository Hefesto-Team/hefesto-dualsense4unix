"""Todo caminho absoluto que uma unit invoca existe em TODOS os formatos."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

FORMATOS: dict[str, Path] = {
    "deb": RAIZ / "scripts" / "build_deb.sh",
    "arch": RAIZ / "packaging" / "arch" / "PKGBUILD",
    "fedora": RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
    "flatpak": RAIZ / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.yml",
}

_ALVO = re.compile(r"/usr/local/lib/hefesto-dualsense4unix/([A-Za-z0-9_.-]+\.sh)")


def _scripts_que_as_units_invocam() -> dict[str, list[str]]:
    """``{script: [units que o invocam]}``, lido das units de verdade."""
    achados: dict[str, list[str]] = {}
    raiz = RAIZ / "assets" / "systemd"
    for unit in sorted(raiz.rglob("*")):
        if not unit.is_file() or unit.suffix not in {".service", ".timer", ".path", ".conf"}:
            continue
        texto = unit.read_text(encoding="utf-8", errors="replace")
        for linha in texto.splitlines():
            corte = linha.strip()
            if corte.startswith("#") or "Exec" not in corte:
                continue
            for nome in _ALVO.findall(corte):
                achados.setdefault(nome, []).append(unit.name)
    return achados


def test_a_regua_acha_alguma_unit_que_invoca_script() -> None:
    """Anticircularidade: sem isto, um regex quebrado aprovaria tudo em silêncio."""
    achados = _scripts_que_as_units_invocam()
    assert achados, (
        "nenhuma unit invoca script em /usr/local/lib — ou a régua quebrou, ou "
        "as units mudaram de forma. Portão cego é pior que portão nenhum."
    )


def test_o_script_que_a_unit_invoca_existe_no_repositorio() -> None:
    """Mordida: renomear um script sem mexer na unit que o chama."""
    faltando = {
        nome: units
        for nome, units in _scripts_que_as_units_invocam().items()
        if not (RAIZ / "scripts" / nome).exists()
    }
    assert not faltando, (
        "estas units invocam script que não existe em `scripts/`: "
        + "; ".join(f"{n} (por {', '.join(u)})" for n, u in faltando.items())
    )


def test_todo_formato_leva_o_que_as_units_invocam() -> None:
    """A régua das três ocorrências de hoje."""
    conteudo = {
        formato: caminho.read_text(encoding="utf-8", errors="replace")
        for formato, caminho in FORMATOS.items()
        if caminho.exists()
    }
    assert len(conteudo) == len(FORMATOS), (
        f"formato sem arquivo de declaração: "
        f"{sorted(set(FORMATOS) - set(conteudo))}"
    )

    buracos: list[str] = []
    for nome, units in _scripts_que_as_units_invocam().items():
        sem = [f for f, texto in conteudo.items() if nome not in texto]
        if sem:
            buracos.append(
                f"{nome} (invocado por {', '.join(units)}) não viaja em: "
                f"{', '.join(sorted(sem))}"
            )

    assert not buracos, (
        "unit chamando caminho que o pacote não preenche — é a terceira vez que "
        "esta família aparece:\n  " + "\n  ".join(buracos) + "\n\n"
        "Quem instala por pacote fica com a unit apontando para um arquivo que "
        "nunca existiu, e o systemd falha calado a cada disparo."
    )
