import streamlit as st
import sqlite3
import random
import time
from datetime import datetime
import hashlib
from typing import List, Dict, Tuple

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
</style>
""", unsafe_allow_html=True)

class SorteioSystem:
    """Sistema principal de sorteio"""
    
    def __init__(self, db_path="sorteio.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa banco de dados"""
        with sqlite3.connect(self.db_path) as conn:
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
                
                INSERT OR IGNORE INTO sessao (id) VALUES (1);
            """)
    
    def cadastrar_aluno(self, nome: str, email: str) -> Tuple[bool, str, int]:
        """Cadastra novo aluno"""
        try:
            nome, email = nome.strip(), email.strip().lower()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Verificar email existente
                if cursor.execute("SELECT 1 FROM alunos WHERE email = ?", (email,)).fetchone():
                    return False, "Email já cadastrado!", 0
                
                # Gerar número único
                while True:
                    numero = random.randint(1000, 9999)
                    if not cursor.execute("SELECT 1 FROM alunos WHERE numero_sorte = ?", (numero,)).fetchone():
                        break
                
                # Inserir aluno
                cursor.execute("INSERT INTO alunos (nome, email, numero_sorte) VALUES (?, ?, ?)", 
                             (nome, email, numero))
                return True, "Cadastrado com sucesso!", numero
                
        except Exception as e:
            return False, f"Erro: {str(e)}", 0
    
    def get_alunos(self) -> List[Dict]:
        """Lista alunos ordenados"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT id, nome, email, numero_sorte FROM alunos ORDER BY nome").fetchall()
            return [{"id": r[0], "nome": r[1], "email": r[2], "numero_sorte": r[3]} for r in rows]
    
    def get_status_sessao(self) -> Dict:
        """Status da sessão atual"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT ativa, sessao_id, sorteios_count FROM sessao WHERE id = 1").fetchone()
            return {
                "ativa": bool(row[0]) if row else False,
                "sessao_id": row[1] if row else None,
                "sorteios_count": row[2] if row else 0
            }
    
    def iniciar_sessao(self) -> str:
        """Inicia nova sessão"""
        sessao_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""UPDATE sessao SET ativa = TRUE, sessao_id = ?, sorteios_count = 0, 
                           created_at = CURRENT_TIMESTAMP, ended_at = NULL WHERE id = 1""", (sessao_id,))
        return sessao_id
    
    def sortear(self) -> Tuple[bool, Dict]:
        """Realiza sorteio"""
        status = self.get_status_sessao()
        
        if not status["ativa"] or status["sorteios_count"] >= 3:
            return False, {}
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Números já sorteados
            sorteados = [row[0] for row in cursor.execute(
                "SELECT numero_sorte FROM sorteios WHERE sessao_id = ?", 
                (status["sessao_id"],)
            ).fetchall()]
            
            # Alunos disponíveis
            placeholders = ",".join("?" * len(sorteados)) if sorteados else "0"
            query = f"SELECT id, nome, numero_sorte FROM alunos WHERE numero_sorte NOT IN ({placeholders}) ORDER BY RANDOM() LIMIT 1"
            
            vencedor = cursor.execute(query, sorteados).fetchone()
            if not vencedor:
                return False, {}
            
            # Registrar sorteio
            posicao = status["sorteios_count"] + 1
            cursor.execute("INSERT INTO sorteios (sessao_id, aluno_id, numero_sorte, posicao) VALUES (?, ?, ?, ?)",
                         (status["sessao_id"], vencedor[0], vencedor[2], posicao))
            
            # Atualizar contador
            cursor.execute("UPDATE sessao SET sorteios_count = sorteios_count + 1 WHERE id = 1")
            
            return True, {"id": vencedor[0], "nome": vencedor[1], "numero_sorte": vencedor[2], "posicao": posicao}
    
    def encerrar_sessao(self) -> List[Dict]:
        """Encerra sessão e retorna vencedores"""
        status = self.get_status_sessao()
        if not status["ativa"]:
            return []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Buscar vencedores
            vencedores = cursor.execute("""
                SELECT s.posicao, a.nome, s.numero_sorte
                FROM sorteios s JOIN alunos a ON s.aluno_id = a.id
                WHERE s.sessao_id = ? ORDER BY s.posicao
            """, (status["sessao_id"],)).fetchall()
            
            # Encerrar sessão
            cursor.execute("UPDATE sessao SET ativa = FALSE, ended_at = CURRENT_TIMESTAMP WHERE id = 1")
            
            return [{"posicao": r[0], "nome": r[1], "numero_sorte": r[2]} for r in vencedores]
    
    def get_vencedores_sessao_atual(self) -> List[Dict]:
        """Vencedores da sessão atual"""
        status = self.get_status_sessao()
        if not status["sessao_id"]:
            return []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT s.posicao, a.nome, s.numero_sorte
                FROM sorteios s JOIN alunos a ON s.aluno_id = a.id
                WHERE s.sessao_id = ? ORDER BY s.posicao
            """, (status["sessao_id"],)).fetchall()
            
            return [{"posicao": r[0], "nome": r[1], "numero_sorte": r[2]} for r in rows]

# Sistema global
@st.cache_resource
def get_sistema():
    return SorteioSystem()

sistema = get_sistema()

def sidebar_alunos():
    """Sidebar com lista de alunos"""
    with st.sidebar:
        st.header("👥 Cadastrados")
        alunos = sistema.get_alunos()
        
        if alunos:
            st.markdown(f"**Total: {len(alunos)} pessoas**")
            for aluno in alunos:
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
    """Área de cadastro"""
    st.header("📋 Cadastro")
    
    with st.form("cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome Completo *", placeholder="Digite seu nome completo")
        with col2:
            email = st.text_input("Email *", placeholder="seu.email@exemplo.com")
        
        if st.form_submit_button("🎯 Cadastrar e Receber Número da Sorte", use_container_width=True):
            if not nome or not email:
                st.error("Preencha todos os campos!")
            elif "@" not in email:
                st.error("Email inválido!")
            else:
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
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

def area_admin():
    """Painel administrativo"""
    st.header("🎯 Painel Administrativo")
    
    # Autenticação simples
    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False
    
    if not st.session_state.admin_logged:
        senha = st.text_input("Senha:", type="password")
        if st.button("Entrar"):
            if senha == "admin123":
                st.session_state.admin_logged = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
        return
    
    # Interface admin
    status = sistema.get_status_sessao()
    
    st.markdown(f"""
    <div class="admin-panel">
        <h3>Status da Sessão</h3>
        <p>Status: <span class="status-badge status-{'active' if status['ativa'] else 'inactive'}">
            {'🟢 ATIVA' if status['ativa'] else '🔴 INATIVA'}
        </span></p>
        <p>Sorteios realizados: <strong>{status['sorteios_count']}/3</strong></p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🚀 Iniciar Nova Sessão", disabled=status['ativa'], use_container_width=True):
            sessao_id = sistema.iniciar_sessao()
            st.success(f"Nova sessão iniciada! ID: {sessao_id}")
            st.rerun()
    
    with col2:
        if st.button("🎲 SORTEAR", disabled=not status['ativa'] or status['sorteios_count'] >= 3, use_container_width=True):
            sucesso, vencedor = sistema.sortear()
            if sucesso:
                st.session_state.ultimo_vencedor = vencedor
                st.session_state.mostrar_vencedor = True
                st.rerun()
            else:
                st.error("Não foi possível sortear!")
    
    with col3:
        if st.button("🏁 Encerrar Sessão", disabled=not status['ativa'], use_container_width=True):
            vencedores = sistema.encerrar_sessao()
            st.session_state.vencedores_finais = vencedores
            st.session_state.mostrar_podium = True
            st.session_state.mostrar_vencedor = False
            st.rerun()

def exibir_vencedor():
    """Exibe vencedor atual"""
    vencedor = st.session_state.ultimo_vencedor
    
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
        if st.button("✅ Continuar Sorteio", use_container_width=True):
            st.session_state.mostrar_vencedor = False
            st.rerun()
    
    with col2:
        if st.button("🏁 Encerrar e Ver Pódio", use_container_width=True):
            vencedores = sistema.encerrar_sessao()
            st.session_state.vencedores_finais = vencedores
            st.session_state.mostrar_podium = True
            st.session_state.mostrar_vencedor = False
            st.rerun()

def exibir_podium():
    """Exibe pódio final"""
    st.header("🏆 PÓDIO FINAL")
    
    vencedores = st.session_state.vencedores_finais
    
    # Exibir vencedores
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
            # Limpar estados
            for key in ['mostrar_podium', 'vencedores_finais', 'ultimo_vencedor', 'mostrar_vencedor']:
                if key in st.session_state:
                    del st.session_state[key]
            
            sessao_id = sistema.iniciar_sessao()
            st.success(f"Nova sessão iniciada! ID: {sessao_id}")
            time.sleep(1)
            st.rerun()
    
    with col2:
        if st.button("🎊 Finalizar Apresentação", use_container_width=True):
            # Limpar estados
            for key in ['mostrar_podium', 'vencedores_finais', 'ultimo_vencedor', 'mostrar_vencedor']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

def area_resultados():
    """Área de resultados"""
    st.header("📊 Resultados da Sessão Atual")
    
    vencedores = sistema.get_vencedores_sessao_atual()
    
    if vencedores:
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
    else:
        st.info("Nenhum sorteio realizado ainda.")

def main():
    """Função principal"""
    st.title("🎲 Sorteio Eletrônico")
    st.markdown("---")
    
    # Sidebar
    sidebar_alunos()
    
    # Controle de fluxo principal
    if st.session_state.get('mostrar_vencedor') and st.session_state.get('ultimo_vencedor'):
        exibir_vencedor()
        return
    
    if st.session_state.get('mostrar_podium') and st.session_state.get('vencedores_finais'):
        exibir_podium()
        return
    
    # Menu normal
    menu = st.radio(
        "Escolha uma opção:",
        ["👤 Cadastro", "🎯 Administração", "📊 Resultados"],
        horizontal=True
    )
    
    if menu == "👤 Cadastro":
        area_cadastro()
    elif menu == "🎯 Administração":
        area_admin()
    else:
        area_resultados()

if __name__ == "__main__":
    main()

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