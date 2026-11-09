# Gemini examples

## Live headset translation

[`livevoicetranslater.py`](livevoicetranslater.py) streams speech from a microphone to the Gemini
Live Translate API and plays the translated audio through your headphones. It
also prints source and translated transcripts when the API provides them.
Microphone audio is sent to Google for processing.

### Requirements

- Python 3.11 or newer.
- A Gemini API key with access to the `gemini-3.5-live-translate-preview` model.
  Obtain a key from [Google AI Studio](https://aistudio.google.com/apikey).
- An internet connection and a working microphone and audio output device.
- Microphone input at 16 kHz and audio output at 24 kHz. Device support depends
  on the operating system and audio driver.

The following commands use PowerShell on Windows. Run them from the repository
directory:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "your-api-key"
```

The environment variable lasts for the current PowerShell session. Keep your
API key private and do not commit it to the repository.

### Run

Connect your headset, then start translation:

```powershell
.\venv\Scripts\python.exe livevoicetranslater.py --target-language es
```

Speak into the microphone and listen through the headphones. Spanish (`es`) is
the default; use another supported language code, such as `fr`, to change the
target. The example uses the system's default input and output devices. Press
**Ctrl+C** to stop.

Status messages appear when microphone audio is captured and sent to Gemini,
and when translated audio is sent to the output device. They repeat at most
every five seconds while each activity continues. Captured audio may be silence;
the messages do not confirm speech recognition or that audio is audible. Source
and translation transcripts appear separately when provided by the API.

To choose specific devices, list them and use their displayed IDs or names:

```powershell
.\venv\Scripts\python.exe livevoicetranslater.py --list-devices
```

Choose an input with `in` channels and an output with `out` channels. In the
command below, replace `<input-id>` and `<output-id>` with the numbers from
your current device list (without the angle brackets):

```powershell
.\venv\Scripts\python.exe livevoicetranslater.py --target-language es --input-device <input-id> --output-device <output-id>
```

Device IDs may change when devices are connected or disconnected. You can omit
both device options to use the system defaults. Check
`.\venv\Scripts\python.exe livevoicetranslater.py --help` for all options.

### Troubleshooting

- **Missing API key:** Set `GEMINI_API_KEY` in the same terminal before running.
- **Connection or model errors:** Check your internet connection, API key and
  project access to the preview model. See the [Live Translate documentation](https://aistudio.google.com/docs/live-api/live-translate).
  The example explicitly selects the Gemini API `v1beta` endpoint.
- **No sound or microphone/device errors:** Check operating-system microphone
  permissions and headset volume, list devices, and select the intended input
  and output. If a device rejects a sample rate, try a different device or audio
  driver. For `Invalid device`, list devices again and select a current output
  ID, or omit `--output-device` to use the default.
- **Audio stream or buffer errors:** Check the connection and device configuration
  and retry. The program stops rather than silently dropping audio when its
  buffers fill.

To run the simulated audio tests without a live API connection:

```powershell
.\venv\Scripts\python.exe -m unittest -v test_livevoicetranslater
```
