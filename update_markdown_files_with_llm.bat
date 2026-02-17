@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%CD%"
set "SCRIPT_DIR=%~dp0"

cls
echo ================================================================
echo Markdown Updater - Batch LLM Runner
echo Root: %ROOT_DIR%
echo ================================================================
echo.
echo Choose the LLM to run for all .md files:
echo   1. Claude Sonnet
echo   2. Codex 5.3
echo   3. Gemini 3
echo.
set /p "LLM_CHOICE=Enter choice (1/2/3): "

set "LLM_NAME="
set "LLM_CMD="
set "LLM_MODEL="

if "%LLM_CHOICE%"=="1" (
    set "LLM_NAME=Claude Sonnet"
    set "LLM_MODEL=claude-sonnet-4-5-20250929"
    set "LLM_CMD=claude --dangerously-skip-permissions --model !LLM_MODEL! -p"
)
if "%LLM_CHOICE%"=="2" (
    set "LLM_NAME=Codex 5.3"
    set "LLM_MODEL=gpt-5.3-codex"
    set "LLM_CMD=codex exec --skip-git-repo-check --full-auto --model !LLM_MODEL! -"
)
if "%LLM_CHOICE%"=="3" (
    set "LLM_NAME=Gemini 3"
    set "LLM_MODEL=gemini-3-pro-preview"
    set "LLM_CMD=gemini --model !LLM_MODEL! --yolo"
)

if not defined LLM_NAME (
    echo.
    echo Invalid choice: "%LLM_CHOICE%"
    goto :END
)

echo.
echo Selected LLM: !LLM_NAME! (!LLM_MODEL!)
echo Searching for .md files under: %ROOT_DIR%
echo.

set /a FILE_COUNT=0
for /r "%ROOT_DIR%" %%F in (*.md) do (
    set /a FILE_COUNT+=1
)

if !FILE_COUNT! EQU 0 (
    echo No .md files found.
    goto :END
)

echo Found !FILE_COUNT! markdown file^(s^).
echo.

set /a INDEX=0
for /r "%ROOT_DIR%" %%F in (*.md) do (
    set /a INDEX+=1
    set "FILE_FULL=%%~fF"
    set "FILE_REL=%%~fF"
    set "FILE_REL=!FILE_REL:%ROOT_DIR%\=!"

    echo ---------------------------------------------------------------
    echo [!INDEX!/!FILE_COUNT!] Updating: !FILE_REL!
    echo LLM: !LLM_NAME!
    echo ---------------------------------------------------------------

    set "PROMPT_FILE=%TEMP%\agentharness_md_update_prompt_!RANDOM!!RANDOM!.txt"
    > "!PROMPT_FILE!" (
        echo update !FILE_REL!. make sure the information is correct and up to date with all the files. the point of this file is to allow any developer that has never seen the code in this folder to understand what each file is for and how it connects to other files. the idea is that any new developer can read this file instead of having to read the code files themselves. the point is that if a new developer that has never seen the project and is given a task he can read this file to be able to understand exactly what files he needs to look at to change and how he needs to change it to complete a task
    )

    call !LLM_CMD! < "!PROMPT_FILE!"
    set "CMD_EXIT=!ERRORLEVEL!"
    del /q "!PROMPT_FILE!" >nul 2>nul

    if not "!CMD_EXIT!"=="0" (
        echo [WARN] Command exited with code !CMD_EXIT! for !FILE_REL!
    )
    echo.
)

echo ================================================================
echo Completed markdown update run.
echo Processed !FILE_COUNT! file^(s^) with !LLM_NAME!.
echo ================================================================

:END
echo.
set /p "_EXIT=Press Enter to close..."
endlocal
