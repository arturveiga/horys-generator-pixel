"""Instala ou atualiza a skill horys-pixel-liso no Claude Code e no Codex. Rode de novo sempre que mudar
scripts/revisor_prompt.md (o texto do revisor é gerado dele para os dois agentes).

- pasta real da skill: repo horys-generator-pixel/skills/horys-pixel-liso; ~/.agents/skills/horys-pixel-liso é junção para ela (o Codex lê ~/.agents/skills)
- junção para o Claude: ~/.claude/skills/horys-pixel-liso -> pasta real
- agente do Claude: ~/.claude/agents/horys-pixel-liso-revisor.md
- agente do Codex:  ~/.codex/agents/horys-pixel-liso-revisor.toml
"""
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(AQUI)
HOME = os.path.expanduser("~")
DESCRICAO = ("Revisor independente e exigente do estilo Horys Pixel Liso (v4). Julga boas práticas universais de pixel art "
             "e o que o Artur pediu e aprovou (ficha e pasta _aprovados; a régua é o Artur). Recebe a pasta gerada por grade.py "
             "(_regua com a prancha boas práticas e os aprovados do Artur, _8x, _silhueta, _quadros_4x, gif, _checagem.txt com o portão de "
             "medidas), a ficha e a praticas.md. Na rodada 1 (v01) faz o inventário completo de defeitos. Dá nota de 0 a 100 "
             "por critério e o percentual de aceitação, e devolve só um JSON com PASSA (sem grave e aceitação >= 80) ou "
             "NAO_PASSA e as correções. Use quando a skill horys-pixel-liso pedir a revisão de uma rodada, inclusive a do "
             "esboço de silhueta. Não edita arquivos e não fala com o usuário.")


def main():
    corpo = open(os.path.join(AQUI, "revisor_prompt.md"), encoding="utf-8").read().strip()
    # junção do Claude
    link = os.path.join(HOME, ".claude", "skills", "horys-pixel-liso")
    if not os.path.exists(link):
        r = subprocess.run(["cmd", "/c", "mklink", "/J", link, SKILL], capture_output=True, text=True)
        print("junção:", (r.stdout or r.stderr).strip())
    else:
        print("junção já existe:", link)
    # agente do Claude
    pasta = os.path.join(HOME, ".claude", "agents")
    os.makedirs(pasta, exist_ok=True)
    md = ("---\nname: horys-pixel-liso-revisor\n"
          f"description: {DESCRICAO}\n"
          "tools: Read, Glob, Grep\nmodel: opus\ncolor: red\nomitClaudeMd: true\nmaxTurns: 20\n---\n\n" + corpo + "\n")
    with open(os.path.join(pasta, "horys-pixel-liso-revisor.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print("agente do Claude:", os.path.join(pasta, "horys-pixel-liso-revisor.md"))
    # agente do Codex
    pasta = os.path.join(HOME, ".codex", "agents")
    os.makedirs(pasta, exist_ok=True)
    if "'''" in corpo:
        sys.exit("o prompt não pode conter três aspas simples seguidas (quebra o TOML)")
    toml = ('name = "horys-pixel-liso-revisor"\n'
            f'description = "{DESCRICAO}"\n'
            "developer_instructions = '''\n" + corpo + "\n'''\n")
    with open(os.path.join(pasta, "horys-pixel-liso-revisor.toml"), "w", encoding="utf-8") as f:
        f.write(toml)
    print("agente do Codex:", os.path.join(pasta, "horys-pixel-liso-revisor.toml"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
