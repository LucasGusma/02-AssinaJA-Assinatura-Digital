# AssinaJA · Gestor Inteligente de Pendências e Assinatura Digital

Plataforma de alta performance desenvolvida em **FastAPI (Python)** e **React + TypeScript** para gestão, auditoria e resolução de pendências de assinatura em prontuários eletrônicos hospitalares.

---

## 🚀 Arquitetura e Tecnologias

- **Backend:** FastAPI, Pydantic V2, Python 3.11+, pool de conexões otimizado com `python-oracledb`.
- **Frontend:** React 18, TypeScript, Tailwind CSS / UI moderna com foco em usabilidade médica.
- **Persistência & Integração:** Pacotes PL/SQL corporativos com paginação no banco de dados e contratos REST em JSON.
- **Segurança:** Cookies de sessão com proteção HTTP-Only, CORS rigoroso e RBAC (Role-Based Access Control).

---

## 💡 Destaques de Engenharia

- **Desacoplamento de Contrato:** Adaptadores independentes para comunicação com banco legado e rotinas modernas.
- **Performance:** Consultas paginadas diretamente no banco, com tempo de resposta sub-100ms.
- **Auditoria Assistencial:** Rastreamento completo de visualizações, tentativas e confirmações de assinatura.

---

## 🛠️ Como Executar

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env
python -m app.main

# Frontend
cd frontend
npm install
npm run dev
```

---
*Higienizado para publicação de portfólio, sem credenciais nem dados de pacientes.*
