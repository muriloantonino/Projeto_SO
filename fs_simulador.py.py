#!/usr/bin/env python3
"""
Simulador de Sistema de Arquivos (Etapa 1)
Disciplina: Sistemas Operacionais
Estratégia: Alocação Indexada (i-node)
"""

import math
import sys
import shlex


class Inode:
    def __init__(self, inode_id: int, is_directory: bool, name: str):
        self.id = inode_id
        self.is_directory = is_directory
        self.name = name
        self.size_bytes = 0
        self.data_blocks = []  # Lista de IDs de blocos físicos alocados
        self.children = {}     # name -> Inode (usado se for diretório)
        self.parent = None     # Referência ao Inode pai


class DiskBlock:
    def __init__(self, block_id: int):
        self.id = block_id
        self.is_allocated = False
        self.block_type = "LIVRE"  # 'INODE' ou 'DADO'
        self.owner_path = ""
        self.used_bytes = 0
        self.block_index = 0       # Qual bloco do arquivo é (1, 2, 3...)


class FileSystemSimulator:
    def __init__(self, total_blocks: int = 16, block_size_kb: int = 4):
        self.block_size = block_size_kb * 1024  # em bytes (ex: 4096)
        self.total_blocks = total_blocks
        self.disk = [DiskBlock(i) for i in range(total_blocks)]
        self.inode_counter = 0

        # Criação do diretório raiz '/'
        self.root = self._create_inode(is_directory=True, name="/")
        self.root.parent = self.root
        self.current_dir = self.root

        # Aloca o bloco físico 0 para o Inode Raiz
        self._allocate_block_for_inode(self.root, "/")

    def _create_inode(self, is_directory: bool, name: str) -> Inode:
        node = Inode(self.inode_counter, is_directory, name)
        self.inode_counter += 1
        return node

    def _find_free_block(self):
        for block in self.disk:
            if not block.is_allocated:
                return block
        return None

    def _allocate_block_for_inode(self, node: Inode, path_str: str) -> bool:
        blk = self._find_free_block()
        if not blk:
            return False
        blk.is_allocated = True
        blk.block_type = f"INODE_{node.name.upper() if node.name != '/' else 'RAIZ'}"
        blk.owner_path = path_str
        blk.used_bytes = self.block_size
        node.data_blocks.append(blk.id)
        return True

    def _resolve_path(self, path: str):
        """Resolve caminhos relativos e absolutos, retornando o nó alvo se existir."""
        if not path:
            return None
        parts = [p for p in path.split("/") if p]
        curr = self.root if path.startswith("/") else self.current_dir

        for part in parts:
            if part == ".":
                continue
            elif part == "..":
                curr = curr.parent
            elif part in curr.children:
                curr = curr.children[part]
            else:
                return None
        return curr

    def _parse_size(self, size_str: str) -> int:
        """Converte strings como '10KB', '512B', '2MB' em bytes."""
        size_str = size_str.strip().upper()
        if size_str.endswith("KB"):
            return int(float(size_str[:-2]) * 1024)
        elif size_str.endswith("MB"):
            return int(float(size_str[:-2]) * 1024 * 1024)
        elif size_str.endswith("B"):
            return int(size_str[:-1])
        return int(size_str)

    # ---------------- OPERAÇÕES CRUD ----------------

    def mkdir(self, path: str) -> bool:
        parent, name = self._get_parent_and_name(path)
        if not parent or not parent.is_directory:
            print(f"Erro: Caminho pai inexistente para '{path}'.")
            return False
        if name in parent.children:
            print(f"Erro: '{name}' já existe.")
            return False

        # Criação do Inode
        new_dir = self._create_inode(is_directory=True, name=name)
        new_dir.parent = parent
        parent.children[name] = new_dir
        return True

    def create(self, path: str, size_str: str) -> bool:
        size_bytes = self._parse_size(size_str)
        blocks_needed = math.ceil(size_bytes / self.block_size)
        
        # 1 bloco pro Inode + N blocos de dados
        total_needed = 1 + blocks_needed
        free_blocks = [b for b in self.disk if not b.is_allocated]

        if len(free_blocks) < total_needed:
            print(f"Erro: Espaço insuficiente em disco. Necessários {total_needed} blocos, disponíveis {len(free_blocks)}.")
            return False

        parent, name = self._get_parent_and_name(path)
        if not parent or not parent.is_directory:
            print(f"Erro: Caminho inexistente para '{path}'.")
            return False
        if name in parent.children:
            print(f"Erro: '{name}' já existe.")
            return False

        new_file = self._create_inode(is_directory=False, name=name)
        new_file.size_bytes = size_bytes
        new_file.parent = parent

        # 1. Aloca bloco do i-node
        inode_block = free_blocks[0]
        inode_block.is_allocated = True
        inode_block.block_type = f"INODE_{name.split('.')[0].upper()}"
        inode_block.owner_path = f"{parent.name.rstrip('/')}/{name}" if parent != self.root else f"/{name}"
        inode_block.used_bytes = self.block_size
        new_file.data_blocks.append(inode_block.id)

        # 2. Aloca blocos de dados
        remaining_bytes = size_bytes
        for i in range(blocks_needed):
            data_blk = free_blocks[1 + i]
            data_blk.is_allocated = True
            data_blk.block_type = "DADO"
            data_blk.owner_path = inode_block.owner_path
            data_blk.block_index = i + 1

            bytes_in_this_block = min(self.block_size, remaining_bytes)
            data_blk.used_bytes = bytes_in_this_block
            remaining_bytes -= bytes_in_this_block

            new_file.data_blocks.append(data_blk.id)

        parent.children[name] = new_file
        return True

    def rm(self, path: str) -> bool:
        target = self._resolve_path(path)
        if not target:
            print(f"Erro: '{path}' não encontrado.")
            return False
        if target == self.root:
            print("Erro: Não é permitido remover o diretório raiz.")
            return False

        self._recursive_delete(target)
        del target.parent.children[target.name]
        return True

    def _recursive_delete(self, node: Inode):
        if node.is_directory:
            for child in list(node.children.values()):
                self._recursive_delete(child)
        for blk_id in node.data_blocks:
            blk = self.disk[blk_id]
            blk.is_allocated = False
            blk.block_type = "LIVRE"
            blk.owner_path = ""
            blk.used_bytes = 0
            blk.block_index = 0
        node.data_blocks.clear()

    def _get_parent_and_name(self, path: str):
        path = path.rstrip("/")
        if not path:
            return None, None
        if "/" not in path:
            return self.current_dir, path
        parent_path, name = path.rsplit("/", 1)
        parent = self.root if parent_path == "" else self._resolve_path(parent_path)
        return parent, name

    # ---------------- VISUALIZAÇÃO E DIAGNÓSTICO ----------------

    def tree(self):
        print("\n[ÁRVORE DO SISTEMA DE ARQUIVOS]")
        print("/")
        self._print_tree_recursive(self.root, prefix="")

    def _print_tree_recursive(self, node: Inode, prefix: str):
        entries = list(node.children.values())
        for idx, child in enumerate(entries):
            is_last = (idx == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            sub_prefix = "    " if is_last else "│   "

            if child.is_directory:
                print(f"{prefix}{connector}{child.name}/ [DIR]")
                self._print_tree_recursive(child, prefix + sub_prefix)
            else:
                kb_size = child.size_bytes // 1024
                print(f"{prefix}{connector}{child.name} ({kb_size} KB) [ARQ]")

    def fs_status(self, details: bool = True):
        total_kb = (self.total_blocks * self.block_size) // 1024
        blk_kb = self.block_size // 1024
        print(f"Tamanho do Bloco de Disco: {blk_kb} KB | Total de Blocos: {self.total_blocks} ({total_kb} KB)\n")

        print("[MAPA DE ALOCAÇÃO DO DISCO (Indexado)]")
        i = 0
        while i < self.total_blocks:
            blk = self.disk[i]
            if not blk.is_allocated:
                # Agrupa blocos livres contíguos
                start = i
                while i + 1 < self.total_blocks and not self.disk[i + 1].is_allocated:
                    i += 1
                if start == i:
                    print(f"Bloco {start:02d}            : [LIVRE]")
                else:
                    print(f"Bloco {start:02d}..{i:02d}         : [LIVRE]")
            else:
                if blk.block_type.startswith("INODE"):
                    print(f"Bloco {blk.id:02d} [{blk.block_type:<10}] : {blk.owner_path}")
                else:
                    print(f"Bloco {blk.id:02d} [{blk.block_type:<10}] : '{blk.owner_path}' (Bloco {blk.block_index} - {blk.used_bytes} bytes ocupados)")
            i += 1

        if details:
            self._print_fragmentation_report()

    def _print_fragmentation_report(self):
        print("\n--- RELATÓRIO DE FRAGMENTAÇÃO ---")
        total_internal_frag = 0
        files_found = []

        def collect_files(node):
            if not node.is_directory:
                files_found.append(node)
            for child in node.children.values():
                collect_files(child)

        collect_files(self.root)

        for f in files_found:
            # Blocos de dados ocupados (excluindo o bloco do Inode)
            data_blocks_count = len(f.data_blocks) - 1
            allocated_bytes = data_blocks_count * self.block_size
            internal_frag = allocated_bytes - f.size_bytes
            total_internal_frag += max(0, internal_frag)

            percent_waste = (internal_frag / self.block_size) * 100 if self.block_size else 0
            last_blk_id = f.data_blocks[-1]

            print(f"Tamanho Real do Arquivo '{f.name}': {f.size_bytes} bytes ({f.size_bytes // 1024} KB)")
            print(f"Espaço Alocado no Disco          : {allocated_bytes} bytes ({data_blocks_count} blocos de {self.block_size // 1024} KB)")
            print(f"Fragmentação Interna             : {internal_frag} bytes ({percent_waste:.0f}% de desperdício no Bloco {last_blk_id:02d})")

        # Análise de Fragmentação Externa
        # Na alocação indexada, o arquivo não requer blocos contíguos para ser gravado,
        # portanto a fragmentação externa não impede a alocação enquanto houver blocos livres.
        print(f"Fragmentação Externa             : 0 bytes")
        print(f"Necessidade de Compactação       : NÃO (Blocos alocados via i-node indexado)")


def main():
    fs = FileSystemSimulator(total_blocks=16, block_size_kb=4)
    print("Simulador de Sistema de Arquivos iniciado. Digite 'help' para comandos.")

    while True:
        try:
            cmd_line = input("> ").strip()
            if not cmd_line:
                continue

            parts = shlex.split(cmd_line)
            cmd = parts[0]

            if cmd == "exit":
                break
            elif cmd == "mkdir":
                if len(parts) < 2:
                    print("Uso: mkdir <caminho>")
                else:
                    fs.mkdir(parts[1])
            elif cmd == "create":
                # Exemplo: create /sistema/logs/app.log --size 10KB
                if len(parts) >= 4 and parts[2] == "--size":
                    fs.create(parts[1], parts[3])
                elif len(parts) >= 3:
                    fs.create(parts[1], parts[2])
                else:
                    print("Uso: create <caminho> --size <tamanho>")
            elif cmd == "rm":
                if len(parts) < 2:
                    print("Uso: rm <caminho>")
                else:
                    fs.rm(parts[1])
            elif cmd == "tree":
                fs.tree()
            elif cmd == "fs_status":
                details = "--details" in parts
                fs.fs_status(details=details)
            elif cmd == "help":
                print("Comandos suportados:")
                print("  mkdir <path>")
                print("  create <path> --size <X>KB")
                print("  rm <path>")
                print("  tree")
                print("  fs_status [--details]")
                print("  exit")
            else:
                print(f"Comando desconhecido: '{cmd}'. Digite 'help'.")
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando...")
            break


if __name__ == "__main__":
    main()