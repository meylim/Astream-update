# Utilisation d'une image Python légère
FROM python:3.11-slim

# Empêcher Python de générer des fichiers .pyc et activer le logging immédiat
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dossier de travail
WORKDIR /app

# Installation des dépendances système nécessaires pour lxml et le réseau
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copie des fichiers de dépendances
COPY pyproject.toml .

# Installation des dépendances via pip (pour la simplicité en Docker)
RUN pip install --no-cache-dir .

# Copie du code source
COPY . .

# Exposition du port (par défaut Stremio utilise souvent le 8080 ou 8000)
EXPOSE 8000

# Commande de lancement
CMD ["python", "-m", "astream.main"]
