Repo: C:\Users\artur\workspace\repos\horys\horys-generator-pixel (horys-pixel: MCP que desenha ao vivo no Aseprite). Leia antes: skills/horys-pixel/SKILL.md (fluxo), new-task.md e docs/aprendizados-boss.md.

## Etapa única: a imagem PARADA perfeita do boss "golem-caveira", visão top-down

Só a base parada, de frente (virado para baixo/jogador), para um jogo top-down estilo Tiny Swords. Animação NÃO faz parte desta etapa.

Especificação:
- câmera 3/4 de cima (top-down de RPG): topo da cabeça e dos ombros visíveis, pés levemente achatados, sem perspectiva de baixo;
- ~96 px de altura com contorno, quadro 192×192, pé no pivô (96,127), contorno anil 2 px, sombra elíptica no chão;
- no máximo 16 cores do estilo horys-pixel-liso: rampas pedra lilás, masmorra, areia, fogo, magia + contorno #18122c;
- identidade: crânio bege com espiral na testa, olhos laranja acesos e presas; fumaça roxa nos ombros; placas de pedra com espinhos nos ombros e antebraços; medalhão de runa laranja no peito; runas laranja nos joelhos; 5 pedras flutuantes acima da cabeça, separadas dela por pelo menos 1 px de vão;
- leitura no tamanho real (1×): rosto, medalhão e punhos reconhecíveis; silhueta clara.

Pronto quando: o portão de medidas passa sem falha (horys_exportar / horys_portao), o revisor (horys_revisar) dá zero defeito estrutural e aceitação ≥ 80, e o Artur aprova no Aseprite.

## Arquivos

Pasta: C:\Users\artur\.horys-pixel\experimentos\golem-caveira\
- conceito.png: arte original do Artur (frente PURA, não top-down; fundo verde). conceito_margem.png: a mesma com margem; passou no portão de entrada.
- golem-caveira (sprite antigo): quadro 0 = conversão de conceito_margem.png a 96 px. Defeitos vistos: rosto do crânio virou mancha escura, pedras flutuantes grudadas na silhueta da cabeça, câmera de frente pura.

## Passos

1. Gere a arte top-down (decisão do Artur: NÃO converter a conceito.png de frente pura; ela serve só de referência de design). Gere o prompt com horys_prompt_traducao: tipo boss, modo parado, vista "3/4 de cima (top-down de RPG), de frente para o jogador, simétrico, pernas abertas em A", rampas ["pedra lilás","masmorra","areia","fogo","magia"], referencia = conceito_margem.png com referencia_propria true, pecas e foco do design acima, nao_fazer: textura/manchas/rachaduras nas placas (cada placa uma cor base + uma sombra), pedras encostando na cabeça. Mostre o prompt ao Artur; ELE gera a imagem e coloca em <pasta>\entrada\. Pare e espere a imagem.
2. horys_portao_entrada (altura 96). Se reprovar, passe ao Artur as correções para pedir no mesmo chat do gerador. Não force sem ele pedir.
3. horys_asset_novo (tipo boss, estados [{nome: parado, quadros: 1}]) e horys_converter (altura 96).
4. Limpeza: horys_limpar; depois à mão (horys_pixel_map com x/y, só as linhas erradas): crânio legível (use o 16×16 abaixo como ponto de partida e ajuste à câmera de cima), vão entre pedras e cabeça, tirar qualquer cor fora das 16, rever mãos e pés. horys_contorno. Julgue com horys_ver critica:true.
5. horys_exportar (estados ["parado"]) → ler o checagem.txt → corrigir só o que falhou → horys_revisar. Repetir até o critério de pronto. Mostrar ao Artur a folha 8× e o 1×.

Crânio de frente 16×16 (a=#18122c c=#f5d9b2 b=#e3c69c g=#d0ac8d o=#b49e7d y=#fdbe45 r=#ef7926):
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

## Avisos práticos

- Mudança no código só vale depois de reiniciar o daemon (`pythonw -m horys_pixel.daemon.servidor`; a ponte sobe outro sozinha). Depois o Artur reconecta o Aseprite em Horys › Conexão e painel.
- A ponte MCP mantém o schema antigo até reiniciar a sessão do Claude Code: se 'rampas' chegar como texto, o traducao.subpaleta já aceita.
- Há correções não commitadas no working tree (converter, prompt de poses, registro, portão no horys_sequencia). Commit só com autorização do Artur.
- Olhe o resultado inteiro antes de dizer que está pronto. Atualize new-task.md com evidência.
