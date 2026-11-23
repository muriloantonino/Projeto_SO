#!/usr/bin/env python3
"""
Simulador de Sistema Operacionais (Etapas 1, 2, 3 e 4)
- Etapa 1: Sistema de Arquivos (Árvore, CRUD, Alocação Indexada / i-node)
- Etapa 2: Escalonamento de Disco (SSTF/FCFS) e RAID 5 (XOR real)
- Etapa 3: Segurança (Modo Kernel/Usuário, SHA-256+Salt, ACL rwx, Criptografia, Antivírus)
- Etapa 4: Memória Híbrida (Área Reservada Contígua + Compactação | Memória Virtual Paginada + LRU)
"""

import math
import re
import time
import shlex
import hashlib
import secrets
from datetime import datetime


# ==============================================================================
# CAMADA 0: SEGURANÇA, AUTENTICAÇÃO, CRIPTOGRAFIA E AUDITORIA (ETAPA 3)
# ==============================================================================

class User:
    def __init__(self, username: str, group: str, password: str, is_root: bool = False):
        self.username = username
        self.group = group
        self.is_root = is_root
        self.salt = secrets.token_hex(16)
        self.password_hash = self._hash_password(password, self.salt)

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

    def verify_password(self, password: str) -> bool:
        return self._hash_password(password, self.salt) == self.password_hash


class SecurityManager:
    MALWARE_SIGNATURES = [b"EICAR-TEST-SIGNATURE", b"MALWARE_PAYLOAD", b"TROJAN_EXEC"]

    def __init__(self):
        self.users = {}
        self.audit_logs = []
        self.add_user("root", "admin", "root", is_root=True, silent=True)
        self.add_user("carlos", "devs", "1234", is_root=False, silent=True)
        self.current_user = self.users["root"]

    def mode_name(self) -> str:
        return "MODO_KERNEL" if self.current_user.is_root else "MODO_USUARIO"

    def log_event(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.audit_logs.append(f"[{ts}] {message}")

    def require_kernel(self, action_name: str) -> bool:
        if not self.current_user.is_root:
            msg = f"[NEGADO]: Operação crítica '{action_name}' requer MODO_KERNEL (root). Usuário atual: '{self.current_user.username}'."
            print(msg)
            self.log_event(msg)
            return False
        return True

    def add_user(self, username: str, group: str, password: str, is_root: bool = False, silent: bool = False):
        if not silent and not self.require_kernel("useradd"):
            return
        if username in self.users:
            print(f"Erro: Usuário '{username}' já existe.")
            return
        self.users[username] = User(username, group, password, is_root=is_root)
        if not silent:
            print(f"Usuário '{username}' (Grupo: '{group}') criado com hash SHA-256 + salt.")
            self.log_event(f"USERADD: '{username}' criado por '{self.current_user.username}'.")

    def login(self, username: str, password: str) -> bool:
        user = self.users.get(username)
        if not user or not user.verify_password(password):
            print("[FALHA DE AUTENTICAÇÃO]: Usuário ou senha inválidos.")
            self.log_event(f"LOGIN_FALHA: tentativa para usuário '{username}'.")
            return False
        self.current_user = user
        print(f"Autenticado com sucesso. Usuário: '{user.username}' | Grupo: '{user.group}' | Modo: {self.mode_name()}")
        self.log_event(f"LOGIN_OK: '{user.username}' ({self.mode_name()}).")
        return True

    @staticmethod
    def format_permissions(mode: int) -> str:
        chars = []
        for shift in (6, 3, 0):
            bits = (mode >> shift) & 0b111
            chars.append("r" if bits & 4 else "-")
            chars.append("w" if bits & 2 else "-")
            chars.append("x" if bits & 1 else "-")
        return "".join(chars)

    def check_acl(self, node, path: str, action: str) -> bool:
        if self.current_user.is_root:
            return True
        bit_map = {"r": 4, "w": 2, "x": 1}
        action_label = {"r": "LEITURA", "w": "ESCRITA", "x": "EXECUÇÃO"}[action]
        req_bit = bit_map[action]

        if self.current_user.username == node.owner:
            allowed_bits = (node.permissions >> 6) & 0b111
        elif self.current_user.group == node.group:
            allowed_bits = (node.permissions >> 3) & 0b111
        else:
            allowed_bits = node.permissions & 0b111

        if allowed_bits & req_bit:
            return True

        perm_str = self.format_permissions(node.permissions)
        octal_str = f"{node.permissions:03o}"
        print("\n[SISTEMA DE SEGURANÇA - VERIFICAÇÃO DE ACL]")
        print(f"Objeto      : {path}")
        print(f"Proprietário: {node.owner} (Grupo: {node.group})")
        print(f"Permissões  : {perm_str} ({octal_str})")
        print(f"Ação Pedida : {action_label} por '{self.current_user.username}' (Grupo: {self.current_user.group})\n")
        print(f"[NEGADO]: O usuário '{self.current_user.username}' não possui permissão de {action_label.lower()} no objeto '{path}'.")
        print("Tentativa não autorizada registrada nos logs do sistema.")
        self.log_event(f"ACL_NEGADO: '{self.current_user.username}' tentou {action_label} em '{path}' ({octal_str}).")
        return False

    @staticmethod
    def _generate_keystream(key: str, length: int) -> bytes:
        key_bytes = key.encode("utf-8")
        stream = bytearray()
        counter = 0
        while len(stream) < length:
            digest = hashlib.sha256(key_bytes + counter.to_bytes(4, "big")).digest()
            stream.extend(digest)
            counter += 1
        return bytes(stream[:length])

    def xor_cipher(self, data: bytes, key: str) -> bytes:
        ks = self._generate_keystream(key, len(data))
        return bytes(a ^ b for a, b in zip(data, ks))

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()


# ==============================================================================
# CAMADA 1: ARRANJO RAID 5 (ETAPA 2)
# ==============================================================================

class PhysicalDisk:
    def __init__(self, disk_id: int):
        self.disk_id = disk_id
        self.online = True
        self.stripes = {}


class RAID5Array:
    def __init__(self, num_disks: int = 3, block_size: int = 4096):
        self.num_disks = num_disks
        self.block_size = block_size
        self.disks = [PhysicalDisk(i + 1) for i in range(num_disks)]
        self.stripe_counter = 0
        self.file_stripes = {}

    @staticmethod
    def _xor_bytes(b1: bytes, b2: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(b1, b2))

    def _pad_block(self, data: bytes) -> bytes:
        if len(data) < self.block_size:
            return data + b"\x00" * (self.block_size - len(data))
        return data[:self.block_size]

    def write_data(self, file_path: str, raw_data: bytes, verbose: bool = True):
        data_disks_per_stripe = self.num_disks - 1
        stripe_capacity = data_disks_per_stripe * self.block_size
        num_stripes = max(1, math.ceil(len(raw_data) / stripe_capacity))
        allocated_stripes = []

        if verbose:
            print(f"\nArranjo Ativo: RAID 5 ({self.num_disks} Discos Físicos, Blocos de {self.block_size // 1024} KB)")
            print("[E/S - DISTRIBUIÇÃO EM DISCO]")

        for s in range(num_stripes):
            stripe_id = self.stripe_counter
            self.stripe_counter += 1
            allocated_stripes.append(stripe_id)

            parity_disk_idx = (self.num_disks - 1 - (stripe_id % self.num_disks))
            chunk_start = s * stripe_capacity
            stripe_chunk = raw_data[chunk_start : chunk_start + stripe_capacity]

            data_blocks = []
            for d in range(data_disks_per_stripe):
                part = stripe_chunk[d * self.block_size : (d + 1) * self.block_size]
                data_blocks.append(self._pad_block(part))

            parity_block = bytes(self.block_size)
            for blk in data_blocks:
                parity_block = self._xor_bytes(parity_block, blk)

            data_idx = 0
            for disk_idx, disk in enumerate(self.disks):
                if disk_idx == parity_disk_idx:
                    disk.stripes[stripe_id] = parity_block
                    if verbose:
                        print(f"  Disco {disk.disk_id} (Stripe {stripe_id:02d}): [PARIDADE : XOR ({len(parity_block)} B)]")
                else:
                    disk.stripes[stripe_id] = data_blocks[data_idx]
                    if verbose:
                        print(f"  Disco {disk.disk_id} (Stripe {stripe_id:02d}): [DADO Part {data_idx + 1} ({len(data_blocks[data_idx])} B)]")
                    data_idx += 1

        self.file_stripes[file_path] = allocated_stripes

    def fail_disk(self, disk_id: int):
        if not (1 <= disk_id <= self.num_disks):
            print(f"Erro: Disco {disk_id} inválido (1 a {self.num_disks}).")
            return
        disk = self.disks[disk_id - 1]
        disk.online = False
        disk.stripes.clear()
        print(f"[RAID 5] Falha simulada no Disco {disk_id}! Status: OFFLINE.")

    def read_and_reconstruct(self, file_path: str, original_size: int, verbose: bool = True) -> bytes:
        if file_path not in self.file_stripes:
            return b""
        if len([d for d in self.disks if not d.online]) > 1:
            if verbose:
                print("[RAID 5] ERRO CRÍTICO: Mais de 1 disco falhou.")
            return b""

        reconstructed = bytearray()
        for stripe_id in self.file_stripes[file_path]:
            parity_disk_idx = (self.num_disks - 1 - (stripe_id % self.num_disks))
            for disk_idx, disk in enumerate(self.disks):
                if disk_idx == parity_disk_idx:
                    continue
                if disk.online:
                    reconstructed.extend(disk.stripes[stripe_id])
                else:
                    recovered = bytes(self.block_size)
                    healthy = []
                    for other in self.disks:
                        if other.online:
                            recovered = self._xor_bytes(recovered, other.stripes[stripe_id])
                            healthy.append(f"Disco {other.disk_id}")
                    if verbose:
                        print(f"[RAID 5] Disco {disk.disk_id} OFFLINE -> Reconstruindo via XOR ({' XOR '.join(healthy)}) [OK]")
                    reconstructed.extend(recovered)
        return bytes(reconstructed[:original_size])

    def rebuild_disk(self, disk_id: int):
        if not (1 <= disk_id <= self.num_disks):
            print(f"Erro: Disco {disk_id} inválido.")
            return
        target = self.disks[disk_id - 1]
        if target.online:
            print(f"[RAID 5] Disco {disk_id} já está ONLINE.")
            return
        if len([d for d in self.disks if not d.online]) > 1:
            print("[RAID 5] ERRO: Impossível reconstruir com mais de 1 disco falho.")
            return
        for stripe_id in range(self.stripe_counter):
            recovered = bytes(self.block_size)
            for other in self.disks:
                if other.disk_id != disk_id and stripe_id in other.stripes:
                    recovered = self._xor_bytes(recovered, other.stripes[stripe_id])
            target.stripes[stripe_id] = recovered
        target.online = True
        print(f"[RAID 5] Disco {disk_id} reconstruído com sucesso -> ONLINE [OK]")

    def tamper_raw_block(self, file_path: str) -> bool:
        if file_path not in self.file_stripes:
            return False
        stripe_id = self.file_stripes[file_path][0]
        parity_disk_idx = (self.num_disks - 1 - (stripe_id % self.num_disks))
        for idx, disk in enumerate(self.disks):
            if idx != parity_disk_idx and disk.online and stripe_id in disk.stripes:
                raw = bytearray(disk.stripes[stripe_id])
                raw[0] ^= 0xFF
                disk.stripes[stripe_id] = bytes(raw)
                return True
        return False


# ==============================================================================
# CAMADA 2: ESCALONAMENTO DE BRAÇO DE DISCO (ETAPA 2)
# ==============================================================================

class DiskScheduler:
    def __init__(self, initial_head: int = 53, algorithm: str = "SSTF"):
        self.head_position = initial_head
        self.algorithm = algorithm.upper()
        self.pending_queue = []

    def enqueue(self, tracks: list):
        self.pending_queue.extend(tracks)

    def process_queue(self, operation_label: str = "E/S"):
        if not self.pending_queue:
            return
        print(f"\n[{operation_label}] Trilhas pendentes: {self.pending_queue} | Cabeça atual: {self.head_position}")
        reqs = list(self.pending_queue)
        self.pending_queue.clear()

        pos = self.head_position
        ordem = [pos]
        distancias = []

        if self.algorithm == "SSTF":
            while reqs:
                prox = min(reqs, key=lambda t: abs(t - pos))
                distancias.append(abs(prox - pos))
                pos = prox
                ordem.append(pos)
                reqs.remove(prox)
        else:
            for prox in reqs:
                distancias.append(abs(prox - pos))
                pos = prox
                ordem.append(pos)

        self.head_position = pos
        print(f"--- ESCALONAMENTO ({self.algorithm}) ---")
        print(f"Ordem: {' -> '.join(map(str, ordem))} | Movimento total: {sum(distancias)} trilhas")


# ==============================================================================
# CAMADA 3: GERENCIAMENTO DE MEMÓRIA HÍBRIDA (ETAPA 4)
# ==============================================================================

class ReservedBlock:
    def __init__(self, name: str, start_kb: int, size_kb: int, locked: bool = False):
        self.name = name
        self.start_kb = start_kb
        self.size_kb = size_kb
        self.locked = locked  # True para o Núcleo Base do SO

    @property
    def end_kb(self) -> int:
        return self.start_kb + self.size_kb


class PageTableEntry:
    def __init__(self, page_num: int, used_bytes: int):
        self.page_num = page_num
        self.used_bytes = used_bytes
        self.valid = False          # Está na RAM física?
        self.frame_num = None       # Moldura física na RAM Dinâmica
        self.in_swap = True         # Reside no Swap (memória secundária)


class VirtualProcess:
    def __init__(self, pid: int, name: str, size_bytes: int, page_size: int):
        self.pid = pid
        self.name = name
        self.size_bytes = size_bytes
        self.num_pages = max(1, math.ceil(size_bytes / page_size))
        self.page_table = {}

        remaining = size_bytes
        for p in range(self.num_pages):
            used = min(page_size, remaining)
            remaining -= used
            self.page_table[p] = PageTableEntry(p, used)


class PhysicalFrame:
    def __init__(self, frame_num: int):
        self.frame_num = frame_num
        self.process_name = None
        self.pid = None
        self.page_num = None
        self.last_access = 0.0  # Timestamp para LRU


class MemoryManager:
    def __init__(self, sec: SecurityManager, scheduler: DiskScheduler, reserved_total_kb: int = 4096, num_frames: int = 4, page_size_kb: int = 4):
        self.sec = sec
        self.scheduler = scheduler
        self.reserved_total_kb = reserved_total_kb  # 4 MB
        self.page_size = page_size_kb * 1024        # 4 KB
        self.pid_counter = 100

        # Área Estática/Reservada: começa com o Núcleo Base do SO (0.0 MB - 1.0 MB)
        self.reserved_blocks = [
            ReservedBlock("Núcleo Base do SO", start_kb=0, size_kb=1024, locked=True)
        ]

        # Área Dinâmica (Memória Virtual Paginada)
        self.frames = [PhysicalFrame(i) for i in range(num_frames)]
        self.virtual_processes = {}  # name -> VirtualProcess
        self.swap_space = set()      # {(process_name, page_num)}
        self.page_fault_count = 0
        self.page_hit_count = 0

    @staticmethod
    def _kb_to_mb(kb: int) -> str:
        return f"{kb / 1024:.1f} MB"

    def _get_reserved_gaps(self):
        """Retorna lista de lacunas livres [(start_kb, size_kb), ...] na Área Reservada."""
        blocks = sorted(self.reserved_blocks, key=lambda b: b.start_kb)
        gaps = []
        cursor = 0
        for blk in blocks:
            if blk.start_kb > cursor:
                gaps.append((cursor, blk.start_kb - cursor))
            cursor = blk.end_kb
        if cursor < self.reserved_total_kb:
            gaps.append((cursor, self.reserved_total_kb - cursor))
        return gaps

    # --- CRIAÇÃO E ENCERRAMENTO DE PROCESSOS ---

    def create_process(self, name: str, size_bytes: int, proc_type: str):
        proc_type = proc_type.lower()
        if proc_type == "critical":
            if not self.sec.require_kernel("create_process --type critical"):
                return
            if any(b.name == name for b in self.reserved_blocks):
                print(f"Erro: Processo crítico '{name}' já existe.")
                return

            size_kb = max(1, math.ceil(size_bytes / 1024))
            gaps = self._get_reserved_gaps()
            # Alocação Contígua (First-Fit)
            chosen_start = None
            for start_kb, gap_kb in gaps:
                if gap_kb >= size_kb:
                    chosen_start = start_kb
                    break

            if chosen_start is None:
                total_free = sum(g[1] for g in gaps)
                max_gap = max((g[1] for g in gaps), default=0)
                print(f"[ERRO DE ALOCAÇÃO CONTÍGUA]: Não há bloco único de {size_kb} KB na Área Reservada.")
                print(f"Memória livre total: {total_free} KB | Maior bloco contíguo: {max_gap} KB.")
                if total_free >= size_kb:
                    print("Dica: Há fragmentação externa! Execute 'memory_compact --reserved' para compactar.")
                return

            new_blk = ReservedBlock(name, start_kb=chosen_start, size_kb=size_kb)
            self.reserved_blocks.append(new_blk)
            self.reserved_blocks.sort(key=lambda b: b.start_kb)
            print(f"- Alocado de forma contígua na Área Reservada: [{self._kb_to_mb(new_blk.start_kb)} até {self._kb_to_mb(new_blk.end_kb)}] ({size_kb} KB)")

        elif proc_type == "normal":
            if name in self.virtual_processes:
                print(f"Erro: Processo '{name}' já existe.")
                return

            self.pid_counter += 1
            proc = VirtualProcess(self.pid_counter, name, size_bytes, self.page_size)
            self.virtual_processes[name] = proc
            for p in range(proc.num_pages):
                self.swap_space.add((name, p))

            size_kb = size_bytes / 1024
            page_kb = self.page_size / 1024
            print("\n[CRIAÇÃO DE PROCESSO NÃO CRÍTICO - MEMÓRIA VIRTUAL]")
            print(f"Processo (PID {proc.pid}) : {name}")
            print(f"Tamanho do Processo : {size_kb:.1f} KB ({size_bytes} Bytes)")
            print(f"Tamanho da Página   : {page_kb:.0f} KB ({self.page_size} Bytes)")
            print(f"Cálculo de Páginas  : {size_kb:.1f} KB / {page_kb:.0f} KB = {size_kb / page_kb:.2f} -> Requer {proc.num_pages} Página(s) Lógica(s).")

            print("\n--- ANÁLISE DE FRAGMENTAÇÃO INTERNA ---")
            total_internal_frag = 0
            for p, entry in proc.page_table.items():
                pct = (entry.used_bytes / self.page_size) * 100
                waste = self.page_size - entry.used_bytes
                total_internal_frag += waste
                print(f"Página Lógica {p} : {entry.used_bytes} Bytes ocupados ({pct:.0f}% de uso)")
            print(f"Fragmentação Interna Total: {total_internal_frag} Bytes de desperdício.")
            print("Status: Tabela de Páginas gerada sem alocar molduras na RAM (Alocação por demanda).")
        else:
            print("Erro: Tipo inválido. Use --type critical ou --type normal.")

    def terminate_process(self, name: str):
        # Verifica na Área Reservada
        for blk in self.reserved_blocks:
            if blk.name == name:
                if blk.locked:
                    print("Erro: Não é permitido encerrar o Núcleo Base do SO.")
                    return
                if not self.sec.require_kernel("terminate_process (critical)"):
                    return
                self.reserved_blocks.remove(blk)
                print(f"[ENCERRAMENTO DE PROCESSO CRÍTICO] Processo '{name}' finalizado.")
                print(f"Área de {blk.size_kb} KB no intervalo [{self._kb_to_mb(blk.start_kb)} a {self._kb_to_mb(blk.end_kb)}] liberada na Área Reservada da RAM.")
                return

        # Verifica na Memória Virtual
        if name in self.virtual_processes:
            proc = self.virtual_processes.pop(name)
            freed_frames = []
            for frame in self.frames:
                if frame.process_name == name:
                    freed_frames.append(frame.frame_num)
                    frame.process_name = None
                    frame.pid = None
                    frame.page_num = None
                    frame.last_access = 0.0
            self.swap_space = {item for item in self.swap_space if item[0] != name}
            print(f"[ENCERRAMENTO DE PROCESSO] '{name}' (PID {proc.pid}) finalizado. Molduras liberadas: {freed_frames}")
            return

        print(f"Erro: Processo '{name}' não encontrado.")

    # --- STATUS E COMPACTAÇÃO ---

    def memory_status(self, mode: str = "all"):
        if mode in ("all", "reserved"):
            print(f"\n--- MAPA DA ÁREA CRÍTICA/RESERVADA DA RAM (Total: {self._kb_to_mb(self.reserved_total_kb)} - Alocação Fixa) ---")
            blocks = sorted(self.reserved_blocks, key=lambda b: b.start_kb)
            cursor = 0
            gap_idx = 0
            gaps = []

            for blk in blocks:
                if blk.start_kb > cursor:
                    gap_idx += 1
                    gap_size = blk.start_kb - cursor
                    gaps.append(gap_size)
                    print(f"[{self._kb_to_mb(cursor)} - {self._kb_to_mb(blk.start_kb)}] : FRAGMENTO LIVRE {gap_idx:<5} ({gap_size} KB) [LIVRE - LACUNA]")
                print(f"[{self._kb_to_mb(blk.start_kb)} - {self._kb_to_mb(blk.end_kb)}] : {blk.name:<21} ({blk.size_kb} KB) [OCUPADO]")
                cursor = blk.end_kb

            if cursor < self.reserved_total_kb:
                gap_idx += 1
                gap_size = self.reserved_total_kb - cursor
                gaps.append(gap_size)
                label = f"FRAGMENTO LIVRE {gap_idx}" if len(gaps) > 1 else "Bloco Livre Contíguo"
                tag = "[LIVRE - LACUNA]" if len(gaps) > 1 else "[LIVRE]"
                print(f"[{self._kb_to_mb(cursor)} - {self._kb_to_mb(self.reserved_total_kb)}] : {label:<21} ({gap_size} KB) {tag}")

            total_free = sum(gaps)
            max_contig = max(gaps, default=0)
            has_ext_frag = len(gaps) > 1

            print("\n--- DIAGNÓSTICO DE FRAGMENTAÇÃO EXTERNA ---")
            print(f"Total de Memória Livre na Área Reservada : {total_free} KB ({self._kb_to_mb(total_free)})")
            print(f"Maior Bloco Contíguo Disponível          : {max_contig} KB ({self._kb_to_mb(max_contig)})")
            if has_ext_frag:
                print(f"Fragmentação Externa Detectada           : SIM ({len(gaps)} fragmentos não contíguos)")
                print(f"Status: Uma requisição contígua entre {max_contig + 1} KB e {total_free} KB falhará sem compactação.")
            else:
                print("Fragmentação Externa Detectada           : NÃO")

        if mode in ("all", "virtual"):
            used_frames = sum(1 for f in self.frames if f.process_name is not None)
            print(f"\n--- MEMÓRIA VIRTUAL / RAM DINÂMICA ({used_frames}/{len(self.frames)} Molduras Ocupadas | Página: {self.page_size // 1024} KB) ---")
            for f in self.frames:
                if f.process_name:
                    age_ms = (time.perf_counter() - f.last_access) * 1000
                    print(f"  Moldura {f.frame_num:02d} : {f.process_name} (PID {f.pid}) - Página {f.page_num} [Último acesso há {age_ms:.1f}ms]")
                else:
                    print(f"  Moldura {f.frame_num:02d} : [LIVRE]")
            print(f"Swap (Disco): {len(self.swap_space)} página(s) | Page Hits: {self.page_hit_count} | Page Faults: {self.page_fault_count}")

    def compact_reserved(self):
        if not self.sec.require_kernel("memory_compact --reserved"):
            return
        print("\n[EXECUTANDO COMPACTAÇÃO DA ÁREA RESERVADA DA RAM]")
        print("Realocando blocos contíguos para eliminar a fragmentação externa...")

        blocks = sorted(self.reserved_blocks, key=lambda b: b.start_kb)
        cursor = 0
        moved = False
        for blk in blocks:
            if blk.start_kb != cursor:
                old_range = f"[{self._kb_to_mb(blk.start_kb)} a {self._kb_to_mb(blk.end_kb)}]"
                blk.start_kb = cursor
                new_range = f"[{self._kb_to_mb(blk.start_kb)} a {self._kb_to_mb(blk.end_kb)}]"
                print(f"- Mapeamento de '{blk.name}': {old_range} -> Ajustado para: {new_range}")
                moved = True
            cursor = blk.end_kb

        if not moved:
            print("- Nenhum bloco precisou ser movido (já estava compactado).")

        self.memory_status(mode="reserved")

    # --- TRADUÇÃO DE ENDEREÇOS, PAGE FAULT E LRU ---

    def translate_address(self, proc_name: str, page_num: int):
        proc = self.virtual_processes.get(proc_name)
        if not proc:
            print(f"Erro: Processo virtual '{proc_name}' não encontrado.")
            return
        if page_num not in proc.page_table:
            print(f"Erro: Página Lógica {page_num} fora dos limites de '{proc_name}' (0 a {proc.num_pages - 1}).")
            return

        entry = proc.page_table[page_num]
        print("\n[TRADUÇÃO DE ENDEREÇO: PÁGINA LÓGICA -> MOLDURA FÍSICA]")
        if entry.valid:
            self.page_hit_count += 1
            self.frames[entry.frame_num].last_access = time.perf_counter()
            print(f"Solicitação: Página Lógica {page_num} -> Mapeada na Moldura Física {entry.frame_num} (RAM Dinâmica) [HIT]")
        else:
            print(f"Solicitação: Página Lógica {page_num} -> NÃO ESTÁ NA RAM (Reside no Swap) [MISS / PAGE FAULT]")
            print(f"Dica: Use 'execute_step --process {proc_name} --instruction \"LOAD_DATA Página {page_num}\"' para carregar na RAM.")

    def execute_step(self, proc_name: str, instruction: str):
        proc = self.virtual_processes.get(proc_name)
        if not proc:
            print(f"Erro: Processo virtual '{proc_name}' não encontrado.")
            return

        nums = re.findall(r"\d+", instruction)
        if not nums:
            print("Erro: Informe o número da página na instrução (ex: \"LOAD_DATA Página 2\").")
            return
        page_num = int(nums[-1])

        if page_num not in proc.page_table:
            print(f"Erro: Segmentation Fault! Página {page_num} inválida para '{proc_name}'.")
            return

        print("\n[CPU - REFERÊNCIA DE MEMÓRIA EM EXECUÇÃO]")
        print(f"{proc_name} (PID {proc.pid}) executa '{instruction}' -> Requisita Página Lógica {page_num}...")

        entry = proc.page_table[page_num]
        if entry.valid:
            self.page_hit_count += 1
            self.frames[entry.frame_num].last_access = time.perf_counter()
            print(f"- Consulta Tabela de Páginas -> Página Lógica {page_num} encontrada na Moldura Física {entry.frame_num} [HIT]")
            return

        # PAGE FAULT REAL
        self.page_fault_count += 1
        print(f"- Consulta Tabela de Páginas -> Página Lógica {page_num} NÃO ESTÁ NA RAM!")
        print(f"\n[PAGE FAULT DETECTADO]: Página Lógica {page_num} ausente na RAM!")

        free_frame = next((f for f in self.frames if f.process_name is None), None)

        if free_frame is None:
            # RAM Dinâmica cheia -> Algoritmo LRU (Least Recently Used)
            victim_frame = min(self.frames, key=lambda f: f.last_access)
            elapsed_ms = (time.perf_counter() - victim_frame.last_access) * 1000

            print("Memória RAM cheia. Executando Substituição de Página (Algoritmo LRU):")
            print(f"- Analisando histórico de acesso: Página Lógica {victim_frame.page_num} de '{victim_frame.process_name}' (PID {victim_frame.pid}) não é usada há {elapsed_ms:.1f}ms (Mais antiga).")
            print(f"- Removendo Página Lógica {victim_frame.page_num} do PID {victim_frame.pid} da RAM -> Salvando no Swap (Disco).")

            # Atualiza tabela de páginas da vítima
            victim_proc = self.virtual_processes.get(victim_frame.process_name)
            if victim_proc and victim_frame.page_num in victim_proc.page_table:
                victim_proc.page_table[victim_frame.page_num].valid = False
                victim_proc.page_table[victim_frame.page_num].frame_num = None
                victim_proc.page_table[victim_frame.page_num].in_swap = True
            self.swap_space.add((victim_frame.process_name, victim_frame.page_num))

            # Integração com Etapa 2: gera E/S real de Swap-Out + Swap-In no escalonador de disco
            swap_tracks = [(victim_frame.pid * 7 + victim_frame.page_num * 13) % 200, (proc.pid * 7 + page_num * 13) % 200]
            self.scheduler.enqueue(swap_tracks)
            self.scheduler.process_queue("E/S - SWAPPING (OUT/IN)")

            target_frame = victim_frame
        else:
            print(f"Moldura livre encontrada: Moldura Física {free_frame.frame_num}. Carregando do Swap...")
            swap_track = (proc.pid * 7 + page_num * 13) % 200
            self.scheduler.enqueue([swap_track])
            self.scheduler.process_queue("E/S - SWAP-IN")
            target_frame = free_frame

        # Carrega nova página na moldura
        target_frame.process_name = proc.name
        target_frame.pid = proc.pid
        target_frame.page_num = page_num
        target_frame.last_access = time.perf_counter()

        entry.valid = True
        entry.frame_num = target_frame.frame_num
        self.swap_space.discard((proc.name, page_num))

        print(f"- Carregando Página Lógica {page_num} de '{proc.name}' na Moldura Física {target_frame.frame_num} (RAM Dinâmica).")
        print(f"- Tabela de Páginas atualizada: Página Lógica {page_num} ---> Moldura Física {target_frame.frame_num}")


# ==============================================================================
# CAMADA 4: SISTEMA DE ARQUIVOS INTEGRADO (ETAPAS 1, 2, 3 e 4)
# ==============================================================================

class Inode:
    def __init__(self, inode_id: int, is_directory: bool, name: str, owner: str, group: str, permissions: int):
        self.id = inode_id
        self.is_directory = is_directory
        self.name = name
        self.owner = owner
        self.group = group
        self.permissions = permissions
        self.size_bytes = 0
        self.data_blocks = []
        self.children = {}
        self.parent = None
        self.is_encrypted = False
        self.content_hash = ""


class DiskBlock:
    def __init__(self, block_id: int, track: int):
        self.id = block_id
        self.track = track
        self.is_allocated = False
        self.block_type = "LIVRE"
        self.owner_path = ""
        self.used_bytes = 0
        self.block_index = 0


class FileSystemSimulator:
    def __init__(self, total_blocks: int = 32, block_size_kb: int = 4):
        self.block_size = block_size_kb * 1024
        self.total_blocks = total_blocks
        self.disk = [DiskBlock(i, track=(i * 17 + 14) % 200) for i in range(total_blocks)]
        self.inode_counter = 0

        self.sec = SecurityManager()
        self.scheduler = DiskScheduler(initial_head=53, algorithm="SSTF")
        self.raid = RAID5Array(num_disks=3, block_size=self.block_size)
        self.mem = MemoryManager(self.sec, self.scheduler, reserved_total_kb=4096, num_frames=4, page_size_kb=4)

        self.root = self._create_inode(True, "/", "root", "admin", 0o755)
        self.root.parent = self.root
        self.current_dir = self.root
        self._allocate_block_for_inode(self.root, "/")

    def _create_inode(self, is_dir: bool, name: str, owner: str, group: str, perm: int) -> Inode:
        node = Inode(self.inode_counter, is_dir, name, owner, group, perm)
        self.inode_counter += 1
        return node

    def _find_free_block(self):
        return next((b for b in self.disk if not b.is_allocated), None)

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

    def _get_parent_and_name(self, path: str):
        path = path.rstrip("/")
        if not path:
            return None, None
        if "/" not in path:
            return self.current_dir, path
        parent_path, name = path.rsplit("/", 1)
        parent = self.root if parent_path == "" else self._resolve_path(parent_path)
        return parent, name

    def _get_full_path(self, node: Inode) -> str:
        if node == self.root:
            return "/"
        parts = []
        curr = node
        while curr != self.root:
            parts.append(curr.name)
            curr = curr.parent
        return "/" + "/".join(reversed(parts))

    @staticmethod
    def parse_size(size_str: str) -> int:
        s = size_str.strip().upper()
        if s.endswith("MB"):
            return int(float(s[:-2]) * 1024 * 1024)
        elif s.endswith("KB"):
            return int(float(s[:-2]) * 1024)
        elif s.endswith("B"):
            return int(s[:-1])
        return int(s)

    # ---------------- CRUD (ETAPAS 1, 2, 3) ----------------

    def mkdir(self, path: str):
        parent, name = self._get_parent_and_name(path)
        if not parent or not parent.is_directory:
            print(f"Erro: Diretório pai inexistente para '{path}'.")
            return
        if not self.sec.check_acl(parent, self._get_full_path(parent), "w"):
            return
        if name in parent.children:
            print(f"Erro: '{name}' já existe.")
            return
        u = self.sec.current_user
        new_dir = self._create_inode(True, name, u.username, u.group, 0o755)
        new_dir.parent = parent
        parent.children[name] = new_dir

    def create(self, path: str, size_str: str, content: str = ""):
        size_bytes = self.parse_size(size_str)
        blocks_needed = max(1, math.ceil(size_bytes / self.block_size))
        free_blocks = [b for b in self.disk if not b.is_allocated]
        if len(free_blocks) < blocks_needed + 1:
            print("Erro: Espaço insuficiente em disco.")
            return

        parent, name = self._get_parent_and_name(path)
        if not parent or not parent.is_directory:
            print(f"Erro: Caminho pai inexistente para '{path}'.")
            return
        if not self.sec.check_acl(parent, self._get_full_path(parent), "w"):
            return
        if name in parent.children:
            print(f"Erro: '{name}' já existe.")
            return

        u = self.sec.current_user
        new_file = self._create_inode(False, name, u.username, u.group, 0o644)
        new_file.size_bytes = size_bytes
        new_file.parent = parent
        full_path = self._get_full_path(new_file)

        inode_blk = free_blocks[0]
        inode_blk.is_allocated = True
        inode_blk.block_type = f"INODE_{name.split('.')[0].upper()}"
        inode_blk.owner_path = full_path
        inode_blk.used_bytes = self.block_size
        new_file.data_blocks.append(inode_blk.id)

        remaining = size_bytes
        tracks = [inode_blk.track]
        for i in range(blocks_needed):
            blk = free_blocks[1 + i]
            blk.is_allocated = True
            blk.block_type = "DADO"
            blk.owner_path = full_path
            blk.block_index = i + 1
            used = min(self.block_size, remaining)
            blk.used_bytes = used
            remaining -= used
            new_file.data_blocks.append(blk.id)
            tracks.append(blk.track)

        parent.children[name] = new_file
        raw = content.encode("utf-8") if content else (f"DADOS_{name}_" * (size_bytes // 10 + 1)).encode("utf-8")[:size_bytes]
        new_file.content_hash = self.sec.sha256_bytes(raw)
        self.scheduler.enqueue(tracks)
        self.scheduler.process_queue(f"E/S - CREATE {full_path}")
        self.raid.write_data(full_path, raw)

    def write_file(self, path: str, content: str):
        target = self._resolve_path(path)
        if not target:
            raw = content.encode("utf-8")
            self.create(path, f"{max(len(raw), 1024)}B", content=content)
            return
        if target.is_directory:
            print(f"Erro: '{path}' é um diretório.")
            return
        full_path = self._get_full_path(target)
        if not self.sec.check_acl(target, full_path, "w"):
            return
        raw = content.encode("utf-8")
        target.size_bytes = len(raw)
        target.is_encrypted = False
        target.content_hash = self.sec.sha256_bytes(raw)
        self.scheduler.enqueue([self.disk[b].track for b in target.data_blocks])
        self.scheduler.process_queue(f"E/S - WRITE {full_path}")
        self.raid.write_data(full_path, raw)

    def read_file(self, path: str):
        target = self._resolve_path(path)
        if not target or target.is_directory:
            print(f"Erro: Arquivo '{path}' não encontrado.")
            return
        full_path = self._get_full_path(target)
        if not self.sec.check_acl(target, full_path, "r"):
            return
        self.scheduler.enqueue([self.disk[b].track for b in target.data_blocks])
        self.scheduler.process_queue(f"E/S - READ {full_path}")
        data = self.raid.read_and_reconstruct(full_path, target.size_bytes)
        if target.is_encrypted:
            print(f"\n[CONTEÚDO CRIPTOGRAFADO]: 0x{data[:16].hex().upper()}...")
        else:
            print(f"\n[CONTEÚDO DE '{full_path}'] ({len(data)} B): \"{data[:150].decode('utf-8', errors='ignore')}\"")

    def rm(self, path: str):
        target = self._resolve_path(path)
        if not target or target == self.root:
            print(f"Erro: Não é possível remover '{path}'.")
            return
        if not self.sec.check_acl(target, self._get_full_path(target), "w"):
            return
        self._recursive_delete(target)
        del target.parent.children[target.name]
        print(f"'{path}' removido.")

    def _recursive_delete(self, node: Inode):
        if node.is_directory:
            for c in list(node.children.values()):
                self._recursive_delete(c)
        for blk_id in node.data_blocks:
            blk = self.disk[blk_id]
            blk.is_allocated = False
            blk.block_type = "LIVRE"
            blk.owner_path = ""
            blk.used_bytes = 0
        node.data_blocks.clear()

    def chmod(self, octal_str: str, path: str):
        target = self._resolve_path(path)
        if not target:
            print(f"Erro: '{path}' não encontrado.")
            return
        if not self.sec.current_user.is_root and self.sec.current_user.username != target.owner:
            print("[NEGADO]: Apenas o proprietário ou root pode alterar permissões.")
            return
        target.permissions = int(octal_str, 8)
        print(f"Permissões de '{path}' alteradas para {self.sec.format_permissions(target.permissions)} ({octal_str}).")

    def chown(self, owner_group: str, path: str):
        if not self.sec.require_kernel("chown"):
            return
        target = self._resolve_path(path)
        if not target or ":" not in owner_group:
            print("Uso: chown <usuario>:<grupo> <caminho>")
            return
        owner, group = owner_group.split(":", 1)
        target.owner, target.group = owner, group
        print(f"Proprietário de '{path}' alterado para {owner}:{group}.")

    def encrypt_file(self, path: str, key: str):
        target = self._resolve_path(path)
        if not target or target.is_directory:
            print(f"Erro: Arquivo '{path}' não encontrado.")
            return
        full_path = self._get_full_path(target)
        if not self.sec.check_acl(target, full_path, "w"):
            return
        plain = self.raid.read_and_reconstruct(full_path, target.size_bytes, verbose=False)
        cipher = self.sec.xor_cipher(plain, key)
        target.is_encrypted = True
        target.content_hash = self.sec.sha256_bytes(cipher)
        self.raid.write_data(full_path, cipher, verbose=False)
        print(f"Arquivo '{full_path}' criptografado com sucesso.")
        print(f'Conteúdo gravado nos blocos físicos: "0x{cipher[:8].hex().upper()}... (Encrypted Ciphertext)"')

    def decrypt_file(self, path: str, key: str):
        target = self._resolve_path(path)
        if not target or target.is_directory or not target.is_encrypted:
            print(f"Erro: '{path}' não encontrado ou não está criptografado.")
            return
        full_path = self._get_full_path(target)
        if not self.sec.check_acl(target, full_path, "w"):
            return
        cipher = self.raid.read_and_reconstruct(full_path, target.size_bytes, verbose=False)
        plain = self.sec.xor_cipher(cipher, key)
        target.is_encrypted = False
        target.content_hash = self.sec.sha256_bytes(plain)
        self.raid.write_data(full_path, plain, verbose=False)
        print(f"Arquivo '{full_path}' descriptografado com sucesso.")

    def antivirus_scan(self, path: str = "/"):
        start_node = self._resolve_path(path)
        if not start_node:
            print(f"Erro: '{path}' não encontrado.")
            return
        files = []
        def collect(n):
            if not n.is_directory:
                files.append(n)
            for c in n.children.values():
                collect(c)
        collect(start_node)
        print("\n[MÓDULO DE SEGURANÇA - VARREDURA DE INTEGRIDADE]")
        print(f"Analisando {len(files)} arquivo(s)...")
        for f in files:
            fpath = self._get_full_path(f)
            disk_bytes = self.raid.read_and_reconstruct(fpath, f.size_bytes, verbose=False)
            if self.sec.sha256_bytes(disk_bytes) != f.content_hash:
                print(f"- {fpath:<28} : [ALERTA] Hash do bloco difere do registro oficial!")
                self.sec.log_event(f"AV_ALERTA: Integridade violada em '{fpath}'.")
                continue
            hit = next((sig for sig in self.sec.MALWARE_SIGNATURES if sig in disk_bytes), None)
            if hit:
                print(f"- {fpath:<28} : [AMEAÇA] Assinatura '{hit.decode()}' detectada!")
            else:
                st = "Criptografado e Íntegro" if f.is_encrypted else "Íntegro"
                print(f"- {fpath:<28} : [OK - {st}]")

    def tree(self):
        print("\n[ÁRVORE DO SISTEMA DE ARQUIVOS]")
        print(f"/ [{self.sec.format_permissions(self.root.permissions)} root:admin]")
        self._print_tree(self.root, "")

    def _print_tree(self, node: Inode, prefix: str):
        entries = list(node.children.values())
        for idx, c in enumerate(entries):
            conn = "└── " if idx == len(entries) - 1 else "├── "
            sub = "    " if idx == len(entries) - 1 else "│   "
            perm = self.sec.format_permissions(c.permissions)
            if c.is_directory:
                print(f"{prefix}{conn}{c.name}/ [DIR {perm} {c.owner}:{c.group}]")
                self._print_tree(c, prefix + sub)
            else:
                enc = " [ENC]" if c.is_encrypted else ""
                print(f"{prefix}{conn}{c.name} ({c.size_bytes} B) [ARQ {perm} {c.owner}:{c.group}]{enc}")

    def fs_status(self):
        print(f"\nBloco: {self.block_size // 1024} KB | Total: {self.total_blocks} blocos")
        for b in self.disk:
            if b.is_allocated:
                print(f"Bloco {b.id:02d} (Trilha {b.track:03d}) [{b.block_type:<10}] : {b.owner_path} ({b.used_bytes} B)")
        free_count = sum(1 for b in self.disk if not b.is_allocated)
        print(f"Blocos Livres: {free_count}/{self.total_blocks}")


# ==============================================================================
# PARSER AUXILIAR DE FLAGS E SHELL INTERATIVO
# ==============================================================================

def parse_flags(parts: list) -> dict:
    """Extrai argumentos no formato --chave valor."""
    flags = {}
    i = 1
    while i < len(parts):
        if parts[i].startswith("--"):
            key = parts[i][2:]
            if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                flags[key] = parts[i + 1]
                i += 2
            else:
                flags[key] = True
                i += 1
        else:
            i += 1
    return flags


def main():
    fs = FileSystemSimulator()
    print("Simulador de SO (Etapas 1, 2, 3 e 4). Padrão: root (senha: root) | carlos (senha: 1234)")
    print("Digite 'help' para ver todos os comandos.")

    while True:
        try:
            u = fs.sec.current_user
            prompt_char = "#" if u.is_root else "$"
            cmd_line = input(f"\n[{u.username}@{fs.sec.mode_name()}]{prompt_char} ").strip()
            if not cmd_line:
                continue

            parts = shlex.split(cmd_line)
            cmd = parts[0]
            flags = parse_flags(parts)

            if cmd == "exit":
                break
            # --- ETAPA 4: MEMÓRIA ---
            elif cmd == "create_process":
                if "name" in flags and "size" in flags and "type" in flags:
                    fs.mem.create_process(flags["name"], fs.parse_size(flags["size"]), flags["type"])
                else:
                    print('Uso: create_process --name "Nome" --size 512KB --type <critical|normal>')
            elif cmd == "terminate_process":
                if "name" in flags:
                    fs.mem.terminate_process(flags["name"])
                else:
                    print('Uso: terminate_process --name "Nome"')
            elif cmd == "memory_status":
                if "reserved" in flags:
                    fs.mem.memory_status("reserved")
                elif "virtual" in flags:
                    fs.mem.memory_status("virtual")
                else:
                    fs.mem.memory_status("all")
            elif cmd == "memory_compact":
                fs.mem.compact_reserved()
            elif cmd == "translate_address":
                if "process" in flags and "page" in flags:
                    fs.mem.translate_address(flags["process"], int(flags["page"]))
                else:
                    print("Uso: translate_address --process <Nome> --page <N>")
            elif cmd == "execute_step":
                if "process" in flags and "instruction" in flags:
                    fs.mem.execute_step(flags["process"], flags["instruction"])
                else:
                    print('Uso: execute_step --process <Nome> --instruction "LOAD_DATA Página 2"')
            # --- ETAPA 3: SEGURANÇA ---
            elif cmd == "whoami":
                print(f"Usuário: '{u.username}' | Grupo: '{u.group}' | Modo: {fs.sec.mode_name()}")
            elif cmd == "login":
                user_arg = flags.get("user", parts[1] if len(parts) >= 2 else "")
                if user_arg:
                    fs.sec.login(user_arg, input("Senha: "))
                else:
                    print("Uso: login --user <usuario>")
            elif cmd == "useradd" and len(parts) >= 4:
                fs.sec.add_user(parts[1], parts[2], parts[3])
            elif cmd == "chmod" and len(parts) >= 3:
                fs.chmod(parts[1], parts[2])
            elif cmd == "chown" and len(parts) >= 3:
                fs.chown(parts[1], parts[2])
            elif cmd == "encrypt_file" and len(parts) >= 4 and "key" in flags:
                fs.encrypt_file(parts[1], flags["key"])
            elif cmd == "decrypt_file" and len(parts) >= 4 and "key" in flags:
                fs.decrypt_file(parts[1], flags["key"])
            elif cmd == "antivirus_scan":
                fs.antivirus_scan(parts[1] if len(parts) >= 2 else "/")
            elif cmd == "tamper_block" and len(parts) >= 2:
                if fs.sec.require_kernel("tamper_block"):
                    if fs.raid.tamper_raw_block(parts[1]):
                        print(f"[SIMULAÇÃO] Bloco físico de '{parts[1]}' adulterado!")
            elif cmd == "security_logs":
                for line in fs.sec.audit_logs:
                    print(" ", line)
            # --- ETAPAS 1 e 2: FS / E/S / RAID ---
            elif cmd == "mkdir" and len(parts) >= 2:
                fs.mkdir(parts[1])
            elif cmd == "create" and len(parts) >= 3:
                fs.create(parts[1], flags.get("size", parts[2]))
            elif cmd == "write_file" and len(parts) >= 3:
                fs.write_file(parts[1], " ".join(parts[2:]))
            elif cmd == "read_file" and len(parts) >= 2:
                fs.read_file(parts[1])
            elif cmd == "rm" and len(parts) >= 2:
                fs.rm(parts[1])
            elif cmd == "tree":
                fs.tree()
            elif cmd == "fs_status":
                fs.fs_status()
            elif cmd == "set_scheduler" and len(parts) >= 2:
                if fs.sec.require_kernel("set_scheduler"):
                    fs.scheduler.algorithm = parts[1].upper()
                    print(f"Escalonador: {fs.scheduler.algorithm}")
            elif cmd == "fail_disk" and len(parts) >= 2:
                if fs.sec.require_kernel("fail_disk"):
                    fs.raid.fail_disk(int(parts[1]))
            elif cmd == "rebuild_disk" and len(parts) >= 2:
                if fs.sec.require_kernel("rebuild_disk"):
                    fs.raid.rebuild_disk(int(parts[1]))
            elif cmd == "help":
                print("Memória (Etapa 4):")
                print('  create_process --name "Nome" --size <X>KB --type <critical|normal>')
                print('  terminate_process --name "Nome"')
                print("  memory_status [--reserved | --virtual] | memory_compact --reserved")
                print("  translate_address --process <Nome> --page <N>")
                print('  execute_step --process <Nome> --instruction "LOAD_DATA Página <N>"')
                print("Segurança (Etapa 3):")
                print("  login --user <u> | useradd <u> <g> <senha> | whoami | security_logs")
                print("  chmod <750> <path> | chown <u:g> <path> | encrypt_file | decrypt_file | antivirus_scan")
                print("FS / E/S / RAID (Etapas 1 e 2):")
                print("  mkdir | create | write_file | read_file | rm | tree | fs_status")
                print("  set_scheduler <SSTF|FCFS> | fail_disk <n> | rebuild_disk <n> | exit")
            else:
                print("Comando inválido. Digite 'help'.")
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando...")
            break


if __name__ == "__main__":
    main()
