"""O mapa de canais tem de separar DÍVIDA de DECISÃO — e só a dívida reprova.

O DEFEITO QUE ESTE ARQUIVO EXISTE PARA NÃO DEIXAR VOLTAR
--------------------------------------------------------
Medido em 22/08/2026, rodando o contador deste arquivo contra
`docs/data/mapa-controles.csv`: **41 células diziam que a casa MEDIU e o produto
NÃO ACIONA** — 20 no cabo, 21 no rádio, 13 linhas com as duas assim. (São
**43 em 07/09/2026** — a recontagem está no fim deste bloco.) (Foram
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

**RECONTADO EM 07/09/2026: são 43** — 22 no cabo, 21 no rádio.
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
# Z6-05 (24/08/2026): o domínio ganhou dono só —
# `check_paridade_transporte.DOMINIO_POR_SUFIXO["por_que_nao_aciona"]` — e este
# arquivo passou a IMPORTAR em vez de manter cópia própria, fechando o que o
# cabeçalho pediu: "a lista continuar tendo UM dono". O quinto valor,
# `o-aparelho-recusa`, entrou nesse gesto.
from check_paridade_transporte import DOMINIO_POR_SUFIXO as _DOMINIO_DO_PORTAO

LADOS = ("cabo", "radio")
SUFIXO = "por_que_nao_aciona"

#: O que conta como "a casa mediu e o produto não faz". As duas colunas são
#: OUTRAS que a conferida — é isso que faz a régua valer.
DE_ONDE_SEI_MEDIDO = "medido"
ACIONA_NAO = "não"

DIVIDA = "divida"
DECISAO = "decisao-tomada"
NADA_A_ACIONAR = "nada-a-acionar"
SO_ELA_DECIDE = "so-ela-decide"
#: O quinto valor (Z6-05, 24/08/2026): causa FORA do nosso código, como o
#: `HANDSHAKE 0x04` da cor por rádio — nunca `decisao-tomada`, que diria que a
#: escolha foi nossa.
O_APARELHO_RECUSA = "o-aparelho-recusa"

#: O domínio. Valor fora daqui reprova, de propósito: acrescentar resposta nova
#: ao mapa é acrescentá-la aqui no mesmo gesto — e desde Z6-05 o gesto é no
#: portão (`DOMINIO_POR_SUFIXO["por_que_nao_aciona"]`), nunca mais aqui.
DOMINIO = _DOMINIO_DO_PORTAO["por_que_nao_aciona"]

#: ─────────────────────────────────────────────────────────────────────────
#: O TETO DA DÍVIDA — retrato de 24/08/2026 (baixado de 22/08), e ele só desce.
#: ─────────────────────────────────────────────────────────────────────────
#: PAGA em 24/08/2026 (Z6-05): `identidade.cor_do_aparelho@dualsense` (rádio)
#: saiu desta lista. Não é mais dívida — a medição de 23/08/2026 (`HANDSHAKE
#: 0x04`, `btmon`) nomeou a causa como `o-aparelho-recusa`, e causa do
#: APARELHO não é "ninguém escreveu o código". Ficam as três:
#:
#:   audio.saida_dedicada@dualsense          rádio — som no controle sem fio;
#:                                           o canal existe e responde, o
#:                                           conteúdo do payload não foi
#:                                           identificado;
#:   movimento.imu.perda@dualsense           cabo — o contador de reports do
#:                                           `corpo[11..14]`, medido e nunca lido;
#:   movimento.imu.perda@pro                 rádio — 1613 episódios num dia, e
#:                                           nada no produto os mostra.
#:
#: SUBIR ESTE NÚMERO É CONFISSÃO, não conserto: quem o subir está dizendo que a
#: casa passou a dever mais do que devia. Pagar uma dívida é BAIXÁ-LO no mesmo
#: commit — senão o teto vira folga e o portão para de morder.
#:
#: ─────────────────────────────────────────────────────────────────────────
#: SUBIU PARA 23 EM 03/09/2026, e a confissão vem com a distinção que importa.
#: ─────────────────────────────────────────────────────────────────────────
#: **A CASA NÃO PASSOU A DEVER MAIS. A MEDIÇÃO PASSOU A DIZER.** As vinte
#: células novas saíram da leva "as setenta e nove células mudas": oito agentes
#: responderam `aciona` onde NINGUÉM tinha respondido — as mudas caíram de 208
#: para 47 —, e vinte dessas respostas foram `não, e a razão é dívida NOSSA`.
#:
#: A dívida existia antes e não tinha nome. Uma célula muda não é uma casa sem
#: dívida: é uma casa que não sabe. O teto de 3 aferia o que estava ESCRITO,
#: não
#: o que era verdade — e é por isso que subi-lo aqui é o gesto honesto, e
#: mantê-lo em 3 apagando as respostas seria o desonesto.
#:
#: **AS VINTE, por família:**
#:
#:   áudio (7)        alto_falante, microfone, microfone.mudo,
#:                    microfone.volume (cabo e rádio), saida_dedicada e o
#:                    payload_do_degrau dela — todas do DualSense
#:   vibração (10)    haptics_vcm@dualsense (os dois lados) e rumble
#:                    direito/esquerdo do `pro` e do `sn30`, nos dois lados
#:   gatilho (2)      `gatilho.leitura@dualsense`, cabo e rádio
#:   o resto (4)      identidade.pareamento, movimento.imu.perda@pro (rádio),
#:                    plataforma.vigia_zumbi@pro
#:
#: **A REGRA NÃO MUDOU, e é o que impede este número de virar folga:** daqui
#: para a frente ele só desce. Quem pagar uma delas baixa o teto no mesmo
#: commit; quem quiser subi-lo de novo escreve, como está escrito aqui, por que
#: a casa passou a dever mais — ou por que a medição passou a dizer mais.
#:
#: ─────────────────────────────────────────────────────────────────────────
#: SUBIU PARA 25 EM 06/09/2026, e de novo a casa NÃO passou a dever mais.
#: ─────────────────────────────────────────────────────────────────────────
#: As duas células novas são `vibracao.rumble.ff@pro`, cabo e rádio, e vêm da
#: leva que levantou na FONTE as 38 células `nao-medido` do Nintendo Pro.
#:
#: **É A MESMA FALTA que já estava confessada**, e é isso que precisa ficar
#: escrito para ninguém a ler como dívida nova: as quatro células de
#: `vibracao.rumble.direito@pro` e `vibracao.rumble.esquerdo@pro` já diziam
#: `divida` desde 03/09, com a razão «o Hefesto simplesmente não tem escritor
#: de force feedback para controle externo» — e as duas linhas filhas DECLARAM,
#: no próprio `detalhe`, que não repetem o levantamento e apontam para
#: `vibracao.rumble.ff@pro`. A linha DONA do levantamento é que estava muda.
#:
#: Ficar em `nao-medido` seria dizer «ninguém olhou para o aparelho», e
#: olharam: o caminho (`EV_FF`/`FF_RUMBLE` no nó de gamepad) está lido no
#: driver e a ausência do escritor está medida por `grep` na árvore. A escolha
#: era entre um número honesto e uma célula que mente calada.
#:
#: **O LEVE QUE ISSO DEIXA, e ele baixa QUATRO de uma vez:** um escritor de
#: force feedback para externo fecha as SEIS células juntas (`ff`, `direito`,
#: `esquerdo`, nos dois lados) e este teto cai para 19. Quem, em vez disso,
#: decidir que as filhas não devem recontar o que a mãe já conta, colapsa as
#: quatro delas e baixa o teto para 21 sem escrever uma linha de produto.
#:
#: ─────────────────────────────────────────────────────────────────────────
#: DESCEU PARA 23 EM 06/09/2026 (SPECS-A-PROCEDENCIA-01), e desceu pelo MOTIVO
#: CERTO — que é para isso que este número está aqui.
#: ─────────────────────────────────────────────────────────────────────────
#: As duas células que saíram são `audio.microfone.volume@dualsense`, cabo e
#: rádio. Elas diziam `divida`, e não era: a decisão está DATADA no código —
#: `core/backend_pydualsense.py`, SOM-SEMPRE-01, deixa o volume do microfone
#: FORA da chamada de propósito, porque o dono do microfone no Linux é o kernel
#: (AUDIO-OWNER-01). As duas passaram a `decisao-tomada`.
#:
#: **NENHUMA dívida foi paga com código nesta descida**, e é isso que precisa
#: ficar escrito para ninguém a ler como trabalho feito: o que mudou é a
#: CLASSIFICAÇÃO, não o produto. A diferença importa porque `divida` chama
#: alguém para trabalhar e `decisao-tomada` não — as duas células estavam na
#: fila de quem procura o que fazer, e não havia nada a fazer nelas. O achado é
#: da A-RECUSA-QUE-CITOU-O-MAPA-01 §4.4.
#:
#: ESTE ARQUIVO NÃO ESTAVA NA `posse:` DA SPECS-A-PROCEDENCIA-01. Ele foi
#: tocado porque a mudança do mapa move este número por construção — o
#: `test_o_teto_e_um_numero_deste_arquivo_e_nao_do_csv` exige que o teto seja
#: exatamente a conta de hoje —, e deixá-lo velho entregaria a suíte vermelha a
#: quem costura. Está declarado na entrega daquela sprint.
#:
#: ─────────────────────────────────────────────────────────────────────────
#: SUBIU PARA 24 EM 08/09/2026, e subir é DIZER QUE A CASA PASSOU A DEVER MAIS
#: ─────────────────────────────────────────────────────────────────────────
#: **O número já era 24 desde 07/09 e ninguém viu.** O teto ficou em 23 e a
#: suíte carregou esta vermelha por um dia inteiro — a leva de 08/09 encontrou
#: a régua já reprovando na BASE (medido: base 24, branch 24, ZERO células
#: entraram com o merge). Não é dívida nova de hoje; é um teto que parou de
#: bater com a realidade e uma reprova que virou paisagem.
#:
#: QUANDO CRUZOU, e o commit é nomeado: `ef61c628` (07/09, *"as 53 células
#: mudas do Pro e do 8BitDo respondidas no fonte do driver"*). O saldo dele
#: foi +2 -1:
#:
#:   ENTRARAM  `combinacao.rumble_simultaneo@pro`, cabo E rádio
#:   SAIU      `audio.saida_dedicada.payload_do_degrau@dualsense`, rádio
#:
#: E AS DUAS QUE ENTRARAM SÃO DÍVIDA DE VERDADE, não erro de classificação —
#: é a diferença que importa aqui. Aquele commit foi LER o fonte do
#: `hid-nintendo` e responder o que estava mudo; o que ele descobriu foi que o
#: rumble simultâneo no Pro é coisa que o driver permite e o Hefesto não faz.
#: Uma célula muda virou uma célula que CHAMA alguém para trabalhar. É
#: exatamente o que este número existe para tornar visível, e por isso ele
#: sobe em vez de a régua ser afrouxada.
#:
#: A REGRA NÃO MUDA: pagar baixa o teto no mesmo commit. O que muda é que o
#: teto volta a ser a conta de hoje, que é o que o
#: `test_o_teto_e_um_numero_deste_arquivo_e_nao_do_csv` cobra — e um teto que
#: não bate transforma a régua inteira em ruído que se aprende a ignorar.
TETO_DA_DIVIDA = 24


def _linhas(caminho: Path | str) -> list[dict[str, str]]:
    texto = Path(caminho).read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(texto)))


def _cabecalho(caminho: Path | str) -> list[str]:
    texto = Path(caminho).read_text(encoding="utf-8")
    return next(csv.reader(io.StringIO(texto)))


def _celula(linha: dict[str, str], coluna: str) -> str:
    return (linha.get(coluna) or "").strip()


def populacao(caminho: Path | str) -> list[tuple[str, str]]:
    """As células em que a casa MEDIU e o produto NÃO ACIONA.

    Lê `de_onde_sei` e `aciona`, e NUNCA a coluna que este arquivo confere: uma
    população derivada da própria coluna conferida encolheria junto com o
    descuido, e o portão ficaria verde exatamente quando alguém esquecesse de
    responder.
    """
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
    """Toda célula que se declara DÍVIDA, esteja ou não na população.

    Conta o arquivo inteiro de propósito: uma dívida escrita numa célula que o
    recorte de hoje não alcança continua sendo dívida, e o teto existe para
    contar o que a casa deve — não o que este recorte enxerga.
    """
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


# ── as quatro regras ────────────────────────────────────────────────────────


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
    """A promessa da regra 3, exercida — senão ela é só uma frase no docstring.

    Um mapa em que TODA célula da população virou `decisao-tomada` continua
    verde. É
    isto que separa este portão do que nunca foi escrito: ele não cobra a
    lacuna, cobra a dívida.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as pasta:
        # A POPULAÇÃO **E** AS DÍVIDAS DE FORA DELA — corrigido em 03/09/2026.
        # Este teste trocava só a lista da função de população e exigia zero
        # dívida no fim,
        # o que só valia enquanto toda dívida estivesse dentro dela. A leva das
        # células mudas escreveu `divida` em vinte células cujo `de_onde_sei`
        # não é `medido`, e o `conta_dividas` DECLARA que isso é legítimo:
        # *"uma dívida escrita numa célula que o recorte de hoje não alcança
        # continua sendo dívida"*. Quem estava errado era a suposição do teste,
        # não o dado — então ele passa a trocar o que de fato precisa trocar
        # para exercer o que promete: que `decisao-tomada` pode crescer.
        alvos = set(populacao(MAPA)) | set(conta_dividas(MAPA))
        falso = _csv_de_mentira(
            Path(pasta) / "mapa.csv",
            trocas={chave: DECISAO for chave in alvos},
        )
        assert len(conta_dividas(falso)) == 0
        assert not [chave for chave in populacao(falso) if not respostas(falso).get(chave)]


# ── as duas provas de que a régua é régua ───────────────────────────────────


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
    assert len(antes) == 43, (
        f"o recorte de 07/09/2026 tinha 43 células medidas e não "
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


#: O "ou EXPLICADO" do nome deste teste, que até 29/08/2026 não existia no
#: código: valor do domínio que ninguém usa HOJE e que fica assim mesmo, com a
#: razão datada. Sem esta porta, a única saída para um valor que deixou de ser
#: usado era apagá-lo — e apagar palavra porque o último caso dela foi
#: CONSERTADO é o avesso do que este arquivo quer.
#:
#: A porta é estreita de propósito: entrar aqui exige escrever por que a
#: palavra sobrevive à ausência de uso, e a lista é lida na reprovação.
#: VAZIO DESDE 03/09/2026, e a razão é a melhor possível: `so-ela-decide`
#: VOLTOU AO USO. A leva das células mudas o escreveu de novo — há linha em que
#: o produto pode e a escolha é dela, exatamente o estado que a palavra nomeia,
#: e que a reserva de 29/08 previa que voltaria (*"a ONDA-CONTROLES-07 e a 08
#: nascem exatamente nele"*).
#:
#: A reserva sai porque a reserva é para o que NÃO tem uso; mantê-la sobre um
#: valor vivo esconderia o dia em que ele morrer de novo. É o próprio teste
#: quem manda, com essas palavras.
#:
#: O TEXTO DE 29/08 FICA AQUI, fora do dicionário, porque ele registra por que a
#: palavra sobreviveu ao dia em que ninguém a usava — e é esse registro que
#: impede a próxima pessoa de apagá-la na próxima folga:
#:
#:     "O último uso era `movimento.acelerometro@dualsense`, nos dois lados, e
#:     ele saiu porque a causa FOI RESOLVIDA: ela decidiu (*'não era pra ele
#:     sair. era pra ele FUNCIONAR'*), o produto passou a ler `ABS_X/Y/Z` e a
#:     célula virou `aciona=sim`. A palavra fica porque o ESTADO que ela nomeia
#:     — o produto pode, e a escolha é dela — não deixou de existir."
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
    """Valor de domínio que ninguém usa é vocabulário morto — ou é dívida de fila.

    Os quatro estavam em uso em 22/08/2026. Se um deixar de estar, há DUAS
    saídas, e a escolha é de quem causou a saída: tirá-lo do domínio no mesmo
    gesto, ou declará-lo em `RESERVADOS` com a razão datada de por que a
    palavra sobrevive sem uso. O que o teste recusa é a terceira, que é deixar
    o vocabulário apodrecendo calado.
    """
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
