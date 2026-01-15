; OratioViva NSIS Installer Script
; Génère un installateur Windows professionnel

!include "MUI2.nsh"

; === Configuration ===
Name "OratioViva TTS"
OutFile "dist\OratioViva-Setup.exe"
InstallDir "$PROGRAMFILES\OratioViva"
RequestExecutionLevel admin
CRCCheck on
ShowInstDetails nevershow
ShowUninstDetails nevershow

; === Icônes ===
!define MUI_ICON "assets\app.ico"
!define MUI_UNICON "assets\app.ico"

; === Pages ===
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "French"

; === Variables ===
Var StartMenuFolder

; === Installation ===
Section "Install" SecMain
    SetOutPath $INSTDIR
    
    ; Application files
    File /r "backend\*.py"
    File /r "backend\requirements*.txt"
    
    ; Frontend
    File /r "frontend\dist\*"
    
    ; Assets
    File "assets\app.ico"
    
    ; Modèles (optionnel - peut être lourd)
    ${If} ${FileExists} "models\*.*"
        SetOutPath $INSTDIR\models
        File /r "models\*.*"
    ${EndIf}
    
    ; Création des dossiers de données
    CreateDirectory "$INSTDIR\data"
    CreateDirectory "$INSTDIR\data\outputs"
    CreateDirectory "$INSTDIR\data\outputs\audio"
    
    ; Configuration par défaut
    WriteRegStr HKLM "Software\OratioViva" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\OratioViva" "DataDir" "$INSTDIR\data"
    
    ; Variables d'environnement utilisateur
    WriteRegExpandStr HKCU "Environment" "ORATIO_DATA_DIR" "$INSTDIR\data"
    WriteRegExpandStr HKCU "Environment" "ORATIO_MODELS_DIR" "$INSTDIR\models"
    WriteRegStr HKCU "Environment" "ORATIO_TTS_PROVIDER" "local"
    
    ; Raccourcis
    CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\OratioViva.lnk" "$INSTDIR\launcher.bat" "" "$INSTDIR\app.ico"
    CreateShortcut "$DESKTOP\OratioViva.lnk" "$INSTDIR\launcher.bat" "" "$INSTDIR\app.ico"
    
    ; Fichier de lancement
    SetOutPath $INSTDIR
    File "scripts\launcher.bat"
    
    ; Uninstall
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    ; Ajout dans Programmes et fonctionnalités
    WriteRegStr HKLM "Microsoft\Windows\CurrentVersion\Uninstall\OratioViva" "DisplayName" "OratioViva TTS"
    WriteRegStr HKLM "Microsoft\Windows\CurrentVersion\Uninstall\OratioViva" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKLM "Microsoft\Windows\CurrentVersion\Uninstall\OratioViva" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Microsoft\Windows\CurrentVersion\Uninstall\OratioViva" "Publisher" "OratioViva"
    WriteRegStr HKLM "Microsoft\Windows\CurrentVersion\Uninstall\OratioViva" "DisplayVersion" "1.0.0"
    WriteRegDWORD HKLM "Microsoft\Windows\CurrentVersion\Uninstall\OratioViva" "NoModify" 1
    WriteRegDWORD HKLM "Microsoft\Windows\CurrentVersion\Uninstall\OratioViva" "NoRepair" 1
    
SectionEnd

; === Désinstallation ===
Section "Uninstall"
    ; Suppression des fichiers
    Delete "$INSTDIR\*"
    RMDir /r "$INSTDIR\models"
    RMDir /r "$INSTDIR\data"
    RMDir "$INSTDIR"
    
    ; Suppression des raccourcis
    Delete "$SMPROGRAMS\$StartMenuFolder\OratioViva.lnk"
    RMDir "$SMPROGRAMS\$StartMenuFolder"
    Delete "$DESKTOP\OratioViva.lnk"
    
    ; Suppression du registre
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\OratioViva"
    DeleteRegKey HKLM "Software\OratioViva"
    DeleteRegKey HKCU "Environment" "ORATIO_DATA_DIR"
    DeleteRegKey HKCU "Environment" "ORATIO_MODELS_DIR"
    DeleteRegKey HKCU "Environment" "ORATIO_TTS_PROVIDER"
    
SectionEnd
