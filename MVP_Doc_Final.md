**Documento di Progetto: Sistema di Trascrizione Audio Automatizzato**

**Versione:** 1.0
**Data:** 03 Giungo 2025
**Autore:** AI Assistant (basato su input utente)
**Destinatario:** Team di Sviluppo / AI per lo sviluppo assistito

**1. Sommario Esecutivo e Obiettivi**

Questo documento descrive l'architettura, le funzionalità e la roadmap evolutiva di un sistema di trascrizione audio. L'obiettivo iniziale (MVP) è fornire una soluzione robusta e gratuita per la trascrizione di file audio MP3 di lunga durata, operante localmente tramite Docker, con capacità di interruzione e ripresa. Le evoluzioni future mirano a migliorare l'usabilità attraverso un'interfaccia frontend, integrare funzionalità AI avanzate (come il riassunto) e garantire manutenibilità e scalabilità.

**Criticità Attuale:** L'utilizzo attuale è limitato a utenti tecnici familiari con la riga di comando Docker. La gestione manuale dei file e l'avvio dei processi non sono user-friendly per un pubblico più ampio.

**Obiettivo Strategico:** Evolvere da uno strumento CLI a una piattaforma web accessibile che automatizzi il workflow di trascrizione e analisi testuale per utenti non tecnici.

**2. Stato Attuale (MVP Baseline - CLI Docker-based)**

La soluzione corrente è un'applicazione Python containerizzata con Docker, che utilizza OpenAI Whisper per la trascrizione.

*   **Funzionalità Chiave MVP Attuale:**
    *   Trascrizione di file MP3 in testo.
    *   Supporto per file audio lunghi (gestiti tramite segmentazione interna).
    *   Meccanismo di checkpointing per interruzione e ripresa del processo di trascrizione (basato su file `progress.json` per ogni audio).
    *   Operatività locale e gratuita (escludendo i costi hardware e di energia).
    *   Configurazione tramite variabili d'ambiente Docker (modello Whisper, lingua, durata sessione, durata chunk).
    *   Input/Output tramite volumi Docker mappati (`audio_input`, `transcriptions_output`, `persistent_data`).
*   **Stack Tecnologico MVP Attuale:**
    *   Backend: Python, OpenAI Whisper, Pydub.
    *   Orchestrazione: Docker, Docker Compose.
    *   Sistema Operativo Host: Qualsiasi OS con supporto Docker.
*   **Limitazioni MVP Attuale:**
    *   Interfaccia utente: Solo CLI.
    *   Gestione file: Manuale (copia in `audio_input`).
    *   Feedback utente: Limitato ai log della console Docker.
    *   Nessuna gestione utenti o multi-tenancy.
    *   Scalabilità limitata alla singola istanza e alle risorse della macchina host.

**3. Evoluzione Proposta: Roadmap e Funzionalità**

**FASE 1: MVP Web Application - Interfaccia Utente e Gestione Base**

L'obiettivo di questa fase è rendere il sistema accessibile a utenti non tecnici tramite un'interfaccia web.

*   **3.1. Backend (API Service)**
    *   **Tecnologie Proposte:** Python (Flask/FastAPI) per leggerezza e integrazione con lo script di trascrizione esistente.
    *   **Funzionalità API:**
        *   `POST /api/upload`: Caricamento file audio. Il backend salva il file nel volume `audio_input`.
        *   `GET /api/transcriptions`: Elenco delle trascrizioni disponibili (e loro stato: in corso, completato, errore).
        *   `POST /api/transcriptions/{filename}/start`: Avvio del processo di trascrizione per un file specifico. Questo endpoint invocherà lo script `transcribe.py` (es. tramite `subprocess`, o meglio, gestendo una coda di task).
        *   `GET /api/transcriptions/{filename}/status`: Recupero dello stato di avanzamento di una trascrizione (leggendo il `progress.json` associato o un database).
        *   `GET /api/transcriptions/{filename}/download`: Download del file di testo della trascrizione.
        *   `DELETE /api/transcriptions/{filename}`: Eliminazione di un file audio e della sua trascrizione (e dati persistenti associati).
        *   `(Opzionale) POST /api/transcriptions/{filename}/cancel`: Tentativo di interrompere un processo di trascrizione in corso (potrebbe essere complesso da implementare in modo pulito con Whisper se non a livello di chunk).
    *   **Gestione dei Processi di Trascrizione:**
        *   Inizialmente, l'API potrebbe lanciare `docker-compose run ...` per ogni richiesta. Criticità: concorrenza, gestione risorse.
        *   **Miglioramento Critico:** Implementare una coda di task (es. Celery con Redis/RabbitMQ) per gestire le richieste di trascrizione in modo asincrono. Il servizio API accoda il task, un worker (che potrebbe essere lo stesso script `transcribe.py` adattato) lo preleva ed esegue. Questo permette di gestire più richieste e di non bloccare l'API.
    *   **Persistenza Stato:**
        *   Oltre a `progress.json`, considerare un piccolo database (es. SQLite inizialmente, poi PostgreSQL/MySQL) per metadati sui file, utenti (futuro), stato dei job.

*   **3.2. Frontend**
    *   **Tecnologie Proposte:** Framework JavaScript moderno (React, Vue.js, o Svelte) per un'esperienza utente reattiva. HTML/CSS/JS Vanilla per un MVP più snello se le risorse sono limitate.
    *   **Pagine/Componenti Chiave:**
        *   **Pagina di Upload:**
            *   Controllo per selezionare e caricare file MP3 (con validazione formato e dimensione).
            *   Barra di progresso per l'upload.
        *   **Dashboard Trascrizioni:**
            *   Elenco tabellare dei file audio caricati/processati.
            *   Colonne: Nome File, Data Upload, Stato (In Coda, In Elaborazione, Completato, Errore), Azioni.
            *   Indicatore di progresso per i task in elaborazione (polling dell'API di stato).
            *   Pulsanti Azione: "Avvia Trascrizione" (se non avviata automaticamente post-upload), "Visualizza/Scarica", "Elimina".
        *   **(Opzionale) Pagina Dettaglio Trascrizione:**
            *   Visualizzazione del testo trascritto.
            *   Player audio (HTML5) per riascoltare l'audio originale sincronizzato (sfida complessa).
    *   **Usabilità Frontend:**
        *   **Feedback Utente:** Notifiche chiare per upload riuscito, avvio task, completamento, errori.
        *   **Semplicità:** Interfaccia intuitiva, minimi passaggi per ottenere una trascrizione.
        *   **Responsive Design:** Utilizzabile su diverse dimensioni di schermo (almeno desktop e tablet).

*   **3.3. Docker Compose Aggiornato**
    *   Aggiungere un servizio per l'API backend (es. `api_server`).
    *   Aggiungere un servizio per il frontend (se servito staticamente da Nginx o se un'app Node.js).
    *   Eventualmente, un servizio per la coda di task (Redis/RabbitMQ) e per i worker Celery.
    *   Il servizio `transcriber` originale potrebbe diventare il "worker" che viene invocato dalla coda.

**FASE 2: Funzionalità Avanzate e Integrazione AI**

*   **3.4. Backend (Miglioramenti e Funzionalità AI)**
    *   **Gestione Utenti (se necessario):**
        *   Autenticazione e autorizzazione (es. JWT, OAuth).
        *   Isolamento dei dati per utente.
    *   **Riassunto Automatico:**
        *   Endpoint API: `POST /api/transcriptions/{filename}/summarize`
        *   Integrazione con modelli LLM (OpenAI GPT, modelli open source come Llama, Mistral eseguibili localmente o tramite API).
        *   Scelta del modello e gestione dei prompt per riassunti di qualità.
        *   **Criticità:** Il riassunto di testi lunghi può richiedere LLM potenti e/o tecniche di chunking del testo. Costi API o requisiti hardware per modelli locali.
    *   **Speaker Diarization (Identificazione Parlanti):**
        *   Integrazione di librerie/modelli per la diarizzazione (es. `pyannote.audio`, o funzionalità di WhisperX).
        *   Modifica dell'output per includere i tag dei parlanti (es. `[Speaker A]: ...`, `[Speaker B]: ...`).
        *   **Criticità:** Accuratezza variabile, configurazione complessa.
    *   **Esportazione Formati Multipli:**
        *   Supporto per SRT (sottotitoli), VTT, DOCX oltre al TXT.
    *   **Notifiche:**
        *   Email o notifiche web push al completamento di task lunghi.
    *   **Webhook:** Per integrare con sistemi esterni al completamento.

*   **3.5. Frontend (Miglioramenti e Funzionalità AI)**
    *   **Visualizzazione Riassunti:** Sezione dedicata per mostrare i riassunti generati.
    *   **Editor di Trascrizioni:**
        *   Interfaccia per correggere manualmente le trascrizioni.
        *   Sincronizzazione audio-testo per facilitare la correzione.
        *   Salvataggio delle modifiche.
    *   **Configurazione Parametri AI:**
        *   Opzioni per scegliere il tipo di riassunto (estrattivo, astrattivo, lunghezza).
        *   Opzioni per la diarizzazione.
    *   **Ricerca nel Testo Trascritto:** Funzionalità di ricerca full-text all'interno delle trascrizioni.

**4. Considerazioni Architetturali e Tecniche Cross-Cutting**

*   **4.1. Configurazione**
    *   Centralizzare la configurazione il più possibile (variabili d'ambiente, file `.env`).
    *   Documentare tutte le opzioni configurabili.
    *   Considerare un pannello di amministrazione per configurazioni dinamiche (fase avanzata).

*   **4.2. Programmazione e Best Practices**
    *   **Modularità:** Codice ben separato in moduli/servizi.
    *   **Test:** Unit test, test di integrazione. Per il frontend, test E2E (es. Cypress, Playwright).
    *   **Version Control:** Git (obbligatorio).
    *   **CI/CD:** Pipeline per build, test e deploy automatici (es. GitHub Actions, GitLab CI).
    *   **Logging:** Logging strutturato e centralizzato (es. ELK stack o alternative più leggere se in locale).
    *   **Documentazione Codice:** Docstring, commenti, API documentation (Swagger/OpenAPI per il backend).

*   **4.3. Usabilità (Generale)**
    *   **Performance:** L'interfaccia web deve essere reattiva. I task di backend (trascrizione) sono lunghi, quindi il feedback asincrono è cruciale.
    *   **Gestione Errori:** Messaggi di errore chiari e utili per l'utente. Retry-policy per operazioni fallite (dove applicabile).
    *   **Accessibilità (a11y):** Considerare gli standard WCAG per il frontend.

*   **4.4. Manutenzione**
    *   **Aggiornamento Dipendenze:** Piano per aggiornare regolarmente le librerie e i modelli (Whisper, LLM).
    *   **Monitoring:** Dashboard per monitorare lo stato dei servizi, l'utilizzo delle risorse, la lunghezza delle code.
    *   **Backup e Restore:** Strategie per il backup dei dati persistenti (database, file di trascrizione, modelli se customizzati).

*   **4.5. Scalabilità e Performance (Considerazioni Future)**
    *   **Worker di Trascrizione Scalabili:** Se l'uso cresce, possibilità di scalare orizzontalmente i worker di trascrizione (più container worker).
    *   **Load Balancing:** Per l'API e il frontend.
    *   **Ottimizzazione Modelli:** Uso di modelli quantizzati o versioni più leggere se le risorse sono un vincolo. Considerare l'uso di GPU se disponibile per accelerare Whisper e LLM.

*   **4.6. Sicurezza**
    *   **Input Validation:** Sanificare tutti gli input utente.
    *   **Sicurezza API:** Proteggere gli endpoint (autenticazione, rate limiting).
    *   **Gestione Dipendenze Sicure:** Controllare le vulnerabilità nelle librerie usate.
    *   **Data Privacy:** Se si gestiscono dati sensibili, considerare crittografia a riposo e in transito, e politiche di conservazione dei dati.

**5. Sfide e Criticità da Affrontare**

*   **Requisiti Hardware:** La trascrizione (specialmente con modelli Whisper grandi) e l'inferenza LLM sono resource-intensive (CPU, RAM, potenzialmente GPU). L'esecuzione locale su hardware limitato (i3) impone l'uso di modelli più piccoli e tempi di elaborazione lunghi.
*   **Complessità della Gestione Asincrona:** Implementare correttamente code di task e feedback utente per operazioni lunghe.
*   **Accuratezza dei Modelli AI:** L'accuratezza di Whisper e degli LLM può variare. La diarizzazione è particolarmente sfidante.
*   **Costi (se si usano API esterne):** L'uso di API cloud per Whisper o LLM introduce costi.
*   **Tempo di Sviluppo:** Implementare un frontend completo e funzionalità AI richiede un investimento significativo.

**6. Conclusioni e Prossimi Passi**

La soluzione attuale fornisce una solida base per la trascrizione locale. La Fase 1 (MVP Web Application) è cruciale per estendere l'accessibilità del sistema. Le fasi successive aggiungeranno valore significativo attraverso l'integrazione di funzionalità AI più avanzate. È fondamentale un approccio iterativo, raccogliendo feedback e prioritizzando le funzionalità in base alle esigenze degli utenti e alle risorse disponibili.

**Raccomandazione Immediata:** Iniziare lo sviluppo dell'API backend (Fase 1) con un sistema di code di task e parallelamente un frontend semplice per l'upload e la visualizzazione dello stato.

---

Questo documento dovrebbe fornire una base solida per la pianificazione e lo sviluppo. Spero sia utile!