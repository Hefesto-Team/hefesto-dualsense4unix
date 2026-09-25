"""O doctor acusa o que o udev DECIDIU sobre o nó físico, e quem o segura.

O-FISICO-NASCE-ESCONDIDO-EM-QUALQUER-MAQUINA-01 (25/09/2026). Na mesa dela, o
doctor saiu `rc=0, tudo OK` com três DualSense físicos nascendo com a ACL da
sessão e a Steam segurando os três: o `check_udev` confere que o ARQUIVO da
regra existe, e o `_veredito_do_hide` que o nó está FECHADO agora — e nenhum
dos dois responde as duas perguntas que decidiam:

1. o udev deu a tag corrente `uaccess` (`Q:` no banco dele) ao nó físico? E,
   se deu, QUAL regra de terceiro a devolveu depois da nossa?
2. quem, além do Hefesto, tem o nó aberto agora (`/proc/<pid>/fd`)?

E o carimbo do nascimento condenado, que o daemon publica no `state_full`, não
era lido por ninguém desde que a janela GTK saiu.

As funções shell REAIS rodam aqui por `source` (o molde de
`test_acusa_o_culpado_01_o_doctor_que_acusava_a_pessoa_errada.py`), contra um
banco do udev, um /sys, um /proc e diretórios de regras DE MENTIRA. Nada lê o
/run, o /sys, o /proc nem o /etc de verdade, e o socket do daemon é um servidor
de mentira numa pasta temporária.

AS MORDIDAS, medidas em 25/09/2026:
  - `_tags_correntes_do_no` lendo `G:` em vez de `Q:` → a régua da tag
    pegajosa reprova (o nó fechado seria acusado de aberto);
  - o filtro do `hefesto` fora de `_veredito_de_quem_segura_o_fisico` → a
    régua do daemon reprova (o próprio Hefesto seria acusado);
  - o `pede_reconexao` ignorado em `_veredito_dos_nascimentos` → a régua do
    condenado reprova.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
TERCEIROS = RAIZ / "tests" / "fixtures" / "udev" / "de-terceiros"
NOVA = "73-hefesto-ps5-controller.rules"
VELHA = "70-ps5-controller.rules"


def _chamar(funcao: str, *args: str) -> str:
    """Executa uma função do doctor de verdade, via `source`, e devolve a saída."""
    res = subprocess.run(
        [
            "bash",
            "-c",
            # O `set --` cala o parser de argumentos do doctor no `source`; os
            # argumentos da função vão guardados antes.
            f'ARGS=("$@"); set --; source "$DOCTOR_SH"; {funcao} "${{ARGS[@]}}"',
            "doctor",
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"DOCTOR_SH": str(DOCTOR), "PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"},
    )
    assert res.returncode == 0, res.stderr
    return res.stdout


# ---------------------------------------------------------------------------
# A máquina de mentira: regras, banco do udev e /sys
# ---------------------------------------------------------------------------


def _regras(tmp: Path, *, nossa: str, extra: dict[str, str] | None = None) -> tuple[Path, Path]:
    etc = tmp / "etc" / "udev" / "rules.d"
    usr = tmp / "usr" / "lib" / "udev" / "rules.d"
    etc.mkdir(parents=True)
    usr.mkdir(parents=True)
    shutil.copy(RAIZ / "assets" / NOVA, etc / nossa)
    for nome in ("60-steam-input.rules", "71-sony-controllers.rules", "71-seat.rules",
                 "73-seat-late.rules"):
        shutil.copy(TERCEIROS / nome, usr / nome)
    for nome, texto in (extra or {}).items():
        (usr / nome).write_text(texto, encoding="utf-8")
    return etc, usr


def _no(tmp: Path, base: str, dev: str, hid_id: str, banco_do_no: str) -> None:
    """Um hidraw no /sys de mentira e a entrada dele no banco do udev."""
    sysdir = tmp / "sys" / "class" / "hidraw" / base
    (sysdir / "device").mkdir(parents=True)
    (sysdir / "dev").write_text(dev + "\n", encoding="utf-8")
    (sysdir / "device" / "uevent").write_text(
        f"DRIVER=playstation\nHID_ID={hid_id}\nHID_NAME=DualSense Wireless Controller\n",
        encoding="utf-8",
    )
    banco = tmp / "run" / "udev" / "data"
    banco.mkdir(parents=True, exist_ok=True)
    (banco / f"c{dev}").write_text(banco_do_no, encoding="utf-8")


def _banco(tmp: Path) -> str:
    return str(tmp / "run" / "udev" / "data")


def _sys(tmp: Path) -> str:
    return str(tmp / "sys" / "class" / "hidraw")


#: O banco do hidraw6 dela em 25/09 (o P2 no rádio): uaccess corrente, sem seat.
BANCO_ABERTO = "I:336334317\nG:uaccess\nQ:uaccess\nV:1\n"
#: O que a regra certa deixa: a tag pegajosa fica (G:), a corrente sai (Q:).
BANCO_FECHADO = "I:336334317\nG:uaccess\nG:seat\nQ:seat\nV:1\n"


# ---------------------------------------------------------------------------
# 1. O efeito da regra no banco do udev
# ---------------------------------------------------------------------------


class TestOBancoDoUdevDizComoONoNasceu:
    def test_a_mesa_dela_reprova_e_nomeia_a_71_sony(self, tmp_path: Path) -> None:
        """A regra de antes (70) + a 71-sony do game-devices-udev: FAIL com o endereço."""
        etc, usr = _regras(tmp_path, nossa=VELHA)
        _no(tmp_path, "hidraw6", "237:6", "0005:0000054C:00000CE6", BANCO_ABERTO)
        saida = _chamar(
            "_veredito_do_no_fisico_no_udev", _banco(tmp_path), _sys(tmp_path), "/dev/hidraw6",
            str(etc), str(usr),
        )
        assert "[FAIL]" in saida, saida
        assert "hidraw6 (rádio)" in saida, saida
        assert "71-sony-controllers.rules:22" in saida, saida
        assert "71-sony-controllers.rules:26" in saida, saida
        assert f"a de hoje é a {NOVA}" in saida, saida
        # O 60-steam-input corre ANTES e não é culpado de nada.
        assert "60-steam-input" not in saida, saida

    def test_a_tag_pegajosa_nao_e_acusada(self, tmp_path: Path) -> None:
        """A MORDIDA: leia `G:` no lugar de `Q:` e o nó fechado vira acusação.

        O `TAG-=` só tira a tag CORRENTE; a pegajosa (`G:`) fica no banco para
        sempre. É a corrente que o `73-seat-late` lê para dar a ACL.
        """
        etc, usr = _regras(tmp_path, nossa=NOVA)
        _no(tmp_path, "hidraw6", "237:6", "0005:0000054C:00000CE6", BANCO_FECHADO)
        _no(tmp_path, "hidraw4", "237:4", "0003:0000054C:00000DF2", BANCO_FECHADO)
        saida = _chamar(
            "_veredito_do_no_fisico_no_udev", _banco(tmp_path), _sys(tmp_path),
            "/dev/hidraw4 /dev/hidraw6", str(etc), str(usr),
        )
        assert "[ OK ]" in saida, saida
        assert "2 DualSense" in saida, saida
        assert "[FAIL]" not in saida, saida

    def test_uma_regra_entre_a_nossa_e_a_73_seat_late_e_nomeada(self, tmp_path: Path) -> None:
        """O limite da ordem (o `TAG` não tem `:=`): o doctor é quem o vigia."""
        intruso = 'KERNEL=="hidraw*", KERNELS=="*054C:0CE6*", TAG+="uaccess"\n'
        etc, usr = _regras(tmp_path, nossa=NOVA, extra={"73-i-intruso.rules": intruso})
        _no(tmp_path, "hidraw8", "237:8", "0005:0000054C:00000CE6", BANCO_ABERTO)
        saida = _chamar(
            "_veredito_do_no_fisico_no_udev", _banco(tmp_path), _sys(tmp_path), "/dev/hidraw8",
            str(etc), str(usr),
        )
        assert "[FAIL]" in saida, saida
        assert "73-i-intruso.rules:1" in saida, saida
        assert "71-sony-controllers" not in saida, "a 71-sony corre ANTES da 73-hefesto"

    def test_uma_regra_depois_da_73_seat_late_reabre_na_troca_de_sessao(
        self, tmp_path: Path
    ) -> None:
        tardia = (
            'KERNEL=="hidraw*", ATTRS{idVendor}=="054c", ATTRS{idProduct}=="0ce6", '
            'TAG+="uaccess"\n'
        )
        etc, usr = _regras(tmp_path, nossa=NOVA, extra={"99-tardia.rules": tardia})
        _no(tmp_path, "hidraw4", "237:4", "0003:0000054C:00000CE6", BANCO_ABERTO)
        saida = _chamar(
            "_veredito_do_no_fisico_no_udev", _banco(tmp_path), _sys(tmp_path), "/dev/hidraw4",
            str(etc), str(usr),
        )
        assert "99-tardia.rules:1 — depois da 73-seat-late" in saida, saida
        assert "hidraw4 (cabo)" in saida, saida

    def test_regra_de_outro_aparelho_nao_e_acusada(self, tmp_path: Path) -> None:
        """Uma regra que dá uaccess a OUTRO controle, depois da nossa, não é culpa."""
        outro = 'KERNEL=="hidraw*", ATTRS{idVendor}=="057e", TAG+="uaccess"\n'
        etc, usr = _regras(tmp_path, nossa=NOVA, extra={"99-nintendo.rules": outro})
        assert _chamar("_regras_que_reabrem_o_fisico", NOVA, str(etc), str(usr)) == ""

    def test_udev_antigo_sem_q_le_o_g(self, tmp_path: Path) -> None:
        """Antes do systemd 247 não existe `Q:`, e o `G:` é a tag corrente."""
        etc, usr = _regras(tmp_path, nossa=NOVA)
        _no(tmp_path, "hidraw6", "237:6", "0005:0000054C:00000CE6", "G:uaccess\n")
        saida = _chamar(
            "_veredito_do_no_fisico_no_udev", _banco(tmp_path), _sys(tmp_path), "/dev/hidraw6",
            str(etc), str(usr),
        )
        assert "[FAIL]" in saida, saida

    def test_sem_controle_no_censo_nao_ha_veredito(self, tmp_path: Path) -> None:
        etc, usr = _regras(tmp_path, nossa=NOVA)
        saida = _chamar(
            "_veredito_do_no_fisico_no_udev", _banco(tmp_path), _sys(tmp_path), "",
            str(etc), str(usr),
        )
        assert "[FAIL]" not in saida and "[ OK ]" not in saida, saida

    def test_a_regra_de_hoje_e_preferida_quando_as_duas_existem(self, tmp_path: Path) -> None:
        etc, usr = _regras(tmp_path, nossa=NOVA)
        shutil.copy(etc / NOVA, etc / VELHA)
        assert _chamar("_regra_do_no_instalada", str(etc), str(usr)).strip() == NOVA

    def test_a_variante_aberta_nao_e_acusada(self, tmp_path: Path) -> None:
        """O `--no-fechar-o-no` (e o pacote sem o broker) abre o nó DE PROPÓSITO.

        Conferência de 25/09/2026: a primeira versão deste check dava FAIL
        sobre a escolha de quem instalou — a variante aberta é o caminho de
        volta que o próprio asset ensina, e o fail-safe dos pacotes.

        A MORDIDA: tire o ramo `_regra_do_no_e_a_aberta` do veredito e isto
        volta a FAIL, nomeando a 71-sony como culpada.
        """
        etc, usr = _regras(tmp_path, nossa=NOVA)
        aberta = subprocess.run(
            ["bash", str(RAIZ / "scripts" / "regra_do_no_aberta.sh"), str(etc / NOVA),
             str(tmp_path / "aberta.rules")],
            capture_output=True, text=True, timeout=30, check=True,
        )
        assert aberta.returncode == 0
        shutil.copy(tmp_path / "aberta.rules", etc / NOVA)
        _no(tmp_path, "hidraw6", "237:6", "0005:0000054C:00000CE6", BANCO_ABERTO)
        saida = _chamar(
            "_veredito_do_no_fisico_no_udev", _banco(tmp_path), _sys(tmp_path), "/dev/hidraw6",
            str(etc), str(usr),
        )
        assert "[FAIL]" not in saida, saida
        assert "variante aberta" in saida, saida

    def test_o_link_para_dev_null_desliga_a_regra_de_terceiro(self, tmp_path: Path) -> None:
        """man 7 udev: um link para /dev/null em /etc DESLIGA a de mesmo nome em /usr/lib.

        É o conserto que quem administra a máquina aplica na `71-sony`; o
        doctor não pode continuar acusando a regra desligada. A MORDIDA: volte
        o `[[ -f ]]` para ANTES do `visto` em `_regras_udev_em_ordem` e a
        71-sony reaparece como culpada.
        """
        etc, usr = _regras(tmp_path, nossa=VELHA)
        os.symlink("/dev/null", etc / "71-sony-controllers.rules")
        culpados = _chamar("_regras_que_reabrem_o_fisico", VELHA, str(etc), str(usr))
        assert "71-sony-controllers" not in culpados, culpados
        assert "71-sony-controllers.rules" not in _chamar(
            "_regras_udev_em_ordem", str(etc), str(usr)
        )

    def test_a_varredura_de_manta_respeita_o_link_para_dev_null(self, tmp_path: Path) -> None:
        """A mesma sombra na varredura antiga (`_udev_hidraw_scan`): desligada não acusa."""
        manta = 'KERNEL=="hidraw*", MODE="0666"\n'
        etc, usr = _regras(tmp_path, nossa=NOVA, extra={"99-hidraw.rules": manta})
        assert "99-hidraw.rules:1" in _chamar("_udev_hidraw_rw_global", str(etc), str(usr))
        os.symlink("/dev/null", etc / "99-hidraw.rules")
        assert _chamar("_udev_hidraw_rw_global", str(etc), str(usr)) == ""


# ---------------------------------------------------------------------------
# 2. Quem segura o nó físico agora
# ---------------------------------------------------------------------------


def _processo(proc: Path, pid: int, comm: str, cmdline: str, fds: dict[int, str]) -> None:
    pasta = proc / str(pid)
    (pasta / "fd").mkdir(parents=True)
    (pasta / "comm").write_text(comm + "\n", encoding="utf-8")
    (pasta / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode() + b"\0")
    for fd, alvo in fds.items():
        os.symlink(alvo, pasta / "fd" / str(fd))


class TestQuemSeguraOFisico:
    def _proc(self, tmp: Path) -> Path:
        proc = tmp / "proc"
        _processo(
            proc, 2477877, "hefesto-dualse",
            "/home/x/.venv/bin/python -m hefesto_dualsense4unix daemon start",
            {3: "/dev/hidraw6", 4: "/dev/hidraw8", 9: "/dev/hidraw8"},
        )
        _processo(proc, 44275, "steam", "/home/x/.steam/ubuntu12_32/steam -srt",
                  {132: "/dev/hidraw6", 154: "/dev/hidraw8", 155: "/dev/hidraw9"})
        _processo(proc, 777, "firefox", "firefox", {5: "/dev/null"})
        return proc

    def test_a_steam_e_nomeada_e_o_hefesto_nao(self, tmp_path: Path) -> None:
        """A MORDIDA: tire o filtro do `hefesto` e o próprio daemon vira acusado."""
        saida = _chamar(
            "_veredito_de_quem_segura_o_fisico", str(self._proc(tmp_path)),
            "/dev/hidraw6 /dev/hidraw8", "False",
        )
        assert "[WARN] 2 DualSense" in saida, saida
        assert "hidraw6: steam (PID 44275)" in saida, saida
        assert "hidraw8: steam (PID 44275)" in saida, saida
        assert "2477877" not in saida, saida
        # O hidraw9 é o vpad: a Steam segura o vpad de propósito.
        assert "hidraw9" not in saida, saida

    def test_no_modo_nativo_o_jogo_segura_de_proposito(self, tmp_path: Path) -> None:
        saida = _chamar(
            "_veredito_de_quem_segura_o_fisico", str(self._proc(tmp_path)),
            "/dev/hidraw6 /dev/hidraw8", "True",
        )
        assert "[WARN]" not in saida, saida
        assert "Modo Nativo" in saida, saida

    def test_so_o_hefesto_segura(self, tmp_path: Path) -> None:
        proc = tmp_path / "proc"
        _processo(proc, 10, "hefesto-dualse", "python -m hefesto_dualsense4unix",
                  {3: "/dev/hidraw6"})
        saida = _chamar("_veredito_de_quem_segura_o_fisico", str(proc), "/dev/hidraw6", "")
        assert "[ OK ] só o Hefesto" in saida, saida


# ---------------------------------------------------------------------------
# 3. O nascimento condenado vivo, pelo IPC do daemon
# ---------------------------------------------------------------------------


def _servidor_de_mentira(caminho: Path, resultado: dict[str, object]) -> threading.Thread:
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(caminho))
    srv.listen(1)

    def _laco() -> None:
        conn, _ = srv.accept()
        try:
            conn.settimeout(5.0)
            buf = b""
            while not buf.endswith(b"\n"):
                pedaco = conn.recv(65536)
                if not pedaco:
                    break
                buf += pedaco
            resposta = json.dumps({"jsonrpc": "2.0", "id": 1, "result": resultado})
            conn.sendall(resposta.encode("utf-8") + b"\n")
        finally:
            conn.close()
            srv.close()

    fio = threading.Thread(target=_laco, daemon=True)
    fio.start()
    return fio


def _carimbo(pede: bool, instancia: str) -> dict[str, object]:
    return {
        "confianca": "suspeita" if pede else "limpa",
        "porque": "nasceu com 1 processo(s) segurando o nó do controle",
        "pede_reconexao": pede,
        "instancia": instancia,
        "hw_version": "0x00000811",
        "firme": True,
    }


class TestONascimentoCondenado:
    def test_a_mesa_das_nove_e_meia(self, tmp_path: Path) -> None:
        """A mesa de 25/09: P2, P3 e P4 condenados; P1 limpo."""
        caminho = tmp_path / "d.sock"
        fio = _servidor_de_mentira(
            caminho,
            {
                "native_mode": False,
                "controllers": [
                    {"player_slot": 1, "nascimento": _carimbo(False, "0006")},
                    {"player_slot": 2, "nascimento": _carimbo(True, "000C")},
                    {"player_slot": 3, "nascimento": _carimbo(True, "000E")},
                    {"player_slot": 4, "nascimento": _carimbo(True, "0010")},
                ],
            },
        )
        texto = _chamar("_nascimentos_do_daemon", str(caminho))
        fio.join(5)
        assert "nativo=False" in texto, texto
        saida = _chamar("_veredito_dos_nascimentos", texto)
        assert "[WARN] nascimento condenado vivo em P2 (instância 000C) P3" in saida, saida
        assert "P1" not in saida, saida
        # O carimbo diz a CONDIÇÃO: em 25/09 a barra do P2 obedeceu.
        assert "pode não obedecer" in saida, saida

    def test_sem_condenado_passa(self) -> None:
        """A MORDIDA: ignore o `pede_reconexao` e isto vira aviso."""
        texto = "nativo=False\nnasc|1|False|0006\nnasc|2|False|000C\n"
        saida = _chamar("_veredito_dos_nascimentos", texto)
        assert "[ OK ] nenhum nascimento condenado vivo (2 carimbado(s))" in saida, saida

    def test_daemon_parado_nao_e_veredito(self) -> None:
        saida = _chamar("_veredito_dos_nascimentos", "")
        assert "[WARN]" not in saida and "[ OK ]" not in saida, saida


# ---------------------------------------------------------------------------
# 4. As peças estão no diagnóstico de verdade
# ---------------------------------------------------------------------------


def test_os_dois_checks_rodam_no_main() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    main = texto[texto.index("\nmain() {") :]
    assert "\n    check_o_no_fisico_nasce_sem_acl\n" in main
    assert "\n    check_quem_segura_o_fisico\n" in main


def test_a_varredura_de_hidraw_le_os_cinco_diretorios() -> None:
    """/run e /usr/local/lib valem igual para o udev e ficavam fora."""
    dirs = subprocess.run(
        ["bash", "-c", 'set --; source "$DOCTOR_SH"; printf "%s\\n" "${_DIRS_DE_REGRAS_UDEV[@]}"'],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
        env={"DOCTOR_SH": str(DOCTOR), "PATH": "/usr/bin:/bin"},
    ).stdout.split()
    assert dirs == [
        "/etc/udev/rules.d",
        "/run/udev/rules.d",
        "/usr/local/lib/udev/rules.d",
        "/usr/lib/udev/rules.d",
        "/lib/udev/rules.d",
    ]
    corpo = texto_da_funcao("_udev_hidraw_scan")
    assert '"${_DIRS_DE_REGRAS_UDEV[@]}"' in corpo


def texto_da_funcao(nome: str) -> str:
    texto = DOCTOR.read_text(encoding="utf-8")
    i = texto.index(f"{nome}() {{")
    return texto[i : texto.index("\n}\n", i) + 3]
