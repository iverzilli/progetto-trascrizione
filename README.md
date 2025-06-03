# Applicazione di Trascrizione Audio con Docker e Whisper

Questa applicazione utilizza Docker e OpenAI Whisper per trascrivere file audio (MP3) in testo. È progettata per gestire file lunghi e sessioni di lavoro limitate, permettendo di interrompere e riprendere il processo.

## Prerequisiti

*   Docker installato ([https://www.docker.com/get-started](https://www.docker.com/get-started))
*   Docker Compose installato (solitamente incluso con Docker Desktop)

## Struttura del Progetto

```
progetto-trascrizione/
├── docker-compose.yml      # Configurazione dei servizi Docker
├── Dockerfile              # Istruzioni per costruire l'immagine Docker
├── transcribe_app/         # Codice sorgente dell'applicazione
│   ├── transcribe.py     # Script Python principale
│   └── requirements.txt  # Dipendenze Python
├── audio_input/            # Metti qui i tuoi file MP3 da trascrivere
│   └── esempio.mp3
├── transcriptions_output/  # Le trascrizioni finali appariranno qui
└── persistent_data/        # Dati di lavoro (checkpoint, WAV, segmenti) - NON TOCCARE MANUALMENTE
└── README.md               # Questa guida
```

## Configurazione Iniziale

1.  **Clona o scarica questo progetto.**
2.  **Crea le directory necessarie** se non esistono già, allo stesso livello di `docker-compose.yml`:
    ```bash
    mkdir audio_input
    mkdir transcriptions_output
    mkdir persistent_data
    ```
3.  **Permessi per `persistent_data`**: Assicurati che Docker abbia i permessi di scrittura per la directory `persistent_data` sull'host. Su Linux, potresti aver bisogno di impostare i permessi corretti o gestire l'UID/GID se ci sono problemi di accesso. Un modo semplice è:
    ```bash
    # Esegui questo comando nella directory principale del progetto
    # (potrebbe richiedere sudo a seconda della configurazione di Docker)
    mkdir -p persistent_data
   chmod -R 777 persistent_data  
    ```
    Questo dà permessi completi. Per ambienti di produzione, considera una gestione dei permessi più restrittiva.

4.  **Posiziona i file audio**: Copia i tuoi file `.mp3` nella directory `audio_input/`.

## Costruzione dell'Immagine Docker

La prima volta, o se modifichi `Dockerfile` o `requirements.txt`, devi costruire l'immagine Docker. Questo scaricherà anche il modello Whisper specificato (`small` di default).
```bash
docker-compose build
```
Questo comando utilizza `WHISPER_MODEL_ARG` dal `docker-compose.yml` (default: `small`). Se vuoi usare un modello diverso (es. `base` o `medium`) per la build, modifica `WHISPER_MODEL_ARG` nel `docker-compose.yml` prima di eseguire `build`.

## Esecuzione della Trascrizione

Per trascrivere un file audio, esegui il seguente comando dalla directory principale del progetto, sostituendo `nome_tuo_file.mp3` con il nome effettivo del tuo file:

```bash
docker-compose run --rm transcriber python /app/transcribe_app/transcribe.py /app/audio_input/nome_tuo_file.mp3 /app/transcriptions_output/nome_tuo_file.txt
```

*   `--rm`: Rimuove il container una volta terminata l'esecuzione. Utile per non accumulare container fermi.
*   Il primo argomento (`/app/audio_input/...`) è il percorso del file audio *all'interno del container*.
*   Il secondo argomento (`/app/transcriptions_output/...`) è il percorso del file di testo di output *all'interno del container*.

**Esempio:**
Se hai un file `audio_input/meeting_01.mp3`, il comando sarà:
```bash
docker-compose run --rm transcriber python /app/transcribe_app/transcribe.py /app/audio_input/meeting_01.mp3 /app/transcriptions_output/meeting_01.txt
```

### Ripresa da un'interruzione

Se il processo viene interrotto (manualmente con `Ctrl+C`, o perché il tempo massimo della sessione è scaduto, o per un riavvio del PC), puoi semplicemente **rieseguire lo stesso identico comando**. Lo script rileverà i progressi salvati nella directory `persistent_data/nome_tuo_file/` e riprenderà da dove si era interrotto.

### Limite di Tempo della Sessione

Lo script è configurato per terminare automaticamente dopo un certo periodo (default: 12 ore, configurabile tramite `MAX_SESSION_DURATION_SECONDS` nel `docker-compose.yml`). Se termina per questo motivo, salverà i progressi. Riesegui il comando per continuare.

## Variabili d'Ambiente Configurabili

Puoi modificare queste variabili nel file `docker-compose.yml` (sezione `environment` del servizio `transcriber`):

*   `WHISPER_MODEL`: Modello Whisper da usare (es. `tiny`, `base`, `small`, `medium`, `large`). Default: `small`. Modelli più grandi sono più accurati ma più lenti e richiedono più RAM/VRAM. Per CPU i3, `small` o `base` sono raccomandati.
*   `AUDIO_LANGUAGE`: Codice ISO 639-1 della lingua (es. `it` per italiano, `en` per inglese). Se omesso o lasciato vuoto, Whisper tenterà di rilevare automaticamente la lingua. Default: `it`.
*   `MAX_SESSION_DURATION_SECONDS`: Durata massima in secondi di una singola esecuzione prima che lo script si interrompa automaticamente salvando i progressi. Default: `43200` (12 ore).
*   `CHUNK_DURATION_MS`: Durata di ogni segmento audio in millisecondi. Segmenti più corti significano checkpoint più frequenti ma più overhead. Default: `600000` (10 minuti).

Se modifichi queste variabili, potresti non aver bisogno di fare `docker-compose build` a meno che non cambi `WHISPER_MODEL_ARG` (che influenza la build dell'immagine). Per le altre variabili d'ambiente, `docker-compose run` le applicherà.

## Output e Dati Persistenti

*   **Trascrizioni Finali**: Vengono salvate in `transcriptions_output/`.
*   **Dati di Lavoro**: La directory `persistent_data/` contiene sottodirectory per ogni file audio processato. Queste contengono il file WAV convertito, i segmenti audio, le trascrizioni dei segmenti e un file `progress.json`. **Non modificare o eliminare manualmente i contenuti di `persistent_data/` a meno che tu non voglia resettare completamente il progresso per un file specifico.** Il file `progress.json` viene rimosso automaticamente solo quando la trascrizione di un file è completata con successo al 100%.

## Risoluzione dei Problemi

*   **Permessi**: Se Docker riporta errori di permesso durante la scrittura su volumi (`persistent_data`, `transcriptions_output`), assicurati che l'utente che esegue Docker abbia i permessi di scrittura su quelle directory sull'host. Vedi la sezione "Configurazione Iniziale".
*   **ffmpeg non trovato / Errore di conversione**: Assicurati che `ffmpeg` sia installato correttamente nell'immagine Docker (controlla il `Dockerfile`).
*   **Modello Whisper non scaricato**: Il modello dovrebbe essere scaricato al primo avvio se non presente nella cache (`~/.cache/whisper` nel container, mappato al volume `whisper_cache`). Controlla la connessione internet del container se necessario.
*   **Poco Spazio su Disco**: I file WAV convertiti e i segmenti possono occupare spazio. Assicurati di avere abbastanza spazio disco, specialmente in `persistent_data/`.
*   **Rust / Cargo non trovato durante `pip install openai-whisper`**: Il `Dockerfile` include i passaggi per installare Rust e Cargo. Se fallisce, potrebbero esserci problemi di rete o incompatibilità con l'immagine base.

## Ottimizzazioni e Prestazioni

*   L'hardware (i3 11th gen, 16GB RAM, scheda integrata) significa che la trascrizione sarà principalmente limitata dalla CPU.
*   Il modello `small` di Whisper è un buon compromesso. `base` è più veloce ma meno accurato. `medium` è più accurato ma significativamente più lento su CPU.
*   La conversione in WAV e la segmentazione avvengono una sola volta per file.
*   La RAM da 16GB dovrebbe essere sufficiente per i modelli `small` o `medium` (quest'ultimo al limite).

## Sviluppi Futuri (Frontend)

Questa architettura a container con volumi condivisi è una buona base per un futuro frontend:
1.  Aggiungere un nuovo servizio al `docker-compose.yml` (es. un server web Python/Flask o Node.js).
2.  Questo servizio backend potrebbe:
    *   Esporre API per caricare file (salvandoli in `audio_input/`).
    *   Elencare i file in `audio_input/`.
    *   Avviare il processo di trascrizione (eseguendo un comando `docker exec` nel container `transcriber` o orchestrando `docker-compose run`).
    *   Controllare lo stato leggendo i file `progress.json` da `persistent_data/`.
    *   Servire le trascrizioni finali da `transcriptions_output/`.
3.  Un frontend (React, Vue, HTML semplice) comunicherebbe con queste API.
```
**Test e Considerazioni Finali:**

1.  **Permessi su Linux**: Se usi Linux, potresti dover gestire i permessi per i volumi Docker, specialmente `persistent_data`. L'utente dentro il container (root di default) deve poter scrivere nelle directory mappate. `chmod 777` è una soluzione rapida ma non ideale per produzione. Un'alternativa è specificare `user: "${UID}:${GID}"` nel `docker-compose.yml` per il servizio `transcriber`.
2.  **Download del Modello Whisper**: Il modello `small` (o quello scelto) verrà scaricato la prima volta che `whisper.load_model()` viene chiamato e messo in cache in `~/.cache/whisper` dentro il container. Grazie al volume nominato `whisper_cache`, questo download avverrà una sola volta anche se ricrei i container (purché il volume persista). La riga `RUN python -c "import whisper; whisper.load_model('${WHISPER_MODEL}')"` nel Dockerfile tenta di scaricarlo durante la build.
3.  **Performance**: Con un i3, la trascrizione di 1 ora e 20 minuti (4800 secondi) con il modello `small` potrebbe richiedere diverse ore. Se il rapporto tempo reale / tempo di trascrizione fosse 1:3 (cioè 3 secondi per trascrivere 1 secondo di audio), ci vorrebbero `4800 * 3 = 14400` secondi, ovvero 4 ore. Se fosse 1:5, sarebbero circa 6.6 ore. Questo rientra nel limite di mezza giornata per file, ma la funzionalità di checkpointing è essenziale.
4.  **Pulizia `persistent_data`**: Lo script attuale rimuove solo il file `progress.json` al completamento. I chunk audio/testo e il WAV convertito rimangono in `persistent_data/nome_file/`. Questo è utile per il debug. Se vuoi una pulizia più aggressiva, puoi decommentare e adattare le linee di `os.remove` e `os.rmdir` nella sezione di pulizia dello script `transcribe.py`.
