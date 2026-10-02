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

#: sai com: O-NIX-LEVA-AS-REGRAS-DO-HOST-01
LACUNA_HOJE = {
    "nix": (
        "22/08/2026 — o package.nix leva as regras 82/83, mas NÃO leva o "
        "install-host-udev.sh e não tem gancho de pós-instalação: um derivation "
        "só escreve em $out, e os alvos precisam de /usr/local/lib e "
        "/etc/systemd/system no HOST. O `TEST==` das duas regras é o que "
        "transforma isso em inércia silenciosa em vez de erro a cada conexão. "
        "Pagar a dívida exige um módulo NixOS, que é entrega à parte."
    ),
}


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
            if nome in LACUNA_HOJE:
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
