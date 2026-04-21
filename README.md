# TechAssist - Site de Assistência Técnica

Site moderno e tecnológico para assistência técnica de eletrodomésticos e celulares, desenvolvido em Python com Flask.

## 🚀 Características

- **Design Moderno**: Interface limpa e tecnológica com gradientes e animações
- **Responsivo**: Totalmente adaptável para dispositivos móveis, tablets e desktops
- **Interativo**: Animações suaves e efeitos visuais modernos
- **Funcional**: Sistema de contato e agendamento de serviços
- **Tecnológico**: Visual futurista com partículas e efeitos de glassmorphism

## 📋 Requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)

## 🛠️ Instalação

1. Clone ou baixe este repositório

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

## ▶️ Como Executar

1. Execute o aplicativo Flask:
```bash
python app.py
```

2. Abra seu navegador e acesse:
```
http://localhost:5000
```

## 📁 Estrutura do Projeto

```
Site Tecnica/
├── app.py                 # Aplicação Flask principal
├── requirements.txt       # Dependências do projeto
├── README.md             # Este arquivo
├── data/
│   └── services.json     # Armazenamento de dados (serviços e contatos)
├── templates/
│   ├── base.html         # Template base
│   ├── index.html        # Página inicial
│   ├── sobre.html        # Página sobre
│   ├── servicos.html     # Página de serviços
│   └── contato.html      # Página de contato
└── static/
    ├── css/
    │   └── style.css     # Estilos principais
    └── js/
        ├── main.js       # JavaScript principal
        └── particles.js  # Efeito de partículas
```

## 🎨 Funcionalidades

### Páginas Disponíveis

- **Home** (`/`): Página inicial com hero section, estatísticas e preview de serviços
- **Sobre** (`/sobre`): Informações sobre a empresa e valores
- **Serviços** (`/servicos`): Lista detalhada de todos os serviços oferecidos
- **Contato** (`/contato`): Formulário de contato e informações de contato

### Recursos

- Sistema de mensagens flash para feedback ao usuário
- Formulário de contato funcional que salva dados em JSON
- Design responsivo com menu mobile
- Animações suaves e efeitos visuais
- Gradientes modernos e efeito glassmorphism

## 🔧 Personalização

### Alterar Cores

Edite as variáveis CSS no arquivo `static/css/style.css`:

```css
:root {
    --primary-color: #6366f1;
    --secondary-color: #8b5cf6;
    --accent-color: #ec4899;
    /* ... */
}
```

### Alterar Informações de Contato

Edite os templates em `templates/` para alterar telefones, endereços e outras informações.

### Adicionar Mais Serviços

Edite o arquivo `templates/servicos.html` para adicionar novos serviços.

## 🚀 Deploy

O projeto está pronto para deploy em várias plataformas. Consulte o arquivo `DEPLOY.md` para instruções detalhadas de deploy em:

- **Railway** (Recomendado - Grátis)
- **Render**
- **Heroku**
- **PythonAnywhere**

### Arquivos de Deploy

- `Procfile`: Configuração para Heroku/Railway
- `runtime.txt`: Versão do Python
- `.env.example`: Exemplo de variáveis de ambiente
- `DEPLOY.md`: Guia completo de deploy

### Variáveis de Ambiente

Configure as seguintes variáveis de ambiente em produção:

- `SECRET_KEY`: Chave secreta para sessões (obrigatória)
- `FLASK_ENV`: `production` para produção
- `PORT`: Porta do servidor (padrão: 5000)

## 📝 Notas

- Os dados são salvos em arquivos JSON na pasta `data/`
- A chave secreta deve ser alterada em produção (use variável de ambiente `SECRET_KEY`)
- Para produção, o projeto usa Gunicorn (incluído no `requirements.txt`)

## 🌐 Tecnologias Utilizadas

- **Backend**: Python, Flask
- **Frontend**: HTML5, CSS3, JavaScript
- **Fontes**: Google Fonts (Inter)
- **Ícones**: Font Awesome

## 📄 Licença

Este projeto é fornecido como está, para uso pessoal e comercial.

## 👨‍💻 Desenvolvimento

Para desenvolvimento, o Flask está configurado com `debug=True`. Em produção, desative o modo debug e use um servidor WSGI adequado.

---

Desenvolvido com ❤️ usando Python e Flask

