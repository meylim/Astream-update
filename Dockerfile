# Utilisation d'une image Python légère
FROM python:3.11-slim

# Empêcher Python de générer des fichiers .pyc et activer le logging immédiat
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dossier de travail
WORKDIR /app

# Installation des dépendances système nécessaires pour lxml et curl-cffi
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 1. Copier les fichiers de configuration en premier
COPY pyproject.toml .
COPY README.md .

# 2. Copier le code source MAINTENANT pour que pip puisse construire le package
# On copie tout le dossier astream/
COPY astream/ ./astream/

# 3. Installation du projet et de ses dépendances
RUN pip install --no-cache-dir .

# Exposition du port
EXPOSE 8000

# Commande de lancement (on utilise le module astream.main)
CMD ["python", "-m", "astream.main"]
