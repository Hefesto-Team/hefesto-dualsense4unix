import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import csv
import re

import onde
from monta import CONECTADOS, CSS_POPUP, cor_da_zona, monta

import desenho_da_experimental as exp

# A régua `identidade_congelada` reprova cor de aparelho cravada na página: nome de
# colorway no texto, `--plastico:`, apelido de modelo, hexadecimal do mapa.
_PROSA = re.compile(r"<!--.*?-->|/\*.*?\*/", re.S)

#: A tabela de variáveis do esqueleto; `--plastico:#fff` cai fora daqui e é acusado à parte.
_TABELA_DO_ESQUELETO = re.compile(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})")

_COM_COLORWAY = re.compile(r"<[a-zA-Z][^>]*\bdata-colorway\s*=[^>]*>")


def _mapa_das_cores() -> list[dict[str, str]]:
    """As 233 linhas de `docs/data/cores-do-dualsense.csv`: 28 modelos, 10 zonas."""
    linhas = [ln for ln in (onde.RAIZ / "docs/data/cores-do-dualsense.csv")
              .read_text(encoding="utf-8").splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    return list(csv.DictReader(linhas))


def identidade_congelada(doc: str) -> list[str]:
    """As cores de APARELHO cravadas nesta página, uma frase por achado."""
    mapa = _mapa_das_cores()
    nomes = sorted({(ln.get("nome") or "").strip() for ln in mapa} - {""})
    apelidos = sorted({(ln.get("id") or "").strip() for ln in mapa} - {""})
    tons = sorted({(ln.get("hex") or "").strip().lower() for ln in mapa} - {""})

    limpo = _PROSA.sub(lambda m: "".join(c if c == "\n" else " " for c in m.group(0)), doc)
    achados: list[str] = []

    vaos: list[tuple[int, int]] = []
    for m in _TABELA_DO_ESQUELETO.finditer(limpo):
        apelido, tom = m.group(1), m.group(2)
        if apelido not in apelidos:
            continue
        vaos.append(m.span())
        do_mapa = cor_da_zona(apelido) or ""
        if tom.lower() != do_mapa.lower():
            achados.append(
                f"a página traz `--{apelido}:{tom}` e o mapa dela diz "
                f"`{do_mapa or 'nada'}`. As cinco variáveis de plástico do "
                f"esqueleto são REESCRITAS por `monta.cor_da_zona`; um valor "
                f"que diverge é hexadecimal digitado à mão, não leitura do CSV.")

    def _fora_da_tabela(i: int) -> bool:
        return not any(a <= i < b for a, b in vaos)

    achados += [f"nome de colorway na página: {nome!r}. A identidade do controle "
                f"vem da FITA, que lê do APARELHO — um nome de modelo escrito "
                f"aqui é o desenho mandando na tela do produto."
                for nome in nomes if len(nome) >= 4 and nome in limpo]

    if re.search(r"--plastico\s*:", limpo):
        achados.append(
            "voltou um `--plastico:` cravado à página. A cor do plástico é "
            "leitura de aparelho — quem a escreve é o pacote, nunca o gerador.")

    for apelido in apelidos:
        agulha = rf"(?<![A-Za-z0-9_-]){re.escape(apelido)}(?![A-Za-z0-9_-])"
        achados += [f"apelido de modelo do mapa na página: {apelido!r}. É o que "
                    f"vai num `data-colorway` ou numa classe, e a régua por NOME "
                    f"não o enxerga — nenhum 'Cosmic Red' aparece num "
                    f"`data-colorway=\"cosmic-red\"`."
                    for m in re.finditer(agulha, limpo) if _fora_da_tabela(m.start())]

    achados += [f"a página usa `var(--{apelido})`. Aquelas cinco são a paleta do "
                f"DESENHO, congelada no esqueleto: elas respondem por 5 dos 28 "
                f"modelos do mapa, e quem tiver o sexto vê a cor de outro "
                f"aparelho. A cor do controle DELA vem do pacote, no tique."
                for apelido in apelidos if f"var(--{apelido})" in limpo]

    for tom in tons:
        achados += [f"hexadecimal do mapa cravado na página: {tom}. Ele não tem "
                    f"nome nem `--plastico:` e por isso atravessa as duas réguas "
                    f"que já havia — e é a cor de um modelo que pode não ser o "
                    f"dela."
                    for m in re.finditer(re.escape(tom), limpo, re.I)
                    if _fora_da_tabela(m.start())]

    achados += [f"`data-colorway` sem endereço em {' '.join(m.group(0).split())[:90]!r}. "
                f"O contrato é `data-hef-alvo=\"atributo\"` com "
                f"`data-hef-atributo=\"data-colorway\"` no mesmo elemento; sem "
                f"eles o SVG fica com o colorway do desenho para sempre."
                for m in _COM_COLORWAY.finditer(limpo)
                if 'data-hef-alvo="atributo"' not in m.group(0)
                or 'data-hef-atributo="data-colorway"' not in m.group(0)]

    return achados


if "--conferir" in sys.argv:
    _ALVO = pathlib.Path(sys.argv[sys.argv.index("--conferir") + 1])
    _PROBLEMAS = identidade_congelada(_ALVO.read_text(encoding="utf-8"))
    for _p in _PROBLEMAS:
        print(f"ERRO: {_p}", file=sys.stderr)
    print(f"{_ALVO.name}: {len(_PROBLEMAS)} cor(es) de aparelho cravada(s)")
    raise SystemExit(1 if _PROBLEMAS else 0)


N_CTRL = len(CONECTADOS)
N_USB = sum(1 for c in CONECTADOS if c["via"] == "USB")
N_BT = sum(1 for c in CONECTADOS if c["via"] == "BT")

CSS = CSS_POPUP + exp.CSS
MIOLO = exp.miolo()

_TIRA = '<a class="aba ativa" href="07-lancadores.html">Experimental</a>'
_CHIP_DE_CONTROLE = re.compile(r'^[ \t]*<label class="chip plastico(?: on)?"[^\n]*\n', re.M)
_MARCA = "<!-- ===== fim da aba ===== -->"


def _sem_os_tres(fila: str) -> bool:
    """Os três botões à vista, e cada aceso com o seu gesto (o apagado não leva nenhum)."""
    botoes = re.findall(r'<(?:a|button|span) class="btn mini( apagado)?"([^>]*)>', fila)
    return len(botoes) != len(exp.BOTOES) or any(
        not apagado and 'data-gesto="' not in resto for apagado, resto in botoes)


def _confere_a_forma() -> None:
    """Trava de geração: o que a régua do mockup também afirma, dita antes de gravar."""
    # 19/10/2026: Steam, Heroic e Flatpak de fábrica, o Lutris como extensão instalada e uma
    # linha de migração (o lançador que virou extensão, sem os botões, com o endereço).
    if len(exp.LANCADORES) != 5 or sum(1 for f in exp.LANCADORES if f.virou) != 1:
        raise SystemExit(f"ERRO: {len(exp.LANCADORES)} lançadores, e o desenho tem cinco, "
                         "um deles a linha do que virou extensão.")
    sem_trio = [f.chave for f in exp.LANCADORES if not f.virou and _sem_os_tres(exp.fila_html(f))]
    if sem_trio:
        raise SystemExit(f"ERRO: lançador sem os {len(exp.BOTOES)} botões: {sem_trio}")
    if "class=\"ajuda" in MIOLO + exp.telas():
        raise SystemExit("ERRO: um `span.ajuda` voltou; a dica mora em `data-dica`.")


_confere_a_forma()


#: O ⋮ de cada linha de extensão; o do «Configurar» já traz o menu dele ao lado e fica de fora.
_O_MAIS = re.compile(
    r'(<button class="ext-mais"[^>]*data-v="([^"]+)"[^>]*>\u22ee</button>)(?!<div class="ext-menu)')


def _menu_do_mais(html, classe):
    """O menu do ⋮ de cada extensão, já desenhado (o produto o monta ao clique): `classe` o põe."""
    novo, quantas = _O_MAIS.subn(
        lambda m: (f'{m.group(1)}\n            <div class="ext-menu {classe}" '
                   f'data-menu="{m.group(2)}">{exp.menu_html(m.group(2))}</div>'), html)
    if quantas != len(exp.EXTENSOES):
        raise SystemExit(f"ERRO: achei {quantas} «⋮» e são {len(exp.EXTENSOES)} extensões")
    return novo


if __name__ == "__main__":
    import os
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-07-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    n = monta("07-lancadores", exp.ROTULO_DA_TIRA, MIOLO, CSS)

    _DOC = onde.pagina("07-lancadores.html").read_text()
    if _MARCA not in _DOC or _TIRA not in _DOC:
        raise SystemExit(
            "ERRO: a marca do fim da aba ou a tira mudou no `fim.html` ou no `monta.py`; "
            "sem elas as janelas não entram e o clique em «Configurar» abre nada.")
    _DOC = _DOC.replace(_MARCA, exp.telas().strip() + "\n\n" + _MARCA, 1)

    _CONGELADOS = _CHIP_DE_CONTROLE.findall(_DOC)
    if not _CONGELADOS:
        raise SystemExit(
            "ERRO: não achei um único `<label class=\"chip plastico\">` na página "
            "recém-gerada. Ou `monta.fita()` mudou de forma, ou a fita saiu vazia, "
            "e esta troca ficaria verde sem fazer nada.")
    _DOC = _CHIP_DE_CONTROLE.sub("", _DOC)
    _DOC = _menu_do_mais(_DOC, "ext-pop")
    onde.gravar("07-lancadores.html", _DOC)

    _CRAVADAS = identidade_congelada(_DOC)
    if _CRAVADAS:
        raise SystemExit("ERRO: " + "\nERRO: ".join(_CRAVADAS))

    _MODELOS = sorted({(ln.get("id") or "").strip() for ln in _mapa_das_cores()} - {""})
    print(f"07-lancadores: OK, {n} divs · mesa {N_CTRL} ({N_USB} USB/{N_BT} BT) · "
          f"{len(exp.LANCADORES)} lançadores, {len(exp.EXTENSOES)} extensões, "
          f"{len(exp.JANELAS)} janelas · {len(_CONGELADOS)} chip(s) do desenho fora da fita, "
          f"0 dos {len(_MODELOS)} modelos do mapa cravados na página")
    shutil.copyfile(_prova / "07-lancadores.html", _real / "07-lancadores.html")
    shutil.rmtree(_prova)
