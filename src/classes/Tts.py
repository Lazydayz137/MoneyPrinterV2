import os
import soundfile as sf
from kittentts import KittenTTS as KittenModel

from config import (
    ROOT_DIR,
    get_tts_provider,
    get_tts_voice,
    get_elevenlabs_api_key,
    get_elevenlabs_voice_id,
    get_verbose
)

KITTEN_MODEL = "KittenML/kitten-tts-mini-0.8"
KITTEN_SAMPLE_RATE = 24000

class TTS:
    def __init__(self) -> None:
        self._provider = get_tts_provider()

        if self._provider == "elevenlabs":
            from elevenlabs.client import ElevenLabs
            api_key = get_elevenlabs_api_key()
            if not api_key:
                raise ValueError("ElevenLabs API key is missing. Please set it in config.json.")
            self._elevenlabs_client = ElevenLabs(api_key=api_key)
            self._voice = get_elevenlabs_voice_id() or "Rachel"
        else:
            # Default fallback to KittenTTS / edge-tts equivalent
            self._model = KittenModel(KITTEN_MODEL)
            self._voice = get_tts_voice()

    def synthesize(self, text, output_file=os.path.join(ROOT_DIR, ".mp", "audio.wav")):
        if self._provider == "elevenlabs":
            if get_verbose():
                print(f"Synthesizing using ElevenLabs Voice: {self._voice}")

            audio_generator = self._elevenlabs_client.generate(
                text=text,
                voice=self._voice,
                model="eleven_multilingual_v2"
            )

            with open(output_file, "wb") as f:
                for chunk in audio_generator:
                    if chunk:
                        f.write(chunk)
            return output_file
        else:
            if get_verbose():
                print(f"Synthesizing using KittenTTS Voice: {self._voice}")

            audio = self._model.generate(text, voice=self._voice)
            sf.write(output_file, audio, KITTEN_SAMPLE_RATE)
            return output_file
