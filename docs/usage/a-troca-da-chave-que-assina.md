# A troca da chave que assina

A lista `assets/assinaturas/quem-assina` diz quais chaves SSH assinam os commits do `dev` que o Hefesto aceita
avançar. O clone parte da lista do seu `HEAD` e anda commit a commit pelo primeiro pai da faixa baixada: cada commit
vem assinado por uma chave da lista do pai dele, e só depois de aceito a lista dele passa a valer. Não há salto: a
chave que um commit tirou da lista não assina nada depois dele, nem para o clone que ficou parado antes da retirada. A
lista de um commit nunca vale para ele mesmo, um commit recusado no meio deixa a faixa inteira de fora, e o alvo que
não descende do `HEAD` não avança.

## O roteiro

1. Gerar a chave nova com `ssh-keygen -t ed25519`, fora do repositório.
2. Pôr a linha da chave nova na lista num commit assinado por uma chave que já está na lista, e publicar no `dev`.
3. Assinar os commits seguintes com a chave nova.
4. Aposentar a velha num commit seguinte, assinado pela nova, que tira da lista a linha da velha.

Quem ficou parado antes do passo 2 atravessa os passos 2 a 4 sozinho, no primeiro avanço depois da troca.

## A chave de reserva

A lista deve ter uma chave de reserva, guardada fora da máquina de quem assina. Com a chave de uso perdida, a
reserva assina o commit que põe a nova (passo 2). Sem nenhuma chave da lista, nenhum clone avança sozinho: a saída é
reinstalar pelo caminho de instalação.

## A prova

`tests/unit/test_o_avanco_do_dev_so_com_commit_assinado.py`: a chave nova entra pelo commit que a lista aceitou; o clone
parado antes da troca chega à ponta; o commit de fora no meio da faixa, a lista que só existe na ponta, o commit da
chave já retirada e a lista adulterada por essa chave ficam recusados.
