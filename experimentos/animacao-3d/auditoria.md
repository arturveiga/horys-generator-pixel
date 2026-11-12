# Auditoria de ferramentas (2026-11-11)

Detecção local feita só por leitura (`where`, pastas de instalação, `--version`, import de libs).
Licenças por pesquisa web; o que não foi confirmado na fonte primária está marcado como "não verificado".

| Ferramenta | Versão instalada | Licença | Custo | Compatível? | Risco |
|---|---|---|---|---|---|
| Blender | 5.2.3 LTS (`C:\Program Files\Blender Foundation\Blender 5.2`; não está no PATH) | GPL-2.0+ | grátis | sim; abre headless com `--factory-startup` | baixo: GPL só alcança código que vira parte do Blender; nossos scripts ficam aqui, o Blender fica fora |
| BlenderMCP (ahujasid/blender-mcp) | não instalado (há outro MCP "blender" conectado nesta máquina, não auditado aqui) | MIT (PyPI e listagens; LICENSE no GitHub não verificado) | grátis | não verificado com Blender 5.2 | médio: traz integrações com serviços de geração 3D pagos/por crédito (ex.: Hyper3D Rodin, Hunyuan3D) e Poly Haven/Sketchfab online; todas devem ficar **desligadas** |
| Pixel Art Rendering (Lucas Roedel, Gumroad, $0) | não instalado | não verificado (página não exibe licença; um fork no GitHub é GPL-3.0, o que sugere GPL, por ser add-on de Blender) | $0 (gorjeta opcional) | página diz "atualizado para Blender 5.0"; 5.2 não verificado | médio: licença indefinida; usar só como referência externa, sem copiar código para o repo |
| CloudyTabzy/PixelatorPlus | não instalado (adiado) | **GPL-3.0** (API do GitHub, 2026-11-11) | grátis | não testado | médio: GPL, fica externo; adiado até o Blender nativo ser validado |
| Blockbench | não instalado | GPL-3.0 | grátis | não verificado | baixo: fica externo |
| RenasDemirbas/BlockBenchMCP | não instalado (adiado) | **GPL-3.0** (API do GitHub, 2026-11-11) | grátis | não testado | médio: GPL, fica externo; adiado (Experimento B) |
| Aseprite | instalado em `C:\Users\artur\Documents\aseprite\aseprite.exe` (versão não verificada; não está no PATH) | EULA proprietária (binário compilado pelo usuário: uso pessoal) | já possui | sim (já usado pelo Horys) | baixo |
| ffmpeg | 8.1 essentials (gyan.dev, via Chocolatey) | LGPL/GPL (build essentials) | grátis | sim | baixo: usado como executável externo |
| numpy | 2.4.6 | BSD-3 | grátis | sim | baixo |
| Pillow (PIL) | 12.3.0 | MIT-CMU (HPND) | grátis | sim | baixo |
| scipy | 1.17.1 | BSD-3 | grátis | sim | baixo |

## Veredito

- Caminho nativo A3 (`blender/render_pixel.py`) depende só do Blender 5.2.3 já instalado: custo zero, sem add-ons.
- Serviços pagos de geração 3D do BlenderMCP (Hyper3D/Rodin, Hunyuan3D e similares) ficam **desligados**; o
  projeto não pode depender de gerador pago de terceiros.
- Todo código GPL (Blender, add-ons, Blockbench, plugins) fica **externo**: nada é copiado para o repositório.
- Itens "não verificado" exigem conferir o LICENSE na fonte primária antes de qualquer uso.

## Fontes

- https://pypi.org/project/blender-mcp/
- https://lucasroedel.gumroad.com/l/pixel_art
- https://github.com/enfp-dev-studio/blockbench-mcp
- https://awesome.ecosyste.ms/projects/github.com%2Fjasonjgardner%2Fblockbench-mcp-plugin

## Correção (2026-11-11)

A primeira auditoria marcou PixelatorPlus e BlockBenchMCP como "repositório não encontrado". Errado: os dois
existem e são públicos. Conferido nesta máquina, sem proxy (`git config http.proxy` vazio, `HTTPS_PROXY` vazio):

| Repositório | HTTP (página) | API do GitHub | `git ls-remote` | Licença | Último push |
|---|---|---|---|---|---|
| CloudyTabzy/PixelatorPlus | 200 | 200 | ok (`3e07419`) | GPL-3.0 | 2026-09-28 |
| RenasDemirbas/BlockBenchMCP | 200 | 200 | ok (`6a54fb4`) | GPL-3.0 | 2026-11-02 |

A falha veio da busca web da sessão de auditoria, não de rede, autenticação ou Git. Os dois ficam **adiados** por
decisão do Artur: primeiro o Blender nativo precisa entregar um walk convincente.
