// dotnet/PirateEngineBridge.cs
//
// Hyper-Spherical Systems — Native C# P/Invoke Bridge for .NET / WinForms / WPF
//
// Binds directly to the compiled C++ DLL (python_bridge.dll / pirate_bridge.dll).
// All core IP logic (SISSI, 5+1 Homophonic, M2M prose elimination, key zeroing)
// runs inside compiled, native C++ machine code — protecting your proprietary IP.
//
// Usage:
//   using var session = new PirateSession();
//   string handshakeIndex = session.BuildHandshakeIndex();
//   var (encoded, tokensIn, tokensOut) = session.Encode("Based on the context...");
//   string decoded = session.Decode(encodedResponse);
//   session.Teardown(); // Zeroes key material in C++ memory
//
// License: Proprietary / Commercial

using System;
using System.Runtime.InteropServices;
using System.Text;

namespace HyperSpherical.Engine
{
    public class NativeBridge
    {
        private const string DllName = "python_bridge.dll"; // or pirate_bridge.dll

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl, EntryPoint = "tess_session_create")]
        public static extern IntPtr SessionCreate(ulong seed);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl, EntryPoint = "tess_session_destroy")]
        public static extern void SessionDestroy(IntPtr sessionPtr);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl, EntryPoint = "tess_session_encode", CharSet = CharSet.Ansi)]
        public static extern int SessionEncode(IntPtr sessionPtr, string plaintext, StringBuilder outBuf, int outCap, out int tokensIn, out int tokensOut);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl, EntryPoint = "tess_session_decode", CharSet = CharSet.Ansi)]
        public static extern int SessionDecode(IntPtr sessionPtr, string encoded, StringBuilder outBuf, int outCap);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl, EntryPoint = "tess_session_build_index", CharSet = CharSet.Ansi)]
        public static extern int SessionBuildIndex(IntPtr sessionPtr, StringBuilder outBuf, int outCap);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl, EntryPoint = "tess_session_teardown")]
        public static extern void SessionTeardown(IntPtr sessionPtr);
    }

    public class PirateSession : IDisposable
    {
        private IntPtr _handle;
        private bool _disposed;

        public string SessionToken { get; private; }
        public int TotalTokensIn { get; private; }
        public int TotalTokensOut { get; private; }
        public int TotalTokensSaved => Math.Max(0, TotalTokensIn - TotalTokensOut);
        public float OverallRatio => TotalTokensOut > 0 ? (float)TotalTokensIn / TotalTokensOut : 1.0f;

        public PirateSession(ulong seed = 0)
        {
            _handle = NativeBridge.SessionCreate(seed);
            if (_handle == IntPtr.Zero)
            {
                throw new InvalidOperationException("Failed to allocate native PirateSession in C++ engine.");
            }
            SessionToken = Guid.NewGuid().ToString("N").Substring(0, 8).ToUpper();
        }

        public string BuildHandshakeIndex()
        {
            CheckDisposed();
            var sb = new StringBuilder(8192);
            int res = NativeBridge.SessionBuildIndex(_handle, sb, sb.Capacity);
            return res >= 0 ? sb.ToString() : string.Empty;
        }

        public (string Encoded, int TokensIn, int TokensOut) Encode(string plaintext)
        {
            CheckDisposed();
            var sb = new StringBuilder(plaintext.Length * 3 + 1024);
            int res = NativeBridge.SessionEncode(_handle, plaintext, sb, sb.Capacity, out int inTok, out int outTok);
            if (res >= 0)
            {
                TotalTokensIn += inTok;
                TotalTokensOut += outTok;
                return (sb.ToString(), inTok, outTok);
            }
            return (plaintext, 0, 0);
        }

        public string Decode(string encodedText)
        {
            CheckDisposed();
            var sb = new StringBuilder(encodedText.Length * 3 + 1024);
            int res = NativeBridge.SessionDecode(_handle, encodedText, sb, sb.Capacity);
            return res >= 0 ? sb.ToString() : encodedText;
        }

        public void Teardown()
        {
            if (_handle != IntPtr.Zero)
            {
                NativeBridge.SessionTeardown(_handle);
            }
        }

        private void CheckDisposed()
        {
            if (_disposed || _handle == IntPtr.Zero)
                throw new ObjectDisposedException(nameof(PirateSession));
        }

        public void Dispose()
        {
            if (!_disposed)
            {
                Teardown();
                if (_handle != IntPtr.Zero)
                {
                    NativeBridge.SessionDestroy(_handle);
                    _handle = IntPtr.Zero;
                }
                _disposed = true;
            }
            GC.SuppressFinalize(this);
        }

        ~PirateSession()
        {
            Dispose();
        }
    }
}
