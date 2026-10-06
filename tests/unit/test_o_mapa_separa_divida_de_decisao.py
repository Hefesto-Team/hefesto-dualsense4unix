"""O mapa de canais tem de separar DÍVIDA de DECISÃO — e só a dívida reprova.

O DEFEITO QUE ESTE ARQUIVO EXISTE PARA NÃO DEIXAR VOLTAR
--------------------------------------------------------
Medido em 22/08/2026, rodando o contador deste arquivo contra
`docs/data/mapa-controles.csv`: **41 células diziam que a casa MEDIU e o produto
NÃO ACIONA** — 20 no cabo, 21 no rádio, 13 linhas com as duas assim. (São
**45 em 09/09/2026** — a recontagem está no fim deste bloco.) (Foram
**39 entre 29/08 e 02/09/2026**, e as duas que saíram saíram PELO MOTIVO CERTO:
o acelerômetro do DualSense passou a ser lido nos dois transportes —
ONDA-CONTROLES-04. O número desce quando a dívida é paga; é para isso que ele
está aqui. **Voltou a 41 em 02/09/2026, e a subida é de HONESTIDADE, não de
dívida:** os dois lados de `movimento.imu.ligar@dualsense` subiram de
`inferido-do-codigo` para `medido` porque o caderno tem dois ensaios de bancada
para eles desde 15/08 — a casa passou a admitir que MEDIU, e o `aciona = não`
não mudou. As duas células entraram com `nada-a-acionar`, que é DECISÃO: não há
o que acionar porque não existe comando de ligar a IMU e o sensor emite sempre.
O contador de dívida deste arquivo não se moveu.)

**RECONTADO EM 25/09/2026: são 45** — 23 no cabo, 22 no rádio (na base
desta recontagem eram 47: 24 no cabo, 23 no rádio). As DUAS que SAÍRAM saíram
PELO MOTIVO CERTO: os dois lados de `luz.led_jogador.brilho@dualsense` passaram
a ser ACIONADOS pelo produto. A decisão dela
`D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS` (Fraco, Médio e Forte na linha
LEDs, nascendo no Fraco) virou campo do perfil e report nos dois transportes
(O-BRILHO-DAS-LUZES-DE-NUMERO-01). As duas eram `so-ela-decide`, que é
DECISÃO: o contador de dívida deste arquivo não se moveu.

**RECONTADO EM 21/09/2026: eram 47** — 23 no cabo, 24 no rádio. A que ENTROU é
`audio.microfone.ganho@dualsense` no rádio, e a subida é de HONESTIDADE pela
quinta vez neste arquivo: a célula NASCEU medida em 20/09 (o `amixer` do
controle no cabo respondeu, e os três do rádio não têm placa ALSA nenhuma), com
`aciona = não` e a razão escrita — *pelo rádio o microfone chega como som já
digitalizado, por nó da nossa ponte; não há placa ALSA onde o elemento exista*.
Isso é **DECISÃO, e não dívida**: o contador deste arquivo não se moveu. A tela
diz o mesmo, com o trilho cinza e a razão no `?` ao lado.

**RECONTADO EM 18/09/2026: eram 46** — 23 no cabo, 23 no rádio. A que SAIU
saiu PELO MOTIVO CERTO, e é a mesma que entrou por honestidade em 10/09:
`audio.alto_falante@dualsense` no rádio passou a ser ACIONADA pelo produto. O
som pelo `0x35` e a háptica pelo `0x32` fecharam o contrato da célula, e o
commit `9f1920152` a virou para `sim` com a régua que morde. *A dívida foi paga,
e o número desceu — que é para isso que ele está aqui.*

**RECONTADO EM 10/09/2026: eram 47** — 23 no cabo, 24 no rádio. As DUAS que
entraram são do lado do RÁDIO, e a subida é de HONESTIDADE pela quarta vez
neste arquivo: `audio.alto_falante@dualsense` e
`audio.saida_dedicada.payload_do_degrau@dualsense` subiram para `medido`
porque o som SAIU pelo rádio na bancada dela (report `0x35`, 70 s com a
orelha dela) — e o `aciona = não` continua onde estava, porque o contrato
daquela célula pede TRÊS coisas e a corrida cumpriu uma: falta o **negativo de
rota** e o **teste cego**, que são dela. *A casa passou a admitir que mediu, e
a dívida não se moveu.*

**RECONTADO EM 09/09/2026: eram 45** — 23 no cabo, 22 no rádio. As DUAS que
entraram são os dois lados de `luz.lightbar.brilho@dualsense`, e a subida é de
HONESTIDADE pela terceira vez neste arquivo: a BRILHO-DE-HARDWARE-01 mediu o
byte na bancada DELA e a premissa da sprint caiu junto — o `common[42]` obedece
nos dois transportes, mas o que ele atenua são as **lâmpadas de numeração**, não
a barra. Palavra dela, com os quatro na mão: *"o que o slicer altera não são as
cores do lightbar mas os leds que indicam qual player é o dono daquele
controle"*. <!-- noqa-acento: citação literal -->
A célula subiu de `nao-medido` para `medido` e o `aciona = não` continua onde
estava — agora por MEDIÇÃO, e não por falta de olhar. O mapa ganhou a chave
`luz.led_jogador.brilho` para o dono verdadeiro do byte.

**RECONTADO EM 07/09/2026: eram 43** — 22 no cabo, 21 no rádio.
E o saldo é o que este número existe para mostrar: **três SAÍRAM porque a
dívida foi paga** — `identidade.cor_do_aparelho@dualsense` no rádio e o
`movimento.acelerometro@dualsense` nos dois transportes passaram a ser
acionados pelo produto — e **cinco entraram**, quatro delas por HONESTIDADE, não
por dívida nova: `movimento.imu.ligar@dualsense` nos dois lados,
`identidade.pareamento@dualsense` e `plataforma.crc32@dualsense` no cabo subiram
para `medido` porque a casa passou a admitir que mediu, e o `aciona = não` já
estava lá. A quinta é `plataforma.udev_autosuspend@sn30` no rádio.

*A recontagem esperou:* o agente da SPECS-A-PROCEDENCIA-01 viu o vermelho, o
declarou no relatório dele e NÃO recontou — *"recontar é reescrever a prosa do
arquivo, e ela é de quem a escreveu"*. Estava certo: um número que se conserta
sozinho para o teste passar é um número que ninguém leu.

O
`scripts/gerar-mapa.py` já as pintava de laranja (`--color-lacuna`, "a casa sabe
e o produto não faz") e já as contava no cartão de cada controle (`placar`,
chave `lacuna`).

Contar não bastava, e a razão é o motivo de nunca ter existido portão aqui:
**as 41 não são a mesma coisa.**

- `identidade.revisao_de_placa@dualsense` não é acionada porque o mapa diz, em
  letras grandes, *"NÃO É A COR"* — ler aquele nó para nomear jogador daria dois
  "controles iguais" no dia em que ela comprar um par. **Não acionar é o certo.**
- `movimento.imu.perda@dualsense` não é acionada porque a cura está medida e
  nunca foi ligada — o `__le32` de `corpo[11..14]` é contador de reports nos DOIS
  transportes e o produto não o lê em transporte nenhum. **Não acionar é falta.**

Um portão que reprovasse as 41 juntas reprovaria a decisão junto com a dívida, e
seria desligado na primeira semana — que é exatamente o que teria acontecido se
alguém tivesse escrito um antes de existir a coluna que separa as duas.

A COLUNA, E POR QUE ELA É UM PAR
--------------------------------
`cabo_por_que_nao_aciona` / `radio_por_que_nao_aciona`, ao lado de
`cabo_aciona`/`radio_aciona`. É par por transporte porque a resposta MUDA de
lado: `identidade.cor_do_aparelho@dualsense` é decisão nenhuma no cabo (lá o
produto lê a cor do plástico, e a aba Configurações a mostra desde 22/08) e é
dívida no rádio (lá não chega).

O domínio, e ele responde *"não aciona — e daí?"*:

===================  ============================================================
`` (vazio)           ninguém respondeu. É o que a regra 1 cobra.
`divida`             falta fazer, e há quem queira. **É o que a regra 3 limita.**
`decisao-tomada`     não acionar é a escolha, e ela está certa hoje.
`nada-a-acionar`     não há feature a acionar: ou o aparelho não oferece, ou a
                     linha é de MEDIÇÃO e `aciona = não` responde "o fenômeno
                     não aconteceu", nunca "o produto não faz".
`so-ela-decide`      a pergunta existe, ninguém a respondeu, e a resposta é dela.
                     Nem dívida nem decisão — fila de decisão.
===================  ============================================================

Os valores são hifenizados por um motivo mecânico que vale registrar:
`scripts/validar-acentuacao.py` reprova a palavra "decisão" escrita sem o til, e
está certo — mas não a reprova quando ela é parte de um identificador maior.
Daí `decisao-tomada`, e daí `so-ela-decide`.

O retrato de 22/08/2026, com as 41 preenchidas: **4 dívidas**, 15 decisões,
20 `nada-a-acionar`, 2 `so-ela-decide`.

Em 29/08/2026 as duas `so-ela-decide` saíram — eram o acelerômetro do DualSense
no cabo e no rádio, e a pergunta foi respondida por ela com *"não era pra ele
sair. era pra ele FUNCIONAR"*. A palavra continua no domínio, sem uso e com a
razão escrita, em `RESERVADOS`: o estado que ela nomeia não morreu com a linha
que a usava.

POR QUE O PORTÃO MORA NUM TESTE, E NÃO NO `check_paridade_transporte.py`
------------------------------------------------------------------------
Porque a leva que escreveu esta coluna não tinha `scripts/` no território, e
portão que espera dono nunca nasce. A consequência está dita na cara: hoje o
DOMÍNIO desta coluna tem dono executável AQUI, e não no
`DOMINIO_POR_SUFIXO` do portão — que é o lugar dele. Quem for dono daquele
arquivo fecha isto acrescentando `"por_que_nao_aciona"` ao dicionário e
importando `DOMINIO` daqui, para a lista continuar tendo UM dono.

A RÉGUA FOI VALIDADA, e é a parte que esta casa esquece três vezes por dia
--------------------------------------------------------------------------
Um teste que itera a mesma lista que deveria conferir não mede nada. Dois testes
aqui existem só para provar que este não faz isso:

- `test_a_populacao_nao_depende_da_coluna_que_ela_confere` apaga a coluna nova
  inteira num CSV de mentira e confere que a população continua com o mesmo
  tamanho — a população sai de `de_onde_sei` e `aciona`, que são outras colunas;
- `test_o_teto_e_um_numero_deste_arquivo_e_nao_do_csv` põe uma dívida a mais num
  CSV de mentira e confere que o contador a VÊ. Um teto lido do próprio CSV
  passaria sempre, e é o defeito que a ADR-016 pagou por um mês.

MORDE? (arrancadas uma a uma em 22/08/2026, todas reprovaram)
--------------------------------------------------------------
1. Esvaziar a célula `cabo_por_que_nao_aciona` de
   `identidade.revisao_de_placa@dualsense`:
   `test_toda_celula_medida_e_nao_acionada_diz_por_que` reprova nomeando o `id`
   e o lado.
2. Trocar `decisao-tomada` por `divida` em qualquer célula:
   `test_a_divida_nao_cresce` reprova dizendo 5 contra o teto de 4.
3. Escrever `dívida` (com acento) numa célula: `test_o_valor_cabe_no_dominio`
   reprova — sem ele, uma tipografia nova sairia da conta em silêncio, que é o
   modo de falha que o `ate_onde_foi` já pagou em 12/08.
4. Tirar a coluna do cabeçalho: `test_a_coluna_existe_nos_dois_lados` reprova em
   vez de o arquivo inteiro virar no-op verde.
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

sys.path.insert(0, str(RAIZ / "scripts"))
from check_a_decisao_tem_prova import RESPONDIDAS as _RESPONDIDAS
from check_paridade_transporte import DOMINIO_POR_SUFIXO as _DOMINIO_DO_PORTAO

LADOS = ("cabo", "radio")
SUFIXO = "por_que_nao_aciona"

DE_ONDE_SEI_MEDIDO = "medido"
ACIONA_NAO = "não"

DIVIDA = "divida"
DECISAO = "decisao-tomada"
NADA_A_ACIONAR = "nada-a-acionar"
SO_ELA_DECIDE = "so-ela-decide"
O_APARELHO_RECUSA = "o-aparelho-recusa"

DOMINIO = _DOMINIO_DO_PORTAO["por_que_nao_aciona"]

#:                    payload_do_degrau dela — todas do DualSense
TETO_DA_DIVIDA = 22


def _linhas(caminho: Path | str) -> list[dict[str, str]]:
    texto = Path(caminho).read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(texto)))


def _cabecalho(caminho: Path | str) -> list[str]:
    texto = Path(caminho).read_text(encoding="utf-8")
    return next(csv.reader(io.StringIO(texto)))


def _celula(linha: dict[str, str], coluna: str) -> str:
    return (linha.get(coluna) or "").strip()


def populacao(caminho: Path | str) -> list[tuple[str, str]]:
    """As células em que a casa MEDIU e o produto NÃO ACIONA."""
    achadas: list[tuple[str, str]] = []
    for linha in _linhas(caminho):
        for lado in LADOS:
            medido = _celula(linha, f"{lado}_de_onde_sei") == DE_ONDE_SEI_MEDIDO
            nao = _celula(linha, f"{lado}_aciona") == ACIONA_NAO
            if medido and nao:
                achadas.append((_celula(linha, "id"), lado))
    return achadas


def respostas(caminho: Path | str) -> dict[tuple[str, str], str]:
    """O que cada célula respondeu, para TODA linha do arquivo."""
    ditas: dict[tuple[str, str], str] = {}
    for linha in _linhas(caminho):
        for lado in LADOS:
            ditas[(_celula(linha, "id"), lado)] = _celula(linha, f"{lado}_{SUFIXO}")
    return ditas


def conta_dividas(caminho: Path | str) -> list[tuple[str, str]]:
    """Toda célula que se declara DÍVIDA, esteja ou não na população."""
    return sorted(chave for chave, valor in respostas(caminho).items() if valor == DIVIDA)


def _csv_de_mentira(destino: Path, trocas: dict[tuple[str, str], str] | None = None,
                    apagar_a_coluna: bool = False) -> Path:
    """Uma cópia do mapa com as células que o teste quiser mexidas."""
    texto = MAPA.read_text(encoding="utf-8")
    linhas = list(csv.reader(io.StringIO(texto)))
    cabecalho = linhas[0]
    i_id = cabecalho.index("id")
    indices = {lado: cabecalho.index(f"{lado}_{SUFIXO}") for lado in LADOS}

    saida = [list(cabecalho)]
    for linha in linhas[1:]:
        nova = list(linha)
        for lado in LADOS:
            if apagar_a_coluna:
                nova[indices[lado]] = ""
            valor = (trocas or {}).get((linha[i_id].strip(), lado))
            if valor is not None:
                nova[indices[lado]] = valor
        saida.append(nova)

    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(saida)
    destino.write_text(buffer.getvalue(), encoding="utf-8")
    return destino


def test_a_coluna_existe_nos_dois_lados() -> None:
    """Sem a coluna, todo o resto deste arquivo vira no-op verde."""
    cabecalho = _cabecalho(MAPA)
    faltando = [f"{lado}_{SUFIXO}" for lado in LADOS if f"{lado}_{SUFIXO}" not in cabecalho]
    assert not faltando, (
        "o mapa perdeu a(s) coluna(s) " + ", ".join(faltando) + " — sem elas este "
        "portão aprovaria o arquivo inteiro sem dizer uma palavra, que é pior "
        "que portão nenhum"
    )


def test_toda_celula_medida_e_nao_acionada_diz_por_que() -> None:
    """Regra 1 — medir e não fazer é afirmação forte, e ela deve o porquê."""
    ditas = respostas(MAPA)
    mudas = [chave for chave in populacao(MAPA) if not ditas.get(chave)]
    assert not mudas, (
        f"{len(mudas)} célula(s) dizem `de_onde_sei = medido` e `aciona = não` "
        f"sem responder `{SUFIXO}`: "
        + ", ".join(f"{ident} ({lado})" for ident, lado in mudas[:8])
        + ". Vazio aqui não é 'não deve nada' — é 'ninguém olhou'. Responda "
        f"com um de {sorted(DOMINIO - {''})}"
    )


def test_o_valor_cabe_no_dominio() -> None:
    """Regra 2 — tipografia nova é mentira que sai pela porta que ninguém olha."""
    fora = {
        chave: valor for chave, valor in respostas(MAPA).items() if valor not in DOMINIO
    }
    assert not fora, (
        "valor fora do domínio em " + ", ".join(
            f"{ident} ({lado}) = {valor!r}" for (ident, lado), valor in list(fora.items())[:8]
        ) + f". O domínio é {sorted(DOMINIO)}"
    )


def test_a_divida_nao_cresce() -> None:
    """Regra 3 — a decisão pode crescer à vontade; a dívida, não."""
    devendo = conta_dividas(MAPA)
    assert len(devendo) <= TETO_DA_DIVIDA, (
        f"a dívida do mapa subiu para {len(devendo)} células, e o teto de "
        f"22/08/2026 é {TETO_DA_DIVIDA}: "
        + ", ".join(f"{ident} ({lado})" for ident, lado in devendo)
        + ". Pagar baixa o teto no mesmo commit; subi-lo é dizer que a casa "
        "passou a dever mais"
    )


def test_a_decisao_pode_crescer_sem_reprovar() -> None:
    """A promessa da regra 3, exercida — senão ela é só uma frase no docstring."""
    import tempfile

    with tempfile.TemporaryDirectory() as pasta:
        alvos = set(populacao(MAPA)) | set(conta_dividas(MAPA))
        falso = _csv_de_mentira(
            Path(pasta) / "mapa.csv",
            trocas={chave: DECISAO for chave in alvos},
        )
        assert len(conta_dividas(falso)) == 0
        assert not [chave for chave in populacao(falso) if not respostas(falso).get(chave)]


def test_a_populacao_nao_depende_da_coluna_que_ela_confere() -> None:
    """Apagar a coluna nova não pode encolher a população que a cobra."""
    import tempfile

    antes = populacao(MAPA)
    with tempfile.TemporaryDirectory() as pasta:
        vazio = _csv_de_mentira(Path(pasta) / "mapa.csv", apagar_a_coluna=True)
        depois = populacao(vazio)
    assert antes == depois, (
        "a população mudou quando a coluna conferida foi apagada — quer dizer "
        "que ela é derivada da própria coluna, e o portão ficaria verde "
        "justamente quando alguém esquecesse de responder"
    )
    assert len(antes) == 45, (
        f"o recorte de 25/09/2026 tinha 45 células medidas e não "
        f"acionadas, e agora tem {len(antes)}. Não é reprovação de defeito: é "
        "aviso de que o retrato deste arquivo envelheceu e o texto precisa ser "
        "recontado — leia o cabeçalho deste arquivo, que diz como"
    )


def test_o_teto_e_um_numero_deste_arquivo_e_nao_do_csv() -> None:
    """Uma dívida a mais tem de ser VISTA — teto lido do CSV passaria sempre."""
    import tempfile

    alvo = next(chave for chave in populacao(MAPA) if respostas(MAPA)[chave] == DECISAO)
    with tempfile.TemporaryDirectory() as pasta:
        pior = _csv_de_mentira(Path(pasta) / "mapa.csv", trocas={alvo: DIVIDA})
        assert len(conta_dividas(pior)) == TETO_DA_DIVIDA + 1


RESERVADOS: dict[str, str] = {}

_A_RESERVA_DE_29_08_QUE_CADUCOU = {
    SO_ELA_DECIDE: (
        "29/08/2026, ONDA-CONTROLES-04. O último uso era "
        "`movimento.acelerometro@dualsense`, nos dois lados, e ele saiu porque "
        "a causa FOI RESOLVIDA: ela decidiu (*\"não era pra ele sair. era pra "
        "ele FUNCIONAR\"*), o produto passou a ler `ABS_X/Y/Z` e a célula virou "
        "`aciona=sim`, sem causa a declarar. A palavra fica porque o ESTADO que "
        "ela nomeia — o produto pode, e a escolha é dela — não deixou de "
        "existir com esta linha: a ONDA-CONTROLES-07 (o interruptor do sensor) "
        "e a 08 (a calibração) nascem exatamente nele. Tirá-la do domínio "
        "obrigaria a próxima pessoa a escrever `divida` para uma escolha que "
        "não é dívida nossa, que é a palavra errada que este arquivo existe "
        "para impedir."
    ),
}


@pytest.mark.parametrize("valor", [DIVIDA, DECISAO, NADA_A_ACIONAR, SO_ELA_DECIDE])
def test_cada_valor_do_dominio_e_usado_ou_explicado(valor: str) -> None:
    """Valor de domínio que ninguém usa é vocabulário morto — ou é dívida de fila."""
    usados = set(respostas(MAPA).values())
    if valor in RESERVADOS:
        assert valor not in usados, (
            f"{valor!r} voltou a ser usado no mapa e continua em RESERVADOS. "
            "Tire-o de lá: a reserva é para o que NÃO tem uso, e mantê-la "
            "sobre um valor vivo esconde o dia em que ele morrer de novo"
        )
        return
    assert valor in usados, (
        f"nenhuma célula do mapa usa {valor!r}. Se a resposta deixou de existir, "
        "tire-a de DOMINIO no mesmo gesto, ou declare-a em RESERVADOS com a "
        "razão — domínio maior que o uso é convite a escrever a palavra errada"
    )


def test_reservado_que_ninguem_explica_nao_entra() -> None:
    """A reserva sem razão escrita seria o silêncio com outro nome."""
    assert all(len(razao) > 80 for razao in RESERVADOS.values()), (
        "todo valor reservado tem de trazer a razão datada de por que a "
        "palavra fica sem uso — uma linha curta não é razão, é desculpa"
    )
    assert set(RESERVADOS) <= set(DOMINIO), (
        "só se reserva o que está no domínio: reservar palavra de fora seria "
        "inventar vocabulário pela porta dos fundos"
    )


VETO_DOS_EXTERNOS = "D-2409-O-VETO-DOS-EXTERNOS-SEGUE-ATE-O-RELEASE"
NUNCA_GRAVA_A_CALIBRACAO = "D-2409-O-HEFESTO-NUNCA-GRAVA-A-CALIBRACAO"
RESPONDIDAS_POR_ELA: dict[str, str] = {
    "combinacao.rumble_simultaneo@sn30": VETO_DOS_EXTERNOS,
    "combinacao.tres_na_mesa@pro": VETO_DOS_EXTERNOS,
    "combinacao.tres_na_mesa@sn30": VETO_DOS_EXTERNOS,
    "entrada.bruta@sn30": VETO_DOS_EXTERNOS,
    "entrada.combo.ponte@sn30": VETO_DOS_EXTERNOS,
    "entrada.stick@sn30": VETO_DOS_EXTERNOS,
    "movimento.acelerometro@sn30": VETO_DOS_EXTERNOS,
    "movimento.giroscopio@sn30": VETO_DOS_EXTERNOS,
    "plataforma.adocao@sn30": VETO_DOS_EXTERNOS,
    "vibracao.rumble.ff@sn30": VETO_DOS_EXTERNOS,
    "vibracao.rumble.passthrough@sn30": VETO_DOS_EXTERNOS,
    "entrada.stick.calibracao@dualsense": NUNCA_GRAVA_A_CALIBRACAO,
}
DECISOES_DELA = RAIZ / "docs" / "data" / "decisoes-de-produto.csv"

O_VETO_ALCANCA_O_PRO: dict[str, str] = {
    "plataforma.adocao@pro": VETO_DOS_EXTERNOS,
    "entrada.combo.ponte@pro": VETO_DOS_EXTERNOS,
    "vibracao.rumble.passthrough@pro": VETO_DOS_EXTERNOS,
    "movimento.giroscopio.jogo@pro": VETO_DOS_EXTERNOS,
    "movimento.acelerometro.jogo@pro": VETO_DOS_EXTERNOS,
    "energia.bateria.jogo@pro": VETO_DOS_EXTERNOS,
    "energia.bateria.jogo@sn30": VETO_DOS_EXTERNOS,
    "combinacao.cabo_e_radio.taxa@pro": VETO_DOS_EXTERNOS,
    "combinacao.cabo_e_radio.taxa@sn30": VETO_DOS_EXTERNOS,
}


def respostas_que_voltaram(
    mapa: Path | str,
    decisoes: Path | str,
    respondidas: dict[str, str] | None = None,
) -> list[str]:
    """O que desfaz uma resposta dela, por linha. Lista vazia: nada voltou."""
    linhas = {_celula(linha, "id"): linha for linha in _linhas(mapa)}
    decididas = {
        _celula(linha, "id")
        for linha in _linhas(decisoes)
        if _celula(linha, "estado") in _RESPONDIDAS
    }
    achados: list[str] = []
    if respondidas is None:
        respondidas = RESPONDIDAS_POR_ELA
    for ident, decisao in respondidas.items():
        if decisao not in decididas:
            achados.append(
                f"{ident}: `{decisao}` não está `decidida` (nem acima, na escada) "
                f"em {Path(decisoes).name}")
        linha = linhas.get(ident)
        if linha is None:
            achados.append(f"{ident}: a linha sumiu do mapa")
            continue
        for lado in LADOS:
            aciona = _celula(linha, f"{lado}_aciona")
            if aciona != ACIONA_NAO:
                achados.append(f"{ident} ({lado}): `aciona` = {aciona!r}, e a resposta é não")
                continue
            causa = _celula(linha, f"{lado}_{SUFIXO}")
            if causa != DECISAO:
                achados.append(f"{ident} ({lado}): `{SUFIXO}` = {causa!r}, e ela respondeu")
        texto = " ".join(valor or "" for valor in linha.values())
        if decisao not in texto:
            achados.append(f"{ident}: nenhuma célula cita `{decisao}`")
        if SO_ELA_DECIDE in texto:
            achados.append(f"{ident}: alguma célula ainda diz `{SO_ELA_DECIDE}`")
    return achados


def test_a_resposta_dela_nao_volta_a_ser_pergunta() -> None:
    """MORDE: devolva `so-ela-decide` a uma das doze, apague o id dela, ou mexa no `aciona`."""
    voltaram = respostas_que_voltaram(MAPA, DECISOES_DELA)
    assert not voltaram, (
        f"{len(voltaram)} achado(s) nas linhas que ela respondeu em 24/09/2026: "
        + "; ".join(voltaram)
        + ". A pergunta tem resposta: os dois lados dizem `aciona = não`, a causa é "
        "`decisao-tomada` e a linha cita a decisão pelo id. Se a pergunta voltou, a "
        "decisão sai de `decidida` no arquivo dela e a linha sai de "
        "`RESPONDIDAS_POR_ELA` no mesmo gesto"
    )


def test_a_regua_das_respostas_ve_uma_que_volta() -> None:
    """Uma célula devolvida a `so-ela-decide` num CSV de mentira tem de ser VISTA."""
    import tempfile

    alvo = ("entrada.stick.calibracao@dualsense", "radio")
    with tempfile.TemporaryDirectory() as pasta:
        falso = _csv_de_mentira(Path(pasta) / "mapa.csv", trocas={alvo: SO_ELA_DECIDE})
        voltaram = respostas_que_voltaram(falso, DECISOES_DELA)
    assert any(achado.startswith(f"{alvo[0]} ({alvo[1]})") for achado in voltaram), voltaram
    assert any(SO_ELA_DECIDE in achado for achado in voltaram), voltaram


def _decisoes_com_o_estado(destino: Path, ident: str, estado: str) -> Path:
    """Uma cópia do registro dela com o `estado` de UMA decisão trocado."""
    linhas = list(csv.DictReader(io.StringIO(DECISOES_DELA.read_text(encoding="utf-8"))))
    for linha in linhas:
        if linha["id"] == ident:
            linha["estado"] = estado
    buffer = io.StringIO()
    escritor = csv.DictWriter(buffer, fieldnames=list(linhas[0]), lineterminator="\n")
    escritor.writeheader()
    escritor.writerows(linhas)
    destino.write_text(buffer.getvalue(), encoding="utf-8")
    return destino


@pytest.mark.parametrize("estado", ["implementada", "feita", "no ar"])
def test_a_decisao_que_sobe_a_escada_continua_respondida(estado: str) -> None:
    """DECISAO-SEM-DONO-01: subir a `feita` não desfaz a resposta dela; voltar a `aberta`, sim."""
    import tempfile

    decisao = next(iter(RESPONDIDAS_POR_ELA.values()))
    with tempfile.TemporaryDirectory() as pasta:
        subiu = _decisoes_com_o_estado(Path(pasta) / "subiu.csv", decisao, estado)
        assert respostas_que_voltaram(MAPA, subiu) == respostas_que_voltaram(MAPA, DECISOES_DELA)
        reaberta = _decisoes_com_o_estado(Path(pasta) / "reaberta.csv", decisao, "aberta")
        assert any(decisao in achado for achado in respostas_que_voltaram(MAPA, reaberta))


def _mapa_com_a_linha_mexida(destino: Path, ident: str, colunas: dict[str, str]) -> Path:
    """Uma cópia do mapa com QUALQUER coluna de uma linha trocada."""
    linhas = list(csv.reader(io.StringIO(MAPA.read_text(encoding="utf-8"))))
    cabecalho = linhas[0]
    i_id = cabecalho.index("id")
    for linha in linhas[1:]:
        if linha[i_id].strip() == ident:
            for coluna, valor in colunas.items():
                linha[cabecalho.index(coluna)] = valor
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(linhas)
    destino.write_text(buffer.getvalue(), encoding="utf-8")
    return destino


@pytest.mark.parametrize(
    ("ident", "lado", "aciona"),
    [
        ("entrada.bruta@sn30", "cabo", ""),
        ("plataforma.adocao@sn30", "radio", "sim"),
        ("entrada.stick.calibracao@dualsense", "cabo", "parcial"),
    ],
)
def test_a_regua_das_respostas_ve_o_aciona_que_muda(ident: str, lado: str, aciona: str) -> None:
    """O lado que deixa de dizer `não` tem de ser VISTO, e não sair da conta."""
    import tempfile

    colunas = {f"{lado}_aciona": aciona, f"{lado}_{SUFIXO}": ""}
    with tempfile.TemporaryDirectory() as pasta:
        falso = _mapa_com_a_linha_mexida(Path(pasta) / "mapa.csv", ident, colunas)
        voltaram = respostas_que_voltaram(falso, DECISOES_DELA)
    assert any(achado.startswith(f"{ident} ({lado}): `aciona`") for achado in voltaram), voltaram


def test_o_veto_alcanca_o_pro() -> None:
    """MORDE: devolva `nada-a-acionar` a uma linha do Pro, ou apague o id da taxa."""
    voltaram = respostas_que_voltaram(MAPA, DECISOES_DELA, O_VETO_ALCANCA_O_PRO)
    assert not voltaram, (
        f"{len(voltaram)} achado(s) nas linhas do Pro e da taxa que o veto alcança: "
        + "; ".join(voltaram)
        + ". A pergunta dela nomeava o 8BitDo E o Pro: a não-adoção do Pro é "
        "`decisao-tomada` com o id, não `nada-a-acionar`. Se o veto caiu, a decisão "
        "sai de `decidida` e a linha sai de `O_VETO_ALCANCA_O_PRO` no mesmo gesto"
    )


@pytest.mark.parametrize(
    ("ident", "colunas", "achado"),
    [
        ("plataforma.adocao@pro", {"cabo_por_que_nao_aciona": NADA_A_ACIONAR},
         "plataforma.adocao@pro (cabo): `por_que_nao_aciona`"),
        ("combinacao.cabo_e_radio.taxa@sn30", {"radio_ressalva": ""},
         "combinacao.cabo_e_radio.taxa@sn30: nenhuma célula cita"),
    ],
)
def test_a_regua_do_veto_ve_o_pro_que_volta(ident: str, colunas: dict[str, str],
                                           achado: str) -> None:
    """A régua de cima tem de VER a linha do Pro que desfaz a resposta dela."""
    import tempfile

    with tempfile.TemporaryDirectory() as pasta:
        falso = _mapa_com_a_linha_mexida(Path(pasta) / "mapa.csv", ident, colunas)
        voltaram = respostas_que_voltaram(falso, DECISOES_DELA, O_VETO_ALCANCA_O_PRO)
    assert any(item.startswith(achado) for item in voltaram), voltaram
