# Experimento B: Blockbench + MCP

Alternativa ao Blender: modelo low-poly em cubos no Blockbench, animado e renderizado pela mesma câmera.

## Como vai funcionar

1. Blockbench (GPL-3.0) e o plugin MCP ficam **fora** do repositório, instalados pelo Artur. Nada é
   baixado nem instalado por scripts deste repo.
2. Plugin MCP: o pedido cita `RenasDemirbas/BlockBenchMCP`, mas o repositório não foi encontrado na
   auditoria (ver `../auditoria.md`). Antes de usar, confirmar o repo e a licença; alternativas achadas:
   `enfp-dev-studio/blockbench-mcp` (MIT) e `jasonjgardner/blockbench-mcp-plugin` (licença não confirmada).
3. O agente fala com o Blockbench pelo MCP: monta a câmera ortográfica com o mesmo `pitch` (32°), `yaw` (0)
   e `ortho_scale` do Blender, enquadrada uma vez pela ação inteira, fundo transparente, sem AA.
4. Exporta cada quadro para `../renders/<acao>/0000.png…` e escreve `../renders/<acao>/manifest.json`
   com o **mesmo contrato** do `README.md` da pasta acima, trocando só `"fonte": "blockbench"`.
5. Daí em diante o caminho é igual: loader `render3d` → motor de sequência → spritesheet Godot.

## Regras

- Mesmo canvas, pivô (origem da raiz no chão) e câmera do caminho Blender, para os dois serem comparáveis.
- Nenhum serviço pago e nenhum código GPL copiado para cá.
- O manifest é a única interface: se ele bate, o loader não precisa saber de onde veio o render.
