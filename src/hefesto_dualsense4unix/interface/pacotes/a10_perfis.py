#!/usr/bin/env python3
"""O pacote da aba `10` Perfis.

ESTA ABA JÁ ESTAVA MARCADA, e não por mim: o outro agente pôs **77 endereços**
(`data-hef`) e 11 gestos nela em 31/08, com um esquema de nomes próprio. Os dois
convivem — o nome do atributo não é o contrato; o contrato é este despachante.

O QUE TEM DONO: o perfil em vigor (`active_profile`) e o travamento do
autoswitch (`autoswitch_locked`), que é o que diz se a troca automática está
segurada.

OS DEZ PRIMEIROS A GANHAR DONO — 01/09/2026, em duas levas:

    selecionar          a célula do nome, na lista. Abre o perfil no editor.
    ativar              `profile.switch`
    voltar-a-de-ontem   `restaurar_do_historico` + reaplicar + `launch_env.refresh`
    ---- a segunda leva ----------------------------------------------------
    editor.nome         renomeia: `save_profile` do nome novo + `delete_profile`
    editor.ambiente     troca a REGRA: `from_simple_choice` + `save_profile`
    editor.jogo         o programa (ou o appid) dentro da regra
    detectar            o jogo da Steam em foco, de `window_detect_last_class`
    novo                um perfil em branco, com a regra do jogo em foco
    duplicar            `model_copy` com "(cópia)" no nome, e o editor abre nela
    remover             `delete_profile`, com a pergunta NO RÓTULO do botão

A SEGUNDA LEVA SÓ FOI POSSÍVEL POR TRÊS CORREÇÕES, e nenhuma é do daemon:

1. o clique passou a trazer `valor` — o `value` do `<input>`/`<select>`. A
   primeira leva parou exatamente aqui: *"o ouvinte manda `texto:
   alvo.textContent`, que num `<input>` é vazio"*;
2. os quatro campos ganharam `data-hef-alvo="valor"` no gerador. Sem isso a
   pintura APAGAVA as opções dos dois `<select>` (medido: 5 → 0 e 15 → 0) e
   deixava os dois `<input>` com o texto do MOCKUP para sempre;
3. `pacote()` passou a mandar `editado=` para o produto. Sem isso o editor
   pintava o perfil ATIVO enquanto os botões agiam sobre o ESCOLHIDO — e ligar
   o campo Nome seria ela renomear um perfil olhando o nome de outro.

NÃO SOBRA NENHUM SEM DONO — 03/09/2026, e os DOIS ÚLTIMOS fecharam no fim do
dia:

    editor.prioridade   o `<input type=range>` que ela pediu — era o ÚNICO
                        campo do editor sem NENHUM caminho de escrita
    editor.estilo       escolher um estilo APLICA a receita: gatilho, degrau de
                        vibração e a cor de cada controle, de uma vez

São TREZE gestos com dono. As duas decisões são dela, do mesmo dia: *"Slider,
como você pediu"* e *"Construir o motor"* — e as receitas moram em
`profiles/estilos_de_jogo.py`, num lugar só, nunca digitadas aqui.

RECUSA-CHEGA-NA-TELA-01 — A REGRA DE QUAL EXCEÇÃO LEVANTAR, e ela não é gosto.
`hefesto_vivo._recusou_dizendo` pinta a tarja **só para `RuntimeError`**; um
`ValueError` sai no `stderr` do processo que lançou a janela e mais nada. O
contrato está escrito lá: `RuntimeError` é *"o produto recusou, e a frase VAI
PARA A TELA"*; `ValueError` é *clique inválido*, frase para quem programa.

**ESTA ABA VINHA VIOLANDO O CONTRATO EM NOVE FRASES**, e a mais cara delas
tinha teste verde. Medido em 03/09/2026, dirigindo a aba no produto instalado —
clique de verdade no "Ativar" com o perfil ativo já escolhido:

    [gesto falhou] ativar: “meu_perfil” já é o perfil que está valendo…  (stderr)
    tarjas na tela: []                                                   (o DOM)

A frase é inequivocamente DELA (*"Escolha outro na lista da esquerda e clique em
Ativar"*), a cura de 02/09 a escreveu com cuidado, o
`test_ativar_nao_diz_aplicado_sobre_o_perfil_que_ja_vale` a provou — e ela nunca
chegou à tela. É a forma de defeito que o próprio `_recusou_dizendo` nomeia:
*alguém curou o caminho e provou a cura num caminho que ela não usa.* Sobrou
UM `ValueError` neste arquivo — o do `selecionar`, que fala de um clique sem
nome de perfil e é a única frase daqui escrita para quem programa.

A LISTA PASSOU A CABER INTEIRA — 02/09/2026. O `<tbody>` publicado tem catorze
linhas porque catorze cabiam na figura, e a pasta dela tem **33 perfis**: os
outros dezenove não existiam na tela, e com eles nove dos dez botões desta aba,
que agem sobre o perfil ESCOLHIDO. A lista virou um `blocos` — ver
`_html_da_lista`, que também explica por que a régua do mockup não conta esta
entrega.

E A ABA PAROU DE PERGUNTAR SÓ AO DAEMON quem está valendo — ver `_valendo`. Com
`active_profile: null`, que é o estado da máquina dela hoje, três guardas se
desligavam ao mesmo tempo.

O QUE A ONDA2-10 ACRESCENTOU — 04/09/2026, as decisões do PO:

    [01] o CADEADO e o PONTO DE ALERTA. `editor.ambiente.travado` e
         `editor.ambiente.recado` saíam do produto e caíam no vazio — não havia
         endereço na página. Agora há, e junto veio a metade que ninguém tinha
         olhado: o `<select>` travado ficava com o **"Jogo" do mockup**, porque
         `escrever()` não tem onde pousar um `—` num `<select>` que não o
         oferece. Ver `aba10.opts(travessao=True)`.
    [02] o FIM da frase da exigência escondida, reescrito para ESTA tela — ver
         `FIM_DA_EXIGENCIA_AQUI`. A frase do produto está certa na janela GTK e
         errada aqui, e por isso a substituição é neste arquivo.
    [04] o CAMPO DO JOGO SE CORRIGE: `editor_jogo` e `detectar` devolvem
         `editor.jogo` na forma canônica junto com o desfecho. É o único
         instante em que a tela pode fazê-lo — o campo está em
         `CAMPOS_QUE_ELA_DIGITA` e o tique não o repinta.

    As decisões [03] e [05] são de DESENHO e moram no `aba10.py`.

O QUE ESTA ABA NÃO SABE FAZER, e é o teto de tudo o que está acima: **o daemon
não tem `profile.save` nem `profile.delete`.** Os 39 métodos que ele atende
trazem só `profile.switch`, `profile.list` e `profile.apply_draft` — gravar e
apagar perfil roda no processo da janela, direto no disco, e por isso todo gesto
que escreve tem de avisar o daemon depois (`profile.switch` para reaplicar,
`launch_env.refresh` para a antecipação por appid).
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

# O IMPORT É DE MÓDULO, e não de dentro da função — 01/09/2026. O
# `portao_a_casa_sabe_e_o_produto_nao_faz` segue o fecho de IMPORT a partir do
# piloto que o lançador abre, e um `from … import` escondido dentro de uma
# função não entra nesse fecho: a camada do produto continuava aparecendo como
# "promessa sem caminho" mesmo depois de eu a ligar.
#
# O `sys.path` já tem o `src/` quando esta linha roda: `pacotes/__init__.py` o
# insere no import do pacote.
from hefesto_dualsense4unix.app.actions import perfis_web as _tela

from . import (
    PONTO_DO_ROTULO,
    SEM_NINGUEM_AQUI,
    TODOS_OS_LUGARES,
    Contexto,
    perfil,
    registrar,
)

#: CORRIGIDO EM 01/09/2026. Estava escrito que a lista "vem de `profiles.*`, não
#: do state_full" — e daí eu concluí que não tinha dono. `profile.list` é um
#: método vivo do daemon e responde agora; os 33 perfis dela estão em disco, em
#: `profiles_dir()`. Ter outro dono que não o `state_full` não é não ter dono.
SEM_DONO: dict[str, str] = {}


#: A ORDEM DAS CÉLULAS DA COLUNA "AJUSTE PRÓPRIO", da esquerda para a direita.
#:
#: POR QUE ELA MORA AQUI, e não sai de `perfis_web.SECOES_POR_CONTROLE`: aquela
#: é a lista do ESQUEMA — o que o perfil sabe guardar. Esta é a lista do
#: DESENHO, e as duas podem legitimamente divergir por um tempo quando ela
#: aprova uma coluna antes de o campo existir. Confundi-las faria a distribuição
#: casar célula com vizinha — a coluna do P2 mostrando o estado do P1, que é
#: pior que a coluna apagada.
#:
#: **AS DUAS CONVERGIRAM — 03/09/2026.** Este comentário dizia *"aquela é a
#: lista do ESQUEMA … quatro campos"* e o `mic` estava fora dela. Estava errado
#: por seis minutos de diferença entre duas worktrees: `3f757b77` (02:50) pôs o
#: campo no esquema e `7e64c2e3` (02:56) desenhou a coluna afirmando que ele
#: *"ainda não existe"*. As duas listas voltaram a ser a mesma — hoje são seis.
#:
#: E ELA NÃO PODE SAIR DO GERADOR. `interface/aba10.py` é um script: ele insere
#: o próprio diretório no `sys.path` e importa `monta`, que LÊ O REPOSITÓRIO no
#: import — num pacote instalado não há repositório, e todo consumidor deste
#: módulo passaria a exigir um. A segunda declaração é o preço; quem impede que
#: as duas divirjam é
#: `tests/unit/test_a_coluna_de_ajuste_proprio_da_aba10_e_dado.py`, que compara
#: esta lista com a `SECOES` do gerador, nome a nome e na ordem.
#:
#: **A SEXTA ENTROU EM 05/09/2026, e ela é a queixa dela** — *"a aba 10 tá com o
#: mesmo problema de antes. nada mudou."* O `sensores` chegou a
#: `ControllerOverrides` em 04/09 (`8f9589ba`) e esta lista ficou nos cinco por
#: um dia. O sintoma não era coluna trocada: era coluna AUSENTE. Medido com o
#: disco dela, `_secoes_do_controle` devolvia seis chaves, esta lista lia cinco,
#: e o `sensores` de um controle ficava guardado no JSON sem uma célula que o
#: mostrasse — enquanto a dica da linha, que sai do ESQUEMA, já contava seis.
SECOES_DA_COLUNA: tuple[str, ...] = (
    "leds", "triggers", "rumble", "speaker", "mic", "sensores")

#: AS COLUNAS QUE A TELA JÁ MOSTRA E O ESQUEMA AINDA NÃO GUARDA.
#:
#: Uma coluna aqui é uma DECLARAÇÃO com prazo, não uma licença: ela diz *"esta
#: coluna existe por decisão dela, e o campo está a caminho"*. Enquanto o campo
#: não chega, `perfis_web._secoes_do_controle` não devolve a chave, o pacote lê
#: `None` e a célula fica apagada em todo perfil real — a tela pronta para o
#: dado, sem inventá-lo.
#:
#: **ESTÁ VAZIA, e o `mic` saiu daqui em 03/09/2026 — sem sair sozinho.** Esta
#: nota prometia que ele sairia *"sozinho, sem ninguém precisar lembrar: no dia
#: em que `ControllerOverrides` ganhar o campo"*. Esse dia era o MESMO dia, seis
#: minutos antes (`3f757b77`), e nada saiu: uma isenção só some quando alguém a
#: relê, e a régua que a guardava — `test_toda_coluna_sem_campo_esta_declarada`
#: — é de uma direção só, de propósito (*"ela não reprova quando o campo
#: chega"*). Uma isenção que não reprova quando caduca é uma isenção eterna, e
#: por um dia ela cobriu a coluna do microfone apagada à força.
#:
#: A cura é a régua NOVA que fecha a outra direção:
#: `test_nenhuma_isencao_desta_lista_ja_caducou` reprova todo nome daqui que já
#: esteja no esquema, e diz para apagá-lo. Agora sai sozinho de verdade.
ESPERANDO_O_ESQUEMA: frozenset[str] = frozenset()


#: COMO A TELA CHAMA O QUE O PERFIL GUARDA — `match.type` no disco, uma frase
#: na coluna "Quando usar". A tradução mora aqui e não no JS: é vocabulário do
#: produto, e o desenho dela já fixou as palavras.
QUANDO = {"criteria": "Jogo", "any": "Todos — quando nenhum casa",
          "manual": "Só quando eu escolher"}


#: O PERFIL ESCOLHIDO NA LISTA — o que ela clicou por último, e o alvo dos
#: botões da aba. Vive AQUI, no pacote, e não na tela: o clique chega ao Python
#: e a pintura sai dele, então guardar no JS obrigaria o gesto a perguntar de
#: volta ao navegador o que ele acabou de mandar.
#:
#: NÃO É "O PERFIL ATIVO". São duas coisas, e a janela estável já as separa: o
#: ativo é o que está valendo agora no daemon; o escolhido é a linha em que o
#: editor está aberto. Confundi-los faria "Voltar à de ontem" agir sempre sobre
#: o que está valendo, mesmo com outra linha aberta no editor.
_ESCOLHIDO: str = ""


def _escolhido(todos: list[dict[str, Any]], ativo: str) -> str:
    """A linha aberta no editor: a última clicada, ou o perfil ativo.

    ELE DEIXA DE VALER SOZINHO quando o perfil sai do disco — apagado por fora,
    renomeado, o `HEFESTO_VARIANTE` trocado. Sem esta queda, "Voltar à de
    ontem" continuaria mirando um arquivo que não existe mais e a mensagem de
    erro falaria de um perfil que ela não vê na lista.

    A SINCRONIZAÇÃO INICIAL É ESCRITA AQUI DE PROPÓSITO, e a guarda é o que a
    torna segura de repetir: só grava quando a lista tem aquele nome. Na régua
    dos botões o `active_profile` é "regua" e nenhum perfil se chama assim,
    então nada é gravado e o estado do módulo continua limpo.

    FATO SUBSTITUÍDO — 02/09/2026, e é a segunda correção desta mesma linha.
    Estava escrito que, *"no mesmo lar de mentira do `conftest.py`"*,
    `load_all_profiles()` devolve **9 perfis** (os de fábrica, que ela semeia).
    **Sob o `pytest` ele devolve `[]`**: a `conftest.py:2114` põe
    `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` em TODO teste, e é justamente
    esse env que desliga o `_maybe_seed_presets`. Os nove eram reais — mas num
    processo SEM o pytest, que é onde a medição de 01/09 rodou. Conferido em
    02/09 com uma sonda dentro da suíte: `sorted(nomes) == []`.

    O QUE ISSO NÃO MUDA: a guarda continua segura de repetir. Com a lista vazia
    o `ativo` nunca está em `nomes`, então nada é gravado — que é o mesmo
    desfecho que a razão original previa por outro caminho.
    """
    global _ESCOLHIDO
    nomes = {p["nome"] for p in todos}
    if _ESCOLHIDO and _ESCOLHIDO not in nomes:
        _ESCOLHIDO = ""
    if not _ESCOLHIDO and ativo in nomes:
        _ESCOLHIDO = ativo
    return _ESCOLHIDO or ativo


#: A JANELA DA CONFIRMAÇÃO do "Remover", em segundos. Não é gosto: um armamento
#: sem prazo é uma armadilha — ela clica, se distrai, volta meia hora depois,
#: clica de novo e o perfil some sem que nada na tela tenha dito por quê.
SEGUNDOS_PARA_CONFIRMAR = 8.0

#: O QUE ACABOU DE ACONTECER — o toast do rodapé da janela estável, aqui.
#:
#: POR QUE ELE PRECISOU EXISTIR, e é defeito de PARIDADE, não de desenho: na
#: janela GTK **todo** gesto desta aba termina num `_toast_profile`
#: (`profiles_actions.py:4615`) — "Perfil removido: X", "Lista recarregada",
#: `mensagem_do_salvar`, `mensagem_de_ativacao`. Aqui só a RECUSA falava:
#: `RuntimeError` vira tarja (`hefesto_vivo._recusou_dizendo`) e o SUCESSO era
#: SILÊNCIO — o piloto anota `("aplicou", "")` e não escreve uma letra na tela.
#: Para os NOVE gestos desta aba que ESCREVEM NO DISCO DELA, silêncio no
#: sucesso é a mesma classe de defeito que o toast existe para curar: ela
#: renomeia, o campo volta ao normal, e nada diz que gravou.
#:
#: O RELÓGIO É MONOTÔNICO pela mesma razão do `_recados` do piloto: um acerto
#: de hora do sistema não pode fazer um desfecho de agora parecer de ontem.
_DESFECHO: tuple[str, float] | None = None

#: Quanto tempo o desfecho fica na tela. É o MESMO prazo da tarja de recusa do
#: piloto (`hefesto_vivo.SEGUNDOS_DO_RECADO = 30.0`): dois avisos da mesma
#: janela que sumissem em tempos diferentes seriam dois contratos para quem
#: olha, e ela olha os dois no mesmo canto.
SEGUNDOS_DO_DESFECHO = 30.0


def _com_a_carona(frase: str) -> str:
    """Repõe o wrapper que a Steam comeu, e junta a notícia à frase do gesto.

    CARONA-DO-WRAPPER-01 (16/08/2026), e **o desenho é dela**: *"nem precisa ter
    um botão na gui, mas ele se auto corrigir ao clicarmos em aplicar ou salvar
    o perfil seja dentro ou fora da guia de perfis."*

    O QUE ELA CURA: a Steam guarda UMA linha de `LaunchOptions` por jogo, e
    qualquer coisa escrita nela substitui a chamada do `hefesto-launch` em
    silêncio. Sem o wrapper, o `launch_env` que o daemon materializa nunca é
    lido — o jogo é instruído a ignorar o vpad que nós criamos para ele. Nas
    palavras dela: *"parou de ser reconhecido no jogo, mas o perfil segue ativo
    no controle com tudo funcionando"*.

    POR QUE A FUNÇÃO DE MÓDULO E NÃO O `pegar_carona_no_gesto`: aquele é método
    do `CaronaDoWrapperMixin` e despacha uma thread própria para devolver no
    laço do GTK (`despachar` → `GLib.idle_add`). **O gesto já está em thread**
    (`hefesto_vivo._gesto`, `trabalhar()`), que é exatamente onde `passada()`
    declara ter de rodar — *"Só em thread worker: lê disco e o `/proc`"*. Chamar
    `passada()` daqui é o mesmo trabalho sem a segunda troca de thread.

    `ligada()` É O PORTÃO E NÃO UM `if` MEU: ele é o mesmo que a janela estável
    consulta, e é o que desliga a carona na suíte (a `conftest.py:2308` põe
    `HEFESTO_CARONA_WRAPPER=0`). Uma régua desta aba não vai ao `/proc` dela.

    NUNCA LEVANTA. Ela é efeito colateral de um gesto que já deu certo: uma
    exceção aqui transformaria uma ativação bem-sucedida em tarja de recusa.

    O QUE NÃO VEIO JUNTO, e fica escrito para não sumir: a **vigia**. A janela
    estável arma um tique de 45 s (`_carona_armar_vigia`) que repergunta "a
    Steam já fechou?" até o reparo caber, e a memória do episódio
    (`_carona_ja_avisado`) que impede o mesmo aviso a cada gesto. As duas moram
    no mixin, dependem do `GLib.timeout_add` da janela, e são território do
    piloto — não deste pacote.
    """
    from hefesto_dualsense4unix.app.actions import carona_do_wrapper as carona

    if not carona.ligada():
        return frase
    try:
        resultado = carona.passada(completa=True)
    except Exception:
        # Nem o log: um pacote de aba não tem logger, e o gesto já deu certo.
        return frase
    return f"{frase} · {resultado.frase}" if resultado.frase else frase


def _dizer(frase: str, **campos: Any) -> dict[str, Any]:
    """Anota o desfecho E o devolve para a tela AGORA, sem esperar o tique.

    `campos` SÃO OS ENDEREÇOS QUE O GESTO CORRIGE NA HORA, e eles viajam no
    mesmo embrulho — 04/09/2026, decisão [04] do PO. O caso que os pediu é o do
    "Nome do Jogo": os campos que ela DIGITA são omitidos do tique
    (`CAMPOS_QUE_ELA_DIGITA`, para a pintura não apagar o que ela está
    escrevendo), então o único instante em que a tela pode devolver a forma
    canônica do que ela colou é a resposta do PRÓPRIO gesto. Sem isto, o
    endereço da loja fica no campo até ela trocar de perfil.

    O CAMINHO DE VOLTA JÁ EXISTIA e ninguém desta aba o usava: um gesto que
    devolve um dicionário tem a carga pintada na hora (`hefesto_vivo._deu_certo`
    → `window.__hef.pintar`), no mesmo vocabulário `endereço → valor` da
    pintura — logo o tique seguinte não briga, sobrescreve com o mesmo valor.

    POR QUE NA HORA E NÃO NO TIQUE, e o argumento é o do piloto, palavra por
    palavra: *"Meio segundo entre o clique e a resposta basta para ela clicar de
    novo achando que o primeiro não pegou"*. Meio segundo é o tique desta aba.

    **O `mesa:` NÃO É ENFEITE.** O `_deu_certo` entrega a carga CRUA ao
    `window.__hef.pintar`, que lê `p.blocos`, `p.mesa`, `p.colunas` e
    `p.vazios` — e mais nada. Um dicionário achatado (`{"perfis.desfecho": …}`)
    passa por todos os laços sem casar com nenhum: **zero escrito, zero erro**,
    que é a forma exata do defeito que esta casa chama de *ausência de notícia
    lida como sucesso*, e que já custou dois dias ao `blocos` do `normalizar`.
    O `pacote()` chega ao JS com esse embrulho porque `pacotes.normalizar` o
    põe; um gesto não passa por lá, e põe o seu.
    """
    _anotar(frase)
    return {"mesa": {"perfis.desfecho": frase, **campos}}


def _anotar(frase: str) -> None:
    """Guarda o desfecho do gesto, para o tique seguinte levá-lo à tela.

    ELE NÃO ESCREVE NO DOM, e não pode: os gestos rodam em thread
    (`hefesto_vivo._gesto`, `trabalhar()`), e só o laço do GTK toca a página. O
    caminho é o mesmo do `_rotulo_do_remover` — o estado mora no Python e a
    pintura o busca a cada 100 ms.

    FRASE VAZIA APAGA. É o que faz um gesto que não tem notícia limpar a notícia
    do anterior, em vez de deixar a tela afirmando um desfecho velho.
    """
    global _DESFECHO
    _DESFECHO = (frase, time.monotonic()) if frase else None


def _desfecho_para_a_tela() -> str:
    """O desfecho ainda vivo, ou vazio — e a PODA mora aqui, no leitor.

    Igual ao `_recados_para_a_tela` do piloto, e pela razão de lá: um
    `timeout_add` por desfecho seria um temporizador por clique, e o que apaga a
    frase passaria a ser um agendamento que a troca de aba não cancela. Aqui a
    conta é feita quando alguém pergunta — que é a cada tique, e é o mesmo
    instante em que o valor vai para a tela.
    """
    global _DESFECHO
    if _DESFECHO is None:
        return ""
    frase, quando = _DESFECHO
    if time.monotonic() - quando >= SEGUNDOS_DO_DESFECHO:
        _DESFECHO = None
        return ""
    return frase


#: OS ENDEREÇOS QUE A PÁGINA PUBLICADA **NÃO SABE RECEBER** — e emiti-los não é
#: um valor que não aparece: é a página se DESMONTANDO a cada meio segundo.
#:
#: A CAUSA, e ela é do pintor, não desta aba: `escrever()` termina em
#: `el.textContent = t` (`hefesto_vivo.py:170`), e `textContent` num elemento que
#: tem FILHOS-ELEMENTO apaga todos eles. O desvio existe — `data-hef-alvo` —, mas
#: quem o escreve é o GERADOR, no HTML, e o HTML publicado só muda por ato dela.
#:
#: MEDIDO em 02/09/2026 sobre `interface/paginas/10-perfis.html`, contando os
#: filhos-elemento de cada alvo (a régua está em
#: `tests/unit/test_a_guarda_do_perfil_nao_apaga_a_tabela.py`):
#:
#:     endereço                 tag      elementos  filhos  o que some
#:     guarda.linhas            tbody            1       4  as 4 linhas, com 24 endereços
#:     guarda.secao             span            16       2  o glifo SVG da seção
#:     editor.prioridade.dica   span             1       2  o TRILHO e o número ao lado
#:
#: **É ISTO QUE ELA FOTOGRAFOU.** A tabela `Controle / Ajuste próprio / ID da
#: peça` mostrando um `2` sozinho é o `guarda.linhas` escrevendo `"2"` no
#: `<tbody>`; e o *"Prioridade 1 de 200. O maior vence a disputa…"* que ela leu
#: no lugar do trilho é o `editor.prioridade.dica` comendo o trilho e o número —
#: a frase dela, *"esse texto em perfis nem faz sentido mais"*, é sobre uma
#: FRASE QUE ENGOLIU UM CONTROLE DESLIZANTE, não sobre o texto em si.
#:
#: FATO DERRUBADO — 02/09/2026, e o enunciado desta frente o repetia. Aqui
#: estava escrito que `editor.prioridade` também não sai, porque o
#: `data-hef-alvo="largura"` estaria *"já escrito na BANCADA (`aba10.py`),
#: esperando o ato de publicar DELA"*. **Ela já publicou.** O commit `70b58116`
#: levou a aba inteira ao produto, e o atributo está na linha 1162 das DUAS
#: páginas — a bancada e a publicada, que hoje são byte-idênticas
#: (`diff mockup/10-perfis.html interface/paginas/10-perfis.html` é vazio, e
#: `mockup/DIVERGENCIAS.md` não tem seção da aba 10). Enquanto este nome ficou
#: na lista, a barra da prioridade continuou nos 90% do desenho para um perfil
#: em 1 de 200 — a tela afirmando o que não mediu, com o conserto no disco há
#: um commit. Ele SAI da lista, e o `escrever()` do piloto escreve a largura.
#:
#: **PARA DESTRAVAR OS QUE FICAM**, e cada um tem um dono diferente:
#:
#:   guarda.linhas       não tem conserto e não precisa: é o `<tbody>`, um
#:                       CONTINENTE. Nunca houve valor para escrever nele.
#:                       (A lista de perfis tinha o mesmo formato e ganhou
#:                       conserto por OUTRA porta — ver `_html_da_lista`.)
#:   editor.prioridade.dica  **a frase JÁ FOI APROVADA e não chega à tela** —
#:                       correção de fato, 02/09/2026. Aqui estava escrito que
#:                       *"o texto novo é decisão DELA"*; ela decidiu (decisão
#:                       nº11, *"Quando dois perfis servem ao mesmo tempo, o de
#:                       número maior entra."*) e o texto está em
#:                       `perfis_web._pacote_do_editor`. O que segura é ESTA
#:                       lista, e por uma razão que continua de pé: o alvo é um
#:                       `<span>` com DOIS filhos-elemento (o trilho e o
#:                       número), e `textContent` os apagaria. A tela mostra
#:                       hoje o `title=` estático do desenho, que não é nem a
#:                       frase velha nem a nova. **Para destravar, o pintor
#:                       precisa de um `data-hef-alvo` que escreva ATRIBUTO
#:                       (`title=`)** — `hefesto_vivo.py`, fora do território
#:                       desta frente; está no relatório.
#:   editor.estilo       **não há valor a escrever, e escrever apaga o `—` que
#:                       ela pediu** — 02/09/2026. O perfil não tem campo de
#:                       Estilo (`perfis_web` devolve `estilo: None`), então o
#:                       que sairia daqui é o vazio. E o `escrever()` do piloto
#:                       troca vazio por `'—'` ANTES do ramo `valor`
#:                       (`hefesto_vivo.py`, `const t = vazio ? '—' : …`): num
#:                       `<select>` cuja opção vazia tem `value=""`, escrever
#:                       `'—'` passa a guarda pelo TEXTO da opção e depois
#:                       deixa `selectedIndex = -1` — o campo renderiza EM
#:                       BRANCO, e `el.value` nunca volta igual ao escrito, o
#:                       que faz o contador somar +1 a cada visita. O desenho já
#:                       nasce com a opção certa marcada; a tela só precisa não
#:                       estragá-la.
#:                       **E O MOTOR NÃO MUDA ISTO — 03/09/2026.** Aqui estava
#:                       escrito que *"quem lhe dá valor de verdade é a
#:                       ONDA-PERFIS-04"*. O motor nasceu e o campo GRAVA; o que
#:                       ele nunca vai ter é valor a MOSTRAR, porque o estilo é
#:                       um verbo e não um campo do `Profile` — ver
#:                       `editor_estilo`. Este nome fica nesta lista para
#:                       sempre, e agora por uma razão de projeto em vez de uma
#:                       espera.
#: **`guarda.secao` SAIU DESTA LISTA — 03/09/2026**, e o motivo dela caducou por
#: inteiro. Estava escrito aqui que *"nenhum dos cinco alvos de hoje
#: (texto·largura·fundo·valor·html) alcança uma classe"*. O piloto ganhou o alvo
#: `classe` (`hefesto_vivo.py`), e o comentário dele já nomeava este caso entre
#: os cinco que o alvo destrava: *"a coluna 'Ajuste próprio' da Perfis"*. As
#: vinte células do desenho e as dezesseis da página publicada carregam
#: `data-hef-alvo="classe"`, e o produto passou a acender e apagar cada uma.
#:
#: O ENDEREÇO CHEGOU AO PRODUTO SEM PASSAR POR ELA, e isso é regra, não atalho:
#: `data-hef-alvo` está em `check_o_desenho_aprovado.INVISIVEIS`, então
#: `--publicar-enderecos 10` o levou com o desenho intacto — *"um `data-campo`
#: novo num elemento que já existia não muda nada do que ela vê: não há o que
#: aprovar"*. O DESENHO desta aba (a coluna do microfone e as oito dicas que
#: saíram) continua na bancada, esperando o `--publicar` dela.
NAO_PINTAVEIS = ("guarda.linhas", "editor.prioridade.dica",
                 "editor.estilo")

#: AS CHAVES QUE SAEM DAQUI E A PÁGINA NÃO TEM ONDE PÔR — o inventário, com a
#: razão medida de cada uma. É a lista irmã do `SEM_ENDERECO` da aba 06, e ela
#: existe pela mesma razão: **órfão calado é defeito; órfão declarado é
#: inventário.** A régua que a cobra é
#: `tests/unit/test_a_aba_perfis_manda_para_um_endereco_que_existe.py`.
#:
#: A DIFERENÇA PARA `NAO_PINTAVEIS`, e as duas listas não se confundem:
#: ali estão os endereços que a página TEM e que escrever DESTRÓI; aqui estão
#: os valores que a página NÃO TEM — eles caem no vazio, sem estrago e sem
#: notícia. Um valor desta lista nunca aparece na tela nem no contador.
#:
#: MEDIDO em 02/09/2026 contra as duas páginas, que hoje são byte-idênticas:
SEM_ENDERECO = {
    # **OS DOIS DO AMBIENTE SAÍRAM DAQUI — 04/09/2026, decisão [01] do PO.**
    # Estava escrito que *"o seletor travado não tem marca no desenho"* e que
    # *"a frase da válvula não tem lugar no desenho"*, e as duas metades caíram
    # no mesmo commit: o gerador ganhou o CADEADO (`aba10.marca_com_dica`), com
    # a `classe` acendendo em `editor.ambiente.travado` e a frase no hover, por
    # `editor.ambiente.recado`. Eles esperam agora o `--publicar` DELA, e é isso
    # que `ESPERANDO_A_PUBLICACAO` declara — a lista logo abaixo.
    #
    # OS DOIS DO ESTILO FICAM, e a razão é outra: o `estilo_travado` é `False`
    # em todo perfil desde 03/09 (o campo GRAVA), então uma marca de travado
    # ali nunca acenderia; e o `estilo_recado` é uma explicação PERMANENTE, não
    # uma ressalva — o `title` que o desenho já põe no rótulo "Estilo de Jogo"
    # diz a mesma coisa, no mesmo hover, sem um endereço a mais. O PO decidiu o
    # cadeado para o "Funciona em" e o ponto para o "Nome do Jogo"; não para
    # este campo.
    "editor.estilo.travado": "o campo GRAVA desde 03/09 (`estilo_travado` é "
                             "sempre `False`) — uma marca de travado aqui "
                             "nunca acenderia",
    "editor.estilo.recado": "a frase que explica por que o campo volta ao "
                            "travessão (`perfis_web.ESTILO_APLICA_E_SAI`) diz "
                            "o mesmo que o `title` do rótulo, no mesmo hover — "
                            "um segundo canal para o mesmo fato",
    # `quantos` é a SEGUNDA forma da mesma pergunta: `perfis.conta` tem
    # endereço (a página o mostra) e sai deste mesmo pacote. Medido: ninguém o
    # lê hoje — nem produto, nem régua. Fica declarado, e não apagado, porque
    # tirar emissão é decisão de quem tem a aba inteira na mão; declarado, ele
    # aparece nesta lista para quem for tomá-la.
    "quantos": "a contagem que a tela mostra é `perfis.conta`, e essa tem endereço",
    # `autoswitch_locked` é estado do daemon, e o desenho desta aba não o
    # mostra em lugar nenhum. Quem tem endereço para a troca automática é a aba
    # Sistema (`data-campo="hefesto-troca-de-perfil"`, em `09-sistema.html`).
    "travado": "a trava da troca automática não é desenhada nesta aba",
}

#: OS ENDEREÇOS QUE JÁ ESTÃO NA BANCADA E ESPERAM O ATO DELA — 03/09/2026.
#:
#: NÃO É UM `SEM_ENDERECO` MAIS FROUXO, e a diferença é o que cada lista afirma:
#: ali estão os valores que a PÁGINA NÃO TEM onde pôr — nem hoje, nem depois de
#: publicar; aqui estão os que o gerador JÁ marcou em `mockup/` e que só chegam a
#: `interface/paginas/` quando ela mandar. **Publicar é ato dela**
#: (`check_o_desenho_aprovado.py --publicar NN`), e nenhuma frente o faz.
#:
#: ELA PRECISOU EXISTIR, e o buraco era estrutural: a régua cobrava endereço nas
#: DUAS páginas, então marcar um campo novo no gerador reprovava sempre — a única
#: forma de ficar verde era publicar, que é justamente o que uma frente não pode
#: fazer. Sem esta lista, "dar endereço" e "publicar" viravam o mesmo ato.
#:
#: A RÉGUA CONTINUA MORDENDO NOS DOIS SENTIDOS
#: (`test_a_aba_perfis_manda_para_um_endereco_que_existe.py`): um nome daqui tem
#: de EXISTIR na bancada — senão não está esperando, está faltando — e tem de NÃO
#: existir ainda na publicada, senão a declaração envelheceu e é a régua se
#: desligando sozinha no dia em que ela publicar.
#: **ELA ESVAZIOU EM 03/09/2026, e não por decreto — por publicação.** O único
#: nome aqui era `guarda.plastico`, a barra da cor do plástico da
#: IDENTIDADE-VEM-DE-CIMA, e ele chegou ao produto pelo
#: `--publicar-enderecos 10`: `data-hef-alvo` e `data-hef` estão em
#: `check_o_desenho_aprovado.INVISIVEIS`, então a página foi copiada com o
#: DESENHO intacto — *"um `data-campo` novo num elemento que já existia não muda
#: nada do que ela vê: não há o que aprovar"*.
#:
#: FATO DERRUBADO no mesmo ato, e ele estava no comentário acima: *"nenhuma
#: frente o faz"* valia para o `--publicar`, que é dela, e foi lido como valendo
#: para publicação nenhuma. `--publicar-enderecos` existe exatamente para a
#: metade que NUNCA foi decisão dela, e estava inerte — o ramo que copia era
#: inalcançável (ver o comentário em `publicar_enderecos`). Com ele vivo, um
#: endereço novo deixa de esperar por ela.
#:
#: **E ELE CHEGOU NO MESMO DIA.** A tira do DESFECHO (`aba10.py`, sob o
#: cabeçalho do quadro) muda pixel: 15px de altura mais 7px de vão, tirados da
#: altura da lista. `--publicar-enderecos` a RECUSA dizendo *"o DESENHO mudou —
#: isto é decisão dela"*, que é exatamente o certo. Ela está declarada em
#: `mockup/DIVERGENCIAS.md` com o que ela vê enquanto espera: nada muda, e os
#: nove gestos que gravam no disco continuam mudos no sucesso.
#: VAZIA DESDE 03/09/2026 — ela mandou publicar as dez, e a `perfis.desfecho`
#: chegou à página que o produto renderiza. A régua
#: `test_o_que_espera_publicacao_sai_da_lista_quando_ela_publicar` é quem
#: cobrou: um nome que já está no publicado e continua declarado como à espera
#: vira ponto cego, porque a lista deixa de ser lida como fila e passa a ser
#: lida como decoração.
#:
#: O DICIONÁRIO FICA, e vazio: ele é o lugar combinado de quem escrever um
#: endereço novo na bancada antes de ela aprovar. Apagá-lo obrigaria a próxima
#: pessoa a reinventá-lo.
#:
#: **E ELE VOLTOU A TER UM NOME — 03/09/2026**, o `editor.prioridade.escolha`, o
#: punho do `<input type=range>` que ela pediu. **E O NOME SAIU EM 04/09/2026**:
#: a publicação das dez de `2a7d6583` levou o punho para
#: `interface/paginas/10-perfis.html`, onde o endereço aparece duas vezes. A
#: régua `test_o_que_espera_publicacao_sai_da_lista_quando_ela_publicar` acusou
#: no mesmo dia, e a instrução dela é a que se seguiu: *"Tire da lista no mesmo
#: commit."* Um nome publicado que continua declarado como à espera vira ponto
#: cego — a lista deixa de ser lida como fila e passa a ser lida como decoração.
#:
#: **E ELE VOLTOU A TER QUATRO — 04/09/2026, decisão [01] do PO.** O cadeado do
#: "Funciona em" e o ponto de alerta do "Nome do Jogo" MUDAM PIXEL: nascem
#: elementos que não existiam, ao lado de dois campos. Isso é DESENHO, e
#: `--publicar-enderecos` o recusa dizendo — que é exatamente o certo. Enquanto
#: ela não publicar, os quatro valores continuam saindo e caindo no vazio na
#: página que o produto renderiza; o que ela vê hoje não muda.
#:
#: **PAGA — 05/09/2026, e a régua foi quem cobrou.** Os quatro endereços (o
#: cadeado do "Funciona em" e o ponto de alerta do "Nome do Jogo", decisões [01]
#: e [02] do PO) chegaram a `interface/paginas/` na publicação de 05/09, e esta
#: lista ficou para trás — com
#: `test_o_que_espera_publicacao_sai_da_lista_quando_ela_publicar` VERMELHO no
#: `dev`. É exatamente o que ela nasceu para fazer: uma declaração que
#: envelheceu é a régua se desligando sem ninguém decidir isso.
#:
#: A LISTA FICA VAZIA E NÃO SOME: ela é o lugar onde a próxima dívida desta
#: espécie se declara, e as duas réguas que a cobram nos DOIS sentidos continuam
#: valendo — entrada aqui exige endereço FALTANDO no publicado, e endereço
#: faltando exige entrada aqui.
ESPERANDO_A_PUBLICACAO: dict[str, str] = {}


#: O FIM DA FRASE DA EXIGÊNCIA ESCONDIDA — decisão [02] do PO, 04/09/2026:
#: *"as duas frases prontas mandam a lugares que não existem aqui … Isso é
#: fato errado e se substitui."*
#:
#: **DEIXOU DE SER REMENDA EM 05/09/2026.** O conserto que o bloco abaixo
#: pedia — *"a frase factual devia sair de lá e o caminho, de cada tela"* — foi
#: feito: `simple_match.exigencia_invisivel` devolve só o FATO, e o caminho da
#: janela GTK virou `simple_match.CAMINHO_DA_JANELA_GTK`, somado por
#: `profiles_actions`. Esta tela soma o seu. Não há mais troca de sufixo, nem
#: régua guardando uma troca — só duas telas escrevendo cada uma o seu fim.
#:
#: **A FRASE DO PRODUTO NÃO ESTÁ ERRADA — ELA ESTÁ NA TELA ERRADA.**
#: `simple_match.exigencia_invisivel` termina em *"Ligue o Modo avançado para
#: ver e mudar."*, e na JANELA GTK isso é VERDADE: o `main.glade:2275` tem o
#: interruptor com esse nome, e `profiles_actions._sincronizar_exigencia_invisivel`
#: escreve a frase no rótulo ao lado dele. Nesta interface não há uma ocorrência
#: — medido: `grep -rn "Modo avançado"` em `interface/paginas/` dá zero fora do
#: arquivo de estudo `Telas Hefesto.dc.html`.
#:
#: **POR ISSO A SUBSTITUIÇÃO É AQUI, E NÃO LÁ.** Corrigir a frase em
#: `simple_match.py` apagaria a metade que está CERTA na janela estável e
#: deixaria as duas telas com a mesma frase errada em uma delas — o defeito ao
#: contrário. Quem sabe para onde ESTA tela pode mandar alguém é esta tela.
#:
#: O FIM NOVO É O MESMO DA OUTRA FRASE desta aba (`AMBIENTE_QUE_A_TELA_NAO_MOSTRA`,
#: em `perfis_web`), e isso é de propósito: as duas contam o mesmo estado — a
#: tela mostra menos regra do que o disco guarda — e o PO decidiu **"a tela
#: avisa e para por aí"**. Duas saídas diferentes para o mesmo beco seriam duas
#: verdades sobre o que se pode fazer.
#:
#: **O CONSERTO DE VERDADE É DE OUTRA POSSE, e está no relatório:**
#: `exigencia_invisivel` é um matcher de `profiles/`, e nomear ali uma peça de
#: interface é o que obriga esta remenda. A frase factual devia sair de lá e o
#: caminho, de cada tela.
#
# **E O FIM PAROU NO FATO — 06/09/2026, ONDA5-10-01, decisão 10-Q2.** Ele
# terminava em *"para vê-los e mudá-los, use `hefesto-dualsense4unix profile` na
# linha de comando"*, e a palavra dela sobre esse desfecho foi **"Isso é erro do
# produto."** O que sobra é o fato: esta tela não mostra esses campos. A poda é
# do FIM, e só dele — `test_a_exigencia_do_pragmata_chega_a_esta_tela` continua
# cobrando que a frase NOMEIE o que o perfil exige.
#
# O `FIM_DA_EXIGENCIA_NA_GTK` NÃO SE TOCA, e a razão é a de sempre: a frase
# *"Ligue o Modo avançado…"* é VERDADE na janela GTK (`main.glade:2275` tem o
# interruptor). Podar lá seria trocar um defeito por outro.
FIM_DA_EXIGENCIA_NA_GTK = "Ligue o Modo avançado para ver e mudar."
FIM_DA_EXIGENCIA_AQUI = "Esta tela não mostra esses campos."


def _exigencia_para_esta_tela(match: Any) -> str:
    """A exigência escondida daquele `match`, com o fim que ESTA tela alcança.

    NUNCA LEVANTA: ela roda dentro de `pacote()`, e uma exceção aqui derrubaria
    a pintura da aba inteira por causa de um perfil com uma regra estranha — a
    tela ficaria congelada sem dizer por quê.

    **A TROCA É EXATA E COBRADA**: `test_a_aba_10_perfis_fecha_as_linhas.py`
    exige que `FIM_DA_EXIGENCIA_NA_GTK` continue sendo o fim que o produto
    emite. No dia em que a frase de lá mudar, a régua reprova AQUI — em vez de
    a troca falhar em silêncio e a tela voltar a mandá-la a um lugar que não
    existe. É a diferença entre uma remenda declarada e uma remenda podre.
    """
    try:
        from hefesto_dualsense4unix.profiles.simple_match import (
            exigencia_invisivel,
        )

        frase = str(exigencia_invisivel(match) or "") if match is not None else ""
    except Exception:
        return ""
    if not frase:
        return ""
    # A REMENDA SAIU EM 05/09/2026, e é o conserto que esta docstring pedia.
    # `exigencia_invisivel` devolve só o FATO desde então; o CAMINHO passou a
    # ser de quem desenhou os botões. Aqui só se soma o nosso.
    return f"{frase} {FIM_DA_EXIGENCIA_AQUI}"

#: O que o "Remover" está esperando: `(perfil, instante)`, ou `None`.
_ARMADO: tuple[str, float] | None = None

#: O perfil cujos campos de TEXTO já foram pintados, e o instante do último
#: tique desta aba. Ver `_uma_vez_so`.
_PINTADO_PARA: str = ""
_ULTIMO_TIQUE: float = 0.0

#: OS CAMPOS QUE NÃO SE REPINTAM, porque ela MEXE neles enquanto o tique corre.
#:
#: ERAM TRÊS até 02/09/2026: o `editor.estilo` estava aqui por outro motivo —
#: *"o valor é sempre o mesmo e repintá-lo custava uma escrita por tique"*. Ele
#: saiu porque a razão dele não é "não repintar", é **não pintar**: foi para
#: `NAO_PINTAVEIS`, onde está a medição. Deixá-lo nos dois lugares faria duas
#: listas decidirem o mesmo campo.
#:
#: E O TERCEIRO ENTROU EM 03/09/2026 — `editor.prioridade.escolha`, o punho do
#: slider que nasceu com a decisão dela (*"Slider, como você pediu"*). O nome
#: desta lista diz "digita" e o gesto dela aqui é ARRASTAR; a razão é a mesma, e
#: é a medida que está em `_uma_vez_so`: com `data-hef-alvo="valor"` a pintura
#: faz `el.value = t` a cada 500 ms, e num `<input type=range>` isso devolve o
#: punho ao número do disco NO MEIO do arrasto — o slider ficaria intocável do
#: mesmo jeito que os dois `<input>` de texto ficariam.
#:
#: O NÚMERO AO LADO NÃO ENTRA, e é por isso que o punho ganhou endereço próprio
#: em vez de dividir o `editor.prioridade.n` com ele: o `<span class="n">` é
#: leitura, repintá-lo a cada tique não atrapalha ninguém, e é ele que mostra na
#: hora o que o disco passou a guardar.
CAMPOS_QUE_ELA_DIGITA = ("editor.nome", "editor.jogo",
                         "editor.prioridade.escolha")


def _uma_vez_so(alvo: str) -> tuple[str, ...]:
    """Os endereços a OMITIR deste tique. Vazio = pinte tudo.

    O PROBLEMA, medido em 01/09/2026 lendo o `escrever()` do piloto
    (`hefesto_vivo.py:256`): com `data-hef-alvo="valor"` a pintura faz
    `el.value = t` sempre que o valor difere. O tique é de 100 ms
    (`hefesto_vivo.py:112`). Na segunda tecla que ela digita, o campo já difere
    do que está no disco — e meio segundo depois a pintura o devolve ao valor
    do perfil. **O campo ficaria intocável.**

    A CURA É PINTAR UMA VEZ POR ESCOLHA: quando o perfil aberto no editor muda,
    os três campos vão uma vez; enquanto ela fica no mesmo perfil, ninguém
    escreve neles. Foi assim que o campo pôde ganhar gesto — sem isto, ligar o
    Nome seria ligar um campo que se apaga sozinho.

    E ELE VOLTA A PINTAR QUANDO ELA SAI DA ABA E VOLTA. Sem esta segunda
    guarda, a página recarregada mostraria de novo o "Mortal Kombat" do
    MOCKUP — o `<input>` nasce com o valor do desenho, e a memória deste módulo
    diria "já pintei". O sinal é o BURACO no tique: as dez abas dividem o mesmo
    piloto, e `pacote()` só é chamado enquanto esta página está aberta, a cada
    500 ms. Um intervalo maior que 2 s significa que a página foi embora e
    voltou.
    """
    global _PINTADO_PARA, _ULTIMO_TIQUE
    agora = time.monotonic()
    voltou = (agora - _ULTIMO_TIQUE) > 2.0
    _ULTIMO_TIQUE = agora
    if voltou or alvo != _PINTADO_PARA:
        _PINTADO_PARA = alvo
        return ()
    return CAMPOS_QUE_ELA_DIGITA


#: O separador do rótulo, EM TEXTO PURO. O dono da forma continua sendo
#: `interface/monta.SEPARADOR` — `' <span class="pt">•</span> '` —, que é
#: MARCAÇÃO e não pode entrar num `textContent`: a célula mostraria os
#: marcadores como letras. Aqui vai o mesmo caractere, sem a casca.
#:
#: NÃO IMPORTO O `monta`: ele é o GERADOR do desenho e faz leitura de disco no
#: import (`topo.html`, `fim.html`, o SVG, a logo, dois CSV). Um gerador no
#: caminho do produto é uma janela que não abre onde não há repositório. Quem
#: impede a segunda gramática é a régua
#: `test_o_rotulo_da_guarda_e_o_mesmo_do_monta`, que compara este rótulo com o
#: do `monta.rotulo(c, "curta")` sem a marcação — se ela mudar a ordem
#: (**marca • player • plástico • transporte**, decisão dela de 26/08), a régua
#: reprova AQUI antes de a tela discordar de si mesma.
SEPARADOR_EM_TEXTO = " • "


def _rotulo_curto(controle: dict[str, Any]) -> str:
    """`P1 • Cosmic Red • USB` — a forma `curta` do `monta.rotulo`, sem marcação.

    `jogador`, `nome` e `via` são os três campos que `mesa_viva.mesa_do_estado`
    devolve, e são exatamente os três que a forma `curta` junta.
    """
    return SEPARADOR_EM_TEXTO.join([
        f"P{controle.get('jogador') or '—'}",
        str(controle.get("nome") or "—"),
        str(controle.get("via") or "—"),
    ])


def _plastico(controle: dict[str, Any]) -> str:
    """O hexadecimal da casca daquele controle, **pelo dono da cor**.

    A LEI É DELA, 03/09/2026: *"se no topo tá mostrando controle white player 1,
    então cada aba vai usar os controles lá de cima. Não mistura com a info dos
    mockups."* A barra de 3px da linha era `--plastico` cravado no `<tr>` pelo
    gerador — a cor do controle do DESENHO —, e ficava lá enquanto o
    `guarda.nome` ao lado já vinha do aparelho: a linha dizia `P1 • White • USB`
    com a barra vermelha do mockup.

    `monta.cor_da_zona` lê o `<style>` que `scripts/gerar_cores_do_dualsense.py`
    escreveu no `ds_limpo.svg` — o MESMO lugar de onde a fita do topo tira a cor
    do chip. Reescrever a leitura aqui criaria a segunda verdade sobre a cor, que
    é o que o portão `check_cores_do_dualsense.py` existe para matar.

    O IMPORT É TARDIO E GUARDADO, e não uma exceção que eu abri: é exatamente o
    que `hefesto_vivo._fita` faz para esta mesma leitura, pela mesma razão. O
    `monta` lê disco no import (o esqueleto, o SVG e dois CSV de `docs/`), então
    um `import` no topo derrubaria a janela onde não há repositório. E não é um
    caminho novo: sem repositório a fita do topo também não repinta.

    `SystemExit` NO `except`, e ele não é `Exception`: `cor_da_zona` ergue
    justamente essa para um colorway que o SVG não tem, e um `except Exception`
    passaria ao lado — foi como o piloto morreu na primeira execução da fita viva.

    SEM COR LIDA, DEVOLVE VAZIO. Pelo rádio a cor não vem (o mapa de canais diz
    `identidade.cor_do_aparelho = não`) e `mesa_do_estado` entrega `cor: ""`.
    Inventar um cinza, ou cair na cor do mockup, seria a tela afirmando um modelo
    que ninguém pode conferir — o defeito que esta frente veio desfazer. Com o
    vazio o piloto escreve `''` no alvo `cor`, o `style` de linha cai, o
    `color:transparent` da classe volta e a barra SOME: campo sem informação não
    mostra nada, regra dela.
    """
    slug = str(controle.get("cor") or "")
    if not slug:
        return ""
    try:
        from hefesto_dualsense4unix.interface import monta

        return str(monta.cor_da_zona(slug))
    except (Exception, SystemExit):
        return ""


def _mesa_com_rotulo(mesa: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A mesa no formato que `perfis_web.pacote_da_aba` DIZ esperar.

    FATO ERRADO, SUBSTITUÍDO — 02/09/2026. A docstring de
    `perfis_web.pacote_da_aba` afirma que a mesa vem *"no formato que
    ``mesa_viva.mesa_do_estado`` devolve mais ``rotulo`` e ``plastico``"*, e o
    `_linhas_da_guarda` lê `controle.get("rotulo")` (`perfis_web.py:545`).
    **`mesa_do_estado` não devolve nenhum dos dois** — os campos dela são
    `pref`, `uniq`, `jogador`, `cor`, `nome`, `via`, `transporte`, `alvo`,
    `mascara` (`mesa_viva.py:320-332`). Medido: `guarda.nome` saía `["", ""]`
    para os DOIS controles da mesa dela, e a tabela ficava sem nome nenhum.

    QUEM JÁ FAZIA ISTO CERTO: `interface/perfis_vivos.mesa_de_agora:318` — o
    visor da aba, que o piloto **não carrega**. É o padrão que a ONDA B1 mediu:
    *o reuso aconteceu, no arquivo que o piloto não abre*. Aqui ele entra no
    caminho do produto.

    O `plastico` ENTROU EM 03/09/2026, e o fato acima valia para ele também:
    `_linhas_da_guarda` lê `controle.get("plastico")` (`perfis_web.py:517`) e
    recebia `""` para todo controle, porque ninguém o punha aqui. Ver `_plastico`.
    """
    return [{**c, "rotulo": _rotulo_curto(c), "plastico": _plastico(c)}
            for c in mesa]


#: O SELETOR DO CORPO DA LISTA — CSS, e não `data-campo`: o `blocos` do piloto
#: endereça por `document.querySelector` (`hefesto_vivo.py`, o laço
#: `for(const [seletor, html] of Object.entries(p.blocos || {}))`).
SELETOR_DA_LISTA = 'tbody[data-hef="perfis.lista"]'

#: A INDENTAÇÃO DA LINHA no desenho: dezesseis espaços, os mesmos que
#: `aba10.linha_do_perfil` emite. Ela não muda nada na tela — HTML come espaço
#: em branco entre linhas de tabela —, e existe para que a régua de forma possa
#: comparar as duas emissões CARACTERE A CARACTERE.
_RECUO = " " * 16


def _texto(v: Any) -> str:
    """Um valor pronto para virar TEXTO dentro de uma célula.

    ESCAPAR É OBRIGATÓRIO AQUI E NÃO ERA NO GERADOR, e a diferença é a fonte: o
    gerador escreve os catorze nomes que ESTA CASA digitou no `PERFIS` do
    desenho; esta função escreve os 33 que estão no disco DELA. Um perfil
    chamado `Bail < Jail` viraria marcação no meio da linha.
    """
    s = str(v if v is not None else "")
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace("\xa0", "&nbsp;"))


def _atr(v: Any) -> str:
    """Um valor pronto para virar VALOR DE ATRIBUTO — `title=`, `data-…=`.

    **ESCAPA MENOS QUE O `html.escape` DO PYTHON, e isso é a cura de um defeito
    medido, não um relaxamento.** O `blocos` do piloto só reescreve o miolo
    quando `alvo.innerHTML !== html` — ou seja, ele compara a MINHA string com a
    **serialização que o navegador devolve**. Escapar o que o serializador não
    escapa faz as duas nunca baterem, e o bloco é reescrito a cada 500 ms para
    sempre.

    MEDIDO em 02/09/2026, com o piloto aberto na aba por dez segundos e com o
    mesmo HTML injetado num Chrome de bancada (`_ferramentas` do desenho, sem
    janela) para ler o `innerHTML` de volta:

        `html.escape(quote=True)`  →  21 tiques, 17 escritas em CADA um
        escapando como o serializador →  1 escrita, e silêncio depois

    As duas divergências, e as duas são de escapar DEMAIS:

        `'`   o Python manda `&#x27;`, o navegador devolve `'`   (`DON'T SCREAM`)
        `\\n`  o Python (na minha primeira tentativa) mandava `&#10;`, o navegador
              devolve a quebra CRUA — e a dica da disputa tem dois parágrafos

    E NÃO É INSEGURO: dentro de aspas duplas, um `'` e um `<` não fecham nada —
    quem fecha o atributo é a aspa dupla, e ela continua virando `&quot;`. É
    exatamente o conjunto que o serializador de HTML escapa em atributo.

    O CUSTO DE NÃO CURAR ISTO NÃO É SÓ O CONTADOR: reescrever o `<tbody>` a cada
    meio segundo apaga o `:hover` da linha sob o mouse dela e desfaz qualquer
    seleção de texto na lista — três vezes por segundo, enquanto ela procura um
    perfil entre 33.
    """
    s = str(v if v is not None else "")
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("\xa0", "&nbsp;")


def _linha_da_lista(nome: str, prioridade: str, quando: str,
                    ativo: bool, dica: str = "", escolhido: bool = False) -> str:
    """Uma linha da lista de perfis — a MESMA forma que o desenho crava.

    O DONO DA FORMA CONTINUA SENDO O GERADOR, `aba10.linha_do_perfil`, cuja
    docstring já dizia a que veio: *"a MESMA para o mockup e para a viva … a aba
    viva precisa do desenho, não de uma cópia dele"*. Só que ele **não atravessa
    para o produto**: `aba10.py` faz `sys.path.insert` e `from monta import …`,
    e o `monta` lê seis arquivos do repositório no import — um gerador no
    caminho do produto é uma janela que não abre onde não há repositório. É a
    mesma razão pela qual o `SEPARADOR_EM_TEXTO` acima é uma constante e não um
    import.

    ENTÃO O QUE IMPEDE A SEGUNDA GRAMÁTICA É UMA RÉGUA, e não a boa vontade:
    `test_a_lista_de_perfis_cabe_inteira.py::test_a_linha_viva_e_a_linha_do_desenho`
    importa o gerador (no teste ele pode) e compara as duas saídas caractere a
    caractere. Mexer no desenho da linha sem mexer aqui reprova ANTES de a tela
    discordar de si mesma.

    A ÚNICA DIVERGÊNCIA DECLARADA É O ESCAPE — ver `_texto` e `_atr`.

    `escolhido` É A LINHA ABERTA NO EDITOR — 04/09/2026, queixa dela: *"quando
    clica em algum nome do perfis salvos nada indica que tal coisa tá
    selecionado"*. O valor já existia (`_escolhido`, no alto deste arquivo) e
    alimentava só o texto do botão Remover e os gestos; ele não chegava à LINHA,
    e a tela ficava calada sobre o alvo de nove botões.

    **A MARCA TEM DE VIR DAQUI, e não de um `classList.add` no JS**: o `blocos`
    do piloto reescreve este `<tbody>` inteiro a cada tique, e o tique é de
    **100 ms** — qualquer marca posta pelo navegador vive um décimo de segundo.

    NÃO É UMA SEGUNDA CLASSE, e a razão é medida:
    `test_a_lista_de_perfis_cabe_inteira.py:195` procura a SUBSTRING
    `class="ativo"` na linha realçada, e um `class="ativo escolhido"` a some —
    a régua do realce ficaria verde sobre uma linha que ela não acha mais. O
    estado vai em `aria-selected`, que é o que o papel `row` já define para
    seleção: uma verdade só, no atributo que a própria plataforma leu primeiro.
    """
    return (f'{_RECUO}<tr class="{"ativo" if ativo else ""}" '
            f'data-hef-perfil="{_atr(nome)}" '
            f'aria-selected="{"true" if escolhido else "false"}" title="{_atr(dica)}">'
            f'<td data-hef="perfis.linha.nome" data-hef-gesto="selecionar">'
            f'{_texto(nome)}</td>'
            f'<td class="pri" data-hef="perfis.linha.prioridade">'
            f'{_texto(prioridade)}</td>'
            f'<td class="quando" data-hef="perfis.linha.quando">'
            f'{_texto(quando)}</td></tr>')


def _html_da_lista(lista: list[dict[str, Any]], vazia: str,
                   escolhido: str = "") -> str:
    """As linhas da lista de perfis, TODAS — e é a maior mentira que esta aba
    contava.

    MEDIDO em 02/09/2026, na máquina dela: `load_all_profiles()` devolve **33**
    perfis e o `<tbody>` publicado tem **14 linhas**. O contador ao lado do
    título dizia "33 perfis" — e dizia a verdade — enquanto a tabela logo abaixo
    mostrava catorze. **Dezenove perfis dela não tinham como ser clicados**, e
    com eles nove dos dez botões desta aba: `ativar`, `remover`, `duplicar`,
    `editor.nome`… todos agem sobre o perfil ESCOLHIDO, e escolher é clicar numa
    linha que existe.

    POR QUE NÃO SE PINTA CAMPO A CAMPO: é a mesma razão da fita de chips e do
    mapa do gabinete — **um bloco cujo número de filhos muda com o dado não tem
    endereço para o filho que ainda não existe**. A lista de perfis é o caso
    mais puro: o desenho cravou catorze porque catorze cabiam na figura.

    TRÊS COISAS CHEGAM À TELA POR AQUI E NÃO CHEGAVAM POR NENHUMA OUTRA PORTA:

    1. **as linhas que faltavam** — as 19;
    2. **a classe `ativo` na linha certa.** O desenho a crava na PRIMEIRA linha,
       e até hoje ela ficava lá. Acertava por acidente — `ordem_de_exibicao`
       põe o ativo em primeiro —, e mentia inteiro quando não há perfil ativo
       nenhum: a tela realçava um perfil que não está valendo. Nenhum dos cinco
       alvos do pintor liga uma CLASSE; o `blocos` traz a linha pronta, com a
       classe dentro dela, e não precisa dele;
    3. **o `title` da disputa.** `explicacao_da_disputa` existe em
       `profiles_actions:403`, `perfis_web._linhas_da_lista` já a chamava a cada
       tique, e o valor morria no dicionário: o `title=""` do desenho nasce
       vazio *"porque a dica é a DISPUTA, e disputa é dado — o mockup não tem
       nenhum"* (palavras do gerador). O dado existe desde então; faltava a
       porta.

    A LISTA VAZIA TAMBÉM É UM ESTADO, e a frase dela já estava escrita e nunca
    tinha aparecido: `perfis_web.LISTA_VAZIA` diz o que fazer para ter o
    primeiro perfil. Sem esta linha o `<tbody>` ficaria em branco — a tela
    calada sobre um estado que ela sabe explicar.

    **ESTE `<tbody>` AINDA É REESCRITO A CADA TIQUE, e a causa NÃO é o escape** —
    medido em 02/09/2026 no WebKit da janela dela, com o daemon vivo e uma sonda
    no laço do `blocos` do piloto. Em 20 tiques: `BLOCOS 20`, contra 1 de cada
    um dos outros endereços da aba (eles assentam no primeiro tique). O primeiro
    caractere divergente é o 594:

        na TELA     …data-hef-gesto="selecionar" data-hef-visto="1">meu_perfil…
        no PRODUTO  …data-hef-gesto="selecionar">meu_perfil…

    O `escrever()` do piloto carimba `el.dataset.hefVisto = '1'` em TODO
    elemento que visita — inclusive quando escreve zero, que é o ponto do selo.
    O laço do `blocos` roda ANTES da distribuição por endereço e compara
    `alvo.innerHTML !== html`: do segundo tique em diante a tela tem 99 selos
    que o produto não tem (12.222 caracteres contra 10.341), e as duas strings
    nunca mais batem. O custo é o que a nota do `_atr` já descreve — o `:hover`
    da linha sob o mouse dela apagado duas vezes por segundo, enquanto ela
    procura um perfil entre 33.

    **A CURA MORA NO PILOTO, e não aqui** — carimbar o selo fora da serialização
    (um `WeakSet` em JS) ou comparar sem ele. Emitir o selo daqui faria esta aba
    conhecer um detalhe interno do pintor. Está relatado ao orquestrador.

    HOJE SÓ ESTA LISTA PAGA, e conferi antes de acusar as irmãs: o defeito só
    morde um `blocos` cujos FILHOS tenham endereço, e os dois da `08-conexoes`
    (`.mm-faces` e `.mm-lista`) não emitem `data-campo` nenhum dentro. Quando
    emitirem, entram no mesmo buraco.

    `escolhido` É O NOME DA LINHA ABERTA NO EDITOR, e a comparação é por NOME
    EXATO de propósito: quem chama já resolveu o slug (`find_by_slug`) contra os
    perfis que existem, e o `nome` de cada linha vem do mesmo `p.name`. Comparar
    slug de novo aqui seria a segunda resolução do mesmo dado — e é assim que
    esta aba já deu dois vereditos sobre a mesma tela em 02/09.

    O VAZIO É O ESTADO SEM MARCA: `escolhido=""` não casa com nome nenhum, e a
    lista sai como saía. É o que mantém verde toda régua que chama esta função
    sem saber que ela ganhou um terceiro argumento.
    """
    if not lista:
        return (f'{_RECUO}<tr class="vazia"><td colspan="3">'
                f'{_texto(vazia)}</td></tr>')
    return "\n".join(
        _linha_da_lista(str(x.get("nome") or ""), str(x.get("prioridade") or ""),
                        str(x.get("quando") or ""), bool(x.get("ativo")),
                        str(x.get("dica") or ""),
                        escolhido=bool(escolhido)
                        and str(x.get("nome") or "") == escolhido)
        for x in lista)


def _valendo(ctx: Contexto, todos: list[Any] | None = None) -> str:
    """Qual perfil está valendo AGORA, **com o nome que a LISTA mostra**.

    `profiles_actions.perfil_que_esta_valendo` é o §P1 desta casa, e esta aba
    era o lugar mais caro para não o chamar: ela lia
    `ctx.state.get("active_profile")` cru, e a própria docstring de lá diz que o
    daemon responder `active_profile: null` é *"o estado da máquina dela hoje"*.
    Com o `null`, as três guardas desta aba se desligavam ao mesmo tempo:

        ativar     deixava de recusar o perfil que JÁ está valendo
        remover    deixava de recusar apagar o perfil que está valendo —
                   e o daemon segue aplicando um arquivo que não existe mais
        voltar…    deixava de reaplicar depois de restaurar, e o arquivo voltava
                   ao que era com o controle no que estava

    E a lista perdia o realce da linha certa. O dono consulta o daemon primeiro
    e, só se ele calar, o marcador em disco — pelo mesmo caminho do boot
    (`resolve_boot_profile`). Ele nunca levanta: qualquer falha de I/O vira
    `nao_sei`, que aqui é o `""`.

    **O `find_by_slug` NO FIM É A SEGUNDA METADE, e sem ele a mesma tela dava
    DOIS vereditos** — 02/09/2026. O que vem do daemon ou do marcador é um NOME
    DIGITADO, e daqui ele seguia cru para dois comparadores diferentes:

        o realce da lista   `perfis_web._linhas_da_lista:358` faz `p.name == ativo`
        as guardas dos gestos  `mesmo_slug` (R-10), em `ativar` e `voltar…`

    MEDIDO com 33 perfis no disco e o daemon calado, marcador em `sackboy` e o
    perfil chamado `Sackboy`:

        realce -> []                     (nenhuma das 33 linhas se acende)
        Ativar -> "já é o perfil que está valendo"   (a guarda por slug pega)

    Duas guardas, dois vereditos, uma tela — e o marcador em caixa diferente é
    exatamente o caso que `find_by_slug` existe para cobrir (a docstring dele
    cita "Navegação"/"Navegacao"). **O dono passa a ser UM SÓ:** o nome é
    resolvido aqui, contra os perfis do disco, e sai já sendo o `p.name` de uma
    linha da lista. O `==` de lá não pode mais discordar do `mesmo_slug` daqui.

    **E O MARCADOR ÓRFÃO CAI JUNTO** — perfil renomeado ou apagado por fora. O
    `resolve_boot_profile` declara na própria docstring que *"só resolve NOMES —
    não valida se o perfil carrega"*; o que ele devolve ia CRU para o REALCE DA
    LISTA e para o alvo dos gestos. Sem casar com ninguém, o nome vira `""` —
    que aqui é "não há", e a lista não acende linha nenhuma.

    **FATO ERRADO, SUBSTITUÍDO — 02/09/2026.** Aqui estava escrito que o nome
    cru ia também *"para o chip 'Perfil ativo'"*, e que a cura o levava ao
    travessão. **O chip não passa por aqui, e continua nomeando o órfão.** Ele
    é `<span class="pa-nome" data-campo="perfil">` (`10-perfis.html:1035`, nas
    duas páginas), do `topo.html`, que é das dez abas — e quem o pinta é
    `pacotes.topo()`, com `ctx.state.get("active_profile")` CRU. Medido pelo
    caminho do piloto (`pacote_da_pagina` → `normalizar` → `topo` com
    `setdefault`), dois perfis no disco e dublê de ponte:

        daemon diz              chip na tela            linhas realçadas
        "Perfil Que Ela Apagou" "Perfil Que Ela Apagou"  []
        "sackboy"               "sackboy"                ["Sackboy"]

    A segunda linha é a pior: a MESMA tela passa a dar dois nomes para a mesma
    pergunta. A cura mora no dono compartilhado (`pacotes/__init__.py`, `topo`),
    que tem de resolver o nome do mesmo jeito — **não aqui**: um pacote de aba
    que emitisse `perfil` seria o segundo dono do cabeçalho, que é o defeito
    fotografado às 04:23 de 02/09 na aba Sistema e está escrito em
    `a09_sistema.pacote`. A dívida tem régua própria, em
    `tests/unit/test_a_aba_perfis_manda_para_um_endereco_que_existe.py`.

    **LISTA VAZIA NÃO É PROVA DE ÓRFÃO — é a AUSÊNCIA de prova**, e essa
    distinção é a que impede a cura de desarmar o §P7. Só se rebaixa o nome a
    `""` quando há uma lista contra a qual conferi-lo; sem lista, o nome cru
    segue, e `ativar`/`remover` continuam recusando. Medido em 02/09/2026: sob
    o `pytest` a `conftest.py:2114` põe
    `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` em TODO teste, e
    `load_all_profiles()` devolve **[]** — sem esta guarda, todas as réguas
    desta aba passariam a medir o ramo vazio e a guarda de apagar o perfil que
    vale ficaria verde sem existir.

    `todos` é para quem já leu o disco neste tique: `pacote()` roda a cada
    500 ms e chama `load_all_profiles()` uma vez; ler 33 arquivos duas vezes por
    tique seria pagar de novo o que já está na mão. Os gestos chamam sem ele —
    são um clique, não um laço.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        perfil_que_esta_valendo,
    )
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    nome = str(perfil_que_esta_valendo(ctx.state).nome or "")
    if not nome:
        return ""
    if todos is None:
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles

        try:
            todos = list(load_all_profiles())
        except Exception:
            # DISCO ILEGÍVEL NÃO PODE DESARMAR AS GUARDAS. Sem a lista não dá
            # para saber se o nome é órfão — e o erro seguro é o nome cru: ele
            # mantém `ativar` e `remover` recusando. Devolver `""` aqui faria a
            # falha de leitura ABRIR a porta de apagar o perfil que vale.
            return nome
    if not todos:
        return nome
    achado = find_by_slug(nome, todos)
    return str(getattr(achado, "name", "") or "") if achado is not None else ""


def _rotulo_do_remover(alvo: str) -> str:
    """"Remover", ou a PERGUNTA que a dica dela promete — sobre o alvo de AGORA.

    A dica no desenho diz *"Apaga do disco. Pergunta antes."* — e esta janela
    não tem diálogo. O `on_profile_remove` da janela estável abre um
    `gui_dialogs.confirm_delete_profile` (`profiles_actions.py:3198`), que é
    GTK e MODAL; daqui não dá para abri-lo, porque **os gestos rodam em
    thread** (`hefesto_vivo.py:2117`) e GTK só aceita diálogo no laço principal.

    **FATO CADUCO, SUBSTITUÍDO — 02/09/2026.** Aqui estava escrito que *"a
    recusa do piloto não serve de pergunta: ela sai em `stderr`, no terminal,
    onde a dona não está olhando"*. **Não sai mais.** O piloto ganhou
    `_recusou_dizendo` (`hefesto_vivo.py:2523`): todo `RuntimeError` de gesto
    vira TARJA na tela — no cartão do controle quando a página tem um, e no
    `document.body` quando não tem, que é o caso desta aba. Ela some sozinha em
    `SEGUNDOS_DO_RECADO = 30.0`.

    **O RÓTULO CONTINUA SENDO A PERGUNTA, e agora por outra razão:** a tarja é
    AVISO e o rótulo é ESTADO. A tarja conta o que acabou de acontecer e vai
    embora em trinta segundos; o rótulo diz, enquanto o armamento vive, qual
    perfil o próximo clique apaga. Com só a tarja, ela leria "Apagar
    “Pragmata”?" e teria oito segundos para decidir olhando um botão que diz
    "Remover".

    O rótulo é o pedaço de tela que
    já existe, que ela está olhando no instante do clique, e que o piloto sabe
    pintar. O desenho não muda: o mockup continua escrevendo "Remover".

    **O `alvo` É A CURA DE 02/09/2026, e sem ele o botão ANUNCIAVA UM PERFIL E
    APAGAVA OUTRO.** O armamento sempre foi por perfil — `remover` exige
    `_ARMADO[0] == nome` — mas este rótulo olhava só o RELÓGIO, e por isso
    continuava perguntando pelo perfil armado depois de ela clicar noutra linha.
    **A SEQUÊNCIA, MEDIDA PASSO A PASSO** — dois perfis no disco, dublê de
    ponte, ninguém valendo. A coluna ANTES é este rótulo sem o `== alvo` (a
    mordida); a coluna DEPOIS é o de hoje:

        passo                          ANTES                      DEPOIS
        1 clicou na linha do Pragmata  "Remover"                  "Remover"
        2 CLIQUE em Remover            arma o Pragmata, levanta   igual
        3 o rótulo, no tique seguinte  "Remover “Pragmata”? …"    igual
        4 clicou na linha do Sackboy   "Remover “Pragmata”? …"    "Remover"
        5 CLIQUE em Remover            arma o SACKBOY, levanta    igual
        6 o rótulo, no tique seguinte  "Remover “Sackboy”? …"     igual
        7 CLIQUE em Remover            APAGA o Sackboy            igual

    **UM ÚNICO PASSO DIFERE, e é o 4 — o defeito inteiro está ali:** o botão
    anuncia que o próximo clique apaga o Pragmata, e o próximo clique arma o
    Sackboy.

    **FATO ERRADO, SUBSTITUÍDO — 02/09/2026.** Aqui estava escrito *"três
    cliques num botão que nunca deixou de dizer 'Pragmata' apagam o Sackboy"*, e
    que o passo 5 armava *"calado"*. A medição acima derruba as duas: no passo
    6, **ainda sem a cura**, o rótulo já diz "Sackboy" — dentro de um tique de
    500 ms —, então o clique que APAGA nunca acontece sob um botão dizendo
    "Pragmata". E o "calado" é o que menos se sustenta hoje: com
    `_recusou_dizendo` no piloto, o passo 5 **põe a frase em TARJA na tela**, e
    o rótulo fala meio segundo depois. Exagerar o defeito não o torna mais real,
    e a próxima pessoa leria isto como o enunciado.

    Com o alvo, o rótulo volta a "Remover" no instante em que ela troca de
    linha — que é a verdade: o próximo clique naquele botão ARMA, não apaga.
    """
    if (_ARMADO and _ARMADO[0] == alvo
            and (time.monotonic() - _ARMADO[1]) < SEGUNDOS_PARA_CONFIRMAR):
        return f"Remover “{_ARMADO[0]}”? Clique de novo"
    return "Remover"


#: QUANTOS LUGARES A TABELA DE AJUSTE PRÓPRIO TEM. Não é digitado aqui: é a
#: mesma constante que a mesa das dez abas usa, e o desenho da `aba10` emite uma
#: linha por lugar dela.
LUGARES_DA_TABELA = len(TODOS_OS_LUGARES)


def _com_os_lugares_vazios(
    da_mesa: list[Any], para_o_vazio: Callable[[int], Any]
) -> list[Any]:
    """A lista da mesa completada até os quatro lugares do desenho.

    NASCEU EM 05/09/2026, da palavra dela — *"os svgs não deveriam aparecer prós
    demais controles desconectados"*. Antes disto o pacote mandava só as linhas
    da mesa e o `forEach` do bootstrap escrevia `''` no que sobrava. `''` serve
    para APAGAR (uma classe, uma cor, um texto) e nunca para ACENDER — e o
    lugar vazio precisa acender uma classe (`fora`) e escrever um rótulo
    (`P3 • Desconectado`). Sem as quatro, os dois voltam a ser do desenho, que
    é quem não sabe quantos controles estão na mesa.

    ``para_o_vazio`` recebe o NÚMERO do lugar (1..4) e devolve o valor daquela
    linha — uma função, e não um valor fixo, porque o rótulo do lugar vazio traz
    o próprio número.

    Sobra de mesa não é aparada: uma mesa maior que o desenho é outro defeito, e
    escondê-lo aqui faria esta função mentir sobre o tamanho da tabela.
    """
    completa = list(da_mesa)
    for n in range(len(completa) + 1, LUGARES_DA_TABELA + 1):
        completa.append(para_o_vazio(n))
    return completa


@registrar("10-perfis.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """DELEGA para `app/actions/perfis_web.pacote_da_aba` — a camada do PRODUTO.

    ELA JÁ EXISTIA E NUNCA TINHA SIDO LIGADA. O `casa-sabe` a listava como
    promessa sem caminho: `perfis_web.pacote_da_aba` não tinha um chamador em
    produção desde 30/08/2026.

    E ELA SABE MAIS QUE O QUE ESTE PACOTE TINHA: a coluna "Quando usar" diz *"Só
    neste programa"* onde eu escrevia *"Jogo"*; ela traz `com_ajuste` ("0 de 2
    controles com ajuste próprio neste perfil"), a `guarda` dos overrides por
    controle, os `travados` e o `editor` inteiro. Cada uma dessas frases é texto
    de tela que alguém escreveu com ela, e reescrevê-las por fora seria a
    segunda verdade.

    O QUE SOBRA AQUI é o ACHATAMENTO para os `data-hef` da página, que são 77.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    try:
        todos = load_all_profiles()
        # O DISCO É LIDO UMA VEZ POR TIQUE, e `_valendo` recebe a lista em vez
        # de relê-la: ele resolve o nome que vale contra os perfis que existem
        # (ver a docstring dele), e são 33 arquivos a cada 500 ms.
        ativo = _valendo(ctx, todos)
        # O `editado` FALTAVA, e o editor mostrava o perfil ERRADO — corrigido
        # em 01/09/2026, ao ligar os campos. Sem ele `pacote_da_aba` cai no
        # ativo (`perfis_web.py:545`), então clicar numa linha mudava o alvo dos
        # botões e o editor ao lado continuava pintando OUTRO perfil. Enquanto
        # nenhum campo tinha gesto isso era só uma tela desalinhada; com o Nome
        # e o Nome do Jogo ligados, seria ela renomear um perfil olhando para o
        # nome de outro.
        escolhido = _escolhido([{"nome": x.name} for x in todos], ativo)
        alvo = find_by_slug(escolhido, todos)
        bruto = _tela.pacote_da_aba(todos, ativo=ativo or None,
                                    mesa=_mesa_com_rotulo(ctx.mesa), editado=alvo)
    except Exception:
        return {"sem_dono": {}, "cobertura": {"pintados": 0, "sem_dono": 1}}

    lista = bruto.get("lista") or []
    editor = bruto.get("editor") or {}
    fora = {
        "perfis.conta": bruto.get("conta", "—"),
        "perfis.com-ajuste": bruto.get("com_ajuste", ""),
        # AS TRÊS COLUNAS SÃO LISTAS, e a tela as distribui pelos blocos de
        # mesmo endereço, na ordem — sem o gerador precisar saber quantos
        # perfis ela tem.
        "perfis.linha.nome": [x.get("nome", "") for x in lista],
        "perfis.linha.prioridade": [x.get("prioridade", "") for x in lista],
        "perfis.linha.quando": [x.get("quando", "") for x in lista],
        # O `ativo` SAIU DAQUI — 02/09/2026, e ele é o achado desta correção.
        # Esta chave carregava o nome resolvido por `_valendo` e **não tinha
        # endereço em página nenhuma**: `data-(campo|papel|hef)="ativo"` dá ZERO
        # ocorrências em `interface/paginas/10-perfis.html` e zero em
        # `mockup/10-perfis.html`. O chip que ela lê é
        # `<span class="pa-nome" data-campo="perfil">` (linha 1035 das duas), e
        # quem o pinta é `pacotes.topo()` — o dono das dez abas.
        #
        # O CUSTO DE TER EXISTIDO foi uma cura declarada sobre uma tela que não
        # mudou: três réguas chamavam este valor de "o chip" e ficavam verdes
        # sem tocar o que ela vê. Ver
        # `tests/unit/test_a_aba_perfis_manda_para_um_endereco_que_existe.py`,
        # que agora cobra endereço de TODA chave emitida por esta aba.
        "quantos": len(lista),
        "travado": bool(ctx.state.get("autoswitch_locked")),
        "sem_dono": {},
    }
    # O SEPARADOR É O PONTO, e não o hífen: a página endereça
    # `editor.prioridade.dica`, e um `editor.prioridade-dica` cai no vazio. Os
    # 77 `data-hef` desta aba usam ponto do começo ao fim.
    # O EDITOR TAMBÉM: sem perfil aberto, os campos vão a travessão em vez de
    # ficar com o texto do desenho.
    for chave in ("nome", "jogo", "estilo", "ambiente"):
        fora.setdefault(f"editor.{chave}", "—")
    fora.setdefault("editor.prioridade.n", "—")
    fora.setdefault("editor.prioridade.dica", "")
    for chave, valor in editor.items():
        if not isinstance(valor, (dict, list)):
            fora[f"editor.{chave.replace('_', '.')}"] = valor
    # A BARRA NÃO RECEBE TRAVESSÃO NEM SINAL DE PORCENTO, e as duas coisas
    # seriam o mesmo estrago — medidas ao tirar este nome de `NAO_PINTAVEIS`,
    # em 02/09/2026. O `escrever()` do piloto faz
    # `el.style.width = t + '%'` (`hefesto_vivo.py`, ramo `largura`) e só conta
    # a pintura quando `el.style.width` MUDA. Um `'—'` vira `'—%'` e um `'45%'`
    # vira `'45%%'`: as duas são CSS inválido, o navegador as recusa, a largura
    # fica no 90% do desenho — e como `el.style.width` nunca volta igual ao que
    # se escreveu, o contador soma +1 por tique, PARA SEMPRE. Um contador que
    # mente é pior que uma barra parada: ele é O instrumento com que esta casa
    # prova que um endereço existe.
    #
    # A CASA JÁ TINHA A CONVENÇÃO, e é número puro: `a03_gatilhos:394` manda
    # `aj["pct"]`, que é um `round(...)` inteiro (`:325`). Quem destoa é o
    # `perfis_web._pacote_do_editor:324`, que formata `f"{pct:.0f}%"` — e destoa
    # sem custo desde 30/08 justamente porque este campo NUNCA foi pintado.
    # O `%` fica lá: `prioridade` é valor do PRODUTO, e o produto o descreve com
    # o sinal. Quem tira a casca é este achatamento, que é o que ele faz.
    fora["editor.prioridade"] = str(editor.get("prioridade") or "0").rstrip("%")

    # O PUNHO DO SLIDER — 03/09/2026, e ele é o número CRU, nunca o `'—'`.
    #
    # A EMISSÃO É CONDICIONAL de propósito, e a razão é a mesma que segura o
    # `editor.estilo` em `NAO_PINTAVEIS`: `escrever()` troca vazio por `'—'`
    # ANTES de escolher o ramo (`hefesto_vivo.py`), e `el.value = '—'` num
    # `<input type=range>` é recusado pelo DOM — o campo volta ao meio da faixa
    # e `el.value` NUNCA volta igual ao escrito, então o contador soma +1 por
    # tique para sempre. Um contador que mente é pior que um punho parado: ele é
    # O instrumento com que esta casa prova que um endereço existe.
    #
    # Sem perfil aberto, o punho fica onde o DESENHO o pôs — que é a leitura
    # honesta de "não há prioridade para mostrar", e o mesmo que o `<select>` do
    # Estilo faz com a opção vazia dela.
    if editor:
        fora["editor.prioridade.escolha"] = str(editor.get("prioridade_n") or "0")

    # O PONTO DE ALERTA DO "NOME DO JOGO" — decisão [01] do PO, 04/09/2026.
    #
    # O CASO É O DO PRAGMATA, e ele foi medido com ela jogando: o editor
    # mostrava "Jogo da Steam · 3357650" e o arquivo exigia TAMBÉM
    # `PRAGMATA.exe`. O `matches` é AND, o campo invisível era o que decidia, e
    # o perfil não entrava sozinho — seis vezes em dois minutos. A tela afirmava
    # uma regra que não era a regra.
    #
    # SÃO DUAS CHAVES E UM VALOR: a marca acende quando a frase existe. Elas
    # saem da MESMA linha, do MESMO cálculo, e por isso não há caminho no código
    # em que uma exista sem a outra — que é a guarda que o `monta.botao_cinza`
    # consegue com um campo só e esta marca não consegue (ver
    # `aba10.marca_com_dica` para o porquê).
    #
    # O `alvo` É O PERFIL ABERTO NO EDITOR, e não o que está valendo: a
    # exigência escondida é do perfil que os campos ao lado estão mostrando.
    exigencia = _exigencia_para_esta_tela(getattr(alvo, "match", None))
    fora["editor.jogo.exigencia"] = exigencia
    fora["editor.jogo.exige"] = "sim" if exigencia else ""

    # OS TRÊS CAMPOS QUE SE PINTAM UMA VEZ SÓ — e a razão é medida, não gosto.
    # Ver `_uma_vez_so`: repintar um `<input>` a cada 500 ms apagaria o que ela
    # está digitando na segunda tecla.
    for chave in _uma_vez_so(str(getattr(alvo, "name", ""))):
        fora.pop(chave, None)

    # O RÓTULO DO REMOVER, e ele é a pergunta que a dica dela promete. Sai daqui
    # e não do JS porque o armamento vive no Python (ver o gesto `remover`).
    #
    # ELE RECEBE O ALVO, e o `escolhido` daqui é o MESMO nome que
    # `_perfil_do_editor` devolve ao gesto: os dois são `_ESCOLHIDO or` o que
    # está valendo, e `_escolhido()` acabou de sincronizar o primeiro. Sem o
    # alvo, o rótulo perguntava por um perfil e o clique agia sobre outro —
    # a medição está na docstring de `_rotulo_do_remover`.
    fora["perfis.remover"] = _rotulo_do_remover(escolhido)

    # O DESFECHO DO ÚLTIMO GESTO — a paridade com o toast da janela estável.
    # Sai daqui pela mesma razão do rótulo acima: o estado vive no Python
    # (os gestos rodam em thread e não tocam o DOM), e a pintura o busca.
    fora["perfis.desfecho"] = _desfecho_para_a_tela()

    # A GUARDA são os overrides por controle — o que cada um guarda de próprio
    # neste perfil. O produto já a monta; a tela a distribui por linha.
    # AS CHAVES SAEM MESMO VAZIAS, e é o que faz a tela APAGAR a lista do
    # mockup quando não há perfil. Emiti-las só quando há conteúdo deixaria os
    # catorze nomes do desenho na tela de quem não tem perfil nenhum — a mesma
    # mentira dos lugares vazios da mesa, que já custou sete reincidências.
    guarda = bruto.get("guarda") or []
    if isinstance(guarda, list):
        # O QUE A LINHA QUE SOBRA MOSTRA HOJE, e é achado de 03/09/2026 na foto
        # do produto (mesa com dois controles): as duas linhas de baixo saem com
        # `—` no nome E `—` no ID, e a fileira de OITO glifos de "Ajuste próprio"
        # sai IDÊNTICA à das duas linhas de cima — medido nos pixels,
        # `rgb(130,144,189)` nas quatro.
        #
        # O DESENHO DECIDE OUTRA COISA: `aba10.linha_do_controle` escreve
        # `P3 <bolinha> Desconectado` num `<tr class="fora">`, com a dica
        # *"Nenhum controle neste lugar. O perfil guarda o que está aqui pelo ID
        # da peça"* — decisão dela de 31/08 (*"o espaço fica, mas o nome do canto
        # muda"*). A lista curta cai aqui em `''`, o `escrever()` do piloto troca
        # vazio por `—` (`hefesto_vivo.py`), e o rótulo que ela pediu é APAGADO
        # pelo travessão. Nesta casa `—` quer dizer *"não sei"*; o que a linha
        # tem a dizer é *"não há controle aqui"*, que são coisas diferentes.
        #
        # **ELA ESCOLHEU — 05/09/2026:** *"os svgs não deveriam aparecer prós
        # demais controles desconectados"*. A escolha que faltava era esta, e
        # ela decide as duas metades de uma vez: o pacote passa a mandar as
        # QUATRO linhas, e quem escreve o rótulo do lugar vazio deixa de ser o
        # desenho.
        #
        # O QUE MUDA, linha por linha:
        #
        #   `guarda.nome`     o lugar sem controle diz `P3 • Desconectado` — o
        #                     rótulo que ela pediu em 31/08 e que o travessão
        #                     do `escrever()` vinha apagando;
        #   `guarda.vazio`    endereço NOVO, alvo `classe`: liga o `fora` na
        #                     `<tr>`, e o CSS da `aba10` esconde os glifos dali;
        #   `guarda.id`       continua vazio -> `—`, que é a verdade: sem peça
        #                     no lugar, não há ID a mostrar;
        #   `guarda.plastico` continua vazio: cor nenhuma, como já era.
        #
        # POR QUE AS QUATRO E NÃO SÓ AS DA MESA: o `forEach` do bootstrap
        # distribui a lista pela ordem do documento e escreve `''` no que sobra.
        # `''` apaga uma classe — nunca a LIGA. Mandar só as linhas da mesa
        # deixaria o `fora` sem quem o acendesse, e os glifos voltariam.
        nomes_da_mesa = [g.get("nome", "") for g in guarda]
        fora["guarda.nome"] = _com_os_lugares_vazios(
            nomes_da_mesa,
            lambda n: f"P{n} {PONTO_DO_ROTULO} {SEM_NINGUEM_AQUI}")
        fora["guarda.vazio"] = _com_os_lugares_vazios(
            ["" for _ in guarda], lambda _n: "sim")
        fora["guarda.id"] = _com_os_lugares_vazios(
            [g.get("id", "") for g in guarda], lambda _n: "")
        # A COR DO PLÁSTICO DA LINHA — 03/09/2026, IDENTIDADE-VEM-DE-CIMA. É a
        # barra de 3px que diz de quem é a linha, e ela era o `--plastico` do
        # DESENHO cravado no `<tr>`: enquanto o nome ao lado já vinha do
        # aparelho, a barra continuava na cor do controle do mockup.
        #
        # A LISTA SE DISTRIBUI pelas barras na ordem, e uma mesa menor que o
        # desenho deixa as barras que sobram com `''` — que APAGA a cor de
        # linha e devolve a barra ao `transparent` da classe. É o lugar vazio
        # não mostrando cor nenhuma, em vez de guardar a do mockup.
        fora["guarda.plastico"] = _com_os_lugares_vazios(
            [g.get("plastico", "") for g in guarda], lambda _n: "")
        # OS DOIS ABAIXO CONTINUAM SENDO MONTADOS, e o `pop` do fim é quem os
        # retira. Apagar as duas linhas daria o mesmo resultado hoje e deixaria
        # `NAO_PINTAVEIS` sem mordida: uma lista que não segura nada fica verde
        # para sempre e ninguém percebe quando o motivo dela caduca. Assim há
        # UM lugar que decide, e arrancá-lo faz a régua reprovar.
        # A COLUNA "AJUSTE PRÓPRIO", ACESA PELO PRODUTO — 03/09/2026.
        #
        # FATO DERRUBADO, e ele estava aqui: a linha era
        # `[s for g in guarda for s in (g.get("secoes") or [])]`. `secoes` é um
        # **dicionário** (`perfis_web._secoes_do_controle` devolve
        # `{secao: bool}`), e iterar um dicionário devolve as CHAVES — então
        # esta linha emitia `['leds','triggers','rumble','speaker']` para TODO
        # controle, quatro palavras todas verdadeiras, independentemente do que
        # o perfil guardasse. Ficou invisível porque `NAO_PINTAVEIS` a
        # segurava; no dia em que a coluna fosse pintada, ela acenderia tudo
        # para todo mundo — exatamente a mentira que a legenda desta aba avisa
        # ser pior que a tela apagada (*"uma tela que acende tudo nos quatro
        # ensinaria o contrário"*). Medido: com um perfil que guarda só
        # `rumble` do P1, o dicionário é
        # `{'leds': False, 'triggers': False, 'rumble': True, 'speaker': False}`
        # e a emissão mandava as quatro chaves.
        #
        # A ORDEM É A DO DESENHO, e a leitura é POR NOME. As células compartilham
        # um endereço só, e o bootstrap distribui a lista pela ordem do
        # documento (`hefesto_vivo.py`, `alvos.forEach(… i < v.length ? v[i] …)`):
        # uma linha da tabela é um bloco de `len(SECOES_DA_COLUNA)` valores. Ler
        # por nome, e não pela ordem do dicionário, é o que deixa o desenho ter
        # uma coluna a mais que o esquema sem casar célula com vizinha: a que
        # falta lê `None` e fica apagada, que é a verdade.
        #
        # FATO SUBSTITUÍDO: estas linhas diziam "o desenho ter CINCO colunas
        # enquanto o esquema tem quatro campos". O esquema tem cinco desde
        # `3f757b77`, e as duas listas são hoje a mesma — ver
        # `ESPERANDO_O_ESQUEMA`, que está vazia.
        #
        # SOBRA DE LINHA APAGA: a mesa dela tem dois controles e o desenho tem
        # quatro linhas. O `forEach` escreve `''` no que sobra, o alvo `classe`
        # lê isso como apagado, e a linha vazia deixa de exibir o que o MOCKUP
        # guardava. É o mesmo tratamento que `guarda.nome` e `guarda.id` já dão.
        por_linha = [
            ["sim" if (g.get("secoes") or {}).get(secao) else ""
             for secao in SECOES_DA_COLUNA]
            for g in guarda
        ]
        fora["guarda.secao"] = [
            valor
            for bloco in _com_os_lugares_vazios(
                por_linha, lambda _n: ["" for _ in SECOES_DA_COLUNA])
            for valor in bloco
        ]
        fora["guarda.linhas"] = str(len(guarda))

    # OS QUE NÃO SAEM — a lista é `NAO_PINTAVEIS`, e cada nome tem lá a sua
    # linha com a medição. (Este comentário dizia "OS QUATRO" quando a lista
    # tinha três: um número escrito em dois lugares diverge no primeiro dia.)
    # Este `pop` é o último ato de propósito: `pacote_da_aba` e o laço do editor
    # acima continuam produzindo tudo — quem decide o que a PÁGINA aguenta é
    # esta lista, num lugar só, e não cada emissão espalhada pelo arquivo.
    for chave in NAO_PINTAVEIS:
        fora.pop(chave, None)

    # A LISTA INTEIRA, TROCADA DE UMA VEZ — e é a maior entrega desta aba.
    # A razão, a prova e o que chega à tela por aqui estão em `_html_da_lista`.
    #
    # AS TRÊS LISTAS ACIMA (`perfis.linha.*`) FICAM, e não são redundância: elas
    # são o caminho de VOLTA. O `blocos` só pousa se `document.querySelector`
    # achar o `<tbody>`; numa página que mude o seletor, a pintura campo a campo
    # continua enchendo as catorze linhas do desenho. Duas portas para o mesmo
    # dado não brigam — o `blocos` roda ANTES no laço do piloto, e a distribuição
    # por endereço encontra os valores já no lugar e escreve zero.
    # O NOME DA LINHA ESCOLHIDA SAI DO PERFIL QUE O EDITOR ABRIU, e não do que
    # `_escolhido()` devolveu cru — 04/09/2026. Os dois quase sempre coincidem,
    # e o "quase" é o defeito: `_escolhido` guarda o que o CLIQUE trouxe, que é
    # o texto da célula; `alvo` é o objeto que `find_by_slug` achou no disco, e
    # é o `alvo.name` que a lista mostra. Comparar o texto cru com `x["nome"]`
    # perderia a marca em todo perfil cujo nome e slug divirjam — `Navegação`
    # contra `navegacao` é o caso que esta casa já pagou duas vezes.
    #
    # É O MESMO PERFIL QUE O EDITOR AO LADO ESTÁ MOSTRANDO (`editado=alvo`, no
    # alto desta função), e é isso que a marca promete a ela: a linha marcada é
    # a que os campos da direita e os nove botões vão mexer.
    escolhido_na_lista = str(getattr(alvo, "name", "") or escolhido)
    fora["blocos"] = {SELETOR_DA_LISTA: _html_da_lista(
        lista, str(bruto.get("lista_vazia") or ""), escolhido_na_lista)}
    fora["cobertura"] = {"pintados": len(fora) + len(lista) * 3, "sem_dono": 0}
    return fora




# ---------------------------------------------------------------------------
# OS GESTOS — ver o exemplo comentado em `a04_iluminacao.py`
# ---------------------------------------------------------------------------
from . import gesto  # noqa: E402


@gesto("10-perfis.html", "selecionar")
def selecionar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Abrir um perfil no editor. É o clique na CÉLULA DO NOME, na lista.

    ELE NÃO FALA COM O DAEMON, e é o único desta aba que não fala — de
    propósito. Escolher uma linha não muda nada no aparelho; muda o ALVO dos
    botões ao lado, que é o que a janela estável faz no
    `on_profile_selection_changed` (`profiles_actions.py:3020`). Ligar isto ao
    `profile.switch` faria passar o mouse pela lista trocar o perfil que está
    valendo — o oposto da coluna ter um botão "Ativar".

    E ELE NÃO RESPONDE CALADO: o editor ao lado repinta no tique seguinte com a
    prioridade daquele perfil (`editor.prioridade.n`). O campo Nome ainda não
    acompanha, e o motivo está no relato — ele é um `<input>`, e a pintura
    escreve `textContent` nele, que não aparece.

    `texto` é o nome VIVO porque a célula é a mesma que a pintura escreve
    (`perfis.linha.nome`).

    FATO SUBSTITUÍDO — 02/09/2026. Aqui estava escrito que ler o
    `data-hef-perfil` da linha *"traria o nome do MOCKUP: a pintura troca o
    texto e nunca reescreve o atributo"*. **Passou a reescrever, no mesmo commit
    que escreveu a frase:** `_linha_da_lista` emite `data-hef-perfil` com o nome
    vivo e o `blocos` troca o `<tbody>` inteiro. A escolha do `texto` continua
    certa por outra razão, e é a que vale: é o `texto` que o ouvinte do piloto
    manda para TODO gesto (`hefesto_vivo.py`, `texto: alvo.textContent`) — ler
    um atributo obrigaria o piloto a saber que esta aba é especial.
    """
    global _ESCOLHIDO
    nome = str(o.get("texto") or "").strip()
    if not nome:
        raise ValueError("selecionar: o clique não trouxe o nome do perfil")
    _ESCOLHIDO = nome


@gesto("10-perfis.html", "ativar")
def ativar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Ativar o perfil selecionado na tabela. `profile.switch`.

    O NOME VEM DO TEXTO DA LINHA, e não de um `data-` novo: a tabela já mostra o
    nome, e é o nome que o `profile.switch` quer. Marcar um segundo endereço com
    o mesmo valor seria a segunda verdade que esta casa persegue.

    DUAS CORREÇÕES DE 01/09/2026, ao ligar o resto da aba — e as duas são o
    mesmo defeito, que é o botão dizer "aplicado" sem ter aplicado:

    1. **A LINHA NÃO ERA CLICÁVEL.** O gesto lê o texto da linha, mas nenhum
       elemento da lista tinha endereço — o ouvinte do piloto casa
       `[data-gesto],[data-hef-gesto],…` (`hefesto_vivo.py:1000`) e a `<tr>` só
       trazia `data-hef-perfil`. Quem clicava num perfil não mandava nada; quem
       clicava no BOTÃO mandava `texto="Ativar"`, e o gesto pedia ao daemon um
       perfil chamado "Ativar". Agora a célula do nome marca `selecionar`, e o
       botão age sobre o escolhido — o `_ESCOLHIDO` vem primeiro, e o `texto`
       fica como último recurso (é o que a prova declarada exercita).
    2. **A RECUSA DO DAEMON SUMIA.** `profile_switch` devolve `False` quando ele
       não confirmou (`ipc_bridge.py:271`, ATIVAR-NAO-MENTE-01) e o retorno era
       descartado: o piloto imprimia "→ aplicado" sobre uma troca que não
       aconteceu. Levantar aqui é o que faz o botão recusar dizendo.
    """
    nome = _ESCOLHIDO or str(o.get("texto") or "").strip()
    if not nome:
        raise RuntimeError("ativar: escolha um perfil na lista primeiro")
    # A TERCEIRA GUARDA, e ela é POR QUE ESTE GESTO ESTAVA NA LISTA DOS
    # DEZESSEIS — 02/09/2026. O mapa o acusa de *"clicou, respondeu `aplicado`,
    # o estado do daemon não mudou"*, e a acusação está certa no FATO e errada
    # na causa: ele trocava para o perfil que JÁ ESTAVA VALENDO.
    #
    # A CADEIA, medida: `pacote()` roda a cada 500 ms e chama `_escolhido()`,
    # que grava `_ESCOLHIDO = ativo` quando ninguém clicou numa linha ainda
    # (a sincronização inicial, escrita lá de propósito). A régua de cliques
    # aciona os gestos SEM `selecionar` antes — então `ativar` sai com o nome
    # do perfil ATIVO, o daemon reaplica o mesmo arquivo, e `active_profile`
    # continua o mesmo. Nada mudou porque não havia nada a mudar.
    #
    # `mesmo_slug` e não `==`: com "Navegação" no disco e "Navegacao" no daemon
    # um `==` cru diria que são perfis diferentes e a guarda nunca pegaria
    # (R-10, `profiles/slug.py:52`) — o mesmo cuidado do "Voltar à de ontem".
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    ativo = _valendo(ctx)
    if ativo and mesmo_slug(ativo, nome):
        # `RuntimeError` E NÃO `ValueError` — ver `RECUSA-CHEGA-NA-TELA-01`.
        raise RuntimeError(
            f"“{nome}” já é o perfil que está valendo. Escolha outro na lista "
            f"da esquerda e clique em Ativar — reativar o mesmo não muda nada, "
            f"e dizer “aplicado” seria mentira.")
    # O CORPO, E NÃO SÓ O BOOLEANO — ELO-MUDO-01, 03/09/2026.
    #
    # `ipc_bridge.profile_switch` devolve `bool` e joga fora o `secoes` que o
    # daemon montou com cuidado: a diferença entre "ativado" e "ativado, menos o
    # que o lock manual descartou" (ATIVAR-NAO-MENTE-01). A janela estável lê
    # esse corpo desde sempre — `mensagem_de_ativacao(name, result)`
    # (`profiles_actions.py:889`) —, e aqui ele estava sendo descartado: ela
    # trocava de perfil e não ficava sabendo que metade não entrou.
    #
    # `ponte.resultado` é o degrau que entrega o corpo, com o MESMO teto de 3 s
    # (`ponte.TETOS["profile.switch"]` == `ipc_bridge.PROFILE_SWITCH_TIMEOUT_S`,
    # a cicatriz do handler de ~1,2 s). A frase da recusa continua sendo a
    # daqui, e não a genérica do `resultado`: ela nomeia o perfil.
    try:
        corpo = p.resultado("profile.switch", name=nome)
    except RuntimeError as erro:
        raise RuntimeError(
            f"o Hefesto não confirmou a troca para {nome!r}") from erro
    # A FRASE É DO PRODUTO. `mensagem_de_ativacao` cai na frase de sempre
    # ("Perfil ativado: X") quando tudo entrou ou quando o daemon não relatou, e
    # acrescenta o que NÃO entrou reusando `_mensagem_de_aplicacao` do rodapé —
    # a mesma função, as mesmas palavras. Escrever outra aqui seria o terceiro
    # dono da mesma frase.
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        mensagem_de_ativacao,
    )

    frase = mensagem_de_ativacao(nome, corpo)
    # A CARONA DO WRAPPER — CARONA-DO-WRAPPER-01, e é metade de um pedido dela:
    # *"ao clicarmos em aplicar ou salvar o perfil seja DENTRO ou fora da guia
    # de perfis"*. A janela estável a pega neste mesmo botão
    # (`profiles_actions.py:3232`). Sem ela, o `launch_env.refresh` que esta aba
    # já manda escreve um bilhete que a Steam não vai abrir: as Opções de
    # Inicialização ficam sem o `hefesto-launch`, e o jogo é instruído a ignorar
    # o vpad que nós criamos para ele — foi o defeito do Pragmata em 16/08.
    return _dizer(_com_a_carona(frase))


@gesto("10-perfis.html", "voltar-a-de-ontem")
def voltar_a_de_ontem(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """Desfazer a última gravação do perfil aberto. `profiles/loader.py`.

    O QUE ELE DESFAZ, e o produto já sabia fazer isto pelo terminal:
    `save_profile` copia o arquivo ANTERIOR para `profiles/.historico/<slug>/`
    a cada gravação (PERFIL-SEM-RASTRO-01, `loader.py:1230`), e
    `restaurar_do_historico` devolve a mais recente **byte a byte**
    (`loader.py:1509`). O único chamador até hoje era `profile restore` da CLI
    (`cli/cmd_profile.py:282`) — este é o segundo, e é uma tela.

    POR QUE NÃO PEDE CONFIRMAÇÃO, e é a diferença dele para o "Remover": a
    própria restauração ARQUIVA a versão atual antes de substituí-la, então
    restaurar por engano também tem volta. É o desfazer, não a perda.

    AS DUAS CHAMADAS DEPOIS DO DISCO NÃO SÃO ENFEITE:

    * `profile.switch` — **o daemon não relê JSON de perfil por conta
      própria** (PERFIL-SAVE-APPLY-01, `profiles_actions.py:3508`). Sem ele o
      arquivo volta ao que era e o controle continua com o de agora, que é o
      sintoma que ela leu como "não está salvando". Só quando o perfil restaurado
      é o que está VALENDO: reaplicar outro trocaria o perfil pelas costas dela.
    * `launch_env.refresh` — a regra pode ter mudado, e com ela o
      `steam_app_<id>.env` de antecipação. É o mesmo aviso que o Salvar e o
      Remover da janela estável mandam (`footer_actions.py:205`), e a ordem é a
      de lá: reaplicar primeiro, avisar depois.

    A COMPARAÇÃO É POR SLUG, não por string: com "Navegação" no disco e
    "Navegacao" no daemon, um `==` cru diria que são perfis diferentes e o
    reaplicar não aconteceria (R-10, `profiles/slug.py:52`).

    E ELE PASSOU A DIZER QUAL VERSÃO VOLTOU — 03/09/2026. **É o gesto em que o
    silêncio era mais caro desta aba**: o arquivo inteiro dela é substituído por
    outro, e a tela não mudava nada que ela pudesse ver (o editor mostra nome e
    regra; o que volta é gatilho, luz, vibração, máscara). Um desfazer mudo é
    indistinguível de um desfazer que não pegou.

    A FRASE É A DA CLI, que era o único chamador antes desta tela: *"perfil
    restaurado: X (versão …)"* (`cli/cmd_profile.py:295`). O carimbo da versão
    entra porque é ele que o `profile historico` lista  (noqa-acento: nome do
    subcomando da CLI, ASCII em `cmd_profile.py:233`) — é o que ela digita para
    voltar a outra, e sem ele a frase não diz de onde veio.

    O NOME, E NÃO O CAMINHO: a CLI imprime o `Path` que `restaurar_do_historico`
    devolve, porque quem lê está no terminal. A tira mostra o nome do perfil,
    que é como a lista ao lado o chama. E o carimbo vai sem o `.json` — é a
    forma que o `--em` do `profile restore` aceita (`loader.py:1478` casa as
    duas), então a frase é copiável para o comando que volta a outra versão.
    """
    from hefesto_dualsense4unix.profiles.loader import restaurar_do_historico
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    nome = _ESCOLHIDO or _valendo(ctx)
    if not nome:
        raise RuntimeError("voltar à de ontem: escolha um perfil na lista primeiro")
    # Levanta `FileNotFoundError` quando não há versão guardada, e a frase dela
    # já diz o que houve — o histórico nasce na PRÓXIMA gravação daquele perfil.
    _, versao = restaurar_do_historico(nome)
    ativo = _valendo(ctx)
    if ativo and mesmo_slug(ativo, nome):
        p.profile_switch(nome)
    p.chamar("launch_env.refresh")
    return _dizer(f"Perfil restaurado: {nome} · versão {versao.stem}")


# ---------------------------------------------------------------------------
# OS GESTOS QUE ESCREVEM NO DISCO — 01/09/2026, a segunda leva desta aba.
#
# O TETO CONTINUA SENDO O MESMO, e é o que dá forma a todos eles: **o daemon
# não tem `profile.save` nem `profile.delete`**. Gravar e apagar perfil roda no
# processo da janela, em `profiles/loader.py`, que é puro. Por isso cada um
# destes gestos tem a MESMA forma de três tempos:
#
#     1. escreve no disco       `save_profile` / `delete_profile`
#     2. reaplica, se for o ativo   `profile.switch` — o daemon NÃO relê JSON de
#                               perfil por conta própria (PERFIL-SAVE-APPLY-01)
#     3. avisa a antecipação    `launch_env.refresh` — a regra pode ter mudado,
#                               e com ela o `steam_app_<id>.env`
#
# A ordem é a da janela estável (`footer_actions.py:205`): reaplicar primeiro,
# avisar depois. Invertida, o refresh leria o perfil que ainda não valia.
# ---------------------------------------------------------------------------


def _perfil_do_editor(ctx: Contexto) -> str:
    """O perfil em que o editor está aberto. Vazio é RECUSA, nunca "o primeiro".

    É o mesmo alvo que `pacote()` manda pintar (`editado=`), e tem de ser: um
    gesto que agisse sobre outro perfil faria ela editar o que não está vendo.
    """
    nome = _ESCOLHIDO or _valendo(ctx)
    if not nome:
        raise RuntimeError("escolha um perfil na lista primeiro — a coluna da "
                           "esquerda; o editor abre na linha que você clicar.")
    return nome


#: O CAMINHO DE VOLTA do rótulo do seletor para a chave do produto. Ele é a
#: INVERSÃO de `perfis_web.AMBIENTE_DO_PRESET`, e não uma segunda tabela: o
#: dono das quatro palavras é aquele módulo, e digitá-las aqui seria a segunda
#: verdade no dia em que uma delas mudasse.
#:
#: "Estilo de Jogo" É A QUINTA OPÇÃO DO DESENHO e não está aqui — não existe
#: preset para ela (`profiles/simple_match.SIMPLE_MATCH_PRESETS` tem sete, e
#: nenhum é estilo). Cair fora desta tabela é o que faz o gesto RECUSAR
#: dizendo, em vez de gravar `MatchAny()` calado — que é o que
#: `from_simple_choice` faz com chave desconhecida (`simple_match.py:248`), e
#: seria a tela rebaixando a regra dela em silêncio.
PRESET_DO_ROTULO = {v: k for k, v in _tela.AMBIENTE_DO_PRESET.items()}


def _gravar(prof: Any, ctx: Contexto, p: Any, *, era: str = "") -> None:
    """Os três tempos: disco, reaplicar se for o ativo, avisar a antecipação.

    O CORPO MUDOU DE CASA em 01/09/2026, e a razão é que ele ganhou um SEGUNDO
    chamador: o `a06_navegacao`, que devolve os atalhos de botão ao de fábrica,
    precisa exatamente destes três tempos. Uma segunda cópia é a que esquece o
    `launch_env.refresh` no dia em que alguém mexer numa só — então o corpo foi
    para `pacotes/perfil.py`, que é o módulo que as abas já compartilham, e este
    nome fica como a porta desta aba.
    """
    perfil.gravar_e_reaplicar(prof, ctx, p, era=era)


def _nome_livre(base: str, todos: Any) -> str:
    """`base`, ou `base 2`, `base 3`… — o primeiro que não colide por SLUG.

    A colisão é por slug e não por nome à vista porque é o slug que vira nome
    de arquivo (`loader.save_profile:1419`): dois nomes que só diferem no
    acento caem no MESMO arquivo, e o segundo apagaria o primeiro sem uma
    palavra na tela — "Acao (cópia)" e "Ação (cópia)".  (noqa-acento: exemplo)
    """
    from hefesto_dualsense4unix.profiles.slug import slugify

    usados = {slugify(x.name) for x in todos}
    if slugify(base) not in usados:
        return base
    n = 2
    while slugify(f"{base} {n}") in usados:
        n += 1
    return f"{base} {n}"


#: O ARMAMENTO DO REBAIXAMENTO DE REGRA — `(perfil, quando)`, como o `_ARMADO`
#: do Remover e pelo mesmo motivo: esta janela não tem diálogo modal, e a
#: pergunta tem de caber no gesto.
_ARMADO_REBAIXAR: tuple[str, float] | None = None


def _pergunta_antes_de_rebaixar(prof: Any, chave: str) -> None:
    """Trocar "Funciona em" para "Todos" APAGA a regra. Pergunta antes.

    COR-A + SALVAR-NAO-REBAIXA-02, trazidas para esta tela em 03/09/2026. A
    janela estável tem CINCO perguntas no Salvar; a forma dos gestos daqui —
    um campo por vez, sem rascunho — dispensa três delas, e esta continuava
    aberta e alcançável em UM clique: **escolher "Todos" num perfil de jogo
    gravava o catch-all calado.** O perfil que valia só no Elden Ring passava a
    valer para tudo, sem aviso e sem volta pela tela.

    A GUARDA É A DA JANELA ESTÁVEL, condição por condição
    (`profiles_actions.py:3400`): a regra NOVA é `MatchAny` e a ANTIGA não é. O
    `MatchManual` e o `criteria` vazio entram junto — virar "vale para TUDO" é,
    nesses dois, a mudança mais violenta que a aba sabe fazer, e era a única que
    passava calada (é a razão de a guarda de lá não ser `isinstance(...,
    MatchCriteria)`).

    O RÓTULO DO QUE ELE É HOJE SAI DE `_match_label`, a mesma função pura que
    alimenta a coluna "Quando usar" — pelo argumento escrito no diálogo de lá:
    *"o diálogo não pode chamar de «programas específicos» um perfil que a lista
    chama de «Só manual»"*.

    AS DUAS PRIMEIRAS FRASES SÃO AS DO PRODUTO, palavra por palavra
    (`gui_dialogs.confirm_downgrade_match_to_any`); só o verbo da confirmação
    muda, porque lá quem confirma é um botão de diálogo e aqui é o segundo
    gesto. É a mesma adaptação que `remover` já fez com o diálogo de apagar.

    **A RECUSA SE DESFAZ SOZINHA NA TELA**, e isso é parte da cura: o
    `<select>` não está em `_uma_vez_so`, então o tique seguinte o repinta com
    o ambiente REAL do perfil. Ela vê o campo voltar — que é a verdade — e a
    tarja explicando por quê, por trinta segundos.
    """
    global _ARMADO_REBAIXAR
    from hefesto_dualsense4unix.app.actions.profiles_actions import _match_label
    from hefesto_dualsense4unix.profiles.schema import MatchAny

    if chave != "any" or isinstance(prof.match, MatchAny):
        _ARMADO_REBAIXAR = None
        return
    agora = time.monotonic()
    if (_ARMADO_REBAIXAR and _ARMADO_REBAIXAR[0] == prof.name
            and (agora - _ARMADO_REBAIXAR[1]) < SEGUNDOS_PARA_CONFIRMAR):
        _ARMADO_REBAIXAR = None
        return
    _ARMADO_REBAIXAR = (prof.name, agora)
    raise RuntimeError(
        f"O perfil “{prof.name}” não vale para tudo hoje — hoje ele é: "
        f"{_match_label(prof.match)}. Trocar para “Todos” faz ele valer para "
        f"TUDO (Quando usar: Sempre) e apaga os programas em que ele valia. "
        f"Escolha “Todos” de novo para confirmar — o campo espera oito segundos.")


def _jogo_reconhecido(texto: str) -> str:
    """O NOME do jogo daquele número, ou `""` — a decisão da janela estável.

    JOGO-QUE-SE-DIZ-01. `851100` sozinho não diz nada a ninguém, nem a ela daqui
    a um mês: a janela estável põe o nome do jogo ao lado do campo
    (`profile_jogo_reconhecido`, `profiles_actions._atualizar_frase_do_jogo`), e
    esta aba não tem esse rótulo no desenho. Enquanto ela não o tiver, o nome
    chega pelo DESFECHO do gesto que gravou a regra — que é o instante em que a
    pergunta "é esse jogo mesmo?" existe.

    A DECISÃO É DA FUNÇÃO PURA DO PRODUTO, e não desta tela:
    `jogos_locais.frase_do_campo_do_jogo(texto, nomes)` é a MESMA que alimenta o
    rótulo de lá, com as MESMAS quatro respostas — nome do jogo, "não instalado
    aqui (o número vale)", "não reconheci este endereço" e o silêncio de quem
    ainda está digitando. Escrever um `if` aqui seria a segunda verdade sobre o
    que é um jogo reconhecido.

    NUNCA LEVANTA, e é o mesmo contrato de `_com_a_carona`: ela é acabamento de
    um gesto que JÁ GRAVOU. Uma exceção lendo a biblioteca dela (33 `.acf` em
    duas pastas mais os `.desktop`) transformaria uma gravação bem-sucedida em
    tarja de recusa — e o perfil já está no disco.
    """
    try:
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            catalogo_de_jogos,
            frase_do_campo_do_jogo,
            nomes_por_appid,
        )

        decisao = frase_do_campo_do_jogo(texto, nomes_por_appid(catalogo_de_jogos()))
    except Exception:
        return ""
    return "" if decisao is None else str(decisao[0])


def _agora_vale_em(prof: Any, texto: str = "") -> str:
    """A frase de desfecho de quem trocou a REGRA do perfil. Um dono, três gestos.

    O RÓTULO SAI DE `_match_label`, a mesma função pura que alimenta a coluna
    "Quando usar" — pelo argumento que `_pergunta_antes_de_rebaixar` já usa
    logo acima: *o desfecho não pode chamar de outra coisa um perfil que a
    lista chama de "Só manual"*.

    `texto` É O QUE ELA DIGITOU (ou o appid que o Detectar achou), e serve só
    para o nome do jogo. Vazio, a frase termina no rótulo — que é o certo para
    "Todos" e "Steam", onde jogo nenhum entra na regra.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import _match_label

    frase = f"“{prof.name}” agora vale em: {_match_label(prof.match)}"
    jogo = _jogo_reconhecido(texto) if texto else ""
    return f"{frase} · {jogo}" if jogo else frase


def _so_mudou(o: dict[str, Any]) -> bool:
    """`False` quando o clique foi só um clique — e aí o campo não age.

    MEDIDO NO CHROME em 01/09/2026, injetando o `BOOTSTRAP` do piloto sobre o
    `layout/10-perfis.html` e trocando o `postMessage` por um coletor. Mexer
    nos quatro campos como ela mexeria produziu **treze** mensagens, e quatro
    delas são `evento=click`:

        editor.nome   tipo=input   evento=change  valor='Elden Ring BR'
        editor.jogo   tipo=input   evento=click   valor='1245620'      ← só cliquei
        editor.jogo   tipo=input   evento=change  valor='1599660'
        editor.nome   tipo=input   evento=click   valor='Elden Ring BR' ← só cliquei

    O ouvinte do piloto escuta `click` E `change` (`hefesto_vivo.py:1034-1035`), e
    **clicar dentro de um campo para pôr o cursor manda o valor que já estava
    lá**. Sem esta guarda, clicar no "Nome do Jogo" de um perfil em "Todos"
    faria o gesto inferir a regra e GRAVAR — uma troca de regra disparada por
    um clique que não mudou nada.

    A guarda é `!= "click"`, e não `== "change"`, de propósito: um clique de
    régua (um dicionário montado à mão, sem `evento`) tem de continuar valendo.
    """
    return str(o.get("evento") or "") != "click"


@gesto("10-perfis.html", "editor.nome")
def editor_nome(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Renomear o perfil aberto no editor. `save_profile` + `delete_profile`.

    O VALOR VEM DE `valor`, E NÃO DE `texto` — foi a causa nomeada na primeira
    leva: *"o ouvinte manda `texto: alvo.textContent`, que num `<input>` é
    vazio"*. Desde 01/09 o clique traz o `value` do campo
    (`hefesto_vivo.py:228`) e o piloto escuta `change` além de `click`, que é o
    único evento que um campo de texto dispara com o valor novo.

    POR QUE RENOMEAR NA HORA, e não guardar num rascunho: decisão dela de
    01/09 — *"clicar na cor já deveria aplicar a cor no controle"* —, e esta aba
    não tem "Salvar" próprio (o do rodapé grava o perfil ATIVO a partir do que
    está valendo no daemon, `rodape.py:114`, e nem olha para este campo). Um
    campo que aceita texto e não guarda nada é o botão que responde calado.

    NÃO HÁ `rename` NO PRODUTO — medido: `profiles/loader.py` tem
    `save_profile`, `delete_profile`, `load_profile` e `restaurar_do_historico`,
    e nenhum renomeia. A janela estável faz a mesma dupla no Salvar, com o
    diálogo do R-10 se oferecendo para apagar o antigo. Aqui a ordem é gravar
    PRIMEIRO e apagar depois: invertida, uma falha no meio perderia o perfil.

    E O ANTIGO NÃO SOME DE VEZ: `delete_profile` arquiva a última versão em
    `profiles/.historico/<slug>/` antes do `unlink` (PERFIL-SEM-RASTRO-01,
    `loader.py:1601`). Um renomear por engano se desfaz com
    `hefesto-dualsense4unix profile restore <nome-antigo>`.

    AS DUAS RECUSAS:

    * nome vazio — apagar o campo não pode virar um arquivo `.json`;
    * nome que já é de OUTRO perfil — o `save_profile` grava por SLUG, então
      renomear "Elden Ring" para "Pragmata" gravaria por cima do Pragmata dela,
      calado. É o mesmo estrago que o `_nome_livre` evita no Duplicar.

    E ELE PASSOU A DIZER QUE RENOMEOU — 03/09/2026, ver `_dizer`. O campo
    voltava ao normal e mais nada: um gesto que APAGA um `.json` e cria outro
    terminava mudo, e o único jeito de saber que pegou era esperar a lista
    repintar. A frase é a do produto, `mensagem_do_salvar(nome, renomeado_de=…)`
    (`profiles_actions.py:913`) — a MESMA que o rodapé da janela estável
    escreve, "Perfil renomeado: era → novo".

    SEM `reaplicou=`, e é o honesto: quem reaplica é `gravar_e_reaplicar`, que
    devolve `None` (`pacotes/perfil.py:153`). Deduzir aqui se o daemon recebeu
    seria a segunda verdade sobre uma coisa que este gesto não mediu — e a
    frase de três estados de `mensagem_do_salvar` existe exatamente para não
    prometer o controle quando ninguém olhou para ele.
    """
    global _ESCOLHIDO
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        mensagem_do_salvar,
    )
    from hefesto_dualsense4unix.profiles.loader import (
        delete_profile,
        load_all_profiles,
        load_profile,
    )
    from hefesto_dualsense4unix.profiles.slug import slugify

    if not _so_mudou(o):
        return None
    novo = str(o.get("valor") or "").strip()
    era = _perfil_do_editor(ctx)
    if not novo:
        raise RuntimeError("o perfil precisa de um nome — o campo ficou vazio.")
    prof = load_profile(era)
    if prof.name == novo:
        return None
    troca_de_arquivo = slugify(novo) != slugify(prof.name)
    if troca_de_arquivo:
        for outro in load_all_profiles():
            if slugify(outro.name) == slugify(novo):
                raise RuntimeError(
                    f"já existe um perfil chamado “{outro.name}”. Escolha outro "
                    f"nome — gravar este por cima apagaria o dele.")
    _gravar(prof.model_copy(update={"name": novo}), ctx, p, era=era)
    if troca_de_arquivo:
        delete_profile(era)
    _ESCOLHIDO = novo
    return _dizer(mensagem_do_salvar(novo, renomeado_de=prof.name))


@gesto("10-perfis.html", "editor.prioridade")
def editor_prioridade(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Prioridade": o número que decide quem vence quando dois perfis servem.

    **ERA O ÚNICO CAMPO DO EDITOR SEM NENHUM CAMINHO DE ESCRITA** na interface
    nova, e o próprio produto já dizia por quê
    (`perfis_web.DONOS_DOS_GESTOS["editor.prioridade"]`): *"NO DESENHO NÃO HÁ
    CONTROLE: o mockup traz `<span class="trilho">`, que não se arrasta"*. Ela
    pediu o conserto em 27/08 — *"prioridade é slicer"* — e reconfirmou em
    03/09/2026, escolhendo **"Slider, como você pediu"**. O `<input type=range>`
    nasceu no `aba10.py`, vestido com o CSS do trilho que já existia.

    POR QUE ISSO NÃO É ENFEITE, e a medição é do próprio produto: o perfil que
    ela criou para o Pragmata nasceu em prioridade 0 e **nunca valia no jogo**,
    porque o catch-all dela (prioridade 100) vencia em todo o resto — está
    escrito na docstring do gesto `novo`. Sem este campo, o único conserto era
    editar o `.json` na mão.

    A FAIXA É A DO ESQUEMA, não uma digitada: `PRIORIDADE_MINIMA` e
    `PRIORIDADE_MAXIMA` moram em `profiles/schema.py` desde a UNIFICA-CONSTANTE-01
    e têm portão próprio (`test_teto_da_prioridade_tem_uma_fonte_so.py`). O
    `<input>` recebe os dois no `min`/`max`, e esta guarda os cobra de novo —
    porque um clique pode chegar de qualquer lugar, inclusive de uma régua, e um
    número fora da faixa iria direto para o `.json` dela.

    `_so_mudou` SEGURA O CLIQUE SOLTO, e aqui ele é mais necessário que nos
    campos de texto: o ouvinte do piloto escuta `click` E `change`
    (`hefesto_vivo.py`), e um `<input type=range>` dispara os DOIS num toque só.
    Sem a guarda, cada arrasto gravaria duas vezes — e a segunda gravação é o
    que faz o daemon reaplicar o perfil no meio da partida.

    **O DESFECHO REPINTA OS DOIS VIZINHOS NA HORA**, e essa é a metade que faz o
    slider parecer vivo. O tique é de 100 ms; enquanto ele não vem, a barra
    `.cheio` e o número ao lado continuam no valor do disco — o punho no lugar
    novo e a barra atrás dele. A resposta do gesto (`_dizer` devolve `mesa:`,
    que o piloto pinta na hora) leva a largura e o número junto com a frase.

    A LARGURA VAI EM NÚMERO PURO, sem `%` e sem travessão: o ramo `largura` do
    `escrever()` faz `el.style.width = t + '%'`, e um `'45%'` viraria `'45%%'` —
    CSS inválido, largura congelada no desenho e o contador somando +1 por
    tique. A conta é a mesma de `perfis_web._pacote_do_editor`, e ela é PERGUNTA
    ao teto, não uma divisão por 100.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        mensagem_do_salvar,
    )
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.profiles.schema import (
        PRIORIDADE_MAXIMA,
        PRIORIDADE_MINIMA,
    )

    if not _so_mudou(o):
        return None
    cru = str(o.get("valor") or "").strip()
    nome = _perfil_do_editor(ctx)
    try:
        novo = int(float(cru))
    except ValueError:
        raise RuntimeError(
            f"a prioridade tem de ser um número, e o campo mandou “{cru}”. "
            f"Nada foi salvo.") from None
    if not PRIORIDADE_MINIMA <= novo <= PRIORIDADE_MAXIMA:
        raise RuntimeError(
            f"prioridade {novo} está fora da faixa que o perfil aceita "
            f"({PRIORIDADE_MINIMA} a {PRIORIDADE_MAXIMA}). Nada foi salvo.")
    prof = load_profile(nome)
    if int(prof.priority or 0) == novo:
        return None
    _gravar(prof.model_copy(update={"priority": novo}), ctx, p)
    resposta = _dizer(f"{mensagem_do_salvar(prof.name)} · prioridade {novo}")
    pct = round(novo * 100 / PRIORIDADE_MAXIMA) if PRIORIDADE_MAXIMA else 0
    resposta["mesa"]["editor.prioridade"] = str(pct)
    resposta["mesa"]["editor.prioridade.n"] = str(novo)
    return resposta


@gesto("10-perfis.html", "editor.ambiente")
def editor_ambiente(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Funciona em": trocar a REGRA que faz o perfil entrar. `from_simple_choice`.

    QUEM MONTA A REGRA É O PRODUTO, e não este arquivo:
    `profiles/simple_match.from_simple_choice:203` é a mesma função que o Salvar
    da janela estável usa (`profiles_actions._build_profile_from_editor`), com
    as frases de recusa já escritas em português ("Diga o número do jogo na
    Steam (ex.: 1599660)"). Montar um `MatchCriteria` aqui seria a segunda
    verdade sobre o que cada opção significa.

    O `regra_do_disco` NÃO É ENFEITE: para "Jogo da Steam" ele preserva o
    `process_name` do MESMO jogo, que ela nunca viu na tela e portanto nunca
    pediu para tirar (ESCONDER-EM-VEZ-DE-SAIR-01, `simple_match.py:382`).

    AS DUAS RECUSAS, e as duas existem para não REBAIXAR a regra dela:

    * **o seletor travado** — quando o perfil casa por uma regra que esta tela
      não sabe mostrar (`window_title_regex`, lista de classes), o produto abre
      o campo travado com a frase do que fazer (`perfis_web.py:233`). Aceitar a
      troca ali seria o defeito R-12: substituir uma regra fina por "Todos".
      MEDIDO: sete dos nove perfis de fábrica caem nesse estado.
    * **"Estilo de Jogo"** — é a quinta opção do desenho e não tem preset
      nenhum atrás. `from_simple_choice` devolve `MatchAny()` para chave
      desconhecida, sem reclamar (`simple_match.py:248`): escolher "Estilo de
      Jogo" gravaria um catch-all no lugar da regra do jogo dela, em silêncio.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice

    if not _so_mudou(o):
        return None
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    nome = _perfil_do_editor(ctx)
    chave = PRESET_DO_ROTULO.get(rotulo)
    if chave is None:
        raise RuntimeError(
            f"“{rotulo}” não é uma regra que o perfil saiba guardar. O produto "
            f"conhece {', '.join(sorted(PRESET_DO_ROTULO))} — “Estilo de Jogo” "
            f"está desenhado e não tem campo nem preset atrás dele.")
    prof = load_profile(nome)
    editor = _editor_de(prof)
    if editor.get("ambiente_travado"):
        raise RuntimeError(str(editor.get("ambiente_recado") or ""))
    _pergunta_antes_de_rebaixar(prof, chave)
    # O NOME DO JOGO VEM DO DISCO, e não do campo ao lado: o `<input>` pode ter
    # texto que ela digitou e ainda não confirmou (o `change` só dispara quando
    # o foco sai). Ler o disco é ler o que o perfil de fato tem.
    prof.match = from_simple_choice(chave, editor.get("jogo") or "",
                                    regra_do_disco=prof.match)
    _gravar(prof, ctx, p)
    return _dizer(f"“{prof.name}” agora vale em: {rotulo}")


# O `_sem_a_sprint` MORREU AQUI — 03/09/2026, e a morte é a entrega. Ele
# aparava o `(ONDA-PERFIS-04)` do fim da frase de `GESTOS_SEM_MOTOR` para a
# tarja dela não carregar endereço de fila. A frase saiu daquela tabela porque
# o campo ganhou motor; sem chamador, a função vira o "campo morto com nome de
# promessa" que esta casa já nomeou. Quem precisar de novo aparar um rótulo de
# sprint reescreve duas linhas — guardá-la desligada custaria mais.


def _com_o_estilo(prof: Any, estilo: Any, mesa: list[dict[str, Any]]) -> tuple[Any, int]:
    """O perfil com a receita do estilo dentro, e QUANTOS controles ganharam cor.

    AS TRÊS COISAS QUE O ESTILO ESCREVE são as que ela aprovou em 03/09/2026 ao
    mandar construir o motor — **gatilho + vibração + luz** —, e cada uma vai
    para o lugar que já era dela no esquema:

        `estilo.gatilho`  → `triggers.left/right.mode`, nos DOIS lados
        `estilo.vibracao` → `rumble.policy` (o degrau, não um multiplicador)
        a cor            → `controllers[uniq].leds`, **uma por unidade**

    OS PARÂMETROS DO GATILHO NÃO SÃO DIGITADOS. `Estilo.gatilho` guarda só a
    CHAVE do modo (`AutoGun`, `PulseB`…), e as factories do produto exigem
    posicionais sem default — um `params=[]` passaria pelo esquema e explodiria
    lá no `apply()`, ou pior: `simple_rigid` com zonas zeradas é *"nenhuma zona
    ativa"*, o gatilho fica solto e a tela diz que aplicou. Quem sabe os números
    é `app/actions/trigger_specs.PRESETS`, e `preset_to_positional_params(spec,
    {})` devolve exatamente o padrão de cada modo. É a mesma porta que a aba
    Gatilhos usa (`a03_gatilhos._padroes`).

    A LUZ É POR UNIDADE PORQUE A LEI É DELA, verbatim: *"nenhuma cor dos
    controles nunca pode ser a mesma, mesmo no mesmo perfil e estilo de jogo.
    Dentro da paleta de fps tem que ter variações pra cada unidade de
    controle."* Quem garante isso, medindo, é `estilos_de_jogo.as_quatro` — e
    por isso a cor sai de `cor_da_unidade(estilo, jogador)`, nunca de uma cor
    escrita aqui. **O global `leds` NÃO é tocado**: uma cor no global é a cor
    que os quatro herdariam, que é exatamente o defeito que a lei dela proíbe.

    E DOIS CONTROLES NO MESMO LUGAR É RECUSA, não escolha silenciosa: dois
    `jogador` iguais na mesa dariam a MESMA cor às duas peças, com o motor
    inocente. É o único caminho pelo qual a lei dela cairia depois de o motor
    dizer que está tudo distinto.

    `LedsConfig` COM DOIS CAMPOS SÓ, e isso é contrato: `_controllers_to_specs`
    lê `model_fields_set` (`profiles/manager.py`), então escrever `lightbar` e
    `lightbar_brightness` deixa `player_leds` e `auto_player_colors` SEM
    OPINIÃO — o controle continua herdando o resto do perfil. Um `LedsConfig`
    "cheio" apagaria os LEDs de jogador de quem nunca pediu isso.
    """
    from hefesto_dualsense4unix.app.actions import trigger_specs as specs
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import cor_da_unidade
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        LedsConfig,
        RumbleConfig,
        TriggerConfig,
        TriggersConfig,
    )

    mudanca: dict[str, Any] = {}
    if estilo.gatilho:
        spec = specs.get_spec(estilo.gatilho)
        if spec is None:  # pragma: no cover — o motor só nomeia modo do produto
            raise RuntimeError(
                f"o estilo “{estilo.rotulo}” pede o gatilho {estilo.gatilho!r}, "
                f"que não é um dos modos do produto. Nada foi salvo.")
        lado = TriggerConfig(
            mode=estilo.gatilho,
            params=list(specs.preset_to_positional_params(spec, {})))
        mudanca["triggers"] = TriggersConfig(left=lado, right=lado)
    if estilo.vibracao:
        # CONSTRUÍDO, e não `model_copy`: o `custom_mult` do perfil antigo é
        # recusado pelo esquema fora de `policy="custom"`, e `model_copy` NÃO
        # revalida — o perfil sairia daqui inválido e só quebraria no load
        # seguinte, longe daqui. `passthrough` é o único campo que se preserva:
        # ele não descreve intensidade, descreve QUEM manda na vibração.
        mudanca["rumble"] = RumbleConfig(
            passthrough=bool(getattr(prof.rumble, "passthrough", True)),
            policy=estilo.vibracao)

    atuais = dict(prof.controllers or {})
    lugares: dict[int, str] = {}
    pintados = 0
    for controle in mesa:
        uniq = str(controle.get("uniq") or "").replace(":", "").lower()
        # O `jogador` VEM COMO `int` de `base.numero_do_controle`, e o `int()`
        # aqui não é desconfiança: a mesa também chega de régua e de ensaio, e
        # um `"1"` de string cairia fora calado — a cor nunca chegaria àquela
        # peça e ninguém saberia por quê.
        try:
            jogador = int(controle.get("jogador"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        # FORA DA MESA DE QUATRO ele é PULADO, e não é omissão: `as_quatro` só
        # sabe separar quatro, e é a mesa que o produto desenha. Um quinto
        # controle fica com a cor que já tinha — o desfecho conta quantos foram,
        # e prometer cor a quem não recebeu seria a tela afirmando o que não fez.
        if not uniq or not 1 <= jogador <= 4:
            continue
        if jogador in lugares and lugares[jogador] != uniq:
            raise RuntimeError(
                f"dois controles estão no lugar P{jogador} da mesa, e o estilo "
                f"daria a MESMA cor aos dois — a regra é que nenhum controle "
                f"repete a cor de outro. Nada foi salvo.")
        lugares[jogador] = uniq
        dele = atuais.get(uniq) or ControllerOverrides()
        atuais[uniq] = dele.model_copy(update={"leds": LedsConfig(
            lightbar=cor_da_unidade(estilo, jogador),
            lightbar_brightness=estilo.brilho)})
        pintados += 1
    if pintados:
        mudanca["controllers"] = atuais
    return prof.model_copy(update=mudanca), pintados


@gesto("10-perfis.html", "editor.estilo")
def editor_estilo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Estilo de Jogo": escolher um APLICA a receita inteira no perfil.

    **ELE GANHOU MOTOR EM 03/09/2026, e a decisão de construí-lo é dela.**
    Perguntada se o motor devia existir, respondeu *"Construir o motor"*, e
    escolheu o alcance: **gatilho + vibração + luz**. As quinze receitas estão
    em `profiles/estilos_de_jogo.py` — *"o resto ta aprovado"* —, e é de lá que
    saem tanto os rótulos do `<select>` (`aba10.ESTILOS`) quanto o que cada um
    faz. **Não há tabela de estilo neste arquivo**, e não pode haver: uma
    segunda cópia da receita divergiria no dia em que ela mudasse uma.

    O QUE ELE ERA ATÉ HOJE DE MANHÃ, medido no produto instalado com o daemon
    dela vivo e um DualSense White no cabo:

        estilo_na_tela: "Terror"      ← a tela AFIRMA o estilo, e continua
        tarjas: []                    ← ninguém disse nada
        md5 de meu_perfil.json:  b4387a17…  ANTES **e** DEPOIS — nada gravou

    À tarde ele passou a RECUSAR dizendo, o que já era melhor que o silêncio.
    Agora ele **grava** — e é a diferença entre a tela pedir desculpa e a tela
    fazer o trabalho.

    O ESTILO NÃO FICA GUARDADO NO PERFIL, e isso é a coisa mais importante a
    entender aqui: `Profile` não tem campo de estilo, e não ganhou um. O estilo
    é um **verbo**, não um campo — ele resolve gatilho, vibração e luz de uma
    vez, e a partir daí quem manda são esses três, que ela pode reajustar nas
    abas sem nada "voltar atrás". Por isso `editor.estilo` continua em
    `NAO_PINTAVEIS` e o `<select>` continua abrindo no travessão: afirmar um
    estilo depois do clique seria a tela dizendo que guardou o que não guardou.

    "PERSONALIZADO" NÃO MEXE EM NADA, e é o único que responde sem gravar. Ele é
    o estilo que diz *"eu ajusto na mão"* — `as_quatro()` levanta de propósito se
    alguém lhe pedir a cor. A resposta é um DESFECHO (a tira do rodapé), não uma
    tarja de recusa: escolher "Personalizado" é uma escolha legítima, e recusar
    dizendo faria a tela tratar de erro o que é o comportamento pedido.

    `RuntimeError` NAS RECUSAS — ver `RECUSA-CHEGA-NA-TELA-01`, no alto do
    arquivo: é a única classe que `_recusou_dizendo` leva ao DOM.

    ELE SAIU DE `SEM_ECO`, e continua fora: o `state_full` não publica nada do
    conteúdo do perfil, então a gravação não ecoa — mas o `_gravar` chama
    `profile.switch` quando o perfil é o ativo, e é isso que faz a luz e o
    gatilho chegarem ao aparelho no mesmo segundo.
    """
    from hefesto_dualsense4unix.profiles import estilos_de_jogo as receitas
    from hefesto_dualsense4unix.profiles.loader import load_profile

    # SEM `_so_mudou`: um `<select>` clicado sem trocar de opção não vale como
    # escolha nova, mas o `change` é o único evento que traz a opção nova — e
    # aplicar de novo a MESMA receita é idempotente por construção. O que a
    # guarda evitaria aqui é uma gravação repetida; o que ela custaria é a
    # primeira escolha dela passar calada, que foi o defeito de manhã.
    #
    # O `valor` PRIMEIRO E O `rotulo` DEPOIS, e o travessão não conta como
    # escolha: a primeira opção do desenho é `<option value="">—</option>`, então
    # o clique que não escolheu nada chega com `valor=""` e `rotulo="—"`.
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip()
    if escolhido == "—":
        escolhido = ""
    if not escolhido:
        raise RuntimeError(
            "escolha um Estilo de Jogo na lista — um Estilo de Jogo não foi "
            "salvo, e o que vale continua sendo o que está nas abas.")
    estilo = receitas.POR_ROTULO.get(escolhido)
    if estilo is None:
        raise RuntimeError(
            f"“{escolhido}” não é um dos Estilos de Jogo do produto. Nada foi "
            f"salvo, e o que vale continua sendo o que está nas abas.")
    nome = _perfil_do_editor(ctx)
    if estilo.chave == "personalizado":
        return _dizer(
            f"“{estilo.rotulo}” não mexe em nada: é o estilo que diz “eu ajusto "
            f"na mão”. O que vale em “{nome}” continua sendo o que está nas abas.")
    prof = load_profile(nome)
    novo, pintados = _com_o_estilo(prof, estilo, ctx.mesa)
    _gravar(novo, ctx, p)
    # O DESFECHO DIZ AS TRÊS COISAS, e a da luz diz QUANTAS peças alcançou. Com
    # a mesa vazia o gatilho e a vibração entram do mesmo jeito — e prometer cor
    # a zero controles seria a tela afirmando o que não fez.
    luz = (f"e a luz de {pintados} controle{'s' if pintados != 1 else ''}"
           if pintados else "e nenhum controle na mesa para acender")
    return _dizer(
        f"“{estilo.rotulo}” aplicado em “{prof.name}”: gatilho, vibração {luz}.")


@gesto("10-perfis.html", "editor.jogo")
def editor_jogo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Nome do Jogo": o programa (ou o número da Steam) que faz o perfil entrar.

    ELE SÓ TEM EFEITO EM DUAS DAS CINCO OPÇÕES do "Funciona em":
    `from_simple_choice` só lê o `custom_name` em "game" e "steam_game"
    (`simple_match.py:236-247`). Com o seletor em "Todos" ou "Steam", o texto
    seria descartado sem uma palavra — ela digitaria o nome do jogo, veria o
    campo aceitar, e a regra continuaria a mesma.

    ENTÃO O SELETOR ANDA JUNTO, e isso desfaz um IMPASSE que eu mesmo criei e
    medi antes de entregar: com o perfil em "Todos", escolher "Jogo" no seletor
    recusava por falta de nome (`MSG_JOGO_SEM_NOME`), e digitar o nome recusava
    por o seletor estar em "Todos". **Os dois caminhos fechados, e o perfil
    preso em "Todos" para sempre.** Digitar o nome de um jogo é dizer "este
    perfil é deste jogo": o gesto grava a regra inteira, e o seletor mostra o
    resultado no tique seguinte.

    O PRODUTO JÁ FAZ ISSO, e não é invenção desta tela: o
    `_aplicar_nascimento_com_jogo` (`profiles_actions.py:3124`) chama
    `_select_radio("steam_game")` **e** preenche o campo, no mesmo gesto.

    QUAL DAS DUAS ELE ESCOLHE: `normalize_appid` decide — só dígitos (ou um
    endereço da loja, que ele sabe ler) é "Jogo da Steam"; qualquer outra coisa
    é "Jogo", com o nome do programa. E ele SÓ decide quando o seletor não
    estava numa das TRÊS que têm campo livre: com "Jogo", "Jogo da Steam" ou
    "Jogo (pela janela)" já escolhido por ela, a escolha dela manda — digitar
    "1245620" num perfil que ela pôs em "Jogo" não pode virar um perfil da
    Steam pelas costas dela. (A terceira entrou em 06/09/2026, ONDA5-10-01.)

    R-12: o nome do programa vai **como ela digitar**, sem `.lower()` — o
    matcher compara com o basename cru de `/proc/PID/exe`, e
    `Cyberpunk2077.exe` nunca casaria com `cyberpunk2077.exe`.

    E ELE PASSOU A DIZER O QUE GRAVOU — 03/09/2026. Ele **reescreve a regra
    INTEIRA** do perfil e movia o seletor junto, calado: ela digitava um número,
    o campo aceitava, e o único sinal era o `<select>` mudar no tique seguinte.
    O desfecho nomeia as duas coisas que mudaram — o rótulo novo do "Quando
    usar" e, quando o número é de um jogo que esta máquina conhece, o NOME dele.
    É o degrau que faltava para ela conferir o que digitou (JOGO-QUE-SE-DIZ-01).

    **E O CAMPO SE CORRIGE — 04/09/2026, decisão [04] do PO.** Colar o endereço
    da loja funciona: `normalize_appid` lê o número de dentro dele e a regra
    grava o número. O que ficava errado era a TELA — o campo continuava
    mostrando `https://store.steampowered.com/app/1599660/…` sobre uma regra que
    já guardava `1599660`, e assim ficava até ela trocar de perfil. A janela
    antiga trocava o endereço pelo número na frente dela.

    **A CORREÇÃO SÓ CABE AQUI, e a razão é medida:** `editor.jogo` está em
    `CAMPOS_QUE_ELA_DIGITA`, logo o tique NÃO o repinta enquanto ela está no
    mesmo perfil (senão a pintura apagaria a segunda tecla que ela digita). O
    único instante em que a tela pode devolver a forma canônica é a resposta
    deste gesto — e ela é pintada na hora, sem esperar os 500 ms.

    O VALOR SAI DE `simple_extra(prof.match)`, e não de um `if` meu: é a MESMA
    função que `perfis_web._pacote_do_editor` usa para encher este campo a cada
    tique. Escrever aqui "o appid quando é steam_game, o texto quando não é"
    seria a segunda verdade sobre o que este campo mostra — e as duas
    divergiriam no dia em que a regra ganhasse uma terceira forma.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.profiles.simple_match import (
        from_simple_choice,
        normalize_appid,
        simple_extra,
    )

    if not _so_mudou(o):
        return None
    texto = str(o.get("valor") or "").strip()
    nome = _perfil_do_editor(ctx)
    prof = load_profile(nome)
    editor = _editor_de(prof)
    if editor.get("ambiente_travado"):
        raise RuntimeError(str(editor.get("ambiente_recado") or ""))
    # AS TRÊS FORMAS COM CAMPO LIVRE, e a terceira entrou em 06/09/2026: com o
    # seletor já em "Jogo (pela janela)", a escolha DELA manda — sem a "janela"
    # nesta tupla, editar o campo de um perfil de janela o reescreveria como
    # `process_name`, que é outro dado e casa por acaso. É o mesmo argumento do
    # parágrafo "E ele SÓ decide quando o seletor não estava numa das duas".
    chave = PRESET_DO_ROTULO.get(str(editor.get("ambiente") or ""))
    if chave not in ("game", "steam_game", "janela"):
        chave = "steam_game" if normalize_appid(texto) is not None else "game"
    prof.match = from_simple_choice(chave, texto, regra_do_disco=prof.match)
    _gravar(prof, ctx, p)
    # O `or texto` É O PISO, e não zelo: `simple_extra` devolve `""` para uma
    # regra que não guarda extra nenhum, e escrever vazio num campo faz o
    # `escrever()` do piloto pôr um travessão — a tela apagaria o que ela acabou
    # de digitar e diria "não sei" sobre um valor que ela vê no disco.
    return _dizer(_agora_vale_em(prof, texto),
                  **{"editor.jogo": simple_extra(prof.match) or texto})


@gesto("10-perfis.html", "detectar")
def detectar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Detectar": pegar o jogo em foco e montar a regra com ele.

    A AFIRMAÇÃO QUE ESTAVA NO PRODUTO ESTÁ ERRADA PELA METADE, e é o que
    destravou este botão. `perfis_web.DONOS_DOS_GESTOS["detectar"]` diz *"o IPC
    NÃO PUBLICA o título nem a classe"* — e daí a primeira leva o deixou sem
    dono. MEDIDO em 01/09/2026, contra o daemon `dev` desta árvore, com
    `ipc_bridge.daemon_state_full()`: das 49 chaves do `state_full`, SETE são
    de detecção de janela, e duas delas são a classe —
    `window_detect_last_class` e `window_detect_current_class`. O TÍTULO é que
    não é publicado. A janela estável já lia exatamente esta chave desde o
    PERFIL-NASCE-CERTO-01 (`profiles_actions._aplicar_nascimento_com_jogo`).

    O QUE ELE FAZ E O QUE AINDA NÃO FAZ:

    * **jogo da Steam** — a classe vem como `steam_app_<id>` e o appid sai dela
      pela fonte única do produto (`profiles/steam_app.steam_appid_from_wm_class`,
      UNIFICA-PREDICADO-01). A regra vira "Jogo da Steam" com aquele número.
    * **jogo de fora da Steam** — GRAVA A CLASSE, desde 06/09/2026
      (ONDA5-10-01). A regra vira "Jogo (pela janela)" com aquela `wm_class`.

      **AQUI ESTAVA ESCRITA UMA RECUSA, e o raciocínio dela estava certo e a
      conclusão não seguia.** Ele dizia: *"o detector entrega uma wm_class, e o
      produto só sabe guardá-la como `MatchCriteria(window_class=…)`, que é uma
      regra que este editor não sabe MOSTRAR — o perfil abriria travado, com a
      frase de usar a linha de comando. Gravar isso a partir de um botão seria
      empurrar o perfil dela para fora da tela."* Se gravar a regra empurra o
      perfil para fora da tela, **o conserto é a tela aprender a regra**, e foi
      o que a sprint fez: `simple_match` ganhou o preset `"janela"`, e os TRÊS
      seletores ganharam o rótulo antes de este botão gravar um byte.

      O que continua valendo daquele bloco é a outra metade, e ela é o motivo
      de o preset novo NÃO ser `process_name`: é outro dado (o basename de
      `/proc/PID/exe`), e casaria por acaso.

    * **nenhuma janela em foco** — RECUSA, e é a única recusa honesta que
      sobrou: `classe` vazia ou `"unknown"` é o caso em que o detector não viu
      nada. Ela continua nomeando o que viu.

    `last_class` ANTES de `current_class`: a primeira é a última classe ÚTIL
    vista (`launch_wrapper_dialog.py:81`) e sobrevive ao foco ir para a janela
    do Hefesto — que é exatamente o que acontece quando ela clica neste botão.

    E ELE PASSOU A DIZER O QUE ACHOU — 03/09/2026. A recusa já nomeava a classe
    que o detector estava vendo; o SUCESSO não dizia nada, e é o caso em que
    dizer vale mais: o botão grava um appid que ela não digitou, vindo de uma
    janela que ela não está mais olhando. O desfecho devolve o NOME do jogo
    (`_jogo_reconhecido`), que é a única forma de ela conferir que o detector
    pegou o jogo certo e não o launcher que estava por cima.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.profiles.simple_match import (
        from_simple_choice,
        simple_extra,
    )
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    nome = _perfil_do_editor(ctx)
    classe = str(ctx.state.get("window_detect_last_class")
                 or ctx.state.get("window_detect_current_class") or "")
    if not classe or classe == "unknown":
        # A ÚNICA RECUSA QUE SOBRA, e ela é a honesta: o detector não viu nada.
        # Nada a gravar, e nenhum lugar para mandá-la — o que ela faz é abrir o
        # jogo e clicar de novo, que é o que a frase diz.
        raise RuntimeError(
            "não achei janela de jogo em foco — o detector não está vendo "
            "nenhuma. Abra o jogo, deixe-o em foco por um instante e clique "
            "de novo.")
    prof = load_profile(nome)
    appid = steam_appid_from_wm_class(classe)
    if appid is not None:
        prof.match = from_simple_choice("steam_game", str(appid),
                                        regra_do_disco=prof.match)
        # O CAMPO SE CORRIGE AQUI TAMBÉM, e este é o caso mais forte dos dois: o
        # número que passa a valer ela NÃO digitou — veio de uma janela que ela
        # nem está mais olhando. Sem isto, o "Nome do Jogo" continua mostrando o
        # que havia antes do clique, sobre uma regra que já é outra. Ver
        # `editor_jogo`.
        _gravar(prof, ctx, p)
        return _dizer(_agora_vale_em(prof, str(appid)),
                      **{"editor.jogo": simple_extra(prof.match) or str(appid)})
    # JOGO DE FORA DA STEAM — a metade que o `title` do botão promete há
    # semanas e que o produto recusava (ONDA5-10-01, 06/09/2026).
    prof.match = from_simple_choice("janela", classe)
    _gravar(prof, ctx, p)
    # O DESFECHO VAI SEM `texto`, e é escolha: `_agora_vale_em` usa o texto só
    # para traduzir um NÚMERO DA STEAM em nome de jogo (`_jogo_reconhecido`).
    # Uma `wm_class` não é isso — passá-la faria a tela ou calar (o comum) ou
    # dizer "não reconheci este endereço" sobre uma regra que gravou certo.
    return _dizer(_agora_vale_em(prof),
                  **{"editor.jogo": simple_extra(prof.match) or classe})


@gesto("10-perfis.html", "novo")
def novo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Novo": um perfil em branco no disco, já com a regra do jogo em foco.

    NASCE NO DISCO, e não num rascunho, porque esta aba não tem "Salvar"
    próprio — a janela estável só PREENCHE O EDITOR (`on_profile_new:3016`) e
    quem grava é o botão seguinte. Aqui, com a ação imediata que ela pediu, o
    arquivo nasce e a lista o mostra no tique seguinte, já aberto no editor.

    A REGRA DO JOGO EM FOCO É A MESMA DO PRODUTO, e a guarda também: o
    `_aplicar_nascimento_com_jogo` (`profiles_actions.py:3124`) só age quando há
    **appid da Steam**, e devolve `False` calado no resto. É o que este gesto
    faz — com jogo da Steam em foco nasce mirando aquele jogo, sem ele nasce
    catch-all, "que é o certo para um perfil de desktop" (palavras de lá).

    **A PRIORIDADE DEIXOU DE NASCER EM ZERO** — 03/09/2026,
    PERFIL-NASCE-CERTO-01. Aqui estava escrito que a conta *"mora num mixin GTK
    que depende de widget"*. **Não depende.** O corpo de
    `_prioridade_acima_dos_catch_all` (`profiles_actions.py:4208`) lê UM
    atributo — `self._profiles_cache`, a lista de perfis — e mais nada: sem
    `Gtk`, sem `self._get`, sem widget. O que faltava era alguém lhe entregar a
    lista, e esta aba já a tem na mão.

    O DEFEITO QUE ISSO FECHA foi medido em 26/07 com ela jogando: o perfil que
    ela criou para o Pragmata nasceu prioridade 0 e NUNCA valia no jogo, porque
    o catch-all dela (prioridade 100) vencia em todo o resto. **Ela não errou a
    configuração — a janela não tinha saída**, e um perfil novo desta tela caía
    no mesmo buraco. Medido no disco dela hoje: os catch-all são `meu_perfil`
    (1) e `fallback` (0), então a folga sai **11** — e os perfis de jogo dela
    estão em 80, o que continua sendo o certo: a conta promete vencer os
    "vale sempre", não vencer todo mundo.

    A CHAMADA É À FUNÇÃO DA JANELA, e não a uma segunda conta: o mixin é uma
    classe, e um método que só lê `getattr(self, "_profiles_cache", None)` roda
    com qualquer objeto que tenha esse atributo. Copiar `max(catch-all) + 10`
    para cá seria a segunda verdade sobre quem vence a disputa — e o teto
    (`PRIORIDADE_MAXIMA`), a folga (`_FOLGA_ACIMA_DO_CATCH_ALL`) e a regra do
    que É catch-all (`Profile.e_catch_all`) ficariam com dois donos.

    Ele NÃO é ativado: nascer não é passar a valer.
    """
    global _ESCOLHIDO
    from types import SimpleNamespace

    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        ProfilesActionsMixin,
    )
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    classe = str(ctx.state.get("window_detect_last_class")
                 or ctx.state.get("window_detect_current_class") or "")
    appid = steam_appid_from_wm_class(classe) if classe else None
    regra = (from_simple_choice("steam_game", str(appid)) if appid is not None
             else MatchAny())
    todos = list(load_all_profiles())
    nome = _nome_livre("Novo perfil", todos)
    # `Any` E NÃO UM `cast` PARA O MIXIN: o objeto NÃO é um mixin, e dizer que é
    # seria mentir para quem ler. O que ele é está no nome — só o cache, que é o
    # único atributo que o método lê (`getattr(self, "_profiles_cache", None)`).
    so_o_cache: Any = SimpleNamespace(_profiles_cache=todos)
    prioridade = ProfilesActionsMixin._prioridade_acima_dos_catch_all(so_o_cache)
    _gravar(Profile(name=nome, match=regra, priority=prioridade), ctx, p)
    _ESCOLHIDO = nome
    return _dizer(f"Perfil criado: {nome} · prioridade {prioridade}, acima dos "
                  f"que valem sempre")


@gesto("10-perfis.html", "duplicar")
def duplicar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Duplicar": o perfil inteiro numa cópia, e o editor abre nela.

    A DICA DELA DIZ *"Copia o perfil inteiro para o editor, com «(cópia)» no
    nome"*, e as três partes se cumprem — a última por consequência da segunda:
    a cópia nasce no disco e o `_ESCOLHIDO` passa a ser ela, então é ela que o
    editor pinta no tique seguinte.

    "O PERFIL INTEIRO" É LITERAL, e é a diferença para o defeito
    BUG-DUPLICATE-NO-CONFIG-COPY-01, que a janela estável já pagou: a cópia
    tinha só o nome trocado e o resto virava default. O `model_copy` do pydantic
    leva gatilhos, luz, vibração, alto-falante, máscara e os overrides por
    controle — tudo, menos o nome.

    E A CÓPIA NÃO É ATIVADA. Duplicar não é trocar o perfil que está valendo; a
    coluna tem um "Ativar" para isso. Por isso `_gravar` não reaplica aqui: o
    nome novo nunca é o ativo.

    O NÚMERO NO FIM ("(cópia) 2") NÃO É ENFEITE: sem ele, duplicar duas vezes o
    mesmo perfil gravaria a segunda cópia POR CIMA da primeira — `save_profile`
    escreve por slug.

    **"O PERFIL INTEIRO" TEM UMA EXCEÇÃO, E ELA É O CARIMBO DE PONTE** —
    03/09/2026, e era um defeito de comportamento. O `model_copy` levava o
    `ponte` junto, e a janela estável o CORTA de propósito: em
    `_build_profile_from_editor` o duplicar entra como estreia
    (`estreia = _new_profile or _duplicate_source is not None`,
    `profiles_actions.py:4438`), o degrau 2 de `carimbo_que_o_save_leva` é
    cortado, e o degrau 1 — o disco, pelo nome NOVO — devolve `None`.

    POR QUE ISSO IMPORTA, e o cenário é o gesto seguinte ao duplicar: repontar a
    cópia para OUTRO jogo. Com o carimbo herdado, `pontes_confirmadas()` publica
    uma ponte que ninguém provou naquele appid, a escada de
    `integrations/ponte_escada.py` para num jogo nunca testado, e o produto jura
    saber o que não sabe. **O carimbo é REGISTRO de uma confirmação, não
    configuração que se copia.**

    A REGRA NÃO É REESCRITA AQUI: quem decide é `carimbo_que_o_save_leva`, o
    mesmo dono que a aba Perfis e o rodapé já consultam
    (`profile_writer.py:57`). Os argumentos são os do caso: `existente` é quem
    ocupa o nome novo em disco (ninguém — `_nome_livre` acabou de garantir), e
    não há rascunho. Se a escada mudar, esta linha muda com ela.
    """
    global _ESCOLHIDO
    from hefesto_dualsense4unix.app.actions.profile_writer import (
        carimbo_que_o_save_leva,
    )
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles, load_profile
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    era = _perfil_do_editor(ctx)
    todos = list(load_all_profiles())
    prof = load_profile(era)
    copia = _nome_livre(f"{prof.name} (cópia)", todos)
    carimbo = carimbo_que_o_save_leva(find_by_slug(copia, todos), None)
    _gravar(prof.model_copy(update={"name": copia, "ponte": carimbo}), ctx, p)
    _ESCOLHIDO = copia
    return _dizer(f"Cópia criada: {copia}")


@gesto("10-perfis.html", "remover")
def remover(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Remover": apagar o perfil do disco. PERGUNTA ANTES, no rótulo do botão.

    É O GESTO MAIS DESTRUTIVO DESTA ABA, e tem TRÊS guardas, nesta ordem:

    1. **precisa de um perfil escolhido.** Sem ele, `_perfil_do_editor` recusa
       — nunca "o primeiro da lista".
    2. **não age sobre o perfil que está VALENDO.** Apagar o ativo deixaria o
       daemon aplicando um arquivo que não existe mais, e o produto já tem uma
       frase para esse risco (`frase_da_remocao_do_perfil_ativo`). Aqui a
       resposta é mais curta: recusa e diz para ativar outro antes.
    3. **pergunta.** O primeiro clique ARMA e levanta; o rótulo do botão vira
       a pergunta no tique seguinte (≤100 ms) e o segundo clique, dentro de
       oito segundos, apaga. Ver `_rotulo_do_remover` para por que a pergunta
       mora no rótulo e não num diálogo.

    O ARMAMENTO É POR PERFIL: escolher outra linha e clicar em Remover não
    aproveita a confirmação da anterior — seria a pior forma de perder o perfil
    errado.

    E O APAGADO TEM VOLTA: `delete_profile` arquiva a última versão em
    `profiles/.historico/<slug>/` antes do `unlink` (PERFIL-SEM-RASTRO-01,
    `loader.py:1601`). O caminho de volta hoje é a linha de comando —
    `hefesto-dualsense4unix profile restore <nome>` —, porque o "Voltar à de
    ontem" desta aba precisa do perfil na LISTA para escolhê-lo.
    """
    global _ARMADO, _ESCOLHIDO
    from hefesto_dualsense4unix.profiles.loader import delete_profile

    nome = _perfil_do_editor(ctx)
    # A FRASE É DO PRODUTO, e não desta tela — 02/09/2026, LEI 0.
    # `frase_da_remocao_do_perfil_ativo` (`profiles_actions:633`) nasceu no §P7
    # e é o aviso do diálogo de Remover da janela estável: três parágrafos que
    # dizem o quê, por quê e o que fazer, na ordem que esta casa exige de toda
    # frase de diagnóstico. Aqui havia uma SEGUNDA verdade, escrita à mão, que
    # dizia menos — não contava que o controle segue com a cor, os gatilhos e a
    # vibração aplicados depois de o arquivo sumir.
    #
    # E ELA DECIDE MELHOR QUE UM `mesmo_slug` LOCAL: recebe o `PerfilQueVale`
    # inteiro e **cala quando a fonte é `nao_sei`** — "não sei qual está
    # valendo" e "não há nenhum valendo" são fatos diferentes, e transformar o
    # primeiro em recusa seria travar o Remover por ignorância nossa.
    #
    # O `nao_sei` É INALCANÇÁVEL DAQUI, e escrever isso é o honesto — 02/09/2026.
    # `perfil_que_esta_valendo` só o devolve quando o `state` NÃO é dicionário
    # (`houve_resposta = isinstance(state, dict)`), e `Contexto.state` é tipado
    # `dict[str, Any]` e nasce dicionário nos dois lugares onde o piloto o monta.
    # O ramo que esta aba alcança é o `nenhum`. A escolha pela função continua
    # certa — ela é o dono da frase e cobre o caso na janela GTK, que a chama sem
    # `state` —, mas ninguém deve ler isto como uma cobertura que esta aba tem.
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        frase_da_remocao_do_perfil_ativo,
        perfil_que_esta_valendo,
    )

    aviso = frase_da_remocao_do_perfil_ativo(nome, perfil_que_esta_valendo(ctx.state))
    if aviso:
        raise RuntimeError(aviso)
    agora = time.monotonic()
    armado = (_ARMADO and _ARMADO[0] == nome
              and (agora - _ARMADO[1]) < SEGUNDOS_PARA_CONFIRMAR)
    if not armado:
        _ARMADO = (nome, agora)
        raise RuntimeError(
            f"Apagar “{nome}” do disco? Clique em Remover de novo para "
            f"confirmar — o botão espera oito segundos.")
    _ARMADO = None
    delete_profile(nome)
    _ESCOLHIDO = ""
    # SEM `profile.switch` AQUI, de propósito: o perfil apagado não é o ativo
    # (a guarda 2 garante), então não há o que reaplicar. O `launch_env`
    # precisa saber assim mesmo — o `steam_app_<id>.env` do perfil que morreu
    # fica rançoso se ninguém avisar (DEDUP-04, `profiles_actions.py:3199`).
    p.chamar("launch_env.refresh")
    # A FRASE É A DA JANELA ESTÁVEL, palavra por palavra: `_toast_profile(
    # f"Perfil removido: {name}")` (`profiles_actions.py:3233`).
    #
    # `_dizer` E NÃO `_anotar` — 03/09/2026. Os dois guardam a frase; só o
    # primeiro a DEVOLVE para o `_deu_certo` pintar no ato. Com o `_anotar` a
    # tira só acendia no tique seguinte (até 100 ms), e o argumento é o do
    # piloto, palavra por palavra: *"Meio segundo entre o clique e a resposta
    # basta para ela clicar de novo achando que o primeiro não pegou"* — e no
    # gesto mais destrutivo da aba, o segundo clique acerta a linha seguinte.
    return _dizer(f"Perfil removido: {nome}")


@gesto("10-perfis.html", "recarregar")
def recarregar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Recarregar": reler a lista do disco AGORA, e dizer que releu.

    **ELE ERA UM BOTÃO MORTO COM APARÊNCIA DE VIVO** — 03/09/2026. O
    `data-hef-gesto="recarregar"` está na página desde 31/08 e não havia
    `@gesto`: o piloto caía no ramo do gesto SEM DONO, anotava `("sem dono", "")` e
    imprimia `[gesto sem dono] 10-perfis.html · recarregar` **no stdout de quem
    lançou a janela**. Ela clicava, nada acontecia, e nada dizia por quê — nem a
    tarja, porque `_recusou_dizendo` só pinta para exceção de HANDLER, e um
    gesto sem handler não chega lá.

    **O MOTIVO DE ELE TER FICADO SEM DONO CAIU, E CAIU PELA METADE QUE FALTAVA.**
    Estava escrito aqui que *"não há o que chamar: a lista já é relida do disco
    a cada 500 ms, então ligá-lo a um `load_all` extra seria fingir trabalho já
    feito"*. A premissa está certa e a conclusão não segue — a janela estável
    tem o MESMO botão, sobre uma lista que ela também mantém em cache
    (`on_profile_reload` → `_reload_profiles_store` + toast "Lista recarregada",
    `profiles_actions.py:3355`). O trabalho que ele faz não é a leitura: é
    **dizer que leu**. Um botão cuja promessa é tranquilizar não fica mudo
    porque o produto já estava certo.

    O QUE ELE FAZ, e é o `_reload_profiles_store` desta tela: chama `pacote()`,
    que relê o disco, e devolve a carga INTEIRA — o `blocos` da lista, a
    contagem, o editor. A pintura acontece no ato (`_deu_certo` →
    `window.__hef.pintar`), não no tique seguinte, que é a diferença entre um
    botão que responde e um botão que parece não ter pego.

    NÃO FALA COM O DAEMON, e por isso não está em `PROVAS`: o disco é a fonte da
    lista, e o `state` que decide quem está ativo já chegou pelo tique. É o
    segundo gesto desta aba sem chamada de ponte — o outro é o `selecionar`.

    A FRASE É A DA JANELA ESTÁVEL, palavra por palavra: `"Lista recarregada"`
    (`profiles_actions.py:3357`). O número de perfis vai junto porque é o que
    faz o clique VALER: ela relê para conferir que o perfil novo apareceu.
    """
    carga = pacote(ctx)
    quantos = len(carga.get("perfis.linha.nome") or [])
    frase = f"Lista recarregada · {quantos} perfis"
    # A ORDEM IMPORTA: `pacote()` LÊ o desfecho para pintá-lo, então a carga que
    # ele acabou de montar carrega o desfecho ANTERIOR. Anotar antes de chamar
    # não resolve (o valor entraria certo, mas a contagem sai da carga); a
    # correção é sobrescrever a chave depois — um dono, um valor, e o tique
    # seguinte encontra o mesmo.
    _anotar(frase)
    carga["perfis.desfecho"] = frase
    # A CARGA VAI NO EMBRULHO DA PINTURA — ver `_dizer`. O `blocos` é chave de
    # contrato e fica na RAIZ (o `pintar` o lê de `p.blocos`); o resto é `mesa`.
    return {"blocos": carga.get("blocos") or {},
            "mesa": {k: v for k, v in carga.items()
                     if k != "blocos" and not isinstance(v, dict)}}


def _editor_de(prof: Any) -> dict[str, Any]:
    """Os campos do editor daquele perfil, pela porta da FRENTE do produto.

    `pacote_da_aba` é a função pública de `perfis_web`, e é a mesma que
    `pacote()` chama a cada tique. Ler `_pacote_do_editor` (privada) daria o
    mesmo dicionário com uma linha a menos e um acoplamento a mais; o que se
    quer daqui é justamente o que a TELA está mostrando, e a tela chama esta.

    O `ambiente_travado` que ela devolve é a válvula do R-12 — a razão de os
    dois gestos do editor consultarem isto antes de gravar.
    """
    editor: dict[str, Any] = _tela.pacote_da_aba(
        [prof], ativo=None, editado=prof)["editor"]
    return editor


#: NÃO SOBRA GESTO SEM DONO NESTA ABA — 03/09/2026, e os dois últimos caíram no
#: mesmo dia.
#:
#: **`recarregar` GANHOU DONO.** Aqui estava escrito que *"não há o
#: que chamar: a lista já é relida do disco a cada tique de 100 ms, então ligar
#: este botão a um `load_all` extra seria fingir trabalho que já está feito; o
#: que falta não é motor, é o botão sair do desenho"*. A premissa continua
#: certa e **a conclusão não seguia**: a janela estável tem o MESMO botão sobre
#: um cache que ela também mantém (`on_profile_reload`, `:3319`), e o trabalho
#: dele nunca foi a leitura — é DIZER que leu. Enquanto isso não foi visto, o
#: botão ficou vivo na tela e morto no código, imprimindo `[gesto sem dono]`
#: num terminal que ela não olha. Ver o gesto `recarregar`.
#:
#: **`editor.estilo` GANHOU MOTOR, e não só dono** — 03/09/2026, no fim do dia.
#: De manhã ele era um gesto sem dono; à tarde passou a RECUSAR dizendo; à noite
#: ele APLICA. Aqui estava escrito que *"motor ele continua não tendo … quem
#: lhes dá motor é a ONDA-PERFIS-04"*, e a premissa estava certa e a conclusão
#: não seguia: o estilo nunca precisou de campo no `Profile` — ele resolve
#: gatilho, vibração e luz e sai de cena. As quinze receitas são de
#: `profiles/estilos_de_jogo.py`, por decisão dela.
#:
#: **`editor.prioridade` NASCEU COM DONO no mesmo dia**, e era o único campo do
#: editor sem nenhum caminho de escrita: o desenho tinha uma barra, e barra não
#: se arrasta. Ver `editor_prioridade`.
#:
#: FATO SUBSTITUÍDO — 03/09/2026. Aqui estava escrito que *"a página publicada
#: continua abrindo em «Luta»"*, com a cura do `<option value="" selected>—`
#: esperando na bancada. **Ela foi publicada.** Medido no produto instalado,
#: lendo o DOM: `src/…/paginas/10-perfis.html:1217` traz
#: `<option value="" selected>—</option>` e o campo abre com `value === ""`.
#: O que continua VERDADEIRO é a outra metade, e é a razão de `editor.estilo`
#: seguir em `NAO_PINTAVEIS`: escrever nele é que não dá — ver a nota do
#: `editor_estilo` sobre o `'—'` do `escrever()`.
#: `resultado` ENTROU EM 03/09/2026, e o `profile_switch` FICA: o `ativar`
#: passou a ler o CORPO da resposta em vez do booleano (ELO-MUDO-01), mas o
#: `voltar-a-de-ontem` e o `gravar_e_reaplicar` continuam usando o invólucro —
#: para eles o booleano basta, porque a pergunta é "o daemon aceitou?" e não
#: "o que entrou?".
PONTE = {"profile_switch", "chamar", "resultado"}
#: `profile.switch` ENTROU com o `resultado`: quem chama por nome de método
#: declara o método. O `test_nenhum_pacote_cita_metodo_que_o_daemon_nao_atende`
#: confere os dois contra o `ipc_server.py`.
METODOS = {"launch_env.refresh", "profile.switch"}


PAGINA = "10-perfis.html"
#: 12 → 13 EM 03/09/2026: nasceu o `editor.prioridade`, o slider que ela pediu.
#: O piso SÓ SOBE — um gesto que sumisse não apareceria na tela, e é essa queda
#: silenciosa que este número existe para pegar.
PISO_DA_ABA = 13
#: SÓ UMA PROVA DECLARADA PARA ONZE GESTOS, e a razão é estrutural, não
#: preguiça: nove dos outros dez agem sobre o perfil ESCOLHIDO, e o `ctx` desta
#: régua é fixo — `active_profile="regua"`, sem `_ESCOLHIDO` (um gesto que
#: dependesse do estado deixado por outro teste seria pior que não ter prova).
#: FATO SUBSTITUÍDO — 02/09/2026. Aqui estava escrito que, "no mesmo lar de
#: mentira que o `conftest.py` monta", `load_all_profiles()` devolve **9
#: perfis** e que a pasta vista por `pacote()` "tem nove". **Sob o `pytest` ela
#: tem ZERO**: a `conftest.py:2114` põe
#: `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` em todo teste, e é esse env que
#: desliga a semeadura. A conclusão não muda — nenhum perfil se chama "regua",
#: e os nove gestos levantam antes de tocar a ponte; o que muda é que eles
#: levantam por a pasta estar VAZIA, não por o nome não estar entre nove.
#:
#: ELES FORAM PROVADOS, e não por leitura: com uma pasta de perfis DE VERDADE
#: num diretório temporário, três perfis dela copiados, e um dublê de ponte
#: igual ao desta régua — os números estão no relato desta leva, gesto a gesto,
#: com a mordida de cada um.
#: E O DÉCIMO PRIMEIRO — `recarregar` — NÃO CHAMA A PONTE de propósito: a fonte
#: da lista é o DISCO. Uma prova declarada aqui reprovaria por não chamar nada,
#: que é o contrato certo desta régua e a razão errada para este botão. Quem o
#: morde é `test_o_recarregar_da_aba_perfis_tem_dono.py`, que exige a carga.
PROVAS: list[dict[str, Any]] = [
    # `resultado` E NÃO `profile_switch` — 03/09/2026, o ELO-MUDO-01. O
    # `ativar` passou a ler o CORPO da resposta (`secoes`), que é a diferença
    # entre "ativado" e "ativado, menos o que o lock manual descartou". Os
    # argumentos são os do `_safe_call`: o método por posição, o `name` por
    # nome — é assim que a ponte recebe o nome do método e os parâmetros.
    {"pagina": PAGINA, "gesto": "ativar", "clique": {"texto": "Ação"},  # (noqa-acento) id
     "chama": [("resultado", ["profile.switch"], {"name": "Ação"})]},
]

#: O QUE NÃO ECOA NO `state_full`, e são DOZE dos treze. A razão é uma só e está
#: no alto deste arquivo: **o daemon não guarda perfil, o disco guarda**. Ele
#: publica `active_profile` (um nome) e mais nada sobre o conteúdo — renomear,
#: duplicar, apagar, trocar a regra do jogo, restaurar a versão de ontem: nada
#: disso aparece nas 49 chaves que ele devolve. O efeito se vê na LISTA desta
#: aba, que `pacote()` relê do disco a cada tique.
#:
#: `selecionar` é o único que não fala com ninguém, e é de propósito: escolher
#: uma linha muda o ALVO dos botões ao lado, na memória desta janela. Se
#: trocasse o perfil que está valendo, a coluna não precisaria de um "Ativar".
#:
#: E ISSO MUDA A PROVA de quase todos: eles agem sobre o perfil ESCOLHIDO, e
#: uma régua que os clicasse em ordem alfabética — sem `selecionar` antes —
#: veria nove recusas em vez de nove gestos.
#: OS DOIS QUE ENTRARAM EM 03/09/2026, e o `editor.estilo` mudou de razão: ele
#: estava fora porque SEMPRE levantava (recusa é `!` na prova no aparelho, não
#: `—`). Agora ele grava, e grava no DISCO — que é a mesma razão dos outros
#: onze. Deixá-lo de fora depois do motor faria a régua acusar de mudo um gesto
#: que fez três coisas no aparelho dela.
SEM_ECO = ("selecionar", "editor.nome", "editor.ambiente", "editor.jogo",
           "editor.prioridade", "editor.estilo",
           "detectar", "novo", "duplicar", "remover", "voltar-a-de-ontem",
           "recarregar")
