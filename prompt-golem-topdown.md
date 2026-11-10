Repo: C:\Users\artur\workspace\repos\horys\horys-generator-pixel (horys-pixel: MCP que desenha ao vivo no Aseprite). Leia antes: new-task.md (plano e estado), skills/horys-pixel/SKILL.md (fluxo) e docs/aprendizados-boss.md.

## Objetivo

Deixar o boss "golem-caveira" bem feito no Aseprite para um jogo TOP-DOWN (estilo Tiny Swords, vista de frente/3/4 de cima):
- andar de FRENTE (baixo) e andar de LADO (direita; a esquerda é o espelho), 4 a 6 quadros cada;
- ~96 px de altura com contorno, quadro 192×192, pé no pivô (96,127), no máximo 16 cores, estilo horys-pixel-liso;
- mesma identidade em todos os quadros (crânio com espiral e olhos laranja, medalhão de runa no peito, placas de pedra, pedras flutuantes acima da cabeça).
Pronto quando: o portão de medidas (horys_exportar) passa sem falha grave, o revisor (horys_revisar) dá zero defeito estrutural e aceitação ≥ 80, e o Artur aprova o GIF de cada direção.

## Arquivos

Pasta do experimento: C:\Users\artur\.horys-pixel\experimentos\golem-caveira\
- conceito.png: arte original do Artur (frente, parado, fundo verde); conceito_margem.png: a mesma com margem (passou no portão de entrada).
- entrada\Six-Frame Walking Golem Sprite Sheet.png: grade 2×3 do andar de frente (gerador externo). Portão de entrada REPROVADO só em chão (2,9%) e altura (4,5%); usada com forcar porque o Artur autorizou.
- v01\: exportação do sprite golem-caveira-v2 (andar de frente pelo motor de sequência) com o checagem.txt do portão.
- traducao\prompt.md: prompt de poses v2 usado no gerador.

## O que já foi tentado e por que falhou (não repetir)

Converter a grade do gerador quadro a quadro com o motor de sequência (horys_sequencia) dá:
1. rosto do crânio virando mancha na maioria dos quadros (450 px → 96 px deixa o rosto com 2–3 px; a moda apaga);
2. 31 cores e manchas verdes no tronco: o motor quantiza para a paleta INTEIRA do estilo (100+ cores), e o verde do fundo vira a rampa "grama";
3. pouco movimento de perna: o gerador não acerta a passada nem a escala entre células (3 grades seguidas).
Resultado do portão (v01): M03 31 cores, M05 cluster 23 px, A01/A02 "a forma só desliza" (29% de redesenho, meta 30–40%), M10 26 degraus, A13 3,6% de pixels piscando.

## Abordagem pedida

Um desenho só, animado por partes:
1. BASE DE FRENTE limpa: parta do quadro 0 de golem-caveira-v2 (ou converta conceito_margem.png com horys_converter). Corrija à mão: crânio legível (16×16 já desenhado, abaixo), sem verde, reduzido a ≤ 16 cores do estilo (pedra lilás, masmorra, areia, fogo, magia + contorno #18122c), pedras flutuantes separadas da cabeça por 1 px de vão. Revisor até não ter defeito estrutural. O Artur aprova a base antes de animar.
2. ANDAR DE FRENTE: copie a base para 4–6 quadros. Tronco, cabeça, crânio e placas ficam IDÊNTICOS (só sobem/descem 1–2 px). Redesenhe à mão só pernas (contato, descida, passagem com joelho alto) e balanço dos braços. Use as poses da grade como guia de posição, não como pixel. Nunca rotacione partes por vizinho mais próximo.
3. BASE DE PERFIL: precisa de uma referência de lado. Gere com horys_prompt_traducao (tipo boss, modo parado, vista "perfil olhando para a direita", rampas ["pedra lilás","masmorra","areia","fogo","magia"], base_aprovada = a base de frente aprovada) e peça ao Artur para gerar; portão de entrada; converter; limpar à mão como no passo 1.
4. ANDAR DE LADO: mesmo método do passo 2 sobre a base de perfil. A esquerda é o espelho.
5. Exporte só as tags de andar (horys_exportar com estados), olhe o GIF INTEIRO antes de mostrar, rode o revisor e entregue com as marcas de acabamento (horys_entrega).

Crânio de frente 16×16 (x/y = canto do crânio; a=#18122c c=#f5d9b2 b=#e3c69c g=#d0ac8d o=#b49e7d y=#fdbe45 r=#ef7926):
....aaaaaaaa....
..aaccccccbbaa..
.acccccccccbbba.
.accooooooobbba.
acccocccccobbbga
acccocoooobbbbga
abccocobbbbbbbga
abbbooobbbbbbgga
aaaaaabbbbaaaaaa
aayyraabbaaryyaa
aarraabbbbaarraa
abaaaabgabaaaaga
.abbbbaaaabbbga.
.aacbcbcbcbcbaa.
..ac.a.a.a.a.ca.
..aa........aa..

## Correções no código (faça junto, com teste e suíte verde)

1. Motor de sequência quantizando na paleta inteira: horys_sequencia (src/horys_pixel/ferramentas/sequencia.py → sequencia.processar → quantizacao.quantizar) deve aceitar 'rampas' (subpaleta, como traducao.subpaleta) e respeitar cores_max da ficha; a cor do fundo nunca pode virar cor da figura. Teste: grade sintética com fundo verde sai sem nenhum verde e com ≤ cores_max.
2. Trava de identidade que não acha a peça quando ela virou mancha: sequencia/identidade.py só cola se o casamento por cor der erro ≤ 60. Adicione um modo de decalque "fixo": peça desenhada colada numa posição relativa a uma âncora (topo da cabeça/centro de massa), sem casamento. Teste com peça apagada no quadro.
3. Portão de entrada de grade (entrada.py): a linha dos pés e a altura são corrigidas pelo registro do motor; considere aceitar desnível por LINHA da grade (registro alinha) e reportar como aviso, mantendo falha para célula cortada, fundo e chapado. Discuta com o Artur antes de afrouxar.
4. Daemon: mudanças no código só valem depois de reiniciar o processo `pythonw -m horys_pixel.daemon.servidor` (a ponte sobe outro sozinha), e aí o Artur precisa reconectar o Aseprite em Horys › Conexão e painel. Agrupe as mudanças para reiniciar uma vez só. A ponte MCP mantém o schema antigo das ferramentas até reiniciar a sessão do Claude Code.

## Já corrigido nesta sessão (não commitado; revise o diff e peça autorização para commitar)

- ferramentas/estilo.py: o decorador @ferramenta("horys_converter") estava em cima de entrada_reprovada; o converter dava TypeError.
- traducao.py: grade do prompt de poses calculada pelo número de poses (6 → 2×3); 'rampas' (subpaleta) aceita lista ou texto.
- sequencia/registro.py: registro centraliza pelo centro de massa (antes, pela faixa de baixo dos pés, e no andar a figura pulava ±35 px).
- ferramentas/sequencia.py: horys_sequencia recusa grade sem portão de entrada aprovado, salvo forcar + motivo.
- testes novos em tests/test_traducao.py, tests/test_sequencia.py e tests/test_entrada.py. Suíte: 227 passed, 1 skipped.

## Regras

- Commit e download de terceiros só com autorização do Artur.
- Não pule portões; se precisar forçar, pergunte e registre o motivo.
- Olhe o resultado inteiro (GIF/folha), não quadros soltos, antes de dizer que está pronto.
- Atualize new-task.md com evidência ao fim de cada etapa.
