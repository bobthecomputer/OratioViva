#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test des modèles TTS locaux pour diagnostiquer les problèmes
.DESCRIPTION
    Vérifie que chaque modèle peut être chargé et génère un test audio
.PARAMETER Model
    Modèle spécifique à tester (parler, bark, speecht5, mms) ou "all" pour tous
#>
param(
    [string]$Model = "all",
    [string]$Text = "Hello, this is a test of the text to speech system."
)

$ErrorActionPreference = "Continue"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path $scriptRoot -Parent
Push-Location $repoRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Test des modèles TTS locaux" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$python = ".\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Erreur: Environnement Python non trouvé." -ForegroundColor Red
    Write-Host "Exécutez d'abord: cd backend; .\.venv\Scripts\activate; pip install -r requirements.txt -r requirements-tts.txt" -ForegroundColor Yellow
    exit 1
}

$testScript = @"
import sys
import os
import traceback
from pathlib import Path

os.environ['ORATIO_DATA_DIR'] = r'$repoRoot\data'
os.environ['ORATIO_MODELS_DIR'] = r'$repoRoot\models'

test_text = '''$Text'''

results = {}

def test_parler():
    print('Test Parler-TTS Mini...')
    try:
        from transformers import AutoTokenizer
        from parler_tts import ParlerTTSForConditionalGeneration
        import torch
        
        model_path = r'$repoRoot\models\parler-tts_parler-tts-mini-v1.1'
        if not Path(model_path).exists():
            return 'MODÈLE MANQUANT'
        
        model = ParlerTTSForConditionalGeneration.from_pretrained(model_path).to('cpu')
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
        
        model_path = r'$repoRoot\models\suno_bark-small'
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
        print(f'  ✓ Bark: audio généré, shape={audio.shape}')
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
        
        model_path = r'$repoRoot\models\microsoft_speecht5_tts'
        vocoder_path = r'$repoRoot\models\microsoft_speecht5_hifigan'
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
        
        model_path = r'$repoRoot\models\facebook_mms-tts-eng'
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

tests = []
if '$Model'.lower() == 'all' or '$Model'.lower() == 'parler':
    tests.append(('Parler-TTS', test_parler))
if '$Model'.lower() == 'all' or '$Model'.lower() == 'bark':
    tests.append(('Bark', test_bark))
if '$Model'.lower() == 'all' or '$Model'.lower() == 'speecht5':
    tests.append(('SpeechT5', test_speecht5))
if '$Model'.lower() == 'all' or '$Model'.lower() == 'mms':
    tests.append(('MMS', test_mms))

for name, test_func in tests:
    try:
        result = test_func()
        results[name] = result
    except Exception as e:
        print(f'Test {name} planté: {e}')
        results[name] = f'CRASH: {e}'

print()
print('========================================')
print('  Résumé des tests')
print('========================================')
for name, result in results.items():
    status = '✓' if result == 'OK' else '✗'
    print(f'{status} {name}: {result}')

print()
print('Dépendances installées:')
for pkg in ['torch', 'transformers', 'parler-tts', 'numpy']:
    try:
        __import__(pkg)
        print(f'  ✓ {pkg}')
    except ImportError:
        print(f'  ✗ {pkg} MANQUANT')
"@

$testScript | Out-File -FilePath "$repoRoot\scripts\test_models.ps1" -Encoding ASCII

Write-Host "Exécution des tests..." -ForegroundColor Green
& $python "$repoRoot\scripts\test_models.py"

Pop-Location
