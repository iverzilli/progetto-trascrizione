# Usa un'immagine Python ufficiale come base
FROM python:3.9-slim

# Imposta la directory di lavoro nell'immagine
WORKDIR /app

# Installa ffmpeg (per la manipolazione audio) e git (per installare whisper da repo se necessario)
# libgomp1 è una dipendenza di PyTorch (usato da Whisper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copia il file delle dipendenze Python
COPY transcribe_app/requirements.txt .

# Installa le dipendenze Python
#openai-whisper richiede Rust per la tokenizzazione, quindi build-essential e cargo
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN pip install --no-cache-dir -r requirements.txt

# Scarica il modello Whisper durante la build per risparmiare tempo all'avvio
# Puoi scegliere tra: tiny, base, small, medium, large
# Per CPU i3 e italiano, 'small' o 'base' sono un buon compromesso.
# Se i file sono solo in italiano, puoi usare 'small.it' o 'base.it' se disponibili
# o un modello multilingua specificando la lingua durante la trascrizione.
# Usiamo 'small' come default, configurabile via variabile d'ambiente.
ARG WHISPER_MODEL_ARG=small
ENV WHISPER_MODEL=${WHISPER_MODEL_ARG}
RUN python -c "import whisper; print(f'Downloading Whisper model: {whisper.मामले.get_model_path(\"${WHISPER_MODEL}\")}')"

# Copia il resto dell'applicazione nella directory di lavoro
COPY transcribe_app/ /app/transcribe_app/

# Definisce il punto di ingresso per l'esecuzione dello script
# Lo script verrà effettivamente chiamato da docker-compose run
# CMD ["python", "/app/transcribe_app/transcribe.py"]
# Non mettiamo un CMD qui perché vogliamo passare argomenti dinamicamente con docker-compose run