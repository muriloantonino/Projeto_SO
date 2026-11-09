# Projeto_SO

# Simulador de Sistema de Arquivos (Etapa 1)

Projeto desenvolvido para a disciplina de Sistemas Operacionais. Este script em Python simula a estrutura e o gerenciamento de um sistema de arquivos utilizando a estratégia de **Alocação Indexada (i-node)**.

## Funcionalidades Implementadas

* **Hierarquia em Árvore:** Estrutura navegável de diretórios e arquivos.
* **Operações CRUD:** Criação, leitura e remoção de arquivos e diretórios (`mkdir`, `create`, `rm`).
* **Alocação Física:** Simulação de blocos de disco de 4KB. Cada arquivo possui um bloco de i-node (descritor) que aponta para os blocos de dados associados.
* **Diagnóstico e Fragmentação:** Cálculo exato da fragmentação interna (desperdício no último bloco alocado de um arquivo) e externa. Na alocação indexada, a fragmentação externa teórica não impede a gravação, eliminando a necessidade de compactação.

## Como Executar

O simulador foi construído em Python puro e não requer bibliotecas externas. Para rodar, execute o arquivo principal no terminal:

```bash
python fs_simulator.py

## Comandos Disponíveis no Terminal do Simulador

* `mkdir <caminho>`: Cria um novo diretório.
* `create <caminho> --size <tamanho>`: Cria um arquivo com o tamanho especificado (ex: 10KB, 512B).
* `rm <caminho>`: Remove um arquivo ou diretório recursivamente.
* `tree`: Exibe a árvore do sistema de arquivos.
* `fs_status --details`: Exibe o mapa de alocação do disco e o relatório completo de fragmentação.
* `exit`: Encerra o simulador.

## Demonstração (Casos de Teste do Enunciado)

Sequência de comandos executada:

```bash
> mkdir /sistema
> mkdir /sistema/logs
> create /sistema/logs/app.log --size 10KB
> tree

[ÁRVORE DO SISTEMA DE ARQUIVOS]
/
└── sistema/ [DIR]
    └── logs/ [DIR]
        └── app.log (10 KB) [ARQ]

> fs_status --details

Tamanho do Bloco de Disco: 4 KB | Total de Blocos: 16 (64 KB)

[MAPA DE ALOCAÇÃO DO DISCO (Indexado)]
Bloco 00 [INODE_RAIZ] : /
Bloco 01 [INODE_APP ] : /sistema/logs/app.log
Bloco 02 [DADO      ] : '/sistema/logs/app.log' (Bloco 1 - 4096 bytes ocupados)
Bloco 03 [DADO      ] : '/sistema/logs/app.log' (Bloco 2 - 4096 bytes ocupados)
Bloco 04 [DADO      ] : '/sistema/logs/app.log' (Bloco 3 - 2048 bytes ocupados)
Bloco 05..15         : [LIVRE]

--- RELATÓRIO DE FRAGMENTAÇÃO ---
Tamanho Real do Arquivo 'app.log': 10240 bytes (10 KB)
Espaço Alocado no Disco          : 12288 bytes (3 blocos de 4 KB)
Fragmentação Interna             : 2048 bytes (50% de desperdício no Bloco 04)
Fragmentação Externa             : 0 bytes
Necessidade de Compactação       : NÃO (Blocos alocados via i-node indexado)

## Etapa 2: Escalonamento de Disco e RAID 5

O simulador foi expandido para demonstrar as operações de disco integradas às requisições do sistema de arquivos.

### Demonstração de Escalonamento SSTF
Comando executado:
```bash
> write_file /sistema/logs/app.log "Novo Registro"


[E/S] Requisições de leitura/escrita pendentes nas trilhas: [98, 183, 37, 122, 14]
Posição atual da cabeça de leitura: Trilha 53

--- ESCALONAMENTO DE DISCO: SSTF (Shortest Seek Time First) ---
Ordem de Atendimento : 53 -> 37 -> 14 -> 98 -> 122 -> 183
Deslocamento da Cabeça: |53-37| + |37-14| + |14-98| + |98-122| + |122-183|
Total de Movimento    : 16 + 23 + 84 + 24 + 61 = 208 trilhas

> write_file /dados/planilha.csv --size 8KB

Arranjo Ativo: RAID 5 (3 Discos Físicos, Blocos de 4 KB)

[E/S - DISTRIBUIÇÃO EM DISCO]
Disco 1: [Bloco 01: Dados da Planilha.csv - Part 1 (4 KB)]
Disco 2: [Bloco 02: Dados da Planilha.csv - Part 2 (4 KB)]
Disco 3: [PARIDADE : XOR(Bloco 01, Bloco 02)]

[TESTE DE FALHA SIMULADO]
- Falha forçada no Disco 2!

- Recuperando Bloco 02 via operação XOR: (Disco 1 XOR Disco 3) -> Reconstrução [OK]
