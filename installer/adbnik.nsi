; NSIS 3 — optional alternative to Inno Setup
;   makensis installer\adbnik.nsi
; Or: powershell -File scripts\build_installer_nsis.ps1
;
; Install NSIS: https://nsis.sourceforge.io/Download

!include "MUI2.nsh"

!define PRODUCT_NAME "Adbnik"
!define PRODUCT_VERSION "0.2.0"
!define PRODUCT_PUBLISHER "Adbnik contributors"
!define APP_EXE "Adbnik.exe"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "..\dist_installer\Adbnik_Setup_${PRODUCT_VERSION}_nsis.exe"
InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"
RequestExecutionLevel admin
Unicode true

!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\adbnik.ico"
!define MUI_UNICON "..\assets\adbnik.ico"

!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${PRODUCT_NAME}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Application" SecApp
  SetShellVarContext all
  SetOutPath "$INSTDIR"
  ; PyInstaller onedir tree (paths relative to this .nsi file in installer/)
  File /r "..\dist\Adbnik\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "Publisher" "${PRODUCT_PUBLISHER}"
SectionEnd

Section Uninstall
  SetShellVarContext all
  RMDir /r "$INSTDIR"
  RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd
