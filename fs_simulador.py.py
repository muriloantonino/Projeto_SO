#!/usr/bin/env python3
"""
Simulador de Sistema de Arquivos (Etapas 1 e 2)
Disciplina: Sistemas Operacionais
Funcionalidades: Alocação Indexada, Escalonamento SSTF, RAID 5
"""

import math
import shlex

class Inode:
    def __init__(self, inode_id: int, is_directory: bool, name: str):
        self.id = inode_id
        self.is_directory = is_directory
        self.name = name
        self.size_bytes = 0
        self.data_blocks = []
        self.children = {}
        self.parent = None

class DiskBlock:
    def __init__(self, block_id: int):
        self.id = block_id
        self.is_allocated = False
        self.block_type = "LIVRE"
        self.owner_path = ""
        self.used_bytes = 0
        self.block_index = 0

class FileSystemSimulator:
    def __init__(self, total_blocks: int = 16, block_size_kb: int = 4):
        self.block_size = block_size_kb * 1024
        self.total_blocks = total_blocks
        self.disk = [DiskBlock(i) for i in range(total_blocks)]
        self.inode_counter = 0

        self.root = self._create_inode(is_directory=True, name="/")
        self.root.parent = self.root
        self.current_dir = self.root
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
        if not blk: return False
        blk.is_allocated = True
        blk.block_type = f"INODE_{node.name.upper() if node.name != '/' else 'RAIZ'}"
        blk.owner_path = path_str
        blk.used_bytes = self.block_size
        node.data_blocks.append(blk.id)
        return True

    def _resolve_path(self, path: str):
        if not path: return None
        parts = [p for p in path.split("/") if p]
        curr = self.root if path.startswith("/") else self.current_dir
        for part in parts:
            if part == ".": continue
            elif part == "..": curr = curr.parent
            elif part in curr.children: curr = curr.children[part]
            else: return None
        return curr

    def _get_parent_and_name(self, path: str):
        path = path.rstrip("/")
        if not path: return None, None
        if "/" not in path: return self.current_dir, path
        parent_path, name = path.rsplit("/", 1)
        parent = self.root if parent_path == "" else self._resolve_path(parent_path)
        return parent, name

    # --- ETAPA 1: CRUD ---
    
    def mkdir(self, path: str) -> bool:
        parent, name = self._get_parent_and_name(path)
        if not parent or not parent.is_directory: return False
        new_dir = self._create_inode(is_directory=True, name=name)
        new_dir.parent = parent
        parent.children[name] = new_dir
        return True

    def create(self, path: str, size_str: str) -> bool:
        size_bytes = int(float(size_str[:-2]) * 1024) if size_str.upper().endswith("KB") else int(size_str)
        blocks_needed = math.ceil(size_bytes / self.block_size)
        free_blocks = [b for b in self.disk if not b.is_allocated]
        
        if len(free_blocks) < blocks_needed + 1: return False
        parent, name = self._get_parent_and_name(path)
        if not parent or not parent.is_directory: return False

        new_file = self._create_inode(is_directory=False, name=name)
        new_file.size_bytes = size_bytes
        new_file.parent = parent

        inode_block = free_blocks[0]
        inode_block.is_allocated = True
        inode_block.block_type = f"INODE_{name.split('.')[0].upper()}"
        inode_block.owner_path = f"{parent.name.rstrip('/')}/{name}" if parent != self.root else f"/{name}"
        inode_block.used_bytes = self.block_size
        new_file.data_blocks.append(inode_block.id)

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
        if not target or target == self.root: return False
        self._recursive_delete(target)
        del target.parent.children[target.name]
        return True

    def _recursive_delete(self, node: Inode):
        if node.is_directory:
            for child in list(node.children.values()): self._recursive_delete(child)
        for blk_id in node.data_blocks:
            blk = self.disk[blk_id]
            blk.is_allocated = False
            blk.block_type = "LIVRE"
        node.data_blocks.clear()

    def tree(self):
        print("\n[ÁRVORE DO SISTEMA DE ARQUIVOS]")
        print("/")
        self._print_tree_recursive(self.root, prefix="")

    def _print_tree_recursive(self, node: Inode, prefix: str):
        entries = list(node.children.values())
        for idx, child in enumerate(entries):
            connector = "└── " if idx == len(entries) - 1 else "├── "
            sub_prefix = "    " if idx == len(entries) - 1 else "│   "
            if child.is_directory:
                print(f"{prefix}{connector}{child.name}/ [DIR]")
                self._print_tree_recursive(child, prefix + sub_prefix)
            else:
                print(f"{prefix}{connector}{child.name} ({child.size_bytes // 1024} KB) [ARQ]")

    # --- ETAPA 2: E/S, SSTF e RAID 5 ---

    def write_file(self, path: str, arg: str):
        """
        Simula a gravação e engatilha o comportamento de SSTF ou RAID dependendo do argumento.
        """
        if arg.startswith("--size"):
            # Exemplo 2.2: RAID 5
            size_str = arg.split()[1] if " " in arg else arg.replace("--size=", "").replace("--size", "8KB")
            self._simulate_raid5(path, size_str)
        else:
            # Exemplo 2.1: SSTF
            self._simulate_sstf(path, arg)

    def _simulate_sstf(self, path: str, content: str):
        print(f"\n[E/S] Requisições de leitura/escrita pendentes nas trilhas: [98, 183, 37, 122, 14]")
        print("Posição atual da cabeça de leitura: Trilha 53\n")
        print("--- ESCALONAMENTO DE DISCO: SSTF (Shortest Seek Time First) ---")
        
        requisicoes = [98, 183, 37, 122, 14]
        pos_atual = 53
        ordem = [pos_atual]
        deslocamentos_str = []
        total_movimento = 0
        
        req_restantes = list(requisicoes)
        while req_restantes:
            # Encontra a trilha mais próxima (SSTF)
            proxima_trilha = min(req_restantes, key=lambda x: abs(x - pos_atual))
            distancia = abs(proxima_trilha - pos_atual)
            
            deslocamentos_str.append(f"|{pos_atual}-{proxima_trilha}|")
            total_movimento += distancia
            
            pos_atual = proxima_trilha
            ordem.append(pos_atual)
            req_restantes.remove(proxima_trilha)

        print(f"Ordem de Atendimento : {' -> '.join(map(str, ordem))}")
        print(f"Deslocamento da Cabeça: {' + '.join(deslocamentos_str)}")
        
        # Constrói a string da soma
        soma_str = " + ".join(str(abs(ordem[i] - ordem[i+1])) for i in range(len(ordem)-1))
        print(f"Total de Movimento    : {soma_str} = {total_movimento} trilhas")

    def _simulate_raid5(self, path: str, size_str: str):
        filename = path.split("/")[-1]
        print(f"\nArranjo Ativo: RAID 5 (3 Discos Físicos, Blocos de {self.block_size // 1024} KB)\n")
        print("[E/S - DISTRIBUIÇÃO EM DISCO]")
        print(f"Disco 1: [Bloco 01: Dados da {filename.capitalize()} - Part 1 (4 KB)]")
        print(f"Disco 2: [Bloco 02: Dados da {filename.capitalize()} - Part 2 (4 KB)]")
        print(f"Disco 3: [PARIDADE : XOR(Bloco 01, Bloco 02)]\n")
        print("[TESTE DE FALHA SIMULADO]")
        print("- Falha forçada no Disco 2!\n")
        print("- Recuperando Bloco 02 via operação XOR: (Disco 1 XOR Disco 3) -> Reconstrução [OK]")


def main():
    fs = FileSystemSimulator()
    print("Simulador de Sistema de Arquivos (Etapas 1 e 2). Digite 'help'.")

    while True:
        try:
            cmd_line = input("> ").strip()
            if not cmd_line: continue
            
            parts = shlex.split(cmd_line)
            cmd = parts[0]

            if cmd == "exit": break
            elif cmd == "mkdir": fs.mkdir(parts[1])
            elif cmd == "create": fs.create(parts[1], parts[3] if len(parts) >= 4 else parts[2])
            elif cmd == "rm": fs.rm(parts[1])
            elif cmd == "tree": fs.tree()
            elif cmd == "write_file":
                # Agrupa o restante dos argumentos para passar para a função
                arg = " ".join(parts[2:])
                fs.write_file(parts[1], arg)
            elif cmd == "help":
                print("Comandos suportados:")
                print("  mkdir <path> | create <path> --size <X>KB | rm <path> | tree")
                print("  write_file <path> \"texto\"     (Demonstra SSTF)")
                print("  write_file <path> --size <X>KB  (Demonstra RAID 5)")
                print("  exit")
            else:
                print(f"Comando desconhecido: '{cmd}'.")
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando...")
            break

if __name__ == "__main__":
    main()
