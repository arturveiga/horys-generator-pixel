# Aprendizados: boss macaco-golem (2026-11-08)

Pedido `~/.horys-pixel/pedidos/20261108-193955-0b8b`. Boss de ~198 px, 13 cores, contorno suave de 1 px.
Notas do revisor: v05 28% → v08 36% → v12 52% → v13 71% → v14 79% → v15 81% → **v17 84% (PASSA)**.
Animação em rig: anim03 49% → anim06 55% (NAO_PASSA).

## O que fazer

- **Conceito em ilustração chapada, fundo liso verde, e conversão por paleta fechada.** A base só ficou fiel quando o
  Codex gerou a arte já pensada para converter e a redução usou uma subpaleta fechada de 16 cores do boss.
- **Escolher o tamanho pela densidade do design.** Com 151 px e contorno de 2 px a limpeza apagava crânio, presas e
  runas. Com 198 px e contorno suave de 1 px o design sobreviveu (v12, primeira com a forma certa).
- **Revisor desde a primeira versão, com inventário completo.** Corrigir a lista inteira de uma vez rende saltos
  grandes (71 → 79 → 81 → 84).
- **Acabamento que funcionou (sem redesenhar a forma):**
  - olho âmbar aceso dentro da órbita, com arcada por cima, como foco único;
  - metade de baixo mais escura (tom mais claro só nos punhos, pés e numa faixa de 3–4 px no topo das ombreiras);
  - juntar placas: trocar ~40% das linhas entre placas do mesmo plano pelo tom médio;
  - apagar acentos secundários (espirais dos joelhos e ombreira) para o olho e o peito mandarem;
  - zerar pixels órfãos;
  - regularizar a borda até o M10 ficar perto da régua (30 → 12) com busca gulosa local, que mexe 1 px por vez e
    só aceita se o M10 cair;
  - pivô no centro dos pés: a sombra é desenhada no pivô, então pivô errado = sombra deslocada.
- **Crânio de frente.** O crânio de 3/4 olhando para o lado foi rejeitado pelo usuário: para boss que encara o
  jogador, rosto simétrico de frente, com os dois olhos acesos.
- **Pernas em "A".** Canelas abertas em diagonal para fora, pés virados para fora, como na referência; pernas retas
  e paralelas deixam o boss duro.
- **Perguntar como cada estado se move** antes de animar ("hit" era ambíguo: foi soco de cima com os dois punhos).

## O que não fazer

- **Não aceitar a conversão por moda direto da referência original** (fundo em degradê virou retângulo; 27 cores;
  rosto e runas destruídos).
- **Não maquiar nota com retoque parcial** quando o revisor pede `redesenhar_forma`.
- **Não animar boss grande com rig de partes recortadas** (deslocar e girar pedaços da base). Problemas medidos:
  - frestas nas juntas e cortes retos onde as partes se separam;
  - rotação por vizinho mais próximo gera degraus irregulares (M10 sobe);
  - braços acima da cabeça viram blocos colados, sem ombro nem cotovelo;
  - pés quase não saem do chão: a 1× o corpo desliza;
  - cortar a pilha da morte na linha do chão cria borda reta (M17) e achatar por escala deixa as pernas de pé;
  - nuvens de elipse chapada leem como primitiva.
  O forro de pelo escuro sob as partes fechou as costuras, mas o teto do rig ficou em ~55%.
- **Não deixar a sombra crescer com a pilha** na morte: ela fica fixa ou no máximo com a largura da base real.

## Referências de movimento consultadas

- Slynyrd, Pixelblog 56 (ataque top-down): golpe pesado em 6 quadros, 250/50/50/50/300/100 ms; 1 quadro de
  antecipação, smear só no arco do golpe (nunca na antecipação nem na volta), 1 quadro de quique no impacto,
  follow-through segurado mais tempo, volta com leve atraso.
  https://www.slynyrd.com/blog/2025/5/23/pixelblog-56-top-down-character-attack-animation
- Packs de golem (itch.io): andar 8–12 quadros, ataque 8–20, morte 10–20; ex.: Stone Golem (Mattz) 12/20/10.
  https://xzany.itch.io/stone-golem
- Andar pesado: ~8 fps; a massa pesada lidera o quique e as partes leves (crânio, fumaça, pedras) seguem depois.

## Animação: o que aprendemos

- **Animação é desenho novo por quadro.** Cada pose-chave precisa ser redesenhada (corpo inteiro na pose). Recortar a
  base e mover, girar, escalar ou repintar as partes não vira animação: o usuário e o revisor perceberam na hora
  ("você só corta e pinta"). Rig serve no máximo para rascunho de timing.
- **Fluxo certo para boss grande:** o gerador de imagem (Codex) desenha as poses-chave no MESMO enquadramento
  (mesma tela, linha do chão fixa, mesma escala em todas as poses), e o pipeline converte, trava paleta, escala e
  pivô, e mede. Os quadros do meio vêm de mais poses geradas, nunca de recorte da base. O prompt das poses fica em
  `~/.horys-pixel/pedidos/20261108-193955-0b8b/poses/{andar,ataque,morte}.md`.
- **Gerar imagem direto sem a etapa de conversão não basta**: a IA de imagem varia escala, detalhes e paleta entre
  quadros e a animação treme. O Aseprite não é obrigatório para gerar; vale como entrega editável e exportação.
- **Poses-chave pedidas (a partir das referências):**
  - andar pesado ereto: contato E, passagem com pé D erguido, contato D, passagem com pé E erguido; ~8 fps; o corpo
    pesado lidera o quique e crânio, fumaça e pedras atrasam 1–2 quadros; pé erguido 6–8 px, passada 10–14 px;
  - soco de cima: antecipação agachada, os dois punhos unidos acima do crânio, descida com smear sólido em arco
    (2 tons claros, só no golpe), impacto com os punhos no chão, corpo agachado e mais largo, poeira em cachos de
    3 tons, 1 quadro de quique, impacto segurado, recuperação com os punhos subindo;
  - morte: recuo forte (crânio atrasa), petrificação em 2 passos (cor e runas apagam), estátua rachando, pernas
    tombando para fora, pilha de ~1,3× a largura e ~40% da altura sem vão embaixo, fumaça cinza em cachos subindo
    6–10 px por quadro e afinando; nada de elipse chapada nem fumaça lilás.
- **Reduzir o boss pronto não resolve.** Converter a v19 (ou o conceito) para 96 px apagou placas e runas: manchas
  de 11 px; limpando, viraram borrões. Mudar de tamanho exige gerar de novo no tamanho alvo.
- **Desenho à mão do agente sai geométrico.** O golem de 96 px desenhado do zero ficou com cara de robô (caixas,
  espiral virou retângulo, pernas com vão). Para personagem orgânico, a forma vem do gerador de imagem; o agente
  limpa, mede e corrige detalhes (crânio, olhos, órfãos, borda).
- **Gravar prompts com caminho absoluto.** Um `cat > arquivo` sem `cd` gravou os prompts na raiz do repositório e a
  geração falhou sem achar os arquivos.
- **Cota do Codex:** a geração parou por limite de uso (volta 2026-11-12, 12h15). Antes de um lote grande, rodar 1
  pose de teste para conferir cota e enquadramento.

## Próximo passo combinado

Esperar a cota do Codex (2026-11-12) e gerar as 15 poses-chave (andar 4, soco 5, morte 6) sobre a base v19 (crânio
de frente, pernas em "A", ~198 px), com os prompts já salvos; converter como a base; depois os quadros do meio,
portão e revisor até ≥ 80%.
