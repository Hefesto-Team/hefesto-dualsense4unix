"""A MESA DE MEDIÇÃO — as réguas que a provam, e cada uma MORDE.

A queixa dela, de 06/09/2026, é o que decide o que se mede aqui, e ela está
transcrita em `docs/process/agentes/2026-09-06/A-VALIDACAO-DOS-QUATRO-01-entrada/
ESPEC-A-VALIDACAO.md`: a sessão de quem estava na bancada acabava e levava embora não só o
resultado como **o modo de chegar nele**.

Logo a régua mais importante deste arquivo não é a que confere que a página
abre — é a que confere que **o COMO é gravado**, e que gravar sem ele é
recusado. Uma página que salva "passou" e esquece o gesto reproduz o defeito
com um arquivo a mais.

AS MORDIDAS, uma por afirmação, e todas foram vistas reprovar antes de entrar:

* mude uma linha do mapa e os testes mudam — se não mudarem, alguém copiou a
  lista à mão, que é o defeito que a especificação proíbe;
* troque a coluna `peca` e o realce muda de lugar;
* arranque o campo do "como" e a gravação é recusada;
* tire um `.marcada` do seletor e a especificidade cai abaixo da folha das
  zonas — que foi o defeito REAL medido no Chrome nesta leva;
* tire o `class=` fundido e a peça marcada perde a zona de plástico.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

import mesa_de_medicao as med
import monta

CHROME = "/usr/bin/google-chrome"

#: O SUFIXO É INVENTADO, e o endereço só vira "forma de MAC" quando colado ao
#: OUI real EM TEMPO DE EXECUÇÃO. Escrever o endereço inteiro num literal faria
#: os dois portões de anonimato reprovarem este arquivo — e os dois estariam
#: certos. É o mesmo arranjo de `tests/unit/test_bateria_no_journal.py`, e ele
#: existe justamente porque provar a máscara EXIGE um endereço sem máscara.
_SUFIXO_DE_FIXTURE = ("c3", "1a", "f7")


def _endereco_sem_mascara(ultimo: str = "f7") -> str:
    """Um endereço com OUI real desta bancada, montado na hora.

    O OUI REAL importa: é ele que os dois portões reconhecem, e é contra os
    portões que a mordida da máscara é medida.
    """
    from tests.unit.test_docs_mac_anonimato import _OUIS_REAIS_OCTETOS

    return ":".join([*_OUIS_REAIS_OCTETOS[0], _SUFIXO_DE_FIXTURE[0],
                     _SUFIXO_DE_FIXTURE[1], ultimo])


# ---------------------------------------------------------------------------
# Os testes SAEM DOS ARQUIVOS
# ---------------------------------------------------------------------------
def test_a_regua_acha_o_que_medir() -> None:
    """Régua que não acha nada dá verde sobre o vazio."""
    testes = med.todos_os_testes()
    assert len(testes) > 100, f"só {len(testes)} testes — a leitura quebrou"
    assert len({t.id for t in testes}) == len(testes), "id repetido na mesa"
    assert len({t.secao for t in testes}) > 5, "as seções colapsaram numa só"


def test_as_vinte_e_uma_linhas_do_roteiro_estao_todas() -> None:
    """As 21 linhas da §2, e as 13-21 são a ACEITAÇÃO DO PRODUTO."""
    do_roteiro = [t for t in med.todos_os_testes() if t.id.startswith("roteiro-")]
    assert len(do_roteiro) == 21, [t.id for t in do_roteiro]
    assert do_roteiro[0].id == "roteiro-01" and do_roteiro[-1].id == "roteiro-21"


def test_o_roteiro_vem_primeiro() -> None:
    """A hora dela com os quatro controles é a aceitação, e ela tem 60 min."""
    testes = med.todos_os_testes()
    assert all(t.id.startswith("roteiro-") for t in testes[:21])


def _mapa_de_mentira(tmp: pathlib.Path, troca) -> pathlib.Path:
    """Uma cópia do mapa com UMA linha mexida. É o instrumento das mordidas."""
    destino = tmp / "mapa-controles.csv"
    linhas = med.MAPA.read_text(encoding="utf-8").splitlines(keepends=True)
    destino.write_text("".join(troca(linha) for linha in linhas), encoding="utf-8")
    return destino


def test_mordida_mude_o_mapa_e_a_mesa_muda(tmp_path, monkeypatch) -> None:
    """A mordida da especificação §7.1: *mude uma linha do mapa e a página muda;
    se não mudar, ela copiou.*

    A troca é cirúrgica: uma célula que hoje entra na mesa por ter grau fraco
    passa a `O APARELHO OBEDECEU`, e o teste dela tem de SUMIR. Se a lista
    estivesse escrita à mão, ela continuaria lá.
    """
    antes = {t.id for t in med.todos_os_testes()}
    alvo = next(t for t in med.todos_os_testes() if t.id.startswith("mapa-"))
    chave = alvo.id[len("mapa-"):].rsplit("-", 1)[0]

    def promove(linha: str) -> str:
        if not linha.startswith(chave + ","):
            return linha
        campos = next(__import__("csv").reader([linha]))
        cabecalho = next(__import__("csv").reader(
            [med.MAPA.read_text(encoding="utf-8").splitlines()[0]]))
        d = dict(zip(cabecalho, campos, strict=False))
        d["cabo_ate_onde_foi"] = d["radio_ate_onde_foi"] = "O APARELHO OBEDECEU"
        d["cabo_por_que_nao_aciona"] = d["radio_por_que_nao_aciona"] = ""
        # E A PROCEDÊNCIA JUNTO: desde 07/09/2026 é `de_onde_sei` que decide o
        # selo, não o degrau — `ate_onde_foi` está vazio em 115 das 195 células
        # desta árvore, inclusive em muitas que dizem `medido`.
        d["cabo_de_onde_sei"] = d["radio_de_onde_sei"] = "medido"
        saida = __import__("io").StringIO()
        __import__("csv").writer(saida, lineterminator="\n").writerow(
            [d[c] for c in cabecalho])
        return saida.getvalue()

    monkeypatch.setattr(med, "MAPA", _mapa_de_mentira(tmp_path, promove))
    novos = med.todos_os_testes()
    depois = {t.id for t in novos}
    falta_depois = {t.id for t in novos if not t.ja_medido}
    assert antes != falta_depois, (
        "promovi uma célula a medida no mapa e a fila do que falta não mudou — "
        "a lista de testes não está saindo do arquivo.")
    # ELA SAI DA FILA E ENTRA NA OUTRA FAMÍLIA — 07/09/2026. Até aqui a régua
    # cobrava que a célula promovida SUMISSE, e sumir era o comportamento: a
    # mesa só listava o que faltava. Ela pediu o contrário — *"a grande maioria
    # ali já foi validada uns 80%"* —, e agora a célula medida continua na
    # página, com selo e com a resposta do mapa pré-marcada, para ela confirmar
    # de relance em vez de refazer.
    assert alvo.id not in falta_depois, (
        f"{alvo.id} continua na fila do que falta depois de ser promovido")
    assert alvo.id in depois, (
        f"{alvo.id} sumiu da página inteira — o promovido deve migrar de "
        f"família, não desaparecer")
    promovido = next(t for t in novos if t.id == alvo.id)
    assert promovido.ja_medido, "o promovido veio sem selo"
    assert "medido" in promovido.ja_medido


def test_mordida_troque_a_peca_e_o_realce_muda_de_lugar(tmp_path, monkeypatch) -> None:
    """A mordida da especificação §7.7: *troque a `peca` da linha no mapa e veja
    o brilho mudar de lugar.*"""
    alvo = next(t for t in med.todos_os_testes()
                if t.id.startswith("mapa-") and t.pecas)
    chave = alvo.id[len("mapa-"):].rsplit("-", 1)[0]
    original = [p for p, _ in alvo.pecas]
    assert "touchpad" not in original

    import csv as _csv
    import io as _io
    cabecalho = next(_csv.reader([med.MAPA.read_text(encoding="utf-8").splitlines()[0]]))

    def troca_peca(linha: str) -> str:
        if not linha.startswith(chave + ","):
            return linha
        d = dict(zip(cabecalho, next(_csv.reader([linha])), strict=False))
        d["peca"] = "touchpad"
        saida = _io.StringIO()
        _csv.writer(saida, lineterminator="\n").writerow([d[c] for c in cabecalho])
        return saida.getvalue()

    monkeypatch.setattr(med, "MAPA", _mapa_de_mentira(tmp_path, troca_peca))
    agora = next(t for t in med.todos_os_testes() if t.id == alvo.id)
    assert [p for p, _ in agora.pecas] == ["touchpad"], agora.pecas

    marcados = re.findall(
        r'<g id="p1-([^"]+)" class="[^"]*marcada',
        monta.svg("p1", "cosmic-red", apertados=tuple(p for p, _ in agora.pecas),
                  folha=False))
    assert marcados == ["touchpad"], marcados


def test_a_peca_de_um_teste_do_roteiro_declara_a_palavra_que_a_achou() -> None:
    """Realce sem procedência é realce que ninguém pode contestar."""
    com_peca = [t for t in med.todos_os_testes()
                if t.id.startswith("roteiro-") and t.pecas]
    assert com_peca, "nenhuma linha do roteiro achou peça — o vocabulário quebrou"
    for t in com_peca:
        for pid, palavra in t.pecas:
            assert palavra and len(palavra) >= 3, (t.id, pid, palavra)


def test_o_vocabulario_das_pecas_vem_do_csv_e_nao_e_generico() -> None:
    """A afirmação da docstring, remedida: cada palavra identifica no máximo
    quatro peças — e as de quatro são o D-pad."""
    vocab = med.vocabulario_das_pecas()
    assert len(vocab) > 30, len(vocab)
    demais = {k: sorted(v) for k, v in vocab.items() if len(v) > 4}
    assert not demais, demais


def test_os_papeis_saem_da_condicao_que_ela_escreveu() -> None:
    """*Um teste em que os quatro brilham igual não diz nada.*

    E DESDE 07/09/2026 O PAPEL SAI DA CONDIÇÃO, não da citação do posto no
    enunciado — dela: *"cada controle sirva para testarmos variações daquilo e
    o esperado (…) Controle A, não liga, o b cor azul"*. A régua antes exigia
    que a linha 6 (a vibração) tivesse os QUATRO em `observa`, porque o
    enunciado não citava posto nenhum; hoje a coluna diz *"P1: é ESTE que deve
    tremer · P2: não pode tremer …"*, e os quatro deixaram de brilhar igual —
    que é o que a própria docstring pedia.
    """
    sete = next(t for t in med.todos_os_testes() if t.id == "roteiro-07")
    assert sete.papeis["P3"] == med.PAPEL_REAGE, sete.papeis
    assert {sete.papeis[p] for p in ("P1", "P2", "P4")} == {med.PAPEL_CALADO}

    seis = next(t for t in med.todos_os_testes() if t.id == "roteiro-06")
    assert seis.papeis["P1"] == med.PAPEL_REAGE, seis.papeis
    assert {seis.papeis[p] for p in ("P2", "P3", "P4")} == {med.PAPEL_CALADO}

    # NENHUMA DAS 21 SAI COM OS QUATRO IGUAIS SEM QUE A COLUNA MANDE: um teste
    # assim não separa nada, e é o defeito que esta régua existe para pegar.
    # O QUE TEM DE SER DISTINTO É A CONDIÇÃO, NÃO O PAPEL — e a primeira volta
    # desta régua errou nisso. A linha 1 diz *"P1: liga PRIMEIRO · P2: liga
    # SEGUNDO · P3: liga TERCEIRO · P4: liga POR ÚLTIMO"*: quatro condições
    # diferentes, e os quatro DEVEM reagir, porque os quatro têm de aparecer.
    # Exigir papéis diferentes ali seria pedir que um dos controles falhasse.
    for teste in med.todos_os_testes():
        if not teste.id.startswith("roteiro-"):
            continue
        assert len(teste.condicoes) == 4, f"{teste.id}: {teste.condicoes}"
        assert len(set(teste.condicoes.values())) > 1 or teste.um_por_vez, (
            f"{teste.id} manda os quatro fazerem exatamente a mesma coisa e "
            f"não é um-por-vez — não há variação a medir: {teste.condicoes}")


def test_a_condicao_de_cada_controle_vem_da_coluna_do_roteiro() -> None:
    """A coluna *"o que cada controle faz"* chega inteira aos quatro postos.

    MORDIDA JUNTO: uma tabela sem a coluna (as quatro colunas de antes de
    07/09/2026) continua sendo lida, com a condição vazia — uma régua que
    exigisse cinco derrubaria a mesa no dia em que alguém editasse a tabela sem
    saber da coluna nova.
    """
    das_21 = [t for t in med.todos_os_testes() if t.id.startswith("roteiro-")]
    assert len(das_21) == 21, len(das_21)
    assert all(len(t.condicoes) == 4 for t in das_21), (
        [t.id for t in das_21 if len(t.condicoes) != 4])
    oito = next(t for t in das_21 if t.id == "roteiro-08")
    assert "VERMELHO" in oito.condicoes["P1"], oito.condicoes
    assert "AZUL" in oito.condicoes["P2"], oito.condicoes
    assert oito.condicoes["P1"] != oito.condicoes["P2"] != oito.condicoes["P3"]

    de_quatro = med.linhas_do_roteiro.__doc__ or ""
    assert "duas larguras" in de_quatro, (
        "a leitura deixou de declarar que aceita a tabela de quatro colunas")


def test_o_timer_conta_o_que_a_linha_nomeia() -> None:
    """Um teste de 20 minutos mostra os 20 minutos."""
    vinte = next(t for t in med.todos_os_testes() if t.id == "roteiro-10")
    assert vinte.segundos == 20 * 60, vinte.segundos
    assert med.segundos_do_texto("nada aqui") == med.SEGUNDOS_PADRAO


# ---------------------------------------------------------------------------
# O COMO — o ponto inteiro
# ---------------------------------------------------------------------------
def test_o_como_do_arquivo_vem_do_mapa() -> None:
    """O comando, o report, o offset e o canal já estão no CSV. Ninguém digita
    de novo o que o arquivo publica."""
    com_como = [t for t in med.todos_os_testes()
                if t.id.startswith("mapa-") and t.como]
    assert len(com_como) > 20, len(com_como)
    # O CANAL E O COMANDO MUDARAM DE LUGAR EM 07/09/2026, e a régua vai atrás
    # deles onde eles estão. Eles nunca foram GESTO — são de onde a casa sabe —,
    # e ocupavam o campo do "como" enquanto ninguém tinha escrito o gesto de
    # verdade. Hoje o gesto vem do arquivo dono e a procedência desceu para a
    # gaveta, junto do `aciona` e do degrau. O que a régua não pode deixar
    # acontecer é ela SUMIR: sem o comando e o canal, quem for conferir a
    # medição amanhã não sabe por onde a casa falou com o aparelho.
    onde_vive = " ".join(t.hoje for t in com_como)
    assert "canal=" in onde_vive and "comando=" in onde_vive, (
        "o canal e o comando sumiram da procedência das células")
    chaves = {k for t in com_como for k, _ in t.como}
    assert "os passos" in chaves, (
        f"as células do mapa perderam o gesto: {sorted(chaves)}")


def test_mordida_gravar_sem_o_como_e_recusado(tmp_path) -> None:
    """Arranque a gravação do gesto e veja a régua reprovar (§7.9).

    Este é o teste que sustenta a razão de a página existir. Se ele passar a
    aceitar o silêncio, a mesa volta a produzir "passou" sem o como — que é
    exatamente o que se perdia quando a sessão morria.
    """
    r = med.Registro(tmp_path)
    # A RÉGUA LÊ O QUE IMPORTA, não a frase inteira: o motivo mudou em
    # 07/09/2026 — o COMO deixou de ser cobrado DELA e passa a vir do
    # arquivo —, e a recusa continua de pé para a linha que chega sem COMO
    # NENHUM. Cravar o texto fazia a régua reprovar a correção, não o defeito.
    with pytest.raises(ValueError, match="COMO"):
        r.gravar({"teste": "x", "respostas": {"P1": "obedeceu"}})
    with pytest.raises(ValueError):
        r.gravar({"teste": "x", "gesto": "   ", "respostas": {}})
    assert not list(tmp_path.glob("registro-*.jsonl")), (
        "recusou e mesmo assim escreveu no disco")


def test_o_registro_grava_o_como_e_sobrevive_ao_processo(tmp_path) -> None:
    """Uma resposta gravada sobrevive a recarregar — e está EM DISCO (§7.5)."""
    r = med.Registro(tmp_path)
    linha = r.gravar({
        "teste": "roteiro-07", "titulo": "Gatilhos", "secao": "O roteiro",
        "celula": "linha 7", "respostas": {"P3": "obedeceu", "P1": "nada"},
        "o_que_eu_vi": "só o P3 mudou",
        "gesto": "aba 03 > efeito Arma no P3; report 0x02 offset 11 (backend_pydualsense.py)",
        "como_do_arquivo": [["canal", "hidraw"]],
        "mesa": {"postos": {"P1": {"uniq": _endereco_sem_mascara()}}},
        "veredito": med.veredito({"P3": "obedeceu", "P1": "nada"}),
    })
    assert linha["gesto"]
    fita = (tmp_path / f"registro-{__import__('datetime').date.today().isoformat()}.jsonl")
    bruto = fita.read_text(encoding="utf-8")
    assert "report 0x02" in bruto, "o COMO não chegou ao disco"
    # OUTRO processo lê o mesmo disco: é isto que faz a medição sobreviver à
    # sessão que morre.
    outro = med.Registro(tmp_path).ler()
    assert outro["roteiro-07"]["gesto"] == linha["gesto"]
    assert outro["roteiro-07"]["veredito"] == "obedeceu"


def test_o_endereco_sai_mascarado_mesmo_vindo_do_navegador(tmp_path) -> None:
    """MAC mascarado sempre — octetos 4 e 5 zerados. O que chega de fora não é
    de confiança, e por isso a máscara é aplicada DE NOVO na gravação."""
    from tests.unit.test_docs_mac_anonimato import _OUIS_REAIS_OCTETOS

    cru = _endereco_sem_mascara("be")
    linha = med.Registro(tmp_path).gravar({
        "teste": "x", "gesto": "nada", "respostas": {},
        "mesa": {"postos": {"P1": {"uniq": cru}}},
    })
    octetos = linha["mesa"]["postos"]["P1"]["uniq"].split(":")
    assert octetos[3] == "00" and octetos[4] == "00", octetos
    # o que a análise precisa sobrevive: o fabricante e o último octeto
    assert octetos[:3] == list(_OUIS_REAIS_OCTETOS[0]) and octetos[5] == "be"
    assert ":".join(_SUFIXO_DE_FIXTURE[:2]) not in json.dumps(linha)


def test_o_veredito_nao_julga_o_papel() -> None:
    """Uma resposta `obedeceu` num controle que devia ficar calado é um ACHADO;
    virar "falhou" sozinho esconderia a linha que interessa."""
    assert med.veredito({}) == "não feito"
    assert med.veredito({"P1": "obedeceu", "P2": "nada"}) == "obedeceu"
    assert med.veredito({"P1": "outra-coisa"}) == "parcial"
    assert med.veredito({"P1": "nao-vi", "P2": "nao-vi"}) == "não feito"


# ---------------------------------------------------------------------------
# O desenho, a cor e o realce
# ---------------------------------------------------------------------------
def test_mordida_apertados_recusa_quando_a_ancora_some() -> None:
    """`str.replace` que não casa devolve o texto intacto sem avisar. Aqui a
    ausência PARA a geração."""
    with pytest.raises(SystemExit, match="não é um"):
        monta.svg("p1", "cosmic-red", apertados=("alto_falante",))
    with pytest.raises(SystemExit):
        monta.svg("p1", "cosmic-red", apertados=("peca-que-nao-existe",))


def test_mordida_a_peca_marcada_nao_perde_a_zona_de_plastico() -> None:
    """O DEFEITO MEDIDO em 06/09/2026: a classe entrava como um SEGUNDO atributo
    `class`, o navegador ignorava o segundo, e a peça marcada perdia a zona.

    Com um Nova Pink na mesa o R1 pintava `rgb(227,91,140)` e o L2 marcado caía
    no `#3a3f4b` cru do desenho — a peça em foco era a única sem a cor do
    aparelho dela.
    """
    x = monta.svg("p3", "nova-pink", apertados=("l2",), folha=False)
    i = x.index('id="p3-l2"')
    tag = x[x.rindex("<", 0, i):x.index(">", i)]
    assert tag.count("class=") == 1, f"dois atributos class: {tag[:160]}"
    classes = re.search(r'class="([^"]*)"', tag).group(1).split()
    assert "marcada" in classes and "z-gatilhos" in classes, classes


#: Os nomes de elemento que aparecem nos seletores destas duas folhas.
_ELEMENTOS = ("svg", "g", "path", "rect", "circle", "ellipse", "polygon",
              "line", "polyline")


def _especificidade(seletor: str) -> tuple[int, int, int]:
    """(id, classe, elemento) de um seletor, contado como o navegador conta.

    As duas regras que decidem esta conta, e a primeira já me enganou uma vez
    nesta leva: **`:is(a,b)` vale o MAIS ESPECÍFICO dos argumentos** e
    **`:not(X)` vale exatamente X** — o `:not` não acrescenta nada por si. A
    primeira versão desta função somava um ponto de classe pelo `:not(` E outro
    pelo `[fill="none"]` de dentro dele, e por isso dava à folha das zonas um
    ponto que ela não tem.

    Nos dois seletores em jogo todos os argumentos de `:is()` são nomes de
    elemento, então a redução é literal: troca-se o `:is(…)` por UM elemento e
    o `:not(X)` por X.
    """
    achatado = re.sub(r":is\([^)]*\)", " path", seletor)
    achatado = re.sub(r":not\(([^)]*)\)", r"\1", achatado)
    ids = len(re.findall(r"#[\w-]+", achatado))
    classes = (len(re.findall(r"\.[\w-]+", achatado))
               + len(re.findall(r"\[[^\]]+\]", achatado)))
    sem_atributo = re.sub(r"\[[^\]]*\]", " ", achatado)
    elementos = sum(
        len(re.findall(rf"(?<![.#\w-]){nome}(?![\w-])", sem_atributo))
        for nome in _ELEMENTOS)
    return ids, classes, elementos


def test_mordida_o_realce_vence_a_folha_das_zonas() -> None:
    """A conta que a versão anterior desta regra perdia por um ponto.

    Sem o `.marcada` repetido a regra dá (0,2,3) e a folha das zonas dá (0,3,2):
    o realce simplesmente NÃO APARECIA nas peças pintadas — que são quase todas.
    Medido no Chrome antes de virar teste.
    """
    realce = monta.folha_de_realce().splitlines()[0].split("{")[0].strip()
    zona = ('svg[data-colorway="nova-pink"] .z-gatilhos '
            ':is(path,rect,circle,ellipse,polygon):not([fill="none"])')
    assert _especificidade(realce) > _especificidade(zona), (
        f"{realce} = {_especificidade(realce)} não vence "
        f"{_especificidade(zona)} — o realce fica invisível na peça pintada")
    assert "!important" in monta.folha_de_realce(), (
        "sem `!important` o `style` inline do desenho vence a folha")


def test_a_folha_publicada_tem_os_vinte_e_oito_modelos() -> None:
    """*Uma folha podada é uma escolha cravada*, e há portão que a conta como
    dívida (`check_a_cor_vem_do_aparelho.py`). A página publica a tabela DELA."""
    folha = monta.folha_das_cores()
    declarados = set(re.findall(r'svg\[data-colorway="([^"]+)"\]', folha))
    do_csv = {
        (linha.get("id") or "").strip()
        for linha in __import__("csv").DictReader(
            __import__("io").StringIO("\n".join(med._sem_comentario(med.CORES))))
        if (linha.get("id") or "").strip()
    }
    assert declarados == do_csv, do_csv ^ declarados
    assert len(do_csv) == 28, len(do_csv)


def test_o_desenho_de_cada_posto_nao_carrega_a_folha_podada() -> None:
    """Quatro cópias dos 28 seriam 180 KB de CSS que ninguém lê; uma cópia
    podada por desenho seria a escolha cravada que o portão conta."""
    x = monta.svg("p1", "cosmic-red", folha=False)
    assert "cores-do-dualsense-folha" not in x
    assert 'data-colorway="cosmic-red"' in x, (
        "sem o atributo a folha de cima não alcança este desenho")


def test_os_quatro_desenhos_nao_colidem_de_id() -> None:
    """O `pref` é o que permite quatro na mesma página."""
    teste = next(t for t in med.todos_os_testes() if t.pecas)
    mesa = {"postos": {p: {"colorway": "cosmic-red", "lampada": i}
                       for i, p in enumerate(med.POSTOS, 1)}}
    quatro = med.desenhos(teste, mesa)
    assert set(quatro) == set(med.POSTOS)
    for posto in med.POSTOS:
        assert f'id="{posto.lower()}-corpo"' in quatro[posto]
    for pid, _ in teste.pecas:
        assert all(f'id="{p.lower()}-{pid}"' in quatro[p] for p in med.POSTOS)


def test_sem_modelo_publicado_o_desenho_nao_escolhe_um_colorway() -> None:
    """*Sem modelo publicado, travessão — nunca um colorway escolhido.* Escolher
    um seria a tela afirmando um aparelho que ninguém leu."""
    teste = med.todos_os_testes()[0]
    quatro = med.desenhos(teste, {"postos": {}})
    assert all('data-colorway=""' in s for s in quatro.values())


# ---------------------------------------------------------------------------
# O servidor
# ---------------------------------------------------------------------------
@pytest.fixture()
def mesa_no_ar(tmp_path, monkeypatch):
    """Sobe o servidor numa porta livre, com o registro num lar de mentira."""
    monkeypatch.setattr(med, "pasta_do_registro", lambda: tmp_path)
    httpd, url = med.servir(0)
    fio = threading.Thread(target=httpd.serve_forever, daemon=True)
    fio.start()
    try:
        yield url
    finally:
        httpd.shutdown()
        httpd.server_close()


def _pega(url: str) -> str:
    from urllib.request import urlopen
    return urlopen(url, timeout=10).read().decode("utf-8")


def test_a_pagina_sobe_e_traz_os_testes_e_o_indice(mesa_no_ar) -> None:
    corpo = _pega(mesa_no_ar)
    assert "window.__TESTES__" in corpo
    assert 'id="indice"' in corpo and 'id="iniciar"' in corpo
    assert "g.marcada" in corpo, "a folha de realce não foi publicada"
    assert corpo.count('svg[data-colorway="') > 28, "a folha dos 28 não subiu"


def test_o_servidor_recusa_a_gravacao_sem_o_como(mesa_no_ar) -> None:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
    pedido = Request(
        mesa_no_ar + "registro",
        data=json.dumps({"teste": "x", "respostas": {}}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with pytest.raises(HTTPError) as erro:
        urlopen(pedido, timeout=10)
    assert erro.value.code == 400
    assert "COMO" in erro.value.read().decode("utf-8")


def test_o_endpoint_dos_desenhos_traz_quatro_e_a_peca_acesa(mesa_no_ar) -> None:
    from urllib.parse import quote
    teste = next(t for t in med.todos_os_testes() if t.pecas)
    corpo = _pega(mesa_no_ar + "desenhos?teste=" + quote(teste.id))
    assert corpo.count('class="ctl') == 4
    assert corpo.count("marcada") == 4 * len(teste.pecas)
    for posto in med.POSTOS:
        assert f'name="r-{posto}"' in corpo, "faltam as respostas por controle"


def test_o_servidor_so_atende_o_proprio_computador() -> None:
    """`127.0.0.1`, nunca `0.0.0.0`: esta página mostra o endereço dos controles
    dela e o que a bancada mediu."""
    httpd, url = med.servir(0)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
        assert url.startswith("http://127.0.0.1:")
    finally:
        httpd.server_close()


def test_o_validar_sh_existe_e_tem_o_sem_abrir() -> None:
    """A janela é DELA; a régua usa `--sem-abrir`."""
    sh = RAIZ / "validar.sh"
    assert sh.exists() and os.access(sh, os.X_OK)
    fonte = sh.read_text(encoding="utf-8")
    assert "--sem-abrir" in fonte
    for proibido in ("install.sh", "systemctl", "pkill"):
        assert proibido not in fonte.replace(
            "`pkill -f` já derrubou o", ""), (
            f"o lançador da mesa não pode tocar em {proibido}")


@pytest.mark.skipif(not shutil.which("shellcheck"), reason="sem shellcheck")
def test_o_lancador_passa_no_shellcheck() -> None:
    """O `portoes.sh` varre `scripts/*.sh`; o `validar.sh` mora na RAIZ, e sem
    esta linha ele ficaria fora de toda régua de shell da casa."""
    r = subprocess.run(["shellcheck", "-S", "error", str(RAIZ / "validar.sh")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# A PROVA COM O NAVEGADOR — os três tempos, clicados
# ---------------------------------------------------------------------------
@pytest.fixture()
def mentira(tmp_path):
    """Quatro modelos DIFERENTES, pela porta declarada da régua.

    Sem colorway não há folha de zonas a vencer, e a prova que interessa — *o
    realce vence a cor do plástico* — não existiria.
    """
    arq = tmp_path / "mentira.json"
    modelos = [("P1", "cosmic-red", "Cosmic Red", "USB"),
               ("P2", "starlight-blue", "Starlight Blue", "USB"),
               ("P3", "nova-pink", "Nova Pink", "BT"),
               ("P4", "midnight-black", "Midnight Black", "BT")]
    arq.write_text(json.dumps({"daemon": "", "quando": "", "postos": {
        p: {"posto": p, "presente": True, "nome": n, "modelo": n,
            "colorway": s, "transporte": t, "bateria": 80 + i,
            "estado_da_bateria": "discharging", "uniq": _endereco_sem_mascara(f"b{i}"),
            "lampada": i, "barra": "#00ff00"}
        for i, (p, s, n, t) in enumerate(modelos, 1)}}), encoding="utf-8")
    return arq




def _abre_o_como(pg) -> None:
    """Abre a gaveta do campo do COMO, CLICANDO — nunca pelo `.open`.

    O `#gesto` saiu da cara do teste em 07/09/2026: ele repetia em prosa os
    passos que já estavam logo acima, e ela escreveu *"quanto texto (…) tá
    impossível ler ou fazer algo aqui"*. Ele mora numa gaveta com nome, e o
    `fill` desta régua estourou por isso — a quebra estava CERTA. Abrir pelo
    clique é o gesto dela; pelo `.open` seria medir um caminho que a mão dela
    não tem.
    """
    if not pg.evaluate("() => !!document.querySelector('#caixa-do-gesto')?.open"):
        pg.click("#caixa-do-gesto > summary")
    pg.wait_for_selector("#gesto", state="visible")


@pytest.mark.skipif(not pathlib.Path(CHROME).exists(), reason="sem Chrome")
def test_a_pagina_dirigida_pelo_navegador(mesa_no_ar, mentira, monkeypatch) -> None:
    """Os três tempos, clicados — e o realce medido no `getComputedStyle`.

    ELE NÃO ABRE JANELA NA TELA DELA: o Chrome sobe headless, que é o padrão do
    `launch()`, e é o mesmo caminho que os portões `pecas-do-dualsense` e
    `cores-do-dualsense` já usam.
    """
    sync_playwright = pytest.importorskip(
        "playwright.sync_api", reason="playwright não está no pyproject",
    ).sync_playwright
    monkeypatch.setenv(med.PORTA_DA_REGUA, str(mentira))

    # O ALVO É ESCOLHIDO PELO QUE A RÉGUA PRECISA MEDIR: uma peça a acender
    # (`l2`) E os dois papéis na mesma linha, para o "brilham igual não diz
    # nada" ter o que comparar. Antes bastava a peça, e a régua dependia de o
    # primeiro achado ter papéis distintos — o que deixou de ser verdade quando
    # as condições entraram, em 07/09/2026.
    alvo = next(t for t in med.todos_os_testes()
                if t.id.startswith("roteiro-")
                and any(p == "l2" for p, _ in t.pecas)
                and len(set(t.papeis.values())) > 1
                and not t.um_por_vez)
    assert med.PAPEL_REAGE in alvo.papeis.values(), alvo.papeis
    assert med.PAPEL_CALADO in alvo.papeis.values(), alvo.papeis

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROME)
        pg = navegador.new_page(viewport={"width": 1240, "height": 900})
        try:
            pg.goto(mesa_no_ar + "#" + alvo.id)
            pg.wait_for_selector("#iniciar")

            # §7.2 — o botão de iniciar existe, e NADA acontece antes dele.
            assert pg.is_visible("#antes")
            assert not pg.is_visible("#depois")
            # OS DESENHOS ESTÃO NA TELA NO TEMPO 1, e é o pedido dela: o
            # botão "mostra o que vai acontecer E O QUE OBSERVAR". A peça
            # acesa é o que observar. Esta linha cobrava zero desenho até
            # 06/09/2026 — ver a razão inteira em
            # `test_nada_acontece_antes_do_iniciar_...` do arquivo irmão.
            pg.wait_for_selector(".ctl svg")
            assert pg.eval_on_selector_all(".ctl svg", "e=>e.length") == 4, (
                "os quatro desenhos não chegaram ao TEMPO 1")
            # O TESTE ESCOLHIDO tem de ter os dois papéis — e a régua o
            # escolhe, em vez de crer que o primeiro da fila os terá. O
            # `roteiro-02` (mover cada controle) tem os quatro reagindo desde
            # que as condições entraram, e é correto: os quatro se movem.
            obs = pg.inner_text("#observar")
            assert "DEVE REAGIR" in obs or "não pode reagir" in obs, obs

            # §7.3 — o timer conta antes de aplicar.
            pg.click("#iniciar")
            assert pg.is_visible("#contagem")
            assert pg.inner_text("#relogio").strip() != "", "o relógio não conta"
            pg.click("#pular-timer")
            pg.wait_for_selector(".ctl svg")

            # §7.6 — os quatro, com transporte, modelo e lâmpada de jogador.
            assert pg.eval_on_selector_all(".ctl svg", "e=>e.length") == 4
            cores = pg.eval_on_selector_all(
                ".ctl svg", "es=>es.map(e=>e.getAttribute('data-colorway'))")
            assert cores == ["cosmic-red", "starlight-blue", "nova-pink",
                             "midnight-black"], cores
            # OS PAPÉIS SE PERGUNTAM AO DONO, não se cravam: eles saem da
            # coluna do roteiro desde 07/09/2026, e uma lista escrita à mão
            # aqui reprovaria toda vez que ela editasse a tabela — a régua
            # medindo o mundo de ontem, que é a família que esta casa caça.
            papeis = pg.eval_on_selector_all(".ctl", "es=>es.map(e=>e.className)")
            esperado = [f"ctl papel-{alvo.papeis[p]}" for p in med.POSTOS]
            assert papeis == esperado, (papeis, esperado)
            # cinco lâmpadas por controle, uma acesa por posto -> P1..P4 acendem
            assert pg.eval_on_selector_all(".ctl svg .led-on", "e=>e.length") > 0
            texto = pg.inner_text(".quatro")
            oui = ":".join(_endereco_sem_mascara().split(":")[:3])
            assert f"{oui}:00:00:b1" in texto, "o endereço não saiu mascarado"
            assert ":".join(_SUFIXO_DE_FIXTURE[:2]) not in texto

            def tinta(seletor: str) -> str:
                return pg.eval_on_selector(seletor, """e=>{
                  const f = e.querySelector(
                    ':is(path,rect,circle,ellipse,polygon):not([fill="none"])');
                  return f ? getComputedStyle(f).fill : '';
                }""")

            # §7.7 — a peça acende, na peça certa, e com papéis distintos.
            #
            # A COR SE LÊ DO TOKEN, NÃO SE DIGITA — curado em 06/09/2026. Estas
            # duas linhas cravavam `rgb(255, 121, 198)` e `rgb(124, 133, 152)`,
            # os hex que a mesa tinha quando nasceu com paleta PRÓPRIA. Ela
            # mandou usar o tema da casa (`paleta_da_casa.TOKENS`), a paleta
            # mudou por decisão, e a régua reprovou a DECISÃO em vez do
            # defeito. É a família que esta casa mais encontra: *a régua digita
            # o que devia ler*. Agora ela pergunta ao token, e continua
            # cobrando o que importa — que os papéis sejam DISTINTOS e que cada
            # peça use o realce do SEU papel.
            def token(nome: str) -> str:
                return pg.evaluate(
                    "(n) => { const s = document.createElement('span');"
                    " s.style.color = `var(${n})`; document.body.appendChild(s);"
                    " const c = getComputedStyle(s).color; s.remove(); return c; }",
                    nome)

            # O FOCO É UM SÓ, E O PAPEL É A MOLDURA — mudou em 07/09/2026,
            # por decisão dela: *"as bordas ou coisas a serem observadas ficam
            # com o foco o mesmo que temos no mapa dos controles"*. Lá a peça
            # em foco acende em `--pink`, e o rosa é o que ela já associa a
            # "olhe aqui" em toda a casa.
            #
            # ESTA RÉGUA COBRAVA TRÊS CORES DE REALCE, uma por papel, e por
            # isso reprovou a DECISÃO em vez do defeito — a segunda vez que
            # acontece com estas mesmas linhas. O que ela tem de cobrar é que
            # a tela SEPARE os papéis; ela só não pode dizer POR ONDE, porque
            # isso é escolha de desenho e a escolha mudou.
            reage, calado = tinta("#p3-l2"), tinta("#p1-l2")
            assert reage == calado == token("--color-pink"), (
                f"a peça em foco não acende no rosa do mapa: {reage} {calado}")

            def moldura(posto: str) -> dict[str, str]:
                return pg.eval_on_selector(
                    f'.ctl[data-posto="{posto}"]',
                    "e=>{const s=getComputedStyle(e);"
                    " return {halo: s.boxShadow, opacidade: s.opacity,"
                    "         borda: s.borderTopColor};}")

            # OS PAPÉIS SE SEPARAM NA MOLDURA, e a régua vai atrás do que a
            # tela usa hoje: o halo de quem deve reagir, e o recuo de quem tem
            # de ficar calado.
            m3, m1 = moldura("P3"), moldura("P1")
            assert m3 != m1, (
                "os quatro cartões estão idênticos — quem deve reagir e quem "
                "tem de ficar calado não se distinguem em nada")
            assert m3["halo"] != "none", (
                "quem deve reagir perdeu o halo — sobrou só o texto")
            # E A BORDA CONTINUA SENDO A COR DO PLÁSTICO, não a do papel: os
            # dois sinais convivem porque dizem coisas diferentes. A primeira
            # volta pôs um `outline` do papel e ele cobria a cor do modelo.
            assert m3["borda"] != m1["borda"], (
                "os dois cartões têm a mesma borda — a cor do plástico sumiu "
                "da moldura")
            # e a peça que NÃO é do teste continua com a cor do plástico dela
            assert tinta("#p3-r1") != reage
            assert tinta("#p3-r1") != tinta("#p1-r1"), (
                "dois modelos diferentes com a mesma cor de plástico")

            # A MORDIDA no navegador: sem a classe, a cor do aparelho volta.
            pg.eval_on_selector("#p3-l2", "e=>e.classList.remove('marcada')")
            assert tinta("#p3-l2") != reage
            pg.eval_on_selector("#p3-l2", "e=>e.classList.add('marcada')")

            # §7.5 — uma resposta gravada sobrevive a recarregar, e está em disco.
            pg.check('.ctl[data-posto="P3"] input[value="obedeceu"]')
            pg.check('.ctl[data-posto="P1"] input[value="nada"]')
            _abre_o_como(pg)
            pg.fill("#gesto", "aba 03 > efeito Arma no P3 · report 0x02")
            # o campo geral saiu; o que ela escreve é por CONTROLE
            pg.fill('textarea[name="n-P3"]', "só o P3 endureceu")
            pg.click("#salvar")
            pg.wait_for_timeout(500)

            # §7.4 — avançar andou, e o campo do COMO NÃO herda o do anterior.
            assert pg.evaluate("location.hash") != "#" + alvo.id, (
                "salvar não avançou para o teste seguinte")
            # O CAMPO NÃO FICA VAZIO — ele vem com o COMO DO TESTE NOVO.
            # Até 07/09/2026 esta linha cobrava vazio, porque o COMO era
            # cobrado DELA; ela leu a cobrança e disse *"isso aqui me quebra.
            # isso eu espero que a página descreva"*. Agora o campo chega
            # pronto do arquivo, e o que a régua tem de provar é o que ela
            # temia de verdade: que o texto seja o DESTE teste, nunca o do
            # anterior. É a mesma armadilha, cobrada pelo lado certo.
            agora = pg.input_value("#gesto")
            seguinte = pg.evaluate("() => TESTES[atual].id")
            assert agora, "o COMO chegou vazio — ela teria de digitar de novo"
            assert alvo.passa_quando not in agora, (
                "o COMO do teste anterior ficou na tela — ela salvaria o COMO "
                "errado sem perceber")
            do_novo = next(x for x in med.todos_os_testes() if x.id == seguinte)
            # O CAMPO NASCE COM OS PASSOS, e não com o gesto inteiro — mudou em
            # 07/09/2026, quando o COMO deixou de ser o roteiro repetido e
            # passou a ter sete campos vindos do arquivo dono. Esta linha
            # cravava o `passa quando` do roteiro dentro do campo; cobrá-lo de
            # volta hoje seria reprovar a cura. O que ela tem de provar é o
            # mesmo de sempre: que o texto é o DESTE teste.
            passos = dict(do_novo.como).get("os passos", "")
            primeiro = next((x.strip() for x in passos.split("\n") if x.strip()), "")
            assert primeiro and primeiro[:40] in agora, (
                f"o campo do gesto não trouxe os passos deste teste. "
                f"esperado começar por {primeiro[:40]!r}, veio {agora[:120]!r}")
            assert agora.lstrip().startswith("1."), (
                f"os passos chegaram sem numeração: {agora[:60]!r}")
            pg.click("#anterior")
            assert pg.evaluate("location.hash") == "#" + alvo.id, "voltar não anda"

            # RECARREGAR DE VERDADE. Um `goto` que só troca o `#` é navegação
            # no MESMO documento: o `DOMContentLoaded` não dispara e a página
            # continua sendo a de antes. Foi assim que a primeira versão desta
            # régua deu verde sobre um campo que nunca tinha sido relido.
            pg.goto("about:blank")
            pg.goto(mesa_no_ar + "#" + alvo.id)
            pg.wait_for_selector("#iniciar")
            pg.click("#iniciar")
            pg.click("#pular-timer")
            pg.wait_for_selector(".ctl svg")
            assert pg.input_value("#gesto").startswith("aba 03"), (
                "a resposta não sobreviveu a recarregar")
            assert pg.is_checked('.ctl[data-posto="P3"] input[value="obedeceu"]')

            # §7.8 — o índice tem as seções e cada número leva ao teste.
            # `.lower()` porque o título da seção é `text-transform:uppercase`:
            # a régua compara o TEXTO, não o que o CSS fez com ele.
            indice = pg.inner_text("#indice-corpo").lower()
            assert "o roteiro" in indice and "o mapa de canais" in indice
            assert "obedeceu" in indice, "o índice não mostra o estado gravado"
            # A CONTAGEM É POR SEÇÃO desde 07/09/2026 — *"cadê as seções das
            # 21?"*. Antes o índice trazia um total só ("1 de 21"), e esta
            # linha o cravava; com as seis seções do roteiro cada uma conta a
            # sua, e a régua passa a cobrar o que interessa: que ALGUMA seção
            # registre o que acabou de ser respondido.
            contagens = re.findall(r"— (\d+) de (\d+)", indice)
            assert contagens, f"o índice não conta nada: {indice[:200]}"
            assert any(int(f) > 0 for f, _ in contagens), (
                "o índice não conta o que foi feito — nenhuma seção registrou "
                "a resposta que acabou de ser gravada")
            # E AS SEÇÕES SOMAM A FATIA QUE ESTÁ NA TELA, não o acervo: o
            # filtro abre em *"o que falta"* por pedido dela, e um índice que
            # contasse os 199 enquanto a página mostra 148 mandaria procurar
            # teste que não está ali.
            na_tela = pg.evaluate("() => TESTES.length")
            assert sum(int(quantos) for _, quantos in contagens) == na_tela, (
                f"o índice perdeu testes pelo caminho: as seções somam "
                f"{sum(int(q) for _, q in contagens)} e a página mostra "
                f"{na_tela}")
            pg.click('#indice-corpo a[data-ir="0"]')
            assert pg.evaluate("location.hash") == "#roteiro-01", (
                "o número do índice não leva ao teste")
        finally:
            navegador.close()

    # E O DISCO, que é o que a sessão que morre não leva embora.
    fita = next(iter(sorted((med.pasta_do_registro()).glob("registro-*.jsonl"))))
    bruto = fita.read_text(encoding="utf-8")
    assert "report 0x02" in bruto
    oui = ":".join(_endereco_sem_mascara().split(":")[:3])
    assert f"{oui}:00:00:b3" in bruto
    assert ":".join(_SUFIXO_DE_FIXTURE[:2]) not in bruto
