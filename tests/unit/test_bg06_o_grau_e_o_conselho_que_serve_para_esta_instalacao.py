"""BG-06 — o grau que sumia no meio de centenas, e o conselho impossível."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import arvore_congelada

RAIZ = arvore_congelada()
DOCTOR = RAIZ / "scripts" / "doctor.sh"

_CONSELHO_GENERICO = "atualize o Hefesto pelo mesmo caminho por onde você o instalou"

AJUDANTES = (
    "esta_instalacao_e_um_checkout",
    "conselho_de_instalacao",
    "so_no_checkout",
)


def _layout_de_pacote(tmp_path: Path) -> Path:
    """O `.deb`/Flatpak: `scripts/doctor.sh` sem `install.sh` ao lado."""
    destino = tmp_path / "pacote"
    copia = destino / "scripts" / "doctor.sh"
    if copia.is_file():
        return copia
    copia.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DOCTOR, copia)
    return copia


def _rodar(
    doctor: Path,
    comando: str,
    *,
    ambiente: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """`source` do doctor (sem rodar o `main`) e executa `comando`."""
    return subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {comando}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={
            **os.environ,
            "DOCTOR_SH": str(doctor),
            **(ambiente or {}),
        },
    )


_CONFIRM = "[General]\nFastConnectable=true\nJustWorksRepairing=confirm\n"


def _cena_do_agente(
    tmp_path: Path, *, agente: str
) -> subprocess.CompletedProcess[str]:
    """`JustWorksRepairing=confirm` no disco e o agente no estado pedido."""
    etc = tmp_path / "bluetooth"
    etc.mkdir(exist_ok=True)
    (etc / "main.conf").write_text(_CONFIRM, encoding="utf-8")

    binario = tmp_path / "bin"
    binario.mkdir(exist_ok=True)
    (binario / "systemctl").write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "is-active" ]]; then\n'
        f'    printf "{agente}\\n"\n'
        f'    [[ "{agente}" == "active" ]] || exit 3\n'
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (binario / "systemctl").chmod(0o755)

    return _rodar(
        DOCTOR,
        "check_bluez_justworks_repairing; "
        "printf 'RESUMO fails=%s warns=%s\\n' \"${FAILS}\" \"${WARNS}\"",
        ambiente={
            "HEFESTO_BT_ETC": str(etc),
            "HEFESTO_BT_ASSETS": str(RAIZ / "assets" / "bluetooth"),
            "PATH": f"{binario}:{os.environ.get('PATH', '')}",
            "HEFESTO_MARCA_SANDBOX": str(tmp_path / "sem-flatpak-info"),
            "HEFESTO_MARCA_CONTAINER": str(tmp_path / "sem-containerenv"),
            "FLATPAK_ID": "",
            "SNAP": "",
        },
    )


class TestOAgenteMortoNaoEUmAviso:
    """A cena que a BG-06 veio reclassificar."""

    def test_agente_morto_com_confirm_reprova(self, tmp_path: Path) -> None:
        """A mordida do defeito (1), na forma mais curta."""
        proc = _cena_do_agente(tmp_path, agente="inactive")

        assert "[FAIL]" in proc.stdout, (
            "com JustWorksRepairing=confirm e o hefesto-bt-agent.service morto "
            "o exame voltou a AVISAR em vez de reprovar. Nenhum controle entra "
            "por rádio nesse estado, e um aviso no meio de centenas some.\n"
            f"Saída: {proc.stdout}"
        )
        assert "RESUMO fails=1" in proc.stdout

    def test_a_frase_diz_o_que_parou_e_o_que_fazer(self, tmp_path: Path) -> None:
        """Regra desta casa: o quê, por quê e o que fazer — nas três partes."""
        proc = _cena_do_agente(tmp_path, agente="inactive")

        assert "pareamento" in proc.stdout, "não diz O QUE parou"
        assert "RECUSA" in proc.stdout, "não diz POR QUE parou (o BlueZ recusa)"
        assert "hefesto-bt-agent.service" in proc.stdout, "não nomeia o culpado"
        assert "systemctl enable --now hefesto-bt-agent.service" in proc.stdout, (
            "não diz O QUE FAZER"
        )

    def test_o_estado_do_agente_entra_na_frase(self, tmp_path: Path) -> None:
        """`inativo` e `ausente` são diagnósticos diferentes, e a frase mostra."""
        proc = _cena_do_agente(tmp_path, agente="failed")

        assert "failed" in proc.stdout, (
            f"a frase perdeu o estado real da unit: {proc.stdout}"
        )

    def test_agente_vivo_nao_reprova(self, tmp_path: Path) -> None:
        """A contraprova, sem a qual um `fail` incondicional passaria."""
        proc = _cena_do_agente(tmp_path, agente="active")

        assert "[ OK ]" in proc.stdout
        assert "RESUMO fails=0 warns=0" in proc.stdout, (
            f"o exame passou a reclamar de uma cena SÃ: {proc.stdout}"
        )


def _faixas_dos_ajudantes(linhas: list[str]) -> set[int]:
    """As linhas DENTRO do corpo dos três ajudantes (índices 0-based)."""
    dentro: set[int] = set()
    for nome in AJUDANTES:
        abertura = f"{nome}() {{"
        inicios = [i for i, ln in enumerate(linhas) if ln.startswith(abertura)]
        assert len(inicios) == 1, (
            f"não achei exatamente um `{abertura}` em {DOCTOR} — o ajudante "
            "que responde pela pergunta 'há checkout?' sumiu ou foi renomeado"
        )
        inicio = inicios[0]
        fim = next(
            (j for j in range(inicio + 1, len(linhas)) if linhas[j] == "}"), None
        )
        assert fim is not None, f"o corpo de {nome}() não fecha"
        dentro.update(range(inicio, fim + 1))
    return dentro


def varrer(fonte: str) -> list[str]:
    """As frases que mandam rodar o instalador SEM perguntar se ele existe."""
    linhas = fonte.splitlines()
    dentro = _faixas_dos_ajudantes(linhas)
    suspeitas: list[str] = []
    for numero, linha in enumerate(linhas):
        texto = linha.strip()
        limpo = texto.replace("install-host-udev.sh", "").replace("uninstall.sh", "")
        if "install.sh" not in limpo or texto.startswith("#") or numero in dentro:
            continue
        if any(ajudante in texto for ajudante in AJUDANTES):
            continue
        suspeitas.append(f"{numero + 1}: {texto}")
    return suspeitas


class TestNenhumaFraseMandaAoLugarQueNaoExiste:
    """O portão da regra "sai de TODOS os lugares onde aparece"."""

    def test_o_doctor_de_hoje_esta_limpo(self) -> None:
        suspeitas = varrer(DOCTOR.read_text(encoding="utf-8"))

        assert not suspeitas, (
            "frase de conselho mandando rodar o instalador sem perguntar se "
            "esta máquina tem um:\n  "
            + "\n  ".join(suspeitas)
            + "\n\nUse `conselho_de_instalacao` (o gesto) ou `so_no_checkout` "
            "(o aparte que só serve a quem tem o repositório). Em cinco dos "
            "seis formatos deste produto esse arquivo não está na máquina."
        )

    def test_a_varredura_sabe_recusar(self) -> None:
        """Régua que só sabe passar não é régua."""
        original = DOCTOR.read_text(encoding="utf-8")
        antes = set(varrer(original))

        linhas = original.splitlines()
        veneno = '        warn "wrapper ausente — rode ./install.sh (sem flag)"'
        linhas.append(veneno)
        novas = [s for s in varrer("\n".join(linhas)) if s not in antes]

        assert len(novas) == 1, f"a varredura não pegou a frase plantada: {novas}"
        assert novas[0].startswith(f"{len(linhas)}: "), novas[0]
        assert "rode ./install.sh" in novas[0]

    def test_a_varredura_nao_confunde_o_reparador_com_o_instalador(self) -> None:
        """`install-host-udev.sh` CONTÉM `install.sh` — e não é ele."""
        original = DOCTOR.read_text(encoding="utf-8")
        antes = set(varrer(original))
        limpo = '        warn "traga o alvo: sudo /usr/share/x/install-host-udev.sh"'

        depois = set(varrer(original + "\n" + limpo))

        assert depois == antes, f"a varredura confundiu o reparador: {depois - antes}"

    def test_os_ajudantes_sao_usados_de_verdade(self) -> None:
        """ENTREGA-QUE-NAO-LIGOU-01: ajudante vivo e nunca chamado."""
        fonte = DOCTOR.read_text(encoding="utf-8")
        dentro = _faixas_dos_ajudantes(fonte.splitlines())
        chamadas = [
            ln
            for numero, ln in enumerate(fonte.splitlines())
            if numero not in dentro
            and not ln.strip().startswith("#")
            and ("$(conselho_de_instalacao" in ln or "$(so_no_checkout" in ln)
        ]

        assert len(chamadas) >= 30, (
            f"só {len(chamadas)} frases perguntam se há checkout; eram 33 "
            "quando a BG-06 fechou. Se alguma sumiu de propósito, ajuste este "
            "número no mesmo commit e diga por quê."
        )


def _frase(doctor: Path, comando: str) -> str:
    proc = _rodar(doctor, comando)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


class TestOGestoQueServeParaCadaLayout:
    def test_no_checkout_o_gesto_e_o_de_sempre(self) -> None:
        """A cura não podia piorar o caso que já funcionava."""
        assert _frase(DOCTOR, "conselho_de_instalacao") == "rode ./install.sh"
        assert (
            _frase(DOCTOR, "conselho_de_instalacao --native")
            == "rode ./install.sh --native"
        )

    def test_fora_do_checkout_o_gesto_nao_cita_o_instalador(
        self, tmp_path: Path
    ) -> None:
        """A mordida do defeito (2), na forma mais curta."""
        pacote = _layout_de_pacote(tmp_path)

        for comando in ("conselho_de_instalacao", "conselho_de_instalacao --native"):
            frase = _frase(pacote, comando)
            assert "install.sh" not in frase, frase
            assert frase == "atualize o Hefesto pelo mesmo caminho por onde você o instalou"

    def test_o_reparador_do_pacote_so_entra_se_estiver_no_disco(
        self, tmp_path: Path
    ) -> None:
        """MEDIDO, não presumido — e é a mesma pergunta um andar abaixo."""
        pacote = _layout_de_pacote(tmp_path)
        reparador = tmp_path / "reparador.sh"

        sem = _frase(pacote, f'conselho_de_instalacao "" "{reparador}"')
        assert str(reparador) not in sem, sem
        assert sem == "atualize o Hefesto pelo mesmo caminho por onde você o instalou"

        reparador.write_text("#!/bin/bash\n", encoding="utf-8")
        com = _frase(pacote, f'conselho_de_instalacao "" "{reparador}"')
        assert com == f"rode o reparador que veio no seu pacote: sudo {reparador}"

    def test_a_ressalva_do_reparador_nao_aparece_sem_ele(
        self, tmp_path: Path
    ) -> None:
        """O reparador dos pacotes NÃO faz tudo o que o instalador faz."""
        pacote = _layout_de_pacote(tmp_path)
        reparador = tmp_path / "reparador.sh"
        ressalva = "— não traz os timers"

        sem = _frase(pacote, f'conselho_de_instalacao "" "{reparador}" "{ressalva}"')
        assert ressalva not in sem, sem

        reparador.write_text("#!/bin/bash\n", encoding="utf-8")
        com = _frase(pacote, f'conselho_de_instalacao "" "{reparador}" "{ressalva}"')
        assert com.endswith(f"sudo {reparador} {ressalva}"), com

        no_clone = _frase(DOCTOR, f'conselho_de_instalacao "" "{reparador}" "{ressalva}"')
        assert no_clone == "rode ./install.sh", (
            f"a ressalva do reparador vazou para quem tem o repositório: {no_clone}"
        )

    def test_no_checkout_o_reparador_nem_e_consultado(self, tmp_path: Path) -> None:
        """Quem tem o repositório recebe o gesto do repositório, ponto."""
        reparador = tmp_path / "reparador.sh"
        reparador.write_text("#!/bin/bash\n", encoding="utf-8")

        assert (
            _frase(DOCTOR, f'conselho_de_instalacao "" "{reparador}"')
            == "rode ./install.sh"
        )

    def test_o_aparte_de_checkout_some_fora_dele(self, tmp_path: Path) -> None:
        """`so_no_checkout` é o que mantém a tela dela intacta."""
        pacote = _layout_de_pacote(tmp_path)

        assert _frase(DOCTOR, 'so_no_checkout "(sem flag)"') == " (sem flag)"
        assert _frase(pacote, 'so_no_checkout "(sem flag)"') == ""

    def test_a_pergunta_olha_para_um_arquivo_de_verdade(
        self, tmp_path: Path
    ) -> None:
        """Não é presunção: é a existência do arquivo no disco."""
        pacote = _layout_de_pacote(tmp_path)
        raiz = pacote.parent.parent

        antes = _rodar(pacote, "esta_instalacao_e_um_checkout")
        assert antes.returncode != 0

        (raiz / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
        depois = _rodar(pacote, "esta_instalacao_e_um_checkout")
        assert depois.returncode == 0


class TestAsDuasCopiasNaoPodemDivergir:
    """DUPLICAÇÃO DECLARADA — e um portão em cima dela."""

    def test_a_frase_de_fora_do_checkout_e_a_mesma_nos_dois_lugares(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        monkeypatch.setattr(da, "esta_instalacao_e_um_checkout", lambda: False)
        do_produto = da.como_atualizar_esta_instalacao()

        do_doctor = _frase(_layout_de_pacote(tmp_path), "conselho_de_instalacao")

        assert do_doctor == do_produto, (
            "a aba Sistema e o exame passaram a dizer coisas diferentes para a "
            f"MESMA pessoa:\n  GUI....: {do_produto!r}\n  doctor.: {do_doctor!r}"
        )

    def test_a_pergunta_e_a_mesma_nos_dois_lugares(self) -> None:
        """Os dois olham para um `install.sh` ao lado do próprio código."""
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        assert da.BASES_DE_INSTALACAO[0].name != "src"
        fonte = DOCTOR.read_text(encoding="utf-8")
        assert '[[ -f "${ROOT_DIR}/install.sh" ]]' in fonte, (
            "o doctor deixou de perguntar pelo arquivo e voltou a presumir o "
            "formato"
        )


FORMATOS_NOMEADOS = ("flatpak", "arch", "debian", "fedora", "nix")


def _dubles_de_gerenciador(tmp_path: Path, dono: str | None) -> str:
    """Um diretório de `PATH` com `pacman`/`dpkg`/`rpm` — só um responde `0`."""
    binarios = {"arch": "pacman", "debian": "dpkg", "fedora": "rpm"}
    pasta = tmp_path / f"bin-{dono or 'ninguem'}"
    pasta.mkdir(exist_ok=True)
    for formato, nome in binarios.items():
        alvo = pasta / nome
        alvo.write_text(
            f"#!/usr/bin/env bash\nexit {0 if formato == dono else 1}\n",
            encoding="utf-8",
        )
        alvo.chmod(0o755)
    return str(pasta)


def _cena_do_formato(
    tmp_path: Path, formato: str
) -> tuple[Path, str, dict[str, str]]:
    """`(doctor, caminho a interrogar, ambiente)` para um formato."""
    sem_marca = str(tmp_path / "sem-flatpak-info")
    base = {
        "HEFESTO_MARCA_SANDBOX": sem_marca,
        "HEFESTO_MARCA_CONTAINER": str(tmp_path / "sem-containerenv"),
        "FLATPAK_ID": "",
        "SNAP": "",
        "PATH": f"{_dubles_de_gerenciador(tmp_path, None)}:{os.environ.get('PATH', '')}",
    }
    if formato == "checkout":
        return DOCTOR, "", base
    pacote = _layout_de_pacote(tmp_path)
    if formato == "flatpak":
        marca = tmp_path / "flatpak-info-de-mentira"
        marca.write_text("[Application]\n", encoding="utf-8")
        return pacote, "", {**base, "HEFESTO_MARCA_SANDBOX": str(marca)}
    if formato == "nix":
        return pacote, "/nix/store/abc123-hefesto/share/scripts/doctor.sh", base
    if formato in {"arch", "debian", "fedora"}:
        caminho = _dubles_de_gerenciador(tmp_path, formato)
        return pacote, "", {**base, "PATH": f"{caminho}:{os.environ.get('PATH', '')}"}
    return pacote, "", base


def _gesto_do_doctor(tmp_path: Path, formato: str) -> str:
    doctor, alvo, ambiente = _cena_do_formato(tmp_path, formato)
    proc = _rodar(doctor, f'_gesto_de_atualizar "{alvo}"', ambiente=ambiente)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _formato_visto_pelo_doctor(tmp_path: Path, formato: str) -> str:
    doctor, alvo, ambiente = _cena_do_formato(tmp_path, formato)
    proc = _rodar(doctor, f'_formato_desta_instalacao "{alvo}"', ambiente=ambiente)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _gesto_do_produto(tmp_path: Path, formato: str) -> str:
    """A cópia em Python, no mesmo disco de mentira."""
    from hefesto_dualsense4unix.integrations import storm_doctor as sd

    sem_marca = tmp_path / "sem-flatpak-info"
    marca = sem_marca
    raiz = tmp_path / "pacote" / "scripts" / "doctor.sh"
    dono: str | None = None
    if formato == "flatpak":
        marca = tmp_path / "flatpak-info-de-mentira"
        marca.write_text("[Application]\n", encoding="utf-8")
    elif formato == "nix":
        raiz = Path("/nix/store/abc123-hefesto/share/scripts/doctor.sh")
    elif formato in {"arch", "debian", "fedora"}:
        dono = formato
    return sd.gesto_de_atualizar(
        e_checkout=(formato == "checkout"),
        marca_flatpak=marca,
        raiz_do_codigo=raiz,
        consultar_dono=lambda _alvo: dono,
    )


class TestOGestoTemNomeEAsDuasCopiasNaoDivergem:
    """BG-06b — a frase honesta que não dizia o gesto."""

    @pytest.mark.parametrize("formato", FORMATOS_NOMEADOS)
    def test_o_gesto_e_nomeado_por_formato(
        self, tmp_path: Path, formato: str
    ) -> None:
        visto = _formato_visto_pelo_doctor(tmp_path, formato)
        assert visto == formato, (
            f"o exame não reconheceu o formato {formato!r} (viu {visto!r}) — "
            "a detecção olha o disco: o `install.sh` ao lado, o "
            "`/.flatpak-info`, o `/nix/store`, o gerenciador que assume o "
            "arquivo."
        )

        do_doctor = _gesto_do_doctor(tmp_path, formato)
        do_produto = _gesto_do_produto(tmp_path, formato)

        assert do_doctor != _CONSELHO_GENERICO, (
            f"o formato {formato!r} voltou a receber a frase que não diz o "
            f"gesto: {do_doctor!r}"
        )
        assert do_doctor == do_produto, (
            "a aba Sistema e o exame passaram a dizer coisas diferentes para a "
            f"MESMA pessoa ({formato}):\n  GUI....: {do_produto!r}\n"
            f"  doctor.: {do_doctor!r}"
        )
        assert do_doctor.startswith("rode "), (
            f"o gesto de {formato!r} deixou de ser um GESTO: {do_doctor!r}. Ele "
            "entra no MESMO lugar da frase onde entrava 'rode ./install.sh', e "
            "uma oração inteira ali quebra a gramática de quem a hospeda."
        )

    def test_o_formato_sem_dono_continua_recebendo_a_generica(
        self, tmp_path: Path
    ) -> None:
        """A régua sabe RECUSAR — e este é o degrau que prova a honestidade."""
        assert _formato_visto_pelo_doctor(tmp_path, "desconhecido") == "desconhecido"
        assert _gesto_do_doctor(tmp_path, "desconhecido") == _CONSELHO_GENERICO
        assert _gesto_do_produto(tmp_path, "desconhecido") == _CONSELHO_GENERICO

    def test_no_checkout_nada_mudou(self, tmp_path: Path) -> None:
        """A cura não podia piorar o caso que já funcionava — o dela."""
        assert _formato_visto_pelo_doctor(tmp_path, "checkout") == "checkout"
        assert _frase(DOCTOR, "conselho_de_instalacao") == "rode ./install.sh"
        assert (
            _frase(DOCTOR, "conselho_de_instalacao --native")
            == "rode ./install.sh --native"
        )


_HOSPEDEIRA = re.compile(r'^\s*(?:warn|fail|info|pass)\s+"(.*)"\s*$')

_VARIAVEL_CITADA = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)")

_VALOR_DO_VIZINHO = "…"


def _hospedeiras() -> list[tuple[int, str]]:
    achadas: list[tuple[int, str]] = []
    for numero, linha in enumerate(DOCTOR.read_text(encoding="utf-8").splitlines(), 1):
        casa = _HOSPEDEIRA.match(linha)
        if casa is None:
            continue
        texto = casa.group(1)
        if "so_no_checkout" in texto or "conselho_de_instalacao" in texto:
            achadas.append((numero, texto))
    return achadas


def _renderizar(doctor: Path, ambiente: dict[str, str]) -> list[str]:
    """As frases hospedeiras PINTADAS, não lidas."""
    frases = _hospedeiras()
    citadas = {
        nome
        for _n, texto in frases
        for nome in _VARIAVEL_CITADA.findall(texto)
        if not nome.startswith("_")
    }
    prelude = "".join(f'{nome}="{_VALOR_DO_VIZINHO}"\n' for nome in sorted(citadas))
    corpo = "\n".join(f'printf "%s\\n" "{t}"' for _n, t in frases)
    proc = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"\n{prelude}{corpo}'],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={**os.environ, "DOCTOR_SH": str(doctor), **ambiente},
    )
    linhas = proc.stdout.splitlines()
    assert len(linhas) == len(frases), (
        f"nem toda frase renderizou ({len(linhas)} de {len(frases)}): "
        f"{proc.stderr[-800:]}"
    )
    return linhas


def _defeitos_de_junta(frase: str) -> list[str]:
    """Os pedaços de `frase` que denunciam uma colagem torta."""
    achados = [m.group(0) for m in re.finditer(r"\S? ? [;,.)](?: |$)", frase)]
    achados += [m.group(0) for m in re.finditer(r"\S   ?\S", frase)]
    if frase.rstrip().endswith(("—", ":", ";")):
        achados.append(frase.rstrip()[-12:])
    return achados


class TestOAparteNaoQuebraAGramatica:
    """A armadilha que já custou sete frases, conferida onde ela aparece."""

    @pytest.mark.parametrize("formato", ["checkout", "debian", "desconhecido"])
    def test_as_frases_renderizadas_nao_tem_junta_torta(
        self, tmp_path: Path, formato: str
    ) -> None:
        doctor, _alvo, ambiente = _cena_do_formato(tmp_path, formato)
        tortas: list[str] = []
        for (numero, fonte), pintada in zip(
            _hospedeiras(), _renderizar(doctor, ambiente), strict=True
        ):
            for defeito in _defeitos_de_junta(pintada):
                if defeito in fonte:
                    continue
                tortas.append(f"doctor.sh:{numero}: {defeito!r} em {pintada!r}")

        assert not tortas, (
            f"frase com a junta torta no formato {formato!r} — o gesto e o "
            "aparte não colaram:\n  " + "\n  ".join(tortas)
        )

    def test_o_aparte_continua_sumindo_fora_do_checkout(
        self, tmp_path: Path
    ) -> None:
        """O gesto novo não podia ressuscitar o aparte do repositório."""
        doctor, _alvo, ambiente = _cena_do_formato(tmp_path, "debian")
        pintadas = _renderizar(doctor, ambiente)

        assert any("rode sudo apt upgrade" in p for p in pintadas), (
            "nenhuma frase recebeu o gesto nomeado — a cena não morde"
        )
        assert not [p for p in pintadas if "./install.sh" in p], (
            "o aparte do checkout voltou a aparecer para quem instalou por "
            f"pacote: {[p for p in pintadas if './install.sh' in p]}"
        )
