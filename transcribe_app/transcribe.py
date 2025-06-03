import os
import sys
import json
import time
import subprocess
import whisper
from datetime import datetime, timedelta
from pydub import AudioSegment
from pydub.utils import make_chunks

# Carica il modello Whisper. Il modello viene scaricato la prima volta che viene chiamato
# e messo in cache in ~/.cache/whisper (mappato a un volume Docker per persistere).
# La variabile d'ambiente WHISPER_MODEL definisce quale modello usare.
MODEL_NAME = os.getenv('WHISPER_MODEL', 'small') # Default a 'small' se non specificato
AUDIO_LANGUAGE = os.getenv('AUDIO_LANGUAGE', None) # Lingua per Whisper, None per auto-detect

# Durata massima della sessione di lavoro in secondi
# Default a 12 ore se non specificato, per il vincolo "mezza giornata"
MAX_SESSION_SECONDS = int(os.getenv('MAX_SESSION_DURATION_SECONDS', 12 * 60 * 60))

# Durata dei segmenti audio in millisecondi (es. 10 minuti = 600 * 1000)
CHUNK_DURATION_MS = int(os.getenv('CHUNK_DURATION_MS', 10 * 60 * 1000))

# Directory base per i dati persistenti all'interno del container
PERSISTENT_DATA_BASE_DIR = "/app/persistent_data"

# Orario di inizio della sessione corrente
SESSION_START_TIME = time.time()

def log_message(message):
    """Stampa un messaggio con timestamp."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

def check_session_time():
    """Controlla se il tempo massimo della sessione è stato superato."""
    elapsed_seconds = time.time() - SESSION_START_TIME
    if elapsed_seconds >= MAX_SESSION_SECONDS:
        log_message(f"Limite di sessione ({MAX_SESSION_SECONDS // 3600} ore) raggiunto. Salvataggio progressi e uscita.")
        return True
    return False

def convert_mp3_to_wav(mp3_path, wav_path):
    """Converte un file MP3 in WAV (mono, 16kHz) usando ffmpeg."""
    log_message(f"Conversione di {mp3_path} in WAV (16kHz, mono)...")
    try:
        # ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav
        # -y sovrascrive l'output se esiste
        # -hide_banner per output più pulito
        # -loglevel error per mostrare solo errori
        subprocess.run([
            "ffmpeg", "-i", mp3_path,
            "-ar", "16000",  # Frequenza di campionamento 16kHz
            "-ac", "1",      # Canale mono
            "-c:a", "pcm_s16le", # Codec WAV standard
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            wav_path
        ], check=True)
        log_message(f"File WAV creato: {wav_path}")
        return True
    except subprocess.CalledProcessError as e:
        log_message(f"Errore durante la conversione MP3 in WAV: {e}")
        return False
    except FileNotFoundError:
        log_message("ERRORE: ffmpeg non trovato. Assicurati che sia installato e nel PATH.")
        return False


def split_wav_into_chunks(wav_path, chunks_dir, chunk_length_ms):
    """Divide un file WAV in segmenti più piccoli."""
    log_message(f"Divisione di {wav_path} in segmenti da {chunk_length_ms // 1000 // 60} minuti...")
    try:
        audio = AudioSegment.from_wav(wav_path)
        chunks = make_chunks(audio, chunk_length_ms)
        
        os.makedirs(chunks_dir, exist_ok=True)
        chunk_paths = []
        for i, chunk in enumerate(chunks):
            chunk_name = f"chunk_{i:04d}.wav"
            chunk_path = os.path.join(chunks_dir, chunk_name)
            chunk.export(chunk_path, format="wav")
            chunk_paths.append(chunk_path)
            log_message(f"Segmento creato: {chunk_path}")
        log_message(f"Creati {len(chunks)} segmenti in {chunks_dir}")
        return chunk_paths
    except Exception as e:
        log_message(f"Errore durante la divisione del WAV: {e}")
        return None

def transcribe_chunk(model, chunk_path, language=None):
    """Trascrive un singolo segmento audio usando Whisper."""
    log_message(f"Trascrizione del segmento: {chunk_path} con modello {MODEL_NAME}...")
    try:
        # Nota: per trascrizioni più lunghe, potresti voler usare verbose=True/False
        # e gestire i segmenti di Whisper se il chunk stesso è molto lungo.
        # Ma per chunk di 5-10 minuti, una trascrizione diretta va bene.
        if language:
            result = model.transcribe(chunk_path, language=language, fp16=False) # fp16=False per CPU
        else:
            result = model.transcribe(chunk_path, fp16=False) # fp16=False per CPU
        
        log_message(f"Segmento {chunk_path} trascritto.")
        return result["text"]
    except Exception as e:
        log_message(f"Errore durante la trascrizione del segmento {chunk_path}: {e}")
        return None

def main(input_audio_path, output_transcription_path):
    """Funzione principale per orchestrare la trascrizione."""
    global SESSION_START_TIME
    SESSION_START_TIME = time.time() # Resetta il timer all'inizio di ogni chiamata a main

    log_message(f"Avvio trascrizione per: {input_audio_path}")
    log_message(f"Output previsto in: {output_transcription_path}")
    log_message(f"Modello Whisper da utilizzare: {MODEL_NAME}")
    if AUDIO_LANGUAGE:
        log_message(f"Lingua audio specificata: {AUDIO_LANGUAGE}")
    else:
        log_message("Lingua audio: rilevamento automatico di Whisper.")
    log_message(f"Durata massima sessione: {MAX_SESSION_SECONDS // 3600} ore")
    log_message(f"Durata segmenti audio: {CHUNK_DURATION_MS // 1000 // 60} minuti")

    base_filename = os.path.splitext(os.path.basename(input_audio_path))[0]
    
    # Directory specifiche per questo file audio all'interno di PERSISTENT_DATA_BASE_DIR
    file_persistent_dir = os.path.join(PERSISTENT_DATA_BASE_DIR, base_filename)
    os.makedirs(file_persistent_dir, exist_ok=True)

    progress_file_path = os.path.join(file_persistent_dir, "progress.json")
    converted_wav_path = os.path.join(file_persistent_dir, f"{base_filename}_converted.wav")
    chunks_dir = os.path.join(file_persistent_dir, "audio_chunks")
    transcribed_chunks_dir = os.path.join(file_persistent_dir, "transcribed_chunks_text")

    os.makedirs(chunks_dir, exist_ok=True)
    os.makedirs(transcribed_chunks_dir, exist_ok=True)

    progress_data = {
        "original_file": input_audio_path,
        "converted_wav_path": converted_wav_path,
        "audio_chunks_dir": chunks_dir,
        "transcribed_chunks_texts_dir": transcribed_chunks_dir,
        "total_chunks": 0,
        "processed_chunks_count": 0,
        "chunk_paths": [],
        "status": "initialized" # Stati: initialized, wav_converted, chunked, transcribing, completed, error
    }

    # Carica i progressi se esistono
    if os.path.exists(progress_file_path):
        try:
            with open(progress_file_path, 'r') as f:
                progress_data = json.load(f)
            log_message(f"File di progresso caricato: {progress_file_path}")
            # Assicura che le directory esistano anche se il progresso è stato caricato
            os.makedirs(progress_data.get("audio_chunks_dir", chunks_dir), exist_ok=True)
            os.makedirs(progress_data.get("transcribed_chunks_texts_dir", transcribed_chunks_dir), exist_ok=True)
        except json.JSONDecodeError:
            log_message(f"ATTENZIONE: File di progresso {progress_file_path} corrotto. Ricomincio da capo per questo file.")
            # Se corrotto, usa progress_data default e sovrascrivi il file corrotto più tardi

    # --- FASE 1: Conversione in WAV (se non già fatta) ---
    if progress_data["status"] in ["initialized"] or not os.path.exists(progress_data["converted_wav_path"]):
        if check_session_time(): return # Controlla il tempo prima di un'operazione lunga
        if not convert_mp3_to_wav(input_audio_path, progress_data["converted_wav_path"]):
            progress_data["status"] = "error_wav_conversion"
            with open(progress_file_path, 'w') as f: json.dump(progress_data, f, indent=4)
            return
        progress_data["status"] = "wav_converted"
        with open(progress_file_path, 'w') as f: json.dump(progress_data, f, indent=4)
    
    # --- FASE 2: Divisione in segmenti (se non già fatta o se i segmenti mancano) ---
    # Verifica se i chunk sono già stati creati e referenziati
    # Questo controllo è un po' più lasco; se `chunk_paths` è vuoto o il conteggio non corrisponde, rigenera.
    existing_chunk_files = [os.path.join(progress_data["audio_chunks_dir"], f) for f in os.listdir(progress_data["audio_chunks_dir"])] if os.path.exists(progress_data["audio_chunks_dir"]) else []
    
    if progress_data["status"] in ["initialized", "wav_converted"] or \
       not progress_data.get("chunk_paths") or \
       len(progress_data["chunk_paths"]) == 0 or \
       len(progress_data["chunk_paths"]) != len(existing_chunk_files) or \
       not all(os.path.exists(p) for p in progress_data["chunk_paths"]):

        if check_session_time(): return
        
        chunk_file_paths = split_wav_into_chunks(progress_data["converted_wav_path"], progress_data["audio_chunks_dir"], CHUNK_DURATION_MS)
        if chunk_file_paths is None:
            progress_data["status"] = "error_chunking"
            with open(progress_file_path, 'w') as f: json.dump(progress_data, f, indent=4)
            return
        progress_data["chunk_paths"] = chunk_file_paths
        progress_data["total_chunks"] = len(chunk_file_paths)
        progress_data["processed_chunks_count"] = 0 # Resetta i chunk processati se rigeneriamo i chunk
        progress_data["status"] = "chunked"
        # Rimuovi vecchie trascrizioni di chunk se stiamo ricreando i chunk
        for f_name in os.listdir(progress_data["transcribed_chunks_texts_dir"]):
            os.remove(os.path.join(progress_data["transcribed_chunks_texts_dir"], f_name))
        
        with open(progress_file_path, 'w') as f: json.dump(progress_data, f, indent=4)

    # --- FASE 3: Trascrizione dei segmenti ---
    if progress_data["status"] not in ["completed", "error_transcribing"]:
        progress_data["status"] = "transcribing"
        
        # Carica il modello Whisper solo quando serve
        log_message(f"Caricamento del modello Whisper '{MODEL_NAME}'...")
        try:
            model = whisper.load_model(MODEL_NAME)
            log_message("Modello Whisper caricato.")
        except Exception as e:
            log_message(f"Errore durante il caricamento del modello Whisper: {e}")
            progress_data["status"] = "error_loading_model"
            with open(progress_file_path, 'w') as f: json.dump(progress_data, f, indent=4)
            return

        start_chunk_index = progress_data.get("processed_chunks_count", 0)
        
        for i in range(start_chunk_index, progress_data["total_chunks"]):
            if check_session_time(): # Controlla prima di ogni trascrizione
                log_message(f"Interruzione dovuta al limite di tempo. Progresso salvato per {progress_data['processed_chunks_count']}/{progress_data['total_chunks']} segmenti.")
                with open(progress_file_path, 'w') as f: json.dump(progress_data, f, indent=4)
                return

            chunk_to_transcribe_path = progress_data["chunk_paths"][i]
            # Nome del file di testo per la trascrizione del chunk
            chunk_text_filename = f"chunk_{i:04d}_transcription.txt"
            chunk_text_output_path = os.path.join(progress_data["transcribed_chunks_texts_dir"], chunk_text_filename)

            # Se il file di testo del chunk non esiste, trascrivilo
            if not os.path.exists(chunk_text_output_path):
                transcription_text = transcribe_chunk(model, chunk_to_transcribe_path, language=AUDIO_LANGUAGE)
                if transcription_text is None:
                    log_message(f"Trascrizione fallita per il segmento {chunk_to_transcribe_path}. Interruzione.")
                    progress_data["status"] = "error_transcribing"
                    # Potresti voler salvare il progresso parziale qui comunque
                    with open(progress_file_path, 'w') as f: json.dump(progress_data, f, indent=4)
                    return 
                
                with open(chunk_text_output_path, "w", encoding="utf-8") as text_file:
                    text_file.write(transcription_text)
                log_message(f"Trascrizione del segmento {i+1}/{progress_data['total_chunks']} salvata in {chunk_text_output_path}")
            else:
                log_message(f"Trascrizione per il segmento {chunk_to_transcribe_path} già esistente: {chunk_text_output_path}. Salto.")

            progress_data["processed_chunks_count"] = i + 1
            with open(progress_file_path, 'w') as f: json.dump(progress_data, f, indent=4)

        log_message("Tutti i segmenti sono stati trascritti.")
        progress_data["status"] = "completed"
        with open(progress_file_path, 'w') as f: json.dump(progress_data, f, indent=4)

    # --- FASE 4: Assemblaggio e Pulizia (solo se tutto completato) ---
    if progress_data["status"] == "completed":
        log_message(f"Assemblaggio della trascrizione finale in {output_transcription_path}...")
        full_transcription = []
        for i in range(progress_data["total_chunks"]):
            chunk_text_filename = f"chunk_{i:04d}_transcription.txt"
            chunk_text_path = os.path.join(progress_data["transcribed_chunks_texts_dir"], chunk_text_filename)
            if os.path.exists(chunk_text_path):
                with open(chunk_text_path, "r", encoding="utf-8") as text_file:
                    full_transcription.append(text_file.read())
            else:
                log_message(f"ATTENZIONE: Manca il file di trascrizione del segmento {chunk_text_path} durante l'assemblaggio.")
        
        # Scrive la trascrizione completa nel file di output finale
        os.makedirs(os.path.dirname(output_transcription_path), exist_ok=True)
        with open(output_transcription_path, "w", encoding="utf-8") as final_file:
            final_file.write("\n\n".join(full_transcription)) # Aggiunge un doppio a capo tra i segmenti
        
        log_message(f"Trascrizione finale assemblata e salvata in {output_transcription_path}")
        log_message("Pulizia dei file temporanei...")
        
        # Rimuovi i file e le directory temporanee per questo specifico audio
        # Esempio:
        # if os.path.exists(progress_data["converted_wav_path"]): os.remove(progress_data["converted_wav_path"])
        # for chunk_p in progress_data["chunk_paths"]: 
        #     if os.path.exists(chunk_p): os.remove(chunk_p)
        # for text_f in os.listdir(progress_data["transcribed_chunks_texts_dir"]):
        #    if os.path.exists(os.path.join(progress_data["transcribed_chunks_texts_dir"], text_f)): os.remove(os.path.join(progress_data["transcribed_chunks_texts_dir"], text_f))
        # if os.path.exists(progress_data["transcribed_chunks_texts_dir"]): os.rmdir(progress_data["transcribed_chunks_texts_dir"])
        # if os.path.exists(progress_data["audio_chunks_dir"]): os.rmdir(progress_data["audio_chunks_dir"])
        # if os.path.exists(progress_file_path): os.remove(progress_file_path)
        # if not os.listdir(file_persistent_dir): # Se la cartella è vuota, rimuovila
        #    os.rmdir(file_persistent_dir)
        # Per semplicità, la pulizia aggressiva è commentata. Puoi attivarla se necessario.
        # Attualmente, i file di progresso e i chunk rimangono per ispezione.
        # Si potrebbe rimuovere solo progress_file_path per indicare il completamento.
        if os.path.exists(progress_file_path):
            os.remove(progress_file_path) # Rimuovere il file di progresso indica il completamento definitivo
        log_message(f"Pulizia (rimozione file di progresso) completata per {base_filename}.")
        
    elif progress_data["status"].startswith("error"):
        log_message(f"Processo terminato con errore: {progress_data['status']}. Controllare {progress_file_path} per dettagli.")
    else:
        log_message(f"Processo non completato. Stato attuale: {progress_data['status']}. Rieseguire il comando per riprendere.")

    elapsed_total = time.time() - SESSION_START_TIME
    log_message(f"Tempo totale trascorso in questa sessione: {timedelta(seconds=elapsed_total)}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Utilizzo: python transcribe.py <percorso_audio_input> <percorso_testo_output>")
        print("Esempio: python transcribe.py /app/audio_input/mio_audio.mp3 /app/transcriptions_output/mio_audio.txt")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.exists(input_path):
        log_message(f"ERRORE: File audio di input non trovato: {input_path}")
        sys.exit(1)

    main(input_path, output_path)