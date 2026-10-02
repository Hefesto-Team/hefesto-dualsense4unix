"""Testes do portão que reprova documento citando arquivo inexistente."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-referencias-docs.py"

ADR_GLIFOS = "docs/adr/011-glyphs-vs-emojis.md"
LINHA_DA_PROVA = 18
NOME_FANTASMA = "guardian.py"

ARQUIVO_ANINHADO = "gui/janela-de-mentira.glade"


def rodar(*args: str) -> subprocess.CompletedProcess[str]:
    """Executa o validador e devolve o processo terminado."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=RAIZ_REAL,
        check=False,
    )


ENV_REAL = "HEFESTO_DUALSENSE4UNIX_PLUGINS_ENABLED"
ENV_FANTASMA = "HEFESTO_PLUGINS_ENABLED"
METODO_REAL = "profile.switch"
METODO_FANTASMA = "profile.trocar"


@pytest.fixture
def repo_falso(tmp_path: Path) -> Path:
    """Repositório mínimo: um arquivo real e uma pasta docs/ vazia."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "existe_de_verdade.sh").write_text(
        "#!/usr/bin/env bash\n", encoding="utf-8"
    )
    pacote = tmp_path / "src" / "pacote" / "gui"
    pacote.mkdir(parents=True)
    (pacote / ARQUIVO_ANINHADO.split("/")[-1]).write_text(
        "<interface/>\n", encoding="utf-8"
    )

    daemon = tmp_path / "src" / "hefesto_dualsense4unix" / "daemon"
    daemon.mkdir(parents=True)
    (daemon / "ipc_server.py").write_text(
        "class IPCServer:\n"
        "    def __post_init__(self) -> None:\n"
        "        self._handlers = {\n"
        f'            "{METODO_REAL}": self._handle_profile_switch,\n'
        '            "daemon.reload": self._handle_daemon_reload,\n'
        "        }\n",
        encoding="utf-8",
    )
    (daemon / "subsystems.py").write_text(
        f'import os\n\nLIGADO = os.getenv("{ENV_REAL}") == "1"\n',
        encoding="utf-8",
    )
    return tmp_path


def escrever_doc(raiz: Path, nome: str, texto: str) -> Path:
    """Escreve em `docs/usage/` — o escopo onde as três regras valem."""
    pasta = raiz / "docs" / "usage"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / nome
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def test_hook_fantasma_citado_por_um_adr_reprova(repo_falso: Path) -> None:
    """A forma exata do defeito que fez este portão nascer."""
    escrever_doc(
        repo_falso,
        "adr-de-mentira.md",
        "# ADR\n"
        "\n"
        f"O hook `{NOME_FANTASMA}` cobre os proibidos.\n",
    )

    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, (
        "o validador ACEITOU um nome de arquivo solto inexistente -- está cego.\n"
        f"saída: {proc.stdout}{proc.stderr}"
    )
    assert NOME_FANTASMA in proc.stdout
    assert "adr-de-mentira.md:3" in proc.stdout, (
        f"a linha do defeito não apareceu no relatório.\nsaída: {proc.stdout}"
    )


def test_a_arvore_real_esta_limpa() -> None:
    """Regressão: o defeito que originou o portão não volta."""
    assert not list(RAIZ_REAL.rglob(NOME_FANTASMA)), (
        f"{NOME_FANTASMA} passou a existir na árvore; a premissa mudou"
    )

    proc = rodar("--all")

    assert proc.returncode == 0, (
        "há referência morta em docs/:\n" f"{proc.stdout}{proc.stderr}"
    )


def test_documento_que_so_cita_arquivo_existente_passa(repo_falso: Path) -> None:
    escrever_doc(
        repo_falso,
        "ok.md",
        "O instalador roda `scripts/existe_de_verdade.sh` no fim.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_caminho_encurtado_casa_por_sufixo(repo_falso: Path) -> None:
    """A casa cita o caminho ENCURTADO e nunca o completo -- e isso vale."""
    escrever_doc(
        repo_falso, "curto.md", f"A janela mora em `{ARQUIVO_ANINHADO}`.\n"
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_nome_solto_de_configuracao_nao_e_cobrado(repo_falso: Path) -> None:
    """`daemon.toml` vive em ~/.config, não no repositório: não é defeito."""
    escrever_doc(
        repo_falso,
        "config.md",
        "A preferência fica em `daemon.toml`, ao lado de `controllers.json`.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_comando_de_terminal_em_bloco_cercado_nao_e_cobrado(
    repo_falso: Path,
) -> None:
    """Dentro de bloco de código mora comando, não referência de repositório."""
    escrever_doc(
        repo_falso,
        "bloco.md",
        "Reproduza assim:\n\n```\nfind . -name `sumiu_faz_tempo.py`\n```\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_nome_solto_inexistente_reprova(repo_falso: Path) -> None:
    escrever_doc(
        repo_falso,
        "fantasma.md",
        "O hook `guardiao_imaginario.py` cobre os casos proibidos.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert "guardiao_imaginario.py" in proc.stdout
    assert "fantasma.md:1" in proc.stdout


def test_link_markdown_para_documento_inexistente_reprova(repo_falso: Path) -> None:
    """A sprint cita três sprints linkadas no índice que não têm arquivo."""
    escrever_doc(
        repo_falso,
        "indice.md",
        "- [SPRINT-QUE-NAO-EXISTE-01](2026-01-01-SPRINT-QUE-NAO-EXISTE-01.md)\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert "2026-01-01-SPRINT-QUE-NAO-EXISTE-01.md" in proc.stdout


def test_caminho_com_barra_inexistente_reprova(repo_falso: Path) -> None:
    escrever_doc(
        repo_falso,
        "caminho.md",
        "Ele invocava um `scripts/nunca_existiu.sh` que sumiu.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert "scripts/nunca_existiu.sh" in proc.stdout


SPRINT_REAL = "2026-08-06-LUGAR-A-MESA-01-tres-controles-ligados-e-um-jogador-so.md"


def _com_sprint(raiz: Path) -> None:
    """Cria a sprint real que os links de subida deste bloco apontam."""
    pasta = raiz / "docs" / "process" / "sprints"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / SPRINT_REAL).write_text("# LUGAR-À-MESA-01\n", encoding="utf-8")


def test_link_que_sobe_para_arquivo_inexistente_reprova(repo_falso: Path) -> None:
    """A MORDIDA da cura: `../` para nome inventado tem de reprovar."""
    _com_sprint(repo_falso)
    escrever_doc(
        repo_falso,
        "modos.md",
        "> Ver [a decisão](../adr/2026-08-06-NUNCA-EXISTIU-99.md).\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, (
        "o validador ACEITOU um link `../` para arquivo inexistente -- "
        "continua cego ao caminho que sobe.\n"
        f"saída: {proc.stdout}{proc.stderr}"
    )
    assert "2026-08-06-NUNCA-EXISTIU-99.md" in proc.stdout
    assert "modos.md:1" in proc.stdout


def test_link_que_sobe_para_o_processo_e_isento(repo_falso: Path) -> None:
    """E a outra metade, que é a cura de 20/09/2026."""
    escrever_doc(
        repo_falso,
        "modos.md",
        "> Ver [a sprint](../process/sprints/2026-08-06-NAO-VIAJA-NO-GIT.md).\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, (
        "a citação a `docs/process/` escrita como `../process/` foi cobrada "
        "como referência morta -- a isenção de 15/09 não alcançou a forma "
        "relativa, e o portão cai em todo clone limpo.\n"
        f"saída: {proc.stdout}{proc.stderr}"
    )


def test_link_que_sobe_para_arquivo_existente_passa(repo_falso: Path) -> None:
    """O outro lado: os 246 links vivos da árvore não podem virar ruído."""
    _com_sprint(repo_falso)
    escrever_doc(
        repo_falso,
        "modos-ok.md",
        f"> Ver [LUGAR-À-MESA-01](../process/sprints/{SPRINT_REAL}).\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_subida_dupla_resolve_ate_a_raiz(repo_falso: Path) -> None:
    """`../../CHANGELOG.md` e `../../README.md` são a forma mais comum em usage."""
    (repo_falso / "CHANGELOG.md").write_text("# Mudanças\n", encoding="utf-8")
    escrever_doc(
        repo_falso,
        "instalacao.md",
        "O caminho curto está no [CHANGELOG](../../CHANGELOG.md).\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_subida_dupla_para_arquivo_inexistente_reprova(repo_falso: Path) -> None:
    """A contraprova do anterior: sem o arquivo na raiz, o portão morde."""
    escrever_doc(
        repo_falso,
        "instalacao.md",
        "O caminho curto está no [CHANGELOG](../../CHANGELOG.md).\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert "CHANGELOG.md" in proc.stdout


def test_link_que_sobe_alto_demais_e_sai_da_arvore_reprova(repo_falso: Path) -> None:
    """Subir acima da raiz do repositório é sempre link morto para quem clona."""
    escrever_doc(
        repo_falso,
        "fugitivo.md",
        "Ver [fora da árvore](../../../../outro-repo/LEIA.md).\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, (
        "o validador ACEITOU link que sai da árvore do repositório.\n"
        f"saída: {proc.stdout}{proc.stderr}"
    )
    assert "outro-repo/LEIA.md" in proc.stdout


def test_link_que_sobe_nao_ganha_a_leniencia_de_sufixo(repo_falso: Path) -> None:
    """Um `../` errado não casa com o mesmo sufixo morando em outro lugar."""
    escrever_doc(
        repo_falso, "posicao.md", f"A janela mora em `../{ARQUIVO_ANINHADO}`.\n"
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, (
        "um `../` errado casou por sufixo com o arquivo real.\n"
        f"saída: {proc.stdout}{proc.stderr}"
    )
    assert f"../{ARQUIVO_ANINHADO}" in proc.stdout


def test_reticencia_de_elisao_continua_descartada(repo_falso: Path) -> None:
    """A proteção que a exclusão de `..` de fato prestava, medida na árvore."""
    escrever_doc(
        repo_falso,
        "reticencia.md",
        "Fonte histórica: `.venv/lib/.../pydualsense/enums.py` para HID.\n"
        "\n"
        "Ver [o painel](.../painel-de-decisoes.md) e também\n"
        "`docs/process/sprints/2026-08-05-TRAVA-QUE-SOLTA-TARDE-01-...md`.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, (
        "reticência de elisão virou referência morta -- a cura do `../` "
        "reabriu o falso positivo que a exclusão original segurava.\n"
        f"saída: {proc.stdout}"
    )


def test_dois_pontos_no_meio_do_caminho_continua_descartado(repo_falso: Path) -> None:
    """`docs/../scripts/x.sh` não é forma desta casa e segue fora."""
    escrever_doc(
        repo_falso,
        "meio.md",
        "Roda `docs/../scripts/nunca_existiu.sh` no fim.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_marcador_de_isencao_silencia_a_linha(repo_falso: Path) -> None:
    """A sprint que DOCUMENTA a ausência precisa poder citar o ausente."""
    escrever_doc(
        repo_falso,
        "isento.md",
        "O hook `guardiao_imaginario.py` nunca existiu. <!-- ref-externa -->\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_arquivo_de_projeto_de_fora_nao_e_cobrado(repo_falso: Path) -> None:
    """`pydualsense.py` é de terceiros; cobrar a presença dele seria errado."""
    escrever_doc(
        repo_falso,
        "externo.md",
        "O layout está confirmado em `pydualsense.py:551-567`.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_caminho_absoluto_do_sistema_nao_e_cobrado(repo_falso: Path) -> None:
    """`/etc/udev/rules.d/70-x.rules` é do sistema, não deste repositório."""
    escrever_doc(
        repo_falso,
        "sistema.md",
        "A regra fica em `/etc/udev/rules.d/70-inexistente.rules` na máquina.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_variavel_de_ambiente_inexistente_reprova(repo_falso: Path) -> None:
    """A mordida escrita na sprint, parte 1."""
    escrever_doc(
        repo_falso,
        "plugins.md",
        f"Ligue com `{ENV_FANTASMA}=1` na unit.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, (
        "o validador ACEITOU variável de ambiente que não existe no código.\n"
        f"saída: {proc.stdout}{proc.stderr}"
    )
    assert ENV_FANTASMA in proc.stdout
    assert "variável de ambiente" in proc.stdout


def test_variavel_de_ambiente_real_passa(repo_falso: Path) -> None:
    """O outro lado: a variável que EXISTE no código não pode ser cobrada."""
    escrever_doc(repo_falso, "ok-env.md", f"Ligue com `{ENV_REAL}=1`.\n")
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_documento_nao_alimenta_o_indice_de_variaveis(repo_falso: Path) -> None:
    """Um documento não pode se autoautorizar citando a própria invenção."""
    escrever_doc(
        repo_falso,
        "autoritaria.md",
        f"A variável `{ENV_FANTASMA}` liga.\nE de novo: `{ENV_FANTASMA}`.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert proc.stdout.count(ENV_FANTASMA) >= 2, proc.stdout


def test_docs_process_fica_fora_da_regra_de_variavel(repo_falso: Path) -> None:
    """Sprint PROPÕE — e propor o que não existe é o trabalho dela."""
    pasta = repo_falso / "docs" / "process" / "sprints"
    pasta.mkdir(parents=True)
    (pasta / "2026-01-01-PROPOSTA-01.md").write_text(
        f"Proponho `{ENV_FANTASMA}` e o método `{METODO_FANTASMA}`.\n",
        encoding="utf-8",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_metodo_de_ipc_inexistente_reprova(repo_falso: Path) -> None:
    """A mordida escrita na sprint, parte 2: `profile.trocar` reprova."""
    escrever_doc(repo_falso, "ipc.md", f"Chame `{METODO_FANTASMA}` no socket.\n")
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, (
        "o validador ACEITOU método de IPC não registrado.\n"
        f"saída: {proc.stdout}{proc.stderr}"
    )
    assert METODO_FANTASMA in proc.stdout
    assert "método de IPC" in proc.stdout


def test_metodo_de_ipc_real_passa(repo_falso: Path) -> None:
    """`profile.switch` está no `_handlers` e não pode ser cobrado."""
    escrever_doc(repo_falso, "ok-ipc.md", f"Chame `{METODO_REAL}` no socket.\n")
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_renomear_metodo_no_codigo_sem_tocar_o_documento_reprova(
    repo_falso: Path,
) -> None:
    """O cenário REAL da regra 3, e o motivo de ela existir."""
    escrever_doc(repo_falso, "protocolo.md", f"Chame `{METODO_REAL}`.\n")
    assert rodar("--root", str(repo_falso), "--all").returncode == 0

    servidor = repo_falso / "src" / "hefesto_dualsense4unix" / "daemon" / "ipc_server.py"
    servidor.write_text(
        servidor.read_text(encoding="utf-8").replace(METODO_REAL, "profile.select"),
        encoding="utf-8",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, (
        "renomear o método no código não derrubou o documento.\n"
        f"saída: {proc.stdout}{proc.stderr}"
    )
    assert METODO_REAL in proc.stdout


def test_token_que_nao_e_espaco_de_nomes_do_ipc_passa(repo_falso: Path) -> None:
    """`ctx.controller` não é IPC — `ctx` não está no `_handlers`."""
    escrever_doc(
        repo_falso,
        "atributos.md",
        "O plugin recebe `ctx.controller` e lê `info.wm_class`.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_nome_de_arquivo_com_cara_de_metodo_passa(repo_falso: Path) -> None:
    """`daemon.pid`, `daemon.toml` e `daemon.log` não são métodos de IPC."""
    escrever_doc(
        repo_falso,
        "arquivos.md",
        "Ao lado de `daemon.pid` mora o `daemon.toml`, e o `daemon.log`.\n",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_nota_de_verificacao_isenta_o_documento(repo_falso: Path) -> None:
    """O padrão de ADR desta casa não pode ser punido pelo portão."""
    pasta = repo_falso / "docs" / "adr"
    pasta.mkdir(parents=True)
    (pasta / "099-decisao.md").write_text(
        "# ADR-099\n"
        "\n"
        "## Decisão\n"
        "\n"
        f"Ativar por `{ENV_FANTASMA}=1` e chamar `{METODO_FANTASMA}`.\n"
        "\n"
        "## Nota de verificação — 2026-08-01\n"
        "\n"
        f"Os dois nomes acima caducaram: `{ENV_FANTASMA}` virou `{ENV_REAL}`, e\n"
        f"`{METODO_FANTASMA}` virou `{METODO_REAL}`.\n",
        encoding="utf-8",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_sem_a_nota_o_mesmo_adr_reprova(repo_falso: Path) -> None:
    """A contraprova da isenção anterior: arrancada a nota, o portão morde."""
    pasta = repo_falso / "docs" / "adr"
    pasta.mkdir(parents=True)
    (pasta / "099-decisao.md").write_text(
        "# ADR-099\n"
        "\n"
        "## Decisão\n"
        "\n"
        f"Ativar por `{ENV_FANTASMA}=1` e chamar `{METODO_FANTASMA}`.\n",
        encoding="utf-8",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert ENV_FANTASMA in proc.stdout
    assert METODO_FANTASMA in proc.stdout


def test_a_nota_isenta_so_o_nome_que_ela_cita(repo_falso: Path) -> None:
    """A isenção é por TOKEN, não por documento inteiro."""
    pasta = repo_falso / "docs" / "adr"
    pasta.mkdir(parents=True)
    (pasta / "099-decisao.md").write_text(
        "# ADR-099\n"
        "\n"
        "## Decisão\n"
        "\n"
        f"Ativar por `{ENV_FANTASMA}=1`. Depois chame `daemon.desligar`.\n"
        "\n"
        "## Nota de verificação — 2026-08-01\n"
        "\n"
        f"`{ENV_FANTASMA}` caducou; a real é `{ENV_REAL}`.\n",
        encoding="utf-8",
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert "daemon.desligar" in proc.stdout
    assert ENV_FANTASMA not in proc.stdout, (
        "a nota citou esta variável e ela ainda foi cobrada.\n" f"saída: {proc.stdout}"
    )


def test_sem_ipc_server_a_regra_de_metodo_se_desliga(repo_falso: Path) -> None:
    """Um portão que reprova tudo quando tropeça é pior que portão nenhum."""
    (repo_falso / "src" / "hefesto_dualsense4unix" / "daemon" / "ipc_server.py").unlink()
    escrever_doc(repo_falso, "ipc.md", f"Chame `{METODO_FANTASMA}`.\n")
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, proc.stdout


def test_readme_entra_na_varredura(repo_falso: Path) -> None:
    """A página que mais gente copia ficava de fora só por morar na raiz."""
    (repo_falso / "README.md").write_text(
        f"Ligue os plugins com `{ENV_FANTASMA}=1`.\n", encoding="utf-8"
    )
    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, proc.stdout
    assert "README.md:1" in proc.stdout


def test_link_com_basename_certo_e_pasta_errada_reprova(repo_falso: Path) -> None:
    """A MORDIDA da cura E3: a forma exata do defeito plantado na auditoria."""
    pasta = repo_falso / "docs" / "process" / "sprints"
    pasta.mkdir(parents=True)
    (pasta / "real.md").write_text("# Sprint\n", encoding="utf-8")
    escrever_doc(repo_falso, "citante.md", "Ver [a sprint](real.md).\n")

    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 1, (
        "o validador ACEITOU um link com o basename certo e a pasta errada -- "
        "voltou a casar por sufixo sem resolver contra a pasta de quem cita.\n"
        f"saída: {proc.stdout}{proc.stderr}"
    )
    assert "real.md" in proc.stdout
    assert "citante.md:1" in proc.stdout


def test_link_com_basename_e_a_pasta_certa_passa(repo_falso: Path) -> None:
    """A contraprova: o MESMO basename, citado de onde o arquivo de fato mora."""
    pasta = repo_falso / "docs" / "process" / "sprints"
    pasta.mkdir(parents=True)
    (pasta / "real.md").write_text("# Sprint\n", encoding="utf-8")
    (pasta / "citante.md").write_text("Ver [a sprint](real.md).\n", encoding="utf-8")

    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, (
        "um link bare para o vizinho de verdade da mesma pasta passou a "
        f"reprovar -- a cura ficou estreita demais.\nsaída: {proc.stdout}"
    )


def test_nome_solto_entre_crases_continua_leniente_de_qualquer_pasta(
    repo_falso: Path,
) -> None:
    """A E3 não pode fechar a convenção que `test_caminho_encurtado_casa_por_sufixo`"""
    fundo = repo_falso / "src" / "pacote" / "fundo"
    fundo.mkdir(parents=True)
    (fundo / "remoto.py").write_text("# módulo\n", encoding="utf-8")
    escrever_doc(repo_falso, "cita_por_crase.md", "Veja `remoto.py` para o resto.\n")

    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, (
        "um nome solto entre crases, convenção desta casa, passou a "
        f"reprovar por causa da E3.\nsaída: {proc.stdout}"
    )


def test_link_bare_para_arquivo_de_raiz_passa_de_qualquer_pasta(
    repo_falso: Path,
) -> None:
    """`install.sh` não tem diretório para encurtar -- não há "pasta errada"
    possível para ele, então o link bare vale de QUALQUER documento.
    """
    (repo_falso / "install.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    escrever_doc(repo_falso, "cita_a_raiz.md", "Rode o [instalador](install.sh).\n")

    proc = rodar("--root", str(repo_falso), "--all")

    assert proc.returncode == 0, (
        "um link bare para um arquivo que mora NA RAIZ passou a reprovar "
        f"citado de outra pasta.\nsaída: {proc.stdout}"
    )
