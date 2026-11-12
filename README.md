# Mic2Clip

Windows tray app for voice dictation: speak, see the text appear live, polish or translate it with Gemini, and copy it to the clipboard to paste anywhere.

## What it does

- **Always at hand.** Lives in the system tray. A global hotkey (default `Alt+Q`) or a tray click shows and hides the dictation window. Only one instance can run at a time.
- **Live speech recognition.** Streams microphone audio to Google Cloud Speech to Text and shows partial results while you speak. Ten recognition languages, optional automatic punctuation.
- **Long dictation.** Streams are restarted automatically before Google's streaming time limit, so dictation is not cut off.
- **Voice commands for punctuation.** Spoken punctuation words are replaced with symbols (the default set in `commands.cfg` is for Russian dictation, e.g. "tochka" becomes a period). Any language can be added in `commands.cfg`.
- **AI editing.** "Improve text" fixes grammar, punctuation and clarity with Gemini without changing the language. "Translate" translates into one of nine languages.
- **Clipboard.** "Copy to clipboard" (or `Ctrl+Enter`), with options to close the window or clear the text after copying.
- **Compact mode.** A mini window with a single microphone button. The tray icon turns red while listening.
- **Auto hide.** The window hides and listening stops after a configurable period of silence.

## Tech stack

- **Language:** Python 3.10+
- **UI:** PySide6 (Qt 6): tray icon, windows, cross thread signals
- **Speech:** Google Cloud Speech to Text, streaming recognition (`google-cloud-speech`)
- **AI:** Google Gemini API (`google-generativeai`)
- **Audio:** `sounddevice`, `numpy`
- **System:** `keyboard` (global hotkey), `pyperclip` (clipboard), `python-dotenv`

## Project structure

```
app_win/
  main.py              Entry point: tray icon, hotkey, single instance, wiring
  app_controller.py    App logic: talk state, silence timer, voice commands
  speech_service.py    Microphone capture and streaming recognition session
  audio_stream.py      Audio input stream
  gemini_service.py    Improve text and translate with Gemini
  dictation_window.py  Main dictation window
  mini_window.py       Compact window
  hotkeys.py           Global hotkey registration
  config.py            Loads settings.cfg and .env
  settings.cfg         Hotkey, auto hide, Gemini model, audio settings
  commands.cfg         Spoken word to punctuation mapping
  .env.example         Required secrets
Idea_MASTER.txt        Product concept
Implementation_MASTER.txt  Implementation plan
```

## Getting started

Requirements: Windows, Python 3.10+, a Google Cloud project with Speech to Text enabled and a service account JSON key, and a Gemini API key.

```bash
cd app_win
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env     # set GOOGLE_APPLICATION_CREDENTIALS and GEMINI_API_KEY
python main.py
```

`mic2clip_0.cmd` starts the app without a console window. If the global hotkey does not register, run the app as administrator or use the tray menu.

## Security notes

- API keys and the path to the Google service account file live only in `.env`. The service account JSON and `.env` are excluded from git. See `.env.example`.

## Author

**Andrey Zabolotsky**, Senior Full Stack Developer
[LinkedIn](https://linkedin.com/in/andzab) · [GitHub](https://github.com/anddan21)
