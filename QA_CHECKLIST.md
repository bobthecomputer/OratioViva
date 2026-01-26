# OratioViva Pre-Release QA Checklist

## 1. Automated Tests
- [x] Backend unit tests pass (`pytest -q`)
- [ ] Frontend tests pass (`npm run test`)
- [x] New preset tests added and passing (10 tests)
- [x] New diagnostics tests added and passing
- [x] New telemetry tests added and passing

## 2. Static Analysis
- [x] Backend syntax check passes (`python -m py_compile`)
- [x] Frontend lint passes (`npm run lint`)
- [ ] No critical ESLint warnings (minor prop-types warnings exist)

## 3. Manual Testing Matrix

### Voice/Model Combinations
| Model Class | Voice Example | Style | Voice Prompt | Voice Ref | Status |
|------------|--------------|-------|--------------|-----------|--------|
| Dia2 (streaming) | dia2_2b_en | ✓ | ✓ | ✗ | |
| Parler-TTS | parler_en_neutral | ✓ | ✓ | ✗ | |
| SpeechT5 | speecht5_hub | ✗ | ✗ | ✓ | |
| XTTS-v2 | xtts_v2_example | ✗ | ✗ | ✓ | |
| Kokoro | kokoro_en_us | ✓ | ✓ | ✗ | |

### Tone/Prompt Presets
- [x] Neutral tone works
- [ ] Expressive tone works
- [ ] Calm tone works
- [ ] Authoritative tone works
- [ ] Custom tone can be created
- [ ] Custom tone can be deleted

### Long Audio
- [ ] Sequential chunking works
- [ ] Parallel chunking works
- [ ] Chunk size adjustment works
- [ ] Combined audio plays correctly

### Error Handling
- [ ] Missing model shows appropriate error
- [ ] Invalid voice_ref shows helpful message
- [ ] Unsupported style for model shows warning
- [ ] Backend restart works

### Storage/Cleanup
- [x] Diagnostics panel shows correct info
- [ ] Cleanup deletes audio files
- [ ] Cleanup optionally deletes history
- [ ] Storage stats are accurate

### First-Run Experience
- [ ] First-run guide shows on first launch
- [ ] Guide can be skipped
- [ ] All guide steps are clear

### Telemetry
- [ ] Telemetry toggle saves correctly
- [ ] Toggle is persisted across restarts

## 4. Localization
- [x] English strings complete
- [x] French strings complete
- [x] No missing i18n keys (music/sfx tabs added)

## 5. Build Verification
- [x] Frontend builds successfully (`npm run build`)
- [x] Build output is clean
- [ ] No console errors in dev mode

## 6. Performance
- [ ] App loads within 3 seconds
- [ ] Voice list loads within 2 seconds
- [ ] Diagnostics load within 1 second

## 7. Release Checklist
- [ ] Version number updated
- [ ] CHANGELOG.md updated
- [ ] README.md updated
- [ ] Installer tested on clean Windows VM
- [ ] Backend starts without errors
- [ ] Frontend connects to backend
- [ ] Audio playback works
- [ ] Export functionality works

## Known Issues (to be addressed before release)
- ESLint prop-types warnings exist but don't affect functionality

## Sign-off
- [ ] Developer: _______________
- [ ] Tester: _______________
- [ ] Date: _______________
