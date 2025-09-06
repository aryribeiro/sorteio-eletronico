import streamlit as st
import sqlite3
import random
import time
import threading
from datetime import datetime, timedelta
import hashlib
from typing import List, Dict, Tuple, Optional
from contextlib import contextmanager
from functools import lru_cache
import weakref

# Configuração da página
st.set_page_config(
    page_title="Sorteio Eletrônico",
    page_icon="🎲",
    layout="centered",
    initial_sidebar_state="expanded"
)

# CSS otimizado
st.markdown("""
<style>
    .big-winner {
        font-size: 3.5rem;
        font-weight: bold;
        text-align: center;
        color: #FF6B35;
        background: linear-gradient(45deg, #FFE66D, #FF6B35);
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 10px 40px rgba(255,107,53,0.3);
        margin: 30px 0;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
    }
    
    .winner-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 25px;
        border-radius: 15px;
        margin: 15px 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.15);
        color: white;
        text-align: center;
    }
    
    .podium-card {
        border-radius: 15px;
        padding: 25px;
        text-align: center;
        font-weight: bold;
        margin: 15px 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        color: #333;
    }
    
    .student-item {
        background: rgba(255,255,255,0.1);
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        border-left: 4px solid #4CAF50;
    }
    
    .admin-panel {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 25px;
        border-radius: 15px;
        margin: 20px 0;
    }
    
    .status-badge {
        padding: 8px 16px;
        border-radius: 20px;
        display: inline-block;
        font-weight: bold;
    }
    
    .status-active { background: #4CAF50; color: white; }
    .status-inactive { background: #f44336; color: white; }
    
    .main {
        background-color: #ffffff;
        color: #333333;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        max-width: 1200px;
    }
    /* Performance - esconde elementos desnecessários */
    header {display: none !important;}
    footer {display: none !important;}
    #MainMenu {display: none !important;}
    .stDeployButton {display: none !important;}
    
    /* Otimizações de renderização */
    div[data-testid="stAppViewBlockContainer"] {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0.5rem !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    .element-container {
        margin-top: 0.25rem !important;
        margin-bottom: 0.25rem !important;
    }
    
    /* Scrolling suave para listas grandes */
    .student-item {
        scroll-behavior: smooth;
    }
    
    /* Animações otimizadas */
    @media (prefers-reduced-motion: reduce) {
        .big-winner {
            animation: none;
        }
    }
    
    /* Responsividade melhorada */
    @media (max-width: 768px) {
        .big-winner {
            font-size: 2.5rem;
            padding: 20px;
        }
        .podium-card {
            padding: 15px;
            margin: 10px 0;
        }
    }
</style>
""", unsafe_allow_html=True)

class ConnectionPool:
    """Pool de conexões SQLite otimizado"""
    
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._connections = []
        self._lock = threading.Lock()
        self._in_use = set()
        
    @contextmanager
    def get_connection(self):
        """Context manager para conexões reutilizáveis"""
        conn = None
        try:
            with self._lock:
                # Procurar conexão disponível
                for c in self._connections:
                    if c not in self._in_use:
                        conn = c
                        self._in_use.add(conn)
                        break
                
                # Criar nova se necessário
                if conn is None and len(self._connections) < self.max_connections:
                    conn = sqlite3.connect(
                        self.db_path,
                        check_same_thread=False,
                        timeout=30.0
                    )
                    # Configurar WAL mode para melhor concorrência
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
                    conn.execute("PRAGMA cache_size=10000")
                    conn.execute("PRAGMA temp_store=MEMORY")
                    
                    self._connections.append(conn)
                    self._in_use.add(conn)
                
                # Usar conexão existente se pool cheio
                if conn is None:
                    conn = self._connections[0]
                    if conn not in self._in_use:
                        self._in_use.add(conn)
            
            yield conn
            
        finally:
            if conn:
                with self._lock:
                    self._in_use.discard(conn)
    
    def close_all(self):
        """Fecha todas as conexões"""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except:
                    pass
            self._connections.clear()
            self._in_use.clear()

class CacheManager:
    """Gerenciador de cache com TTL"""
    
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        self._lock = threading.Lock()
    
    def get(self, key: str, ttl_seconds: int = 300) -> Optional[any]:
        """Recupera item do cache se válido"""
        with self._lock:
            if key in self._cache:
                if datetime.now() - self._timestamps[key] < timedelta(seconds=ttl_seconds):
                    return self._cache[key]
                else:
                    # Expirou
                    del self._cache[key]
                    del self._timestamps[key]
            return None
    
    def set(self, key: str, value: any):
        """Define item no cache"""
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = datetime.now()
    
    def invalidate(self, pattern: str = None):
        """Invalida cache por padrão"""
        with self._lock:
            if pattern:
                keys_to_remove = [k for k in self._cache.keys() if pattern in k]
                for key in keys_to_remove:
                    del self._cache[key]
                    del self._timestamps[key]
            else:
                self._cache.clear()
                self._timestamps.clear()
    
    def cleanup_expired(self, max_age_seconds: int = 3600):
        """Limpa entradas expiradas"""
        with self._lock:
            now = datetime.now()
            expired = [
                k for k, t in self._timestamps.items() 
                if now - t > timedelta(seconds=max_age_seconds)
            ]
            for key in expired:
                del self._cache[key]
                del self._timestamps[key]

class OptimizedSorteioSystem:
    """Sistema otimizado de sorteio com pooling e cache"""
    
    def __init__(self, db_path="sorteio.db"):
        self.db_path = db_path
        self.pool = ConnectionPool(db_path)
        self.cache = CacheManager()
        self._prepared_statements = {}
        self._last_action_time = {}
        self._debounce_delay = 1.0  # segundos
        self._init_db()
    
    def _init_db(self):
        """Inicializa banco com índices otimizados"""
        with self.pool.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS alunos (
                    id INTEGER PRIMARY KEY,
                    nome TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    numero_sorte INTEGER UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS sorteios (
                    id INTEGER PRIMARY KEY,
                    sessao_id TEXT NOT NULL,
                    aluno_id INTEGER,
                    numero_sorte INTEGER,
                    posicao INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (aluno_id) REFERENCES alunos (id)
                );
                
                CREATE TABLE IF NOT EXISTS sessao (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    ativa BOOLEAN DEFAULT FALSE,
                    sessao_id TEXT,
                    sorteios_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP,
                    ended_at TIMESTAMP
                );
                
                -- Índices para performance
                CREATE INDEX IF NOT EXISTS idx_alunos_email ON alunos(email);
                CREATE INDEX IF NOT EXISTS idx_alunos_numero ON alunos(numero_sorte);
                CREATE INDEX IF NOT EXISTS idx_sorteios_sessao ON sorteios(sessao_id);
                CREATE INDEX IF NOT EXISTS idx_sorteios_posicao ON sorteios(sessao_id, posicao);
                
                INSERT OR IGNORE INTO sessao (id) VALUES (1);
            """)
    
    def _debounce_action(self, action_key: str) -> bool:
        """Implementa debouncing para evitar spam de ações"""
        now = time.time()
        last_time = self._last_action_time.get(action_key, 0)
        
        if now - last_time < self._debounce_delay:
            return False
        
        self._last_action_time[action_key] = now
        return True
    
    def _get_prepared_statement(self, conn, key: str, query: str):
        """Cache de prepared statements"""
        if key not in self._prepared_statements:
            self._prepared_statements[key] = query
        return conn.execute(query)
    
    def cadastrar_aluno(self, nome: str, email: str) -> Tuple[bool, str, int]:
        """Cadastra novo aluno com debouncing"""
        if not self._debounce_action(f"cadastro_{email}"):
            return False, "Aguarde um momento antes de tentar novamente", 0
        
        try:
            nome, email = nome.strip(), email.strip().lower()
            
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                
                # Verificar email existente com índice otimizado
                if cursor.execute("SELECT 1 FROM alunos WHERE email = ? LIMIT 1", (email,)).fetchone():
                    return False, "Email já cadastrado!", 0
                
                # Gerar número único eficientemente
                max_attempts = 100
                for _ in range(max_attempts):
                    numero = random.randint(1000, 9999)
                    if not cursor.execute("SELECT 1 FROM alunos WHERE numero_sorte = ? LIMIT 1", (numero,)).fetchone():
                        break
                else:
                    return False, "Erro ao gerar número único. Tente novamente.", 0
                
                # Inserir aluno
                cursor.execute("INSERT INTO alunos (nome, email, numero_sorte) VALUES (?, ?, ?)", 
                             (nome, email, numero))
                conn.commit()
                
                # Invalidar caches relacionados
                self.cache.invalidate("alunos")
                
                return True, "Cadastrado com sucesso!", numero
                
        except Exception as e:
            return False, f"Erro: {str(e)}", 0
    
    @lru_cache(maxsize=1)
    def _get_alunos_count(self) -> int:
        """Cache do total de alunos"""
        with self.pool.get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM alunos").fetchone()[0]
    
    def get_alunos(self, force_refresh: bool = False) -> List[Dict]:
        """Lista alunos com cache inteligente"""
        cache_key = "alunos_list"
        
        if not force_refresh:
            cached = self.cache.get(cache_key, ttl_seconds=300)  # 5 min cache
            if cached is not None:
                return cached
        
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT id, nome, email, numero_sorte FROM alunos ORDER BY nome"
            ).fetchall()
            
            result = [{"id": r[0], "nome": r[1], "email": r[2], "numero_sorte": r[3]} for r in rows]
            
        self.cache.set(cache_key, result)
        return result
    
    def get_status_sessao(self, use_cache: bool = True) -> Dict:
        """Status da sessão com cache"""
        cache_key = "status_sessao"
        
        if use_cache:
            cached = self.cache.get(cache_key, ttl_seconds=30)  # 30s cache
            if cached is not None:
                return cached
        
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT ativa, sessao_id, sorteios_count FROM sessao WHERE id = 1"
            ).fetchone()
            
            result = {
                "ativa": bool(row[0]) if row else False,
                "sessao_id": row[1] if row else None,
                "sorteios_count": row[2] if row else 0
            }
        
        if use_cache:
            self.cache.set(cache_key, result)
        return result
    
    def iniciar_sessao(self) -> str:
        """Inicia nova sessão com cache invalidation"""
        if not self._debounce_action("iniciar_sessao"):
            return ""
        
        sessao_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
        
        with self.pool.get_connection() as conn:
            conn.execute("""
                UPDATE sessao SET ativa = TRUE, sessao_id = ?, sorteios_count = 0, 
                created_at = CURRENT_TIMESTAMP, ended_at = NULL WHERE id = 1
            """, (sessao_id,))
            conn.commit()
        
        # Invalidar caches
        self.cache.invalidate("status_sessao")
        self.cache.invalidate("vencedores")
        
        return sessao_id
    
    def sortear(self) -> Tuple[bool, Dict]:
        """Realiza sorteio otimizado"""
        if not self._debounce_action("sortear"):
            return False, {}
        
        status = self.get_status_sessao(use_cache=False)  # Força refresh
        
        if not status["ativa"] or status["sorteios_count"] >= 3:
            return False, {}
        
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Query otimizada para números já sorteados
            sorteados_query = """
                SELECT numero_sorte FROM sorteios 
                WHERE sessao_id = ? 
                ORDER BY posicao
            """
            sorteados = [row[0] for row in cursor.execute(sorteados_query, (status["sessao_id"],))]
            
            # Query otimizada para vencedor com LIMIT
            if sorteados:
                placeholders = ",".join("?" * len(sorteados))
                query = f"""
                    SELECT id, nome, numero_sorte FROM alunos 
                    WHERE numero_sorte NOT IN ({placeholders}) 
                    ORDER BY RANDOM() LIMIT 1
                """
                vencedor = cursor.execute(query, sorteados).fetchone()
            else:
                vencedor = cursor.execute(
                    "SELECT id, nome, numero_sorte FROM alunos ORDER BY RANDOM() LIMIT 1"
                ).fetchone()
            
            if not vencedor:
                return False, {}
            
            # Inserir resultado em transação única
            posicao = status["sorteios_count"] + 1
            cursor.execute("""
                INSERT INTO sorteios (sessao_id, aluno_id, numero_sorte, posicao) 
                VALUES (?, ?, ?, ?)
            """, (status["sessao_id"], vencedor[0], vencedor[2], posicao))
            
            cursor.execute("UPDATE sessao SET sorteios_count = ? WHERE id = 1", (posicao,))
            conn.commit()
            
            # Invalidar caches
            self.cache.invalidate("status_sessao")
            self.cache.invalidate("vencedores")
            
            return True, {
                "id": vencedor[0], 
                "nome": vencedor[1], 
                "numero_sorte": vencedor[2], 
                "posicao": posicao
            }
    
    def encerrar_sessao(self) -> List[Dict]:
        """Encerra sessão otimizada"""
        if not self._debounce_action("encerrar_sessao"):
            return []
        
        status = self.get_status_sessao(use_cache=False)
        if not status["ativa"]:
            return []
        
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Query otimizada com JOIN
            vencedores = cursor.execute("""
                SELECT s.posicao, a.nome, s.numero_sorte
                FROM sorteios s 
                INNER JOIN alunos a ON s.aluno_id = a.id
                WHERE s.sessao_id = ? 
                ORDER BY s.posicao
            """, (status["sessao_id"],)).fetchall()
            
            # Encerrar sessão
            cursor.execute(
                "UPDATE sessao SET ativa = FALSE, ended_at = CURRENT_TIMESTAMP WHERE id = 1"
            )
            conn.commit()
            
            # Invalidar caches
            self.cache.invalidate()
            
            return [{"posicao": r[0], "nome": r[1], "numero_sorte": r[2]} for r in vencedores]
    
    def get_vencedores_sessao_atual(self, use_cache: bool = True) -> List[Dict]:
        """Vencedores com cache"""
        status = self.get_status_sessao()
        if not status["sessao_id"]:
            return []
        
        cache_key = f"vencedores_{status['sessao_id']}"
        
        if use_cache:
            cached = self.cache.get(cache_key, ttl_seconds=60)
            if cached is not None:
                return cached
        
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT s.posicao, a.nome, s.numero_sorte
                FROM sorteios s 
                INNER JOIN alunos a ON s.aluno_id = a.id
                WHERE s.sessao_id = ? 
                ORDER BY s.posicao
            """, (status["sessao_id"],)).fetchall()
            
            result = [{"posicao": r[0], "nome": r[1], "numero_sorte": r[2]} for r in rows]
        
        if use_cache:
            self.cache.set(cache_key, result)
        return result
    
    def cleanup_resources(self):
        """Limpa recursos para economia de memória"""
        self.cache.cleanup_expired()
        self._prepared_statements.clear()
        
        # Limpa ações antigas
        current_time = time.time()
        old_actions = [
            k for k, t in self._last_action_time.items() 
            if current_time - t > 3600  # 1 hora
        ]
        for key in old_actions:
            del self._last_action_time[key]

# Estados otimizados para session_state
class SessionStateManager:
    """Gerenciador otimizado de estados"""
    
    @staticmethod
    def get_compressed_state(key: str, default=None):
        """Recupera estado de forma compactada"""
        return st.session_state.get(key, default)
    
    @staticmethod
    def set_compressed_state(key: str, value, expire_after: int = 3600):
        """Define estado com expiração"""
        st.session_state[key] = {
            'value': value,
            'timestamp': time.time(),
            'expire_after': expire_after
        }
    
    @staticmethod
    def cleanup_expired_states():
        """Limpa estados expirados"""
        current_time = time.time()
        keys_to_remove = []
        
        for key, state_data in st.session_state.items():
            if isinstance(state_data, dict) and 'timestamp' in state_data:
                if current_time - state_data['timestamp'] > state_data.get('expire_after', 3600):
                    keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del st.session_state[key]
    
    @staticmethod
    def get_state_value(key: str, default=None):
        """Recupera valor do estado gerenciado"""
        state_data = st.session_state.get(key)
        if isinstance(state_data, dict) and 'value' in state_data:
            current_time = time.time()
            if current_time - state_data['timestamp'] <= state_data.get('expire_after', 3600):
                return state_data['value']
            else:
                # Expirado
                if key in st.session_state:
                    del st.session_state[key]
        return default

# Sistema global com cleanup automático
@st.cache_resource
def get_sistema():
    sistema = OptimizedSorteioSystem()
    
    # Cleanup periódico em background
    def periodic_cleanup():
        import threading
        timer = threading.Timer(300.0, periodic_cleanup)  # 5 min
        timer.daemon = True
        timer.start()
        sistema.cleanup_resources()
    
    periodic_cleanup()
    return sistema

sistema = get_sistema()
state_manager = SessionStateManager()

def sidebar_alunos():
    """Sidebar otimizada com lazy loading"""
    with st.sidebar:
        st.header("👥 Cadastrados")
        
        # Lazy loading - só carrega quando necessário
        if st.sidebar.button("🔄 Atualizar Lista", key="refresh_sidebar"):
            alunos = sistema.get_alunos(force_refresh=True)
        else:
            alunos = sistema.get_alunos()
        
        if alunos:
            st.markdown(f"**Total: {len(alunos)} pessoas**")
            
            # Paginação para listas grandes
            items_per_page = 10
            total_pages = max(1, (len(alunos) + items_per_page - 1) // items_per_page)
            
            if total_pages > 1:
                page = st.selectbox("Página", range(1, total_pages + 1), key="sidebar_page") - 1
                start_idx = page * items_per_page
                end_idx = min(start_idx + items_per_page, len(alunos))
                alunos_page = alunos[start_idx:end_idx]
            else:
                alunos_page = alunos
            
            for aluno in alunos_page:
                st.markdown(f"""
                <div class="student-item">
                    <strong>{aluno['nome']}</strong><br>
                    <small>🎯 Nº {aluno['numero_sorte']}</small><br>
                    <small>📧 {aluno['email']}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Nenhum aluno cadastrado")

def area_cadastro():
    """Área de cadastro otimizada"""
    st.header("📋 Cadastro")
    
    with st.form("cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome Completo *", placeholder="Digite seu nome completo")
        with col2:
            email = st.text_input("Email *", placeholder="seu.email@exemplo.com")
        
        submitted = st.form_submit_button("🎯 Cadastrar e Receber Número da Sorte", use_container_width=True)
        
        if submitted:
            if not nome or not email:
                st.error("Preencha todos os campos!")
            elif "@" not in email:
                st.error("Email inválido!")
            else:
                with st.spinner("Processando cadastro..."):
                    sucesso, msg, numero = sistema.cadastrar_aluno(nome, email)
                
                if sucesso:
                    st.success(f"✅ {msg}")
                    st.balloons()
                    st.markdown(f"""
                    <div class="winner-card">
                        <h2>🎯 SEU NÚMERO DA SORTE</h2>
                        <h1 style="font-size: 3rem; margin: 0;">{numero:04d}</h1>
                        <p>Guarde bem este número!</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Usar state manager otimizado
                    state_manager.set_compressed_state("last_cadastro", {
                        "nome": nome,
                        "numero": numero,
                        "timestamp": time.time()
                    }, expire_after=300)
                    
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

def area_admin():
    """Painel administrativo otimizado"""
    st.header("🎯 Painel Administrativo")
    
    # Autenticação com estado persistente
    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False
    
    if not st.session_state.admin_logged:
        with st.form("login_form"):
            senha = st.text_input("Senha:", type="password")
            login_btn = st.form_submit_button("Entrar")
            
            if login_btn:
                if senha == "admin123":
                    st.session_state.admin_logged = True
                    st.success("Login realizado!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Senha incorreta!")
        return
    
    # Interface admin otimizada
    status = sistema.get_status_sessao()
    
    st.markdown(f"""
    <div class="admin-panel">
        <h3>Status da Sessão</h3>
        <p>Status: <span class="status-badge status-{'active' if status['ativa'] else 'inactive'}">
            {'🟢 ATIVA' if status['ativa'] else '🔴 INATIVA'}
        </span></p>
        <p>Sorteios realizados: <strong>{status['sorteios_count']}/3</strong></p>
        {f"<p>ID da Sessão: <code>{status['sessao_id']}</code></p>" if status['sessao_id'] else ""}
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🚀 Iniciar Nova Sessão", disabled=status['ativa'], use_container_width=True):
            with st.spinner("Iniciando sessão..."):
                sessao_id = sistema.iniciar_sessao()
            
            if sessao_id:
                st.success(f"Nova sessão iniciada! ID: {sessao_id}")
                time.sleep(1)
                st.rerun()
    
    with col2:
        sortear_disabled = not status['ativa'] or status['sorteios_count'] >= 3
        if st.button("🎲 SORTEAR", disabled=sortear_disabled, use_container_width=True):
            with st.spinner("Realizando sorteio..."):
                sucesso, vencedor = sistema.sortear()
            
            if sucesso:
                state_manager.set_compressed_state("ultimo_vencedor", vencedor, expire_after=1800)
                state_manager.set_compressed_state("mostrar_vencedor", True, expire_after=1800)
                st.rerun()
            else:
                st.error("Não foi possível sortear!")
    
    with col3:
        if st.button("🏁 Encerrar Sessão", disabled=not status['ativa'], use_container_width=True):
            with st.spinner("Encerrando sessão..."):
                vencedores = sistema.encerrar_sessao()
            
            if vencedores:
                state_manager.set_compressed_state("vencedores_finais", vencedores, expire_after=1800)
                state_manager.set_compressed_state("mostrar_podium", True, expire_after=1800)
                state_manager.set_compressed_state("mostrar_vencedor", False)
                st.rerun()
    
    # Logout
    if st.button("🚪 Logout", type="secondary"):
        st.session_state.admin_logged = False
        st.rerun()

def exibir_vencedor():
    """Exibe vencedor atual otimizado"""
    vencedor = state_manager.get_state_value("ultimo_vencedor")
    
    if not vencedor:
        st.error("Dados do vencedor não encontrados")
        return
    
    st.markdown(f"""
    <div class="big-winner">
        🎉 VENCEDOR SORTEADO! 🎉<br>
        {vencedor['nome']}<br>
        Número: {vencedor['numero_sorte']:04d}<br>
        {vencedor['posicao']}º Lugar
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        # Verificar se ainda há sorteios disponíveis
        status = sistema.get_status_sessao(use_cache=False)
        sortear_disabled = not status['ativa'] or status['sorteios_count'] >= 3
        
        if st.button("🎲 SORTEAR", disabled=sortear_disabled, use_container_width=True):
            with st.spinner("Realizando sorteio..."):
                sucesso, vencedor = sistema.sortear()
            
            if sucesso:
                state_manager.set_compressed_state("ultimo_vencedor", vencedor, expire_after=1800)
                state_manager.set_compressed_state("mostrar_vencedor", True, expire_after=1800)
                st.rerun()
            else:
                st.error("Não foi possível sortear!")
                # Volta para a administração
                state_manager.set_compressed_state("mostrar_vencedor", False)
                st.rerun()
    
    with col2:
        if st.button("🏁 Encerrar e Ver Pódio", use_container_width=True):
            with st.spinner("Processando..."):
                vencedores = sistema.encerrar_sessao()
            
            if vencedores:
                state_manager.set_compressed_state("vencedores_finais", vencedores, expire_after=1800)
                state_manager.set_compressed_state("mostrar_podium", True, expire_after=1800)
                state_manager.set_compressed_state("mostrar_vencedor", False)
                st.rerun()

def exibir_podium():
    """Exibe pódio final otimizado"""
    st.header("🏆 PÓDIO FINAL")
    
    vencedores = state_manager.get_state_value("vencedores_finais")
    
    if not vencedores:
        st.error("Dados do pódio não encontrados")
        return
    
    # Exibir vencedores com animação CSS
    for vencedor in sorted(vencedores, key=lambda x: x['posicao']):
        pos = vencedor['posicao']
        emoji = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉"
        cor = "#FFD700" if pos == 1 else "#C0C0C0" if pos == 2 else "#CD7F32"
        
        st.markdown(f"""
        <div class="podium-card" style="background: linear-gradient(135deg, {cor}, {cor});">
            <div style="font-size: 3rem; margin-bottom: 10px;">{emoji}</div>
            <div style="font-size: 1.5rem; margin-bottom: 10px;">{pos}º LUGAR</div>
            <div style="font-size: 1.8rem; margin: 15px 0;">{vencedor['nome']}</div>
            <div style="font-size: 1.2rem;">Número: {vencedor['numero_sorte']:04d}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Nova Sessão", use_container_width=True, type="primary"):
            # Limpar estados otimizado
            keys_to_clear = ['mostrar_podium', 'vencedores_finais', 'ultimo_vencedor', 'mostrar_vencedor']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            with st.spinner("Iniciando nova sessão..."):
                sessao_id = sistema.iniciar_sessao()
            
            if sessao_id:
                st.success(f"Nova sessão iniciada! ID: {sessao_id}")
                time.sleep(1)
                st.rerun()
    
    with col2:
        if st.button("🎊 Finalizar Apresentação", use_container_width=True):
            # Limpar todos os estados
            keys_to_clear = ['mostrar_podium', 'vencedores_finais', 'ultimo_vencedor', 'mostrar_vencedor']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

def area_resultados():
    """Área de resultados otimizada"""
    st.header("📊 Resultados da Sessão Atual")
    
    # Cache de resultados
    vencedores = sistema.get_vencedores_sessao_atual()
    
    if vencedores:
        st.markdown("### 🏆 Classificação Atual")
        
        for vencedor in vencedores:
            pos = vencedor['posicao']
            emoji = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉"
            
            st.markdown(f"""
            <div class="winner-card">
                <h3>{emoji} {pos}º Lugar</h3>
                <h2>{vencedor['nome']}</h2>
                <p>Número: {vencedor['numero_sorte']:04d}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Estatísticas adicionais
        status = sistema.get_status_sessao()
        if status['ativa']:
            st.info(f"📈 Sorteios restantes: {3 - status['sorteios_count']}")
        
    else:
        st.info("Nenhum sorteio realizado ainda.")
        
        # Mostrar informações da sessão se ativa
        status = sistema.get_status_sessao()
        if status['ativa']:
            st.markdown(f"""
            <div class="admin-panel">
                <h4>Sessão Ativa</h4>
                <p>ID: <code>{status['sessao_id']}</code></p>
                <p>Aguardando primeiro sorteio...</p>
            </div>
            """, unsafe_allow_html=True)

def main():
    """Função principal otimizada"""
    # Cleanup automático de estados expirados
    state_manager.cleanup_expired_states()
    
    st.title("🎲 Sorteio Eletrônico")
    st.markdown("---")
    
    # Sidebar com lazy loading
    sidebar_alunos()
    
    # Controle de fluxo otimizado
    mostrar_vencedor = state_manager.get_state_value("mostrar_vencedor", False)
    mostrar_podium = state_manager.get_state_value("mostrar_podium", False)
    ultimo_vencedor = state_manager.get_state_value("ultimo_vencedor")
    
    if mostrar_vencedor and ultimo_vencedor:
        exibir_vencedor()
        return
    
    if mostrar_podium:
        exibir_podium()
        return
    
    # Menu principal com estado persistente
    menu_options = ["👤 Cadastro", "🎯 Administração", "📊 Resultados"]
    menu_key = "main_menu"
    
    # Preservar seleção do menu
    if menu_key not in st.session_state:
        st.session_state[menu_key] = menu_options[0]
    
    menu = st.radio(
        "Escolha uma opção:",
        menu_options,
        horizontal=True,
        key=menu_key
    )
    
    # Roteamento otimizado
    if menu == "👤 Cadastro":
        area_cadastro()
    elif menu == "🎯 Administração":
        area_admin()
    else:
        area_resultados()
    
    # Cleanup periódico no final
    if hasattr(sistema, 'cleanup_resources'):
        # Fazer cleanup a cada 50 execuções para não impactar performance
        cleanup_counter = st.session_state.get('cleanup_counter', 0) + 1
        st.session_state.cleanup_counter = cleanup_counter
        
        if cleanup_counter % 50 == 0:
            sistema.cleanup_resources()

# Função de inicialização otimizada
@st.cache_data(ttl=3600)  # Cache por 1 hora
def get_app_metadata():
    """Metadados da aplicação com cache"""
    return {
        "version": "2.0.0",
        "last_updated": datetime.now().isoformat(),
        "features": ["connection_pooling", "intelligent_cache", "lazy_loading", "debouncing"]
    }

# Tratamento de erros global
def handle_app_errors():
    """Tratamento global de erros"""
    try:
        main()
    except Exception as e:
        st.error("⚠️ Ocorreu um erro inesperado. Recarregue a página.")
        
        # Log do erro (em produção, usar logging apropriado)
        if st.secrets.get("DEBUG", False):
            st.exception(e)
        
        # Opção de reset
        if st.button("🔄 Resetar Aplicação"):
            st.session_state.clear()
            sistema.cache.invalidate()
            st.rerun()

if __name__ == "__main__":
    # Inicialização com verificações
    try:
        # Verificar metadados
        metadata = get_app_metadata()
        
        # Executar aplicação
        handle_app_errors()
        
    except Exception as e:
        st.error("❌ Falha crítica na inicialização da aplicação")
        st.code(f"Erro: {str(e)}")
        
        if st.button("🔄 Tentar Novamente"):
            st.rerun()

st.markdown("""
<style>
    .main {
        background-color: #ffffff;
        color: #333333;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    /* Esconde completamente todos os elementos da barra padrão do Streamlit */
    header {display: none !important;}
    footer {display: none !important;}
    #MainMenu {display: none !important;}
    /* Remove qualquer espaço em branco adicional */
    div[data-testid="stAppViewBlockContainer"] {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0 !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    /* Remove quaisquer margens extras */
    .element-container {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
</style>
""", unsafe_allow_html=True)
st.markdown("---")
st.markdown("""
<div style="text-align: center;">
    <h4>Sorteio Eletrônico: a sorte, por meio de números e pessoas</h4>
    Por 🎲<strong>Ary Ribeiro</strong>: <a href="mailto:aryribeiro@gmail.com">aryribeiro@gmail.com</a><br>
    <em>Obs.: o web app foi testado apenas em computador.</em>
</div>
""", unsafe_allow_html=True)