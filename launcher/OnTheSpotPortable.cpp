// Native Win32 PortableApps launcher. No script-to-exe wrapping, no admin rights.
// SPDX-License-Identifier: MIT (launcher); OnTheSpot itself is GPL-2.0.
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <string>
#include <vector>
#include <filesystem>
namespace fs = std::filesystem;

static HANDLE g_child = nullptr;
static bool g_userStopped = false;
static constexpr UINT_PTR MONITOR_TIMER = 55;
static constexpr int STOP_BUTTON = 101;

static std::wstring quoted(const std::wstring& s) {
    std::wstring out=L"\"";
    size_t n=0;
    for(wchar_t c:s){
        if(c==L'\\') {++n;continue;}
        if(c==L'"'){out.append(n*2+1,L'\\');out+=L'"';n=0;continue;}
        out.append(n,L'\\');n=0;out+=c;
    }
    out.append(n*2,L'\\');out+=L'"';return out;
}
static void fail(const std::wstring& msg){MessageBoxW(nullptr,msg.c_str(),L"OnTheSpot Portable",MB_OK|MB_ICONERROR);}

static LRESULT CALLBACK launcherWindow(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch(msg) {
      case WM_CREATE:
        CreateWindowW(L"STATIC",L"OnTheSpot is running locally in your web browser.",
                      WS_CHILD|WS_VISIBLE,22,20,405,23,hwnd,nullptr,nullptr,nullptr);
        CreateWindowW(L"STATIC",L"Keep this small launcher window open while using OnTheSpot.",
                      WS_CHILD|WS_VISIBLE,22,48,410,23,hwnd,nullptr,nullptr,nullptr);
        CreateWindowW(L"BUTTON",L"Stop OnTheSpot",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_PUSHBUTTON,
                      22,87,158,34,hwnd,reinterpret_cast<HMENU>(static_cast<INT_PTR>(STOP_BUTTON)),nullptr,nullptr);
        SetTimer(hwnd,MONITOR_TIMER,500,nullptr);
        return 0;
      case WM_COMMAND:
        if(LOWORD(wParam)==STOP_BUTTON){g_userStopped=true;DestroyWindow(hwnd);return 0;}
        break;
      case WM_TIMER:
        if(wParam==MONITOR_TIMER && g_child && WaitForSingleObject(g_child,0)==WAIT_OBJECT_0){
            DestroyWindow(hwnd);return 0;
        }
        break;
      case WM_CLOSE:
        g_userStopped=true;
        DestroyWindow(hwnd);return 0;
      case WM_DESTROY:
        KillTimer(hwnd,MONITOR_TIMER);
        PostQuitMessage(0);return 0;
    }
    return DefWindowProcW(hwnd,msg,wParam,lParam);
}

int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR,int){
    std::vector<wchar_t> path(32768);
    DWORD n=GetModuleFileNameW(nullptr,path.data(),static_cast<DWORD>(path.size()));
    if(n==0 || n>=path.size()){fail(L"Cannot locate the PortableApps launcher.");return 10;}
    const fs::path root=fs::path(std::wstring(path.data(),n)).parent_path();
    const fs::path python=root/L"App"/L"OnTheSpot"/L"runtime"/L"python.exe";
    const fs::path bootstrap=root/L"App"/L"OnTheSpot"/L"portable_bootstrap.py";
    if(!fs::is_regular_file(python) || !fs::is_regular_file(bootstrap)){
        fail(L"Portable application runtime is incomplete. Re-extract a validated ZIP. Existing Data must not be deleted.");return 11;
    }
    HANDLE mutex=CreateMutexW(nullptr,FALSE,L"Local\\OnTheSpotPortable_9D19B364_040E_4B16");
    if(!mutex){fail(L"Cannot create the application instance guard.");return 12;}
    if(GetLastError()==ERROR_ALREADY_EXISTS){fail(L"OnTheSpot Portable is already running. Close it before starting a second copy.");CloseHandle(mutex);return 13;}
    std::wstring cmd=quoted(python.wstring())+L" -I "+quoted(bootstrap.wstring());
    int argc=0;
    LPWSTR* argv=CommandLineToArgvW(GetCommandLineW(),&argc);
    if(!argv){fail(L"Unable to parse Windows command-line arguments.");CloseHandle(mutex);return 18;}
    for(int i=1;i<argc;i++)cmd+=L" "+quoted(argv[i]);
    LocalFree(argv);
    std::vector<wchar_t> command(cmd.begin(),cmd.end());command.push_back(0);
    STARTUPINFOW si{};si.cb=sizeof(si);
    PROCESS_INFORMATION pi{};
    const std::wstring cwd=(root/L"App"/L"OnTheSpot").wstring();
    HANDLE job=CreateJobObjectW(nullptr,nullptr);
    if(!job){fail(L"Cannot create process lifecycle guard.");CloseHandle(mutex);return 14;}
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION info{};
    info.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if(!SetInformationJobObject(job,JobObjectExtendedLimitInformation,&info,sizeof(info))){
        fail(L"Cannot configure child-process cleanup.");CloseHandle(job);CloseHandle(mutex);return 15;
    }
    // Unique same-user named event allows a graceful Uvicorn shutdown when
    // the user clicks Stop. Job close remains a crash/force-kill fallback.
    const std::wstring stopName=L"Local\\OnTheSpotPortableStop_"+std::to_wstring(GetCurrentProcessId());
    HANDLE stopEvent=CreateEventW(nullptr,TRUE,FALSE,stopName.c_str());
    if(!stopEvent){fail(L"Cannot create graceful-stop event.");CloseHandle(job);CloseHandle(mutex);return 21;}
    if(!SetEnvironmentVariableW(L"ONTHESPOT_STOP_EVENT",stopName.c_str())){
        fail(L"Cannot configure graceful server shutdown.");CloseHandle(stopEvent);CloseHandle(job);CloseHandle(mutex);return 22;
    }
    BOOL started=CreateProcessW(python.c_str(),command.data(),nullptr,nullptr,FALSE,
                CREATE_NO_WINDOW|CREATE_SUSPENDED|CREATE_NEW_PROCESS_GROUP,nullptr,cwd.c_str(),&si,&pi);
    SetEnvironmentVariableW(L"ONTHESPOT_STOP_EVENT",nullptr);
    if(!started){fail(L"Cannot start bundled Python runtime. Check package files and antivirus quarantine.");CloseHandle(stopEvent);CloseHandle(job);CloseHandle(mutex);return 16;}
    if(!AssignProcessToJobObject(job,pi.hProcess)){
        TerminateProcess(pi.hProcess,17);
        fail(L"Cannot attach OnTheSpot process to portable lifecycle guard.");
        CloseHandle(pi.hThread);CloseHandle(pi.hProcess);CloseHandle(stopEvent);CloseHandle(job);CloseHandle(mutex);return 17;
    }
    g_child=pi.hProcess;
    ResumeThread(pi.hThread);

    WNDCLASSEXW wc{};wc.cbSize=sizeof(wc);wc.lpfnWndProc=launcherWindow;
    wc.hInstance=instance;wc.lpszClassName=L"OnTheSpotPortableServerWindow";
    wc.hIcon=LoadIconW(instance,L"APPICON");wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);
    wc.hbrBackground=reinterpret_cast<HBRUSH>(COLOR_BTNFACE+1);
    if(!RegisterClassExW(&wc)){
        fail(L"Cannot register the OnTheSpot stop-control window.");
        CloseHandle(pi.hThread);CloseHandle(stopEvent);CloseHandle(job);CloseHandle(pi.hProcess);CloseHandle(mutex);return 19;
    }
    HWND hwnd=CreateWindowExW(0,wc.lpszClassName,L"OnTheSpot Portable - Running",
               WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,
               470,176,nullptr,nullptr,instance,nullptr);
    if(!hwnd){
        fail(L"Cannot create the OnTheSpot stop-control window.");
        CloseHandle(pi.hThread);CloseHandle(stopEvent);CloseHandle(job);CloseHandle(pi.hProcess);CloseHandle(mutex);return 20;
    }
    ShowWindow(hwnd,SW_SHOWNORMAL);
    UpdateWindow(hwnd);
    MSG msg{};
    while(GetMessageW(&msg,nullptr,0,0)>0){TranslateMessage(&msg);DispatchMessageW(&msg);}

    DWORD exitcode=0;
    bool finished=(WaitForSingleObject(pi.hProcess,0)==WAIT_OBJECT_0);
    if(finished)GetExitCodeProcess(pi.hProcess,&exitcode);
    if(g_userStopped && !finished){
        // Allow state, sessions and in-flight databases to flush before the
        // lifecycle job forces shutdown after a bounded grace period.
        SetEvent(stopEvent);
        WaitForSingleObject(pi.hProcess,15000);
    }
    CloseHandle(stopEvent);
    // Closing the Job Object terminates only processes owned by this launcher.
    CloseHandle(job);
    WaitForSingleObject(pi.hProcess,10000);
    CloseHandle(pi.hThread);CloseHandle(pi.hProcess);CloseHandle(mutex);
    if(finished && exitcode!=0 && !g_userStopped){
        fail(L"OnTheSpot exited unexpectedly. Check Data\\portable-startup-error.txt and Data\\Config\\logs. Your Data folder is preserved.");
        return static_cast<int>(exitcode);
    }
    return 0;
}
