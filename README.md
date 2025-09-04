# 🎲 Sorteio Eletrônico

Um web app interativo em **Python + Streamlit** para realizar sorteios eletrônicos.  
Cada pessoa se cadastra com **nome completo e email**, recebe um **número da sorte único** e acompanha em tempo real a lista de inscritos.  
O administrador tem acesso a um **painel administrativo**, onde pode iniciar sessões, sortear vencedores e exibir o pódio final.

---

## ✨ Funcionalidades
- Cadastro de pessoas com número da sorte único.
- Validação básica de email e nome.
- Exibição em tempo real da lista de participantes (na barra lateral).
- Painel administrativo protegido por senha.
- Sorteios com até **3 vencedores por sessão**.
- Exibição animada do vencedor e pódio final 🥇🥈🥉.
- Banco de dados **SQLite** integrado.
- Interface personalizada com **CSS customizado**.

---

## 🚀 Como rodar localmente

### 1. Clone este repositório
```bash
git clone https://github.com/aryribeiro/sorteio-eletronico.git
cd sorteio-eletronico

2. Crie e ative um ambiente virtual

python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

3. Instale as dependências

pip install -r requirements.txt

4. Execute o app

streamlit run app.py

O app ficará disponível em:
👉 http://localhost:8501
☁️ Deploy no Streamlit Cloud

    Faça push do repositório no GitHub.

    Vá até https://share.streamlit.io

    .

    Crie um novo app, aponte para app.py.

    O banco de dados (sorteio.db) será criado automaticamente no primeiro uso.

🔐 Painel Administrativo

    O painel administrativo é acessível via aba "🎯 Administração".

    Senha padrão: admin123 (recomenda-se alterar usando st.secrets).

📦 Estrutura de Arquivos

📂 sorteio-eletronico/
 ├── app.py              # Código principal do Streamlit
 ├── requirements.txt    # Dependências do projeto
 ├── README.md           # Documentação
 └── sorteio.db          # Banco SQLite (gerado automaticamente)

⚠️ Observações

    O banco de dados SQLite ainda não foi projetado para uso massivo em escrita concorrente.
    Para turmas grandes (>300 pessoas simultâneas), considere migrar para PostgreSQL ou MySQL.

    O app foi testado em computadores. A experiência em dispositivos móveis pode variar.

👨‍💻 Autor

Ary Ribeiro
📧 aryribeiro@gmail.com
