"""O pacote leva os ALVOS das regras 82 e 83, não só as regras."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
HELPER = RAIZ / "scripts" / "install-host-udev.sh"

ALVOS = (
    ("scripts/bt_nosniff_now.sh", "scripts"),
    ("scripts/bt_bonds_snapshot.sh", "scripts"),
    ("assets/systemd/hefesto-bt-bonds-snapshot.service", "systemd"),
)

FORMATOS = {
    "deb": Path("scripts/build_deb.sh"),
    "arch": Path("packaging/arch/PKGBUILD"),
    "fedora": Path("packaging/fedora/hefesto-dualsense4unix.spec"),
    "flatpak": Path("flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml"),
    "nix": Path("packaging/nix/package.nix"),
}

GANCHOS_DE_REMOCAO = {
    "deb": Path("packaging/debian/prerm"),
    "arch": Path("packaging/arch/hefesto-dualsense4unix.install"),
    "fedora": Path("packaging/fedora/hefesto-dualsense4unix.spec"),
}

#: Nenhuma lacuna. A do `nix` (22/08/2026) saiu em 06/10/2026, com a
#: O-NIX-LEVA-AS-REGRAS-DO-HOST-01: o `package.nix` leva os alvos no `$out` e
#: reescreve o caminho das regras, e o módulo NixOS (`packaging/nix/module.nix`)
#: os liga na máquina. Lacuna nova entra aqui com data e motivo.
LACUNA_HOJE: dict[str, str] = {}

NIX = Path("packaging/nix/package.nix")
MODULO_NIX = Path("packaging/nix/module.nix")
FLAKE = Path("flake.nix")
REGRAS_COM_ALVO = (
    Path("assets/82-nintendo-pro-nosniff.rules"),
    Path("assets/83-hefesto-bond-snapshot.rules"),
)
UNIDADE = Path("assets/systemd/hefesto-bt-bonds-snapshot.service")


def _texto(relativo: Path) -> str:
    return (RAIZ / relativo).read_text(encoding="utf-8")


def _candidatos_do_helper(marcador: str) -> list[str]:
    """Os diretórios que o helper VARRE para achar os alvos, lidos dele."""
    texto = HELPER.read_text(encoding="utf-8")
    inicio = texto.index(f'{marcador}=""')
    fim = texto.index("done", inicio)
    return re.findall(r'"(/(?:app|usr)/share/[^"]+)"', texto[inicio:fim])


def _destino_da_remocao(basename: str) -> str:
    """O caminho ABSOLUTO em que o helper grava o alvo, lido do helper."""
    texto = HELPER.read_text(encoding="utf-8")
    padrao = rf"(/(?:usr/local/lib|etc/systemd/system)\S*/{re.escape(basename)})"
    achados = re.findall(padrao, texto)
    assert achados, f"o helper não grava {basename} em lugar nenhum — régua quebrada"
    return achados[0]


def _recorte_de_instalacao(nome: str, texto: str) -> str:
    """Só a parte da receita que CONSTRÓI o pacote."""
    if nome != "fedora":
        return texto
    inicio = texto.index("\n%install")
    return texto[inicio : texto.index("\n%post", inicio)]


def _secao_files(texto: str) -> str:
    inicio = texto.index("\n%files")
    return texto[inicio : texto.index("\n%changelog", inicio)]


def _macros_expandidas(texto: str) -> str:
    """O spec do Fedora escreve o destino em macro; aqui ele vira caminho."""
    app_id = re.search(r"^%global\s+app_id\s+(\S+)", texto, re.M)
    if app_id:
        texto = texto.replace("%{app_id}", app_id.group(1))
    return texto.replace("%{_datadir}", "/usr/share").replace("%{buildroot}", "")


@pytest.fixture(scope="module")
def receitas() -> dict[str, str]:
    return {
        nome: _recorte_de_instalacao(nome, _macros_expandidas(_texto(caminho)))
        for nome, caminho in FORMATOS.items()
    }


class TestOAlvoViajaComARegra:
    def test_todo_formato_conferido_realmente_leva_as_regras(
        self, receitas: dict[str, str]
    ) -> None:
        """A lista de formatos não é opinião: cada um destes cita as duas regras."""
        for nome, texto in receitas.items():
            for numero in ("82", "83"):
                assert re.search(rf"\b{numero}-[A-Za-z0-9_.*-]*\.rules", texto), (
                    f"{nome} deixou de levar a regra {numero}"
                )

    def test_todo_formato_leva_os_tres_alvos(self, receitas: dict[str, str]) -> None:
        faltando: list[str] = []
        for nome, texto in receitas.items():
            if nome in LACUNA_HOJE:
                continue
            for origem, _familia in ALVOS:
                if Path(origem).name not in texto:
                    faltando.append(f"{nome}: {origem}")
        assert not faltando, (
            "formato que leva as regras 82/83 e NÃO leva o alvo do RUN+= delas — "
            "a regra vai para o disco e fica inerte: " + "; ".join(faltando)
        )

    def test_o_rpm_declara_os_tres_no_files(self) -> None:
        """No RPM, instalar sem declarar no ``%files`` NÃO empacota — aborta o build."""
        secao = _macros_expandidas(_secao_files(_texto(FORMATOS["fedora"])))
        for origem, _familia in ALVOS:
            assert Path(origem).name in secao, (
                f"{origem} sai do %install e não aparece no %files — o rpmbuild "
                "aborta com 'Installed (but unpackaged) file(s) found'"
            )

    def test_o_alvo_aterrissa_onde_o_helper_procura(self, receitas: dict[str, str]) -> None:
        """Levar o arquivo não basta: tem de cair num diretório que o helper varre."""
        candidatos = {
            "scripts": _candidatos_do_helper("BTRES_SCRIPTS_SRC"),
            "systemd": _candidatos_do_helper("BTRES_UNIT_SRC"),
        }
        assert all(candidatos.values()), "o helper deixou de declarar candidatos"
        faltando: list[str] = []
        for nome, texto in receitas.items():
            if nome in LACUNA_HOJE or nome == "nix":
                # O Nix não grava no host: não usa o helper, e o caminho dele é o
                # da classe `TestONixLevaOsAlvosPeloStore`.
                continue
            for familia in ("scripts", "systemd"):
                if not any(destino in texto for destino in candidatos[familia]):
                    faltando.append(f"{nome}: nenhum de {candidatos[familia]}")
        assert not faltando, (
            "formato que copia o alvo para um caminho que o install-host-udev.sh "
            "NÃO varre — entrega zero: " + "; ".join(faltando)
        )


class TestOAlvoSaiQuandoOPacoteSai:
    def test_a_remocao_desfaz_o_que_o_helper_gravou(self) -> None:
        """Alvo que sobrevive ao remove deixa a cura armada sem o pacote."""
        destinos = [_destino_da_remocao(Path(origem).name) for origem, _f in ALVOS]
        faltando: list[str] = []
        for nome, caminho in GANCHOS_DE_REMOCAO.items():
            texto = _macros_expandidas(_texto(caminho))
            for destino in destinos:
                if destino not in texto:
                    faltando.append(f"{nome}: {destino}")
        assert not faltando, (
            "gancho de remoção que não apaga o alvo instalado fora do manifesto — "
            "e o helper também copia as regras para /etc/udev/rules.d, que o "
            "gerenciador não apaga: " + "; ".join(faltando)
        )

    def test_o_snapshot_de_bonds_nao_e_apagado(self) -> None:
        """O /var/lib é o salva-vidas dela; desinstalar não é motivo para queimá-lo."""
        for nome, caminho in GANCHOS_DE_REMOCAO.items():
            texto = _texto(caminho)
            assert "/var/lib/hefesto-dualsense4unix/bt-bonds" not in texto, (
                f"{nome} apaga os snapshots de bonds na remoção"
            )


def _caminhos_de_host(arquivo: Path) -> set[str]:
    """Os caminhos de HOST que a regra (ou a unidade) chama, lidos dela mesma."""
    texto = "\n".join(
        linha for linha in _texto(arquivo).splitlines() if not linha.lstrip().startswith("#")
    )
    achados = set(re.findall(r"/usr/local/lib/hefesto-dualsense4unix(?=/)", texto))
    achados |= set(re.findall(r"/usr/bin/systemctl", texto))
    return achados


class TestONixLevaOsAlvosPeloStore:
    """O Nix não escreve no host: leva os alvos no `$out` e aponta a regra para eles."""

    def test_o_pacote_reescreve_todo_caminho_de_host_que_a_regra_chama(self) -> None:
        """Lido das regras e da unidade, e não digitado aqui: caminho novo na regra
        sem a troca correspondente deixa a regra apontando para o nada."""
        pacote = _texto(NIX)
        sem_troca: list[str] = []
        for arquivo in (*REGRAS_COM_ALVO, UNIDADE):
            achados = _caminhos_de_host(arquivo)
            assert achados, f"{arquivo} não chama caminho de host — régua quebrada"
            fim_do_bloco = r"(?=\n\s*\n|\n\s*(?:#|substituteInPlace|wrapProgram|install))"
            bloco = re.search(
                rf"substituteInPlace \$out/\S+/{re.escape(arquivo.name)}(.*?){fim_do_bloco}",
                pacote,
                re.S,
            )
            if bloco is None:
                sem_troca.append(f"{arquivo.name}: nenhum substituteInPlace")
                continue
            for caminho in sorted(achados):
                if f"--replace-fail {caminho}" not in re.sub(r"\s+", " ", bloco.group(1)):
                    sem_troca.append(f"{arquivo.name}: {caminho}")
        assert not sem_troca, (
            "o package.nix deixa a regra apontando para o host, onde o Nix não tem o "
            "alvo: " + "; ".join(sem_troca)
        )

    def test_a_troca_falha_alto_e_nao_calada(self) -> None:
        """`--replace` sem `-fail` entrega a regra intacta quando o caminho muda."""
        pacote = _texto(NIX)
        assert "--replace-fail" in pacote
        assert not re.search(r"substituteInPlace[^\n]*\n?[^\n]*--replace\s", pacote), (
            "uma troca do package.nix usa `--replace` (silencioso) em vez de `--replace-fail`"
        )

    def test_os_alvos_ficam_no_out_e_com_o_path_do_que_chamam(self) -> None:
        pacote = _texto(NIX)
        for origem, _familia in ALVOS:
            nome = Path(origem).name
            instala = rf"install -D\S* {re.escape(origem)}\s*\\\s*\$out/\S*{re.escape(nome)}"
            assert re.search(instala, pacote), f"o package.nix não instala {origem} no $out"
        for nome in ("bt_nosniff_now.sh", "bt_bonds_snapshot.sh"):
            assert re.search(rf"wrapProgram \$out/libexec/\S+/{re.escape(nome)}", pacote), (
                f"{nome} roda pelo PATH do udev/systemd, que não tem `find`, `flock` nem "
                "`logger`: sem o wrapper o alvo morre calado"
            )

    def test_o_modulo_liga_o_que_o_nixos_precisa(self) -> None:
        modulo = "\n".join(
            linha for linha in _texto(MODULO_NIX).splitlines()
            if not linha.lstrip().startswith("#")
        )
        for pedaco in (
            "services.udev.packages",
            "systemd.packages",
            "systemd.timers.hefesto-bt-bonds-snapshot",
            "/var/lib/hefesto-dualsense4unix",
            '"uinput"',
            '"uhid"',
            "lib.mkIf cfg.enable",
        ):
            assert pedaco in modulo, f"o módulo NixOS perdeu `{pedaco}`"
        assert "ReadWritePaths=/var/lib/hefesto-dualsense4unix" in _texto(UNIDADE), (
            "a unidade deixou de declarar o diretório de estado: o tmpfiles do módulo "
            "ficou sem razão (ou a razão mudou de lugar)"
        )

    def test_o_flake_exporta_o_modulo(self) -> None:
        assert "nixosModules.default = import ./packaging/nix/module.nix" in _texto(FLAKE)

    def test_o_hash_do_pydualsense_e_real(self) -> None:
        """O placeholder impedia qualquer build, e com ele o job do CI não prova nada."""
        pacote = "\n".join(
            linha for linha in _texto(NIX).splitlines() if not linha.lstrip().startswith("#")
        )
        assert "fakeSha256" not in pacote
        assert re.search(r'hash = "sha256-[A-Za-z0-9+/]{43}="', pacote)


class TestALacunaNaoEnvelheceCalada:
    def test_lacuna_declarada_que_ja_nao_vale_reprova(
        self, receitas: dict[str, str]
    ) -> None:
        pagas: list[str] = []
        for nome in LACUNA_HOJE:
            assert nome in FORMATOS, f"lacuna declarada para formato que não existe: {nome}"
            texto = receitas[nome]
            if all(Path(origem).name in texto for origem, _f in ALVOS):
                pagas.append(nome)
        assert not pagas, (
            "lacuna declarada que já ganhou dono — APAGUE a entrada de "
            "LACUNA_HOJE: " + "; ".join(pagas)
        )

    def test_toda_lacuna_tem_data_e_motivo(self) -> None:
        for nome, razao in LACUNA_HOJE.items():
            assert re.match(r"\d{2}/\d{2}/\d{4} — ", razao), (
                f"a lacuna de {nome} não começa com data e motivo"
            )
