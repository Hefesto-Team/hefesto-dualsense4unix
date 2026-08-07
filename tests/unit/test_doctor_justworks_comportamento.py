"""RADIO-ABERTO-01/E1-bis — o detector de `JustWorksRepairing` tem MORDIDA?

O DEFEITO DESTA BANCADA (MEDIDO em 06/08/2026, por duas mutações independentes
que deixavam a suíte INTEIRA verde — 138 passed e paridade OK nas duas):

  (A) trocar ``fail "JustWorksRepairing=always ATIVO...`` por ``pass "...`` em
      ``scripts/doctor.sh``. O doctor passava a APROVAR, com selo verde, o valor
      que a própria sprint classifica como injeção de teclas.
  (C) apagar a linha ``check_bluez_justworks_repairing`` de ``main()``. A função
      ficava viva e NUNCA CHAMADA — ENTREGA-QUE-NAO-LIGOU-01 literal.

Os dois únicos testes que existiam (``test_doctor_le_pelo_dono_unico`` e
``test_doctor_avisa_em_vez_de_mentir_quando_o_dono_some``) são grep de TEXTO e
sobreviviam às duas mutilações; o portão de paridade também, porque procurava
palavras que continuam vivas DENTRO da função morta.

COMO ESTA BANCADA MORDE

Ela EXECUTA a função. O harness extrai ``check_bluez_justworks_repairing`` do
``scripts/doctor.sh`` por ``awk`` (do cabeçalho até o ``}`` de coluna 1), põe por
cima stubs de ``pass``/``fail``/``warn``/``info`` que só imprimem o rótulo, e a
roda contra uma RAIZ FALSA (``HEFESTO_BT_ETC``) com um ``systemctl`` de mentira
no ``PATH``. Nada em ``/etc`` é lido, nada é escrito, e não é preciso root.

A extração por ``awk`` é deliberada: se alguém renomear a função, o harness não
a encontra e TODOS os testes deste arquivo ficam vermelhos — renomear não é
rota de fuga.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.conftest import arvore_congelada

#: Cópia da árvore tirada uma vez por sessão — ver ARVORE-CONGELADA-01 em
#: `tests/conftest.py`. Esta bancada EXTRAI a função do `scripts/doctor.sh` por
#: `awk` e a EXECUTA; se o arquivo mudar debaixo da medição (agente irmão,
#: `git checkout`, editor salvando), o veredito é sobre o produto de outra
#: pessoa. MEDIDO em 06/08/2026, com reprodução em três braços.
RAIZ = arvore_congelada()
DOCTOR = RAIZ / "scripts" / "doctor.sh"
BLUEZ = RAIZ / "scripts" / "bluez_config.sh"
FUNCAO = "check_bluez_justworks_repairing"

#: Os cinco valores que o `case` do detector distingue, e o veredito que cada um
#: TEM de produzir. A tabela é o contrato: `always` é `[FAIL]` e não `[WARN]`,
#: porque a sprint o classifica como injeção de teclas.
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
        # Os marcadores de sandbox apontam para caminhos que NÃO EXISTEM por
        # padrão: a bancada roda fora de container, e um teste que dependesse
        # do `/.flatpak-info` da máquina seria um teste diferente a cada máquina.
        "HEFESTO_MARCA_SANDBOX": str(tmp_path / "sem-flatpak-info"),
        "HEFESTO_MARCA_CONTAINER": str(tmp_path / "sem-containerenv"),
        "FLATPAK_ID": "",
        "SNAP": "",
        **(extra or {}),
    }
    return subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, timeout=60, env=ambiente
    )


# ---------------------------------------------------------------------------
# Os cinco ramos, executados
# ---------------------------------------------------------------------------


def test_always_reprova_e_nao_ganha_selo_verde(tmp_path: Path) -> None:
    """A MUTAÇÃO (A): `fail` virando `pass` deixava a suíte inteira verde.

    `always` remove a última recusa do BlueZ ao re-pareamento por Just Works de
    quem já tem bond. Com o agente NoInputNoOutput, isso termina em injeção de
    teclas. O veredito é `[FAIL]`, não `[WARN]` e muito menos `[ OK ]`.
    """
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


def test_confirm_com_agente_morto_avisa(tmp_path: Path) -> None:
    """A contrapartida honesta da cura: `confirm` DEPENDE do agente registrado.

    Com o `hefesto-bt-agent.service` morto (já falhou duas vezes em 04/08), o
    re-pareamento legítimo dela é RECUSADO — e é o doctor que tem de dizer isso
    antes que ela descubra pelo controle que não conecta.
    """
    proc = _rodar(tmp_path, _MAIN_CONF["confirm"], agente="inactive")

    assert "[ OK ]" in proc.stdout, "o valor continua certo; o que falta é o agente"
    assert "[WARN]" in proc.stdout
    assert "hefesto-bt-agent.service" in proc.stdout
    assert "RESUMO fails=0 warns=1" in proc.stdout


def test_chave_ausente_avisa_o_default_da_distro(tmp_path: Path) -> None:
    """Sem a chave, quem manda é o default da distro — que não é decisão nossa."""
    proc = _rodar(tmp_path, _MAIN_CONF["ausente"])

    assert "[WARN]" in proc.stdout
    assert "não está declarado" in proc.stdout
    assert "RESUMO fails=0 warns=1" in proc.stdout


def test_never_avisa_sem_prometer_o_que_nao_cumpre(tmp_path: Path) -> None:
    """`never` é MAIS restritivo que o nosso `confirm` — e a promessa tem ressalva.

    A promessa antiga ("a sua linha é neutralizada, e o remover a devolve") é
    FALSA quando o `never` está DENTRO do bloco hefesto, que é justamente onde
    quem lê este aviso vai escrever. Hoje o aviso separa os dois casos.
    """
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
    """Máquina sem BlueZ não é máquina insegura.

    E é a LINHA DE BASE do par de testes de sandbox abaixo: fora de container, a
    ausência do arquivo continua sendo `info`, sem WARN e sem FAIL.
    """
    proc = _rodar(tmp_path, None)

    assert "RESUMO fails=0 warns=0" in proc.stdout
    assert "BlueZ ausente" in proc.stdout


def test_dentro_do_sandbox_o_detector_diz_que_nao_sabe(tmp_path: Path) -> None:
    """CEGO E SILENCIOSO era o pior dos dois (achado de 06/08/2026).

    Dentro do Flatpak, `/etc/bluetooth` não existe: o manifesto não pede
    `--filesystem=host`, então o /etc do host não é alcançável. A função caía no
    ramo "BlueZ ausente?" e imprimia `info ... pulo o check` — nem WARN, nem
    FAIL — numa máquina cujo HOST tem `JustWorksRepairing=always` ATIVO. Pior
    que o caso do `.deb`, que ao menos avisava.

    "Não existe" e "não consigo ver" são respostas diferentes, e a segunda tem
    de ser dita em voz alta: é a diferença entre "você está segura" e "eu não
    sei se você está segura".
    """
    marca = tmp_path / "flatpak-info-de-mentira"
    marca.write_text("[Application]\nname=br.andrefarias.Hefesto\n", encoding="utf-8")

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
    """O marcador não sequestra a leitura: se o arquivo está lá, ele vale.

    Sem esta metade, um `--filesystem=host` no manifesto (ou um Flatpak que
    monte o /etc) faria o doctor virar um "não sei" permanente — trocar um
    silêncio por um ruído não é cura.
    """
    marca = tmp_path / "flatpak-info-de-mentira"
    marca.write_text("[Application]\n", encoding="utf-8")

    proc = _rodar(
        tmp_path, _MAIN_CONF["always"], extra={"HEFESTO_MARCA_SANDBOX": str(marca)}
    )

    assert "[FAIL]" in proc.stdout, "o sandbox virou desculpa para não julgar"
    assert "NÃO SEI" not in proc.stdout
    assert "RESUMO fails=1" in proc.stdout


def test_sem_o_dono_unico_o_detector_avisa_em_vez_de_inventar(tmp_path: Path) -> None:
    """Sem `bluez_config.sh` ao lado, o doctor NÃO pode dizer "não declarado".

    É o layout do `.deb` antes desta leva: o `doctor.sh` viajava sozinho e a
    função caía neste ramo contra o /etc REAL, que tem `always`. Ver
    `test_empacotamento_leva_o_dono_do_bluez` (bancada de paridade).
    """
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


# ---------------------------------------------------------------------------
# A CHAMADA — a mutação (C) apagava a linha de `main()` e ninguém via
# ---------------------------------------------------------------------------


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
    """ENTREGA-QUE-NAO-LIGOU-01 literal: função viva e nunca chamada.

    MEDIDO: apagar esta linha de `main()` deixava 138 passed e a paridade OK.
    O grep é dentro do CORPO de `main()` — a definição da função (que continua
    existindo na mutação) fica de fora por construção.
    """
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


# ---------------------------------------------------------------------------
# O EMPACOTAMENTO — o doctor empacotado era CEGO (achado de 06/08/2026)
# ---------------------------------------------------------------------------


def test_empacotamento_leva_o_dono_do_bluez() -> None:
    """Quem leva o `doctor.sh` leva o `bluez_config.sh`. Sem exceção.

    MEDIDO: `scripts/build_deb.sh` copiava `doctor.sh` e NÃO copiava
    `bluez_config.sh`. Como o detector lê EXCLUSIVAMENTE pelo dono único em
    `${ROOT_DIR}/scripts/bluez_config.sh`, no layout do .deb ele caía no ramo
    "o dono único da config do BlueZ não está aqui" e NÃO VIA NADA — reproduzido
    contra o /etc REAL desta máquina, que tem `always`.

    O curador anterior registrou isso como dívida de empacotamento com a
    justificativa "exige postinst próprio, e é entrega à parte": verdade para
    APLICAR a config (reescreve conffile do dpkg), FALSO para o DETECTOR, que é
    leitura pura e entra numa linha do laço `for _s in ...` que já existia.
    """
    # O FLATPAK ENTRA PELO MANIFESTO, não pelo invólucro (achado de 06/08/2026,
    # MEDIDO): `scripts/build_flatpak.sh` tem 120 linhas, chama o
    # `flatpak-builder` e NÃO LISTA ARQUIVO NENHUM. Quem declara o conteúdo do
    # pacote é `flatpak/br.andrefarias.Hefesto.yml`. Com o invólucro na lista,
    # pôr o `doctor.sh` no manifesto sem o `bluez_config.sh` passava verde aqui
    # e no `check_packaging_parity.sh`: o invólucro não cita `doctor.sh`, o
    # `continue` disparava, e a regra de PAR nunca alcançava o Flatpak.
    empacotadores = [
        RAIZ / "scripts" / "build_deb.sh",
        RAIZ / "flatpak" / "br.andrefarias.Hefesto.yml",
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
        # SÓ LINHA DE CÓDIGO CONTA. Procurar a palavra no arquivo inteiro é o
        # que fez o portão de paridade passar verde com o `bluez_config.sh`
        # arrancado da linha de cópia do `build_deb.sh` (MEDIDO por mutação):
        # o próprio comentário que EXPLICA a regra a satisfazia.
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


def test_o_detector_le_so_pelo_dono_unico() -> None:
    """Duas fontes para a mesma regra é a classe de defeito desta leva."""
    doctor = DOCTOR.read_text(encoding="utf-8")
    assert '"${dono}" verificar' in doctor
    assert "JustWorksRepairing[[:space:]]*=" not in doctor, (
        "o doctor voltou a ter o próprio parser de JustWorksRepairing"
    )
    assert BLUEZ.exists()
