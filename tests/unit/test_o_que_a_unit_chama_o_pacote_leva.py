"""Todo caminho absoluto que uma unit invoca existe em TODOS os formatos.

A FAMÍLIA, e hoje ela apareceu TRÊS vezes — 22/08/2026:

1. de manhã, as regras udev 82 e 83 viajavam nos cinco instaladores e os alvos
   do ``RUN+=`` delas, em nenhum. A 83 mandava iniciar uma unit inexistente a
   cada conexão Bluetooth;
2. à tarde, os mesmos alvos não estavam nos PACOTES — só o `install.sh` do
   checkout os gravava;
3. à noite, o ``bt_active_mode.sh`` (o ``ExecStartPost`` do drop-in do
   ``bluetooth.service``) e o ``bt_ponte_privilegiada.sh`` (o helper que a
   janela chama) repetiram a três: instalados só pelo checkout, e quem usava
   pacote tinha o drop-in apontando para um arquivo que nunca existiu — a cura
   ``BT-NINTENDO-ACTIVE-01``, a que impede o Pro Controller de cair sob carga,
   simplesmente não rodava.

Três vezes é padrão, e padrão pede portão. **A régua é a UNIT, não uma lista.**
Toda unit em ``assets/systemd/`` é lida, cada caminho absoluto sob
``/usr/local/lib/hefesto-dualsense4unix/`` é extraído dela, e o script de mesmo
nome tem de estar em ``scripts/`` E ser levado pelos quatro formatos.

Uma lista escrita à mão caducaria no próximo ``ExecStartPost``, que é exatamente
o modo como as três aconteceram.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

#: Onde cada formato declara o que empacota. O `install.sh` fica de FORA: ele é
#: o checkout, e o defeito das três vezes foi justamente "só o checkout leva".
FORMATOS: dict[str, Path] = {
    "deb": RAIZ / "scripts" / "build_deb.sh",
    "arch": RAIZ / "packaging" / "arch" / "PKGBUILD",
    "fedora": RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
    "flatpak": RAIZ / "flatpak" / "br.andrefarias.Hefesto.yml",
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
    """A régua das três ocorrências de hoje.

    Mordida: tirar `bt_active_mode.sh` de qualquer um dos quatro formatos.
    """
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
