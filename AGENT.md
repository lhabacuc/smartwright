
# 🧠 MASTER PROMPT — Construir a Smartwright (Adaptive Web Automation Engine)

## 🎯 Objetivo Geral

Crie uma biblioteca chamada **Smartwright** que transforma automação baseada em seletores frágeis em **automação baseada em intenção**.

O usuário **NUNCA fornece seletores**.

Ele escreve:

```python
await smart.click("login_button")
```

E a biblioteca deve:

1. Entender a intenção.
2. Descobrir como executar.
3. Adaptar se o site mudar.
4. Preferir API ao invés de UI sempre que possível.
5. Aprender continuamente com execuções anteriores.

---

# 🏗️ Arquitetura Obrigatória

Estruture o projeto assim:

```
smartwright/
│
├── intent/                 # mapeia intenção humana → significado
├── resolver/               # encontra elementos dinamicamente
├── healing/                # auto-repair quando falha
├── fingerprint/            # detecta mudanças estruturais
├── network_learning/       # descobre APIs automaticamente
│
├── semantic_finder/        # busca baseada em significado (não DOM)
├── api_executor/           # executa via HTTP quando possível
├── ai_recovery/            # fallback inteligente com IA
│
└── core/
```

---

# 🧩 Conceito Central: Intent > Selector

O sistema deve trabalhar com um dicionário semântico:

```python
INTENTS = {
    "login_button": ["Entrar", "Login", "Sign in"],
    "email_field": ["Email", "E-mail", "Username"],
    "password_field": ["Senha", "Password"],
}
```

Essas labels são **pistas humanas**, não seletores técnicos.

---

# 🔎 CAMADA 1 — Smart Resolver

Implemente um resolvedor que tente múltiplas estratégias automaticamente:

Ordem de tentativa:

1. `get_by_role`
2. `get_by_label`
3. `get_by_text`
4. heurística estrutural
5. busca semântica

Nunca falhar na primeira tentativa.

---

# 🧠 CAMADA 2 — Semantic Finder

Quando não houver seletor confiável, o sistema deve buscar por **conceito**.

Exemplo de mapa semântico:

```python
SEMANTIC_MAP = {
    "chat_list_msg": {
        "roles": ["listitem", "row", "article"],
        "patterns": ["message", "chat", "conversation"]
    }
}
```

O finder deve iterar candidatos e validar por significado textual.

Isso evita quebrar quando o frontend muda.

---

# 🌐 CAMADA 3 — Network Learning (API Discovery)

Durante qualquer navegação, o sistema deve observar tráfego:

```python
page.on("request", capture)
page.on("response", analyze)
```

Detectar automaticamente padrões como:

```
POST /api/messages/list
Authorization: Bearer ...
```

E salvar:

```python
API_KNOWLEDGE = {
    "chat_list_msg": {
        "endpoint": "...",
        "method": "POST",
        "payload_template": {...}
    }
}
```

---

# ⚡ CAMADA 4 — API Executor (Modo Preferencial)

Se existir conhecimento de API para uma intenção:

🚫 NÃO usar browser
✅ Executar direto via HTTP.

Decision rule:

```
Se API conhecida → usar API
Senão → usar DOM
```

---

# 🩹 CAMADA 5 — Healing Layer

Se uma ação falhar:

1. Recarregar estado
2. Reavaliar estratégias
3. Reexecutar resolver
4. Atualizar score de sucesso

Nada de retry cego.

Retry deve ser **adaptativo**.

---

# 🧬 CAMADA 6 — DOM Fingerprinting

Capture hash estrutural da página:

```python
hash = md5(dom)
```

Se mudar:

→ ativar modo adaptativo
→ ignorar cache antigo
→ reaprender seletores

---

# 🤖 CAMADA 7 — AI Recovery (Fallback Final)

Somente quando tudo falhar:

1. Extrair trechos relevantes do DOM.
2. Enviar para IA com contexto da intenção.
3. Receber sugestão estratégica.
4. Registrar nova estratégia permanentemente.

Nunca enviar página inteira — apenas snippets relevantes.

---

# 🧠 Decision Engine (Coração do Sistema)

Toda ação passa por:

```python
if api_knowledge.exists(intent):
    use_api()

elif semantic_match_possible:
    use_semantic_search()

elif selector_strategy_works:
    use_dom()

else:
    trigger_ai_recovery()
```

---

# 📚 Aprendizado Contínuo (Obrigatório)

O sistema deve registrar:

* qual estratégia funcionou
* tempo de execução
* taxa de sucesso
* mudanças de layout
* endpoints descobertos

Criando um histórico como:

```
login_button:
  strategy=get_by_role
  success_rate=0.93
```

Execuções futuras priorizam estratégias com maior score.

---

# Experiência Final do Usuário (North Star)

O usuário da lib só escreve:

```python
await smart.goto(url)
await smart.fill("email_field", email)
await smart.fill("password_field", password)
await smart.click("login_button")
```

Sem:

❌ XPath
❌ CSS selector
❌ Esperas manuais
❌ Debug de DOM

---

#  Princípios que NÃO podem ser violados

A implementação deve sempre seguir:

1. **Intent-Driven** — nunca selector-driven.
2. **Self-Healing** — falhar = aprender.
3. **API-First** — UI é fallback.
4. **Structure-Aware** — detectar mudanças reais.
5. **Continuously Learning** — cada execução melhora a próxima.
6. **Minimal Human Input** — usuário descreve o que quer, não como fazer.

---

#  Ordem Recomendada de Implementação

Construa na sequência:

 `network_learning` (maior ganho imediato)
 `semantic_finder` (robustez real)
 `resolver` adaptativo
 `api_executor`
 `healing`
 `fingerprint`
 `ai_recovery` (último — é caro)

---

