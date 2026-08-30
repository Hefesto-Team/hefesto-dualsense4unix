"""IDENTIDADE-01 — o app-id decidido, e a migração de quem já tinha o antigo.

O app-id é a identidade do aplicativo para o sistema operacional, e trocá-lo é
**migração**, não renomeação: ele nomeia o pacote Flatpak, o ícone no tema, o
`.desktop`, e — o que custa caro — a pasta onde os perfis dela moram dentro do
sandbox (`~/.var/app/<app-id>/config/hefesto-dualsense4unix/`).

O id decidido em 21/08/2026 e confirmado em 25/08:

    io.github.hefesto_team.hefesto_dualsense4unix

**POR QUE O LITERAL ESTÁ ESCRITO AQUI, e não importado do produto:** um teste
que lê a constante do próprio código sob teste passa com a cura arrancada — se
alguém trocar o id no produto, a constante acompanha e nada reprova. A mordida
exige que a régua seja independente do que ela mede.
"""
from __future__ import annotations

import re
import subprocess
import types
from pathlib import Path

import hefesto_dualsense4unix.utils.migrate_legacy_paths as mlp
from hefesto_dualsense4unix.utils import xdg_paths

RAIZ = Path(__file__).resolve().parents[2]

APP_ID = "io.github.hefesto_team.hefesto_dualsense4unix"
APP_ID_ANTIGO = "br.andrefarias.Hefesto"

MANIFESTO = RAIZ / "flatpak" / f"{APP_ID}.yml"
METAINFO = RAIZ / "flatpak" / f"{APP_ID}.metainfo.xml"
DESKTOP = RAIZ / "flatpak" / f"{APP_ID}.desktop"

#: Os ÚNICOS lugares que ainda podem nomear o id antigo, e o motivo de cada um.
#: Tudo o mais que o executa ou o empacota tem de falar só do id de hoje — foi
#: a correção pela metade que deixou as duas versões vivas que esta casa paga
#: mais caro. Quem acrescentar uma ocorrência nova é barrado nomeando o arquivo.
PONTOS_DE_TRANSICAO: dict[str, str] = {
    "install.sh": "avisa quem tem o Flatpak antigo instalado — o Flatpak não migra id sozinho",
    "uninstall.sh": "desinstala os DOIS ids e preserva a config dos dois sandboxes",
    "scripts/purge.sh": "descontamina os DOIS ids",
    "src/hefesto_dualsense4unix/utils/migrate_legacy_paths.py": "lê a config do sandbox antigo",
    "src/hefesto_dualsense4unix/app/main.py": "mata a instância anterior sob qualquer dos dois ids",
    # 29/08/2026 (AS DUAS CASAS): os padrões de matança saíram do corpo do
    # `app/main.py` e passaram a derivar de `utils/identidade.py`, porque o app
    # de desenvolvimento precisa dos DELE e não dos do estável. Os dois ids de
    # Flatpak vieram junto, e é aqui que eles moram agora — `app/main.py`
    # continua na lista porque a docstring dele ainda explica o porquê.
    "src/hefesto_dualsense4unix/utils/identidade.py": (
        "os dois app-ids do Flatpak entram nos padrões de matança do ESTÁVEL"
    ),
    "src/hefesto_dualsense4unix/app/app.py": "idem, no pkill de saída",
    f"flatpak/{APP_ID}.yml": "a permissão :ro que deixa a migração LER a casa antiga",
    f"flatpak/{APP_ID}.metainfo.xml": "<replaces> — a loja entende que um SUBSTITUI o outro",
    ".github/workflows/flatpak.yml": "registra de onde o id veio",
    "docs/usage/flatpak.md": "ensina quem tem o antigo a tirá-lo do menu",
}

#: Onde a varredura procura: tudo o que EXECUTA ou EMPACOTA. `docs/process/` e
#: o `CHANGELOG.md` ficam de fora porque são registro do dia em que foram
#: escritos, e `tests/` porque é esta régua e as outras que citam o id.
RAIZES_VARRIDAS = (
    "install.sh",
    "uninstall.sh",
    "NOTICE",
    "scripts",
    "src",
    "flatpak",
    "packaging",
    ".github",
    "LICENSES",
    "docs/usage",
)

_SUFIXOS_BINARIOS = {".png", ".svg", ".mo", ".ico", ".gz", ".xz", ".zst", ".pyc"}


def _arquivos_varridos() -> list[Path]:
    """Só o que o git RASTREIA — bytecode não é produto.

    Esta casa já pagou por uma guarda que confundia `__pycache__/*.pyc` com o
    código: o `.pyc` guarda a string do módulo antigo e acusa um id que já não
    existe em fonte nenhuma. `git ls-files` responde o que está versionado, que
    é o que viaja para a máquina de quem instala.
    """
    saida = subprocess.run(
        ["git", "-C", str(RAIZ), "ls-files", "-z", *RAIZES_VARRIDAS],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [
        RAIZ / rel
        for rel in saida.split("\0")
        if rel and Path(rel).suffix.lower() not in _SUFIXOS_BINARIOS
    ]


# ---------------------------------------------------------------------------
# FASE 2 — o id decidido está no código
# ---------------------------------------------------------------------------
def test_o_id_obedece_a_regra_publicada_do_flathub() -> None:
    """Quatro componentes, cada um `[A-Za-z_][A-Za-z0-9_]*`, domínio minúsculo.

    A regra que derrubou as duas primeiras formas que estavam na mesa
    (`io.github.HefestoTeam.Hefesto` e `io.github.Hefesto_Team.Hefesto`): o
    hífen da organização vira `_`, não some; e o terceiro e o quarto
    componentes são o DONO e o REPOSITÓRIO, não o dono e o nome do aplicativo.
    """
    partes = APP_ID.split(".")
    assert len(partes) >= 4, "o Flathub exige ao menos 4 componentes em io.github.*"
    assert len(partes) <= 5
    for parte in partes:
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", parte), (
            f"componente inválido: {parte!r} — hífen não vale em app-id"
        )
    dominio = ".".join(partes[:3])
    assert dominio == dominio.lower(), "a porção de domínio tem de ser minúscula"
    assert partes[0] == "io" and partes[1] == "github"
    # `io.github.example_foo.bar` mapeia para `github.com/example-foo/bar`.
    dono = partes[2].replace("_", "-")
    repo = partes[3].replace("_", "-")
    assert f"{dono}/{repo}" == "hefesto-team/hefesto-dualsense4unix"


def test_os_tres_arquivos_do_flatpak_tem_o_id_novo_no_nome() -> None:
    for arquivo in (MANIFESTO, METAINFO, DESKTOP):
        assert arquivo.is_file(), f"faltando: {arquivo.relative_to(RAIZ)}"
    for sufixo in (".yml", ".metainfo.xml", ".desktop"):
        antigo = RAIZ / "flatpak" / f"{APP_ID_ANTIGO}{sufixo}"
        assert not antigo.exists(), f"o arquivo do id antigo sobreviveu: {antigo}"


def test_o_manifesto_declara_o_id_novo() -> None:
    texto = MANIFESTO.read_text(encoding="utf-8")
    assert f"\napp-id: {APP_ID}\n" in texto


def test_o_metainfo_declara_o_id_novo() -> None:
    texto = METAINFO.read_text(encoding="utf-8")
    assert f"<id>{APP_ID}</id>" in texto
    assert f'<launchable type="desktop-id">{APP_ID}.desktop</launchable>' in texto


def test_o_metainfo_declara_que_substitui_o_id_antigo() -> None:
    """`<replaces>` é o que impede a loja de mostrar DOIS Hefestos.

    Não confundir com a migração do Flatpak, que não existe: o Flatpak instala
    o id novo ao lado do antigo de qualquer jeito. Isto é a metade que fala com
    a LOJA — GNOME Software e companhia — para ela oferecer a troca em vez de
    um segundo aplicativo homônimo.
    """
    texto = METAINFO.read_text(encoding="utf-8")
    bloco = texto.split("<replaces>", 1)[1].split("</replaces>", 1)[0]
    assert f"<id>{APP_ID_ANTIGO}</id>" in bloco


def test_o_desktop_aponta_o_icone_pelo_id_novo() -> None:
    """O ícone é resolvido por NOME DE ARQUIVO no tema.

    `Icon=` e o destino que o manifesto instala têm de casar, senão o lançador
    fica com o quadrado cinza de "sem ícone" — e o defeito não aparece em teste
    de código nenhum, só na grade de aplicativos dela.
    """
    assert f"Icon={APP_ID}\n" in DESKTOP.read_text(encoding="utf-8")
    manifesto = MANIFESTO.read_text(encoding="utf-8")
    assert f"/app/share/icons/hicolor/256x256/apps/{APP_ID}.png" in manifesto
    assert f"/app/share/applications/{APP_ID}.desktop" in manifesto
    assert f"/app/share/metainfo/{APP_ID}.metainfo.xml" in manifesto


def test_o_id_antigo_so_sobrevive_nos_pontos_de_transicao_declarados() -> None:
    """Correção pela metade deixa as DUAS versões vivas — a régua nos dois sentidos.

    Sentido 1: nenhum arquivo fora da lista nomeia o id antigo.
    Sentido 2: todo arquivo da lista ainda o nomeia — permissão que sobrou de
    um conserto já feito vira licença silenciosa para o id voltar.
    """
    com_id_antigo = {
        str(p.relative_to(RAIZ))
        for p in _arquivos_varridos()
        if APP_ID_ANTIGO in p.read_text(encoding="utf-8", errors="ignore")
        or APP_ID_ANTIGO.replace(".", r"\.") in p.read_text(encoding="utf-8", errors="ignore")
    }
    declarados = set(PONTOS_DE_TRANSICAO)
    assert not (com_id_antigo - declarados), (
        "o id antigo apareceu onde não foi declarado: "
        + ", ".join(sorted(com_id_antigo - declarados))
    )
    assert not (declarados - com_id_antigo), (
        "ponto de transição declarado que já não cita o id antigo (a permissão "
        "virou licença): " + ", ".join(sorted(declarados - com_id_antigo))
    )


# ---------------------------------------------------------------------------
# FASE 3 — a migração de quem já tinha instalado
# ---------------------------------------------------------------------------
def test_o_produto_conhece_os_dois_ids_pelo_nome() -> None:
    assert mlp.APP_ID == APP_ID
    assert mlp.APP_ID_ANTIGO == APP_ID_ANTIGO


def test_o_manifesto_deixa_a_migracao_ler_a_casa_antiga() -> None:
    """Sem esta permissão a migração é código morto dentro do sandbox.

    O Flatpak esconde `~/.var/app/<outro-id>/` de quem não pediu, e o id novo é
    "outro id": os perfis dela existiriam, invisíveis, dois diretórios ao lado.
    """
    texto = MANIFESTO.read_text(encoding="utf-8")
    assert f"--filesystem=~/.var/app/{APP_ID_ANTIGO}:ro" in texto


def test_traduz_o_caminho_do_sandbox_novo_para_o_antigo() -> None:
    novo = Path.home() / ".var/app" / APP_ID / "config/hefesto-dualsense4unix"
    esperado = Path.home() / ".var/app" / APP_ID_ANTIGO / "config/hefesto-dualsense4unix"
    assert mlp._raiz_do_sandbox_antigo(novo) == esperado


def test_fora_do_sandbox_nao_ha_o_que_traduzir() -> None:
    """Instalação nativa não muda de pasta ao trocar o app-id — e não pode mudar.

    O `~/.config/hefesto-dualsense4unix` não depende de app-id nenhum. Se esta
    tradução respondesse aqui, um usuário do `.deb` que um dia experimentou o
    Flatpak veria perfis aparecerem do nada na instalação nativa.
    """
    assert mlp._raiz_do_sandbox_antigo(Path.home() / ".config/hefesto-dualsense4unix") is None
    # Uma pasta chamada como o app-id, mas fora de `.var/app/`, não conta.
    assert mlp._raiz_do_sandbox_antigo(Path("/opt") / APP_ID / "config") is None


def _sandbox(tmp_path: Path, app_id: str) -> Path:
    return tmp_path / ".var" / "app" / app_id


def _wire_sem_legado_curto(monkeypatch, tmp_path: Path, cfg: Path, data: Path) -> None:
    monkeypatch.setattr(
        mlp,
        "_LEGACY",
        types.SimpleNamespace(
            user_config_dir=str(tmp_path / "nao_existe_cfg"),
            user_data_dir=str(tmp_path / "nao_existe_data"),
        ),
    )
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: cfg)
    monkeypatch.setattr(xdg_paths, "data_dir", lambda ensure=False: data)


def test_os_perfis_atravessam_a_troca_de_app_id(tmp_path, monkeypatch) -> None:
    """O que a Fase 3 promete: perfis intactos do outro lado da migração."""
    antigo_cfg = _sandbox(tmp_path, APP_ID_ANTIGO) / "config" / "hefesto-dualsense4unix"
    (antigo_cfg / "profiles").mkdir(parents=True)
    (antigo_cfg / "profiles" / "sackboy_nativo.json").write_text("{}", encoding="utf-8")
    (antigo_cfg / "gui_preferences.json").write_text('{"aba": 3}', encoding="utf-8")
    antigo_data = _sandbox(tmp_path, APP_ID_ANTIGO) / "data" / "hefesto-dualsense4unix"
    antigo_data.mkdir(parents=True)
    (antigo_data / "prontuario.json").write_text("{}", encoding="utf-8")

    novo_cfg = _sandbox(tmp_path, APP_ID) / "config" / "hefesto-dualsense4unix"
    novo_data = _sandbox(tmp_path, APP_ID) / "data" / "hefesto-dualsense4unix"
    novo_cfg.mkdir(parents=True)
    novo_data.mkdir(parents=True)

    _wire_sem_legado_curto(monkeypatch, tmp_path, novo_cfg, novo_data)
    resultado = mlp.migrate_legacy_paths()

    assert (novo_cfg / "profiles" / "sackboy_nativo.json").is_file()
    assert (novo_cfg / "gui_preferences.json").is_file()
    assert (novo_data / "prontuario.json").is_file()
    assert sorted(resultado["config_app_id_antigo"]) == [
        "gui_preferences.json",
        "profiles/sackboy_nativo.json",
    ]
    assert resultado["data_app_id_antigo"] == ["prontuario.json"]


def test_a_migracao_nao_apaga_a_casa_antiga(tmp_path, monkeypatch) -> None:
    """UMA VEZ, sem apagar o antigo — apagar antes da prova não tem volta."""
    antigo_cfg = _sandbox(tmp_path, APP_ID_ANTIGO) / "config" / "hefesto-dualsense4unix"
    antigo_cfg.mkdir(parents=True)
    (antigo_cfg / "fps.json").write_text('{"origem": "antiga"}', encoding="utf-8")
    novo_cfg = _sandbox(tmp_path, APP_ID) / "config" / "hefesto-dualsense4unix"
    novo_data = _sandbox(tmp_path, APP_ID) / "data" / "hefesto-dualsense4unix"
    novo_cfg.mkdir(parents=True)
    novo_data.mkdir(parents=True)

    _wire_sem_legado_curto(monkeypatch, tmp_path, novo_cfg, novo_data)
    mlp.migrate_legacy_paths()

    assert (antigo_cfg / "fps.json").is_file(), "a origem foi apagada"
    assert (antigo_cfg / "fps.json").read_text(encoding="utf-8") == '{"origem": "antiga"}'


def test_a_migracao_nao_sobrescreve_o_que_o_novo_ja_tem(tmp_path, monkeypatch) -> None:
    antigo_cfg = _sandbox(tmp_path, APP_ID_ANTIGO) / "config" / "hefesto-dualsense4unix"
    antigo_cfg.mkdir(parents=True)
    (antigo_cfg / "fps.json").write_text('{"origem": "antiga"}', encoding="utf-8")
    novo_cfg = _sandbox(tmp_path, APP_ID) / "config" / "hefesto-dualsense4unix"
    novo_data = _sandbox(tmp_path, APP_ID) / "data" / "hefesto-dualsense4unix"
    novo_cfg.mkdir(parents=True)
    novo_data.mkdir(parents=True)
    (novo_cfg / "fps.json").write_text('{"origem": "nova"}', encoding="utf-8")

    _wire_sem_legado_curto(monkeypatch, tmp_path, novo_cfg, novo_data)
    resultado = mlp.migrate_legacy_paths()

    assert (novo_cfg / "fps.json").read_text(encoding="utf-8") == '{"origem": "nova"}'
    assert "config_app_id_antigo" not in resultado


def test_e_idempotente(tmp_path, monkeypatch) -> None:
    antigo_cfg = _sandbox(tmp_path, APP_ID_ANTIGO) / "config" / "hefesto-dualsense4unix"
    antigo_cfg.mkdir(parents=True)
    (antigo_cfg / "fps.json").write_text("{}", encoding="utf-8")
    novo_cfg = _sandbox(tmp_path, APP_ID) / "config" / "hefesto-dualsense4unix"
    novo_data = _sandbox(tmp_path, APP_ID) / "data" / "hefesto-dualsense4unix"
    novo_cfg.mkdir(parents=True)
    novo_data.mkdir(parents=True)

    _wire_sem_legado_curto(monkeypatch, tmp_path, novo_cfg, novo_data)
    assert mlp.migrate_legacy_paths()["config_app_id_antigo"] == ["fps.json"]
    assert mlp.migrate_legacy_paths() == {}


# ---------------------------------------------------------------------------
# FASE 3 — o que os instaladores fazem com os dois ids
# ---------------------------------------------------------------------------
def test_o_uninstall_desinstala_os_dois_ids() -> None:
    """Conhecer só o id de hoje deixaria o aplicativo antigo no menu dela."""
    texto = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
    assert "HEFESTO_FLATPAK_APP_IDS=(" in texto
    bloco = texto.split("HEFESTO_FLATPAK_APP_IDS=(", 1)[1].split(")", 1)[0]
    assert APP_ID in bloco
    assert APP_ID_ANTIGO in bloco


def test_o_uninstall_preserva_a_config_dos_dois_sandboxes() -> None:
    """A pasta do sandbox É a config de quem instalou por Flatpak.

    Apagá-la incondicionalmente contradizia a promessa do próprio script
    ("configs preservadas por padrão") e destruiria a origem que a migração de
    app-id precisa ler.
    """
    texto = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
    assert 'rm -rf "${_fp_home}/cache"' in texto, "o cache volátil deve sair sempre"
    assert 'rm -rf "${HOME}/.var/app/' not in texto, (
        "voltou a apagar a casa do sandbox sem olhar para --purge-config"
    )
    assert '[[ "${KEEP_CONFIG}" -eq 0 ]]' in texto.split("HEFESTO_FLATPAK_APP_IDS=(", 1)[1]


def test_o_purge_descontamina_os_dois_ids() -> None:
    texto = (RAIZ / "scripts" / "purge.sh").read_text(encoding="utf-8")
    bloco = texto.split("purge_flatpak()", 1)[1].split("\n}", 1)[0]
    assert APP_ID in bloco
    assert APP_ID_ANTIGO in bloco


def test_o_install_avisa_quem_tem_o_flatpak_antigo() -> None:
    """O Flatpak não migra id: sem aviso, ficam dois Hefestos no menu dela.

    E o aviso tem de DIZER O QUE FAZER — é a régua desta casa para toda frase
    de diagnóstico: o quê, por quê, e o comando.
    """
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    assert f'APP_ID_FLATPAK_ANTIGO="{APP_ID_ANTIGO}"' in texto
    assert 'flatpak info "${APP_ID_FLATPAK_ANTIGO}"' in texto
    assert "flatpak uninstall --user %s" in texto
    assert "versão ANTIGA do Hefesto instalada pelo Flatpak" in texto
    assert "não se perdem" in texto, "o aviso precisa dizer que os perfis sobrevivem"
