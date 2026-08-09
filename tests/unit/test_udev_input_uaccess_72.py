"""OQ-6 — o touchpad e o giroscópio funcionavam por acidente.

Ela autorizou, em 09/08/2026: *"autorizo inclusive o touchpad e giroscópio devem
funcionar por default em todos os modos possíveis"*. A medição do mesmo dia
mostrou que **por default eles não funcionavam** — funcionavam porque a usuária
desta máquina está no grupo ``input`` **por fora do produto**.

O ITEM JÁ TINHA NOME, e este módulo usa o nome que a casa deu, não um inventado:

- ``docs/process/sprints/2026-08-07-INDICE-a-ordem-de-execucao-do-que-o-
  diagnostico-abriu.md:372`` — **OQ-6**, *"a regra que daria acesso aos nós de
  entrada nunca foi escrita"*, custo M, marcado para entrar no jogo;
- ``docs/process/sprints/2026-08-08-INDICE-a-madrugada-em-que-o-produto-era-o-
  reu.md:123`` — o mesmo item como **C-3**, grau MEDIDO;
- ``docs/process/sprints/2026-08-09-A-NOITE-DOS-QUATRO-INVENTARIOS-01-o-que-a-
  casa-sabe-e-o-que-o-produto-faz.md:133`` — **F-8**, *"o touchpad e o
  giroscópio dela funcionam por acidente"*.

O QUE FOI MEDIDO (``udevadm info -q property`` nos nós vivos, 09/08/2026)::

    event6  "DualSense Wireless Controller"                 TAGS=:uaccess:seat:
    event7  "DualSense Wireless Controller Motion Sensors"  TAGS=:systemd:
    event8  "DualSense Wireless Controller Touchpad"        TAGS=(vazio)

Só o gamepad ganhava ACL, e quem a dava era a regra do SISTEMA
``/usr/lib/udev/rules.d/70-uaccess.rules``, cuja única linha de input é
``SUBSYSTEM=="input", ENV{ID_INPUT_JOYSTICK}=="?*", TAG+="uaccess"``. Os nós
auxiliares do ``hid_playstation`` não são joystick: o ``input_id`` do kernel
classifica o de movimento como ``ID_INPUT_ACCELEROMETER=1`` e o do touchpad como
``ID_INPUT_TOUCHPAD=1``. Nenhuma regra desta casa os cobria — ``assets/70-*``
cobre só ``SUBSYSTEM=="hidraw"``, e ``scripts/install_udev.sh`` só cria o grupo
``hefesto``, nunca o ``input``.

O CUSTO DO SILÊNCIO: ``core/evdev_reader.py:1396`` engole a ``PermissionError``
num ``except Exception: continue``. Sem acesso, o nó some do mapa de descoberta
e o daemon relata "esse controle não tem sensor". O sintoma da falta de
permissão é a AUSÊNCIA de dado, que não acusa ninguém — a mesma armadilha do
"daemon vivo é mais velho que o código".

A CURA é ``assets/72-hefesto-touchpad-motion-uaccess.rules``, e o item 3.3 de
``docs/history/RESPOSTAS_V1.md`` já mandava exatamente isto em vez de grupo:
*"NÃO adicionar usuário ao grupo input. Criar udev rule seletiva por VID/PID"*.

AS MORDIDAS deste módulo (cada uma foi arrancada e vista reprovar):

- arrancar a linha do touchpad -> ``test_touchpad_tem_uaccess`` reprova;
- arrancar a linha de movimento -> ``test_motion_tem_uaccess`` reprova;
- arrancar a linha da IMU Nintendo -> ``test_imu_nintendo_tem_uaccess`` reprova;
- renumerar o arquivo para >= 73 -> ``test_o_numero_e_menor_que_73`` reprova
  (e este é o dente que importa: o arquivo continuaria instalando, o
  ``udevadm verify`` continuaria aprovando, e a TAG nunca viraria ACL);
- trocar ``TAG+="uaccess"`` por ``GROUP="input"`` -> ``test_nunca_o_grupo_input``
  reprova;
- tirar o ``KERNEL=="event*"`` (deixando a regra pegar os ``jsN`` que a
  ``80-motion-joydev-hide.rules`` esconde de propósito) ->
  ``test_so_event_nunca_js`` reprova.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REGRA = REPO_ROOT / "assets" / "72-hefesto-touchpad-motion-uaccess.rules"

#: Quem transforma ``TAG+="uaccess"`` em ACL é a
#: ``/usr/lib/udev/rules.d/73-seat-late.rules``
#: (``TAG=="uaccess", ENV{MAJOR}!="", RUN{builtin}+="uaccess"``). Regra numerada
#: >= 73 roda DEPOIS dela e a TAG morre inerte — já aconteceu duas vezes nesta
#: casa (a ``71-uhid`` nasceu 79; a ``79-external-controller-leds`` carregava uma
#: TAG morta que o bloco ONDA-R foi remover).
LIMITE_UACCESS = 73


def _linhas_de_codigo(path: Path) -> list[str]:
    """Só linha de CÓDIGO: o comentário que EXPLICA a regra não pode provar nada."""
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


@pytest.fixture(scope="module")
def linhas() -> list[str]:
    if not REGRA.is_file():
        pytest.fail(f"regra ausente: {REGRA}")
    return _linhas_de_codigo(REGRA)


def test_o_arquivo_existe() -> None:
    assert REGRA.is_file(), (
        "sem esta regra, touchpad e giroscópio só funcionam para quem está no "
        "grupo 'input' por fora do produto — numa máquina nova, não funcionam."
    )


def test_o_numero_e_menor_que_73() -> None:
    numero = int(REGRA.name[:2])
    assert numero < LIMITE_UACCESS, (
        f"{REGRA.name}: numerada {numero} >= {LIMITE_UACCESS}. A "
        "73-seat-late.rules já teria passado e a TAG uaccess NUNCA viraria ACL "
        "— o arquivo instala, o udevadm verify aprova, e nada funciona."
    )


def test_cabecalho_marca_origem_hefesto() -> None:
    primeira = REGRA.read_text(encoding="utf-8").splitlines()[0]
    assert "hefesto-dualsense4unix" in primeira, (
        f"{REGRA.name}: primeira linha deve marcar a origem hefesto"
    )


def test_toda_linha_de_codigo_da_uaccess(linhas: list[str]) -> None:
    assert linhas, "o arquivo não tem linha de código nenhuma"
    for ln in linhas:
        assert 'TAG+="uaccess"' in ln, f"linha sem TAG uaccess: {ln}"


def test_motion_tem_uaccess(linhas: list[str]) -> None:
    """O nó do giroscópio é ID_INPUT_ACCELEROMETER — a 70-uaccess não o cobre."""
    alvo = [ln for ln in linhas if "Motion Sensors" in ln]
    assert alvo, (
        "nenhuma linha cobre o nó '… Motion Sensors': o giroscópio do DualSense "
        "fica em root:input e o daemon relata 'esse controle não tem sensor'."
    )
    for ln in alvo:
        assert 'ATTRS{id/vendor}=="054c"' in ln, (
            f"linha de movimento sem âncora de fabricante Sony: {ln}"
        )


def test_touchpad_tem_uaccess(linhas: list[str]) -> None:
    """O nó do touchpad é ID_INPUT_TOUCHPAD — a 70-uaccess também não o cobre."""
    alvo = [ln for ln in linhas if "Touchpad" in ln]
    assert alvo, (
        "nenhuma linha cobre o nó '… Touchpad': o cursor por touchpad e as "
        "teclas de região morrem em EACCES silencioso (evdev_reader.py:1396)."
    )
    for ln in alvo:
        assert 'ATTRS{id/vendor}=="054c"' in ln, (
            f"linha de touchpad sem âncora de fabricante Sony: {ln}"
        )


def test_imu_nintendo_tem_uaccess(linhas: list[str]) -> None:
    """O `hid-nintendo` publica a IMU num nó "<nome> (IMU)" — mesma lacuna.

    Fonte do formato do nome: ``assets/dkms/hid-nintendo/hid-nintendo.c:2353``
    (``devm_kasprintf(..., "%s (IMU)", ctlr->input->name)``).
    """
    alvo = [ln for ln in linhas if "IMU" in ln]
    assert alvo, (
        "nenhuma linha cobre o nó '(IMU)' do hid-nintendo: o giroscópio do "
        "Nintendo Pro / 8BitDo em modo Switch fica inacessível."
    )
    for ln in alvo:
        assert 'ATTRS{id/vendor}=="057e"' in ln, (
            f"linha de IMU sem âncora de fabricante Nintendo: {ln}"
        )


def test_so_event_nunca_js(linhas: list[str]) -> None:
    """Os ``jsN`` estão ESCONDIDOS de propósito pela 80-motion-joydev-hide.

    Dar acesso a eles seria desfazer a KERNEL-07 pelo outro lado: os "joysticks
    fantasmas" da API js legada voltariam a aparecer para jogos antigos.
    """
    for ln in linhas:
        assert 'KERNEL=="event*"' in ln, (
            f'linha sem KERNEL=="event*": {ln}\n'
            "sem essa âncora a regra alcança os jsN que a 80-motion-joydev-hide "
            "esconde de propósito."
        )
        assert "js[" not in ln and 'KERNEL=="js' not in ln, (
            f"linha alcançando nó js legado: {ln}"
        )


def test_nunca_o_grupo_input() -> None:
    """A decisão de RESPOSTAS_V1 item 3.3, e a da 71-uhid: grupo `input` jamais.

    Membro de ``input`` lê TODOS os ``/dev/input/event*`` da máquina — o teclado
    dela inclusive. É uma primitiva de keylogger para resolver um problema de
    touchpad de controle. O ``uaccess`` dá ACL por SESSÃO, só nos nós nomeados.
    """
    texto = REGRA.read_text(encoding="utf-8")
    codigo = "\n".join(_linhas_de_codigo(REGRA))
    assert 'GROUP="input"' not in codigo, (
        "a regra põe os nós no grupo 'input' — proibido: "
        "docs/history/RESPOSTAS_V1.md item 3.3 e assets/71-uhid.rules"
    )
    assert "usermod" not in codigo, "regra udev não mexe em grupo de usuário"
    # O porquê tem de estar escrito no arquivo: a próxima pessoa que achar o
    # grupo mais simples precisa esbarrar na razão antes de trocar.
    assert "keylogger" in texto, (
        "o arquivo não explica por que o grupo 'input' está fora — sem isso a "
        "próxima leva troca uaccess por grupo achando que simplifica."
    )


def test_nao_desfaz_a_76_nem_a_78(linhas: list[str]) -> None:
    """Permissão é uma coisa; classificação é outra.

    A 76 marca ``LIBINPUT_IGNORE_DEVICE`` no touchpad e a 78 tira o
    ``ID_INPUT_JOYSTICK`` do nó de movimento. Se esta regra mexesse em qualquer
    das duas propriedades, curaria o acesso e reabriria dois defeitos fechados
    (cursor engasgado e joystick fantasma na lista do jogo).
    """
    for ln in linhas:
        assert "LIBINPUT_IGNORE_DEVICE" not in ln, (
            f"esta regra não pode tocar a flag da 76: {ln}"
        )
        assert "ID_INPUT_JOYSTICK" not in ln, (
            f"esta regra não pode devolver ID_INPUT_JOYSTICK (regra 78): {ln}"
        )
        assert "MODE=" not in ln, (
            f"esta regra não altera modo — só a TAG, que é o mínimo: {ln}"
        )


def test_cobre_usb_e_bluetooth_pelo_mesmo_atributo(linhas: list[str]) -> None:
    """``id/vendor`` existe por USB E por Bluetooth; ``idVendor`` só por USB.

    Ancorar em ``ATTRS{idVendor}`` (o atributo do pai USB) deixaria o controle
    por Bluetooth de fora em silêncio — e o alvo desta casa são quatro
    controles por Bluetooth, um por jogador.
    """
    for ln in linhas:
        assert "ATTRS{idVendor}" not in ln, (
            f"âncora que só existe por USB — por BT não há pai USB: {ln}"
        )
        assert "ATTRS{id/vendor}" in ln, f"linha sem âncora de fabricante: {ln}"


def test_a_regra_e_instalada_por_todos_os_formatos() -> None:
    """Paridade: a regra que não viaja é a regra que não existe.

    O ``scripts/check_packaging_parity.sh`` cobra isto por conta própria para
    toda ``assets/NN-*.rules``; aqui a cobrança é explícita e nominal, para que
    a falha diga o nome do formato furado sem precisar ler o portão inteiro.
    """
    alvos = {
        "scripts/install_udev.sh": REGRA.name,
        "scripts/install-host-udev.sh": REGRA.name,
        "install.sh": REGRA.name,
        "uninstall.sh": REGRA.name,
        "packaging/arch/PKGBUILD": REGRA.name,
        "packaging/fedora/hefesto-dualsense4unix.spec": REGRA.name,
        "packaging/nix/package.nix": REGRA.name,
        "flatpak/br.andrefarias.Hefesto.yml": REGRA.name,
    }
    faltando = []
    for rel, agulha in alvos.items():
        caminho = REPO_ROOT / rel
        if not caminho.is_file():
            continue
        if agulha not in caminho.read_text(encoding="utf-8"):
            faltando.append(rel)
    assert not faltando, f"{REGRA.name} não chega em: {faltando}"


def test_o_build_deb_cobre_pelo_glob_do_prefixo() -> None:
    """O .deb cobre por glob (``assets/72-*.rules``), não por nome.

    A lista única ``UDEV_RULES_GLOBS`` alimenta os DOIS destinos (o diretório
    vivo e o espelho ``/usr/share/.../udev-rules``, que o
    ``install-host-udev.sh`` prefere e exige completo).
    """
    build = REPO_ROOT / "scripts" / "build_deb.sh"
    if not build.is_file():
        pytest.skip("scripts/build_deb.sh ausente")
    texto = build.read_text(encoding="utf-8")
    prefixo = REGRA.name[:2]
    assert f"assets/{prefixo}-*.rules" in texto or REGRA.name in texto, (
        f"scripts/build_deb.sh não cobre {REGRA.name} (nem por glob "
        f"'assets/{prefixo}-*.rules' nem por nome)"
    )


# ---------------------------------------------------------------------------
# O PORTÃO — a mordida do próprio gate, num repo fake
# ---------------------------------------------------------------------------
# Mesmo padrão de tests/unit/test_check_packaging_parity.py: pytest +
# subprocess num repo fake em tmp_path. Aqui o alvo é a seção NOVA
# ("acesso da sessão aos nós de ENTRADA"), e o contrato é que ela reprove cada
# forma de arrancar a cura — inclusive as duas que um `grep` ingênuo aprovaria:
# a regra virar comentário, e a regra ser renumerada para >= 73.

SCRIPT_REL = "scripts/check_packaging_parity.sh"

#: A regra fake, na forma mínima que a seção nova aceita.
_REGRA_BOA = (
    '# fake\n'
    'ACTION=="add|change", SUBSYSTEM=="input", KERNEL=="event*", '
    'ATTRS{id/vendor}=="054c", ATTRS{name}=="*Motion Sensors", TAG+="uaccess"\n'
    'ACTION=="add|change", SUBSYSTEM=="input", KERNEL=="event*", '
    'ATTRS{id/vendor}=="054c", ATTRS{name}=="*Touchpad", TAG+="uaccess"\n'
)

_BUILD_DEB_FAKE = """\
UDEV_RULES_GLOBS=(
    assets/72-*.rules
)
for rules_file in "${UDEV_RULES_GLOBS[@]}"; do
    cp "$rules_file" "${STAGING}/usr/lib/udev/rules.d/"
done
for rules_file in "${UDEV_RULES_GLOBS[@]}"; do
    install -Dm644 "$rules_file" \
        "${STAGING}/usr/share/hefesto-dualsense4unix/udev-rules/"
done
"""

NOME_FAKE = "72-fake-touchpad-motion-uaccess.rules"


def _semeia_simbolico(raiz: Path) -> None:
    desenho = '<svg viewBox="0 0 16 16"><title>fake</title></svg>\n'
    for alvo in (
        raiz / "assets" / "simbolico" / "hefesto-dualsense4unix-symbolic.svg",
        raiz
        / "packaging"
        / "cosmic-applet"
        / "data"
        / "icons"
        / "hicolor"
        / "symbolic"
        / "apps"
        / "com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg",
    ):
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(desenho, encoding="utf-8")


@pytest.fixture
def repo_fake(tmp_path: Path) -> Path:
    """Repo fake com UMA regra 72 de acesso, coberta em todo instalador."""
    src = REPO_ROOT / SCRIPT_REL
    if not src.exists():
        pytest.skip(f"{SCRIPT_REL} não encontrado")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "flatpak").mkdir()
    (tmp_path / "packaging" / "arch").mkdir(parents=True)
    (tmp_path / "packaging" / "fedora").mkdir(parents=True)
    dst = tmp_path / SCRIPT_REL
    shutil.copy2(src, dst)
    dst.chmod(0o755)

    (tmp_path / "assets" / NOME_FAKE).write_text(_REGRA_BOA, encoding="utf-8")
    (tmp_path / "scripts" / "install_udev.sh").write_text(
        f'sudo install -Dm644 "$ASSETS/{NOME_FAKE}" /etc/udev/rules.d/{NOME_FAKE}\n'
        "sudo udevadm trigger --action=change --subsystem-match=input\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "install-host-udev.sh").write_text(
        f'RULES=("{NOME_FAKE}")\n'
        'cmd+="udevadm trigger --action=change --subsystem-match=input; "\n',
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "build_deb.sh").write_text(
        _BUILD_DEB_FAKE, encoding="utf-8"
    )
    (tmp_path / "packaging" / "arch" / "PKGBUILD").write_text(
        f"    assets/{NOME_FAKE} \\\n", encoding="utf-8"
    )
    (tmp_path / "packaging" / "fedora" / "hefesto-dualsense4unix.spec").write_text(
        f"    assets/{NOME_FAKE}\n", encoding="utf-8"
    )
    (tmp_path / "uninstall.sh").write_text(
        f"sudo rm -f /etc/udev/rules.d/{NOME_FAKE}\n", encoding="utf-8"
    )
    (tmp_path / "flatpak" / "fake.yml").write_text(
        f"      - install -Dm644 assets/{NOME_FAKE}\n", encoding="utf-8"
    )
    _semeia_simbolico(tmp_path)
    return tmp_path


def _roda(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", SCRIPT_REL],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


class TestOPortaoMorde:
    SECAO = "acesso da sessão aos nós de ENTRADA"

    def test_com_a_regra_o_portao_passa(self, repo_fake: Path) -> None:
        r = _roda(repo_fake)
        assert self.SECAO in r.stdout, "a seção nova não rodou"
        assert r.returncode == 0, r.stdout

    def test_o_estado_anterior_a_09_08_reprova(self, repo_fake: Path) -> None:
        """O repo COM regras udev e SEM nenhuma que dê acesso à entrada.

        É literalmente o estado do repositório até 09/08/2026: quinze regras,
        nenhuma tocando ``/dev/input/event*``. O arquivo continua existindo e
        continua coberto por todo instalador — só não concede nada. É a forma
        do defeito, e é ela que o portão tem de acusar.
        """
        (repo_fake / "assets" / NOME_FAKE).write_text(
            '# fake — regra que existe e não dá acesso nenhum à entrada\n'
            'ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="054c", '
            'ATTR{power/control}="on"\n',
            encoding="utf-8",
        )
        r = _roda(repo_fake)
        assert r.returncode == 1
        assert "SENSORES DE MOVIMENTO" in r.stdout
        assert "TOUCHPAD" in r.stdout

    def test_checkout_sem_regra_udev_alguma_fica_silencioso(
        self, repo_fake: Path
    ) -> None:
        """Limite consciente, no molde dos outros blocos deste portão.

        Fixture mínima de outro teste (sem ``assets/NN-*.rules``) não pode
        reprovar por uma seção que não é o alvo dela. Fica pinado aqui para que
        seja decisão, e não acidente de escrita.
        """
        (repo_fake / "assets" / NOME_FAKE).unlink()
        r = _roda(repo_fake)
        assert r.returncode == 0, r.stdout
        assert "nada a checar" in r.stdout

    def test_a_regra_virando_comentario_reprova(self, repo_fake: Path) -> None:
        """O texto continua no arquivo — e o portão continua reprovando."""
        alvo = repo_fake / "assets" / NOME_FAKE
        alvo.write_text(
            "\n".join(
                "# " + ln if ln.startswith("ACTION") else ln
                for ln in _REGRA_BOA.splitlines()
            )
            + "\n",
            encoding="utf-8",
        )
        r = _roda(repo_fake)
        assert r.returncode == 1, (
            "comentário satisfez o portão — é o vácuo que a seção do BlueZ já "
            "pagou uma vez"
        )
        assert "SENSORES DE MOVIMENTO" in r.stdout

    def test_a_regra_renumerada_para_79_reprova(self, repo_fake: Path) -> None:
        """O dente que importa: >= 73 a TAG nunca vira ACL."""
        novo = NOME_FAKE.replace("72-", "79-", 1)
        (repo_fake / "assets" / NOME_FAKE).rename(repo_fake / "assets" / novo)
        for rel in (
            "scripts/install_udev.sh",
            "scripts/install-host-udev.sh",
            "scripts/build_deb.sh",
            "packaging/arch/PKGBUILD",
            "packaging/fedora/hefesto-dualsense4unix.spec",
            "uninstall.sh",
            "flatpak/fake.yml",
        ):
            p = repo_fake / rel
            p.write_text(
                p.read_text(encoding="utf-8")
                .replace(NOME_FAKE, novo)
                .replace("assets/72-*.rules", "assets/79-*.rules"),
                encoding="utf-8",
            )
        r = _roda(repo_fake)
        assert r.returncode == 1, (
            "regra numerada 79 passou verde — ela instala, o udevadm verify "
            "aprova, e a TAG NUNCA vira ACL (a 73-seat-late já passou)"
        )
        assert "NUNCA vira ACL" in r.stdout

    def test_so_o_touchpad_coberto_reprova(self, repo_fake: Path) -> None:
        alvo = repo_fake / "assets" / NOME_FAKE
        alvo.write_text(
            "\n".join(
                ln for ln in _REGRA_BOA.splitlines() if "Motion Sensors" not in ln
            )
            + "\n",
            encoding="utf-8",
        )
        r = _roda(repo_fake)
        assert r.returncode == 1
        assert "SENSORES DE MOVIMENTO" in r.stdout

    def test_so_o_movimento_coberto_reprova(self, repo_fake: Path) -> None:
        alvo = repo_fake / "assets" / NOME_FAKE
        alvo.write_text(
            "\n".join(ln for ln in _REGRA_BOA.splitlines() if "Touchpad" not in ln)
            + "\n",
            encoding="utf-8",
        )
        r = _roda(repo_fake)
        assert r.returncode == 1
        assert "TOUCHPAD" in r.stdout

    def test_sem_o_trigger_de_input_reprova(self, repo_fake: Path) -> None:
        """Sem o trigger, a regra só valeria no próximo replug do controle."""
        p = repo_fake / "scripts" / "install_udev.sh"
        p.write_text(
            p.read_text(encoding="utf-8").replace("--subsystem-match=input", ""),
            encoding="utf-8",
        )
        r = _roda(repo_fake)
        assert r.returncode == 1
        assert "próximo replug" in r.stdout
