import sys
import os
import traceback
from pathlib import Path

# Fix encoding for Windows console
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf8')(sys.stderr.buffer)

os.environ['ORATIO_DATA_DIR'] = os.path.dirname(os.path.abspath(__file__)).replace('scripts', 'data')
os.environ['ORATIO_MODELS_DIR'] = os.path.dirname(os.path.abspath(__file__)).replace('scripts', 'models')

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
models_dir = os.path.join(repo_root, 'models')

test_text = "Hello, this is a test of the text to speech system."

results = {}

def test_parler():
    print('Test Parler-TTS Mini...')
    try:
        from transformers import AutoTokenizer
        from parler_tts import ParlerTTSForConditionalGeneration
        import torch

        model_path = os.path.join(models_dir, 'parler-tts_parler-tts-mini-v1.1')
        if not Path(model_path).exists():
            return 'MODÈLE MANQUANT'

        model = ParlerTTSForConditionalGeneration.from_pretrained(model_path).to('cpu')
        model.eval()
        tokenizer = AutoTokenizer.from_pretrained(model_path)

        description = 'Neutral speaker, clear voice, studio quality.'
        desc_ids = tokenizer(description, return_tensors='pt').input_ids.to('cpu')
        prompt_ids = tokenizer(test_text, return_tensors='pt').input_ids.to('cpu')

        with torch.inference_mode():
            audio = model.generate(input_ids=desc_ids, prompt_input_ids=prompt_ids)

        print(f'  ✓ Parler-TTS: audio généré, shape={audio.shape}')
        return 'OK'
    except Exception as e:
        print(f'  ✗ Erreur: {e}')
        traceback.print_exc()
        return f'ERREUR: {e}'

def test_bark():
    print('Test Bark Small...')
    try:
        from transformers import pipeline
        import torch

        model_path = os.path.join(models_dir, 'suno_bark-small')
        if not Path(model_path).exists():
            return 'MODÈLE MANQUANT'

        bark = pipeline(
            task='text-to-audio',
            model=model_path,
            device='cpu',
            trust_remote_code=True,
        )

        output = bark(test_text)
        audio = output['audio']
        print(f'  ✓ Bark: audio généré, shape={audio.shape if hasattr(audio, "shape") else len(audio)}')
        return 'OK'
    except Exception as e:
        print(f'  ✗ Erreur: {e}')
        traceback.print_exc()
        return f'ERREUR: {e}'

def test_speecht5():
    print('Test SpeechT5...')
    try:
        from transformers import SpeechT5ForTextToSpeech, SpeechT5HifiGan, SpeechT5Processor
        import torch

        model_path = os.path.join(models_dir, 'microsoft_speecht5_tts')
        vocoder_path = os.path.join(models_dir, 'microsoft_speecht5_hifigan')
        if not Path(model_path).exists():
            return 'MODÈLE MANQUANT'

        processor = SpeechT5Processor.from_pretrained(model_path)
        model = SpeechT5ForTextToSpeech.from_pretrained(model_path)
        vocoder = SpeechT5HifiGan.from_pretrained(vocoder_path)

        inputs = processor(text=test_text, return_tensors='pt')
        speaker_embeddings = torch.zeros((1, 512))

        with torch.inference_mode():
            speech = model.generate_speech(
                inputs['input_ids'],
                speaker_embeddings,
                vocoder=vocoder,
            )

        print(f'  ✓ SpeechT5: audio généré, shape={speech.shape}')
        return 'OK'
    except Exception as e:
        print(f'  ✗ Erreur: {e}')
        traceback.print_exc()
        return f'ERREUR: {e}'

def test_mms():
    print('Test MMS TTS...')
    try:
        from transformers import AutoProcessor, VitsModel
        import torch

        model_path = os.path.join(models_dir, 'facebook_mms-tts-eng')
        if not Path(model_path).exists():
            return 'MODÈLE MANQUANT'

        processor = AutoProcessor.from_pretrained(model_path)
        model = VitsModel.from_pretrained(model_path)
        model.eval()

        inputs = processor(text=test_text, return_tensors='pt')
        with torch.inference_mode():
            waveform = model(**inputs).waveform

        print(f'  ✓ MMS: audio généré, shape={waveform.shape}')
        return 'OK'
    except Exception as e:
        print(f'  ✗ Erreur: {e}')
        traceback.print_exc()
        return f'ERREUR: {e}'

print("=" * 50)
print("  Test des modèles TTS locaux")
print("=" * 50)
print()

tests = [
    ('Parler-TTS', test_parler),
    ('Bark', test_bark),
    ('SpeechT5', test_speecht5),
    ('MMS', test_mms),
]

for name, test_func in tests:
    try:
        result = test_func()
        results[name] = result
    except Exception as e:
        print(f'Test {name} planté: {e}')
        results[name] = f'CRASH: {e}'

print()
print("=" * 50)
print("  Résumé des tests")
print("=" * 50)
for name, result in results.items():
    status = '✓' if result == 'OK' else '✗'
    print(f'{status} {name}: {result}')

print()
print("Dépendances installées:")
for pkg in ['torch', 'transformers', 'parler_tts', 'numpy']:
    try:
        __import__(pkg.replace('-', '_'))
        print(f'  ✓ {pkg}')
    except ImportError:
        print(f'  ✗ {pkg} MANQUANT')

print()
print("Python:", sys.version)
