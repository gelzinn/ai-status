/* Share the CLI's Python/Qt runtime without linking a second C runtime.
 * CREATE_NO_WINDOW hides the console, not Qt's windows. Preserve redirected
 * standard handles and original arguments for diagnostics and collectors.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#define CAPACITY 32768

static void fail(void)
{
    MessageBoxW(NULL, L"AI Status could not start. Reinstall the app and try again.",
                L"AI Status", MB_OK | MB_ICONERROR);
    ExitProcess(1);
}

static void append(WCHAR *output, DWORD *length, const WCHAR *input)
{
    while (*input) {
        if (*length >= CAPACITY - 1) fail();
        output[(*length)++] = *input++;
    }
    output[*length] = L'\0';
}

void WINAPI wWinMainCRTStartup(void)
{
    HANDLE heap = GetProcessHeap();
    WCHAR *path = HeapAlloc(heap, HEAP_ZERO_MEMORY, CAPACITY * sizeof(WCHAR));
    WCHAR *command = HeapAlloc(heap, HEAP_ZERO_MEMORY, CAPACITY * sizeof(WCHAR));
    STARTUPINFOW *startup = HeapAlloc(heap, HEAP_ZERO_MEMORY, sizeof(STARTUPINFOW));
    PROCESS_INFORMATION *process = HeapAlloc(heap, HEAP_ZERO_MEMORY, sizeof(PROCESS_INFORMATION));
    const WCHAR *arguments = GetCommandLineW();
    DWORD length, commandLength = 0, exitCode = 1;
    HANDLE input = GetStdHandle(STD_INPUT_HANDLE);
    HANDLE output = GetStdHandle(STD_OUTPUT_HANDLE);
    HANDLE error = GetStdHandle(STD_ERROR_HANDLE);
    if (!path || !command || !startup || !process) fail();
    length = GetModuleFileNameW(NULL, path, CAPACITY);
    if (!length || length >= CAPACITY) fail();
    while (length && path[length - 1] != L'\\') --length;
    if (!length) fail();
    path[length] = L'\0';
    append(path, &length, L"ai-status-cli.exe");

    /* Skip only the executable token; preserve quoted/Unicode arguments. */
    if (*arguments == L'\"') {
        ++arguments;
        while (*arguments && *arguments != L'\"') ++arguments;
        if (*arguments) ++arguments;
    } else {
        while (*arguments && *arguments != L' ' && *arguments != L'\t') ++arguments;
    }
    append(command, &commandLength, L"\"");
    append(command, &commandLength, path);
    append(command, &commandLength, L"\"");
    append(command, &commandLength, arguments);
    startup->cb = sizeof(STARTUPINFOW);
    if (input && output && error && input != INVALID_HANDLE_VALUE &&
            output != INVALID_HANDLE_VALUE && error != INVALID_HANDLE_VALUE) {
        startup->dwFlags = STARTF_USESTDHANDLES;
        startup->hStdInput = input;
        startup->hStdOutput = output;
        startup->hStdError = error;
    }
    if (!CreateProcessW(path, command, NULL, NULL, TRUE, CREATE_NO_WINDOW,
                        NULL, NULL, startup, process)) fail();
    CloseHandle(process->hThread);
    WaitForSingleObject(process->hProcess, INFINITE);
    GetExitCodeProcess(process->hProcess, &exitCode);
    CloseHandle(process->hProcess);
    ExitProcess(exitCode);
}
