"""GTK-2 — os três leitores do `main.glade` que NÃO são a janela.

**A decisão dela** (`D-0609-GTK-LEVA-INTEIRA`): *"a ideia sempre foi
reaproveitar o que fiz no gtk e não apontar nada mais pra lá mas pro html"*. O
motor fica; a janela sai. Enquanto três programas que não são a janela lerem o
`gui/main.glade`, apagá-lo quebra o produto NOVO — e esta régua é a que prova
que já não quebra.

OS TRÊS, e o que cada um lia:

===================================  =======================================
`interface/aba05.py:273`             duas frases de tela, no corpo do módulo
`integrations/storm_doctor.py:69`    o rótulo vivo de um botão, pelo id
`scripts/i18n_extract.sh:22`         as strings traduzíveis da janela
===================================  =======================================

A CORREÇÃO DO ENUNCIADO, e ela é entrega: a sprint diz *"três textos de tela"*
na aba 05. **São DOIS desde 05/09/2026** — a terceira (*"Espera 5 segundos
antes de trocar de faixa"*) explicava o Modo Auto, que saiu desta tela por
decisão dela, e `test_a_frase_do_auto_nao_volta_a_aba` existe para ela não
voltar.

AS MORDIDAS, todas sobre o PRODUTO e nenhuma sobre o texto do fonte:

* devolva o `_GLADE = (…/"main.glade").read_text()` ao corpo de `aba05.py` →
  `test_a_aba_05_monta_com_o_glade_apagado` reprova com o `FileNotFoundError`
  que a `GTK-3` encontraria no dia de apagar;
* troque a bandeira `lido_da_fonte` de `storm_doctor.rotulo_do_botao` por
  `alvo == se_faltar` → `test_a_reserva_fica_vazia_quando_a_leitura_acerta`
  reprova, porque hoje o rótulo do `btn_storm_fix_safe` no glade é palavra por
  palavra o `se_faltar` desta casa;
* apague o registro em `_ROTULOS_DE_RESERVA` →
  `test_sem_a_fonte_a_frase_fica_de_pe_e_o_produto_sabe` reprova na segunda
  metade (a primeira continua passando, e é esse o ponto);
* tire a guarda do `$GLADE` do `i18n_extract.sh` →
  `test_sem_o_glade_o_extrator_para_e_diz_o_que_sumiu` reprova, e o `.pot`
  volta a ficar velho em silêncio.

ONDE ELA NÃO MEDE: não abre janela nenhuma, não fala com o daemon e não escreve
uma linha na árvore — o gerador da aba 05 roda numa CÓPIA, com a bancada
desviada por `HEFESTO_BANCADA`.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GLADE = RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

#: ONDE CADA FRASE MORA NO GLADE, enquanto o glade existir. As âncoras são as
#: MESMAS que `aba05._do_glade` usava até 06/09/2026 — de propósito: é a
#: comparação que impede as duas telas de divergirem antes de a janela sair.
NO_GLADE = {
    "DICA_DO_TETO_DA_MESA":
        r'id="rumble_policy_economia".*?tooltip-text[^>]*>[^<]*?'
        r'(O Perfil de Bateria pode impor um teto[^<]*?)</property>',
    "DICA_DOS_VALORES_QUE_PASSAM":
        r'id="rumble_info".*?<property name="label"[^>]*>&lt;i&gt;'
        r'(.*?)&lt;/i&gt;</property>',
}

#: O id do botão que as frases do doctor mandam clicar, e a reserva dele.
#:
#: **A RESERVA MUDOU DE PALAVRA EM 06/09/2026 (`SISTEMA-STEAM-01`)**, e a razão
#: é um defeito que estava VIVO na tela dela: a frase mandava clicar em
#: *"Consertar problemas conhecidos"* **na aba Sistema**, e na aba Sistema que
#: ela usa o botão se chama *"Refazer os consertos automáticos"*. O
#: `rotulo_do_botao` passou a perguntar primeiro à PÁGINA que o produto
#: renderiza, e só depois ao glade — a reserva acompanha o que a tela viva diz.
BOTAO = "btn_storm_fix_safe"
RESERVA_DO_BOTAO = "Refazer os consertos automáticos"


def _sem_fonte_nenhuma(doutor, monkeypatch, tmp_path) -> None:
    """Tira as DUAS fontes do alcance — a página e o glade.

    ERAM UMA SÓ ATÉ 06/09/2026, e por isso bastava mover o `__file__`. Com a
    página respondendo primeiro, mover só o `__file__` deixa o rótulo ser LIDO
    e a reserva nunca sai: o caso passaria a medir o caminho feliz enquanto o
    docstring dele diz que mede a ausência — que é a forma de instrumento falso
    que este arquivo inteiro existe para pegar.
    """
    monkeypatch.setattr(doutor, "_NA_TELA_VIVA", {})
    monkeypatch.setattr(
        doutor, "__file__", str(tmp_path / "sem_gui" / "storm_doctor.py"))


# ===========================================================================
# 1. AS DUAS FRASES DA VIBRAÇÃO TÊM DONO NO MOTOR
# ===========================================================================
def test_a_aba_05_le_as_duas_frases_do_motor_e_nao_as_digita(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O dono é `app/telas/vibracao`, e a aba **lê** dele — não redigita.

    A identidade (`is`) é o que separa ler de copiar: dois literais iguais
    passariam num `==` e divergiriam na primeira edição, que é exatamente o
    defeito que a disciplina de 26/08 existe para matar.

    O `HEFESTO_BANCADA` está aqui porque importar `aba05` GERA a página: sem o
    desvio, esta régua reescreveria `mockup/05-vibracao.html` na árvore de quem
    a roda. Instrumento não muda o que mede.
    """
    monkeypatch.setenv("HEFESTO_BANCADA", str(tmp_path))
    sys.path.insert(0, str(INTERFACE))
    import aba05

    from hefesto_dualsense4unix.app.telas import vibracao

    for nome in NO_GLADE:
        assert getattr(aba05, nome) is getattr(vibracao, nome), (
            f"a aba 05 deixou de LER {nome} de `app/telas/vibracao` — se ela "
            "voltar a digitar o texto, as duas cópias divergem na primeira "
            "edição (RUM-01, o botão 'Devolver ao jogo' que não existia)")


@pytest.mark.skipif(not GLADE.exists(),
                    reason="o `gui/main.glade` já saiu (GTK-3) — não há duas "
                           "telas a comparar, e o dono passou a ser único")
def test_enquanto_o_glade_existir_as_duas_telas_dizem_o_mesmo() -> None:
    """A janela estável e a aba nova repetem a MESMA oração, palavra por palavra.

    Enquanto os dois arquivos existirem há duas cópias no disco, e duas cópias
    divergem. Esta é a régua que segura a divergência até a `GTK-3` apagar o
    XML — e ela se cala sozinha no dia em que isso acontecer, em vez de virar
    um vermelho herdado.
    """
    from hefesto_dualsense4unix.app.telas import vibracao

    fonte = GLADE.read_text(encoding="utf-8")
    for nome, padrao in NO_GLADE.items():
        achado = re.search(padrao, fonte, re.S)
        assert achado, (
            f"a âncora de {nome} saiu do glade. Ou a janela mudou a frase (e o "
            "dono em `app/telas/vibracao` tem de acompanhar), ou ela saiu de lá "
            "— e aí esta régua sai junto")
        assert html.unescape(achado.group(1)).strip() == getattr(vibracao, nome), (
            f"a janela estável e o dono novo divergiram em {nome}: a janela diz "
            f"{html.unescape(achado.group(1)).strip()!r} e o produto novo diz "
            f"{getattr(vibracao, nome)!r}")


def test_a_aba_05_monta_com_o_glade_apagado(tmp_path: Path) -> None:
    """A MORDIDA FORTE, e é ela que prova a sprint inteira.

    O `gui/main.glade` é **apagado de verdade** numa cópia descartável, e a aba
    05 tem de continuar montando com as duas frases dentro. Nada é remendado: o
    arquivo não existe, e é esse o mundo em que a `GTK-3` vai deixar a árvore.

    A cópia leva `src/`, `docs/data` e `assets/` (o que o gerador lê) e a
    bancada vai para o `tmp_path` pelo `HEFESTO_BANCADA` — a árvore de quem
    roda não recebe um byte.
    """
    arvore = tmp_path / "descartavel"
    (arvore / "docs").mkdir(parents=True)
    ignorar = shutil.ignore_patterns("__pycache__")
    shutil.copytree(RAIZ / "src", arvore / "src", ignore=ignorar)
    shutil.copytree(RAIZ / "docs" / "data", arvore / "docs" / "data", ignore=ignorar)
    shutil.copytree(RAIZ / "assets", arvore / "assets", ignore=ignorar)

    glade = arvore / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
    if glade.exists():
        glade.unlink()
    assert not glade.exists(), "a mordida não apagou o glade — ela não mediu nada"

    bancada = tmp_path / "bancada"
    bancada.mkdir()
    saida = subprocess.run(
        [sys.executable, "aba05.py"],
        cwd=arvore / "src" / "hefesto_dualsense4unix" / "interface",
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
             "HEFESTO_BANCADA": str(bancada),
             "PYTHONPATH": str(arvore / "src")},
        capture_output=True, text=True, timeout=180,
    )
    assert saida.returncode == 0, (
        "a aba 05 NÃO monta com o `gui/main.glade` apagado — é este o defeito "
        f"que a GTK-3 encontraria no dia de apagar:\n{saida.stderr[-3000:]}")

    pagina = (bancada / "05-vibracao.html").read_text(encoding="utf-8")
    from hefesto_dualsense4unix.app.telas import vibracao

    for nome in NO_GLADE:
        frase = getattr(vibracao, nome)
        assert pagina.count(frase) == 1, (
            f"a aba montou sem o glade, mas {nome} sumiu da página — montar "
            "calado é pior que não montar")


# ===========================================================================
# 2. O RÓTULO DE RESERVA NÃO É MAIS CALADO
# ===========================================================================
@pytest.fixture
def doutor(monkeypatch: pytest.MonkeyPatch):
    """O `storm_doctor` com os dois caches ZERADOS.

    Os dois são de módulo e sobrevivem entre casos: sem isto, a ordem dos
    testes decidiria o resultado — que é como um dublê envenena outro arquivo
    (medido em 04/09/2026).
    """
    from hefesto_dualsense4unix.integrations import storm_doctor as sd

    monkeypatch.setattr(sd, "_ROTULOS_EM_CACHE", {})
    monkeypatch.setattr(sd, "_ROTULOS_DE_RESERVA", {})
    return sd


@pytest.mark.skipif(not GLADE.exists(), reason="o `gui/main.glade` já saiu (GTK-3)")
def test_a_reserva_fica_vazia_quando_a_leitura_acerta(doutor) -> None:
    """Com a fonte ao alcance, NADA é declarado reserva.

    **É AQUI QUE O INSTRUMENTO PODE MENTIR, e o caso existe por isso:** o
    rótulo lido é palavra por palavra o `se_faltar` desta casa. Uma
    implementação que comparasse as duas strings acusaria reserva sobre uma
    leitura que deu certo — régua respondendo sobre outra coisa que não o
    produto.

    **A FONTE MUDOU DE ORDEM EM 06/09/2026:** quem responde primeiro é a PÁGINA
    que o produto renderiza, e o glade só depois. O `skipif` do glade fica: no
    dia em que ele sair, este caso continua valendo pela página, e é ela que
    tem de responder.
    """
    lido = doutor.rotulo_do_botao(BOTAO, RESERVA_DO_BOTAO)
    assert lido == RESERVA_DO_BOTAO, (
        f"o rótulo lido da tela viva é {lido!r} e a reserva desta casa diz "
        f"{RESERVA_DO_BOTAO!r}. A reserva tem de acompanhar a tela: ela é o "
        "que a frase publica no dia em que fonte nenhuma responder.")
    assert doutor.rotulos_de_reserva() == {}, (
        "o produto declarou RESERVA sobre um rótulo que ele acabou de LER — a "
        "bandeira `lido_da_fonte` virou uma comparação de strings")


def test_sem_a_fonte_a_frase_fica_de_pe_e_o_produto_sabe(
    doutor, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """As DUAS metades da mordida do Passo 2, no mesmo caso.

    1. **a frase não some** — a reserva continua sendo reserva, porque uma
       frase que some é pior que uma frase com um nome velho;
    2. **o produto SABE que ela é a de reserva** — e é esta metade que era o
       defeito: sem ela o `se_faltar` virava permanente e nada acusava.
    """
    _sem_fonte_nenhuma(doutor, monkeypatch, tmp_path)

    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        saiu = doutor.rotulo_do_botao(BOTAO, RESERVA_DO_BOTAO)

    assert saiu == RESERVA_DO_BOTAO, (
        "sem a fonte a frase de tela SUMIU — a reserva deixou de ser macia, e "
        "uma frase que some é pior que uma com nome velho")
    assert doutor.rotulos_de_reserva() == {BOTAO: RESERVA_DO_BOTAO}, (
        "o rótulo saiu da reserva e o produto NÃO registrou — é o silêncio que "
        "esta sprint veio matar")
    assert any(BOTAO in str(a.message) for a in avisos), (
        "nenhum aviso saiu: a reserva voltou a ser calada em runtime")


def test_o_produto_nao_publica_nenhum_rotulo_de_reserva(doutor) -> None:
    """O PORTÃO QUE FICA: rodado o produto, a lista de reserva tem de ser VAZIA.

    Este é o caso que vai para o vermelho no dia em que a `GTK-3` apagar o
    `gui/main.glade` sem dar dono novo ao rótulo — e é para isso que ele
    existe. Ele não pede o glade de volta: pede que a frase de tela nomeie um
    botão que alguém conferiu.

    O caminho exercido é o `check_snd_quirk`. Os DOIS chamadores reais de
    `rotulo_do_botao` no produto (`:477` no `check_steam_input` e `:615` aqui)
    pedem o MESMO id com a MESMA reserva, então um deles basta para a lista —
    e exercitar o outro exigiria um `localconfig.vdf` de mentira, que mediria
    a fixture, não o rótulo.
    """
    doutor.check_snd_quirk(quirk_flags_text="", conf_path=Path("/nao/existe.conf"))
    assert doutor.rotulos_de_reserva() == {}, (
        "o produto está publicando rótulo de RESERVA na tela: "
        f"{doutor.rotulos_de_reserva()}. A frase manda clicar num nome que "
        "ninguém conferiu. Dê um dono ao rótulo — o `gui/main.glade` está "
        "sendo aposentado (D-0609-GTK-LEVA-INTEIRA)")


def _laudo(doutor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """O `storm_report` com TUDO por fixture — não pergunta nada à máquina."""
    monkeypatch.setattr(doutor, "_allowlist_path", lambda: tmp_path / "vazia.txt")
    return doutor.storm_report(
        tmp_path, quirks_text="", dropin_dir=tmp_path, rules_dir=tmp_path,
        snd_quirk_text="", snd_conf_path=tmp_path / "ausente.conf",
        cards_text="", controles_no_cabo=0,
    )


#: A meia-frase pela qual a linha da reserva se reconhece no laudo.
MARCA_DA_RESERVA = "não pôde ser conferido"


@pytest.mark.skipif(not GLADE.exists(), reason="o `gui/main.glade` já saiu (GTK-3)")
def test_o_laudo_nao_ganha_linha_quando_o_rotulo_foi_lido(
    doutor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A linha da reserva é CONDICIONAL, e hoje ela não aparece.

    Uma linha a mais no exame é uma linha a mais na tela dela. Este caso é o que
    impede a cura de cobrar o preço no caminho que já estava certo.
    """
    linhas = _laudo(doutor, tmp_path, monkeypatch)
    assert not [m for _, m in linhas if MARCA_DA_RESERVA in m], (
        "o laudo ganhou a linha da reserva com o rótulo LIDO da fonte — a cura "
        "está cobrando preço de quem não devia nada")


def test_o_laudo_diz_quando_o_nome_do_botao_veio_da_reserva(
    doutor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O produto CONSOME o registro — não basta expô-lo numa função.

    É a diferença entre saber e dizer. Sem esta linha, `rotulos_de_reserva()`
    seria uma promessa pública sem chamador no produto: o portão
    `portao_a_casa_sabe_e_o_produto_nao_faz` reprova exatamente isso, e reprovou
    a primeira versão desta sprint.
    """
    _sem_fonte_nenhuma(doutor, monkeypatch, tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        linhas = _laudo(doutor, tmp_path, monkeypatch)

    da_reserva = [m for _, m in linhas if MARCA_DA_RESERVA in m]
    assert len(da_reserva) == 1, (
        "o laudo NÃO diz que citou um nome de botão que ninguém conferiu — o "
        f"produto sabe e cala. Linhas: {[m[:60] for _, m in linhas]}")
    assert RESERVA_DO_BOTAO in da_reserva[0], (
        "a linha da reserva não nomeia o rótulo em questão")


# ===========================================================================
# 3. O `i18n_extract.sh` NÃO EXTRAI MENOS EM SILÊNCIO
# ===========================================================================
def _arvore_de_extracao(tmp_path: Path, *, com_glade: bool) -> Path:
    """Uma árvore mínima onde o `i18n_extract.sh` roda de verdade.

    Mínima de propósito: o que se mede aqui é o SCRIPT, e copiar 112 MB para
    contar msgids seria pagar caro por menos medição.
    """
    arvore = tmp_path / ("com" if com_glade else "sem")
    (arvore / "scripts").mkdir(parents=True)
    pacote = arvore / "src" / "hefesto_dualsense4unix"
    (pacote / "gui").mkdir(parents=True)
    (arvore / "po").mkdir()
    shutil.copy(RAIZ / "scripts" / "i18n_extract.sh", arvore / "scripts")
    # O ACENTO NÃO É ENFEITE: sem um byte fora do ASCII o `xgettext` deixa
    # `CHARSET` no cabeçalho e o `msgcat` recusa o arquivo. A árvore de mentira
    # tem de parecer com a de verdade no que o instrumento OLHA.
    (pacote / "frases.py").write_text(
        'from gettext import gettext as _\n\nTITULO = _("Frase do Python — çã")\n',
        encoding="utf-8")
    if com_glade:
        (pacote / "gui" / "main.glade").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<interface>\n'
            '  <object class="GtkLabel" id="rotulo">\n'
            '    <property name="label" translatable="yes">Frase da Janela — çã'
            '</property>\n'
            '  </object>\n'
            '</interface>\n',
            encoding="utf-8")
    return arvore


def _extrair(arvore: Path, *argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "scripts/i18n_extract.sh", *argumentos],
        cwd=arvore, capture_output=True, text=True, timeout=120)


@pytest.mark.skipif(shutil.which("xgettext") is None,
                    reason="gettext ausente nesta máquina")
def test_com_o_glade_o_extrator_continua_o_de_sempre(tmp_path: Path) -> None:
    """A cura não pode cobrar o preço no caminho que já funcionava."""
    arvore = _arvore_de_extracao(tmp_path, com_glade=True)
    saida = _extrair(arvore)
    assert saida.returncode == 0, saida.stderr
    pot = (arvore / "po" / "hefesto-dualsense4unix.pot").read_text(encoding="utf-8")
    assert "Frase do Python" in pot and "Frase da Janela" in pot, (
        "com o glade no lugar o catálogo perdeu uma das duas fontes")
    assert not list((arvore / "po").glob("*.pot.python")), (
        "o parcial ficou para trás no `po/` — o `trap` de limpeza caiu")


@pytest.mark.skipif(shutil.which("xgettext") is None,
                    reason="gettext ausente nesta máquina")
def test_sem_o_glade_o_extrator_para_e_diz_o_que_sumiu(tmp_path: Path) -> None:
    """A MORDIDA do Passo 3: sem a fonte, o comportamento MUDA e se OUVE.

    O defeito medido em 06/09/2026 não era "extrai menos": o `xgettext` do
    passo [2/3] morria, o `set -e` levava o script junto, e o estrago era
    calado em dois lugares — o `.pot` ficava com o conteúdo ANTIGO (o catálogo
    seguia publicando as frases de uma janela que já não existe) e o parcial
    `po/*.pot.python` ficava para trás. A mensagem que se via era um
    "failed to load external entity" do gettext, que não nomeia nem a causa
    nem a decisão.
    """
    arvore = _arvore_de_extracao(tmp_path, com_glade=False)
    pot = arvore / "po" / "hefesto-dualsense4unix.pot"
    pot.write_text('msgid "o catálogo de ontem"\nmsgstr ""\n', encoding="utf-8")

    saida = _extrair(arvore)
    assert saida.returncode != 0, (
        "o extrator seguiu sem a fonte da janela — é assim que um catálogo "
        "encolhe em silêncio")
    assert "main.glade" in saida.stderr, "a recusa não nomeia o que sumiu"
    assert "D-0609-GTK-LEVA-INTEIRA" in saida.stderr, (
        "a recusa não diz POR QUE o arquivo sumiu — sem isso ela vira mais um "
        "erro de ferramenta para alguém contornar")
    assert "--sem-a-janela" in saida.stderr, "a recusa não diz como seguir"
    assert pot.read_text(encoding="utf-8") == 'msgid "o catálogo de ontem"\nmsgstr ""\n', (
        "o `.pot` foi mexido numa execução que falhou")
    assert not list((arvore / "po").glob("*.pot.python")), (
        "o parcial ficou para trás numa execução interrompida")


@pytest.mark.skipif(shutil.which("xgettext") is None,
                    reason="gettext ausente nesta máquina")
def test_a_bandeira_deixa_o_catalogo_menor_sair_por_escrito(tmp_path: Path) -> None:
    """`--sem-a-janela` é a saída, e ela DIZ o tamanho do buraco.

    Recusar sem oferecer caminho vira contorno: alguém comenta a guarda e o
    silêncio volta pela porta dos fundos.
    """
    arvore = _arvore_de_extracao(tmp_path, com_glade=False)
    saida = _extrair(arvore, "--sem-a-janela")
    assert saida.returncode == 0, saida.stderr
    assert "SEM A JANELA" in saida.stdout, (
        "o catálogo menor saiu sem dizer que é menor")
    pot = (arvore / "po" / "hefesto-dualsense4unix.pot").read_text(encoding="utf-8")
    assert "Frase do Python" in pot
