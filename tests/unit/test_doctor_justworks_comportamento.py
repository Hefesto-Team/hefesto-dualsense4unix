"""RADIO-ABERTO-01/E1-bis — o detector de `JustWorksRepairing` tem MORDIDA?"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.conftest import arvore_congelada

RAIZ = arvore_congelada()
DOCTOR = RAIZ / "scripts" / "doctor.sh"
BLUEZ = RAIZ / "scripts" / "bluez_config.sh"
FUNCAO = "check_bluez_justworks_repairing"

_MAIN_CONF = {
    "confirm": "[General]\nFastConnectable=true\nJustWorksRepairing=confirm\n",
    "always": "[General]\nFastConnectable=true\nJustWorksRepairing=always\n",
    "never": "[General]\nJustWorksRepairing=never\n",
    "ausente": "[General]\nName = BlueZ\n",
}


def _extrair_funcao() -> str:
    """A função, tal como está no doctor.sh de hoje — nunca uma cópia."""
    proc = subprocess.run(
        ["awk", f"/^{FUNCAO}\\(\\) \\{{/ {{ dentro = 1 }} dentro {{ print }} "
         "dentro && /^\\}$/ { exit }", str(DOCTOR)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    corpo = proc.stdout
    assert corpo.startswith(f"{FUNCAO}() {{"), (
        f"não achei a função {FUNCAO} em {DOCTOR} — se ela foi renomeada, o "
        "detector de JustWorksRepairing perdeu a bancada que o exercita"
    )
    assert corpo.rstrip().endswith("}"), "a extração da função não fechou"
    return corpo


def _harness(tmp_path: Path, agente: str = "active") -> Path:
    """Stubs mínimos + a função de verdade. `agente` = o que o systemctl diz."""
    bin_falso = tmp_path / "bin"
    bin_falso.mkdir(exist_ok=True)
    (bin_falso / "systemctl").write_text(
        "#!/usr/bin/env bash\n"
        f'if [[ "$1" == "is-active" ]]; then printf "{agente}\\n"; '
        f'[[ "{agente}" == "active" ]] || exit 3; fi\nexit 0\n',
        encoding="utf-8",
    )
    (bin_falso / "systemctl").chmod(0o755)

    script = tmp_path / "harness.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -uo pipefail\n"
        "QUIET=0; FAILS=0; WARNS=0\n"
        "pass() { printf '[ OK ] %s\\n' \"$*\"; }\n"
        "fail() { printf '[FAIL] %s\\n' \"$*\"; FAILS=$((FAILS + 1)); }\n"
        "warn() { printf '[WARN] %s\\n' \"$*\"; WARNS=$((WARNS + 1)); }\n"
        "info() { printf '       %s\\n' \"$*\"; }\n"
        f'ROOT_DIR="{RAIZ}"\n'
        + _extrair_funcao()
        + f"\n{FUNCAO}\n"
        "printf 'RESUMO fails=%s warns=%s\\n' \"${FAILS}\" \"${WARNS}\"\n",
        encoding="utf-8",
    )
    return script


def _rodar(
    tmp_path: Path,
    main_conf: str | None,
    agente: str = "active",
    extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    etc = tmp_path / "bluetooth"
    etc.mkdir(exist_ok=True)
    if main_conf is not None:
        (etc / "main.conf").write_text(main_conf, encoding="utf-8")
    script = _harness(tmp_path, agente=agente)
    import os

    ambiente = {
        **os.environ,
        "HEFESTO_BT_ETC": str(etc),
        "HEFESTO_BT_ASSETS": str(RAIZ / "assets" / "bluetooth"),
        "PATH": f"{tmp_path / 'bin'}:{os.environ.get('PATH', '')}",
        "HEFESTO_MARCA_SANDBOX": str(tmp_path / "sem-flatpak-info"),
        "HEFESTO_MARCA_CONTAINER": str(tmp_path / "sem-containerenv"),
        "FLATPAK_ID": "",
        "SNAP": "",
        **(extra or {}),
    }
    return subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, timeout=60, env=ambiente
    )


def test_always_reprova_e_nao_ganha_selo_verde(tmp_path: Path) -> None:
    """A MUTAÇÃO (A): `fail` virando `pass` deixava a suíte inteira verde."""
    proc = _rodar(tmp_path, _MAIN_CONF["always"])

    assert "[FAIL]" in proc.stdout, (
        "o detector deixou de REPROVAR JustWorksRepairing=always — é a mutação "
        "que a suíte inteira aceitou verde em 06/08/2026"
    )
    assert "[ OK ]" not in proc.stdout, "o valor perigoso saiu com selo verde"
    assert "always" in proc.stdout
    assert "injeção de teclas" in proc.stdout
    assert "RESUMO fails=1" in proc.stdout


def test_confirm_e_aprovado(tmp_path: Path) -> None:
    """Linha de base: sem ela, um detector que reprova tudo 'passaria' no (A)."""
    proc = _rodar(tmp_path, _MAIN_CONF["confirm"])

    assert "[ OK ]" in proc.stdout
    assert "confirm" in proc.stdout
    assert "RESUMO fails=0 warns=0" in proc.stdout


def test_confirm_com_agente_morto_reprova(tmp_path: Path) -> None:
    """A contrapartida honesta da cura: `confirm` DEPENDE do agente registrado."""
    proc = _rodar(tmp_path, _MAIN_CONF["confirm"], agente="inactive")

    assert "[ OK ]" in proc.stdout, "o valor continua certo; o que falta é o agente"
    assert "[FAIL]" in proc.stdout, (
        "o agente morto voltou a sair como aviso — ver a BG-06"
    )
    assert "hefesto-bt-agent.service" in proc.stdout
    assert "RESUMO fails=1 warns=0" in proc.stdout


def test_chave_ausente_avisa_o_default_da_distro(tmp_path: Path) -> None:
    """Sem a chave, quem manda é o default da distro — que não é decisão nossa."""
    proc = _rodar(tmp_path, _MAIN_CONF["ausente"])

    assert "[WARN]" in proc.stdout
    assert "não está declarado" in proc.stdout
    assert "RESUMO fails=0 warns=1" in proc.stdout


def test_never_avisa_sem_prometer_o_que_nao_cumpre(tmp_path: Path) -> None:
    """`never` é MAIS restritivo que o nosso `confirm` — e a promessa tem ressalva."""
    proc = _rodar(tmp_path, _MAIN_CONF["never"])

    assert "[WARN]" in proc.stdout
    assert "never" in proc.stdout
    assert "MAIS restritivo" in proc.stdout
    assert "FORA das sentinelas" in proc.stdout and "DENTRO do bloco" in proc.stdout, (
        "o aviso voltou a prometer a devolução sem dizer que ela só vale FORA "
        "do bloco — é a promessa falsa no lugar mais provável"
    )


def test_arquivo_ilegivel_nao_vira_nao_declarado(tmp_path: Path) -> None:
    """"não consigo ler" e "não declarado" são coisas MUITO diferentes."""
    import os

    if os.geteuid() == 0:
        pytest.skip("root lê qualquer modo; o cenário não existe")
    etc = tmp_path / "bluetooth"
    etc.mkdir(exist_ok=True)
    (etc / "main.conf").write_text(_MAIN_CONF["always"], encoding="utf-8")
    (etc / "main.conf").chmod(0o000)
    try:
        proc = _rodar(tmp_path, None)
    finally:
        (etc / "main.conf").chmod(0o644)

    assert "[WARN]" in proc.stdout
    assert "não consigo LER" in proc.stdout
    assert "não está declarado" not in proc.stdout


def test_sem_main_conf_o_detector_pula_em_vez_de_reprovar(tmp_path: Path) -> None:
    """Máquina sem BlueZ não é máquina insegura."""
    proc = _rodar(tmp_path, None)

    assert "RESUMO fails=0 warns=0" in proc.stdout
    assert "BlueZ ausente" in proc.stdout


def test_dentro_do_sandbox_o_detector_diz_que_nao_sabe(tmp_path: Path) -> None:
    """CEGO E SILENCIOSO era o pior dos dois (achado de 06/08/2026)."""
    marca = tmp_path / "flatpak-info-de-mentira"
    marca.write_text(
        "[Application]\nname=io.github.hefesto_team.hefesto_dualsense4unix\n",
        encoding="utf-8",
    )

    proc = _rodar(tmp_path, None, extra={"HEFESTO_MARCA_SANDBOX": str(marca)})

    assert "[WARN]" in proc.stdout, (
        "dentro do sandbox o detector ficou CEGO E SILENCIOSO — o host pode "
        f"estar com always e ninguém fica sabendo. Saída: {proc.stdout}"
    )
    assert "NÃO SEI" in proc.stdout
    assert "sandbox" in proc.stdout
    assert "RESUMO fails=0 warns=1" in proc.stdout
    assert "pulo o check" not in proc.stdout, (
        "ainda sai a frase que trata 'não consigo ver' como 'não existe'"
    )


def test_sandbox_que_enxerga_o_arquivo_julga_normalmente(tmp_path: Path) -> None:
    """O marcador não sequestra a leitura: se o arquivo está lá, ele vale."""
    marca = tmp_path / "flatpak-info-de-mentira"
    marca.write_text("[Application]\n", encoding="utf-8")

    proc = _rodar(
        tmp_path, _MAIN_CONF["always"], extra={"HEFESTO_MARCA_SANDBOX": str(marca)}
    )

    assert "[FAIL]" in proc.stdout, "o sandbox virou desculpa para não julgar"
    assert "NÃO SEI" not in proc.stdout
    assert "RESUMO fails=1" in proc.stdout


def test_sem_o_dono_unico_o_detector_avisa_em_vez_de_inventar(tmp_path: Path) -> None:
    """Sem `bluez_config.sh` ao lado, o doctor NÃO pode dizer "não declarado"."""
    etc = tmp_path / "bluetooth"
    etc.mkdir(exist_ok=True)
    (etc / "main.conf").write_text(_MAIN_CONF["always"], encoding="utf-8")
    script = _harness(tmp_path)
    corpo = script.read_text(encoding="utf-8").replace(
        f'ROOT_DIR="{RAIZ}"', f'ROOT_DIR="{tmp_path / "raiz-sem-dono"}"'
    )
    script.write_text(corpo, encoding="utf-8")
    import os

    proc = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HEFESTO_BT_ETC": str(etc)},
    )

    assert "[WARN]" in proc.stdout
    assert "o dono único da config do BlueZ não está aqui" in proc.stdout
    assert "[ OK ]" not in proc.stdout


def _corpo_do_main() -> str:
    proc = subprocess.run(
        ["awk", "/^main\\(\\) \\{$/ { dentro = 1 } dentro { print } "
         "dentro && /^\\}$/ { exit }", str(DOCTOR)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.stdout.startswith("main() {"), "não achei main() em scripts/doctor.sh"
    return proc.stdout


def test_o_detector_e_chamado_por_main(tmp_path: Path) -> None:
    """ENTREGA-QUE-NAO-LIGOU-01 literal: função viva e nunca chamada."""
    corpo = _corpo_do_main()
    chamadas = [
        ln.strip() for ln in corpo.splitlines() if ln.strip() == FUNCAO
    ]
    assert chamadas == [FUNCAO], (
        f"{FUNCAO} não é chamada dentro de main() — o detector de "
        "JustWorksRepairing=always ficou vivo e desligado"
    )


def test_o_detector_e_chamado_no_bloco_de_radio(tmp_path: Path) -> None:
    """E chamado ONDE se vê: junto dos vizinhos de rádio, não num canto morto."""
    corpo = _corpo_do_main()
    linhas = [ln.strip() for ln in corpo.splitlines()]
    i = linhas.index(FUNCAO)
    vizinhos = linhas[max(0, i - 3):i + 3]
    assert "check_bluez_fastconnectable" in vizinhos, (
        "o detector saiu de perto do check irmão de BlueZ — se mudou de lugar "
        "de propósito, mova esta asserção junto e diga por quê"
    )


def test_empacotamento_leva_o_dono_do_bluez() -> None:
    """Quem leva o `doctor.sh` leva o `bluez_config.sh`. Sem exceção."""
    empacotadores = [
        RAIZ / "scripts" / "build_deb.sh",
        RAIZ / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.yml",
        RAIZ / "scripts" / "build_appimage.sh",
        RAIZ / "scripts" / "build_appimage_gui.sh",
        RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
        RAIZ / "packaging" / "arch" / "PKGBUILD",
        RAIZ / "packaging" / "nix" / "package.nix",
    ]
    sem_dono = []
    levam_doctor = []
    for arquivo in empacotadores:
        if not arquivo.exists():
            continue
        codigo = "\n".join(
            ln for ln in arquivo.read_text(encoding="utf-8").splitlines()
            if not ln.lstrip().startswith("#")
        )
        if "doctor.sh" not in codigo:
            continue
        levam_doctor.append(arquivo.name)
        if "bluez_config.sh" not in codigo:
            sem_dono.append(arquivo.name)

    assert levam_doctor, (
        "nenhum empacotamento leva o doctor.sh — se isso mudou de propósito, "
        "este teste tem de mudar junto"
    )
    assert sem_dono == [], (
        f"empacotamento leva o doctor.sh e deixa o bluez_config.sh para trás: "
        f"{sem_dono}. O detector cai no ramo 'o dono único não está aqui' e a "
        "máquina fica sem enxergar JustWorksRepairing=always."
    )


class TestOSeloVerdeNaoSaiAntesDoDaemonCarregar:
    """SELO-VERDE-CEDO-DEMAIS-01 (06/08/2026)."""

    def test_config_mais_nova_que_o_daemon_avisa(self, tmp_path: Path) -> None:
        """O ramo que fecha o defeito: o disco já mudou, o daemon não sabe."""
        proc = _rodar(
            tmp_path,
            _MAIN_CONF["confirm"],
            extra={"HEFESTO_BT_ATIVO_DESDE": "1"},
        )

        assert "[ OK ]" in proc.stdout, "o valor no disco continua certo"
        assert "daemon VIVO ainda roda com o valor anterior" in proc.stdout
        assert "RESUMO fails=0 warns=1" in proc.stdout

    def test_daemon_mais_novo_que_a_config_nao_avisa(self, tmp_path: Path) -> None:
        """A contraprova: com o daemon reiniciado DEPOIS, o aviso é ruído."""
        proc = _rodar(
            tmp_path,
            _MAIN_CONF["confirm"],
            extra={"HEFESTO_BT_ATIVO_DESDE": "9999999999"},
        )

        assert "[ OK ]" in proc.stdout
        assert "daemon VIVO ainda roda" not in proc.stdout
        assert "RESUMO fails=0 warns=0" in proc.stdout

    def test_sem_systemd_que_responda_o_aviso_se_cala(self, tmp_path: Path) -> None:
        """O defeito que a cura da cura fechou, e que era de PRODUÇÃO."""
        proc = _rodar(tmp_path, _MAIN_CONF["confirm"])

        assert "[ OK ] " in proc.stdout
        assert "daemon VIVO ainda roda" not in proc.stdout, (
            "o aviso voltou a sair sem saber a hora do daemon — é o falso "
            "positivo do `date -d ''`, que devolve meia-noite em vez de falhar"
        )
        assert "RESUMO fails=0 warns=0" in proc.stdout


def test_o_detector_le_so_pelo_dono_unico() -> None:
    """Duas fontes para a mesma regra é a classe de defeito desta leva."""
    doctor = DOCTOR.read_text(encoding="utf-8")
    assert '"${dono}" verificar' in doctor
    assert "JustWorksRepairing[[:space:]]*=" not in doctor, (
        "o doctor voltou a ter o próprio parser de JustWorksRepairing"
    )
    assert BLUEZ.exists()
