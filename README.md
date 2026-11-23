# Projeto_SO
# Murilo Antonino dos Santos Silva

# Simulador de Sistemas Operacionais (Etapas 1 a 4)

Projeto desenvolvido para a disciplina de Sistemas Operacionais. Este script em Python simula de forma integrada um **Sistema de Arquivos (Alocação Indexada / i-node)**, **Escalonamento de Disco e RAID 5**, **Segurança (ACL, Criptografia e Antivírus)** e **Gerenciamento de Memória Híbrida (Área Reservada Contígua e Memória Virtual Paginada com LRU)**.

## Como Executar

O simulador foi construído em Python puro e não requer bibliotecas externas. Para rodar, execute o arquivo principal no terminal:

```bash
python fs_simulator.py
```

---

## Etapa 1: Sistema de Arquivos (Alocação Indexada / i-node)

### Funcionalidades Implementadas
- **Hierarquia em Árvore:** Estrutura navegável de diretórios e arquivos.
- **Operações CRUD:** Criação, leitura e remoção de arquivos e diretórios (`mkdir`, `create`, `rm`).
- **Alocação Física:** Simulação de blocos de disco de 4KB. Cada arquivo possui um bloco de i-node (descritor) que aponta para os blocos de dados associados.
- **Diagnóstico e Fragmentação:** Cálculo exato da fragmentação interna (desperdício no último bloco alocado de um arquivo) e externa. Na alocação indexada, a fragmentação externa teórica não impede a gravação, eliminando a necessidade de compactação.

### Comandos Disponíveis
- `mkdir <caminho>`: Cria um novo diretório.
- `create <caminho> --size <tamanho>`: Cria um arquivo com o tamanho especificado (ex: 10KB, 512B).
- `rm <caminho>`: Remove um arquivo ou diretório recursivamente.
- `tree`: Exibe a árvore do sistema de arquivos.
- `fs_status`: Exibe o mapa de alocação do disco e os blocos ocupados/livres.
- `exit`: Encerra o simulador.

### Demonstração (Casos de Teste)
```bash
> mkdir /sistema
> mkdir /sistema/logs
> create /sistema/logs/app.log --size 10KB
> tree
> fs_status
```

---

## Etapa 2: Escalonamento de Disco (SSTF/FCFS) e RAID 5 Dinâmico

As operações de E/S são totalmente integradas ao Sistema de Arquivos (sem dados fixos/hardcoded):
- **Escalonamento Dinâmico:** Cada bloco alocado corresponde a uma trilha física real. Operações de criação, leitura, escrita e *swapping* enviam as trilhas para o escalonador (**SSTF** ou **FCFS**), que movimenta a cabeça de leitura dinamicamente.
- **RAID 5 Real:** Os dados em bytes são fatiados entre 3 discos físicos com rotação de paridade e cálculo **XOR bit a bit real**. Em caso de falha de um disco, os dados são reconstruídos dinamicamente na leitura ou restaurados com `rebuild_disk`.

### Comandos Principais
- `set_scheduler <SSTF|FCFS>` — Alterna o algoritmo de escalonamento do braço de disco
- `fail_disk <1|2|3>` — Simula falha física e perda de dados em um dos discos do RAID 5
- `rebuild_disk <1|2|3>` — Reconstrói o disco falho utilizando paridade XOR dos discos saudáveis

### Exemplo de Teste (E/S Dinâmico + Falha e Reconstrução RAID 5)
```bash
> mkdir /dados
> write_file /dados/teste.txt "Sistemas Operacionais - Teste RAID 5"
> fail_disk 2
> read_file /dados/teste.txt
> rebuild_disk 2
```

---

## Etapa 3: Segurança, ACL, Criptografia e Integridade

O simulador implementa modos de execução (`MODO_KERNEL` e `MODO_USUARIO`), autenticação com **SHA-256 + salt**, permissões `rwx` (ACL), criptografia em repouso e varredura de integridade/antivírus.

**Usuários padrão:** `root` (senha: `root`) e `carlos` (senha: `1234`).

### Comandos Principais
- `login --user <usuario>` / `useradd <usuario> <grupo> <senha>` / `whoami`
- `chmod <octal> <caminho>` / `chown <usuario>:<grupo> <caminho>`
- `encrypt_file <caminho> --key "<chave>"` / `decrypt_file <caminho> --key "<chave>"`
- `antivirus_scan [caminho]` / `tamper_block <caminho>` / `security_logs`

---

## Etapa 4: Gerenciamento de Memória Híbrida

A RAM simulada é dividida em **Área Reservada** (4 MB, alocação contígua fixa para o Kernel e processos críticos, com detecção de fragmentação externa e compactação) e **Memória Virtual Paginada** (alocação por demanda, páginas de 4 KB, tradução de endereços, *Page Fault*, substituição **LRU** e *Swapping* integrado ao escalonador de disco).

### Comandos Principais
- `create_process --name "<Nome>" --size <X>KB --type <critical|normal>`
- `terminate_process --name "<Nome>"`
- `memory_status [--reserved | --virtual]`
- `memory_compact --reserved`
- `translate_address --process <Nome> --page <N>`
- `execute_step --process <Nome> --instruction "LOAD_DATA Página <N>"`

### Exemplo de Teste (Área Reservada e Compactação)
```bash
> create_process --name "Kernel_DiskDriver" --size 512KB --type critical
> create_process --name "Kernel_NetDriver" --size 1024KB --type critical
> create_process --name "Kernel_CryptoEngine" --size 512KB --type critical
> terminate_process --name "Kernel_NetDriver"
> memory_status --reserved
> memory_compact --reserved
```

### Exemplo de Teste (Memória Virtual, Page Fault e LRU)
```bash
> create_process --name "App_Navegador" --size 10KB --type normal
> create_process --name "App_Editor" --size 8KB --type normal
> execute_step --process App_Navegador --instruction "LOAD_DATA Página 0"
> execute_step --process App_Navegador --instruction "LOAD_DATA Página 1"
> execute_step --process App_Editor --instruction "LOAD_DATA Página 0"
> execute_step --process App_Editor --instruction "LOAD_DATA Página 1"
> translate_address --process App_Navegador --page 1
> execute_step --process App_Navegador --instruction "LOAD_DATA Página 2"
> memory_status --virtual
```
