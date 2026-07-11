// app_loopback_capture.exe --pid <PID>
//
// Captura o audio de loopback de UM processo especifico (+ arvore de
// processos filhos) via a API de loopback POR PROCESSO do Windows
// (AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK, Windows 10 build 19041+/
// 2004+) e streama PCM int16 cru pela saida padrao (stdout, binario).
//
// A logica de ativacao/inicializacao/captura e baseada na amostra oficial da
// Microsoft (github.com/microsoft/Windows-classic-samples,
// Samples/ApplicationLoopback) — verificada linha a linha antes de escrever
// este arquivo, nao reconstruida de memoria. Reescrita aqui com COM/threads
// puros (sem WRL/WIL/Media Foundation) pra manter o binario simples, sem
// dependencias externas de build (sem NuGet).
//
// Formato de captura FIXO (48000Hz, estereo, 16 bits) — a amostra oficial da
// Microsoft usa exatamente essa abordagem (formato fixo + a flag
// AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM, que faz o proprio Windows converter o
// audio pro formato pedido) em vez de negociar o formato nativo do processo
// via GetMixFormat — assim o lado Python nunca precisa lidar com float nem
// com um formato variavel.
//
// Protocolo de saida (stdout, binario):
//   16 bytes de cabecalho: magic "ALC1" (4), sample_rate u32 LE (4),
//   channels u16 LE (2), bits_per_sample u16 LE (2, sempre 16), format_tag
//   u16 LE (2, sempre 1 = PCM), reservado u16 LE (2, sempre 0).
//   Depois: fluxo continuo de PCM int16 intercalado.
//
// Codigos de saida: 0 = processo-alvo terminou (desconexao normal, nao e
// erro); 2 = argumentos invalidos; 3 = falha ao ativar/inicializar/capturar.

#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <audioclientactivationparams.h>
#include <objidl.h>

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <io.h>
#include <vector>

#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "mmdevapi.lib")
#pragma comment(lib, "uuid.lib")

namespace {

constexpr UINT32 TARGET_SAMPLE_RATE = 48000;
constexpr UINT16 TARGET_CHANNELS = 2;
constexpr UINT16 TARGET_BITS_PER_SAMPLE = 16;
constexpr WORD WAVE_FORMAT_PCM_TAG = 1;  // WAVE_FORMAT_PCM, evita depender de mmreg.h

#pragma pack(push, 1)
struct WireHeader {
    char magic[4];
    uint32_t sample_rate;
    uint16_t channels;
    uint16_t bits_per_sample;
    uint16_t format_tag;
    uint16_t reserved;
};
#pragma pack(pop)
static_assert(sizeof(WireHeader) == 16, "WireHeader deve ter exatamente 16 bytes");

std::atomic<bool> g_stopRequested{false};

void LogError(const wchar_t* msg, HRESULT hr = S_OK) {
    if (hr != S_OK) {
        fwprintf(stderr, L"ERROR: %s (hr=0x%08lX)\n", msg, static_cast<unsigned long>(hr));
    } else {
        fwprintf(stderr, L"ERROR: %s\n", msg);
    }
    fflush(stderr);
}

bool WriteAllToStdout(const void* data, size_t size) {
    const char* p = static_cast<const char*>(data);
    size_t remaining = size;
    const int fd = _fileno(stdout);
    while (remaining > 0) {
        unsigned int chunk = remaining > 0x00100000u ? 0x00100000u : static_cast<unsigned int>(remaining);
        int written = _write(fd, p, chunk);
        if (written <= 0) {
            return false;
        }
        p += written;
        remaining -= static_cast<size_t>(written);
    }
    return true;
}

BOOL WINAPI ConsoleHandler(DWORD signal) {
    if (signal == CTRL_C_EVENT || signal == CTRL_BREAK_EVENT || signal == CTRL_CLOSE_EVENT) {
        g_stopRequested = true;
        return TRUE;
    }
    return FALSE;
}

DWORD WINAPI ProcessWatchThread(LPVOID param) {
    HANDLE h = static_cast<HANDLE>(param);
    WaitForSingleObject(h, INFINITE);
    g_stopRequested = true;
    return 0;
}

// ── handler de conclusao de ActivateAudioInterfaceAsync (COM puro, sem WRL) ─
class ActivationCompletionHandler : public IActivateAudioInterfaceCompletionHandler {
public:
    ActivationCompletionHandler() {
        m_event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        // ActivateAudioInterfaceAsync entrega o callback de conclusao numa
        // thread MTA gerenciada pelo sistema — sem marcar este objeto como
        // "agil" (agile object), a chamada falha com E_ILLEGAL_METHOD_CALL
        // (confirmado na documentacao oficial da propria funcao). A amostra
        // da Microsoft resolve isso com o mixin FtmBase do WRL; sem WRL,
        // respondemos IID_IAgileObject diretamente (marcador sem metodos) E
        // agregamos um marshaler livre-de-thread pra IID_IMarshal — as duas
        // formas documentadas de marcar um objeto COM como agil.
        HRESULT hrFtm = CoCreateFreeThreadedMarshaler(
            static_cast<IActivateAudioInterfaceCompletionHandler*>(this), &m_marshaler);
        if (FAILED(hrFtm)) {
            fwprintf(stderr, L"AVISO: CoCreateFreeThreadedMarshaler falhou (hr=0x%08lX)\n",
                     static_cast<unsigned long>(hrFtm));
            fflush(stderr);
        }
    }

    ~ActivationCompletionHandler() {
        if (m_marshaler) {
            m_marshaler->Release();
        }
        if (m_event) {
            CloseHandle(m_event);
        }
    }

    // IUnknown
    STDMETHODIMP QueryInterface(REFIID riid, void** ppv) override {
        if (riid == __uuidof(IUnknown) || riid == __uuidof(IActivateAudioInterfaceCompletionHandler)) {
            *ppv = static_cast<IActivateAudioInterfaceCompletionHandler*>(this);
            AddRef();
            return S_OK;
        }
        if (riid == __uuidof(IAgileObject)) {
            // Marcador puro (sem metodos alem dos de IUnknown) — sinaliza que
            // este objeto pode ser chamado de qualquer apartamento sem proxy.
            *ppv = static_cast<IActivateAudioInterfaceCompletionHandler*>(this);
            AddRef();
            return S_OK;
        }
        if (riid == __uuidof(IMarshal) && m_marshaler) {
            return m_marshaler->QueryInterface(riid, ppv);
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    STDMETHODIMP_(ULONG) AddRef() override {
        return static_cast<ULONG>(InterlockedIncrement(&m_ref));
    }
    STDMETHODIMP_(ULONG) Release() override {
        LONG r = InterlockedDecrement(&m_ref);
        if (r == 0) {
            delete this;
        }
        return static_cast<ULONG>(r);
    }

    // IActivateAudioInterfaceCompletionHandler — chamado numa thread MTA do
    // sistema quando o resultado da ativacao fica pronto.
    STDMETHODIMP ActivateCompleted(IActivateAudioInterfaceAsyncOperation* operation) override {
        HRESULT hrActivate = E_UNEXPECTED;
        IUnknown* punkAudioInterface = nullptr;
        HRESULT hr = operation->GetActivateResult(&hrActivate, &punkAudioInterface);
        if (SUCCEEDED(hr)) {
            hr = hrActivate;
        }
        if (SUCCEEDED(hr) && punkAudioInterface) {
            hr = punkAudioInterface->QueryInterface(IID_PPV_ARGS(&m_audioClient));
        }
        if (punkAudioInterface) {
            punkAudioInterface->Release();
        }
        m_result = hr;
        SetEvent(m_event);
        return S_OK;
    }

    // Espera a ativacao terminar. Em sucesso, devolve um IAudioClient com uma
    // referencia propria (o chamador precisa dar Release() nele).
    HRESULT Wait(DWORD timeoutMs, HRESULT* outResult, IAudioClient** outClient) {
        DWORD wr = WaitForSingleObject(m_event, timeoutMs);
        if (wr != WAIT_OBJECT_0) {
            return E_ABORT;
        }
        *outResult = m_result;
        *outClient = m_audioClient;
        if (m_audioClient) {
            m_audioClient->AddRef();
        }
        return S_OK;
    }

private:
    volatile LONG m_ref = 1;
    HANDLE m_event = nullptr;
    HRESULT m_result = E_UNEXPECTED;
    IAudioClient* m_audioClient = nullptr;
    IUnknown* m_marshaler = nullptr;
};

DWORD ParsePid(int argc, wchar_t* argv[]) {
    for (int i = 1; i < argc - 1; i++) {
        if (wcscmp(argv[i], L"--pid") == 0) {
            return wcstoul(argv[i + 1], nullptr, 0);
        }
    }
    return 0;
}

}  // namespace

int wmain(int argc, wchar_t* argv[]) {
    DWORD targetPid = ParsePid(argc, argv);
    if (targetPid == 0) {
        fwprintf(stderr, L"Uso: app_loopback_capture.exe --pid <PID>\n");
        return 2;
    }

    SetConsoleCtrlHandler(ConsoleHandler, TRUE);
    _setmode(_fileno(stdout), _O_BINARY);  // critico no Windows: sem isso o
                                            // modo texto corrompe o PCM (CRLF)

    HANDLE targetProcess = OpenProcess(SYNCHRONIZE, FALSE, targetPid);
    if (!targetProcess) {
        LogError(L"Nao foi possivel abrir o processo-alvo (ja fechou?)");
        return 3;
    }
    CreateThread(nullptr, 0, ProcessWatchThread, targetProcess, 0, nullptr);

    HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(hr)) {
        LogError(L"CoInitializeEx falhou", hr);
        CloseHandle(targetProcess);
        return 3;
    }

    AUDIOCLIENT_ACTIVATION_PARAMS activationParams = {};
    activationParams.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK;
    activationParams.ProcessLoopbackParams.TargetProcessId = targetPid;
    activationParams.ProcessLoopbackParams.ProcessLoopbackMode = PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE;

    PROPVARIANT activateParams = {};
    activateParams.vt = VT_BLOB;
    activateParams.blob.cbSize = sizeof(activationParams);
    activateParams.blob.pBlobData = reinterpret_cast<BYTE*>(&activationParams);

    ActivationCompletionHandler* handler = new ActivationCompletionHandler();
    IActivateAudioInterfaceAsyncOperation* asyncOp = nullptr;

    hr = ActivateAudioInterfaceAsync(
        VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK,
        __uuidof(IAudioClient),
        &activateParams,
        handler,
        &asyncOp);

    if (FAILED(hr)) {
        LogError(L"ActivateAudioInterfaceAsync falhou", hr);
        handler->Release();
        CoUninitialize();
        CloseHandle(targetProcess);
        return 3;
    }

    HRESULT activateResult = E_UNEXPECTED;
    IAudioClient* audioClient = nullptr;
    hr = handler->Wait(10000, &activateResult, &audioClient);
    if (asyncOp) {
        asyncOp->Release();
    }
    handler->Release();

    if (FAILED(hr) || FAILED(activateResult) || !audioClient) {
        LogError(L"Falha ao ativar a interface de audio do processo (ele tem sessao de audio?)",
                 FAILED(activateResult) ? activateResult : hr);
        CoUninitialize();
        CloseHandle(targetProcess);
        return 3;
    }

    WAVEFORMATEX captureFormat = {};
    captureFormat.wFormatTag = WAVE_FORMAT_PCM_TAG;
    captureFormat.nChannels = TARGET_CHANNELS;
    captureFormat.nSamplesPerSec = TARGET_SAMPLE_RATE;
    captureFormat.wBitsPerSample = TARGET_BITS_PER_SAMPLE;
    captureFormat.nBlockAlign = static_cast<WORD>(captureFormat.nChannels * captureFormat.wBitsPerSample / 8);
    captureFormat.nAvgBytesPerSec = captureFormat.nSamplesPerSec * captureFormat.nBlockAlign;
    captureFormat.cbSize = 0;

    hr = audioClient->Initialize(
        AUDCLNT_SHAREMODE_SHARED,
        AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK | AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM,
        0, 0, &captureFormat, nullptr);
    if (FAILED(hr)) {
        LogError(L"IAudioClient::Initialize falhou", hr);
        audioClient->Release();
        CoUninitialize();
        CloseHandle(targetProcess);
        return 3;
    }

    HANDLE sampleReadyEvent = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    hr = audioClient->SetEventHandle(sampleReadyEvent);
    if (FAILED(hr)) {
        LogError(L"SetEventHandle falhou", hr);
        audioClient->Release();
        CoUninitialize();
        CloseHandle(targetProcess);
        CloseHandle(sampleReadyEvent);
        return 3;
    }

    IAudioCaptureClient* captureClient = nullptr;
    hr = audioClient->GetService(IID_PPV_ARGS(&captureClient));
    if (FAILED(hr)) {
        LogError(L"GetService(IAudioCaptureClient) falhou", hr);
        audioClient->Release();
        CoUninitialize();
        CloseHandle(targetProcess);
        CloseHandle(sampleReadyEvent);
        return 3;
    }

    WireHeader header{};
    memcpy(header.magic, "ALC1", 4);
    header.sample_rate = TARGET_SAMPLE_RATE;
    header.channels = TARGET_CHANNELS;
    header.bits_per_sample = TARGET_BITS_PER_SAMPLE;
    header.format_tag = 1;
    header.reserved = 0;
    if (!WriteAllToStdout(&header, sizeof(header))) {
        LogError(L"Falha ao escrever o cabecalho na saida padrao");
        captureClient->Release();
        audioClient->Release();
        CoUninitialize();
        CloseHandle(targetProcess);
        CloseHandle(sampleReadyEvent);
        return 3;
    }

    hr = audioClient->Start();
    if (FAILED(hr)) {
        LogError(L"IAudioClient::Start falhou", hr);
        captureClient->Release();
        audioClient->Release();
        CoUninitialize();
        CloseHandle(targetProcess);
        CloseHandle(sampleReadyEvent);
        return 3;
    }

    bool streamError = false;
    std::vector<char> silenceBuf;

    while (!g_stopRequested.load()) {
        DWORD wr = WaitForSingleObject(sampleReadyEvent, 500);
        if (wr != WAIT_OBJECT_0) {
            continue;  // timeout: so uma chance de reavaliar g_stopRequested
        }

        UINT32 framesAvailable = 0;
        while (SUCCEEDED(captureClient->GetNextPacketSize(&framesAvailable)) && framesAvailable > 0) {
            BYTE* data = nullptr;
            DWORD flags = 0;
            hr = captureClient->GetBuffer(&data, &framesAvailable, &flags, nullptr, nullptr);
            if (FAILED(hr)) {
                streamError = true;
                break;
            }

            DWORD bytesToWrite = framesAvailable * captureFormat.nBlockAlign;
            bool ok;
            if (flags & AUDCLNT_BUFFERFLAGS_SILENT) {
                // silencio: escreve zeros pra manter a cadencia de bytes
                // consistente (o lado Python conta com um fluxo continuo)
                if (silenceBuf.size() < bytesToWrite) {
                    silenceBuf.assign(bytesToWrite, 0);
                }
                ok = WriteAllToStdout(silenceBuf.data(), bytesToWrite);
            } else {
                ok = WriteAllToStdout(data, bytesToWrite);
            }

            captureClient->ReleaseBuffer(framesAvailable);
            if (!ok) {
                streamError = true;
                break;
            }
        }
        if (streamError) {
            break;
        }
    }

    audioClient->Stop();
    captureClient->Release();
    audioClient->Release();
    CoUninitialize();
    CloseHandle(sampleReadyEvent);
    CloseHandle(targetProcess);

    return streamError ? 3 : 0;
}
