"""Testes do portão de glifos (``scripts/validar-glifos.py``), sprint GATE-EMOJI-01.

Nenhum glifo aparece desenhado neste arquivo: todos nascem de ``chr()`` sobre o
codepoint. O motivo é o assunto da própria sprint -- o higienizador do ambiente
apaga caractere dos blocos que o ADR-011 manda preservar, e já apagou, no mesmo
passe, o desenho do código e o valor esperado do teste, deixando o teste verde
com a função quebrada.

As três provas que a sprint pede estão em:

- ``test_a_reprova_a_estrela_viva_no_troubleshooting_8bitdo``
- ``test_b_passa_em_arquivo_com_glifos_permitidos``
- ``test_c_arrancar_a_clausula_de_preservacao_faz_o_portao_reprovar``  (a mordida)

Desvio medido, e está documentado em
``test_widgets_init_nao_carrega_glifo_literal``: a sprint mandava usar
``src/hefesto_dualsense4unix/tui/widgets/__init__.py`` como alvo da mordida, mas
aquele arquivo não tem **nenhum** caractere literal dos quatro blocos -- ele já
constrói tudo por ``chr()``. Sem caractere não há o que preservar, então
arrancar a cláusula não podia fazê-lo reprovar. A mordida usa a interseção real
dos dois conjuntos, medida do próprio Unicode: U+25FD e U+25FE.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "validar-glifos.py"

# Os quatro blocos do ADR-011, seção "Decisão", item "Permitidos".
BLOCOS_ADR_011 = (
    (0x2190, 0x21FF),  # Arrows
    (0x2500, 0x257F),  # Box Drawing
    (0x2580, 0x259F),  # Block Elements
    (0x25A0, 0x25FF),  # Geometric Shapes
)

# Os cinco codepoints que o ADR-011 nomeia um a um como exemplos canônicos.
CODEPOINTS_CANONICOS_ADR_011 = (0x25CF, 0x25CB, 0x25AE, 0x25AF, 0x25D0)

# Interseção medida entre Emoji_Presentation e os blocos preservados. É por
# causa dela que a cláusula de preservação não é decorativa.
INTERSECAO_MEDIDA = (0x25FD, 0x25FE)

ESTRELA_PROIBIDA = 0x2B50  # WHITE MEDIUM STAR
VARIATION_SELECTOR_16 = 0xFE0F

# Trechos exatos que os testes de mordida arrancam do script. Se o texto do
# script mudar, o teste falha no assert de sanidade em vez de passar à toa.
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


# ---------------------------------------------------------------------------
# (a) O portão tem de reprovar HOJE, sem alterar uma linha do repositório.
# ---------------------------------------------------------------------------
def test_a_reprova_a_estrela_proibida_em_documento(sandbox: Path) -> None:
    """O caso que fez o portão nascer, reproduzido em caixa própria.

    Até 27/07/2026 este teste apontava para
    ``docs/usage/troubleshooting-8bitdo.md``, que tinha dois U+2B50 vivos nas
    linhas 29 e 48 -- commitados, passados por pre-commit e por CI, provando que
    o portão prometido pelo ``CONTRIBUTING`` não existia.

    O portão passou a existir e o defeito foi corrigido no mesmo dia: os dois
    pictogramas viraram texto literal, que é o que o ADR-011 manda usar em
    documento. Manter a violação viva só para o teste usá-la de material seria
    usar o defeito como andaime -- e um portão que depende de haver sujeira para
    provar que funciona deixa de provar assim que alguém limpa.

    A forma do caso original está preservada aqui: mesma extensão, mesma
    posição (célula de tabela e título de seção), duas ocorrências.
    """
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
    # A seta em si é bloco preservado e continua permitida; o seletor, não.
    assert cps == {VARIATION_SELECTOR_16}


# ---------------------------------------------------------------------------
# (b) O portão tem de PASSAR em arquivo com glifo permitido.
# ---------------------------------------------------------------------------
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


def test_b_passa_no_registro_historico_da_regressao() -> None:
    """O diff de 21/04/2026 guarda 238 caracteres dos blocos preservados.

    É o registro do incidente que originou o ADR-011. Se o portão reprovar este
    arquivo, o portão virou o higienizador.
    """
    alvo = RAIZ / "docs" / "history" / "glyph-strip-regression-2026-04-23.diff"
    if not alvo.exists():
        pytest.skip("registro histórico ausente nesta árvore")

    texto = alvo.read_text(encoding="utf-8")
    quantos = sum(
        1
        for ch in texto
        if any(ini <= ord(ch) <= fim for ini, fim in BLOCOS_ADR_011)
    )
    assert quantos > 100, "o registro histórico perdeu os glifos que o definem"

    res = _roda(["--check-file", str(alvo)], RAIZ)
    assert res.returncode == 0, res.stdout + res.stderr


# ---------------------------------------------------------------------------
# (c) A MORDIDA: arrancar a cláusula de preservação tem de fazer reprovar.
# ---------------------------------------------------------------------------
def test_intersecao_emoji_presentation_com_blocos_adr_nao_e_vazia() -> None:
    """A cláusula de preservação só morde porque os dois conjuntos se cruzam.

    Se uma revisão futura do Unicode esvaziar essa interseção, a cláusula vira
    código morto e a mordida abaixo deixa de provar qualquer coisa. Este teste
    é o alarme desse dia.
    """
    res = _roda(["--mostrar-criterio"], RAIZ)
    assert res.returncode == 0, res.stderr
    for cp in INTERSECAO_MEDIDA:
        assert f"U+{cp:04X}" in res.stdout, res.stdout
        assert any(ini <= cp <= fim for ini, fim in BLOCOS_ADR_011)


def test_c_arrancar_a_clausula_de_preservacao_faz_o_portao_reprovar(sandbox: Path) -> None:
    """A prova de que o portão lê o que acha que lê.

    U+25FD e U+25FE são Geometric Shapes -- o ADR-011 manda preservar -- e são
    ``Emoji_Presentation``. Com a cláusula, o portão passa. Sem ela, reprova.
    """
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
    """Contraprova do escopo: os cinco canônicos passam nas duas versões.

    U+25CF e companhia não são ``Emoji_Presentation``, então continuam verdes
    mesmo sem a cláusula. Isso delimita o que a mordida acima prova -- e é o
    motivo de o arquivo da TUI não poder ser o alvo dela.
    """
    alvo = sandbox / "src" / "canonicos.py"
    alvo.parent.mkdir(parents=True)
    literais = "".join(chr(cp) for cp in CODEPOINTS_CANONICOS_ADR_011)
    alvo.write_text(f'ESTADO = "{literais}"\n', encoding="utf-8")

    mutilado = _script_mutilado(sandbox, CLAUSULA_DE_PRESERVACAO, "sem-preservacao2.py")
    res = _roda(["--check-file", str(alvo)], sandbox, script=mutilado)
    assert res.returncode == 0, res.stdout


def test_widgets_init_nao_carrega_glifo_literal() -> None:
    """A medição que obrigou a mordida a mudar de alvo.

    A sprint pedia arrancar a cláusula e ver
    ``tui/widgets/__init__.py`` reprovar. Aquele arquivo constrói todos os
    desenhos por ``chr()`` -- não há caractere literal dos quatro blocos nele,
    então nenhuma alteração no portão pode fazê-lo reprovar por glifo
    preservado. Medição vence instrução; o alvo virou a interseção real.
    """
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


# ---------------------------------------------------------------------------
# Defeito conhecido: git ls-files puro é cego a arquivo novo.
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Higiene: binário e diretório de máquina ficam de fora.
# ---------------------------------------------------------------------------
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
    """O número que a sprint dizia não existir sem portão: quantos emojis há.

    Medido em 27/07/2026, antes da cura: dois, os dois U+2B50 do troubleshooting
    do 8BitDo. Depois da cura: zero. Este teste trava o zero -- é o número que
    só passou a existir porque o portão passou a existir.
    """
    res = _roda(["--all"], RAIZ)
    itens = _achados(res.stdout)
    assert itens == [], (
        "emoji proibido no repositório:\n" + "\n".join(str(it) for it in itens)
    )
    assert res.returncode == 0, res.stdout + res.stderr
