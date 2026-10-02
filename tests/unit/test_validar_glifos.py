"""Testes do portão de glifos (``scripts/validar-glifos.py``), sprint GATE-EMOJI-01."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "validar-glifos.py"

BLOCOS_ADR_011 = (
    (0x2190, 0x21FF),
    (0x2500, 0x257F),
    (0x2580, 0x259F),
    (0x25A0, 0x25FF),
)

CODEPOINTS_CANONICOS_ADR_011 = (0x25CF, 0x25CB, 0x25AE, 0x25AF, 0x25D0)

INTERSECAO_MEDIDA = (0x25FD, 0x25FE)

ESTRELA_PROIBIDA = 0x2B50
VARIATION_SELECTOR_16 = 0xFE0F

CLAUSULA_DE_PRESERVACAO = (
    "    if preservado_pelo_adr_011(cp)[0]:\n"
    "        return False\n"
)
FLAGS_DO_LS_FILES = ', "--cached", "--others", "--exclude-standard"'


def _roda(args: list[str], cwd: Path, script: Path = SCRIPT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


def _achados(saida: str) -> list[tuple[str, int, int, int]]:
    """Converte a saída em ``(arquivo, linha, coluna, codepoint)``."""
    itens: list[tuple[str, int, int, int]] = []
    for ln in saida.splitlines():
        if ": U+" not in ln:
            continue
        local, resto = ln.split(": U+", 1)
        arquivo, linha, coluna = local.rsplit(":", 2)
        itens.append((arquivo, int(linha), int(coluna), int(resto.split()[0], 16)))
    return itens


@pytest.fixture()
def sandbox(tmp_path: Path) -> Path:
    """Repositório de brinquedo com o script dentro, para os testes de mordida."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    destino = tmp_path / "scripts"
    destino.mkdir()
    alvo = destino / "validar-glifos.py"
    alvo.write_bytes(SCRIPT.read_bytes())
    alvo.chmod(0o755)
    return tmp_path


def _script_mutilado(sandbox: Path, trecho: str, nome: str) -> Path:
    """Copia o script arrancando ``trecho``. Falha se o trecho não existir."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert trecho in fonte, (
        f"o trecho que o teste arranca sumiu de {SCRIPT.name}; "
        "sem ele a mordida vira teatro"
    )
    mutilado = sandbox / "scripts" / nome
    mutilado.write_text(fonte.replace(trecho, "", 1), encoding="utf-8")
    return mutilado


def test_a_reprova_a_estrela_proibida_em_documento(sandbox: Path) -> None:
    """O caso que fez o portão nascer, reproduzido em caixa própria."""
    alvo = sandbox / "docs" / "usage" / "troubleshooting.md"
    alvo.parent.mkdir(parents=True)
    estrela = chr(ESTRELA_PROIBIDA)
    alvo.write_text(
        "# Troubleshooting\n"
        "\n"
        "| Modo | Veredito |\n"
        "|---|---|\n"
        f"| DirectInput por Bluetooth | {estrela} **PROVADO estável** |\n"
        "\n"
        f"## {estrela} A cura: trocar de modo\n",
        encoding="utf-8",
    )

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 1, res.stdout + res.stderr

    itens = _achados(res.stdout)
    assert itens, res.stdout
    assert {cp for _a, _l, _c, cp in itens} == {ESTRELA_PROIBIDA}
    linhas = {linha for _a, linha, _c, _cp in itens}
    assert linhas == {5, 7}, f"linhas encontradas: {sorted(linhas)}"


def test_o_defeito_que_originou_o_portao_esta_curado() -> None:
    """Regressão: as duas estrelas do troubleshooting do 8BitDo não voltam."""
    alvo = RAIZ / "docs" / "usage" / "troubleshooting-8bitdo.md"
    assert alvo.exists()

    res = _roda(["--check-file", str(alvo)], RAIZ)
    assert res.returncode == 0, res.stdout + res.stderr


def test_formato_da_saida_tem_arquivo_linha_coluna_e_codepoint(sandbox: Path) -> None:
    alvo = sandbox / "docs" / "nota.md"
    alvo.parent.mkdir(parents=True)
    alvo.write_text(f"Resultado{chr(ESTRELA_PROIBIDA)} do teste\n", encoding="utf-8")

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 1
    itens = _achados(res.stdout)
    assert len(itens) == 1
    _arquivo, linha, coluna, cp = itens[0]
    assert (linha, coluna, cp) == (1, 10, ESTRELA_PROIBIDA)
    assert "WHITE MEDIUM STAR" in res.stdout


def test_reprova_variation_selector_16(sandbox: Path) -> None:
    """VS16 só existe para forçar a forma emoji. Quem escreve isso quer emoji."""
    alvo = sandbox / "docs" / "nota.md"
    alvo.parent.mkdir(parents=True)
    alvo.write_text(f"seta{chr(0x2194)}{chr(VARIATION_SELECTOR_16)} colorida\n", encoding="utf-8")

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 1
    cps = {cp for _a, _l, _c, cp in _achados(res.stdout)}
    assert cps == {VARIATION_SELECTOR_16}


def test_b_passa_em_arquivo_com_glifos_permitidos(sandbox: Path) -> None:
    """Os cinco codepoints que o ADR-011 nomeia, mais barra e moldura."""
    alvo = sandbox / "src" / "widgets.py"
    alvo.parent.mkdir(parents=True)
    permitidos = "".join(chr(cp) for cp in CODEPOINTS_CANONICOS_ADR_011)
    moldura = chr(0x250C) + chr(0x2500) * 4 + chr(0x2510)
    barra = chr(0x2588) * 3 + chr(0x2591) * 2
    seta = chr(0x2192)
    alvo.write_text(
        f'ESTADO = "{permitidos}"\nMOLDURA = "{moldura}"\n'
        f'BARRA = "{barra}"\nFLUXO = "entrada {seta} saída"\n',
        encoding="utf-8",
    )

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 0, res.stdout + res.stderr


def test_b_passa_no_widgets_da_tui() -> None:
    """O arquivo que a sprint nomeia como caso (b), rodado como está no repo."""
    alvo = RAIZ / "src" / "hefesto_dualsense4unix" / "tui" / "widgets" / "__init__.py"
    assert alvo.exists()

    res = _roda(["--check-file", str(alvo)], RAIZ)
    assert res.returncode == 0, res.stdout + res.stderr


def test_intersecao_emoji_presentation_com_blocos_adr_nao_e_vazia() -> None:
    """A cláusula de preservação só morde porque os dois conjuntos se cruzam."""
    res = _roda(["--mostrar-criterio"], RAIZ)
    assert res.returncode == 0, res.stderr
    for cp in INTERSECAO_MEDIDA:
        assert f"U+{cp:04X}" in res.stdout, res.stdout
        assert any(ini <= cp <= fim for ini, fim in BLOCOS_ADR_011)


def test_c_arrancar_a_clausula_de_preservacao_faz_o_portao_reprovar(sandbox: Path) -> None:
    """A prova de que o portão lê o que acha que lê."""
    alvo = sandbox / "src" / "medidor.py"
    alvo.parent.mkdir(parents=True)
    literais = "".join(chr(cp) for cp in INTERSECAO_MEDIDA)
    alvo.write_text(f'CELULAS = "{literais}"\n', encoding="utf-8")

    curado = _roda(["--check-file", str(alvo)], sandbox)
    assert curado.returncode == 0, (
        "com a cláusula do ADR-011 o portão tem de preservar Geometric Shapes:\n"
        + curado.stdout
        + curado.stderr
    )

    mutilado = _script_mutilado(sandbox, CLAUSULA_DE_PRESERVACAO, "sem-preservacao.py")
    arrancado = _roda(["--check-file", str(alvo)], sandbox, script=mutilado)
    assert arrancado.returncode == 1, (
        "sem a cláusula o portão TINHA de reprovar; se continuou verde, "
        "a cláusula não é o que decide e o teste não testa nada"
    )
    assert {cp for _a, _l, _c, cp in _achados(arrancado.stdout)} == set(INTERSECAO_MEDIDA)


def test_c_a_clausula_arrancada_tambem_derruba_o_canonico_do_adr(sandbox: Path) -> None:
    """Contraprova do escopo: os cinco canônicos passam nas duas versões."""
    alvo = sandbox / "src" / "canonicos.py"
    alvo.parent.mkdir(parents=True)
    literais = "".join(chr(cp) for cp in CODEPOINTS_CANONICOS_ADR_011)
    alvo.write_text(f'ESTADO = "{literais}"\n', encoding="utf-8")

    mutilado = _script_mutilado(sandbox, CLAUSULA_DE_PRESERVACAO, "sem-preservacao2.py")
    res = _roda(["--check-file", str(alvo)], sandbox, script=mutilado)
    assert res.returncode == 0, res.stdout


def test_widgets_init_nao_carrega_glifo_literal() -> None:
    """A medição que obrigou a mordida a mudar de alvo."""
    alvo = RAIZ / "src" / "hefesto_dualsense4unix" / "tui" / "widgets" / "__init__.py"
    texto = alvo.read_text(encoding="utf-8")
    literais = [
        ch for ch in texto
        if any(ini <= ord(ch) <= fim for ini, fim in BLOCOS_ADR_011)
    ]
    assert literais == [], (
        "o arquivo voltou a ter glifo literal; a mordida da sprint pode voltar "
        f"a apontar para ele: {[hex(ord(c)) for c in literais]}"
    )
    assert "chr(0x25AE)" in texto and "chr(0x2588)" in texto


def test_all_enxerga_arquivo_novo_ainda_nao_adicionado(sandbox: Path) -> None:
    novo = sandbox / "docs" / "recem-escrito.md"
    novo.parent.mkdir(parents=True)
    novo.write_text(f"# Guia\n\nPronto{chr(ESTRELA_PROIBIDA)}\n", encoding="utf-8")

    res = _roda(["--all"], sandbox)
    assert res.returncode == 1, (
        "arquivo novo, ainda sem git add, tem de ser varrido:\n" + res.stdout
    )
    assert "recem-escrito.md" in res.stdout


def test_all_sem_as_flags_fica_cego_ao_arquivo_novo(sandbox: Path) -> None:
    """Mordida do modo --all: sem ``--others --exclude-standard`` ele não vê nada."""
    novo = sandbox / "docs" / "recem-escrito.md"
    novo.parent.mkdir(parents=True)
    novo.write_text(f"# Guia\n\nPronto{chr(ESTRELA_PROIBIDA)}\n", encoding="utf-8")

    mutilado = _script_mutilado(sandbox, FLAGS_DO_LS_FILES, "sem-others.py")
    res = _roda(["--all"], sandbox, script=mutilado)
    assert res.returncode == 0, res.stdout
    assert "recem-escrito.md" not in res.stdout


def test_all_respeita_gitignore(sandbox: Path) -> None:
    (sandbox / ".gitignore").write_text("lixo/\n", encoding="utf-8")
    ignorado = sandbox / "lixo" / "gerado.md"
    ignorado.parent.mkdir(parents=True)
    ignorado.write_text(f"{chr(ESTRELA_PROIBIDA)}\n", encoding="utf-8")

    res = _roda(["--all"], sandbox)
    assert res.returncode == 0, res.stdout


def test_binario_e_ignorado(sandbox: Path) -> None:
    alvo = sandbox / "assets" / "captura.bin"
    alvo.parent.mkdir(parents=True)
    alvo.write_bytes(b"\x00\x01" + chr(ESTRELA_PROIBIDA).encode("utf-8"))

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 0, res.stdout


def test_arquivo_nao_utf8_e_ignorado(sandbox: Path) -> None:
    alvo = sandbox / "docs" / "latin1.txt"
    alvo.parent.mkdir(parents=True)
    alvo.write_bytes("cão".encode("latin-1"))

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 0, res.stdout


def test_pycache_e_ignorado(sandbox: Path) -> None:
    alvo = sandbox / "src" / "__pycache__" / "nota.py"
    alvo.parent.mkdir(parents=True)
    alvo.write_text(f'X = "{chr(ESTRELA_PROIBIDA)}"\n', encoding="utf-8")

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 0, res.stdout


def test_repositorio_inteiro_limpo() -> None:
    """O número que a sprint dizia não existir sem portão: quantos emojis há."""
    res = _roda(["--all"], RAIZ)
    itens = _achados(res.stdout)
    assert itens == [], (
        "emoji proibido no repositório:\n" + "\n".join(str(it) for it in itens)
    )
    assert res.returncode == 0, res.stdout + res.stderr


def _portao():
    """O módulo do portão, carregado do arquivo — ele tem hífen no nome."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_vg_excecoes", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAsExcecoesDelaSaoUmaListaNaoUmaFaixa:
    """Ela abriu o portão para a fileira de saída de som, e só para ela."""

    def test_as_quatro_que_ela_nomeou_passam(self) -> None:
        vg = _portao()
        assert vg.EXCECOES_DELA, "a lista nasceu vazia"
        for cp, papel in vg.EXCECOES_DELA.items():
            assert not vg.e_proibido(cp), f"U+{cp:05X} ({papel}) devia passar"
            assert papel.strip(), (
                f"U+{cp:05X} entrou sem o papel escrito — e o papel é o que "
                f"responde à próxima pessoa que quiser acrescentar mais um")

    def test_o_resto_do_emoji_continua_reprovado(self) -> None:
        """A exceção não pode virar a porta aberta."""
        vg = _portao()
        for cp in (0x1F389, 0x2705, 0x274C, 0x1F4BB, 0x1F600, 0x1F44D):
            assert vg.e_proibido(cp), f"U+{cp:05X} passou e não devia"

    def test_o_seletor_de_variacao_continua_reprovado(self) -> None:
        """A exceção é para o SÍMBOLO, não para o realce dele."""
        vg = _portao()
        assert vg.e_proibido(vg.VARIATION_SELECTOR_16)

    def test_a_excecao_e_uma_lista_e_nao_uma_faixa(self) -> None:
        """A FORMA do dado é a trava."""
        vg = _portao()
        assert isinstance(vg.EXCECOES_DELA, dict)
        assert all(isinstance(k, int) for k in vg.EXCECOES_DELA)
        assert len(vg.EXCECOES_DELA) < 24, (
            "a lista passou de duas dezenas — se ela cresceu tanto, a pergunta "
            "não é qual acrescentar, é se o ADR-011 ainda descreve o produto")

    def test_a_preservacao_do_adr_011_continua_vencendo(self) -> None:
        """O que já era preservado não pode ter sido atropelado pela exceção."""
        vg = _portao()
        for cp in (0x25FD, 0x25FE, 0x25CF, 0x25CB, 0x25AE, 0x25AF, 0x25D0):
            assert not vg.e_proibido(cp), f"U+{cp:05X} caiu — a ordem mudou"
