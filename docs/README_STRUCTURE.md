# Structure du Projet

Ce projet a été réorganisé pour séparer clairement les différentes parties :

## 📁 Structure

```
├── backend/          # Code backend (API, services, logique métier)
│   ├── admin/       # Interface d'administration
│   ├── ai/          # Modules IA et LLM
│   ├── config/      # Configuration
│   ├── graph/       # Graphes de workflow
│   ├── models/      # Modèles de données
│   ├── nodes/       # Nœuds de workflow
│   ├── services/    # Services métier
│   ├── tools/       # Outils backend
│   ├── utils/       # Utilitaires
│   ├── tests/       # Tests
│   └── main.py      # Point d'entrée principal
│
├── frontend/         # Code frontend
│   └── ai-agent-front/  # Application React
│
├── artifacts/        # Scripts, migrations, et fichiers annexes
│   ├── scripts/     # Scripts Python utilitaires
│   ├── shell/       # Scripts shell
│   ├── data/        # Données et fichiers SQL
│   ├── migrations/  # Migrations de base de données
│   ├── sql/         # Fichiers SQL
│   ├── docker/      # Fichiers Docker
│   ├── backups/     # Sauvegardes
│   └── logs/        # Fichiers de logs
│
├── .gitignore       # Fichiers à ignorer par Git
└── README.md        # Documentation principale
