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
